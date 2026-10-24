from pathlib import Path

import pytest

from tests.check_design_contract import (
    _section,
    _table_rows,
    _validate_artifact_registry,
    _validate_post_submission_sync,
)


def test_canonical_section_and_table_are_exactly_one() -> None:
    document = "# X\n\n## Canonical identity\n\n| field | value |\n|---|---|\n| city | ポセイドン |\n"
    rows = _table_rows(_section(document, "Canonical identity"), ("field", "value"))
    assert rows == [{"field": "city", "value": "ポセイドン"}]
    with pytest.raises(ValueError, match="exactly once"):
        _section(document + "\n## Canonical identity\n", "Canonical identity")


def test_artifact_registry_rejects_unknown_or_compound_lifecycle_state() -> None:
    prefix = "| artifact_id | 内容 | 正本 | canonical_state | 実装・実測注記 |\n|---|---|---|---|---|\n"
    valid = prefix + "| demo | viewer | `web/index.html` | implemented | local |\n"
    _validate_artifact_registry(valid)
    for invalid_state in ("accepted", "accepted-setting / implemented"):
        invalid = prefix + f"| demo | viewer | `web/index.html` | {invalid_state} | local |\n"
        with pytest.raises(ValueError, match="exactly one ADR-012 state"):
            _validate_artifact_registry(invalid)


def test_post_submission_sync_rejects_case_regression_and_surface_drift() -> None:
    root = Path(__file__).resolve().parents[1]
    documents = [
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/world/cases.md",
            "docs/roadmap.md",
            "docs/knowledge/open-questions.md",
            "docs/knowledge/artifacts.md",
            "PUBLIC_READY.md",
            "docs/submission-checklist.md",
        )
    ]
    _validate_post_submission_sync(*documents)

    mutations = (
        (0, "| measured |", "| implemented |"),
        (1, "状態: `measured`", "状態: `implemented`"),
        (2, "| Escapeの復帰先 |", "| Escapeの戻り先 |"),
        (3, "鏡潮事案はmeasured、残り9事件はconcept", "全10事件はconcept"),
        (4, "`v0.1.2`", "`v0.1.1`"),
        (5, "`v0.1.2` release済み", "candidate branch検証済み"),
        # 他事件の前進 (concept -> implemented) で要約だけが古いまま残る drift も拒否する
        (0, "| 生命継続、汚染範囲、開示、可逆性 | concept |", "| 生命継続、汚染範囲、開示、可逆性 | implemented |"),
    )
    for index, before, after in mutations:
        candidate = documents.copy()
        candidate[index] = candidate[index].replace(before, after, 1)
        with pytest.raises(ValueError):
            _validate_post_submission_sync(*candidate)
