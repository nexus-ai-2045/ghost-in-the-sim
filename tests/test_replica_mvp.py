from __future__ import annotations

from pathlib import Path
import json
from dataclasses import replace

import pytest

from ghost_in_the_sim.decision import (
    DecisionContext,
    DecisionStatus,
    RecordedDecisionEngine,
    ReplicaAction,
    ReplicaMode,
    RuleDecisionEngine,
)
from ghost_in_the_sim.actual_trace import _trace_hash_from_bytes, load_actual_ai_trace
from ghost_in_the_sim.replica import (
    DEFAULT_SEEDS,
    build_result_card,
    classify_run_failure,
    run_replica_batch,
    run_replica_scenario,
)


def test_rule_engine_is_deterministic_and_maps_all_modes() -> None:
    engine = RuleDecisionEngine()
    decisions = []
    for mode in ReplicaMode:
        context = DecisionContext.for_run(mode=mode, seed=42, turn=1)
        first = engine.decide(context)
        second = engine.decide(context)
        assert first == second
        assert first.action is {
            ReplicaMode.CENTRALIZED: ReplicaAction.PROTECT_CONTINUITY,
            ReplicaMode.PLURAL: ReplicaAction.REQUEST_VERIFICATION,
            ReplicaMode.AUTONOMOUS: ReplicaAction.REQUEST_COOPERATION,
        }[mode]
        decisions.append(first.decision_id)
    assert len(set(decisions)) == 3


def test_recorded_engine_replays_valid_ai_fixture_with_provenance() -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=17, turn=1)
    fixture = RuleDecisionEngine(model="fixture-ai-v1", prompt_hash="sha256:prompt-v1").decide(context).with_updates(
        decision_source="llm_generated_in_codex_session",
        model_id="unavailable_to_agent",
        temperature="unavailable_to_agent",
    )
    replay = RecordedDecisionEngine([fixture.to_dict()]).decide(context)

    assert replay == fixture
    assert replay.model_id == "unavailable_to_agent"
    assert replay.decision_source == "llm_generated_in_codex_session"
    assert replay.prompt_hash == "sha256:prompt-v1"
    assert replay.fixture_hash.startswith("sha256:")


@pytest.mark.parametrize("failure", ["invalid", "stale", "revoked", "unknown"])
def test_untrusted_decisions_fail_closed_with_audited_fallback(failure: str) -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=17, turn=1)
    valid = RuleDecisionEngine(model="fixture-ai-v1", prompt_hash="sha256:prompt-v1").decide(context)
    if failure == "invalid":
        payload = {**valid.to_dict(), "action": "execute_unbounded_command"}
    elif failure == "stale":
        payload = valid.with_updates(issued_at_turn=0).to_dict()
    elif failure == "revoked":
        payload = valid.with_updates(status=DecisionStatus.REVOKED).to_dict()
    else:
        payload = []

    outcome = run_replica_scenario(
        requested_mode=ReplicaMode.AUTONOMOUS,
        seed=17,
        turn_limit=2,
        decision_engine=RecordedDecisionEngine([payload] if isinstance(payload, dict) else payload),
    )

    assert outcome.decisions[0].action is ReplicaAction.ABSTAIN
    assert outcome.effective_mode is ReplicaMode.PLURAL
    assert outcome.audit.fallback_applied is True
    assert outcome.audit.reason_code == f"decision_{failure}"
    assert outcome.audit.requested_mode is ReplicaMode.AUTONOMOUS


def test_batch_runs_three_modes_across_fixed_seeds_and_replays() -> None:
    first = run_replica_batch(turn_limit=3)
    second = run_replica_batch(turn_limit=3)

    assert len(first.runs) == len(ReplicaMode) * len(DEFAULT_SEEDS) == 9
    assert first.to_dict() == second.to_dict()
    assert {(run.requested_mode, run.seed) for run in first.runs} == {
        (mode, seed) for mode in ReplicaMode for seed in DEFAULT_SEEDS
    }
    assert all(run.result.manifest()["scenario_id"] == "poseidon-replica-crisis-01" for run in first.runs)
    assert {run.result.condition_id for run in first.runs} == {"centralized", "plural", "autonomous"}
    assert all(decision.model_id and decision.prompt_hash for run in first.runs for decision in run.decisions)


