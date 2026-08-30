from __future__ import annotations

from pathlib import Path
import json
from dataclasses import replace

import pytest

from ghost_in_the_sim.decision import (
    DecisionContext,
    DecisionValidationError,
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
from ghost_in_the_sim.evidence_contract import project_evidence, validate_derived_evidence
from ghost_in_the_sim.operative import MIKAGE_DEFAULT_PLAN
from ghost_in_the_sim.scenario import KAGAMISHIO
from ghost_in_the_sim.run_bundle import build_verified_run_bundle


def test_every_mode_uses_the_same_kagamishio_scenario_and_operative_plan() -> None:
    batch = run_replica_batch(seeds=(42,), turn_limit=12)
    assert {run.scenario for run in batch.runs} == {KAGAMISHIO}
    assert {run.operative_plan for run in batch.runs} == {MIKAGE_DEFAULT_PLAN}
    assert all(run.operative_state.option_preservation < 1.0 for run in batch.runs)


def test_run_rejects_scenario_horizon_and_partner_pause_drift() -> None:
    from dataclasses import replace
    from ghost_in_the_sim.operative import PartnerAction

    one_beat = replace(KAGAMISHIO, beats=KAGAMISHIO.beats[:1])
    one_beat_plan = replace(MIKAGE_DEFAULT_PLAN, scenario_id=one_beat.scenario_id, partner_actions=())
    with pytest.raises(ValueError, match="turn_limit"):
        run_replica_scenario(requested_mode="plural", seed=42, turn_limit=2, scenario=one_beat, operative_plan=one_beat_plan)
    wrong_pause = replace(MIKAGE_DEFAULT_PLAN, partner_actions=(PartnerAction(9, "request_pause", "late"),))
    with pytest.raises(ValueError, match="partner pause beat"):
        run_replica_scenario(requested_mode="plural", seed=42, scenario=KAGAMISHIO, operative_plan=wrong_pause)


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
    assert all(run.result.manifest()["scenario_id"] == "kagamishio-proteus-01" for run in first.runs)
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
    from ghost_in_the_sim.batch_cli import artifact_revision, build_ensemble_runs, build_playable_trajectories

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
    revision = artifact_revision(root, evidence_fixture=root / "fixtures" / "actual-ai-trace-seed42.json")
    card["artifact_revision"] = revision
    expected = {
        **batch.to_dict(),
        "artifact_revision": revision,
        "ai_evidence_runs": [run.to_dict() for run in evidence_batch.runs],
        "experience_capability": {
            "schema_version": "ghost-in-the-sim-experience/v1",
            "renderer_mode": "artifact-only",
            "operation_console": True,
            "ai_emergence_console": True,
        },
        "trajectories": [build_verified_run_bundle(run) for run in batch.runs],
        "playable_trajectories": build_playable_trajectories(),
        "ensemble_runs": build_ensemble_runs(),
        "result_card": card,
    }
    expected["evidence_summary"] = project_evidence(expected)
    assert tracked == expected


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


def test_canonical_evidence_projection_rejects_derived_summary_mutations() -> None:
    batch = run_replica_batch(seeds=DEFAULT_SEEDS, turn_limit=3)
    payload = {**batch.to_dict(), "result_card": build_result_card(batch)}
    payload["evidence_summary"] = project_evidence(payload)
    validate_derived_evidence(payload)
    for mutation in ("failure", "reversal"):
        changed = json.loads(json.dumps(payload))
        if mutation == "failure":
            changed["result_card"]["failure_runs"] = [changed["result_card"]["runs"][0]]
        else:
            changed["result_card"]["seed_sensitivity"]["plural_vs_centralized_sign_reversals"] = ["fabricated"]
        with pytest.raises(ValueError):
            validate_derived_evidence(changed)


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
    assert sensitivity["by_mode"] == {}
    assert sensitivity["plural_vs_centralized_sign_reversals"] == []


def test_partial_fallback_is_excluded_from_every_comparison_surface() -> None:
    class PluralFailureEngine:
        def decide(self, context: DecisionContext):
            if context.requested_mode is ReplicaMode.PLURAL:
                raise DecisionValidationError("decision_invalid", "synthetic plural failure")
            return RuleDecisionEngine().decide(context)

    card = build_result_card(run_replica_batch(seeds=(17,), turn_limit=3, decision_engine=PluralFailureEngine()))

    assert all(check["status"] == "not_observable" for check in card["refutation_checks"])
    assert set(card["seed_sensitivity"]["by_mode"]) == {"centralized", "autonomous"}
    assert card["seed_sensitivity"]["plural_vs_centralized_sign_reversals"] == []


def test_batch_cli_writes_result_card_without_changing_canonical_batch_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    output = tmp_path / "comparison.json"
    monkeypatch.setattr("sys.argv", ["batch_cli", "--output", str(output), "--turn-limit", "3"])

    assert batch_cli.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "result_card" in payload
    expected = build_result_card(run_replica_batch(turn_limit=3))
    expected["artifact_revision"] = payload["artifact_revision"]
    assert payload["result_card"] == expected


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
    assert payload["artifact_revision"] == payload["result_card"]["artifact_revision"]


def test_batch_cli_rejects_mixed_comparison_and_actual_ai_evidence_providers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "actual-ai-trace-seed42.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "batch_cli",
            "--output",
            str(tmp_path / "comparison.json"),
            "--actual-ai-trace",
            str(fixture),
            "--actual-ai-evidence-trace",
            str(fixture),
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        batch_cli.main()


def test_artifact_revision_changes_for_every_declared_generator_input() -> None:
    from ghost_in_the_sim.batch_cli import ARTIFACT_INPUTS, _artifact_revision_from_inputs

    baseline_inputs = {name: f"content:{name}".encode() for name in ARTIFACT_INPUTS}
    baseline_inputs["actual-ai-evidence-trace"] = b"fixture"
    baseline = _artifact_revision_from_inputs(baseline_inputs)

    for name in baseline_inputs:
        changed = dict(baseline_inputs)
        changed[name] += b"\nchanged"
        assert _artifact_revision_from_inputs(changed) != baseline, name


def test_artifact_revision_binds_each_selected_fixture_role(tmp_path: Path) -> None:
    from ghost_in_the_sim.batch_cli import artifact_revision

    root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"fixture": 1}', encoding="utf-8")
    second.write_text('{"fixture": 2}', encoding="utf-8")
    assert artifact_revision(root, comparison_fixture=first) != artifact_revision(root, comparison_fixture=second)
    assert artifact_revision(root, evidence_fixture=first) != artifact_revision(root, evidence_fixture=second)
    assert artifact_revision(root, comparison_fixture=first) != artifact_revision(root, evidence_fixture=first)


