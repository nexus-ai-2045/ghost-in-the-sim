"""公開面へ第三者作品の固有識別子が混入しないことを検査する。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOTS = (
    ROOT / "README.md",
    ROOT / "docs" / "architecture",
    ROOT / "docs" / "design",
    ROOT / "docs" / "world",
    ROOT / "web",
)
FORBIDDEN = (
    "攻殻機動隊",
    "ghost in the shell",
    "草薙素子",
    "motoko kusanagi",
    "公安9課",
    "section 9",
    "笑い男",
    "人形使い",
    "タチコマ",
)


def _public_files() -> list[Path]:
    files: list[Path] = []
    for root in PUBLIC_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(
                path
                for path in root.rglob("*")
                if path.suffix.lower() in {".md", ".html", ".css", ".js", ".json"}
            )
    return files


def main() -> int:
    findings: list[str] = []
    for path in _public_files():
        text = path.read_text(encoding="utf-8").casefold()
        for term in FORBIDDEN:
            if term.casefold() in text:
                findings.append(f"{path.relative_to(ROOT)}: {term}")
    if findings:
        raise SystemExit("ip-boundary: FAIL\n" + "\n".join(findings))
    print("ip-boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
