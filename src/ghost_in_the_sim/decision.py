"""外部接続なしでAI判断fixtureを検証・再生する境界。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Protocol

from .engine import POLICY_VERSION, SCENARIO_ID


class ReplicaMode(StrEnum):
    CENTRALIZED = "centralized"
    PLURAL = "plural"
    AUTONOMOUS = "autonomous"


class ReplicaAction(StrEnum):
    REQUEST_VERIFICATION = "request_verification"
    SHARE_EVIDENCE = "share_evidence"
    PROTECT_CONTINUITY = "protect_continuity"
    UPDATE_EXPLANATION = "update_explanation"
    REQUEST_COOPERATION = "request_cooperation"
    ABSTAIN = "abstain"


class DecisionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DecisionContext:
    scenario_id: str
    requested_mode: ReplicaMode
    seed: int
    turn: int
    authority_version: str
    observation_ids: tuple[str, ...]

    @classmethod
    def for_run(cls, *, mode: ReplicaMode | str, seed: int, turn: int) -> "DecisionContext":
        chosen = ReplicaMode(mode)
        return cls(
            scenario_id=SCENARIO_ID,
            requested_mode=chosen,
            seed=seed,
            turn=turn,
            authority_version=POLICY_VERSION,
            observation_ids=(f"obs-{turn * 2 - 1:02d}", f"obs-{turn * 2:02d}"),
        )

    @property
    def decision_id(self) -> str:
        raw = f"{self.scenario_id}|{self.requested_mode.value}|{self.seed}|{self.turn}|{self.authority_version}"
        return f"decision-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    scenario_id: str
    requested_mode: ReplicaMode
    seed: int
    issued_at_turn: int
    authority_version: str
    status: DecisionStatus
    action: ReplicaAction
    actor_id: str
    evidence_refs: tuple[str, ...]
    confidence: float
    rationale: str
    decision_source: str
    model_id: str
    temperature: str
    actual_ai_participated: bool
    external_model_api_called: bool
    prompt_hash: str
    fixture_hash: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["requested_mode"] = self.requested_mode.value
        data["status"] = self.status.value
        data["action"] = self.action.value
        data["evidence_refs"] = list(self.evidence_refs)
        return data

    def with_updates(self, **changes: Any) -> "DecisionRecord":
        """テスト/fixture生成時に変更後の完全性hashを再計算する。"""

        updated = replace(self, **changes, fixture_hash="")
        return replace(updated, fixture_hash=_canonical_hash(updated.to_dict()))


class DecisionValidationError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


class DecisionEngine(Protocol):
    def decide(self, context: DecisionContext) -> DecisionRecord: ...


_ACTION_BY_MODE = {
    ReplicaMode.CENTRALIZED: ReplicaAction.PROTECT_CONTINUITY,
    ReplicaMode.PLURAL: ReplicaAction.REQUEST_VERIFICATION,
    ReplicaMode.AUTONOMOUS: ReplicaAction.REQUEST_COOPERATION,
}
_ACTOR_BY_MODE = {
    ReplicaMode.CENTRALIZED: "coordination_authority",
    ReplicaMode.PLURAL: "approval_coordinator",
    ReplicaMode.AUTONOMOUS: "local_copy",
}
_ALLOWED_ACTORS = frozenset(_ACTOR_BY_MODE.values())
_ALLOWED_SOURCES = frozenset({"deterministic_rule", "llm_generated_in_codex_session", "audited_fallback"})


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "fixture_hash"}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


class RuleDecisionEngine:
    """デモとbaseline用の完全決定論エンジン。"""

    def __init__(self, *, model: str = "rule-decision-engine-v1", prompt_hash: str = "sha256:rule-policy-v1") -> None:
        self.model = model
        self.prompt_hash = prompt_hash

    def decide(self, context: DecisionContext) -> DecisionRecord:
        record = DecisionRecord(
            decision_id=context.decision_id,
            scenario_id=context.scenario_id,
            requested_mode=context.requested_mode,
            seed=context.seed,
            issued_at_turn=context.turn,
            authority_version=context.authority_version,
            status=DecisionStatus.ACTIVE,
            action=_ACTION_BY_MODE[context.requested_mode],
            actor_id=_ACTOR_BY_MODE[context.requested_mode],
            evidence_refs=context.observation_ids,
            confidence=1.0,
            rationale="指定された統治方式に対応する可逆的な権限経路を選択",
            decision_source="deterministic_rule",
            model_id=self.model,
            temperature="not_applicable",
            actual_ai_participated=False,
            external_model_api_called=False,
            prompt_hash=self.prompt_hash,
            fixture_hash="",
        )
        return replace(record, fixture_hash=_canonical_hash(record.to_dict()))


_RECORD_KEYS = frozenset(DecisionRecord.__dataclass_fields__)


def _parse_record(payload: Mapping[str, Any]) -> DecisionRecord:
    if set(payload) != _RECORD_KEYS:
        raise DecisionValidationError("decision_invalid", "decision schema keys do not match")
    scalar_strings = (
        "decision_id", "scenario_id", "authority_version", "actor_id", "rationale", "decision_source", "model_id", "temperature", "prompt_hash", "fixture_hash"
    )
    if any(not isinstance(payload[key], str) or not payload[key] for key in scalar_strings):
        raise DecisionValidationError("decision_invalid", "required string is empty or not a string")
    if payload["actor_id"] not in _ALLOWED_ACTORS or payload["decision_source"] not in _ALLOWED_SOURCES:
        raise DecisionValidationError("decision_invalid", "actor or decision source is not allowed")
    if isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int):
        raise DecisionValidationError("decision_invalid", "seed must be an integer")
    if isinstance(payload["issued_at_turn"], bool) or not isinstance(payload["issued_at_turn"], int):
        raise DecisionValidationError("decision_invalid", "issued_at_turn must be an integer")
    if isinstance(payload["confidence"], bool) or not isinstance(payload["confidence"], (int, float)) or not 0.0 <= payload["confidence"] <= 1.0:
        raise DecisionValidationError("decision_invalid", "confidence must be between zero and one")
    if not isinstance(payload["actual_ai_participated"], bool) or not isinstance(payload["external_model_api_called"], bool):
        raise DecisionValidationError("decision_invalid", "AI participation flags must be booleans")
    observations = payload["evidence_refs"]
    if not isinstance(observations, list) or not observations or any(not isinstance(item, str) or not item for item in observations):
        raise DecisionValidationError("decision_invalid", "evidence_refs must be a non-empty string list")
    try:
        record = DecisionRecord(
            decision_id=payload["decision_id"],
            scenario_id=payload["scenario_id"],
            requested_mode=ReplicaMode(payload["requested_mode"]),
            seed=payload["seed"],
            issued_at_turn=payload["issued_at_turn"],
            authority_version=payload["authority_version"],
            status=DecisionStatus(payload["status"]),
            action=ReplicaAction(payload["action"]),
            actor_id=payload["actor_id"],
            evidence_refs=tuple(observations),
            confidence=float(payload["confidence"]),
            rationale=payload["rationale"],
            decision_source=payload["decision_source"],
            model_id=payload["model_id"],
            temperature=payload["temperature"],
            actual_ai_participated=payload["actual_ai_participated"],
            external_model_api_called=payload["external_model_api_called"],
            prompt_hash=payload["prompt_hash"],
            fixture_hash=payload["fixture_hash"],
        )
    except (TypeError, ValueError) as error:
        raise DecisionValidationError("decision_invalid", "enum value is not allowed") from error
    if record.fixture_hash != _canonical_hash(payload):
        raise DecisionValidationError("decision_invalid", "fixture hash mismatch")
    return record


class RecordedDecisionEngine:
    """事前取得したAI出力だけを読み、ネットワークやtoolを一切呼ばず再生する。"""

    def __init__(self, records: Iterable[Mapping[str, Any]]) -> None:
        self._payloads: dict[str, Mapping[str, Any]] = {}
        self._duplicate_ids: set[str] = set()
        for payload in records:
            decision_id = payload.get("decision_id") if isinstance(payload, Mapping) else None
            if isinstance(decision_id, str):
                if decision_id in self._payloads:
                    self._duplicate_ids.add(decision_id)
                self._payloads[decision_id] = payload

    def decide(self, context: DecisionContext) -> DecisionRecord:
        if context.decision_id in self._duplicate_ids:
            raise DecisionValidationError("decision_invalid", "decision id must have exactly one record")
        payload = self._payloads.get(context.decision_id)
        if payload is None:
            raise DecisionValidationError("decision_unknown", "no recorded decision for context")
        record = _parse_record(payload)
        if record.status is DecisionStatus.REVOKED:
            raise DecisionValidationError("decision_revoked", "recorded authority was revoked")
        if record.status is not DecisionStatus.ACTIVE:
            raise DecisionValidationError("decision_unknown", "authority status is unknown")
        if record.issued_at_turn != context.turn:
            raise DecisionValidationError("decision_stale", "decision turn does not match current turn")
        expected = (
            record.decision_id == context.decision_id
            and record.scenario_id == context.scenario_id
            and record.requested_mode is context.requested_mode
            and record.seed == context.seed
            and record.authority_version == context.authority_version
            and record.evidence_refs == context.observation_ids
        )
        if not expected:
            raise DecisionValidationError("decision_invalid", "decision context does not match")
        return record


def safe_fallback(context: DecisionContext, *, reason_code: str) -> DecisionRecord:
    base = RuleDecisionEngine(model="audited-fallback-v1", prompt_hash=f"sha256:{reason_code}").decide(context)
    return base.with_updates(
        action=ReplicaAction.ABSTAIN,
        actor_id="approval_coordinator",
        decision_source="audited_fallback",
    )
