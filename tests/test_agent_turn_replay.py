from __future__ import annotations

import copy

import pytest

from ghost_in_the_sim.agent_providers import RecordedProposalProvider, RuleProposalProvider
from ghost_in_the_sim.agent_schedule import OutcomeStatus
from ghost_in_the_sim.agent_turn import AgentId, PROTOCOL_VERSION
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
