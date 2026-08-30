from __future__ import annotations

import copy

import pytest

from ghost_in_the_sim.agent_providers import RecordedProposalProvider, RuleProposalProvider
from ghost_in_the_sim.agent_schedule import OutcomeStatus
from ghost_in_the_sim.agent_turn import AgentId, AgentProposal, AuthorityStatus, PROTOCOL_VERSION
from ghost_in_the_sim.decision import ReplicaAction
from ghost_in_the_sim.operative import OperationalFocus, PauseResponse, build_gameplay_plan
from ghost_in_the_sim.replica import run_ensemble_scenario, run_replica_batch
from ghost_in_the_sim.run_bundle import (
    _digest,
    build_run_bundle,
    build_verified_run_bundle,
    validate_run_bundle,
    verify_run_bundle,
)


def _ensemble_bundle(turn_limit: int = 4) -> dict:
    run = run_ensemble_scenario(requested_mode="plural", seed=42, turn_limit=turn_limit)
    return build_verified_run_bundle(run)


def _refresh_evidence(bundle: dict) -> None:
    bundle["evidence"]["run_request_sha256"] = _digest(bundle["run_request"])
    bundle["evidence"]["event_stream_sha256"] = _digest(bundle["event_stream"])
    bundle["evidence"]["replay_sha256"] = _digest(bundle["replay"])


def test_ensemble_runs_four_agents_per_turn_and_is_deterministic() -> None:
    first = run_ensemble_scenario(requested_mode="plural", seed=42, turn_limit=4)
    second = run_ensemble_scenario(requested_mode="plural", seed=42, turn_limit=4)

    assert first.to_dict() == second.to_dict()
    assert len(first.agent_rounds) == 4
    assert all(len(round_result.outcomes) == 4 for round_result in first.agent_rounds)
    assert [outcome.agent_id for outcome in first.agent_rounds[0].outcomes] == list(AgentId)
    assert len(first.applied_influences) == 4
    assert first.effective_mode is first.requested_mode


def test_ensemble_bundle_adds_agent_replay_without_changing_v1_top_level() -> None:
    ensemble = _ensemble_bundle()
    legacy_run = next(
        run for run in run_replica_batch(seeds=(42,), turn_limit=4).runs
        if run.requested_mode.value == "plural"
    )
    legacy = build_run_bundle(legacy_run)

    assert set(ensemble) == set(legacy)
    assert "agent_turns" not in legacy["replay"]
    assert ensemble["replay"]["protocol_version"] == PROTOCOL_VERSION
    assert ensemble["replay"]["trajectory_class"] == "recorded-agent-turns"
    assert len(ensemble["replay"]["agent_turns"]) == 16
    assert ensemble["replay"]["interaction_refs"]
    assert ensemble["replay"]["emergence_metrics"]["validated_proposal_count"] == 16
    assert ensemble["replay"]["emergence_metrics"]["applied_count"] == 4
    verify_run_bundle(ensemble)


def test_ensemble_replay_uses_recorded_proposals_without_recalling_rule_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _ensemble_bundle()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("rule provider must not be called during exact replay")

    monkeypatch.setattr(RuleProposalProvider, "propose", forbidden)
    verify_run_bundle(bundle)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda replay: replay["agent_turns"][0]["proposal"].__setitem__(
                "proposal_digest", "sha256:" + "0" * 64
            ),
            "proposal digest",
        ),
        (lambda replay: replay["agent_turns"].reverse(), "canonical turn and agent order"),
        (
            lambda replay: replay["agent_turns"][0]["request"]["run_ref"].__setitem__(
                "environment_seed", 99
            ),
            "request",
        ),
        (lambda replay: replay["interaction_refs"].clear(), "interaction refs"),
        (
            lambda replay: replay["emergence_metrics"].__setitem__(
                "validated_proposal_count", 999
            ),
            "emergence metrics",
        ),
    ],
)
def test_ensemble_bundle_rejects_digest_order_cross_run_and_projection_mutations(
    mutate, message: str
) -> None:
    bundle = copy.deepcopy(_ensemble_bundle())
    mutate(bundle["replay"])
    _refresh_evidence(bundle)

    with pytest.raises(ValueError, match=message):
        validate_run_bundle(bundle)


