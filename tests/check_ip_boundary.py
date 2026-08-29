"""全追跡テキスト面へ第三者作品の固有識別子が混入しないことを検査する。"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTION_EXEMPTIONS = {
    "THIRD_PARTY_NOTICES.md",
    "docs/application-theme-memo.md",
    "docs/adr/ADR-001-original-agent-model.md",
    "docs/adr/ADR-007-source-and-name-boundary.md",
    "docs/adr/ADR-011-named-homage-boundary.md",
    "tests/check_ip_boundary.py",
    "tests/test_ip_boundary.py",
}
JAPANESE_FORBIDDEN = ("草薙素子", "公安9課", "笑い男", "人形使い", "タチコマ")
ENGLISH_FORBIDDEN = tuple(
    re.compile(rf"(?<![a-z0-9_]){term}(?![a-z0-9_])", re.IGNORECASE)
    for term in (r"ghost\s+in\s+the\s+shell", r"motoko\s+kusanagi", r"section\s+9")
)


def _public_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    files: list[Path] = []
    for relative in completed.stdout.splitlines():
        normalized = relative.replace("\\", "/")
        path = ROOT / relative
        if normalized not in ATTRIBUTION_EXEMPTIONS and path.is_file():
            files.append(path)
    return files


def _find_terms(text: str) -> list[str]:
    folded = text.casefold()
    findings = [term for term in JAPANESE_FORBIDDEN if term.casefold() in folded]
    findings.extend(pattern.pattern for pattern in ENGLISH_FORBIDDEN if pattern.search(text))
    return findings


def main() -> int:
    findings: list[str] = []
    for path in _public_files():
        raw = path.read_bytes()
        if b"\x00" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            findings.append(f"{path.relative_to(ROOT)}: UTF-8で読めません ({error})")
            continue
        findings.extend(f"{path.relative_to(ROOT)}: {term}" for term in _find_terms(text))
    if findings:
        raise SystemExit("ip-boundary: FAIL\n" + "\n".join(findings))
    print("ip-boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
