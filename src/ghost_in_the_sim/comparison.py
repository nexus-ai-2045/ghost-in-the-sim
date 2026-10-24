"""同一seedで条件差を読むための小さな比較器。"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import Condition, RunResult, run_experiment


@dataclass(frozen=True)
class PairedComparison:
    seed: int
    baseline: RunResult
    candidate: RunResult
    deltas: dict[str, float]


def compare_conditions(*, baseline: Condition | str, candidate: Condition | str, seed: int, turn_limit: int = 12) -> PairedComparison:
    """共通seed（CRN）で二条件を比較し、政策優劣の断定はしない。"""

    left = run_experiment(condition=baseline, seed=seed, turn_limit=turn_limit)
    right = run_experiment(condition=candidate, seed=seed, turn_limit=turn_limit)
    keys = tuple(left.metrics)
    return PairedComparison(
        seed=seed,
        baseline=left,
        candidate=right,
        deltas={key: round(right.metrics[key] - left.metrics[key], 6) for key in keys},
    )
