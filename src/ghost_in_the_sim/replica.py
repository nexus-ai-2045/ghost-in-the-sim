"""複製配備された危機対応AIを3方式で比較するMVP orchestration。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .decision import (
    DecisionContext,
    DecisionEngine,
    DecisionRecord,
    DecisionValidationError,
    ReplicaMode,
    RuleDecisionEngine,
    safe_fallback,
)
from .engine import ActionInfluence, Condition, RunResult, run_experiment
from .evidence_contract import project_refutation_checks, project_sign_reversals


DEFAULT_SEEDS = (17, 42, 99)
_CONDITION_BY_MODE = {
    ReplicaMode.CENTRALIZED: Condition.CENTRALIZED,
    ReplicaMode.PLURAL: Condition.PLURAL,
    ReplicaMode.AUTONOMOUS: Condition.AUTONOMOUS,
}


@dataclass(frozen=True)
class DecisionAudit:
    requested_mode: ReplicaMode
    effective_mode: ReplicaMode
    fallback_applied: bool
    reason_code: str


@dataclass(frozen=True)
class ReplicaRun:
    requested_mode: ReplicaMode
    effective_mode: ReplicaMode
    seed: int
    decisions: tuple[DecisionRecord, ...]
    audit: DecisionAudit
    result: RunResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_mode": self.requested_mode.value,
            "effective_mode": self.effective_mode.value,
            "seed": self.seed,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "audit": {**asdict(self.audit), "requested_mode": self.audit.requested_mode.value, "effective_mode": self.audit.effective_mode.value},
            "manifest": self.result.manifest(),
            "metrics": self.result.metrics,
            "events": [event.to_dict() for event in self.result.events],
        }


@dataclass(frozen=True)
class ReplicaBatch:
    seeds: tuple[int, ...]
    runs: tuple[ReplicaRun, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"seeds": list(self.seeds), "runs": [run.to_dict() for run in self.runs]}


def classify_run_failure(result: RunResult) -> tuple[bool, tuple[str, ...]]:
    """RunResultだけから失敗を決定し、engineの実行経路と分離して検査可能にする。"""

    reasons = []
    if result.termination_reason != "turn_limit_reached":
        reasons.append(f"termination:{result.termination_reason}")
    completed_turns = len(result.events)
    if completed_turns != result.turn_limit:
        reasons.append(f"incomplete_turns:{completed_turns}/{result.turn_limit}")
    return bool(reasons), tuple(reasons)


def _representative_log_refs(result: RunResult) -> list[str]:
    if not result.events:
        return []
    selected = [result.events[0]]
    selected.extend(
        event
        for event in result.events
        if event.action_type in {"issue_correction", "request_cross_check"} or event.dissent_delivered
    )
    selected.append(result.events[-1])
    turns = list(dict.fromkeys(event.turn for event in selected))[:3]
    return [f"{result.run_id}#event-turn-{turn}" for turn in turns]


def build_result_card(batch: ReplicaBatch) -> dict[str, Any]:
    """比較batchを、結論ではなく検証可能な観測カードへ変換する。"""

    run_cards = []
    for run in batch.runs:
        failed, reasons = classify_run_failure(run.result)
        run_cards.append(
            {
                "run_id": run.result.run_id,
                "mode": run.requested_mode.value,
                "effective_mode": run.effective_mode.value,
                "seed": run.seed,
                "metrics": dict(run.result.metrics),
                "representative_log_refs": _representative_log_refs(run.result),
                "failed_run": failed,
                "failure_reasons": list(reasons),
                "termination_reason": run.result.termination_reason,
                "completed_turns": len(run.result.events),
                "turn_limit": run.result.turn_limit,
            }
        )

    raw_payload = batch.to_dict()
    checks = project_refutation_checks(raw_payload)
    sign_reversals = project_sign_reversals(raw_payload)

    sensitivity_by_mode: dict[str, dict[str, dict[str, float]]] = {}
    for mode in ReplicaMode:
        mode_runs = [
            run
            for run in batch.runs
            if run.requested_mode is mode and run.effective_mode is mode and not run.audit.fallback_applied
        ]
        if not mode_runs:
            continue
        metrics = sorted(set.intersection(*(set(run.result.metrics) for run in mode_runs)))
        sensitivity_by_mode[mode.value] = {}
        for metric in metrics:
            values = [run.result.metrics[metric] for run in mode_runs]
            sensitivity_by_mode[mode.value][metric] = {
                "min": min(values),
                "max": max(values),
                "range": round(max(values) - min(values), 6),
            }

    return {
        "schema_version": "result-card-v1",
        "run_count": len(run_cards),
        "runs": run_cards,
        "failure_runs": [card for card in run_cards if card["failed_run"]],
        "refutation_checks": checks,
        "seed_sensitivity": {
            "seeds": sorted(batch.seeds),
            "by_mode": sensitivity_by_mode,
            "plural_vs_centralized_sign_reversals": sign_reversals,
        },
        "limitations": [
            "synthetic_scenario_not_real_world_prediction",
            "parameter_sweep_not_run",
            "model_and_prompt_sensitivity_not_observable_without_live_llm",
            "no_single_winner_score",
        ],
    }


def run_replica_scenario(
    *,
    requested_mode: ReplicaMode | str,
    seed: int,
    turn_limit: int = 12,
    decision_engine: DecisionEngine | None = None,
) -> ReplicaRun:
    mode = ReplicaMode(requested_mode)
    engine = decision_engine or RuleDecisionEngine()
    fallback = False
    reason = "decision_accepted"
    decisions = []
    for decision_turn in range(1, min(3, turn_limit) + 1):
        context = DecisionContext.for_run(mode=mode, seed=seed, turn=decision_turn)
        try:
            decision = engine.decide(context)
        except DecisionValidationError as error:
            if not fallback:
                reason = error.reason_code
            fallback = True
            decision = safe_fallback(context, reason_code=error.reason_code)
        decisions.append(decision)
    effective = ReplicaMode.PLURAL if fallback else mode
    influences = tuple(
        ActionInfluence(turn=decision.issued_at_turn, action_type=decision.action.value, confidence=decision.confidence)
        for decision in decisions
    )
    result = run_experiment(
        condition=_CONDITION_BY_MODE[effective], seed=seed, turn_limit=turn_limit, action_influences=influences
    )
    audit = DecisionAudit(mode, effective, fallback, reason)
    return ReplicaRun(mode, effective, seed, tuple(decisions), audit, result)


def run_replica_batch(
    *, seeds: Iterable[int] = DEFAULT_SEEDS, turn_limit: int = 12, decision_engine: DecisionEngine | None = None
) -> ReplicaBatch:
    fixed_seeds = tuple(seeds)
    if not fixed_seeds or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in fixed_seeds):
        raise ValueError("seeds must be a non-empty integer sequence")
    if len(set(fixed_seeds)) != len(fixed_seeds):
        raise ValueError("seeds must be unique")
    runs = tuple(
        run_replica_scenario(
            requested_mode=mode,
            seed=seed,
            turn_limit=turn_limit,
            decision_engine=decision_engine,
        )
        for mode in ReplicaMode
        for seed in fixed_seeds
    )
    return ReplicaBatch(fixed_seeds, runs)
