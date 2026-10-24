"""provider非依存のagent-turn逐次session。ネットワークやcredentialは所有しない。"""

from __future__ import annotations

from typing import Any, Mapping

from .agent_providers import RecordedProposalProvider
from .agent_schedule import AgentRoundResult
from .agent_turn import AgentId, AgentTurnRequest, PROTOCOL_VERSION, canonical_digest
from .decision import ReplicaMode
from .engine import ActionInfluence, WorldState, run_experiment
from .replica import (
    KAGAMISHIO,
    MIKAGE_DEFAULT_PLAN,
    DecisionAudit,
    EnsembleRun,
    _CONDITION_BY_MODE,
    _agent_requests_for_turn,
    advance_ensemble_turn,
)
from .run_bundle import build_verified_run_bundle


SESSION_VERSION = "ghost-agent-session/v1"
SESSION_KIND = "agent_turn_session"
SESSION_REQUEST_KIND = "agent_session_request_bundle"
_SESSION_KEYS = frozenset(
    {
        "session_version",
        "kind",
        "seed",
        "mode",
        "turn_limit",
        "status",
        "next_turn",
        "rounds",
        "proposals",
        "current_request_bundle",
        "run_bundle",
        "bundle_digest",
    }
)
_REQUEST_KEYS = frozenset(
    {
        "protocol_version",
        "kind",
        "seed",
        "mode",
        "session_turn_limit",
        "current_turn",
        "requests",
        "bundle_digest",
    }
)


def _with_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["bundle_digest"] = canonical_digest(result)
    return result


def _without_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("bundle_digest", None)
    return result


def _request_bundle(
    *,
    seed: int,
    mode: ReplicaMode,
    turn_limit: int,
    turn: int,
    confirmed_state: WorldState | None = None,
) -> dict[str, Any]:
    requests = _agent_requests_for_turn(
        mode=mode,
        seed=seed,
        turn=turn,
        scenario=KAGAMISHIO,
        operative_plan=MIKAGE_DEFAULT_PLAN,
        confirmed_state=confirmed_state,
    )
    return _with_digest(
        {
            "protocol_version": PROTOCOL_VERSION,
            "kind": SESSION_REQUEST_KIND,
            "seed": seed,
            "mode": mode.value,
            "session_turn_limit": turn_limit,
            "current_turn": turn,
            "requests": [request.to_dict() for request in requests],
        }
    )