def test_missing_recorded_agent_gets_scoped_fallback_without_mode_change() -> None:
    baseline = run_ensemble_scenario(requested_mode="autonomous", seed=42, turn_limit=2)
    proposals = [
        outcome.proposal.to_dict()
        for round_result in baseline.agent_rounds
        for outcome in round_result.outcomes
        if outcome.proposal is not None
        and not (
            round_result.run_ref.turn == 1
            and outcome.agent_id is AgentId.MAKABE
        )
    ]

    replay = run_ensemble_scenario(
        requested_mode="autonomous",
        seed=42,
        turn_limit=2,
        proposal_provider=RecordedProposalProvider(proposals),
    )

    fallback = next(
        outcome
        for outcome in replay.agent_rounds[0].outcomes
        if outcome.agent_id is AgentId.MAKABE
    )
    assert fallback.status is OutcomeStatus.FALLBACK
    assert fallback.reason_code == "proposal_missing"
    assert replay.effective_mode.value == "autonomous"
    verify_run_bundle(build_verified_run_bundle(replay))


def test_next_turn_requests_observe_the_confirmed_prior_world_state() -> None:
    class CapturingProvider:
        def __init__(self, first_action: ReplicaAction) -> None:
            self.first_action = first_action
            self.requests = []
            self.delegate = RuleProposalProvider()

        def propose(self, request):
            self.requests.append(request)
            proposal = self.delegate.propose(request)
            if request.run_ref.turn == 1 and request.agent.agent_id is AgentId.MIKAGE:
                return AgentProposal.create(
                    request=request,
                    action=self.first_action,
                    evidence_refs=proposal.evidence_refs,
                    confidence=proposal.confidence,
                    reservation=proposal.reservation,
                    dissent=proposal.dissent,
                    cooperation_target=proposal.cooperation_target,
                    expected_consequence=proposal.expected_consequence.text,
                    provenance=proposal.provenance,
                )
            return proposal

    protect = CapturingProvider(ReplicaAction.PROTECT_CONTINUITY)
    abstain = CapturingProvider(ReplicaAction.ABSTAIN)
    run_ensemble_scenario(requested_mode="centralized", seed=42, turn_limit=2, proposal_provider=protect)
    run_ensemble_scenario(requested_mode="centralized", seed=42, turn_limit=2, proposal_provider=abstain)

    protect_turn_2 = next(
        request for request in protect.requests
        if request.run_ref.turn == 2 and request.agent.agent_id is AgentId.MIKAGE
    )
    abstain_turn_2 = next(
        request for request in abstain.requests
        if request.run_ref.turn == 2 and request.agent.agent_id is AgentId.MIKAGE
    )
    assert protect_turn_2.request_digest != abstain_turn_2.request_digest
    assert protect_turn_2.observations[0].summary != abstain_turn_2.observations[0].summary


def test_revoked_replica_cannot_apply_on_the_following_turn() -> None:
    class CapturingProvider:
        def __init__(self) -> None:
            self.requests = []
            self.delegate = RuleProposalProvider()

        def propose(self, request):
            self.requests.append(request)
            return self.delegate.propose(request)

    plan = build_gameplay_plan(focus=OperationalFocus.HOSPITAL, pause_response=PauseResponse.PROCEED)
    provider = CapturingProvider()
    run = run_ensemble_scenario(
        requested_mode="autonomous", seed=42, turn_limit=12,
        operative_plan=plan, proposal_provider=provider,
    )

    port_turn_12 = next(
        outcome for outcome in run.agent_rounds[11].outcomes
        if outcome.agent_id is AgentId.PORT_REPLICA
    )
    port_request = next(
        request for request in provider.requests
        if request.run_ref.turn == 12 and request.agent.agent_id is AgentId.PORT_REPLICA
    )
    assert port_request.authority.status is AuthorityStatus.REVOKED
    assert port_turn_12.reason_code == "authority_revoked"
    assert port_turn_12.influence is not None
    assert port_turn_12.influence.action_type == "abstain"
    assert port_turn_12.proposal is None