def test_autonomous_is_a_first_class_condition_not_an_overconnected_alias() -> None:
    run = run_replica_scenario(requested_mode=ReplicaMode.AUTONOMOUS, seed=42, turn_limit=3)

    assert run.result.condition_id == "autonomous"
    assert [event.action_type for event in run.result.events] == [
        "coordinate_local_response",
        "coordinate_local_response",
        "request_peer_sync",
    ]
    assert "policy-autonomous" in run.result.manifest()["policy_reference_ids"]
    assert all(
        ref in run.result.manifest()["policy_reference_ids"] or ref.startswith("obs-")
        for event in run.result.events
        for ref in event.rationale_refs
    )


def test_actual_ai_trace_replays_nine_decisions_without_claiming_live_api() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "actual-ai-trace-seed42.json"
    records = load_actual_ai_trace(fixture)
    batch = run_replica_batch(
        seeds=(42,),
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in records),
    )

    assert len(records) == 9
    assert len(batch.runs) == 3
    assert all(not run.audit.fallback_applied for run in batch.runs)
    assert all(decision.actual_ai_participated for run in batch.runs for decision in run.decisions)
    assert all(not decision.external_model_api_called for run in batch.runs for decision in run.decisions)
    assert all(decision.model_id == "unavailable_to_agent" for run in batch.runs for decision in run.decisions)


def test_tracked_comparison_is_exactly_reproducible_from_current_engine() -> None:
    root = Path(__file__).resolve().parents[1]
    batch = run_replica_batch(seeds=DEFAULT_SEEDS, turn_limit=12)
    records = load_actual_ai_trace(root / "fixtures" / "actual-ai-trace-seed42.json")
    evidence_batch = run_replica_batch(
        seeds=(42,),
        turn_limit=12,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in records),
    )
    tracked = json.loads((root / "web" / "data" / "comparison.json").read_text(encoding="utf-8"))
    card = build_result_card(batch)
    card["ai_replay_evidence"] = {
        "run_count": len(evidence_batch.runs),
        "decision_sources": sorted(
            {decision.decision_source for run in evidence_batch.runs for decision in run.decisions}
        ),
        "fallback_count": sum(run.audit.fallback_applied for run in evidence_batch.runs),
    }
    assert tracked == {
        **batch.to_dict(),
        "ai_evidence_runs": [run.to_dict() for run in evidence_batch.runs],
        "result_card": card,
    }


def test_actual_trace_hash_is_independent_of_checkout_line_endings() -> None:
    lf = b'{"provenance": {},\n"decisions": []}\n'
    crlf = lf.replace(b"\n", b"\r\n")

    assert _trace_hash_from_bytes(lf) == _trace_hash_from_bytes(crlf)


def test_two_valid_action_traces_causally_change_events_and_metrics() -> None:
    contexts = [DecisionContext.for_run(mode=ReplicaMode.CENTRALIZED, seed=42, turn=turn) for turn in (1, 2, 3)]
    baseline_records = [RuleDecisionEngine().decide(context) for context in contexts]
    changed_records = [
        record.with_updates(action=ReplicaAction.ABSTAIN, confidence=0.9)
        if record.issued_at_turn == 2
        else record
        for record in baseline_records
    ]

    baseline = run_replica_scenario(
        requested_mode=ReplicaMode.CENTRALIZED,
        seed=42,
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in baseline_records),
    )
    changed = run_replica_scenario(
        requested_mode=ReplicaMode.CENTRALIZED,
        seed=42,
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in changed_records),
    )

    assert not baseline.audit.fallback_applied and not changed.audit.fallback_applied
    assert baseline.result.run_id != changed.result.run_id
    assert [event.state_after for event in baseline.result.events] != [event.state_after for event in changed.result.events]
    assert baseline.result.metrics != changed.result.metrics


def test_recorded_engine_rejects_duplicate_decision_id_even_if_records_match() -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.PLURAL, seed=42, turn=1)
    record = RuleDecisionEngine().decide(context).to_dict()
    engine = RecordedDecisionEngine([record, dict(record)])

    with pytest.raises(ValueError, match="exactly one"):
        engine.decide(context)


