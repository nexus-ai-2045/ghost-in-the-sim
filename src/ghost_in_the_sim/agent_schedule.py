"""4主体を1回だけ実行する、有界で決定論的なinteraction scheduler。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .agent_providers import ProposalProvider
from .agent_turn import (
    AgentId,
    AgentProposal,
    AgentTurnRequest,
    AuthorityStatus,
    ProposalValidationError,
    RunRef,
)
from .decision import ReplicaAction
from .engine import ActionInfluence


class OutcomeStatus(StrEnum):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    FALLBACK = "FALLBACK"


@dataclass(frozen=True)
class AgentTurnOutcome:
    agent_id: AgentId
    status: OutcomeStatus
    proposal: AgentProposal | None
    influence: ActionInfluence | None
    reason_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id.value,
            "status": self.status.value,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "influence": (
                {
                    "turn": self.influence.turn,
                    "action_type": self.influence.action_type,
                    "confidence": self.influence.confidence,
                }
                if self.influence
                else None
            ),
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class AgentRoundResult:
    run_ref: RunRef
    outcomes: tuple[AgentTurnOutcome, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_ref": self.run_ref.to_dict(),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


def _provider_for(
    providers: ProposalProvider | Mapping[AgentId | str, ProposalProvider], agent_id: AgentId
) -> ProposalProvider:
    if isinstance(providers, Mapping):
        provider = providers.get(agent_id) or providers.get(agent_id.value)
        if provider is None:
            raise ProposalValidationError("proposal_missing", "provider is missing for agent")
        return provider
    return providers


def _selected(request: AgentTurnRequest, proposal: AgentProposal) -> bool:
    if proposal.action is ReplicaAction.ABSTAIN:
        return False
    if request.run_ref.condition_id == "centralized":
        return proposal.agent_id is AgentId.MIKAGE
    if request.run_ref.condition_id == "plural":
        return True
    return proposal.agent_id in {AgentId.HOSPITAL_REPLICA, AgentId.PORT_REPLICA}


def schedule_one_round(
    requests: tuple[AgentTurnRequest, ...] | list[AgentTurnRequest],
    providers: ProposalProvider | Mapping[AgentId | str, ProposalProvider],
) -> AgentRoundResult:
    """同roundの応答到着順を捨て、canonical agent順で必ず4席を終端させる。"""

    request_tuple = tuple(requests)
    if len(request_tuple) != len(AgentId):
        raise ValueError("one round requires exactly four agent requests")
    request_by_agent = {request.agent.agent_id: request for request in request_tuple}
    if set(request_by_agent) != set(AgentId) or len(request_by_agent) != len(request_tuple):
        raise ValueError("one round requires each canonical agent exactly once")
    first_ref = request_tuple[0].run_ref
    if first_ref.round != 1 or any(request.run_ref != first_ref for request in request_tuple):
        raise ValueError("one round requires one shared round-1 run_ref")

    outcomes: list[AgentTurnOutcome] = []
    for agent_id in AgentId:
        request = request_by_agent[agent_id]
        try:
            proposal = _provider_for(providers, agent_id).propose(request)
        except ProposalValidationError as error:
            outcomes.append(
                AgentTurnOutcome(
                    agent_id=agent_id,
                    status=OutcomeStatus.FALLBACK,
                    proposal=None,
                    influence=ActionInfluence(
                        turn=first_ref.turn,
                        action_type=ReplicaAction.ABSTAIN.value,
                        confidence=1.0,
                    ),
                    reason_code=(
                        "authority_revoked"
                        if request.authority.status is AuthorityStatus.REVOKED
                        else error.reason_code
                    ),
                )
            )
            continue

        if _selected(request, proposal):
            outcomes.append(
                AgentTurnOutcome(
                    agent_id=agent_id,
                    status=OutcomeStatus.APPLIED,
                    proposal=proposal,
                    influence=ActionInfluence(
                        turn=first_ref.turn,
                        action_type=proposal.action.value,
                        confidence=proposal.confidence,
                    ),
                    reason_code=None,
                )
            )
        else:
            outcomes.append(
                AgentTurnOutcome(
                    agent_id=agent_id,
                    status=OutcomeStatus.REJECTED,
                    proposal=proposal,
                    influence=None,
                    reason_code="proposal_not_selected",
                )
            )
    return AgentRoundResult(run_ref=first_ref, outcomes=tuple(outcomes))
