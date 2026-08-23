"""同一seedの条件比較を、結果ファイルとして残すためのCLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .comparison import compare_conditions
from .engine import Condition


def main() -> int:
    parser = argparse.ArgumentParser(description="共通seedで二条件を比較します")
    parser.add_argument("--baseline", choices=[item.value for item in Condition], required=True)
    parser.add_argument("--candidate", choices=[item.value for item in Condition], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--turn-limit", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    comparison = compare_conditions(
        baseline=args.baseline,
        candidate=args.candidate,
        seed=args.seed,
        turn_limit=args.turn_limit,
    )
    payload = {
        "method": "paired common-random-numbers comparison",
        "seed": comparison.seed,
        "baseline": comparison.baseline.manifest(),
        "candidate": comparison.candidate.manifest(),
        "operands": {
            "baseline_metrics": comparison.baseline.metrics,
            "candidate_metrics": comparison.candidate.metrics,
        },
        "deltas": comparison.deltas,
        "interpretation_boundary": "仮定下の比較であり、現実予測や政策推奨ではない。",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
