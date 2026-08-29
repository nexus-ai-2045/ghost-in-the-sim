from pathlib import Path

from check_ip_boundary import ROOT, _decode_text, _find_terms, _public_files


def test_boundary_uses_identifier_edges() -> None:
    assert _find_terms("intersection 9 remains benign") == []
    assert _find_terms("Review Section 9, now")
    assert _find_terms("SECTION 9")


def test_japanese_source_title_remains_forbidden() -> None:
    assert "攻殻機動隊" in _find_terms("攻殻機動隊への言及")


def test_inventory_covers_all_public_text_surfaces() -> None:
    relative = {path.relative_to(ROOT).as_posix() for path in _public_files()}
    assert "RESULTS.md" in relative
    assert "PUBLIC_READY.md" in relative
    assert "LICENSE" in relative
    assert "src/ghost_in_the_sim/engine.py" in relative
    assert any(path.startswith("docs/operations/") for path in relative)


def test_nul_delimited_listing_includes_non_ascii_paths() -> None:
    target = ROOT / "検査対象.md"
    target.write_text("safe", encoding="utf-8")
    try:
        files = {path.relative_to(ROOT).as_posix() for path in _public_files()}
        assert "検査対象.md" in files
    finally:
        target.unlink(missing_ok=True)


def test_decode_text_handles_utf16_bom_and_rejects_opaque_nul() -> None:
    utf16 = "攻殻機動隊".encode("utf-16")
    assert "攻殻機動隊" in (_decode_text(utf16) or "")
    assert _decode_text(b"opaque\x00binary") is None