def _parse_session(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != _SESSION_KEYS:
        raise ValueError("session schema keys do not match")
    source = dict(payload)
    if source["session_version"] != SESSION_VERSION or source["kind"] != SESSION_KIND:
        raise ValueError("session protocol marker is invalid")
    if source["bundle_digest"] != canonical_digest(_without_digest(source)):
        raise ValueError("session bundle digest mismatch")
    if isinstance(source["seed"], bool) or not isinstance(source["seed"], int):
        raise ValueError("session seed must be an integer")
    try:
        ReplicaMode(source["mode"])
    except (TypeError, ValueError) as error:
        raise ValueError("session mode is invalid") from error
    if (
        isinstance(source["turn_limit"], bool)
        or not isinstance(source["turn_limit"], int)
        or not 1 <= source["turn_limit"] <= len(KAGAMISHIO.beats)
    ):
        raise ValueError("session turn_limit is invalid")
    if not isinstance(source["rounds"], list) or not isinstance(source["proposals"], list):
        raise ValueError("session history must be arrays")
    round_count = len(source["rounds"])
    if round_count > source["turn_limit"] or len(source["proposals"]) != round_count * len(AgentId):
        raise ValueError("session state is inconsistent")
    if source["status"] == "awaiting_proposals":
        if (
            round_count >= source["turn_limit"]
            or source["next_turn"] != round_count + 1
            or not isinstance(source["current_request_bundle"], Mapping)
            or source["run_bundle"] is not None
        ):
            raise ValueError("session state is inconsistent")
    elif source["status"] == "completed":
        if (
            round_count != source["turn_limit"]
            or source["next_turn"] is not None
            or source["current_request_bundle"] is not None
            or not isinstance(source["run_bundle"], Mapping)
        ):
            raise ValueError("session state is inconsistent")
    else:
        raise ValueError("session state is inconsistent")
    return source


def _parse_session_request(
    payload: Any, *, session: Mapping[str, Any]
) -> tuple[AgentTurnRequest, ...]:
    if not isinstance(payload, Mapping) or set(payload) != _REQUEST_KEYS:
        raise ValueError("session request bundle schema keys do not match")
    if payload["bundle_digest"] != canonical_digest(_without_digest(payload)):
        raise ValueError("session request bundle digest mismatch")
    turn = payload["current_turn"]
    if (
        payload["protocol_version"] != PROTOCOL_VERSION
        or payload["kind"] != SESSION_REQUEST_KIND
        or payload["seed"] != session["seed"]
        or payload["mode"] != session["mode"]
        or payload["session_turn_limit"] != session["turn_limit"]
        or turn != session["next_turn"]
    ):
        raise ValueError("session request bundle is cross-session or stale")
    if not isinstance(payload["requests"], list):
        raise ValueError("session request bundle requests must be an array")
    requests = tuple(AgentTurnRequest.from_dict(item) for item in payload["requests"])
    if [(request.run_ref.turn, request.agent.agent_id) for request in requests] != [
        (turn, agent_id) for agent_id in AgentId
    ]:
        raise ValueError("session request bundle is outside canonical order")
    return requests


def create_session(*, seed: int, mode: ReplicaMode | str, turn_limit: int) -> dict[str, Any]:
    chosen_mode = ReplicaMode(mode)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if (
        isinstance(turn_limit, bool)
        or not isinstance(turn_limit, int)
        or not 1 <= turn_limit <= len(KAGAMISHIO.beats)
    ):
        raise ValueError("turn_limit must fit within the canonical scenario")
    return _with_digest(
        {
            "session_version": SESSION_VERSION,
            "kind": SESSION_KIND,
            "seed": seed,
            "mode": chosen_mode.value,
            "turn_limit": turn_limit,
            "status": "awaiting_proposals",
            "next_turn": 1,
            "rounds": [],
            "proposals": [],
            "current_request_bundle": _request_bundle(
                seed=seed, mode=chosen_mode, turn_limit=turn_limit, turn=1
            ),
            "run_bundle": None,
        }
    )


def _replay_history(
    session: Mapping[str, Any],
) -> tuple[list[AgentRoundResult], tuple[ActionInfluence, ...], list[str]]:
    mode = ReplicaMode(session["mode"])
    rounds: list[AgentRoundResult] = []
    influences: tuple[ActionInfluence, ...] = ()
    fallback_reasons: list[str] = []
    proposals = session["proposals"]
    if len(proposals) != len(session["rounds"]) * len(AgentId):
        raise ValueError("session round history proposal count mismatch")
    provider = RecordedProposalProvider(proposals)
    for turn in range(1, len(session["rounds"]) + 1):
        round_result, influences, _state, reason = advance_ensemble_turn(
            requested_mode=mode,
            seed=session["seed"],
            turn=turn,
            proposal_provider=provider,
            prior_influences=influences,
        )
        if round_result.to_dict() != session["rounds"][turn - 1]:
            raise ValueError("session round history does not match canonical replay")
        rounds.append(round_result)
        if reason:
            fallback_reasons.append(reason)
    return rounds, influences, fallback_reasons


def advance_session(session_payload: Any, proposal_bundle: Any) -> dict[str, Any]:
    session = _parse_session(session_payload)
    if session["status"] != "awaiting_proposals" or session["next_turn"] is None:
        raise ValueError("session is already completed")
    rounds, influences, fallback_reasons = _replay_history(session)
    request_bundle = session["current_request_bundle"]
    confirmed_state = (
        None
        if not rounds
        else run_experiment(
            condition=_CONDITION_BY_MODE[ReplicaMode(session["mode"])],
            seed=session["seed"],
            turn_limit=len(rounds),
            action_influences=influences,
        ).final_state
    )
    expected_request_bundle = _request_bundle(
        seed=session["seed"],
        mode=ReplicaMode(session["mode"]),
        turn_limit=session["turn_limit"],
        turn=session["next_turn"],
        confirmed_state=confirmed_state,
    )
    if request_bundle != expected_request_bundle:
        raise ValueError("session request bundle does not match canonical replay")
    requests = _parse_session_request(request_bundle, session=session)

    # proposal parserはone-turn CLIと同じtrust boundaryを再利用する。
    from .agent_turn_cli import _parse_proposal_bundle

    proposals = _parse_proposal_bundle(
        proposal_bundle, request_bundle=request_bundle, requests=requests
    )
    provider = RecordedProposalProvider([proposal.to_dict() for proposal in proposals])
    turn = session["next_turn"]
    round_result, influences, confirmed_state, reason = advance_ensemble_turn(
        requested_mode=session["mode"],
        seed=session["seed"],
        turn=turn,
        proposal_provider=provider,
        prior_influences=influences,
    )
    rounds.append(round_result)
    if reason:
        fallback_reasons.append(reason)
    all_proposals = [*session["proposals"], *(proposal.to_dict() for proposal in proposals)]

    if turn < session["turn_limit"]:
        return _with_digest(
            {
                **_without_digest(session),
                "next_turn": turn + 1,
                "rounds": [item.to_dict() for item in rounds],
                "proposals": all_proposals,
                "current_request_bundle": _request_bundle(
                    seed=session["seed"],
                    mode=ReplicaMode(session["mode"]),
                    turn_limit=session["turn_limit"],
                    turn=turn + 1,
                    confirmed_state=confirmed_state,
                ),
            }
        )

    result = run_experiment(
        condition=_CONDITION_BY_MODE[ReplicaMode(session["mode"])],
        seed=session["seed"],
        turn_limit=session["turn_limit"],
        action_influences=influences,
    )
    reason_code = fallback_reasons[0] if fallback_reasons else "agent_turns_completed"
    run = EnsembleRun(
        requested_mode=ReplicaMode(session["mode"]),
        effective_mode=ReplicaMode(session["mode"]),
        seed=session["seed"],
        agent_rounds=tuple(rounds),
        applied_influences=influences,
        audit=DecisionAudit(
            ReplicaMode(session["mode"]),
            ReplicaMode(session["mode"]),
            bool(fallback_reasons),
            reason_code,
        ),
        result=result,
    )
    return _with_digest(
        {
            **_without_digest(session),
            "status": "completed",
            "next_turn": None,
            "rounds": [item.to_dict() for item in rounds],
            "proposals": all_proposals,
            "current_request_bundle": None,
            "run_bundle": build_verified_run_bundle(run),
        }
    )
