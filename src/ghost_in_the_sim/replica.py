"""複製配備された危機対応AIを3方式で比較するMVP orchestration。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .decision import (
    DecisionContext,
    DecisionEngine,
    DecisionRecord,
    DecisionValidationError,
    ReplicaAction,
    ReplicaMode,
    RuleDecisionEngine,
    safe_fallback,
)
from .engine import ActionInfluence, Condition, RunResult, run_experiment


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
