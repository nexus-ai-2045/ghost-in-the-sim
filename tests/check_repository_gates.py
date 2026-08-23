"""リポジトリゲートの配布契約を標準ライブラリだけで検査する。"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "scripts/check_repository_contract.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("repository_contract", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("検査器を読み込めません")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    workflow = (ROOT / ".github/workflows/repository-contract-trusted.yml").read_text(encoding="utf-8")
    required_fragments = (
        "pull_request_target:",
        "contents: read",
        "pull-requests: read",
        "refs/pull/",
        "persist-credentials: false",
        "scripts/check_repository_contract.py",
        "--base-root",
        "--candidate-root",
        "advisory",
    )
    missing = [fragment for fragment in required_fragments if fragment not in workflow]
    if missing:
        raise SystemExit("repository-gates: FAIL\n" + "\n".join(missing))

    verifier = load_verifier()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        base = root / "base"
        candidate = root / "candidate"
        for relative in verifier.PROTECTED_GATE_PATHS:
            for tree in (base, candidate):
                path = tree / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"protected:{relative.as_posix()}\n", encoding="utf-8")
        verifier.verify_candidate(base, candidate)
        (candidate / verifier.PROTECTED_GATE_PATHS[0]).write_text("weakened\n", encoding="utf-8")
        try:
            verifier.verify_candidate(base, candidate)
        except verifier.VerificationError:
            pass
        else:
            raise SystemExit("repository-gates: FAIL\n保護ファイルの変更を検知できません")

    print("repository-gates: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
