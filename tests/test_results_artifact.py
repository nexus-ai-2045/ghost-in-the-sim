from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_results_is_generated_from_tracked_comparison() -> None:
    subprocess.run([sys.executable, "scripts/render_results.py", "--check"], cwd=ROOT, check=True)


def test_readme_quickstart_matches_canonical_reproduction_command() -> None:
    """READMEのクイックスタートは、生成物RESULTS.mdの「再現」節と同じ正本コマンドを載せる。"""

    results = (ROOT / "RESULTS.md").read_text(encoding="utf-8")
    commands = [line for line in results.splitlines() if line.startswith("py -3.13 -m ghost_in_the_sim.batch_cli ")]
    assert len(commands) == 1, "RESULTS.md must contain exactly one canonical batch_cli command"
    assert commands[0] in (ROOT / "README.md").read_text(encoding="utf-8")
