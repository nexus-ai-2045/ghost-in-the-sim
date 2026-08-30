from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from ghost_in_the_sim import run_bundle_cli
from ghost_in_the_sim.decision import DecisionValidationError, RecordedDecisionEngine, RuleDecisionEngine
from ghost_in_the_sim.replica import run_replica_batch
from ghost_in_the_sim.run_bundle import (
    CANONICALIZATION_VERSION,
    SCHEMA_VERSION,
    _canonical_bytes,
    build_run_bundle,
    build_verified_run_bundle,
    validate_run_bundle,
    verify_run_bundle,
)


def _bundle() -> dict:
    batch = run_replica_batch(seeds=(42,), turn_limit=4)
    return build_verified_run_bundle(next(run for run in batch.runs if run.requested_mode.value == "plural"))


def test_bundle_joins_every_surface_by_run_id_and_replays_exactly() -> None:
    first = _bundle()
    second = _bundle()
    assert first == second
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["evidence"]["canonicalization"] == CANONICALIZATION_VERSION
    run_id = first["run_id"]
    assert {first[name]["run_id"] for name in ("run_request", "event_stream", "replay", "evidence")} == {run_id}
    assert {event["run_id"] for event in first["event_stream"]["events"]} == {run_id}
    assert [event["turn"] for event in first["event_stream"]["events"]] == [1, 2, 3, 4]
    verify_run_bundle(first)
    assert first["run_request"]["scenario"]["scenario_id"] == "kagamishio-proteus-01"
    assert first["run_request"]["operative_plan"]["partner_actions"][0]["action"] == "request_pause"
    assert first["replay"]["operative_state"]["option_preservation"] < 1.0
    first_event = first["event_stream"]["events"][0]
    assert first_event["scenario_beat_id"] == "proteus-01"
    assert first_event["operative_action"] == "synchronize_replicas"
    assert first_event["partner_action"] == "observe"
    assert first_event["cost_codes"]
    assert first_event["operative_state_before"] != first_event["operative_state_after"]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda bundle: bundle["replay"].__setitem__("run_id", "other-run"), "same run_id"),
        (lambda bundle: bundle["event_stream"]["events"].reverse(), "contiguous turn order"),
        (lambda bundle: bundle["replay"]["metrics"].__setitem__("public_trust", 999), "evidence digest"),
        (lambda bundle: bundle["evidence"].__setitem__("failed_run", True), "evidence digest"),
        (lambda bundle: bundle["run_request"].__setitem__("seed", True), "seed must be an integer"),
        (lambda bundle: bundle["event_stream"]["events"][0].__setitem__("partner_action", "ignore_pause"), "operative projection"),
    ],
)
def test_bundle_rejects_cross_run_order_and_content_mutations(mutate, message: str) -> None:
    bundle = copy.deepcopy(_bundle())
    mutate(bundle)
    with pytest.raises(ValueError, match=message):
        validate_run_bundle(bundle)


def test_cli_writes_reproducible_v1_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = []
    for name in ("first", "second"):
        output = tmp_path / f"{name}.json"
        monkeypatch.setattr(
            "sys.argv",
            ["run_bundle_cli", "--mode", "plural", "--seed", "42", "--turn-limit", "4", "--output", str(output)],
        )
        assert run_bundle_cli.main() == 0
        outputs.append(output.read_bytes())
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["schema_version"] == SCHEMA_VERSION


def test_bundle_replays_audited_fallback_through_the_original_failure_path() -> None:
    batch = run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=RecordedDecisionEngine([]))
    fallback_run = next(run for run in batch.runs if run.requested_mode.value == "centralized")
    assert fallback_run.audit.fallback_applied is True
    verify_run_bundle(build_verified_run_bundle(fallback_run))