def test_cli_artifact_revision_changes_with_selected_decision_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    contexts = [DecisionContext.for_run(mode=mode, seed=42, turn=1) for mode in ReplicaMode]
    outputs = []
    for version in ("v1", "v2"):
        fixture = tmp_path / f"{version}.json"
        records = [RuleDecisionEngine(prompt_hash=f"sha256:{version}").decide(context).to_dict() for context in contexts]
        fixture.write_text(json.dumps(records), encoding="utf-8")
        output = tmp_path / f"{version}-output.json"
        monkeypatch.setattr(
            "sys.argv",
            ["batch_cli", "--output", str(output), "--turn-limit", "1", "--seed", "42", "--decision-fixture", str(fixture)],
        )
        assert batch_cli.main() == 0
        outputs.append(json.loads(output.read_text(encoding="utf-8"))["artifact_revision"])
    assert outputs[0] != outputs[1]


def test_duplicate_seeds_are_rejected_by_batch_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ghost_in_the_sim import batch_cli

    with pytest.raises(ValueError, match="unique"):
        run_replica_batch(seeds=(42, 42), turn_limit=3)
    monkeypatch.setattr(
        "sys.argv",
        ["batch_cli", "--output", str(tmp_path / "comparison.json"), "--seed", "42", "--seed", "42"],
    )
    with pytest.raises(SystemExit, match="2"):
        batch_cli.main()


def test_batch_cli_rejects_seeds_not_covered_by_actual_ai_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """traceが覆わないseedを黙ってfallbackへ落とさず、CLI境界で停止する。"""

    from ghost_in_the_sim import batch_cli

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "actual-ai-trace-seed42.json"
    monkeypatch.setattr(
        "sys.argv",
        ["batch_cli", "--output", str(tmp_path / "comparison.json"), "--actual-ai-trace", str(fixture)],
    )
    with pytest.raises(SystemExit, match="2"):
        batch_cli.main()

    monkeypatch.setattr(
        "sys.argv",
        ["batch_cli", "--output", str(tmp_path / "comparison.json"), "--seed", "42", "--actual-ai-trace", str(fixture)],
    )
    assert batch_cli.main() == 0


def test_simulated_actions_follow_the_single_planned_action_table() -> None:
    """イベントのaction_typeは_planned_actionの決定表と1ターンも乖離しない。"""

    from ghost_in_the_sim.engine import Condition, _planned_action, run_experiment

    for condition in Condition:
        result = run_experiment(condition=condition, seed=42, turn_limit=12)
        assert [event.action_type for event in result.events] == [
            _planned_action(condition, turn) for turn in range(1, 13)
        ]


def test_actual_ai_trace_rejects_invalid_values_at_load_time() -> None:
    """confidence・evidence_refs等の不正はfallbackへ化ける前に読込時点で失敗する。"""

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "actual-ai-trace-seed42.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    def _write(tmp_payload: dict, path: Path) -> Path:
        path.write_text(json.dumps(tmp_payload, ensure_ascii=False), encoding="utf-8")
        return path

    import copy
    import tempfile

    cases = (
        ("confidence", 1.5, "confidence"),
        ("confidence", "high", "confidence"),
        ("evidence_refs", "obs-01", "evidence_refs"),
        ("evidence_refs", [], "evidence_refs"),
        ("rationale", "", "non-empty strings"),
    )
    with tempfile.TemporaryDirectory() as tmp:
        for field, bad_value, message in cases:
            broken = copy.deepcopy(payload)
            broken["decisions"][0][field] = bad_value
            with pytest.raises(ValueError, match=message):
                load_actual_ai_trace(_write(broken, Path(tmp) / "broken.json"))
