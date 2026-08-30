"""御影冴と真壁迅を、能力値ではなく有限注意と停止要求で表す契約。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .scenario import KAGAMISHIO


@dataclass(frozen=True)
class AttentionAllocation:
    body_control: int
    route_verification: int
    civilian_impact: int
    replica_sync: int
    delegation: int
    self_audit: int

    def __post_init__(self) -> None:
        values = tuple(asdict(self).values())
        if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100 for value in values):
            raise ValueError("attention allocation values must be integers between 0 and 100")
        if sum(values) != 100:
            raise ValueError("attention allocation must sum to 100")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class PartnerAction:
    turn: int
    action: str
    reason: str

    def __post_init__(self) -> None:
        if not 1 <= self.turn <= 12 or self.action != "request_pause" or not self.reason:
            raise ValueError("partner action must be a typed request_pause within the scenario")


@dataclass(frozen=True)
class OperativePlan:
    scenario_id: str
    operative_id: str
    partner_id: str
    base_capability: float
    attention: AttentionAllocation
    partner_actions: tuple[PartnerAction, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.operative_id or not self.partner_id:
            raise ValueError("operative plan identifiers must be non-empty")
        if isinstance(self.base_capability, bool) or not 0.9 <= self.base_capability <= 1.0:
            raise ValueError("operative base capability must remain high")
        turns = [action.turn for action in self.partner_actions]
        if turns != sorted(set(turns)):
            raise ValueError("partner actions must use unique ascending turns")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id, "operative_id": self.operative_id, "partner_id": self.partner_id,
            "base_capability": self.base_capability, "attention": self.attention.to_dict(),
            "partner_actions": [asdict(action) for action in self.partner_actions],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OperativePlan":
        if set(payload) != {"scenario_id", "operative_id", "partner_id", "base_capability", "attention", "partner_actions"}:
            raise ValueError("operative plan schema does not match")
        attention = payload["attention"]
        actions = payload["partner_actions"]
        if not isinstance(attention, Mapping) or set(attention) != set(AttentionAllocation.__dataclass_fields__) or not isinstance(actions, list):
            raise ValueError("operative plan nested schema does not match")
        return cls(
            payload["scenario_id"], payload["operative_id"], payload["partner_id"], payload["base_capability"],
            AttentionAllocation(**attention), tuple(PartnerAction(**item) for item in actions),
        )


@dataclass(frozen=True)
class OperativeState:
    body_integrity: float
    cognitive_integrity: float
    memory_coherence: float
    legal_authority: float
    organizational_trust: float
    public_trust: float
    replica_divergence: float
    option_preservation: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def evaluate_operative(plan: OperativePlan, *, completed_turns: int) -> OperativeState:
    """高能力を維持しつつ、注意配分と不可逆判断の代償を決定論的に投影する。"""

    if not 0 <= completed_turns <= 12:
        raise ValueError("completed turns must be between 0 and 12")
    progress = completed_turns / 12
    attention = plan.attention
    pause_seen = any(action.turn <= completed_turns for action in plan.partner_actions)
    clamp = lambda value: round(min(1.0, max(0.0, value)), 6)
    return OperativeState(
        body_integrity=clamp(plan.base_capability - progress * max(0, 18 - attention.body_control) / 500),
        cognitive_integrity=clamp(plan.base_capability - progress * max(0, 20 - attention.self_audit) / 400),
        memory_coherence=clamp(0.9 + attention.replica_sync / 1000 - progress * 0.04),
        legal_authority=clamp(0.9 - progress * 0.08 + (0.03 if pause_seen else 0.0)),
        organizational_trust=clamp(0.82 + attention.delegation / 1000 + (0.03 if pause_seen else 0.0)),
        public_trust=clamp(0.78 + attention.civilian_impact / 1000),
        replica_divergence=clamp(progress * max(0, 30 - attention.replica_sync) / 100),
        option_preservation=clamp(0.94 - progress * 0.12 + (0.06 if pause_seen else 0.0)),
    )


MIKAGE_DEFAULT_PLAN = OperativePlan(
    KAGAMISHIO.scenario_id, "mikage-sae", "makabe-jin", 0.96,
    AttentionAllocation(18, 18, 18, 16, 14, 16),
    (PartnerAction(8, "request_pause", "irreversible_authority_revocation"),),
)
