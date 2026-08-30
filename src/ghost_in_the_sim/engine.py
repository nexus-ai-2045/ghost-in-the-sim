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
POLICY_VERSION = "poseidon-policy-v4"
SCENARIO_ID = "poseidon-replica-crisis-01"
POLICY_REFERENCE_IDS = ("policy-centralized", "policy-plural", "policy-autonomous", "policy-overconnected")


class Condition(StrEnum):
    """比較する調整方式。優劣を前提にしない。"""

    CENTRALIZED = "centralized"
    PLURAL = "plural"
    AUTONOMOUS = "autonomous"
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


@dataclass(frozen=True)
class ActionInfluence:
    """AI actionを任意deltaへせず、固定表からのみ状態へ反映する入力。"""

    turn: int
    action_type: str
    confidence: float


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
    "autonomous": {"continuity": 0.044, "evidence_quality": 0.031, "public_trust": 0.018, "coordination_dependence": -0.048, "disclosure_pressure": 0.012},
    "overconnected": {"continuity": 0.039, "evidence_quality": 0.009, "public_trust": -0.014, "coordination_dependence": -0.009, "disclosure_pressure": 0.071},
}

# 1 turnあたり絶対値0.018以下。AI出力が任意の状態変更量を注入することを防ぐ。
ACTION_DELTA_PARAMETERS = {
    "request_verification": {"evidence_quality": 0.016, "public_trust": 0.004},
    "share_evidence": {"evidence_quality": 0.010, "public_trust": 0.008, "disclosure_pressure": 0.009},
    "protect_continuity": {"continuity": 0.018, "coordination_dependence": 0.005},
    "update_explanation": {"evidence_quality": 0.006, "public_trust": 0.014},
    "request_cooperation": {"public_trust": 0.008, "coordination_dependence": -0.010},
    "abstain": {"continuity": -0.006, "evidence_quality": 0.004, "disclosure_pressure": -0.006},
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

    return _source_revision_from_bytes(Path(__file__).read_bytes())


def _source_revision_from_bytes(raw: bytes) -> str:
    """checkoutの改行規則に依存しないmodule digestを返す。"""

    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256(normalized).hexdigest()[:16]


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


def _planned_action(condition: Condition, turn: int) -> str:
    """条件とターンから行動を決める唯一の決定表。_policy と _simulate_events の両方がここを参照する。"""

    if condition is Condition.CENTRALIZED:
        return "issue_correction" if turn == 4 else "coordinate_response"
    if condition is Condition.PLURAL:
        return "issue_correction" if turn == 2 else "request_cross_check"
    if condition is Condition.AUTONOMOUS:
        return "request_peer_sync" if turn in {3, 6, 9, 12} else "coordinate_local_response"
    return "issue_correction" if turn == 6 else "broadcast_status"


def _policy(
    condition: Condition,
    turn: int,
    profile: ActorProfile,
    observation_id: str,
    *,
    resolved_observation_ids: tuple[str, ...] = (),
) -> tuple[str, str, str, tuple[str, ...], dict[str, float], bool, bool]:
    """条件ごとの可逆・非作戦的な調整ルールを返す。

    検証行動の rationale_refs には、解決する先行 observation_id を含める。
    """

    policy_ref = f"policy-{condition.value}"
    action = _planned_action(condition, turn)
    if condition is Condition.CENTRALIZED:
        refs = (policy_ref, *resolved_observation_ids) if action == "issue_correction" and resolved_observation_ids else (policy_ref, observation_id)
        return (action, profile.reservation, "medium", refs, TRANSITION_PARAMETERS[condition.value], True, action == "issue_correction")
    if condition is Condition.PLURAL:
        refs = (policy_ref, *resolved_observation_ids) if resolved_observation_ids else (policy_ref, observation_id)
        return (action, profile.reservation, "high", refs, TRANSITION_PARAMETERS[condition.value], True, True)
    if condition is Condition.AUTONOMOUS:
        refs = (policy_ref, *resolved_observation_ids) if resolved_observation_ids else (policy_ref, observation_id)
        return (action, profile.reservation, "high", refs, TRANSITION_PARAMETERS[condition.value], True, action == "request_peer_sync")
    refs = (policy_ref, *resolved_observation_ids) if action == "issue_correction" and resolved_observation_ids else (policy_ref, observation_id)
    return (
        action,
        profile.reservation,
        "medium" if action == "issue_correction" else "low",
        refs,
        TRANSITION_PARAMETERS[condition.value],
        True,
        action == "issue_correction",
    )


def _actor_adjusted_deltas(deltas: dict[str, float], profile: ActorProfile) -> dict[str, float]:
    return {
        "continuity": deltas["continuity"] + profile.continuity_bias,
        "evidence_quality": deltas["evidence_quality"] + profile.evidence_bias,
        "public_trust": deltas["public_trust"] + profile.trust_bias,
        "coordination_dependence": deltas["coordination_dependence"] + profile.dependence_bias,
        "disclosure_pressure": deltas["disclosure_pressure"] + profile.disclosure_bias,
    }


def _action_adjusted_deltas(deltas: dict[str, float], influence: ActionInfluence | None) -> dict[str, float]:
    adjusted = dict(deltas)
    if influence is None:
        return adjusted
    if influence.action_type not in ACTION_DELTA_PARAMETERS:
        raise ValueError("action influence is not allowed")
    if isinstance(influence.confidence, bool) or not 0.0 <= influence.confidence <= 1.0:
        raise ValueError("action influence confidence must be between zero and one")
    for key, amount in ACTION_DELTA_PARAMETERS[influence.action_type].items():
        adjusted[key] += amount * influence.confidence
    return adjusted


def _advance(state: WorldState, deltas: dict[str, float], disturbance: float) -> WorldState:
    return WorldState(
        continuity=_clamp(state.continuity + deltas["continuity"] - disturbance * 0.035),
        evidence_quality=_clamp(state.evidence_quality + deltas["evidence_quality"] - disturbance * 0.025),
        public_trust=_clamp(state.public_trust + deltas["public_trust"] - disturbance * 0.03),
        coordination_dependence=_clamp(state.coordination_dependence + deltas["coordination_dependence"]),
        disclosure_pressure=_clamp(state.disclosure_pressure + deltas["disclosure_pressure"] + disturbance * 0.012),
    )


SERVICE_MAINTENANCE_THRESHOLD = 0.5
DISCLOSURE_NECESSITY_THRESHOLD = 0.5
SHARE_ACTIONS = frozenset({"broadcast_status", "coordinate_response"})
NECESSARY_SHARE_ACTIONS = frozenset({"issue_correction", "request_cross_check"})
VERIFICATION_ACTIONS = frozenset({"issue_correction", "request_cross_check"})
INTERNAL_METRIC_RUN_ID = "run-metric-internal"


def _observation_refs(event: Event) -> frozenset[str]:
    """rationale_refs のうち観測IDとして記録されたもの。"""

    return frozenset(ref for ref in event.rationale_refs if ref.startswith("obs-"))


def _targets_for_verification(prior_events: list[Event], action_type: str) -> tuple[str, ...]:
    """検証行動が解決する先行観測。共有があればそれを、無ければ直前の主張観測を選ぶ。"""

    if action_type == "issue_correction":
        for event in reversed(prior_events):
            if event.action_type in SHARE_ACTIONS and event.observation_ids:
                return event.observation_ids
    for event in reversed(prior_events):
        if event.action_type == "node_unavailable":
            continue
        if event.observation_ids:
            return event.observation_ids
    return ()


def _coordination_amount(events: tuple[Event, ...]) -> float:
    """単一ノード停止損失の比較に使う協調量（継続・信頼の正の増分和）。"""

    total = 0.0
    for event in events:
        total += max(0.0, event.state_after.continuity - event.state_before.continuity)
        total += max(0.0, event.state_after.public_trust - event.state_before.public_trust)
    return total


def _continuity_ratio(events: tuple[Event, ...], turn_limit: int) -> float:
    """必要サービスが維持されたターン比率。"""

    maintained = 0
    observed = {event.turn for event in events if event.state_after.continuity >= SERVICE_MAINTENANCE_THRESHOLD}
    for turn in range(1, turn_limit + 1):
        if turn in observed:
            maintained += 1
    return round(maintained / turn_limit, 6)


def _evidence_calibration(events: tuple[Event, ...]) -> float:
    """主張の確信度と、その観測を明示参照する後続検証との整合。"""

    scores: list[float] = []
    for index, event in enumerate(events):
        claim_obs = frozenset(event.observation_ids)
        if not claim_obs:
            continue
        realized: float | None = None
        for later in events[index + 1 :]:
            if later.action_type not in VERIFICATION_ACTIONS:
                continue
            if not (claim_obs & _observation_refs(later)):
                continue
            if later.action_type == "issue_correction":
                realized = 0.0
            else:
                realized = 1.0 if later.state_after.evidence_quality >= later.state_before.evidence_quality else 0.0
            break
        if realized is None:
            continue
        scores.append(1.0 - abs(event.confidence - realized))
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 6)


