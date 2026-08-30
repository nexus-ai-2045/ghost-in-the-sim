"""既存runtimeの1 runをportableな証拠bundleへ投影する。"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
import math
from typing import Any, Mapping

from .decision import DecisionContext, DecisionRecord, DecisionValidationError, RecordedDecisionEngine, safe_fallback
from .replica import ReplicaRun, classify_run_failure, run_replica_batch
from .operative import OperativePlan, evaluate_operative
from .scenario import ScenarioManifest


SCHEMA_VERSION = "meta-security-run-bundle/v1"
CANONICALIZATION_VERSION = "meta-security-json-c14n/v1"
_TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "run_id", "run_request", "event_stream", "replay", "evidence"}
)


def _normalized_number(value: float) -> str:
    """Python/JavaScriptの表記差を排した、限定decimal契約。"""

    if not math.isfinite(value):
        raise ValueError("canonical JSON does not allow non-finite numbers")
    magnitude = abs(value)
    if value.is_integer() and magnitude > 9_007_199_254_740_991:
        raise ValueError("canonical JSON integer exceeds the JavaScript safe range")
    if magnitude and (magnitude < 1e-6 or magnitude >= 1e21):
        raise ValueError("canonical JSON number is outside the portable decimal range")
    decimal = Decimal(str(value))
    if decimal == 0:
        return "0"
    text = format(decimal, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _canonical_projection(payload: Any) -> Any:
    """数値をtagged decimalへ投影し、言語固有のfloat表記をhash境界から除く。"""

    if payload is None or isinstance(payload, (bool, str)):
        return payload
    if isinstance(payload, int):
        if abs(payload) > 9_007_199_254_740_991:
            raise ValueError("canonical JSON integer exceeds the JavaScript safe range")
        return {"$number": str(payload)}
    if isinstance(payload, float):
        return {"$number": _normalized_number(payload)}
    if isinstance(payload, Mapping):
        return {str(key): _canonical_projection(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_canonical_projection(value) for value in payload]
    raise ValueError(f"unsupported canonical JSON value: {type(payload).__name__}")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        _canonical_projection(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(payload: Any) -> str:
    return f"sha256:{sha256(_canonical_bytes(payload)).hexdigest()}"


class _BundleReplayEngine:
    """通常decisionと監査fallbackを元のruntime経路へ戻す。"""

    def __init__(self, decisions: list[Mapping[str, Any]], *, fallback_reasons: Mapping[str, str]) -> None:
        self._recorded = RecordedDecisionEngine(decisions)
        self._fallback_reasons = fallback_reasons

    def decide(self, context: DecisionContext):
        record = self._recorded.decide(context)
        if record.decision_source == "audited_fallback":
            reason_code = self._fallback_reasons.get(record.decision_id)
            if not reason_code:
                raise DecisionValidationError("bundle_invalid", "fallback reason is missing from replay contract")
            raise DecisionValidationError(reason_code, "replay recorded audited fallback")
        return record


def _fallback_reason_code(record: DecisionRecord) -> str | None:
    if record.decision_source != "audited_fallback":
        return None
    prefix = "sha256:"
    if record.model_id != "audited-fallback-v1" or not record.prompt_hash.startswith(prefix):
        raise ValueError("audited fallback record does not preserve its reason code")
    reason_code = record.prompt_hash[len(prefix) :]
    if not reason_code:
        raise ValueError("audited fallback reason code is empty")
    context = DecisionContext.for_run(mode=record.requested_mode, seed=record.seed, turn=record.issued_at_turn)
    if safe_fallback(context, reason_code=reason_code) != record:
        raise ValueError("audited fallback record does not match the canonical fallback projection")
    return reason_code


def _operative_event_projection(
    *, scenario: ScenarioManifest, plan: OperativePlan, event: Mapping[str, Any]
) -> dict[str, Any]:
    """事件beatと有限注意を、rendererが再計算しない型付きeventへ投影する。"""

    turn = event.get("turn")
    if isinstance(turn, bool) or not isinstance(turn, int) or not 1 <= turn <= len(scenario.beats):
        raise ValueError("operative event turn does not match the scenario")
    beat = scenario.beats[turn - 1]
    attention_by_event = {
        "replica_link_lost": ("replica_sync", "synchronize_replicas"),
        "authority_claim_received": ("route_verification", "verify_authority"),
        "service_conflict_detected": ("civilian_impact", "protect_continuity"),
        "evidence_lineage_split": ("self_audit", "audit_evidence"),
        "local_copy_diverged": ("replica_sync", "synchronize_replicas"),
        "continuity_risk_rises": ("civilian_impact", "protect_continuity"),
        "public_explanation_due": ("delegation", "coordinate_explanation"),
        "authority_revocation_proposed": ("route_verification", "verify_authority"),
        "partner_pause_requested": ("self_audit", "hold_for_partner_review"),
        "independent_evidence_arrives": ("route_verification", "integrate_independent_evidence"),
        "authority_convergence_due": ("delegation", "converge_authority"),
        "after_action_audit": ("self_audit", "self_audit"),
    }
    attention_field, operative_action = attention_by_event[beat.event_type]
    attention_value = getattr(plan.attention, attention_field)
    disturbance = event.get("exogenous_disturbance")
    if isinstance(disturbance, bool) or not isinstance(disturbance, (int, float)) or not math.isfinite(disturbance):
        raise ValueError("operative event disturbance must be finite")
    partner = next((item for item in plan.partner_actions if item.turn == turn), None)
    partner_action = partner.action if partner else "observe"
    confidence = round(min(1.0, max(0.0, plan.base_capability - float(disturbance) * 0.08 + attention_value / 1000)), 6)
    costs = [f"attention:{attention_field}"]
    if partner:
        costs.extend(("continuity_delay", "option_preservation"))
    elif beat.reversibility == "low":
        costs.append("irreversibility_exposure")
    return {
        "scenario_beat_id": beat.beat_id,
        "operative_action": operative_action,
        "partner_action": partner_action,
        "success_confidence": confidence,
        "cost_codes": costs,
        "operative_state_before": evaluate_operative(plan, completed_turns=turn - 1).to_dict(),
        "operative_state_after": evaluate_operative(plan, completed_turns=turn).to_dict(),
    }


def build_run_bundle(run: ReplicaRun) -> dict[str, Any]:
    """ReplicaRunを唯一の正本としてbundleを生成する。"""

    request_contract = {
        "scenario_id": run.result.scenario_id,
        "requested_mode": run.requested_mode.value,
        "seed": run.seed,
        "turn_limit": run.result.turn_limit,
        "model_config_hash": run.result.model_config_hash,
        "model_version": run.result.model_version,
        "code_version": run.result.code_version,
        "prompt_version_or_hash": run.result.prompt_version_or_hash,
        "source_revision": run.result.source_revision,
        "scenario": run.scenario.to_dict(),
        "operative_plan": run.operative_plan.to_dict(),
    }
    provenance = [decision.to_dict() for decision in run.decisions]
    run_id = f"run-{sha256(_canonical_bytes({'request': request_contract, 'decisions': provenance})).hexdigest()[:12]}"
    request = {"run_id": run_id, **request_contract}
    stream_events = []
    for event in run.result.events:
        event_payload = {**event.to_dict(), "run_id": run_id}
        event_payload.update(_operative_event_projection(scenario=run.scenario, plan=run.operative_plan, event=event_payload))
        stream_events.append(event_payload)
    stream = {
        "run_id": run_id,
        "ordering": "turn-ascending/v1",
        "event_count": len(run.result.events),
        "events": stream_events,
    }
    replay = {
        "run_id": run_id,
        "requested_mode": run.requested_mode.value,
        "effective_mode": run.effective_mode.value,
        "audit": {
            "fallback_applied": run.audit.fallback_applied,
            "reason_code": run.audit.reason_code,
        },
        "decisions": provenance,
        "fallback_reason_codes": {
            decision.decision_id: reason_code
            for decision in run.decisions
            if (reason_code := _fallback_reason_code(decision)) is not None
        },
        "manifest": {**run.result.manifest(), "run_id": run_id},
        "final_state": asdict(run.result.final_state),
        "metrics": dict(run.result.metrics),
        "operative_state": run.operative_state.to_dict(),
    }
    failed, failure_reasons = classify_run_failure(run.result)
    evidence = {
        "run_id": run_id,
        "digest_algorithm": "sha256",
        "canonicalization": CANONICALIZATION_VERSION,
        "run_request_sha256": _digest(request),
        "event_stream_sha256": _digest(stream),
        "replay_sha256": _digest(replay),
        "verification": "unverified",
        "failed_run": failed,
        "failure_reasons": list(failure_reasons),
    }
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_request": request,
        "event_stream": stream,
        "replay": replay,
        "evidence": evidence,
    }
    validate_run_bundle(bundle)
    return bundle


def build_verified_run_bundle(run: ReplicaRun) -> dict[str, Any]:
    """replay成功と不可分なverified bundleを生成する。"""

    bundle = build_run_bundle(run)
    verify_run_bundle(bundle)
    bundle["evidence"]["verification"] = "replay-match"
    validate_run_bundle(bundle)
    return bundle


def validate_run_bundle(bundle: Mapping[str, Any]) -> None:
    """cross-run混入、順序drift、内容改ざんをfail-closedで拒否する。"""

    if set(bundle) != _TOP_LEVEL_KEYS or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("run bundle schema does not match meta-security-run-bundle/v1")
    run_id = bundle.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")
    sections = tuple(bundle.get(name) for name in ("run_request", "event_stream", "replay", "evidence"))
    if any(not isinstance(section, Mapping) or section.get("run_id") != run_id for section in sections):
        raise ValueError("every run bundle section must reference the same run_id")
    request, stream, replay, evidence = sections

    seed = request.get("seed")
    turn_limit = request.get("turn_limit")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("run request seed must be an integer")
    if isinstance(turn_limit, bool) or not isinstance(turn_limit, int) or turn_limit < 1:
        raise ValueError("run request turn_limit must be a positive integer")
    scenario = ScenarioManifest.from_dict(request.get("scenario", {}))
    operative_plan = OperativePlan.from_dict(request.get("operative_plan", {}))
    if scenario.scenario_id != operative_plan.scenario_id:
        raise ValueError("operative plan must reference the run scenario")

    events = stream.get("events")
    if not isinstance(events, list) or stream.get("ordering") != "turn-ascending/v1" or stream.get("event_count") != len(events):
        raise ValueError("event stream metadata does not match events")
    turns = [event.get("turn") for event in events if isinstance(event, Mapping)]
    if len(turns) != len(events) or turns != list(range(1, len(events) + 1)):
        raise ValueError("event stream must contain a reproducible contiguous turn order")
    if any(event.get("run_id") != run_id or event.get("seed") != seed for event in events):
        raise ValueError("event stream contains an event from another run")
    for event in events:
        expected_projection = _operative_event_projection(scenario=scenario, plan=operative_plan, event=event)
        if any(event.get(key) != value for key, value in expected_projection.items()):
            raise ValueError("event stream operative projection does not match scenario and plan")

    decisions = replay.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("replay decisions must be an array")
    decision_turns = [decision.get("issued_at_turn") for decision in decisions if isinstance(decision, Mapping)]
    if len(decision_turns) != len(decisions) or decision_turns != sorted(decision_turns):
        raise ValueError("replay decisions must retain deterministic turn order")
    if any(
        decision.get("seed") != seed
        or decision.get("scenario_id") != request.get("scenario_id")
        or decision.get("requested_mode") != request.get("requested_mode")
        for decision in decisions
    ):
        raise ValueError("replay decision does not match the run request")
    fallback_reasons = replay.get("fallback_reason_codes")
    if not isinstance(fallback_reasons, Mapping):
        raise ValueError("fallback reason codes must be an object")
    fallback_decisions = {
        decision["decision_id"]: decision
        for decision in decisions
        if decision.get("decision_source") == "audited_fallback"
    }
    if set(fallback_reasons) != set(fallback_decisions) or any(
        not isinstance(reason, str)
        or not reason
        or fallback_decisions[decision_id].get("prompt_hash") != f"sha256:{reason}"
        for decision_id, reason in fallback_reasons.items()
    ):
        raise ValueError("fallback reason codes do not match audited fallback decisions")
    manifest = replay.get("manifest")
    if not isinstance(manifest, Mapping) or manifest.get("run_id") != run_id:
        raise ValueError("replay manifest does not match run_id")
    if manifest.get("seed") != seed or manifest.get("turn_limit") != turn_limit or manifest.get("event_count") != len(events):
        raise ValueError("replay manifest does not match request or event stream")
    operative_state = replay.get("operative_state")
    if not isinstance(operative_state, Mapping) or set(operative_state) != {
        "body_integrity", "cognitive_integrity", "memory_coherence", "legal_authority",
        "organizational_trust", "public_trust", "replica_divergence", "option_preservation",
    }:
        raise ValueError("replay operative state does not match the typed contract")

    failure_reasons = []
    if manifest.get("termination_reason") != "turn_limit_reached":
        failure_reasons.append(f"termination:{manifest.get('termination_reason')}")
    if len(events) != turn_limit:
        failure_reasons.append(f"incomplete_turns:{len(events)}/{turn_limit}")

    verification = evidence.get("verification")
    if verification not in {"unverified", "replay-match"}:
        raise ValueError("bundle verification state is invalid")
    expected_evidence = {
        "run_id": run_id,
        "digest_algorithm": "sha256",
        "canonicalization": CANONICALIZATION_VERSION,
        "run_request_sha256": _digest(request),
        "event_stream_sha256": _digest(stream),
        "replay_sha256": _digest(replay),
        "verification": verification,
        "failed_run": bool(failure_reasons),
        "failure_reasons": failure_reasons,
    }
    if evidence != expected_evidence:
        raise ValueError("run bundle evidence digest does not match content")


def verify_run_bundle(bundle: Mapping[str, Any]) -> None:
    """既存runtimeで再実行し、hashだけでなくrun全体の一致を確認する。"""

    validate_run_bundle(bundle)
    request = bundle["run_request"]
    decisions = bundle["replay"]["decisions"]
    engine = (
        _BundleReplayEngine(decisions, fallback_reasons=bundle["replay"]["fallback_reason_codes"])
        if decisions
        else None
    )
    batch = run_replica_batch(
        seeds=(request["seed"],),
        turn_limit=request["turn_limit"],
        decision_engine=engine,
        scenario=ScenarioManifest.from_dict(request["scenario"]),
        operative_plan=OperativePlan.from_dict(request["operative_plan"]),
    )
    replayed = next(run for run in batch.runs if run.requested_mode.value == request["requested_mode"])
    candidate = build_run_bundle(replayed)
    expected = json.loads(json.dumps(bundle))
    expected["evidence"]["verification"] = "unverified"
    if candidate != expected:
        raise ValueError("run bundle does not match deterministic replay")
