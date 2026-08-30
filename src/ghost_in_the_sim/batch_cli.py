"""3方式 x 固定seedの再現可能なバッチ実行CLI。"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .decision import RecordedDecisionEngine, ReplicaMode
from .actual_trace import load_actual_ai_trace
from .replica import DEFAULT_SEEDS, build_result_card, run_ensemble_scenario, run_replica_batch
from .evidence_contract import project_evidence, validate_derived_evidence
from .run_bundle import build_verified_run_bundle
from .operative import OperationalFocus, PauseResponse, build_gameplay_plan


ARTIFACT_INPUTS = (
    "src/ghost_in_the_sim/engine.py",
    "src/ghost_in_the_sim/decision.py",
    "src/ghost_in_the_sim/replica.py",
    "src/ghost_in_the_sim/actual_trace.py",
    "src/ghost_in_the_sim/batch_cli.py",
    "src/ghost_in_the_sim/evidence_contract.py",
    "src/ghost_in_the_sim/scenario.py",
    "src/ghost_in_the_sim/operative.py",
    "src/ghost_in_the_sim/run_bundle.py",
    "src/ghost_in_the_sim/agent_turn.py",
    "src/ghost_in_the_sim/agent_providers.py",
    "src/ghost_in_the_sim/agent_schedule.py",
    "scripts/render_results.py",
)


def build_playable_trajectories() -> list[dict[str, Any]]:
    """全直積を避け、同じseedで因果差を示すP0の4経路だけを生成する。"""

    specifications = (
        ("hospital-joint-hold", OperationalFocus.HOSPITAL, ReplicaMode.PLURAL, PauseResponse.HOLD),
        ("port-joint-hold", OperationalFocus.PORT, ReplicaMode.PLURAL, PauseResponse.HOLD),
        ("hospital-joint-proceed", OperationalFocus.HOSPITAL, ReplicaMode.PLURAL, PauseResponse.PROCEED),
        ("hospital-single-proceed", OperationalFocus.HOSPITAL, ReplicaMode.CENTRALIZED, PauseResponse.PROCEED),
    )
    trajectories = []
    for trajectory_id, focus, mode, pause_response in specifications:
        run = run_replica_batch(
            seeds=(42,), operative_plan=build_gameplay_plan(focus=focus, pause_response=pause_response)
        )
        selected = next(item for item in run.runs if item.requested_mode is mode)
        trajectories.append({"trajectory_id": trajectory_id, "bundle": build_verified_run_bundle(selected)})
    return trajectories


def build_ensemble_runs() -> list[dict[str, Any]]:
    """同じ世界seedで、3統治方式の4主体interactionを比較可能にする。"""

    return [
        build_verified_run_bundle(run_ensemble_scenario(requested_mode=mode, seed=42))
        for mode in ReplicaMode
    ]


def _artifact_revision_from_inputs(inputs: dict[str, bytes]) -> str:
    digest = sha256()
    for name in sorted(inputs):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(inputs[name].replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()[:16]


def artifact_revision(
    root: Path,
    *,
    comparison_fixture: Path | None = None,
    evidence_fixture: Path | None = None,
) -> str:
    inputs = {name: (root / name).read_bytes() for name in ARTIFACT_INPUTS}
    if comparison_fixture is not None:
        inputs["selected-comparison-fixture"] = comparison_fixture.read_bytes()
    if evidence_fixture is not None:
        inputs["selected-evidence-fixture"] = evidence_fixture.read_bytes()
    return _artifact_revision_from_inputs(inputs)


def _load_fixture(path: Path) -> RecordedDecisionEngine:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("decision fixture must be a JSON array of objects")
    return RecordedDecisionEngine(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="海洋複合都市圏ポセイドンのAI複製配備MVPを実行します")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turn-limit", type=int, default=12)
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument("--decision-fixture", type=Path)
    parser.add_argument("--actual-ai-trace", type=Path)
    parser.add_argument(
        "--actual-ai-evidence-trace",
        type=Path,
        help="比較条件には混ぜず、実AI由来fixtureの独立replay証拠を同じartifactへ記録します",
    )
    args = parser.parse_args()
    if args.decision_fixture and args.actual_ai_trace:
        parser.error("--decision-fixture and --actual-ai-trace are mutually exclusive")
    if args.actual_ai_evidence_trace and (args.decision_fixture or args.actual_ai_trace):
        parser.error("--actual-ai-evidence-trace requires the deterministic rule comparison provider")
    if args.seeds and len(set(args.seeds)) != len(args.seeds):
        parser.error("--seed values must be unique")
    run_seeds = tuple(args.seeds) if args.seeds else DEFAULT_SEEDS
    decision_engine = None
    if args.actual_ai_trace:
        trace_records = load_actual_ai_trace(args.actual_ai_trace)
        trace_seeds = sorted({record.seed for record in trace_records})
        uncovered = sorted(set(run_seeds) - set(trace_seeds))
        if uncovered:
            parser.error(
                f"--actual-ai-trace covers seeds {trace_seeds} but the batch requests uncovered seeds {uncovered}; "
                "pass matching --seed values instead of letting every uncovered run fall back"
            )
        decision_engine = RecordedDecisionEngine(record.to_dict() for record in trace_records)
    elif args.decision_fixture:
        decision_engine = _load_fixture(args.decision_fixture)
    batch = run_replica_batch(
        seeds=run_seeds,
        turn_limit=args.turn_limit,
        decision_engine=decision_engine,
    )
    payload = batch.to_dict()
    payload["experience_capability"] = {
        "schema_version": "ghost-in-the-sim-experience/v1",
        "renderer_mode": "artifact-only",
        "operation_console": True,
        "ai_emergence_console": True,
    }
    payload["trajectories"] = [build_verified_run_bundle(run) for run in batch.runs]
    payload["playable_trajectories"] = build_playable_trajectories()
    payload["ensemble_runs"] = build_ensemble_runs()
    payload["result_card"] = build_result_card(batch)
    root = Path(__file__).resolve().parents[2]
    payload["artifact_revision"] = artifact_revision(
        root,
        comparison_fixture=args.actual_ai_trace or args.decision_fixture,
        evidence_fixture=args.actual_ai_evidence_trace,
    )
    payload["result_card"]["artifact_revision"] = payload["artifact_revision"]
    if args.actual_ai_evidence_trace:
        evidence_records = load_actual_ai_trace(args.actual_ai_evidence_trace)
        evidence_batch = run_replica_batch(
            seeds=(42,),
            turn_limit=args.turn_limit,
            decision_engine=RecordedDecisionEngine(record.to_dict() for record in evidence_records),
        )
        payload["ai_evidence_runs"] = [run.to_dict() for run in evidence_batch.runs]
        payload["result_card"]["ai_replay_evidence"] = {
            "run_count": len(evidence_batch.runs),
            "decision_sources": sorted(
                {decision.decision_source for run in evidence_batch.runs for decision in run.decisions}
            ),
            "fallback_count": sum(run.audit.fallback_applied for run in evidence_batch.runs),
        }
    payload["evidence_summary"] = project_evidence(payload)
    validate_derived_evidence(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "run_count": len(batch.runs), "seeds": list(batch.seeds)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
