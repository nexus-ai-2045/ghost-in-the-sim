"""3方式 x 固定seedの再現可能なバッチ実行CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .decision import RecordedDecisionEngine
from .actual_trace import load_actual_ai_trace
from .replica import DEFAULT_SEEDS, run_replica_batch


def _load_fixture(path: Path) -> RecordedDecisionEngine:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("decision fixture must be a JSON array of objects")
    return RecordedDecisionEngine(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="架空都市圏ハーバー・ループのAI複製配備MVPを実行します")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turn-limit", type=int, default=12)
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument("--decision-fixture", type=Path)
    parser.add_argument("--actual-ai-trace", type=Path)
    args = parser.parse_args()
    if args.decision_fixture and args.actual_ai_trace:
        parser.error("--decision-fixture and --actual-ai-trace are mutually exclusive")
    decision_engine = (
        RecordedDecisionEngine(record.to_dict() for record in load_actual_ai_trace(args.actual_ai_trace))
        if args.actual_ai_trace
        else _load_fixture(args.decision_fixture)
        if args.decision_fixture
        else None
    )
    batch = run_replica_batch(
        seeds=tuple(args.seeds) if args.seeds else DEFAULT_SEEDS,
        turn_limit=args.turn_limit,
        decision_engine=decision_engine,
    )
    payload = batch.to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "run_count": len(batch.runs), "seeds": list(batch.seeds)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
