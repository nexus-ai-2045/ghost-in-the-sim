from pathlib import Path

from check_ip_boundary import ROOT, _find_terms, _public_files


def test_boundary_uses_identifier_edges() -> None:
    assert _find_terms("intersection 9 remains benign") == []
    assert _find_terms("Review Section 9, now")
    assert _find_terms("SECTION 9")


def test_inventory_covers_all_public_text_surfaces() -> None:
    relative = {path.relative_to(ROOT).as_posix() for path in _public_files()}
    assert "RESULTS.md" in relative
    assert "PUBLIC_READY.md" in relative
    assert "LICENSE" in relative
    assert "src/ghost_in_the_sim/engine.py" in relative
    assert any(path.startswith("docs/operations/") for path in relative)