def test_bundle_preserves_a_distinct_fallback_reason_for_each_decision() -> None:
    class MixedFailureEngine:
        def decide(self, context):
            if context.turn == 1:
                raise DecisionValidationError("decision_unknown", "synthetic missing decision")
            if context.turn == 2:
                raise DecisionValidationError("decision_invalid", "synthetic invalid decision")
            return RuleDecisionEngine().decide(context)

    batch = run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=MixedFailureEngine())
    run = next(item for item in batch.runs if item.requested_mode.value == "centralized")
    bundle = build_verified_run_bundle(run)
    assert list(bundle["replay"]["fallback_reason_codes"].values()) == ["decision_unknown", "decision_invalid"]
    verify_run_bundle(bundle)


def test_fallback_modes_and_equivalent_actions_have_distinct_requested_run_ids() -> None:
    fallback = run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=RecordedDecisionEngine([]))
    assert len({build_run_bundle(run)["run_id"] for run in fallback.runs}) == 3

    class AlternateProvenanceEngine:
        def decide(self, context):
            return RuleDecisionEngine().decide(context).with_updates(model_id="equivalent-actions-other-model")

    baseline = run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=RuleDecisionEngine())
    alternate = run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=AlternateProvenanceEngine())
    baseline_run = next(run for run in baseline.runs if run.requested_mode.value == "plural")
    alternate_run = next(run for run in alternate.runs if run.requested_mode.value == "plural")
    assert [decision.action for decision in baseline_run.decisions] == [
        decision.action for decision in alternate_run.decisions
    ]
    assert build_run_bundle(baseline_run)["run_id"] != build_run_bundle(alternate_run)["run_id"]


def test_build_does_not_claim_replay_match_before_verification() -> None:
    run = next(run for run in run_replica_batch(seeds=(42,), turn_limit=3).runs if run.requested_mode.value == "plural")
    assert build_run_bundle(run)["evidence"]["verification"] == "unverified"
    assert build_verified_run_bundle(run)["evidence"]["verification"] == "replay-match"

    class UnreplayableEngine:
        def decide(self, context):
            return replace(RuleDecisionEngine().decide(context), fixture_hash="sha256:stale")

    unreplayable = next(
        run
        for run in run_replica_batch(seeds=(42,), turn_limit=3, decision_engine=UnreplayableEngine()).runs
        if run.requested_mode.value == "plural"
    )
    assert build_run_bundle(unreplayable)["evidence"]["verification"] == "unverified"
    with pytest.raises(ValueError, match="deterministic replay"):
        build_verified_run_bundle(unreplayable)


def test_cross_runtime_canonical_digest_vector(tmp_path: Path) -> None:
    payload = {"whole": 1, "integral_float": 1.0, "decimal": 0.125, "negative_zero": -0.0}
    expected = b'{"decimal":{"$number":"0.125"},"integral_float":{"$number":"1"},"negative_zero":{"$number":"0"},"whole":{"$number":"1"}}'
    assert _canonical_bytes(payload) == expected
    with pytest.raises(ValueError, match="portable decimal range"):
        _canonical_bytes({"too_small": 1e-7})
    with pytest.raises(ValueError, match="JavaScript safe range"):
        _canonical_bytes({"too_large": 9_007_199_254_740_992})
    with pytest.raises(ValueError, match="JavaScript safe range"):
        _canonical_bytes({"too_large_float": 1e20})
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the cross-runtime golden vector")
    script = Path(__file__).with_name("check_run_bundle_canonicalization.mjs")
    completed = subprocess.run([node, str(script)], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "run-bundle-canonicalization: PASS" in completed.stdout


def test_cli_binds_actual_trace_to_nondefault_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "seed17.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_bundle_cli", "--mode", "plural", "--seed", "17", "--turn-limit", "3",
            "--actual-ai-trace", str(root / "fixtures" / "actual-ai-trace-seed42.json"),
            "--output", str(output),
        ],
    )
    assert run_bundle_cli.main() == 0
    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert {decision["seed"] for decision in bundle["replay"]["decisions"]} == {17}
    assert all(decision["decision_source"] != "audited_fallback" for decision in bundle["replay"]["decisions"])
