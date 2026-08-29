import os
from pathlib import Path

import pytest

from check_ip_boundary import (
    ATTRIBUTION_ALLOWANCES,
    JAPANESE_FORBIDDEN,
    ROOT,
    _decode_text,
    _find_terms,
    _attribution_allowance,
    _public_files,
    _term_count_mismatches,
    main,
)


def test_boundary_uses_identifier_edges() -> None:
    assert _find_terms("intersection 9 remains benign") == []
    assert _find_terms("Review Section " + "9, now")
    assert _find_terms("SECTION " + "9")


def test_japanese_source_title_remains_forbidden() -> None:
    title = JAPANESE_FORBIDDEN[0]
    assert title in _find_terms(title + "への言及")


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
    title = JAPANESE_FORBIDDEN[0]
    utf16 = title.encode("utf-16")
    assert title in (_decode_text(utf16) or "")
    assert _decode_text(b"opaque\x00binary") is None


def test_backslash_filename_cannot_inherit_an_attribution_exemption() -> None:
    literal = "THIRD_PARTY_NOTICES.md"
    assert _attribution_allowance(literal)
    assert not _attribution_allowance(literal.replace("_", "\\_", 1))


def test_checker_and_regression_test_are_not_whole_file_exemptions() -> None:
    assert "tests/check_ip_boundary.py" not in ATTRIBUTION_ALLOWANCES
    assert "tests/test_ip_boundary.py" not in ATTRIBUTION_ALLOWANCES
    public = {path.relative_to(ROOT).as_posix() for path in _public_files()}
    assert "tests/check_ip_boundary.py" in public
    assert "tests/test_ip_boundary.py" in public


def test_attribution_allowance_is_exact_count_not_whole_file_exemption() -> None:
    title = JAPANESE_FORBIDDEN[0]
    path = "THIRD_PARTY_NOTICES.md"
    assert _term_count_mismatches(title, path) == []
    assert _term_count_mismatches(title + title, path)
    assert _term_count_mismatches(title + JAPANESE_FORBIDDEN[1], path)


def test_forbidden_git_path_name_fails_even_with_safe_body() -> None:
    target = ROOT / f"{JAPANESE_FORBIDDEN[0]}.md"
    target.write_text("safe", encoding="utf-8")
    try:
        with pytest.raises(SystemExit, match="path-name"):
            main()
    finally:
        target.unlink(missing_ok=True)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics are verified by Linux CI")
def test_symlink_surface_fails_closed() -> None:
    target = ROOT / "boundary-link"
    target.symlink_to(JAPANESE_FORBIDDEN[0])
    try:
        with pytest.raises(SystemExit, match="シンボリックリンク"):
            main()
    finally:
        target.unlink(missing_ok=True)