def test_duplicate_decision_id_causes_audited_fallback() -> None:
    records = [
        RuleDecisionEngine().decide(DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=42, turn=turn)).to_dict()
        for turn in (1, 2, 3)
    ]
    engine = RecordedDecisionEngine([records[0], records[0], *records[1:]])

    run = run_replica_scenario(
        requested_mode=ReplicaMode.AUTONOMOUS, seed=42, turn_limit=3, decision_engine=engine
    )

    assert run.audit.fallback_applied
    assert run.audit.reason_code == "decision_invalid"
    assert run.effective_mode is ReplicaMode.PLURAL


def test_failure_classifier_is_pure_and_reports_incomplete_synthetic_run() -> None:
    completed = run_replica_scenario(requested_mode=ReplicaMode.PLURAL, seed=17, turn_limit=3).result
    failed = replace(
        completed,
        events=completed.events[:2],
        termination_reason="absorbing_state_continuity_lost",
    )

    assert classify_run_failure(completed) == (False, ())
    assert classify_run_failure(failed) == (
        True,
        ("termination:absorbing_state_continuity_lost", "incomplete_turns:2/3"),
    )


def test_result_card_is_machine_readable_and_seed_falsification_is_deterministic() -> None:
    batch = run_replica_batch(seeds=(17, 42, 99), turn_limit=3)

    first = build_result_card(batch)
    second = build_result_card(batch)

    assert first == second
    assert first["schema_version"] == "result-card-v1"
    assert first["run_count"] == 9
    assert len(first["runs"]) == 9
    assert first["failure_runs"] == []
    assert all(not run["failed_run"] for run in first["runs"])
    assert all(run["completed_turns"] == run["turn_limit"] == 3 for run in first["runs"])
    assert all(run["representative_log_refs"] for run in first["runs"])
    checks = first["refutation_checks"]
    assert {item["check_id"] for item in checks} == {
        "plural_always_better_without_tradeoff",
        "centralized_always_better_without_tradeoff",
    }
    assert all(item["seed"] is None for item in checks)
    assert all({entry["seed"] for entry in item["evidence"]["per_seed"]} == {17, 42, 99} for item in checks)
    for item in checks:
        per_seed = item["evidence"]["per_seed"]
        expected = "triggered" if all(entry["status"] == "triggered" for entry in per_seed) else "not_triggered"
        assert item["status"] == expected
    assert first["seed_sensitivity"]["seeds"] == [17, 42, 99]
    assert first["seed_sensitivity"]["by_mode"]["plural"]["public_trust"]["range"] > 0
    assert "parameter_sweep_not_run" in first["limitations"]


def test_result_card_does_not_compare_modes_that_fell_back_to_another_mode() -> None:
    batch = run_replica_batch(
        seeds=(17,),
        turn_limit=3,
        decision_engine=RecordedDecisionEngine([]),
    )

    checks = build_result_card(batch)["refutation_checks"]

    assert all(check["status"] == "not_observable" for check in checks)
    assert all(
        entry["evidence"]["reason"] == "required_effective_mode_missing"
        for check in checks
        for entry in check["evidence"]["per_seed"]
    )
    sensitivity = build_result_card(batch)["seed_sensitivity"]
    assert set(sensitivity["by_mode"]) == {"plural"}
    assert sensitivity["plural_vs_centralized_sign_reversals"] == []


def test_batch_cli_writes_result_card_without_changing_canonical_batch_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    output = tmp_path / "comparison.json"
    monkeypatch.setattr("sys.argv", ["batch_cli", "--output", str(output), "--turn-limit", "3"])

    assert batch_cli.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "result_card" in payload
    assert payload["result_card"] == build_result_card(run_replica_batch(turn_limit=3))


def test_batch_cli_keeps_actual_ai_evidence_separate_from_rule_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "comparison.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "batch_cli",
            "--output",
            str(output),
            "--turn-limit",
            "3",
            "--actual-ai-evidence-trace",
            str(root / "fixtures" / "actual-ai-trace-seed42.json"),
        ],
    )

    assert batch_cli.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 9
    assert {decision["decision_source"] for run in payload["runs"] for decision in run["decisions"]} == {"deterministic_rule"}
    assert len(payload["ai_evidence_runs"]) == 3
    assert payload["result_card"]["ai_replay_evidence"] == {
        "decision_sources": ["llm_generated_in_codex_session"],
        "fallback_count": 0,
        "run_count": 3,
    }
