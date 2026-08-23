"""公開対象に含めない原典・認証素材の追跡を検査する。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath


FORBIDDEN_SUFFIXES = {".zip", ".cbz", ".cbr", ".pem", ".key"}
FORBIDDEN_PARTS = {"raw", "ocr", "pages", "scans", "sources"}


def tracked_files() -> list[PurePosixPath]:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    )
    return [PurePosixPath(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings = []
    for path in tracked_files():
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"禁止拡張子: {path}")
        if any(part.lower() in FORBIDDEN_PARTS for part in path.parts):
            findings.append(f"公開除外ディレクトリ: {path}")
    if findings:
        print("public-boundary: FAIL", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("public-boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
