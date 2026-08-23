"""候補PRがbase側のリポジトリ検査境界を置換していないか確認する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROTECTED_GATE_PATHS = (
    Path(".github/workflows/repository-contract.yml"),
    Path(".github/workflows/repository-contract-trusted.yml"),
    Path(".repo-preflight-consistency.json"),
    Path("scripts/check_repository_contract.py"),
)


class VerificationError(ValueError):
    """候補を信頼済みbaseから検証できない。"""


def regular_file(root: Path, relative: Path) -> Path:
    root = root.resolve()
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise VerificationError(f"symlinkは許可されません: {relative}")
    if not current.is_file():
        raise VerificationError(f"通常ファイルではありません: {relative}")
    try:
        current.resolve(strict=True).relative_to(root)
    except ValueError as exc:
        raise VerificationError(f"repo外を参照しています: {relative}") from exc
    return current


def verify_candidate(base_root: Path, candidate_root: Path) -> None:
    for relative in PROTECTED_GATE_PATHS:
        base = regular_file(base_root, relative)
        candidate = regular_file(candidate_root, relative)
        if base.read_bytes() != candidate.read_bytes():
            raise VerificationError(
                f"保護されたゲートが変更されています: {relative}; "
                "別のbootstrap PRとして人間レビューしてください"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verify_candidate(args.base_root, args.candidate_root)
    except VerificationError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print("ADVISORY: candidate preserves the trusted repository gate boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