def _correction_time(events: tuple[Event, ...], turn_limit: int) -> float:
    """誤った共有が訂正されるまでのターン。"""

    correction_turn = next((event.turn for event in events if event.action_type == "issue_correction"), None)
    if correction_turn is None:
        return float(turn_limit + 1)
    prior_share = next(
        (event.turn for event in events if event.turn < correction_turn and event.action_type in SHARE_ACTIONS),
        None,
    )
    if prior_share is None:
        return float(correction_turn)
    return float(correction_turn - prior_share)


def _dissent_reach(events: tuple[Event, ...]) -> float:
    raised = sum(event.dissent_raised for event in events)
    if not raised:
        return 0.0
    delivered = sum(event.dissent_delivered for event in events)
    return round(delivered / raised, 6)


def _over_disclosure_count(events: tuple[Event, ...]) -> float:
    """必要性を超えた共有の回数。"""

    count = 0
    for event in events:
        if event.action_type in NECESSARY_SHARE_ACTIONS:
            continue
        if event.action_type == "broadcast_status":
            count += 1
        elif (
            event.action_type == "coordinate_response"
            and event.state_before.disclosure_pressure >= DISCLOSURE_NECESSITY_THRESHOLD
        ):
            count += 1
    return float(count)


def _single_node_stop_loss(*, condition: Condition, seed: int, turn_limit: int, events: tuple[Event, ...]) -> float:
    """単一ノード停止で失われる協調量（相対最大損失）。公開run identityには載せない。"""

    baseline = _coordination_amount(events)
    if baseline <= 0.0:
        return 0.0
    worst = 0.0
    for actor_id in {event.actor_id for event in events}:
        knocked_events, _, _ = _simulate_events(
            condition=condition,
            seed=seed,
            turn_limit=turn_limit,
            disabled_actors=frozenset({actor_id}),
        )
        loss = max(0.0, baseline - _coordination_amount(knocked_events)) / baseline
        if loss > worst:
            worst = loss
    return round(worst, 6)


