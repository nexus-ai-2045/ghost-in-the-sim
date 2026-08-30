from __future__ import annotations

from dataclasses import replace

import pytest

from ghost_in_the_sim.agent_providers import RecordedProposalProvider, RuleProposalProvider
from ghost_in_the_sim.agent_turn import (
    AgentId,
    AgentProposal,
    AgentTurnRequest,
    Authority,
    AuthorityStatus,
    Observation,
    PriorProposal,
    Dissent,
    ProposalValidationError,
    RunRef,
    build_agent_descriptor,
    canonical_digest,
)


def _request(agent_id: AgentId = AgentId.MIKAGE) -> AgentTurnRequest:
    return AgentTurnRequest.create(
        run_ref=RunRef(
            scenario_id="kagamishio-proteus-01",
            environment_seed=42,
            condition_id="plural",
            turn=3,
            round=1,
        ),
        agent=build_agent_descriptor(
            agent_id,
            observation_scope=("obs-05", "obs-06"),
        ),
        authority=Authority(version="poseidon-policy-v4", status=AuthorityStatus.ACTIVE),
        observations=(
            Observation(
                observation_id="obs-05",
                summary="病院複製の治療継続命令は署名有効・来歴未検証",
                evidence_refs=("obs-05",),
            ),
        ),
    )


def test_request_digest_is_canonical_and_round_trips_strictly() -> None:
    request = _request()

    assert request.idempotency_key == request.request_digest
    assert request.request_digest == canonical_digest(request.digest_payload())
    assert AgentTurnRequest.from_dict(request.to_dict()) == request

    reordered = dict(reversed(tuple(request.digest_payload().items())))
    assert canonical_digest(reordered) == request.request_digest


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: {**payload, "unknown": True},
        lambda payload: {**payload, "deadline_ms": 60_001},
        lambda payload: {**payload, "idempotency_key": "sha256:" + "0" * 64},
        lambda payload: {**payload, "request_digest": "sha256:" + "0" * 64},
        lambda payload: {
            **payload,
            "agent": {**payload["agent"], "observation_scope": ["obs-05", "obs-05"]},
        },
    ],
)
def test_request_parser_fails_closed_for_schema_or_digest_drift(mutation) -> None:
    payload = mutation(_request().to_dict())

    with pytest.raises(ProposalValidationError) as error:
        AgentTurnRequest.from_dict(payload)

    assert error.value.reason_code == "request_invalid"


def test_rule_provider_is_byte_stable_and_proposal_is_bound_to_request() -> None:
    request = _request()
    provider = RuleProposalProvider()

    first = provider.propose(request)
    second = provider.propose(request)

    assert first == second
    assert first.request_digest == request.request_digest
    assert first.run_ref == request.run_ref
    assert first.agent_id is request.agent.agent_id
    assert first.proposal_digest == canonical_digest(first.digest_payload())
    assert AgentProposal.from_dict(first.to_dict(), request=request) == first


@pytest.mark.parametrize(
    ("mutator", "reason_code"),
    [
        (lambda payload: {**payload, "action": "execute_unbounded_command"}, "proposal_invalid"),
        (lambda payload: {**payload, "confidence": 1.1}, "proposal_invalid"),
        (
            lambda payload: {
                **payload,
                "expected_consequence": {
                    **payload["expected_consequence"],
                    "is_projection": False,
                },
            },
            "proposal_invalid",
        ),
        (lambda payload: {**payload, "unknown": "field"}, "proposal_invalid"),
        (lambda payload: {**payload, "request_digest": "sha256:" + "0" * 64}, "proposal_stale"),
    ],
)
def test_proposal_parser_fails_closed(mutator, reason_code: str) -> None:
    request = _request()
    payload = mutator(RuleProposalProvider().propose(request).to_dict())
    if reason_code != "proposal_stale":
        payload["proposal_digest"] = canonical_digest(
            {key: value for key, value in payload.items() if key != "proposal_digest"}
        )

    with pytest.raises(ProposalValidationError) as error:
        AgentProposal.from_dict(payload, request=request)

    assert error.value.reason_code == reason_code


