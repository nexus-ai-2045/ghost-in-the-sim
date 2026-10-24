from __future__ import annotations

import copy

import pytest

from ghost_in_the_sim.agent_providers import RuleProposalProvider
from ghost_in_the_sim.agent_session import advance_session, create_session
from ghost_in_the_sim.agent_turn import AgentTurnRequest, canonical_digest


def _proposal_bundle(session: dict) -> dict:
    request_bundle = session["current_request_bundle"]
    provider = RuleProposalProvider()
    proposals = [
        provider.propose(AgentTurnRequest.from_dict(item)).to_dict()
        for item in request_bundle["requests"]
    ]
    payload = {
        "protocol_version": "ghost-agent-turn/v1",
        "kind": "agent_proposal_bundle",
        "request_bundle_digest": request_bundle["bundle_digest"],
        "proposals": proposals,
    }
    payload["bundle_digest"] = canonical_digest(payload)
    return payload


def test_session_interleaves_confirmed_state_before_exporting_next_turn() -> None:
    session = create_session(seed=42, mode="plural", turn_limit=3)
    turn_one = session["current_request_bundle"]

    assert session["status"] == "awaiting_proposals"
    assert session["next_turn"] == 1
    assert {item["run_ref"]["turn"] for item in turn_one["requests"]} == {1}

    session = advance_session(session, _proposal_bundle(session))
    turn_two = session["current_request_bundle"]

    assert session["next_turn"] == 2
    assert len(session["rounds"]) == 1
    assert {item["run_ref"]["turn"] for item in turn_two["requests"]} == {2}
    summaries = [
        obs["summary"] for item in turn_two["requests"] for obs in item["observations"]
    ]
    assert all("確定状態" in summary for summary in summaries)
    assert turn_two["bundle_digest"] != turn_one["bundle_digest"]


def test_completed_session_emits_verified_run_bundle_with_one_run_id() -> None:
    session = create_session(seed=42, mode="plural", turn_limit=3)
    while session["status"] != "completed":
        session = advance_session(session, _proposal_bundle(session))

    bundle = session["run_bundle"]
    assert session["current_request_bundle"] is None
    assert session["next_turn"] is None
    assert len(session["rounds"]) == 3
    assert bundle["schema_version"] == "meta-security-run-bundle/v1"
    assert bundle["evidence"]["verification"] == "replay-match"
    run_id = bundle["run_request"]["run_id"]
    assert {event["run_id"] for event in bundle["event_stream"]["events"]} == {run_id}
    assert bundle["replay"]["run_id"] == run_id
    assert bundle["evidence"]["run_id"] == run_id


def test_session_rejects_stale_duplicate_and_tampered_transition() -> None:
    session = create_session(seed=42, mode="plural", turn_limit=2)
    first_proposals = _proposal_bundle(session)
    advanced = advance_session(session, first_proposals)

    with pytest.raises(ValueError, match="request bundle digest"):
        advance_session(advanced, first_proposals)

    tampered = copy.deepcopy(advanced)
    tampered["rounds"][0]["run_ref"]["turn"] = 2
    tampered["bundle_digest"] = canonical_digest(
        {key: value for key, value in tampered.items() if key != "bundle_digest"}
    )
    with pytest.raises(ValueError, match="canonical replay|round history"):
        advance_session(tampered, _proposal_bundle(advanced))

    forged_request = copy.deepcopy(advanced)
    forged_request["current_request_bundle"]["requests"][0]["observations"][0][
        "summary"
    ] = "偽造された確定状態"
    forged_request["current_request_bundle"]["bundle_digest"] = canonical_digest(
        {
            key: value
            for key, value in forged_request["current_request_bundle"].items()
            if key != "bundle_digest"
        }
    )
    forged_request["bundle_digest"] = canonical_digest(
        {key: value for key, value in forged_request.items() if key != "bundle_digest"}
    )
    with pytest.raises(ValueError, match="request bundle does not match canonical replay"):
        advance_session(forged_request, _proposal_bundle(advanced))


def test_session_rejects_rehashed_state_that_skips_a_turn() -> None:
    session = create_session(seed=42, mode="plural", turn_limit=3)
    skipped = copy.deepcopy(session)
    skipped["next_turn"] = 2
    skipped["current_request_bundle"]["current_turn"] = 2
    for request in skipped["current_request_bundle"]["requests"]:
        request["run_ref"]["turn"] = 2
        request["request_digest"] = canonical_digest(
            {key: value for key, value in request.items() if key != "request_digest"}
        )
    skipped["current_request_bundle"]["bundle_digest"] = canonical_digest(
        {
            key: value
            for key, value in skipped["current_request_bundle"].items()
            if key != "bundle_digest"
        }
    )
    skipped["bundle_digest"] = canonical_digest(
        {key: value for key, value in skipped.items() if key != "bundle_digest"}
    )

    with pytest.raises(ValueError, match="session state is inconsistent"):
        advance_session(skipped, {})


def test_session_is_deterministic_for_same_seed_and_proposals() -> None:
    first = create_session(seed=17, mode="autonomous", turn_limit=2)
    second = create_session(seed=17, mode="autonomous", turn_limit=2)
    assert first == second

    while first["status"] != "completed":
        first = advance_session(first, _proposal_bundle(first))
        second = advance_session(second, _proposal_bundle(second))
    assert first == second
