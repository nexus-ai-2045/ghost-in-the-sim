from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ghost_in_the_sim import run_bundle_cli
from ghost_in_the_sim.decision import DecisionValidationError, RecordedDecisionEngine, RuleDecisionEngine
from ghost_in_the_sim.replica import run_replica_batch
from ghost_in_the_sim.run_bundle import SCHEMA_VERSION, build_run_bundle, validate_run_bundle, verify_run_bundle


def _bundle() -> dict:
    batch = run_replica_batch(seeds=(42,), turn_limit=4)
    return build_run_bundle(next(run for run in batch.runs if run.requested_mode.value == "plural"))


def test_bundle_joins_every_surface_by_run_id_and_replays_exactly() -> None:
    first = _bundle()
    second = _bundle()
    assert first == second
    assert first["schema_version"] == SCHEMA_VERSION
    run_id = first["run_id"]
    assert {first[name]["run_id"] for name in ("run_request", "event_stream", "replay", "evidence")} == {run_id}
    assert {event["run_id"] for event in first["event_stream"]["events"]} == {run_id}
    assert [event["turn"] for event in first["event_stream"]["events"]] == [1, 2, 3, 4]
    verify_run_bundle(first)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda bundle: bundle["replay"].__setitem__("run_id", "other-run"), "same run_id"),
        (lambda bundle: bundle["event_stream"]["events"].reverse(), "contiguous turn order"),
        (lambda bundle: bundle["replay"]["metrics"].__setitem__("public_trust", 999), "evidence digest"),
        (lambda bundle: bundle["evidence"].__setitem__("failed_run", True), "evidence digest"),
        (lambda bundle: bundle["run_request"].__setitem__("seed", True), "seed must be an integer"),
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
    verify_run_bundle(build_run_bundle(fallback_run))


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
    bundle = build_run_bundle(run)
    assert list(bundle["replay"]["fallback_reason_codes"].values()) == ["decision_unknown", "decision_invalid"]
    verify_run_bundle(bundle)
