"""Raw run payloadからMVPの派生証拠を一意に投影する。"""

from __future__ import annotations

from typing import Any


HIGHER_IS_BETTER = frozenset({"continuity", "evidence_calibration", "public_trust", "dissent_reach"})


def project_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    runs = payload["runs"]
    failure_ids = sorted(
        run["manifest"]["run_id"]
        for run in runs
        if run["manifest"]["termination_reason"] != "turn_limit_reached"
        or len(run["events"]) != run["manifest"]["turn_limit"]
    )
    evidence_runs = payload.get("ai_evidence_runs")
    replay = None
    if evidence_runs is not None:
        replay = {
            "run_count": len(evidence_runs),
            "decision_sources": sorted(
                {decision["decision_source"] for run in evidence_runs for decision in run["decisions"]}
            ),
            "fallback_count": sum(bool(run["audit"]["fallback_applied"]) for run in evidence_runs),
        }
    by_mode_seed = {(run["requested_mode"], run["seed"]): run for run in runs}
    reversals: list[str] = []
    seeds = sorted(set(payload["seeds"]))
    paired = []
    for seed in seeds:
        plural = by_mode_seed.get(("plural", seed))
        centralized = by_mode_seed.get(("centralized", seed))
        if plural and centralized and not plural["audit"]["fallback_applied"] and not centralized["audit"]["fallback_applied"]:
            paired.append((plural, centralized))
    if paired:
        for metric in sorted(paired[0][0]["metrics"]):
            deltas = []
            for plural, centralized in paired:
                raw = plural["metrics"][metric] - centralized["metrics"][metric]
                deltas.append(raw if metric in HIGHER_IS_BETTER else -raw)
            if any(value < 0 for value in deltas) and any(value > 0 for value in deltas):
                reversals.append(metric)
    return {
        "seeds": seeds,
        "run_count": len(runs),
        "failure_run_ids": failure_ids,
        "ai_replay": replay,
        "plural_vs_centralized_sign_reversals": reversals,
    }


def validate_derived_evidence(payload: dict[str, Any]) -> None:
    projected = project_evidence(payload)
    if payload.get("evidence_summary") != projected:
        raise ValueError("evidence_summary does not match raw runs")
    card = payload["result_card"]
    card_failures = sorted(item["run_id"] for item in card["failure_runs"])
    if card_failures != projected["failure_run_ids"]:
        raise ValueError("failure_runs do not match raw runs")
    if card.get("ai_replay_evidence") != projected["ai_replay"]:
        raise ValueError("ai replay summary does not match evidence runs")
    if card["seed_sensitivity"]["plural_vs_centralized_sign_reversals"] != projected["plural_vs_centralized_sign_reversals"]:
        raise ValueError("seed sensitivity does not match raw runs")
