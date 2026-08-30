"""meta-security-run-bundle/v1を生成・検証するCLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .actual_trace import load_actual_ai_trace
from .decision import RecordedDecisionEngine, ReplicaMode
from .replica import run_replica_batch
from .run_bundle import build_run_bundle, verify_run_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="ポセイドン危機対応runをportable bundleへ出力します")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=[mode.value for mode in ReplicaMode], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--turn-limit", type=int, default=12)
    parser.add_argument("--actual-ai-trace", type=Path)
    args = parser.parse_args()
    if args.turn_limit < 1:
        parser.error("--turn-limit must be positive")
    engine = None
    if args.actual_ai_trace:
        records = load_actual_ai_trace(args.actual_ai_trace)
        engine = RecordedDecisionEngine(record.to_dict() for record in records)
    batch = run_replica_batch(seeds=(args.seed,), turn_limit=args.turn_limit, decision_engine=engine)
    selected = next(run for run in batch.runs if run.requested_mode.value == args.mode)
    bundle = build_run_bundle(selected)
    verify_run_bundle(bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "run_id": bundle["run_id"], "schema_version": bundle["schema_version"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
