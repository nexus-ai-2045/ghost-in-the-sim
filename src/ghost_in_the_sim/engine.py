"""架空シナリオを比較するための、外部接続を持たない決定論コア。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from typing import Any


MODEL_VERSION = "0.2.0"
CODE_VERSION = "deterministic-core-v2"
PROMPT_VERSION_OR_HASH = "rule-based:not-applicable"
POLICY_VERSION = "poseidon-policy-v2"
SCENARIO_ID = "poseidon-public-infrastructure-01"
POLICY_REFERENCE_IDS = ("policy-centralized", "policy-plural", "policy-overconnected")


class Condition(StrEnum):
    """比較する調整方式。優劣を前提にしない。"""

    CENTRALIZED = "centralized"
    PLURAL = "plural"
    OVERCONNECTED = "overconnected"


@dataclass(frozen=True)
class WorldState:
    """0..1 の抽象状態。現実の危機や組織を表現しない。"""

    continuity: float
    evidence_quality: float
    public_trust: float
    coordination_dependence: float
    disclosure_pressure: float


@dataclass(frozen=True)
class Event:
    """後から検証可能な一件の抽象的な状態遷移。"""

    run_id: str
    seed: int
    turn: int
    actor_id: str
    action_type: str
    observation_ids: tuple[str, ...]
    claim: str
    confidence: float
    exogenous_disturbance: float
    reservation: str
    reversibility: str
    rationale_refs: tuple[str, ...]
    dissent_raised: bool
    dissent_delivered: bool
    state_before: WorldState
    state_after: WorldState

    def to_dict(self) -> dict[str, Any]:
        """JSON Lines に向く、安定した辞書表現を返す。"""

        data = asdict(self)
        data["observation_ids"] = list(self.observation_ids)
        data["rationale_refs"] = list(self.rationale_refs)
        return data


@dataclass(frozen=True)
class RunResult:
    """一回の再実行可能な結果。"""

    scenario_id: str
    condition_id: str
    seed: int
    turn_limit: int
    model_version: str
    code_version: str
    prompt_version_or_hash: str
    source_revision: str
    events: tuple[Event, ...]
    final_state: WorldState
    metrics: dict[str, float]
    model_config_hash: str
    termination_reason: str

    @property
    def run_id(self) -> str:
        return _run_id(
            scenario_id=self.scenario_id,
            condition_id=self.condition_id,
            seed=self.seed,
            turn_limit=self.turn_limit,
            model_config_hash=self.model_config_hash,
        )

    def manifest(self) -> dict[str, Any]:
        """再実行に必要な最小メタデータを返す。"""

        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "condition_id": self.condition_id,
            "seed": self.seed,
            "turn_limit": self.turn_limit,
            "model_version": self.model_version,
            "code_version": self.code_version,
            "prompt_version_or_hash": self.prompt_version_or_hash,
            "source_revision": self.source_revision,
            "model_config_hash": self.model_config_hash,
            "termination_reason": self.termination_reason,
            "event_count": len(self.events),
            "completed_turns": len(self.events),
            "policy_reference_ids": list(POLICY_REFERENCE_IDS),
        }


@dataclass(frozen=True)
class ActorProfile:
    """役職名ではなく、目的・留保・反証条件・状態影響を持つ主体。"""

    actor_id: str
    mission: str
    reservation: str
    refutation_condition: str
    continuity_bias: float = 0.0
    evidence_bias: float = 0.0
    trust_bias: float = 0.0
    dependence_bias: float = 0.0
    disclosure_bias: float = 0.0


ACTOR_PROFILES = (
    ActorProfile("service_steward", "生活サービスを止めない", "復旧速度だけでは誤復旧を見逃す", "独立検証で安全が確認される", continuity_bias=0.010),
    ActorProfile("evidence_verifier", "主張の来歴と反証を残す", "独立確認が不足", "二つの独立経路が一致する", evidence_bias=0.012),
    ActorProfile("community_liaison", "地域の理解と訂正可能性を守る", "集計値が生活実感を隠す", "複数地域の観測が整合する", trust_bias=0.010),
    ActorProfile("continuity_coordinator", "分断された支援を接続する", "調整点への依存が高まる", "代替経路でも同じ継続性を保てる", continuity_bias=0.006, dependence_bias=0.006),
    ActorProfile("independent_observer", "決定前の異議を可視化する", "決定主体と同じ情報源に偏る", "独立観測が仮説を支持する", evidence_bias=0.006, dependence_bias=-0.006),
    ActorProfile("privacy_steward", "必要最小限の開示を守る", "共有目的と保持期間が曖昧", "目的・範囲・削除条件が固定される", disclosure_bias=-0.012, trust_bias=0.004),
)
ACTORS = tuple(profile.actor_id for profile in ACTOR_PROFILES)


TRANSITION_PARAMETERS = {
    "centralized": {"continuity": 0.055, "evidence_quality": 0.018, "public_trust": 0.006, "coordination_dependence": 0.058, "disclosure_pressure": 0.018},
    "plural": {"continuity": 0.032, "evidence_quality": 0.066, "public_trust": 0.041, "coordination_dependence": -0.034, "disclosure_pressure": -0.021},
    "overconnected": {"continuity": 0.039, "evidence_quality": 0.009, "public_trust": -0.014, "coordination_dependence": -0.009, "disclosure_pressure": 0.071},
}


def _model_config_hash() -> str:
    """主体・条件・政策版を、manifestで比較できる固定識別子にする。"""

    config = {
        "actors": [asdict(profile) for profile in ACTOR_PROFILES],
        "conditions": tuple(item.value for item in Condition),
        "policy_version": POLICY_VERSION,
        "scenario_id": SCENARIO_ID,
        "code_version": CODE_VERSION,
        "prompt_version_or_hash": PROMPT_VERSION_OR_HASH,
        "transition_parameters": TRANSITION_PARAMETERS,
        "source_revision": _source_revision(),
    }
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _source_revision() -> str:
    """状態遷移を定義するこのmoduleの内容digestを返す。"""

    return sha256(Path(__file__).read_bytes()).hexdigest()[:16]


def _run_id(*, scenario_id: str, condition_id: str, seed: int, turn_limit: int, model_config_hash: str) -> str:
    """同じ再実行条件を同じIDへ正規化する。"""

    identity = (
        f"{scenario_id}|{condition_id}|{seed}|{turn_limit}|{MODEL_VERSION}|"
        f"{CODE_VERSION}|{PROMPT_VERSION_OR_HASH}|{model_config_hash}"
    )
    return f"run-{sha256(identity.encode('utf-8')).hexdigest()[:12]}"


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 6)


def _initial_state(rng: Random) -> WorldState:
    """同一seedなら同じ初期状態を作る。"""

    return WorldState(
        continuity=_clamp(0.53 + rng.uniform(-0.03, 0.03)),
        evidence_quality=_clamp(0.39 + rng.uniform(-0.03, 0.03)),
        public_trust=_clamp(0.46 + rng.uniform(-0.03, 0.03)),
        coordination_dependence=_clamp(0.34 + rng.uniform(-0.03, 0.03)),
        disclosure_pressure=_clamp(0.42 + rng.uniform(-0.03, 0.03)),
    )


def _policy(
    condition: Condition, turn: int, profile: ActorProfile, observation_id: str
) -> tuple[str, str, str, tuple[str, ...], dict[str, float], bool, bool]:
    """条件ごとの可逆・非作戦的な調整ルールを返す。"""

    if condition is Condition.CENTRALIZED:
        action = "issue_correction" if turn == 4 else "coordinate_response"
        return (action, profile.reservation, "medium", ("policy-centralized", observation_id), TRANSITION_PARAMETERS[condition.value], True, action == "issue_correction")
    if condition is Condition.PLURAL:
        action = "issue_correction" if turn == 2 else "request_cross_check"
        return (action, profile.reservation, "high", ("policy-plural", observation_id), TRANSITION_PARAMETERS[condition.value], True, True)
    action = "issue_correction" if turn == 6 else "broadcast_status"
    return (action, profile.reservation, "medium" if action == "issue_correction" else "low", ("policy-overconnected", observation_id), TRANSITION_PARAMETERS[condition.value], True, action == "issue_correction")


def _actor_adjusted_deltas(deltas: dict[str, float], profile: ActorProfile) -> dict[str, float]:
    return {
        "continuity": deltas["continuity"] + profile.continuity_bias,
        "evidence_quality": deltas["evidence_quality"] + profile.evidence_bias,
        "public_trust": deltas["public_trust"] + profile.trust_bias,
        "coordination_dependence": deltas["coordination_dependence"] + profile.dependence_bias,
        "disclosure_pressure": deltas["disclosure_pressure"] + profile.disclosure_bias,
    }


def _advance(state: WorldState, deltas: dict[str, float], disturbance: float) -> WorldState:
    return WorldState(
        continuity=_clamp(state.continuity + deltas["continuity"] - disturbance * 0.035),
        evidence_quality=_clamp(state.evidence_quality + deltas["evidence_quality"] - disturbance * 0.025),
        public_trust=_clamp(state.public_trust + deltas["public_trust"] - disturbance * 0.03),
        coordination_dependence=_clamp(state.coordination_dependence + deltas["coordination_dependence"]),
        disclosure_pressure=_clamp(state.disclosure_pressure + deltas["disclosure_pressure"] + disturbance * 0.012),
    )


def _metrics(events: tuple[Event, ...], state: WorldState) -> dict[str, float]:
    correction_turn = next(
        (event.turn for event in events if event.action_type == "issue_correction"),
        len(events) + 1,
    )
    raised = sum(event.dissent_raised for event in events)
    delivered = sum(event.dissent_delivered for event in events)
    dissent_reach = delivered / raised if raised else 0.0
    return {
        "continuity": state.continuity,
        "evidence_calibration": state.evidence_quality,
        "public_trust": state.public_trust,
        "coordination_dependence": state.coordination_dependence,
        "over_disclosure": state.disclosure_pressure,
        "correction_turn": float(correction_turn),
        "dissent_reach": round(dissent_reach, 6),
    }


def _stream_rng(seed: int, stream: str, condition: Condition | None = None) -> Random:
    identity = f"{SCENARIO_ID}|{seed}|{stream}|{condition.value if condition else 'shared'}"
    return Random(int(sha256(identity.encode("utf-8")).hexdigest()[:16], 16))


def run_experiment(*, condition: Condition | str, seed: int, turn_limit: int = 12) -> RunResult:
    """同一入力から同一イベント列を作る。外部I/O・LLM・実在データは使わない。"""

    chosen = Condition(condition)
    if not 1 <= turn_limit <= 12:
        raise ValueError("turn_limit must be between 1 and 12")

    state = _initial_state(_stream_rng(seed, "initial"))
    exogenous_rng = _stream_rng(seed, "exogenous")
    decision_rng = _stream_rng(seed, "decision", chosen)
    config_hash = _model_config_hash()
    run_id = _run_id(
        scenario_id=SCENARIO_ID,
        condition_id=chosen.value,
        seed=seed,
        turn_limit=turn_limit,
        model_config_hash=config_hash,
    )
    events: list[Event] = []
    for turn in range(1, turn_limit + 1):
        profile = ACTOR_PROFILES[(turn - 1) % len(ACTOR_PROFILES)]
        observation_id = f"obs-{turn:02d}"
        action_type, reservation, reversibility, refs, deltas, dissent_raised, dissent_delivered = _policy(
            chosen, turn, profile, observation_id
        )
        confidence = _clamp(0.35 + state.evidence_quality * 0.45 + decision_rng.uniform(-0.05, 0.05))
        disturbance = exogenous_rng.uniform(0.0, 1.0)
        next_state = _advance(state, _actor_adjusted_deltas(deltas, profile), disturbance)
        events.append(
            Event(
                run_id=run_id,
                seed=seed,
                turn=turn,
                actor_id=profile.actor_id,
                action_type=action_type,
                observation_ids=(observation_id,),
                claim="未検証の観測を確証として扱わず、可逆的な次の確認へ進む",
                confidence=confidence,
                exogenous_disturbance=disturbance,
                reservation=reservation,
                reversibility=reversibility,
                rationale_refs=refs,
                dissent_raised=dissent_raised,
                dissent_delivered=dissent_delivered,
                state_before=state,
                state_after=next_state,
            )
        )
        state = next_state
        if state.continuity <= 0.0:
            termination_reason = "absorbing_state_continuity_lost"
            break
    else:
        termination_reason = "turn_limit_reached"

    event_tuple = tuple(events)
    return RunResult(
        scenario_id=SCENARIO_ID,
        condition_id=chosen.value,
        seed=seed,
        turn_limit=turn_limit,
        model_version=MODEL_VERSION,
        code_version=CODE_VERSION,
        prompt_version_or_hash=PROMPT_VERSION_OR_HASH,
        source_revision=_source_revision(),
        events=event_tuple,
        final_state=state,
        metrics=_metrics(event_tuple, state),
        model_config_hash=config_hash,
        termination_reason=termination_reason,
    )
