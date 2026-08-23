"""ローカル実験の入出力境界。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .engine import Condition, RunResult, run_experiment


def write_run(result: RunResult, output_dir: Path) -> None:
    """再現用manifest、イベント列、単一runの指標をローカルへ出力する。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_manifest.json").write_text(
        json.dumps(result.manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "events.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for event in result.events:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    (output_dir / "metrics.json").write_text(
        json.dumps(result.metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "final_state.json").write_text(
        json.dumps(asdict(result.final_state), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="架空シナリオの決定論的比較実験を実行します")
    parser.add_argument("--condition", choices=[item.value for item in Condition], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--turn-limit", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(condition=args.condition, seed=args.seed, turn_limit=args.turn_limit)
    write_run(result, args.output_dir)
    print(json.dumps(result.manifest(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