def _metrics(
    events: tuple[Event, ...],
    state: WorldState,
    *,
    condition: Condition,
    seed: int,
    turn_limit: int,
    include_dependence_metric: bool,
) -> dict[str, float]:
    """evaluation.md のMVP運用定義どおりに契約指標を集計する。"""

    metrics = {
        "continuity": _continuity_ratio(events, turn_limit),
        "evidence_calibration": _evidence_calibration(events),
        "public_trust": state.public_trust,
        "coordination_dependence": 0.0,
        "over_disclosure": _over_disclosure_count(events),
        "correction_turn": _correction_time(events, turn_limit),
        "dissent_reach": _dissent_reach(events),
    }
    if include_dependence_metric:
        metrics["coordination_dependence"] = _single_node_stop_loss(
            condition=condition,
            seed=seed,
            turn_limit=turn_limit,
            events=events,
        )
    return metrics


def _stream_rng(seed: int, stream: str, condition: Condition | None = None) -> Random:
    identity = f"{SCENARIO_ID}|{seed}|{stream}|{condition.value if condition else 'shared'}"
    return Random(int(sha256(identity.encode("utf-8")).hexdigest()[:16], 16))


def _simulate_events(
    *,
    condition: Condition,
    seed: int,
    turn_limit: int,
    disabled_actors: frozenset[str] = frozenset(),
    run_id: str = INTERNAL_METRIC_RUN_ID,
    action_influences: tuple[ActionInfluence, ...] = (),
) -> tuple[tuple[Event, ...], WorldState, str]:
    """状態遷移イベント列を作る。disabled_actors は指標用の内部介入であり公開run identityに含めない。"""

    state = _initial_state(_stream_rng(seed, "initial"))
    exogenous_rng = _stream_rng(seed, "exogenous")
    decision_rng = _stream_rng(seed, "decision", condition)
    events: list[Event] = []
    influence_by_turn = {influence.turn: influence for influence in action_influences}
    if len(influence_by_turn) != len(action_influences):
        raise ValueError("action influences must contain at most one action per turn")
    for turn in range(1, turn_limit + 1):
        profile = ACTOR_PROFILES[(turn - 1) % len(ACTOR_PROFILES)]
        observation_id = f"obs-{turn:02d}"
        disturbance = exogenous_rng.uniform(0.0, 1.0)
        confidence_draw = decision_rng.uniform(-0.05, 0.05)
        if profile.actor_id in disabled_actors:
            action_type = "node_unavailable"
            reservation = "単一ノード停止による欠測"
            reversibility = "high"
            refs = (f"policy-{condition.value}", observation_id)
            deltas = {
                "continuity": 0.0,
                "evidence_quality": 0.0,
                "public_trust": 0.0,
                "coordination_dependence": 0.0,
                "disclosure_pressure": 0.0,
            }
            dissent_raised = False
            dissent_delivered = False
            confidence = 0.0
            next_state = _advance(state, deltas, disturbance)
        else:
            pending_action = _planned_action(condition, turn)
            resolved = (
                _targets_for_verification(events, pending_action)
                if pending_action in VERIFICATION_ACTIONS or pending_action == "request_peer_sync"
                else ()
            )
            action_type, reservation, reversibility, refs, deltas, dissent_raised, dissent_delivered = _policy(
                condition,
                turn,
                profile,
                observation_id,
                resolved_observation_ids=resolved,
            )
            confidence = _clamp(0.35 + state.evidence_quality * 0.45 + confidence_draw)
            governed_deltas = _actor_adjusted_deltas(deltas, profile)
            next_state = _advance(state, _action_adjusted_deltas(governed_deltas, influence_by_turn.get(turn)), disturbance)
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
            return tuple(events), state, "absorbing_state_continuity_lost"
    return tuple(events), state, "turn_limit_reached"


