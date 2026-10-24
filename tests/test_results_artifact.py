from __future__ import annotations

from pathlib import Path
import json
import os
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_results_is_generated_from_tracked_comparison() -> None:
    subprocess.run([sys.executable, "scripts/render_results.py", "--check"], cwd=ROOT, check=True)


def test_readme_quickstart_matches_and_executes_canonical_reproduction_command(tmp_path: Path) -> None:
    """READMEのクイックスタートは、生成物RESULTS.mdの「再現」節と同じ正本コマンドを載せる。"""

    results = (ROOT / "RESULTS.md").read_text(encoding="utf-8")
    commands = [line for line in results.splitlines() if line.startswith("py -3.13 -m ghost_in_the_sim.batch_cli ")]
    assert len(commands) == 1, "RESULTS.md must contain exactly one canonical batch_cli command"
    command = commands[0]
    assert command in (ROOT / "README.md").read_text(encoding="utf-8")

    tokens = shlex.split(command)
    assert tokens[:4] == ["py", "-3.13", "-m", "ghost_in_the_sim.batch_cli"]
    output_index = tokens.index("--output") + 1
    output = tmp_path / "comparison.json"
    tokens[output_index] = str(output)
    subprocess.run(
        [sys.executable, "-m", "ghost_in_the_sim.batch_cli", *tokens[4:]],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["seeds"] == [17, 42, 99]
    assert len(payload["runs"]) == 9
    assert payload["experience_capability"] == {
        "ai_emergence_console": True,
        "operation_console": True,
        "renderer_mode": "artifact-only",
        "schema_version": "ghost-in-the-sim-experience/v1",
    }
    assert len(payload["trajectories"]) == 9
    assert {bundle["evidence"]["verification"] for bundle in payload["trajectories"]} == {"replay-match"}
    assert [item["trajectory_id"] for item in payload["playable_trajectories"]] == [
        "hospital-joint-hold", "port-joint-hold", "hospital-joint-proceed", "hospital-single-proceed",
    ]
    assert {item["bundle"]["run_request"]["seed"] for item in payload["playable_trajectories"]} == {42}
    assert {item["bundle"]["evidence"]["verification"] for item in payload["playable_trajectories"]} == {"replay-match"}
    assert len(payload["ensemble_runs"]) == 3
    assert {item["run_request"]["seed"] for item in payload["ensemble_runs"]} == {42}
    assert {item["run_request"]["requested_mode"] for item in payload["ensemble_runs"]} == {
        "centralized", "plural", "autonomous",
    }
    assert {item["replay"]["trajectory_class"] for item in payload["ensemble_runs"]} == {
        "recorded-agent-turns",
    }
    assert {item["evidence"]["verification"] for item in payload["ensemble_runs"]} == {"replay-match"}
