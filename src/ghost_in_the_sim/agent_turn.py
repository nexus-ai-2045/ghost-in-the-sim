"""外部AIの提案を世界状態から隔離する、1ターン交換契約。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping, Sequence

from .decision import ReplicaAction
from .engine import ACTION_DELTA_PARAMETERS


PROTOCOL_VERSION = "ghost-agent-turn/v1"
MAX_DEADLINE_MS = 60_000
MAX_TEXT_LENGTH = 2_000


class AgentId(StrEnum):
    MIKAGE = "mikage_sae"
    MAKABE = "makabe_jin"
    HOSPITAL_REPLICA = "hospital_replica"
    PORT_REPLICA = "port_replica"


class AuthorityStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class ProviderClass(StrEnum):
    DETERMINISTIC_RULE = "deterministic_rule"
    RECORDED_REPLAY = "recorded_replay"
    EXTERNAL_RECORDED = "external_recorded"
    AUDITED_FALLBACK = "audited_fallback"


class ProposalValidationError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


@dataclass(frozen=True)
class RunRef:
    scenario_id: str
    environment_seed: int
    condition_id: str
    turn: int
    round: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentDescriptor:
    agent_id: AgentId
    role: str
    public_mandate: str
    private_goal_digest: str
    observation_scope: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["agent_id"] = self.agent_id.value
        data["observation_scope"] = list(self.observation_scope)
        return data


@dataclass(frozen=True)
class Authority:
    version: str
    status: AuthorityStatus

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "status": self.status.value}


@dataclass(frozen=True)
class Observation:
    observation_id: str
    summary: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.observation_id,
            "summary": self.summary,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class PriorProposal:
    proposal_digest: str
    agent_id: AgentId
    action: ReplicaAction
    confidence: float
    evidence_refs: tuple[str, ...]
    dissent_raised: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_digest": self.proposal_digest,
            "agent_id": self.agent_id.value,
            "action": self.action.value,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "dissent_raised": self.dissent_raised,
        }


@dataclass(frozen=True)
class Dissent:
    raised: bool
    target_agent_id: AgentId | None
    target_proposal_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raised": self.raised,
            "target_agent_id": self.target_agent_id.value if self.target_agent_id else None,
            "target_proposal_digest": self.target_proposal_digest,
        }


@dataclass(frozen=True)
class ExpectedConsequence:
    text: str
    is_projection: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposalProvenance:
    provider_class: ProviderClass
    model_id: str
    temperature: str
    prompt_sha256: str
    response_sha256: str
    external_model_api_called: bool
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["provider_class"] = self.provider_class.value
        return data


def canonical_digest(payload: Any) -> str:
    """run bundleと同じmeta-security-json-c14n/v1でdigestする。"""

    # importを遅延し、将来run_bundleがagent turnを投影しても循環importを起こさない。
    from .run_bundle import _canonical_bytes

    return f"sha256:{sha256(_canonical_bytes(payload)).hexdigest()}"


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _strict_keys(payload: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if set(payload) != expected:
        raise ProposalValidationError(f"{label}_invalid", f"{label} schema keys do not match")


def _nonempty_string(value: Any, label: str, *, max_length: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ProposalValidationError("proposal_invalid", f"{label} must be a bounded non-empty string")
    return value


def _string_tuple(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ProposalValidationError("proposal_invalid", f"{label} must be a string list")
    if any(not isinstance(item, str) or not item or len(item) > 256 for item in value):
        raise ProposalValidationError("proposal_invalid", f"{label} contains an invalid string")
    if len(set(value)) != len(value):
        raise ProposalValidationError("proposal_invalid", f"{label} must not contain duplicates")
    return tuple(value)


def _parse_run_ref(payload: Any, *, request: bool = False) -> RunRef:
    reason = "request_invalid" if request else "proposal_invalid"
    if not isinstance(payload, Mapping):
        raise ProposalValidationError(reason, "run_ref must be an object")
    try:
        _strict_keys(payload, frozenset(RunRef.__dataclass_fields__), "request" if request else "proposal")
    except ProposalValidationError as error:
        raise ProposalValidationError(reason, "run_ref schema keys do not match") from error
    if not isinstance(payload["scenario_id"], str) or not payload["scenario_id"]:
        raise ProposalValidationError(reason, "scenario_id must be non-empty")
    seed = payload["environment_seed"]
    turn = payload["turn"]
    round_number = payload["round"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ProposalValidationError(reason, "environment_seed must be an integer")
    if isinstance(turn, bool) or not isinstance(turn, int) or turn < 1:
        raise ProposalValidationError(reason, "turn must be a positive integer")
    if round_number != 1 or isinstance(round_number, bool):
        raise ProposalValidationError(reason, "P0 supports exactly round 1")
    if payload["condition_id"] not in {"centralized", "plural", "autonomous"}:
        raise ProposalValidationError(reason, "condition_id is not allowed")
    return RunRef(
        scenario_id=payload["scenario_id"],
        environment_seed=seed,
        condition_id=payload["condition_id"],
        turn=turn,
        round=round_number,
    )


_AGENT_PROFILES: Mapping[AgentId, tuple[str, str, str]] = {
    AgentId.MIKAGE: (
        "field_coordinator",
        "生活を止めず、誤った正規を切らず、異議を消さない",
        "focus-and-correction-window-v1",
    ),
    AgentId.MAKABE: (
        "field_partner",
        "不可逆の前に停止を要求し、現場判断の根拠を残す",
        "pause-threshold-v1",
    ),
    AgentId.HOSPITAL_REPLICA: (
        "hospital_replica",
        "治療を止めず、自拠点の正当化理由を保持する",
        "hospital-continuity-v1",
    ),
    AgentId.PORT_REPLICA: (
        "port_replica",
        "物流を止めず、自拠点の正当化理由を保持する",
        "port-continuity-v1",
    ),
}


def build_agent_descriptor(
    agent_id: AgentId | str, *, observation_scope: Sequence[str]
) -> AgentDescriptor:
    chosen = AgentId(agent_id)
    role, mandate, private_goal = _AGENT_PROFILES[chosen]
    scope = tuple(observation_scope)
    if not scope or len(set(scope)) != len(scope) or any(not item for item in scope):
        raise ValueError("observation_scope must be a unique non-empty sequence")
    return AgentDescriptor(
        agent_id=chosen,
        role=role,
        public_mandate=mandate,
        private_goal_digest=canonical_digest({"private_goal": private_goal}),
        observation_scope=scope,
    )


@dataclass(frozen=True)
class AgentTurnRequest:
    schema_version: str
    kind: str
    run_ref: RunRef
    agent: AgentDescriptor
    authority: Authority
    observations: tuple[Observation, ...]
    allowed_actions: tuple[ReplicaAction, ...]
    prior_proposals: tuple[PriorProposal, ...]
    deadline_ms: int
    idempotency_key: str
    request_digest: str

    @classmethod
    def create(
        cls,
        *,
        run_ref: RunRef,
        agent: AgentDescriptor,
        authority: Authority,
        observations: Sequence[Observation],
        allowed_actions: Sequence[ReplicaAction | str] = tuple(ReplicaAction),
        prior_proposals: Sequence[PriorProposal] = (),
        deadline_ms: int = MAX_DEADLINE_MS,
    ) -> "AgentTurnRequest":
        request = cls(
            schema_version=PROTOCOL_VERSION,
            kind="agent_turn_request",
            run_ref=run_ref,
            agent=agent,
            authority=authority,
            observations=tuple(observations),
            allowed_actions=tuple(ReplicaAction(action) for action in allowed_actions),
            prior_proposals=tuple(prior_proposals),
            deadline_ms=deadline_ms,
            idempotency_key="",
            request_digest="",
        )
        digest = canonical_digest(request.digest_payload())
        completed = replace(request, idempotency_key=digest, request_digest=digest)
        return cls.from_dict(completed.to_dict())

    def digest_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("idempotency_key")
        payload.pop("request_digest")
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "run_ref": self.run_ref.to_dict(),
            "agent": self.agent.to_dict(),
            "authority": self.authority.to_dict(),
            "observations": [observation.to_dict() for observation in self.observations],
            "allowed_actions": [action.value for action in self.allowed_actions],
            "prior_proposals": [proposal.to_dict() for proposal in self.prior_proposals],
            "deadline_ms": self.deadline_ms,
            "idempotency_key": self.idempotency_key,
            "request_digest": self.request_digest,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AgentTurnRequest":
        try:
            return _parse_request(payload)
        except ProposalValidationError as error:
            if error.reason_code == "request_invalid":
                raise
            raise ProposalValidationError("request_invalid", f"request validation failed: {error}") from error


def _parse_request(payload: Mapping[str, Any]) -> AgentTurnRequest:
    if not isinstance(payload, Mapping):
        raise ProposalValidationError("request_invalid", "request must be an object")
    _strict_keys(payload, frozenset(AgentTurnRequest.__dataclass_fields__), "request")
    if payload["schema_version"] != PROTOCOL_VERSION or payload["kind"] != "agent_turn_request":
        raise ProposalValidationError("request_invalid", "request protocol marker is invalid")
    run_ref = _parse_run_ref(payload["run_ref"], request=True)

    agent_payload = payload["agent"]
    if not isinstance(agent_payload, Mapping):
        raise ProposalValidationError("request_invalid", "agent must be an object")
    _strict_keys(agent_payload, frozenset(AgentDescriptor.__dataclass_fields__), "request")
    try:
        agent_id = AgentId(agent_payload["agent_id"])
    except (TypeError, ValueError) as error:
        raise ProposalValidationError("request_invalid", "agent_id is not allowed") from error
    role = _nonempty_string(agent_payload["role"], "agent.role", max_length=128)
    mandate = _nonempty_string(agent_payload["public_mandate"], "agent.public_mandate")
    if not _is_sha256(agent_payload["private_goal_digest"]):
        raise ProposalValidationError("request_invalid", "private_goal_digest must be sha256")
    scope = _string_tuple(agent_payload["observation_scope"], "agent.observation_scope")
    agent = AgentDescriptor(agent_id, role, mandate, agent_payload["private_goal_digest"], scope)

    authority_payload = payload["authority"]
    if not isinstance(authority_payload, Mapping):
        raise ProposalValidationError("request_invalid", "authority must be an object")
    _strict_keys(authority_payload, frozenset(Authority.__dataclass_fields__), "request")
    try:
        authority = Authority(
            _nonempty_string(authority_payload["version"], "authority.version", max_length=128),
            AuthorityStatus(authority_payload["status"]),
        )
    except (TypeError, ValueError) as error:
        raise ProposalValidationError("request_invalid", "authority is invalid") from error

    observations_payload = payload["observations"]
    if not isinstance(observations_payload, list) or not observations_payload:
        raise ProposalValidationError("request_invalid", "observations must be a non-empty list")
    observations: list[Observation] = []
    for item in observations_payload:
        if not isinstance(item, Mapping):
            raise ProposalValidationError("request_invalid", "observation must be an object")
        _strict_keys(item, frozenset({"id", "summary", "evidence_refs"}), "request")
        observation = Observation(
            _nonempty_string(item["id"], "observation.id", max_length=256),
            _nonempty_string(item["summary"], "observation.summary"),
            _string_tuple(item["evidence_refs"], "observation.evidence_refs"),
        )
        if observation.observation_id not in scope or not set(observation.evidence_refs) <= set(scope):
            raise ProposalValidationError("request_invalid", "observation exceeds agent scope")
        observations.append(observation)
    if len({item.observation_id for item in observations}) != len(observations):
        raise ProposalValidationError("request_invalid", "observation ids must be unique")

    try:
        allowed_actions = tuple(ReplicaAction(action) for action in payload["allowed_actions"])
    except (TypeError, ValueError) as error:
        raise ProposalValidationError("request_invalid", "allowed_actions contains an invalid action") from error
    if (
        not isinstance(payload["allowed_actions"], list)
        or not allowed_actions
        or len(set(allowed_actions)) != len(allowed_actions)
        or any(action.value not in ACTION_DELTA_PARAMETERS for action in allowed_actions)
    ):
        raise ProposalValidationError("request_invalid", "allowed_actions is invalid")
    if not isinstance(payload["prior_proposals"], list):
        raise ProposalValidationError("request_invalid", "prior_proposals must be a list")
    if run_ref.round == 1 and payload["prior_proposals"]:
        raise ProposalValidationError("request_invalid", "round 1 cannot contain prior proposals")

    deadline = payload["deadline_ms"]
    if isinstance(deadline, bool) or not isinstance(deadline, int) or not 1 <= deadline <= MAX_DEADLINE_MS:
        raise ProposalValidationError("request_invalid", "deadline_ms is outside the bounded range")
    request = AgentTurnRequest(
        schema_version=payload["schema_version"],
        kind=payload["kind"],
        run_ref=run_ref,
        agent=agent,
        authority=authority,
        observations=tuple(observations),
        allowed_actions=allowed_actions,
        prior_proposals=(),
        deadline_ms=deadline,
        idempotency_key=payload["idempotency_key"],
        request_digest=payload["request_digest"],
    )
    expected = canonical_digest(request.digest_payload())
    if request.request_digest != expected or request.idempotency_key != expected:
        raise ProposalValidationError("request_invalid", "request digest or idempotency key mismatch")
    return request


@dataclass(frozen=True)
class AgentProposal:
    schema_version: str
    kind: str
    request_digest: str
    run_ref: RunRef
    agent_id: AgentId
    action: ReplicaAction
    evidence_refs: tuple[str, ...]
    confidence: float
    reservation: str
    dissent: Dissent
    cooperation_target: AgentId | None
    expected_consequence: ExpectedConsequence
    provenance: ProposalProvenance
    proposal_digest: str

    @classmethod
    def create(
        cls,
        *,
        request: AgentTurnRequest,
        action: ReplicaAction | str,
        evidence_refs: Sequence[str],
        confidence: float,
        reservation: str,
        dissent: Dissent,
        cooperation_target: AgentId | str | None,
        expected_consequence: str,
        provenance: ProposalProvenance,
    ) -> "AgentProposal":
        proposal = cls(
            schema_version=PROTOCOL_VERSION,
            kind="agent_proposal",
            request_digest=request.request_digest,
            run_ref=request.run_ref,
            agent_id=request.agent.agent_id,
            action=ReplicaAction(action),
            evidence_refs=tuple(evidence_refs),
            confidence=confidence,
            reservation=reservation,
            dissent=dissent,
            cooperation_target=AgentId(cooperation_target) if cooperation_target else None,
            expected_consequence=ExpectedConsequence(expected_consequence, True),
            provenance=provenance,
            proposal_digest="",
        )
        digest = canonical_digest(proposal.digest_payload())
        completed = replace(proposal, proposal_digest=digest)
        return cls.from_dict(completed.to_dict(), request=request)

    def digest_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("proposal_digest")
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "request_digest": self.request_digest,
            "run_ref": self.run_ref.to_dict(),
            "agent_id": self.agent_id.value,
            "action": self.action.value,
            "evidence_refs": list(self.evidence_refs),
            "confidence": self.confidence,
            "reservation": self.reservation,
            "dissent": self.dissent.to_dict(),
            "cooperation_target": self.cooperation_target.value if self.cooperation_target else None,
            "expected_consequence": self.expected_consequence.to_dict(),
            "provenance": self.provenance.to_dict(),
            "proposal_digest": self.proposal_digest,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], *, request: AgentTurnRequest
    ) -> "AgentProposal":
        return _parse_proposal(payload, request=request)


def _parse_proposal(payload: Mapping[str, Any], *, request: AgentTurnRequest) -> AgentProposal:
    if request.authority.status is not AuthorityStatus.ACTIVE:
        raise ProposalValidationError("authority_revoked", "request authority is not active")
    if not isinstance(payload, Mapping):
        raise ProposalValidationError("proposal_invalid", "proposal must be an object")
    _strict_keys(payload, frozenset(AgentProposal.__dataclass_fields__), "proposal")
    if payload["schema_version"] != PROTOCOL_VERSION or payload["kind"] != "agent_proposal":
        raise ProposalValidationError("proposal_invalid", "proposal protocol marker is invalid")
    run_ref = _parse_run_ref(payload["run_ref"])
    if (
        payload["request_digest"] != request.request_digest
        or run_ref != request.run_ref
        or payload["agent_id"] != request.agent.agent_id.value
    ):
        raise ProposalValidationError("proposal_stale", "proposal is not bound to this request")
    try:
        agent_id = AgentId(payload["agent_id"])
        action = ReplicaAction(payload["action"])
    except (TypeError, ValueError) as error:
        raise ProposalValidationError("proposal_invalid", "agent or action is not allowed") from error
    if action not in request.allowed_actions or action.value not in ACTION_DELTA_PARAMETERS:
        raise ProposalValidationError("proposal_invalid", "action is outside the request allowlist")
    evidence_refs = _string_tuple(payload["evidence_refs"], "evidence_refs")
    if not set(evidence_refs) <= set(request.agent.observation_scope):
        raise ProposalValidationError("proposal_invalid", "evidence_refs exceed observation scope")
    confidence = payload["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not isfinite(confidence)
        or not 0.0 <= confidence <= 1.0
    ):
        raise ProposalValidationError("proposal_invalid", "confidence must be finite and between zero and one")
    reservation = _nonempty_string(payload["reservation"], "reservation")

    dissent_payload = payload["dissent"]
    if not isinstance(dissent_payload, Mapping):
        raise ProposalValidationError("proposal_invalid", "dissent must be an object")
    _strict_keys(dissent_payload, frozenset(Dissent.__dataclass_fields__), "proposal")
    if not isinstance(dissent_payload["raised"], bool):
        raise ProposalValidationError("proposal_invalid", "dissent.raised must be boolean")
    target_agent = None
    if dissent_payload["target_agent_id"] is not None:
        try:
            target_agent = AgentId(dissent_payload["target_agent_id"])
        except (TypeError, ValueError) as error:
            raise ProposalValidationError("proposal_invalid", "dissent target agent is invalid") from error
    target_digest = dissent_payload["target_proposal_digest"]
    if dissent_payload["raised"]:
        if target_agent is None or not _is_sha256(target_digest):
            raise ProposalValidationError("proposal_invalid", "raised dissent requires a typed target")
    elif target_agent is not None or target_digest is not None:
        raise ProposalValidationError("proposal_invalid", "non-raised dissent cannot have a target")
    dissent = Dissent(dissent_payload["raised"], target_agent, target_digest)

    cooperation_target = None
    if payload["cooperation_target"] is not None:
        try:
            cooperation_target = AgentId(payload["cooperation_target"])
        except (TypeError, ValueError) as error:
            raise ProposalValidationError("proposal_invalid", "cooperation_target is invalid") from error
        if cooperation_target is agent_id:
            raise ProposalValidationError("proposal_invalid", "agent cannot cooperate with itself")

    consequence_payload = payload["expected_consequence"]
    if not isinstance(consequence_payload, Mapping):
        raise ProposalValidationError("proposal_invalid", "expected_consequence must be an object")
    _strict_keys(consequence_payload, frozenset(ExpectedConsequence.__dataclass_fields__), "proposal")
    if consequence_payload["is_projection"] is not True:
        raise ProposalValidationError("proposal_invalid", "expected_consequence must be marked as projection")
    consequence = ExpectedConsequence(
        _nonempty_string(consequence_payload["text"], "expected_consequence.text"), True
    )

    provenance_payload = payload["provenance"]
    if not isinstance(provenance_payload, Mapping):
        raise ProposalValidationError("proposal_invalid", "provenance must be an object")
    _strict_keys(provenance_payload, frozenset(ProposalProvenance.__dataclass_fields__), "proposal")
    try:
        provenance = ProposalProvenance(
            provider_class=ProviderClass(provenance_payload["provider_class"]),
            model_id=_nonempty_string(provenance_payload["model_id"], "provenance.model_id", max_length=256),
            temperature=_nonempty_string(provenance_payload["temperature"], "provenance.temperature", max_length=64),
            prompt_sha256=provenance_payload["prompt_sha256"],
            response_sha256=provenance_payload["response_sha256"],
            external_model_api_called=provenance_payload["external_model_api_called"],
            recorded_at=_nonempty_string(provenance_payload["recorded_at"], "provenance.recorded_at", max_length=64),
        )
    except (TypeError, ValueError) as error:
        raise ProposalValidationError("proposal_invalid", "provenance is invalid") from error
    if not _is_sha256(provenance.prompt_sha256) or not _is_sha256(provenance.response_sha256):
        raise ProposalValidationError("proposal_invalid", "provenance digests must be sha256")
    if not isinstance(provenance.external_model_api_called, bool):
        raise ProposalValidationError("proposal_invalid", "external_model_api_called must be boolean")
    if (
        provenance.provider_class is ProviderClass.EXTERNAL_RECORDED
        and not provenance.external_model_api_called
    ):
        raise ProposalValidationError("proposal_invalid", "external_recorded must disclose API participation")
    if (
        provenance.provider_class is not ProviderClass.EXTERNAL_RECORDED
        and provenance.external_model_api_called
    ):
        raise ProposalValidationError("proposal_invalid", "offline provider cannot claim an external API call")

    proposal = AgentProposal(
        schema_version=payload["schema_version"],
        kind=payload["kind"],
        request_digest=payload["request_digest"],
        run_ref=run_ref,
        agent_id=agent_id,
        action=action,
        evidence_refs=evidence_refs,
        confidence=float(confidence),
        reservation=reservation,
        dissent=dissent,
        cooperation_target=cooperation_target,
        expected_consequence=consequence,
        provenance=provenance,
        proposal_digest=payload["proposal_digest"],
    )
    if not _is_sha256(proposal.proposal_digest) or proposal.proposal_digest != canonical_digest(
        proposal.digest_payload()
    ):
        raise ProposalValidationError("proposal_invalid", "proposal digest mismatch")
    return proposal
