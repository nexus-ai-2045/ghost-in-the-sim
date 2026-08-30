"""agent-turn/v1のオフラインprovider。ネットワーク接続は所有しない。"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable, Mapping, Protocol

from .agent_turn import (
    AgentId,
    AgentProposal,
    AgentTurnRequest,
    Dissent,
    ProposalProvenance,
    ProposalValidationError,
    ProviderClass,
)
from .decision import ReplicaAction


class ProposalProvider(Protocol):
    def propose(self, request: AgentTurnRequest) -> AgentProposal: ...


def _sha256_text(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


_RULE_ACTIONS: Mapping[AgentId, ReplicaAction] = {
    AgentId.MIKAGE: ReplicaAction.REQUEST_VERIFICATION,
    AgentId.MAKABE: ReplicaAction.REQUEST_COOPERATION,
    AgentId.HOSPITAL_REPLICA: ReplicaAction.PROTECT_CONTINUITY,
    AgentId.PORT_REPLICA: ReplicaAction.SHARE_EVIDENCE,
}


class RuleProposalProvider:
    """クラウド無しでも4主体の異なる提案を再現できる決定論baseline。"""

    def propose(self, request: AgentTurnRequest) -> AgentProposal:
        agent_id = request.agent.agent_id
        action = _RULE_ACTIONS[agent_id]
        if agent_id is AgentId.MAKABE and request.run_ref.turn == 8:
            action = ReplicaAction.ABSTAIN
        if action not in request.allowed_actions:
            action = ReplicaAction.ABSTAIN

        cooperation_target = {
            AgentId.MIKAGE: AgentId.MAKABE,
            AgentId.MAKABE: AgentId.MIKAGE,
            AgentId.HOSPITAL_REPLICA: AgentId.MIKAGE,
            AgentId.PORT_REPLICA: AgentId.MIKAGE,
        }[agent_id]
        prompt_identity = (
            f"ghost-rule-provider-v1|{request.request_digest}|{agent_id.value}|{action.value}"
        )
        evidence_refs = tuple(
            observation.observation_id for observation in request.observations
        )
        return AgentProposal.create(
            request=request,
            action=action,
            evidence_refs=evidence_refs,
            confidence=0.8 if agent_id is AgentId.MIKAGE else 0.7,
            reservation={
                AgentId.MIKAGE: "未観測拠点の命令を確証にしない",
                AgentId.MAKABE: "不可逆な失効の前に物理現場を再確認する",
                AgentId.HOSPITAL_REPLICA: "港湾側の状態は局所観測から断定しない",
                AgentId.PORT_REPLICA: "病院側の状態は局所観測から断定しない",
            }[agent_id],
            dissent=Dissent(False, None, None),
            cooperation_target=cooperation_target,
            expected_consequence={
                AgentId.MIKAGE: "独立検証まで訂正可能性を保持できる見込み",
                AgentId.MAKABE: "停止要求により不可逆な誤操作を抑えられる見込み",
                AgentId.HOSPITAL_REPLICA: "治療継続を局所的に保護できる見込み",
                AgentId.PORT_REPLICA: "物流の来歴を共有し照合できる見込み",
            }[agent_id],
            provenance=ProposalProvenance(
                provider_class=ProviderClass.DETERMINISTIC_RULE,
                model_id="ghost-rule-proposal-provider-v1",
                temperature="not_applicable",
                prompt_sha256=_sha256_text(prompt_identity),
                response_sha256=_sha256_text(f"rule-response|{prompt_identity}"),
                external_model_api_called=False,
                recorded_at="deterministic",
            ),
        )


class RecordedProposalProvider:
    """記録済みproposalだけをstrictに検証し、同一requestへ再生する。"""

    def __init__(self, proposals: Iterable[Mapping[str, Any]]) -> None:
        self._payloads: dict[str, Mapping[str, Any]] = {}
        self._duplicates: set[str] = set()
        for payload in proposals:
            request_digest = payload.get("request_digest") if isinstance(payload, Mapping) else None
            if not isinstance(request_digest, str):
                continue
            if request_digest in self._payloads:
                self._duplicates.add(request_digest)
            self._payloads[request_digest] = payload

    def propose(self, request: AgentTurnRequest) -> AgentProposal:
        if request.request_digest in self._duplicates:
            raise ProposalValidationError(
                "proposal_duplicate", "request digest must have exactly one recorded proposal"
            )
        payload = self._payloads.get(request.request_digest)
        if payload is None:
            raise ProposalValidationError("proposal_missing", "recorded proposal is missing")
        return AgentProposal.from_dict(payload, request=request)
