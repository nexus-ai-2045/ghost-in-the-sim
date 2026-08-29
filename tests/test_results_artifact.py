from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_results_is_generated_from_tracked_comparison() -> None:
    subprocess.run([sys.executable, "scripts/render_results.py", "--check"], cwd=ROOT, check=True)
