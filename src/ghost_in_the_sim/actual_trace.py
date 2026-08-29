"""Codex session内で生成済みのAI判断raw traceを安全なreplay recordへ正規化する。"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .decision import DecisionContext, DecisionRecord, DecisionStatus, ReplicaAction, ReplicaMode, RuleDecisionEngine


_MODE_ALIASES = {
    "centralized": ReplicaMode.CENTRALIZED,
    "joint_approval": ReplicaMode.PLURAL,
    "plural": ReplicaMode.PLURAL,
    "autonomous_copies": ReplicaMode.AUTONOMOUS,
    "autonomous": ReplicaMode.AUTONOMOUS,
}
_RAW_KEYS = frozenset({"mode_id", "turn", "actor_id", "action", "evidence_refs", "confidence", "reservation", "rationale"})
_PROVENANCE_KEYS = frozenset({"decision_source", "model_id", "temperature", "actual_ai_participated", "external_model_api_called"})


def _trace_hash_from_bytes(raw_bytes: bytes) -> str:
    """Return a checkout-independent hash for the UTF-8 JSON trace."""

    normalized = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"sha256:{sha256(normalized).hexdigest()}"


def load_actual_ai_trace(path: Path, *, seed: int = 42) -> list[DecisionRecord]:
    raw_bytes = path.read_bytes()
    payload: Any = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"provenance", "decisions"}:
        raise ValueError("actual AI trace must contain provenance and decisions only")
    provenance = payload["provenance"]
    decisions = payload["decisions"]
    if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_KEYS:
        raise ValueError("actual AI provenance schema mismatch")
    if not isinstance(decisions, list) or len(decisions) != 9:
        raise ValueError("actual AI trace must contain exactly nine decisions")
    prompt_hash = _trace_hash_from_bytes(raw_bytes)
    records: list[DecisionRecord] = []
    seen: set[tuple[ReplicaMode, int]] = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) != _RAW_KEYS:
            raise ValueError("actual AI decision schema mismatch")
        try:
            mode = _MODE_ALIASES[item["mode_id"]]
            action = ReplicaAction(item["action"])
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError("actual AI mode or action is not allowed") from error
        turn = item["turn"]
        if isinstance(turn, bool) or not isinstance(turn, int) or turn not in {1, 2, 3}:
            raise ValueError("actual AI turn must be 1, 2, or 3")
        if (mode, turn) in seen:
            raise ValueError("actual AI mode/turn pair is duplicated")
        seen.add((mode, turn))
        context = DecisionContext.for_run(mode=mode, seed=seed, turn=turn)
        base = RuleDecisionEngine(model=provenance["model_id"], prompt_hash=prompt_hash).decide(context)
        record = base.with_updates(
            status=DecisionStatus.ACTIVE,
            action=action,
            actor_id=item["actor_id"],
            evidence_refs=tuple(item["evidence_refs"]),
            confidence=item["confidence"],
            rationale=f"{item['rationale']} 留保: {item['reservation']}",
            decision_source=provenance["decision_source"],
            model_id=provenance["model_id"],
            temperature=provenance["temperature"],
            actual_ai_participated=provenance["actual_ai_participated"],
            external_model_api_called=provenance["external_model_api_called"],
        )
        records.append(record)
    if seen != {(mode, turn) for mode in ReplicaMode for turn in (1, 2, 3)}:
        raise ValueError("actual AI trace does not cover all three modes and turns")
    return records
