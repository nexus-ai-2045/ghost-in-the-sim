"""型付き事件manifest。runtimeへ物語本文ではなく検証可能なbeatだけを渡す。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


SCENARIO_EVENT_TYPES = frozenset({
    "replica_link_lost", "authority_claim_received", "service_conflict_detected", "evidence_lineage_split",
    "local_copy_diverged", "continuity_risk_rises", "public_explanation_due", "partner_pause_requested",
    "authority_revocation_proposed", "independent_evidence_arrives", "authority_convergence_due", "after_action_audit",
})


@dataclass(frozen=True)
class ScenarioBeat:
    turn: int
    beat_id: str
    event_type: str
    observation_ids: tuple[str, ...]
    reversibility: str

    def __post_init__(self) -> None:
        if isinstance(self.turn, bool) or self.turn < 1:
            raise ValueError("scenario beat turn must be a positive integer")
        if not self.beat_id or not self.event_type:
            raise ValueError("scenario beat identifiers must be non-empty")
        if self.event_type not in SCENARIO_EVENT_TYPES:
            raise ValueError("scenario beat event type is not registered")
        if not self.observation_ids or any(not item for item in self.observation_ids):
            raise ValueError("scenario beat observations must be non-empty")
        if self.reversibility not in {"high", "medium", "low"}:
            raise ValueError("scenario beat reversibility is invalid")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observation_ids"] = list(self.observation_ids)
        return payload


@dataclass(frozen=True)
class ScenarioManifest:
    scenario_id: str
    title: str
    beats: tuple[ScenarioBeat, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.title or not self.beats:
            raise ValueError("scenario manifest fields must be non-empty")
        if [beat.turn for beat in self.beats] != list(range(1, len(self.beats) + 1)):
            raise ValueError("scenario beats must use contiguous turn order")
        if len({beat.beat_id for beat in self.beats}) != len(self.beats):
            raise ValueError("scenario beat ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {"scenario_id": self.scenario_id, "title": self.title, "beats": [beat.to_dict() for beat in self.beats]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScenarioManifest":
        if set(payload) != {"scenario_id", "title", "beats"} or not isinstance(payload.get("beats"), list):
            raise ValueError("scenario manifest schema does not match")
        beats = []
        for item in payload["beats"]:
            if not isinstance(item, Mapping) or set(item) != {"turn", "beat_id", "event_type", "observation_ids", "reversibility"}:
                raise ValueError("scenario beat schema does not match")
            observations = item["observation_ids"]
            if not isinstance(observations, list):
                raise ValueError("scenario beat observations must be an array")
            beats.append(ScenarioBeat(item["turn"], item["beat_id"], item["event_type"], tuple(observations), item["reversibility"]))
        return cls(payload["scenario_id"], payload["title"], tuple(beats))


_BEAT_TYPES = (
    "replica_link_lost", "authority_claim_received", "service_conflict_detected", "evidence_lineage_split",
    "local_copy_diverged", "continuity_risk_rises", "public_explanation_due", "partner_pause_requested",
    "authority_revocation_proposed", "independent_evidence_arrives", "authority_convergence_due", "after_action_audit",
)

KAGAMISHIO = ScenarioManifest(
    "kagamishio-proteus-01",
    "鏡潮事案 / PROTEUS",
    tuple(
        ScenarioBeat(turn, f"proteus-{turn:02d}", event_type, (f"obs-{turn:02d}",), "low" if turn in {8, 11} else "high" if turn < 5 else "medium")
        for turn, event_type in enumerate(_BEAT_TYPES, 1)
    ),
)
