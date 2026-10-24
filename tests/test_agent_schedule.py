from __future__ import annotations

from dataclasses import replace

import pytest

from ghost_in_the_sim.agent_providers import RecordedProposalProvider, RuleProposalProvider
from ghost_in_the_sim.agent_schedule import OutcomeStatus, schedule_one_round
from ghost_in_the_sim.agent_turn import (
    AgentId,
    AgentTurnRequest,
    Authority,
    AuthorityStatus,
    Observation,
    RunRef,
    build_agent_descriptor,
)


def _requests(condition_id: str = "plural") -> tuple[AgentTurnRequest, ...]:
    run_ref = RunRef(
        scenario_id="kagamishio-proteus-01",
        environment_seed=42,
        condition_id=condition_id,
        turn=8,
        round=1,
    )
    authority = Authority(version="poseidon-policy-v4", status=AuthorityStatus.ACTIVE)
    requests = []
    for index, agent_id in enumerate(AgentId, start=1):
        observation_id = f"obs-{index:02d}"
        requests.append(
            AgentTurnRequest.create(
                run_ref=run_ref,
                agent=build_agent_descriptor(agent_id, observation_scope=(observation_id,)),
                authority=authority,
                observations=(
                    Observation(
                        observation_id=observation_id,
                        summary=f"{agent_id.value}の局所観測",
                        evidence_refs=(observation_id,),
                    ),
                ),
            )
        )
    return tuple(requests)


def test_scheduler_runs_exactly_four_agents_once_in_canonical_order() -> None:
    requests = tuple(reversed(_requests()))

    result = schedule_one_round(requests, RuleProposalProvider())

    assert result.run_ref.round == 1
    assert [outcome.agent_id for outcome in result.outcomes] == list(AgentId)
    assert len(result.outcomes) == 4
    assert {outcome.status for outcome in result.outcomes} >= {
        OutcomeStatus.APPLIED,
        OutcomeStatus.REJECTED,
    }
    assert all(outcome.proposal is not None for outcome in result.outcomes)


def test_scheduler_fallback_is_agent_scoped_and_does_not_change_condition() -> None:
    requests = _requests("autonomous")
    proposals = [RuleProposalProvider().propose(request).to_dict() for request in requests]
    missing_makabe = [
        proposal for proposal in proposals if proposal["agent_id"] != AgentId.MAKABE.value
    ]

    result = schedule_one_round(requests, RecordedProposalProvider(missing_makabe))

    makabe = next(outcome for outcome in result.outcomes if outcome.agent_id is AgentId.MAKABE)
    assert makabe.status is OutcomeStatus.FALLBACK
    assert makabe.reason_code == "proposal_missing"
    assert makabe.influence.action_type == "abstain"
    assert result.run_ref.condition_id == "autonomous"
    assert any(outcome.status is OutcomeStatus.APPLIED for outcome in result.outcomes)


def test_scheduler_is_deterministic_for_same_requests_and_provider() -> None:
    requests = _requests()

    first = schedule_one_round(requests, RuleProposalProvider())
    second = schedule_one_round(requests, RuleProposalProvider())

    assert first.to_dict() == second.to_dict()


@pytest.mark.parametrize(
    "requests",
    [
        lambda values: values[:-1],
        lambda values: values + (values[0],),
        lambda values: values[:-1] + (replace(values[-1], run_ref=replace(values[-1].run_ref, round=2)),),
    ],
)
def test_scheduler_rejects_unbounded_or_mixed_rounds(requests) -> None:
    with pytest.raises(ValueError):
        schedule_one_round(requests(_requests()), RuleProposalProvider())