def test_recorded_provider_rejects_missing_duplicate_stale_and_revoked_records() -> None:
    request = _request()
    proposal = RuleProposalProvider().propose(request).to_dict()

    with pytest.raises(ProposalValidationError) as missing:
        RecordedProposalProvider([]).propose(request)
    assert missing.value.reason_code == "proposal_missing"

    with pytest.raises(ProposalValidationError) as duplicate:
        RecordedProposalProvider([proposal, dict(proposal)]).propose(request)
    assert duplicate.value.reason_code == "proposal_duplicate"

    stale_request = replace(request, run_ref=replace(request.run_ref, turn=4))
    with pytest.raises(ProposalValidationError) as stale:
        RecordedProposalProvider([proposal]).propose(stale_request)
    assert stale.value.reason_code == "proposal_stale"

    revoked = replace(request, authority=replace(request.authority, status=AuthorityStatus.REVOKED))
    with pytest.raises(ProposalValidationError) as revoked_error:
        AgentProposal.from_dict(proposal, request=revoked)
    assert revoked_error.value.reason_code == "authority_revoked"


def _prior(proposal: AgentProposal) -> PriorProposal:
    return PriorProposal(
        proposal_digest=proposal.proposal_digest,
        run_ref=proposal.run_ref,
        agent_id=proposal.agent_id,
        action=proposal.action,
        confidence=proposal.confidence,
        evidence_refs=proposal.evidence_refs,
        dissent_raised=proposal.dissent.raised,
    )


def test_dissent_is_bound_to_exact_prior_proposal_in_same_run_and_turn() -> None:
    target_request = _request(AgentId.MAKABE)
    target = RuleProposalProvider().propose(target_request)
    dissent_request = AgentTurnRequest.create(
        run_ref=target_request.run_ref,
        agent=build_agent_descriptor(AgentId.MIKAGE, observation_scope=("obs-05", "obs-06")),
        authority=target_request.authority,
        observations=target_request.observations,
        prior_proposals=(_prior(target),),
    )

    proposal = AgentProposal.create(
        request=dissent_request,
        action=target.action,
        evidence_refs=("obs-05",),
        confidence=0.9,
        reservation="真壁の停止提案へ異議を記録する",
        dissent=Dissent(True, AgentId.MAKABE, target.proposal_digest),
        cooperation_target=None,
        expected_consequence="対象を明示した異議が監査可能になる",
        provenance=RuleProposalProvider().propose(dissent_request).provenance,
    )

    assert proposal.dissent.target_agent_id is AgentId.MAKABE
    assert proposal.dissent.target_proposal_digest == target.proposal_digest


@pytest.mark.parametrize("mutation", ["unknown", "other_agent"])
def test_dissent_rejects_unknown_or_wrong_agent_target(mutation: str) -> None:
    target_request = _request(AgentId.MAKABE)
    target = RuleProposalProvider().propose(target_request)
    prior = _prior(target)
    dissent_request = AgentTurnRequest.create(
        run_ref=target_request.run_ref,
        agent=build_agent_descriptor(AgentId.MIKAGE, observation_scope=("obs-05", "obs-06")),
        authority=target_request.authority,
        observations=target_request.observations,
        prior_proposals=(prior,),
    )
    digest = target.proposal_digest if mutation != "unknown" else "sha256:" + "0" * 64
    agent = AgentId.PORT_REPLICA if mutation == "other_agent" else AgentId.MAKABE
    base = RuleProposalProvider().propose(dissent_request).to_dict()
    base["dissent"] = {
        "raised": True,
        "target_agent_id": agent.value,
        "target_proposal_digest": digest,
    }
    base["proposal_digest"] = canonical_digest(
        {key: value for key, value in base.items() if key != "proposal_digest"}
    )

    with pytest.raises(ProposalValidationError, match="dissent target"):
        AgentProposal.from_dict(base, request=dissent_request)


def test_request_rejects_prior_proposal_from_another_turn() -> None:
    target_request = _request(AgentId.MAKABE)
    target = RuleProposalProvider().propose(target_request)
    prior = replace(_prior(target), run_ref=replace(target.run_ref, turn=4))

    with pytest.raises(ProposalValidationError, match="same run and turn"):
        AgentTurnRequest.create(
            run_ref=target_request.run_ref,
            agent=build_agent_descriptor(
                AgentId.MIKAGE, observation_scope=("obs-05", "obs-06")
            ),
            authority=target_request.authority,
            observations=target_request.observations,
            prior_proposals=(prior,),
        )
