"""Raw run payloadからMVPの派生証拠を一意に投影する。"""

from __future__ import annotations

from typing import Any


HIGHER_IS_BETTER = frozenset({"continuity", "evidence_calibration", "public_trust", "dissent_reach"})


def metric_delta(candidate: float, baseline: float, metric: str) -> float:
    """指標の向きを揃えた candidate−baseline 差。Python 側の唯一の定義（JS 側は独立検証として別実装）。"""

    value = candidate - baseline if metric in HIGHER_IS_BETTER else baseline - candidate
    return round(value, 6)


def project_refutation_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    by_mode_seed = {(run["requested_mode"], run["seed"]): run for run in payload["runs"]}
    definitions = (
        ("plural_always_better_without_tradeoff", "plural", "centralized"),
        ("centralized_always_better_without_tradeoff", "centralized", "plural"),
    )
    checks = []
    for check_id, candidate_mode, baseline_mode in definitions:
        observation_id = f"{candidate_mode}_dominates_{baseline_mode}"
        observations = []
        for seed in sorted(payload["seeds"]):
            candidate = by_mode_seed.get((candidate_mode, seed))
            baseline = by_mode_seed.get((baseline_mode, seed))
            if (
                not candidate
                or not baseline
                or candidate["audit"]["fallback_applied"]
                or baseline["audit"]["fallback_applied"]
                or candidate["effective_mode"] != candidate_mode
                or baseline["effective_mode"] != baseline_mode
            ):
                observations.append(
                    {
                        "check_id": observation_id,
                        "seed": seed,
                        "status": "not_observable",
                        "evidence": {"reason": "required_effective_mode_missing"},
                    }
                )
                continue
            deltas = {
                metric: metric_delta(candidate["metrics"][metric], baseline["metrics"][metric], metric)
                for metric in sorted(candidate["metrics"].keys() & baseline["metrics"].keys())
            }
            dominates = bool(deltas) and all(value >= 0 for value in deltas.values()) and any(value > 0 for value in deltas.values())
            observations.append(
                {
                    "check_id": observation_id,
                    "seed": seed,
                    "status": "triggered" if dominates else "not_triggered" if deltas else "not_observable",
                    "evidence": {
                        "candidate_run_id": candidate["manifest"]["run_id"],
                        "baseline_run_id": baseline["manifest"]["run_id"],
                        "direction_adjusted_metric_deltas": deltas,
                    },
                }
            )
        observable = [item for item in observations if item["status"] != "not_observable"]
        complete = len(observable) == len(observations) and bool(observations)
        checks.append(
            {
                "check_id": check_id,
                "seed": None,
                "status": (
                    "triggered"
                    if complete and all(item["status"] == "triggered" for item in observable)
                    else "not_triggered"
                    if complete
                    else "not_observable"
                ),
                "evidence": {"per_seed": observations},
            }
        )
    return checks


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
    return {
        "seeds": sorted(set(payload["seeds"])),
        "run_count": len(runs),
        "failure_run_ids": failure_ids,
        "ai_replay": replay,
        "plural_vs_centralized_sign_reversals": project_sign_reversals(payload),
        "refutation_checks": project_refutation_checks(payload),
    }


def project_sign_reversals(payload: dict[str, Any]) -> list[str]:
    """plural対centralizedでseed間に符号反転がある指標。result cardと派生証拠の唯一の定義。"""

    by_mode_seed = {(run["requested_mode"], run["seed"]): run for run in payload["runs"]}
    paired = []
    for seed in sorted(set(payload["seeds"])):
        plural = by_mode_seed.get(("plural", seed))
        centralized = by_mode_seed.get(("centralized", seed))
        if plural and centralized and not plural["audit"]["fallback_applied"] and not centralized["audit"]["fallback_applied"]:
            paired.append((plural, centralized))
    if not paired:
        return []
    reversals: list[str] = []
    for metric in sorted(paired[0][0]["metrics"]):
        deltas = []
        for plural, centralized in paired:
            raw = plural["metrics"][metric] - centralized["metrics"][metric]
            deltas.append(raw if metric in HIGHER_IS_BETTER else -raw)
        if any(value < 0 for value in deltas) and any(value > 0 for value in deltas):
            reversals.append(metric)
    return reversals


def validate_derived_evidence(payload: dict[str, Any]) -> None:
    seeds = payload.get("seeds")
    runs = payload.get("runs")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds)
        or len(seeds) != len(set(seeds))
        or not isinstance(runs, list)
        or set(seeds) != {run.get("seed") for run in runs if isinstance(run, dict)}
    ):
        raise ValueError("seeds must be unique integers matching raw runs")
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
    if card["refutation_checks"] != projected["refutation_checks"]:
        raise ValueError("refutation checks do not match raw runs")
