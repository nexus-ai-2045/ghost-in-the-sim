from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ghost_in_the_sim.comparison import compare_conditions
from ghost_in_the_sim.engine import Condition, run_experiment


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


def test_event_contract_and_metric_ranges_are_preserved() -> None:
    result = run_experiment(condition=Condition.OVERCONNECTED, seed=9, turn_limit=6)

    assert len(result.events) == 6
    for event in result.events:
        assert event.run_id == result.run_id
        assert event.seed == 9
        assert event.actor_id
        assert event.observation_ids[0].startswith("obs-")
        assert event.claim
        assert 0.0 <= event.confidence <= 1.0
        assert event.reservation
        assert event.reversible is True
        assert event.rationale_refs
    assert result.manifest()["termination_reason"] == "turn_limit_reached"
    assert result.manifest()["model_config_hash"]
    for metric in (
        "continuity",
        "evidence_calibration",
        "public_trust",
        "coordination_dependence",
        "over_disclosure",
        "dissent_reach",
    ):
        assert 0.0 <= result.metrics[metric] <= 1.0


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
    assert len(events) == 6
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
