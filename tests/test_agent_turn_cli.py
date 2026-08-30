from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ghost_in_the_sim.agent_providers import RuleProposalProvider
from ghost_in_the_sim.agent_turn import AgentId
from ghost_in_the_sim.agent_turn_cli import (
    build_recorded_fixture,
    build_request_bundle,
    main,
    verify_recorded_fixture,
    write_canonical_json,
)


def _proposal_bundle(request_bundle: dict) -> dict:
    provider = RuleProposalProvider()
    proposals = []
    from ghost_in_the_sim.agent_turn import AgentTurnRequest, canonical_digest

    for payload in request_bundle["requests"]:
        request = AgentTurnRequest.from_dict(payload)
        proposals.append(provider.propose(request).to_dict())
    payload = {
        "protocol_version": request_bundle["protocol_version"],
        "kind": "agent_proposal_bundle",
        "request_bundle_digest": request_bundle["bundle_digest"],
        "proposals": proposals,
    }
    payload["bundle_digest"] = canonical_digest(payload)
    return payload


def test_export_is_canonical_complete_and_contains_no_secret_surface(tmp_path: Path) -> None:
    first = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    second = build_request_bundle(seed=42, mode="plural", turn_limit=1)

    assert first == second
    assert len(first["requests"]) == len(AgentId)
    assert first["protocol_version"] == "ghost-agent-turn/v1"
    text = json.dumps(first).lower()
    for forbidden in ("prompt", "private_memory", "raw_env", "secret", "filesystem_path"):
        assert forbidden not in text

    output = tmp_path / "requests.json"
    write_canonical_json(output, first)
    assert output.read_bytes().endswith(b"\n")
    assert output.read_text(encoding="utf-8") == write_canonical_json(None, first)


def test_ingest_binds_every_proposal_to_exactly_one_request_and_verifies_replay() -> None:
    requests = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    proposals = _proposal_bundle(requests)

    fixture = build_recorded_fixture(requests, proposals)
    bundle = verify_recorded_fixture(fixture)

    assert len(fixture["proposals"]) == 4
    assert bundle["evidence"]["verification"] == "replay-match"
    assert bundle["run_request"]["seed"] == 42
    assert bundle["replay"]["trajectory_class"] == "recorded-agent-turns"


def test_verify_rebuilds_canonical_requests_and_rejects_forged_fixture_metadata() -> None:
    requests = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    fixture = build_recorded_fixture(requests, _proposal_bundle(requests))
    fixture["request_bundle_digest"] = "sha256:" + "0" * 64
    from ghost_in_the_sim.agent_turn import canonical_digest

    fixture["bundle_digest"] = canonical_digest(
        {key: value for key, value in fixture.items() if key != "bundle_digest"}
    )

    with pytest.raises(ValueError, match="request bundle digest"):
        verify_recorded_fixture(fixture)


def test_verify_revalidates_every_fixture_proposal_against_canonical_request() -> None:
    requests = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    fixture = build_recorded_fixture(requests, _proposal_bundle(requests))
    fixture["proposals"].pop()
    from ghost_in_the_sim.agent_turn import canonical_digest

    fixture["bundle_digest"] = canonical_digest(
        {key: value for key, value in fixture.items() if key != "bundle_digest"}
    )

    with pytest.raises(ValueError, match="missing"):
        verify_recorded_fixture(fixture)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda requests, proposals: proposals["proposals"].pop(), "missing"),
        (
            lambda requests, proposals: proposals["proposals"].append(
                copy.deepcopy(proposals["proposals"][0])
            ),
            "duplicate",
        ),
        (
            lambda requests, proposals: proposals["proposals"][0]["run_ref"].__setitem__(
                "environment_seed", 99
            ),
            "invalid|cross-run|digest",
        ),
        (
            lambda requests, proposals: proposals.__setitem__("unknown", True),
            "schema",
        ),
        (
            lambda requests, proposals: proposals.__setitem__(
                "request_bundle_digest", "sha256:" + "0" * 64
            ),
            "request bundle digest",
        ),
    ],
)
def test_ingest_fails_closed_for_missing_duplicate_cross_run_digest_and_unknown_fields(
    mutate, message: str
) -> None:
    requests = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    proposals = _proposal_bundle(requests)
    mutate(requests, proposals)
    from ghost_in_the_sim.agent_turn import canonical_digest

    digest_payload = dict(proposals)
    digest_payload.pop("bundle_digest")
    proposals["bundle_digest"] = canonical_digest(digest_payload)

    with pytest.raises(ValueError, match=message):
        build_recorded_fixture(requests, proposals)


def test_request_bundle_rejects_unknown_field_and_digest_mutation() -> None:
    requests = build_request_bundle(seed=42, mode="plural", turn_limit=1)
    proposals = _proposal_bundle(requests)
    requests["unknown"] = True

    with pytest.raises(ValueError, match="schema"):
        build_recorded_fixture(requests, proposals)


def test_cli_export_ingest_verify_round_trip(tmp_path: Path) -> None:
    requests_path = tmp_path / "requests.json"
    proposals_path = tmp_path / "proposals.json"
    fixture_path = tmp_path / "fixture.json"
    bundle_path = tmp_path / "run-bundle.json"

    assert main(
        [
            "export",
            "--seed",
            "42",
            "--mode",
            "plural",
            "--turn-limit",
            "1",
            "--output",
            str(requests_path),
        ]
    ) == 0
    requests = json.loads(requests_path.read_text(encoding="utf-8"))
    write_canonical_json(proposals_path, _proposal_bundle(requests))
    assert main(
        [
            "ingest",
            "--requests",
            str(requests_path),
            "--proposals",
            str(proposals_path),
            "--output",
            str(fixture_path),
        ]
    ) == 0
    assert main(
        ["verify", "--fixture", str(fixture_path), "--output", str(bundle_path)]
    ) == 0
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["evidence"]["verification"] == "replay-match"


def test_export_fails_closed_before_emitting_stale_future_turn_requests() -> None:
    with pytest.raises(ValueError, match="one turn at a time"):
        build_request_bundle(seed=42, mode="plural", turn_limit=2)
