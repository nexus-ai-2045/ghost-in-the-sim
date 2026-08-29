from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ghost_in_the_sim.engine as engine_module
from ghost_in_the_sim.comparison import compare_conditions
from ghost_in_the_sim.engine import (
    ACTOR_PROFILES,
    TRANSITION_PARAMETERS,
    Condition,
    _actor_adjusted_deltas,
    run_experiment,
)


def test_same_input_produces_identical_manifest_events_and_metrics() -> None:
    first = run_experiment(condition=Condition.PLURAL, seed=42, turn_limit=6)
    second = run_experiment(condition=Condition.PLURAL, seed=42, turn_limit=6)

    assert first.manifest() == second.manifest()
    assert [event.to_dict() for event in first.events] == [event.to_dict() for event in second.events]
    assert first.metrics == second.metrics


def test_conditions_produce_distinct_auditable_traces_with_same_seed() -> None:
    comparison = compare_conditions(
        baseline=Condition.CENTRALIZED,
        candidate=Condition.PLURAL,
        seed=17,
        turn_limit=6,
    )

    assert comparison.baseline.seed == comparison.candidate.seed == 17
    assert comparison.baseline.condition_id != comparison.candidate.condition_id
    assert [event.action_type for event in comparison.baseline.events] != [event.action_type for event in comparison.candidate.events]
    assert any(delta != 0 for delta in comparison.deltas.values())
    assert [event.exogenous_disturbance for event in comparison.baseline.events] == [
        event.exogenous_disturbance for event in comparison.candidate.events
    ]


def test_event_contract_and_metric_ranges_are_preserved() -> None:
    result = run_experiment(condition=Condition.OVERCONNECTED, seed=9, turn_limit=6)

    assert len(result.events) == 6
    run_observation_ids = {obs for event in result.events for obs in event.observation_ids}
    for event in result.events:
        assert event.run_id == result.run_id
        assert event.seed == 9
        assert event.actor_id
        assert event.observation_ids[0].startswith("obs-")
        assert event.claim
        assert 0.0 <= event.confidence <= 1.0
        assert event.reservation
        assert event.reversibility in {"high", "medium", "low"}
        assert event.rationale_refs
        assert all(
            ref in run_observation_ids or ref in result.manifest()["policy_reference_ids"]
            for ref in event.rationale_refs
        )
        assert isinstance(event.dissent_raised, bool)
        assert isinstance(event.dissent_delivered, bool)
    assert result.manifest()["termination_reason"] == "turn_limit_reached"
    assert result.manifest()["model_config_hash"]
    assert result.manifest()["code_version"] == "deterministic-core-v2"
    assert result.manifest()["prompt_version_or_hash"] == "rule-based:not-applicable"
    assert len(result.manifest()["source_revision"]) == 16
    # overconnected: broadcast at turn 1, correction at turn 6 → 5 turns until corrected
    assert result.metrics["correction_turn"] == 5.0
    assert result.metrics["over_disclosure"] == 5.0
    for metric in (
        "continuity",
        "evidence_calibration",
        "public_trust",
        "coordination_dependence",
        "dissent_reach",
    ):
        assert 0.0 <= result.metrics[metric] <= 1.0
    assert result.metrics["over_disclosure"] >= 0.0


def test_contract_metrics_match_evaluation_operational_definitions() -> None:
    result = run_experiment(condition=Condition.PLURAL, seed=42, turn_limit=12)
    assert result.metrics["continuity"] == 1.0
    assert result.metrics["over_disclosure"] == 0.0
    assert result.metrics["dissent_reach"] == 1.0
    assert result.metrics["correction_turn"] == 2.0
    assert 0.0 <= result.metrics["evidence_calibration"] <= 1.0
    assert 0.0 <= result.metrics["coordination_dependence"] <= 1.0


def test_evidence_calibration_matches_linked_observations_only() -> None:
    result = run_experiment(condition=Condition.CENTRALIZED, seed=42, turn_limit=12)
    correction = next(event for event in result.events if event.action_type == "issue_correction")
    resolved = {ref for ref in correction.rationale_refs if ref.startswith("obs-")}
    assert resolved == {"obs-03"}
    # obs-01/02 must not be treated as corrected solely by later correction ordering
    assert "obs-01" not in resolved and "obs-02" not in resolved
    scored_claim_turns = []
    for index, event in enumerate(result.events):
        claim_obs = set(event.observation_ids)
        for later in result.events[index + 1 :]:
            if later.action_type != "issue_correction":
                continue
            if claim_obs & {ref for ref in later.rationale_refs if ref.startswith("obs-")}:
                scored_claim_turns.append(event.turn)
                break
    assert scored_claim_turns == [3]


def test_node_stop_stays_internal_and_does_not_reuse_public_run_id() -> None:
    public = run_experiment(condition=Condition.PLURAL, seed=42, turn_limit=4)
    stopped_events, _, _ = engine_module._simulate_events(
        condition=Condition.PLURAL,
        seed=42,
        turn_limit=4,
        disabled_actors=frozenset({"service_steward"}),
    )
    assert any(event.action_type == "node_unavailable" for event in stopped_events)
    assert stopped_events[0].actor_id == "service_steward"
    assert stopped_events[0].action_type == "node_unavailable"
    assert stopped_events[0].run_id == engine_module.INTERNAL_METRIC_RUN_ID
    assert stopped_events[0].run_id != public.run_id
    assert "disabled_actors" not in public.manifest()


def test_actor_profiles_change_transition_deltas() -> None:
    base = TRANSITION_PARAMETERS[Condition.PLURAL.value]
    first = _actor_adjusted_deltas(base, ACTOR_PROFILES[0])
    second = _actor_adjusted_deltas(base, ACTOR_PROFILES[1])
    assert first != second
    assert all(profile.reservation and profile.refutation_condition for profile in ACTOR_PROFILES)


def test_absorbing_state_terminates_early(monkeypatch) -> None:
    def lose_continuity(state, deltas, disturbance):
        return engine_module.WorldState(
            continuity=0.0,
            evidence_quality=state.evidence_quality,
            public_trust=state.public_trust,
            coordination_dependence=state.coordination_dependence,
            disclosure_pressure=state.disclosure_pressure,
        )

    monkeypatch.setattr(engine_module, "_advance", lose_continuity)
    result = engine_module.run_experiment(condition=Condition.PLURAL, seed=3, turn_limit=12)
    assert len(result.events) == 1
    assert result.termination_reason == "absorbing_state_continuity_lost"


def test_cli_writes_replay_bundle(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "run"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ghost_in_the_sim.cli",
            "--condition",
            "plural",
            "--seed",
            "42",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(root / "src")},
    )

    assert json.loads(completed.stdout)["seed"] == 42
    assert json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))["condition_id"] == "plural"
    events = [json.loads(line) for line in (output_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(events) == 12
    assert {event["run_id"] for event in events} == {json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))["run_id"]}


def test_compare_cli_writes_paired_comparison(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "comparison.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ghost_in_the_sim.compare_cli",
            "--baseline",
            "centralized",
            "--candidate",
            "plural",
            "--seed",
            "42",
            "--output",
            str(output),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(root / "src")},
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["baseline"]["seed"] == payload["candidate"]["seed"] == 42
    assert payload["deltas"]
    assert payload["operands"]["baseline_metrics"]
    assert payload["operands"]["candidate_metrics"]
