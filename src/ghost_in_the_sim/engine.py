"""架空シナリオを比較するための、外部接続を持たない決定論コア。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from random import Random
from typing import Any


MODEL_VERSION = "0.1.0"
POLICY_VERSION = "nagishima-policy-v1"
SCENARIO_ID = "nagishima-public-infrastructure-01"


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
    reservation: str
    reversible: bool
    rationale_refs: tuple[str, ...]
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
            "model_config_hash": self.model_config_hash,
            "termination_reason": self.termination_reason,
            "event_count": len(self.events),
        }


ACTORS = (
    "service_steward",
    "evidence_verifier",
    "community_liaison",
    "continuity_coordinator",
    "independent_observer",
    "privacy_steward",
)


def _model_config_hash() -> str:
    """主体・条件・政策版を、manifestで比較できる固定識別子にする。"""

    config = {
        "actors": ACTORS,
        "conditions": tuple(item.value for item in Condition),
        "policy_version": POLICY_VERSION,
    }
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _run_id(*, scenario_id: str, condition_id: str, seed: int, turn_limit: int, model_config_hash: str) -> str:
    """同じ再実行条件を同じIDへ正規化する。"""

    identity = f"{scenario_id}|{condition_id}|{seed}|{turn_limit}|{MODEL_VERSION}|{model_config_hash}"
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


def _policy(condition: Condition, turn: int) -> tuple[str, str, bool, tuple[str, ...], dict[str, float]]:
    """条件ごとの可逆・非作戦的な調整ルールを返す。"""

    if condition is Condition.CENTRALIZED:
        return (
            "coordinate_response",
            "単一窓口の判断を待つため、異議は次ターンへ持ち越す",
            True,
            ("policy-centralized", "obs-shared"),
            {"continuity": 0.055, "evidence_quality": 0.018, "public_trust": 0.006, "coordination_dependence": 0.058, "disclosure_pressure": 0.018},
        )
    if condition is Condition.PLURAL:
        return (
            "request_cross_check",
            "複数の独立確認がそろうまで結論を留保する",
            True,
            ("policy-plural", "obs-shared", f"turn-{turn}-reservation"),
            {"continuity": 0.032, "evidence_quality": 0.066, "public_trust": 0.041, "coordination_dependence": -0.034, "disclosure_pressure": -0.021},
        )
    return (
        "broadcast_status",
        "接続点が多く、必要性を超えた共有の恐れが残る",
        True,
        ("policy-overconnected", "obs-shared"),
        {"continuity": 0.039, "evidence_quality": 0.009, "public_trust": -0.014, "coordination_dependence": -0.009, "disclosure_pressure": 0.071},
    )


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
        (event.turn for event in events if event.action_type == "request_cross_check"),
        len(events) + 1,
    )
    dissent_reach = sum("reservation" in ref for event in events for ref in event.rationale_refs) / len(events)
    return {
        "continuity": state.continuity,
        "evidence_calibration": state.evidence_quality,
        "public_trust": state.public_trust,
        "coordination_dependence": state.coordination_dependence,
        "over_disclosure": state.disclosure_pressure,
        "correction_turn": float(correction_turn),
        "dissent_reach": round(dissent_reach, 6),
    }


def run_experiment(*, condition: Condition | str, seed: int, turn_limit: int = 6) -> RunResult:
    """同一入力から同一イベント列を作る。外部I/O・LLM・実在データは使わない。"""

    chosen = Condition(condition)
    if not 1 <= turn_limit <= 12:
        raise ValueError("turn_limit must be between 1 and 12")

    rng = Random(seed)
    state = _initial_state(rng)
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
        actor = ACTORS[(turn - 1) % len(ACTORS)]
        action_type, reservation, reversible, refs, deltas = _policy(chosen, turn)
        confidence = _clamp(0.35 + state.evidence_quality * 0.45 + rng.uniform(-0.05, 0.05))
        disturbance = rng.uniform(0.0, 1.0)
        next_state = _advance(state, deltas, disturbance)
        events.append(
            Event(
                run_id=run_id,
                seed=seed,
                turn=turn,
                actor_id=actor,
                action_type=action_type,
                observation_ids=(f"obs-{turn:02d}",),
                claim="未検証の観測を確証として扱わず、可逆的な次の確認へ進む",
                confidence=confidence,
                reservation=reservation,
                reversible=reversible,
                rationale_refs=refs,
                state_before=state,
                state_after=next_state,
            )
        )
        state = next_state

    event_tuple = tuple(events)
    return RunResult(
        scenario_id=SCENARIO_ID,
        condition_id=chosen.value,
        seed=seed,
        turn_limit=turn_limit,
        model_version=MODEL_VERSION,
        events=event_tuple,
        final_state=state,
        metrics=_metrics(event_tuple, state),
        model_config_hash=config_hash,
        termination_reason="turn_limit_reached",
    )
