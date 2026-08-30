from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "docs" / "operations" / "context-handoff.md"

CANONICAL_POINTERS = (
    "docs/product/repository-goal.md",
    "docs/architecture/ai-replica-mvp.md",
    "docs/architecture/simulation-contract.md",
    "docs/architecture/agent-contract.md",
    "docs/roadmap.md",
    "docs/knowledge/artifacts.md",
    "docs/operations/repository-gates.md",
)

REQUIRED_HEADINGS = (
    "## 正本の読み順",
    "## いま閉じるゴール",
    "## 境界",
    "## 再開時の実測",
    "## phaseと残務の導出",
    "## 完了receipt",
)


def _canonical_batch_command(text: str) -> str:
    matches = re.findall(
        r"^py -3\.13 -m ghost_in_the_sim\.batch_cli --output "
        r"web/data/comparison\.json --actual-ai-evidence-trace "
        r"fixtures/actual-ai-trace-seed42\.json$",
        text,
        flags=re.MULTILINE,
    )
    assert len(matches) == 1, "canonical batch command must appear exactly once"
    return matches[0]


def test_context_handoff_points_to_existing_canonical_sources() -> None:
    text = CONTEXT.read_text(encoding="utf-8")

    for heading in REQUIRED_HEADINGS:
        assert text.count(heading) == 1, f"missing or duplicate context heading: {heading}"

    for relative_path in CANONICAL_POINTERS:
        assert (ROOT / relative_path).is_file(), f"missing canonical source: {relative_path}"
        assert relative_path in text, f"context handoff does not point to: {relative_path}"


def test_context_handoff_does_not_freeze_ephemeral_workspace_state() -> None:
    text = CONTEXT.read_text(encoding="utf-8")

    forbidden_patterns = {
        "Windows absolute path": r"[A-Za-z]:\\",
        "temporary worktree path": r"Projects-worktrees",
        "exact git SHA": r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])",
    }
    for label, pattern in forbidden_patterns.items():
        assert re.search(pattern, text, flags=re.IGNORECASE) is None, label


def test_context_handoff_reuses_canonical_reproduction_command() -> None:
    context = CONTEXT.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    results = (ROOT / "RESULTS.md").read_text(encoding="utf-8")

    expected = _canonical_batch_command(readme)
    assert _canonical_batch_command(results) == expected
    assert _canonical_batch_command(context) == expected
