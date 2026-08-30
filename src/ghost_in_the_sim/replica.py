"""複製配備された危機対応AIを3方式で比較するMVP orchestration。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable

from .agent_providers import ProposalProvider, RuleProposalProvider
from .agent_schedule import AgentRoundResult, OutcomeStatus, schedule_one_round
from .agent_turn import (
    AgentId,
    AgentTurnRequest,
    Authority,
    AuthorityStatus,
    Observation,
    RunRef,
    build_agent_descriptor,
)
from .decision import (
    DecisionContext,
    DecisionEngine,
    DecisionRecord,
    DecisionValidationError,
    ReplicaMode,
    RuleDecisionEngine,
    safe_fallback,
)
from .engine import ActionInfluence, Condition, RunResult, WorldState, run_experiment
from .evidence_contract import project_refutation_checks, project_sign_reversals
from .operative import MIKAGE_DEFAULT_PLAN, OperativePlan, OperativeState, evaluate_operative
from .scenario import KAGAMISHIO, ScenarioManifest


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
    scenario: ScenarioManifest = KAGAMISHIO
    operative_plan: OperativePlan = MIKAGE_DEFAULT_PLAN
    operative_state: OperativeState | None = None

    def __post_init__(self) -> None:
        if self.scenario.scenario_id != self.operative_plan.scenario_id:
            raise ValueError("operative plan must reference the selected scenario")
        if self.operative_state is None:
            object.__setattr__(self, "operative_state", evaluate_operative(self.operative_plan, completed_turns=len(self.result.events)))

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
            "scenario": self.scenario.to_dict(),
            "operative_plan": self.operative_plan.to_dict(),
            "operative_state": self.operative_state.to_dict(),
        }


@dataclass(frozen=True)
class ReplicaBatch:
    seeds: tuple[int, ...]
    runs: tuple[ReplicaRun, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"seeds": list(self.seeds), "runs": [run.to_dict() for run in self.runs]}


@dataclass(frozen=True)
class EnsembleRun:
    """4主体のproposalを合成し、既存決定論runtimeへ一つの影響として渡したrun。"""

    requested_mode: ReplicaMode
    effective_mode: ReplicaMode
    seed: int
    agent_rounds: tuple[AgentRoundResult, ...]
    applied_influences: tuple[ActionInfluence, ...]
    audit: DecisionAudit
    result: RunResult
    scenario: ScenarioManifest = KAGAMISHIO
    operative_plan: OperativePlan = MIKAGE_DEFAULT_PLAN
    operative_state: OperativeState | None = None

    def __post_init__(self) -> None:
        if self.scenario.scenario_id != self.operative_plan.scenario_id:
            raise ValueError("operative plan must reference the selected scenario")
        if self.operative_state is None:
            object.__setattr__(
                self,
                "operative_state",
                evaluate_operative(self.operative_plan, completed_turns=len(self.result.events)),
            )

    @property
    def decisions(self) -> tuple[DecisionRecord, ...]:
        """legacy bundle projectionと共有する。agent proposalをdecisionへ偽装しない。"""

        return ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_mode": self.requested_mode.value,
            "effective_mode": self.effective_mode.value,
            "seed": self.seed,
            "agent_rounds": [round_result.to_dict() for round_result in self.agent_rounds],
            "applied_influences": [asdict(influence) for influence in self.applied_influences],
            "audit": {
                **asdict(self.audit),
                "requested_mode": self.audit.requested_mode.value,
                "effective_mode": self.audit.effective_mode.value,
            },
            "manifest": self.result.manifest(),
            "metrics": self.result.metrics,
            "events": [event.to_dict() for event in self.result.events],
            "scenario": self.scenario.to_dict(),
            "operative_plan": self.operative_plan.to_dict(),
            "operative_state": self.operative_state.to_dict(),
        }


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


def _validate_runtime_scenario(scenario: ScenarioManifest, operative_plan: OperativePlan) -> None:
    """engineがKAGAMISHIO固定の間は別scenarioを黙って偽装しない。"""

    if scenario != KAGAMISHIO:
        raise ValueError("engine supports only the canonical scenario")
    if scenario.scenario_id != operative_plan.scenario_id:
        raise ValueError("operative plan must reference the selected scenario")


def run_replica_scenario(
    *,
    requested_mode: ReplicaMode | str,
    seed: int,
    turn_limit: int = 12,
    decision_engine: DecisionEngine | None = None,
    scenario: ScenarioManifest = KAGAMISHIO,
    operative_plan: OperativePlan = MIKAGE_DEFAULT_PLAN,
) -> ReplicaRun:
    if isinstance(turn_limit, bool) or not isinstance(turn_limit, int) or not 1 <= turn_limit <= len(scenario.beats):
        raise ValueError("turn_limit must fit within the selected scenario")
    _validate_runtime_scenario(scenario, operative_plan)
    for partner_action in operative_plan.partner_actions:
        if not 1 <= partner_action.turn <= len(scenario.beats):
            raise ValueError("partner action must fit within the selected scenario")
        if scenario.beats[partner_action.turn - 1].event_type != "partner_pause_requested":
            raise ValueError("request_pause must match the scenario partner pause beat")
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
    return ReplicaRun(mode, effective, seed, tuple(decisions), audit, result, scenario, operative_plan)


def run_replica_batch(
    *, seeds: Iterable[int] = DEFAULT_SEEDS, turn_limit: int = 12, decision_engine: DecisionEngine | None = None,
    scenario: ScenarioManifest = KAGAMISHIO, operative_plan: OperativePlan = MIKAGE_DEFAULT_PLAN,
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
            scenario=scenario,
            operative_plan=operative_plan,
        )
        for mode in ReplicaMode
        for seed in fixed_seeds
    )
    return ReplicaBatch(fixed_seeds, runs)


def _agent_requests_for_turn(
    *,
    mode: ReplicaMode,
    seed: int,
    turn: int,
    scenario: ScenarioManifest,
    operative_plan: OperativePlan,
    confirmed_state: WorldState | None = None,
) -> tuple[AgentTurnRequest, ...]:
    """外生beatと前turnで確定したworld stateから部分観測を分配する。"""

    beat = scenario.beats[turn - 1]
    common_id = beat.observation_ids[0]
    focus_id = f"{common_id}-{operative_plan.focus.value}-focus"
    scopes = {
        AgentId.MIKAGE: (common_id, focus_id),
        AgentId.MAKABE: (common_id, f"{common_id}-port-field"),
        AgentId.HOSPITAL_REPLICA: (f"{common_id}-hospital-local",),
        AgentId.PORT_REPLICA: (f"{common_id}-port-local",),
    }
    state_summary = (
        "初期状態（前turnなし）"
        if confirmed_state is None
        else (
            f"確定状態 continuity={confirmed_state.continuity:.6f}, "
            f"evidence={confirmed_state.evidence_quality:.6f}, "
            f"trust={confirmed_state.public_trust:.6f}, "
            f"dependence={confirmed_state.coordination_dependence:.6f}, "
            f"disclosure={confirmed_state.disclosure_pressure:.6f}"
        )
    )
    summaries = {
        AgentId.MIKAGE: f"{beat.event_type}: 選択した現場と共通来歴を照合; {state_summary}",
        AgentId.MAKABE: f"{beat.event_type}: 港湾側の物理現場から不可逆性を確認; {state_summary}",
        AgentId.HOSPITAL_REPLICA: f"{beat.event_type}: 病院の治療継続だけを局所観測; {state_summary}",
        AgentId.PORT_REPLICA: f"{beat.event_type}: 港湾の物流継続だけを局所観測; {state_summary}",
    }
    run_ref = RunRef(
        scenario_id=scenario.scenario_id,
        environment_seed=seed,
        condition_id=mode.value,
        turn=turn,
        round=1,
    )
    revoked_agent = _revoked_agent_for_turn(turn=turn, scenario=scenario, operative_plan=operative_plan)
    return tuple(
        AgentTurnRequest.create(
            run_ref=run_ref,
            agent=build_agent_descriptor(agent_id, observation_scope=scopes[agent_id]),
            authority=Authority(
                version="poseidon-policy-v4",
                status=(AuthorityStatus.REVOKED if agent_id is revoked_agent else AuthorityStatus.ACTIVE),
            ),
            observations=tuple(
                Observation(
                    observation_id=observation_id,
                    summary=summaries[agent_id],
                    evidence_refs=(observation_id,),
                )
                for observation_id in scopes[agent_id]
            ),
        )
        for agent_id in AgentId
    )


def _revoked_agent_for_turn(
    *, turn: int, scenario: ScenarioManifest, operative_plan: OperativePlan,
) -> AgentId | None:
    """確定済みのauthority convergenceを次turnの権限へ反映する。"""

    if turn <= 1 or scenario.beats[turn - 2].event_type != "authority_convergence_due":
        return None
    return {
        "hospital": AgentId.HOSPITAL_REPLICA,
        "port": AgentId.PORT_REPLICA,
        "defer": None,
    }[operative_plan.revocation_target.value]


def _compose_agent_round(round_result: AgentRoundResult) -> AgentRoundResult:
    """複数の採用候補をengineの1 turn 1 influence契約へ決定論的に収束する。"""

    candidates = [
        outcome for outcome in round_result.outcomes
        if outcome.status is OutcomeStatus.APPLIED and outcome.influence is not None
    ]
    selected = None
    if candidates:
        selected = (
            candidates[(round_result.run_ref.turn - 1) % len(candidates)]
            if round_result.run_ref.condition_id == "autonomous"
            else candidates[0]
        )
    outcomes = tuple(
        replace(
            outcome,
            status=OutcomeStatus.REJECTED,
            influence=None,
            reason_code="proposal_not_selected",
        )
        if outcome.status is OutcomeStatus.APPLIED and outcome is not selected
        else outcome
        for outcome in round_result.outcomes
    )
    return AgentRoundResult(run_ref=round_result.run_ref, outcomes=outcomes)


def run_ensemble_scenario(
    *,
    requested_mode: ReplicaMode | str,
    seed: int,
    turn_limit: int = 12,
    proposal_provider: ProposalProvider | None = None,
    scenario: ScenarioManifest = KAGAMISHIO,
    operative_plan: OperativePlan = MIKAGE_DEFAULT_PLAN,
) -> EnsembleRun:
    """4主体を毎turn一度だけ実行し、既存runtimeへ有界なActionInfluenceを渡す。"""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(turn_limit, bool) or not isinstance(turn_limit, int) or not 1 <= turn_limit <= len(scenario.beats):
        raise ValueError("turn_limit must fit within the selected scenario")
    _validate_runtime_scenario(scenario, operative_plan)
    mode = ReplicaMode(requested_mode)
    provider = proposal_provider or RuleProposalProvider()
    rounds: list[AgentRoundResult] = []
    influences: list[ActionInfluence] = []
    fallback_reasons: list[str] = []
    confirmed_state: WorldState | None = None
    for turn in range(1, turn_limit + 1):
        round_result = _compose_agent_round(
            schedule_one_round(
                _agent_requests_for_turn(
                    mode=mode,
                    seed=seed,
                    turn=turn,
                    scenario=scenario,
                    operative_plan=operative_plan,
                    confirmed_state=confirmed_state,
                ),
                provider,
            )
        )
        rounds.append(round_result)
        fallback_reasons.extend(
            outcome.reason_code
            for outcome in round_result.outcomes
            if outcome.status is OutcomeStatus.FALLBACK and outcome.reason_code
        )
        applied = next(
            (
                outcome.influence
                for outcome in round_result.outcomes
                if outcome.status is OutcomeStatus.APPLIED and outcome.influence is not None
            ),
            None,
        )
        if applied is None:
            applied = next(
                (
                    outcome.influence
                    for outcome in round_result.outcomes
                    if outcome.status is OutcomeStatus.FALLBACK and outcome.influence is not None
                ),
                None,
            )
        if applied is not None:
            influences.append(applied)
        confirmed_state = run_experiment(
            condition=_CONDITION_BY_MODE[mode],
            seed=seed,
            turn_limit=turn,
            action_influences=tuple(influences),
        ).final_state

    result = run_experiment(
        condition=_CONDITION_BY_MODE[mode],
        seed=seed,
        turn_limit=turn_limit,
        action_influences=tuple(influences),
    )
    reason = fallback_reasons[0] if fallback_reasons else "agent_turns_completed"
    audit = DecisionAudit(mode, mode, bool(fallback_reasons), reason)
    return EnsembleRun(
        requested_mode=mode,
        effective_mode=mode,
        seed=seed,
        agent_rounds=tuple(rounds),
        applied_influences=tuple(influences),
        audit=audit,
        result=result,
        scenario=scenario,
        operative_plan=operative_plan,
    )
