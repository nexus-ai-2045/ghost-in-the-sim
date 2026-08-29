"""全追跡テキスト面へ第三者作品の固有識別子が混入しないことを検査する。"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
JAPANESE_FORBIDDEN = (
    "\u653b\u6bbb\u6a5f\u52d5\u968a",
    "\u8349\u8599\u7d20\u5b50",
    "\u516c\u5b899\u8ab2",
    "\u7b11\u3044\u7537",
    "\u4eba\u5f62\u4f7f\u3044",
    "\u30bf\u30c1\u30b3\u30de",
)
ATTRIBUTION_ALLOWANCES = {
    "THIRD_PARTY_NOTICES.md": {JAPANESE_FORBIDDEN[0]: 1},
    "docs/application-theme-memo.md": {JAPANESE_FORBIDDEN[0]: 1},
}
ENGLISH_FORBIDDEN = tuple(
    re.compile(rf"(?<![a-z0-9_]){term}(?![a-z0-9_])", re.IGNORECASE)
    for term in (r"ghost\s+in\s+the\s+shell", r"motoko\s+kusanagi", r"section\s+9")
)
_BOM_DECODERS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
)


def _public_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files: list[Path] = []
    for relative_bytes in completed.stdout.split(b"\0"):
        if not relative_bytes:
            continue
        relative = relative_bytes.decode("utf-8")
        path = ROOT / relative
        if path.is_file() or path.is_symlink():
            files.append(path)
    return files


def _attribution_allowance(git_path: str) -> dict[str, int]:
    """Return exact term counts for a literal Git path, never a whole-file exemption."""

    return ATTRIBUTION_ALLOWANCES.get(git_path, {})


def _decode_text(raw: bytes) -> str | None:
    for bom, encoding in _BOM_DECODERS:
        if raw.startswith(bom):
            return raw.decode(encoding)
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8")


def _find_terms(text: str) -> list[str]:
    folded = text.casefold()
    findings = [term for term in JAPANESE_FORBIDDEN if term.casefold() in folded]
    findings.extend(pattern.pattern for pattern in ENGLISH_FORBIDDEN if pattern.search(text))
    return findings


def _term_count_mismatches(text: str, git_path: str) -> list[str]:
    folded = text.casefold()
    actual = {term: folded.count(term.casefold()) for term in JAPANESE_FORBIDDEN}
    actual.update({pattern.pattern: len(pattern.findall(text)) for pattern in ENGLISH_FORBIDDEN})
    expected = _attribution_allowance(git_path)
    return [
        f"{term} expected={expected.get(term, 0)} actual={count}"
        for term, count in actual.items()
        if count != expected.get(term, 0)
    ]


def main() -> int:
    findings: list[str] = []
    for path in _public_files():
        relative = path.relative_to(ROOT).as_posix()
        findings.extend(f"{relative}: path-name:{term}" for term in _find_terms(relative))
        if path.is_symlink():
            findings.append(f"{relative}: シンボリックリンクは公開内容を間接化するため検査不能")
            continue
        raw = path.read_bytes()
        try:
            text = _decode_text(raw)
        except UnicodeDecodeError as error:
            findings.append(f"{relative}: テキストとして読めません ({error})")
            continue
        if text is None:
            findings.append(f"{relative}: NULを含む未対応エンコーディングのため検査不能")
            continue
        findings.extend(f"{relative}: {mismatch}" for mismatch in _term_count_mismatches(text, relative))
    if findings:
        raise SystemExit("ip-boundary: FAIL\n" + "\n".join(findings))
    print("ip-boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
