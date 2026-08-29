import pytest

from check_design_contract import _section, _table_rows, _validate_artifact_registry


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