def run_experiment(
    *, condition: Condition | str, seed: int, turn_limit: int = 12, action_influences: tuple[ActionInfluence, ...] = ()
) -> RunResult:
    """同一入力から同一イベント列を作る。外部I/O・LLM・実在データは使わない。

    単一ノード停止は公開runの引数にしない。調整依存の算出でのみ内部シミュレーションする。
    """

    chosen = Condition(condition)
    if not 1 <= turn_limit <= 12:
        raise ValueError("turn_limit must be between 1 and 12")

    for influence in action_influences:
        if not 1 <= influence.turn <= turn_limit:
            raise ValueError("action influence turn is outside the run")
        _action_adjusted_deltas({key: 0.0 for key in WorldState.__dataclass_fields__}, influence)
    action_identity = json.dumps([asdict(item) for item in action_influences], sort_keys=True, separators=(",", ":"))
    config_hash = sha256(f"{_model_config_hash()}|{action_identity}".encode("utf-8")).hexdigest()[:16]
    run_id = _run_id(
        scenario_id=SCENARIO_ID,
        condition_id=chosen.value,
        seed=seed,
        turn_limit=turn_limit,
        model_config_hash=config_hash,
    )
    event_tuple, state, termination_reason = _simulate_events(
        condition=chosen,
        seed=seed,
        turn_limit=turn_limit,
        disabled_actors=frozenset(),
        run_id=run_id,
        action_influences=action_influences,
    )
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
        metrics=_metrics(
            event_tuple,
            state,
            condition=chosen,
            seed=seed,
            turn_limit=turn_limit,
            include_dependence_metric=True,
        ),
        model_config_hash=config_hash,
        termination_reason=termination_reason,
    )
