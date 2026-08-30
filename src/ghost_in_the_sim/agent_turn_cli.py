"""外部runnerとagent turnを安全に交換する、networkなしのfile CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .agent_providers import RecordedProposalProvider
from .agent_turn import AgentId, AgentProposal, AgentTurnRequest, PROTOCOL_VERSION, canonical_digest
from .replica import (
    KAGAMISHIO,
    MIKAGE_DEFAULT_PLAN,
    ReplicaMode,
    _agent_requests_for_turn,
    run_ensemble_scenario,
)
from .run_bundle import build_verified_run_bundle


REQUEST_BUNDLE_KIND = "agent_turn_request_bundle"
PROPOSAL_BUNDLE_KIND = "agent_proposal_bundle"
RECORDED_FIXTURE_KIND = "recorded_agent_proposal_fixture"

_REQUEST_BUNDLE_KEYS = frozenset(
    {"protocol_version", "kind", "seed", "mode", "turn_limit", "requests", "bundle_digest"}
)
_PROPOSAL_BUNDLE_KEYS = frozenset(
    {"protocol_version", "kind", "request_bundle_digest", "proposals", "bundle_digest"}
)
_FIXTURE_KEYS = frozenset(
    {
        "protocol_version",
        "kind",
        "seed",
        "mode",
        "turn_limit",
        "request_bundle_digest",
        "proposals",
        "bundle_digest",
    }
)


def _without_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("bundle_digest", None)
    return result


def _require_exact_keys(payload: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ValueError(f"{label} schema keys do not match")
    return payload


def _validate_digest(payload: Mapping[str, Any], label: str) -> None:
    if payload["bundle_digest"] != canonical_digest(_without_digest(payload)):
        raise ValueError(f"{label} bundle digest mismatch")


def _parse_request_bundle(payload: Any) -> tuple[dict[str, Any], tuple[AgentTurnRequest, ...]]:
    source = _require_exact_keys(payload, _REQUEST_BUNDLE_KEYS, "request bundle")
    if source["protocol_version"] != PROTOCOL_VERSION or source["kind"] != REQUEST_BUNDLE_KIND:
        raise ValueError("request bundle protocol marker is invalid")
    seed, turn_limit = source["seed"], source["turn_limit"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("request bundle seed must be an integer")
    if isinstance(turn_limit, bool) or not isinstance(turn_limit, int) or not 1 <= turn_limit <= len(KAGAMISHIO.beats):
        raise ValueError("request bundle turn_limit is invalid")
    try:
        mode = ReplicaMode(source["mode"])
    except (TypeError, ValueError) as error:
        raise ValueError("request bundle mode is invalid") from error
    if not isinstance(source["requests"], list):
        raise ValueError("request bundle requests must be an array")
    _validate_digest(source, "request")
    try:
        requests = tuple(AgentTurnRequest.from_dict(item) for item in source["requests"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"request bundle contains an invalid request: {error}") from error
    expected_order = [
        (turn, agent_id)
        for turn in range(1, turn_limit + 1)
        for agent_id in AgentId
    ]
    observed_order = [(request.run_ref.turn, request.agent.agent_id) for request in requests]
    if observed_order != expected_order:
        raise ValueError("request bundle is missing, duplicate, or outside canonical order")
    if any(
        request.run_ref.environment_seed != seed
        or request.run_ref.condition_id != mode.value
        or request.run_ref.scenario_id != KAGAMISHIO.scenario_id
        for request in requests
    ):
        raise ValueError("request bundle contains a cross-run request")
    return dict(source), requests


def build_request_bundle(*, seed: int, mode: ReplicaMode | str, turn_limit: int) -> dict[str, Any]:
    """4主体 x turnのrequestを既存runtimeからcanonical順にexportする。"""

    chosen_mode = ReplicaMode(mode)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(turn_limit, bool) or not isinstance(turn_limit, int) or not 1 <= turn_limit <= len(KAGAMISHIO.beats):
        raise ValueError("turn_limit must fit within the canonical scenario")
    if turn_limit != 1:
        raise ValueError(
            "request export is stateful and must run one turn at a time; multi-turn export requires an interleaved session"
        )
    requests = [
        request.to_dict()
        for turn in range(1, turn_limit + 1)
        for request in _agent_requests_for_turn(
            mode=chosen_mode,
            seed=seed,
            turn=turn,
            scenario=KAGAMISHIO,
            operative_plan=MIKAGE_DEFAULT_PLAN,
        )
    ]
    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "kind": REQUEST_BUNDLE_KIND,
        "seed": seed,
        "mode": chosen_mode.value,
        "turn_limit": turn_limit,
        "requests": requests,
    }
    payload["bundle_digest"] = canonical_digest(payload)
    return payload


def _parse_proposal_bundle(
    payload: Any, *, request_bundle: Mapping[str, Any], requests: Sequence[AgentTurnRequest]
) -> tuple[AgentProposal, ...]:
    source = _require_exact_keys(payload, _PROPOSAL_BUNDLE_KEYS, "proposal bundle")
    if source["protocol_version"] != PROTOCOL_VERSION or source["kind"] != PROPOSAL_BUNDLE_KIND:
        raise ValueError("proposal bundle protocol marker is invalid")
    if source["request_bundle_digest"] != request_bundle["bundle_digest"]:
        raise ValueError("proposal request bundle digest mismatch")
    if not isinstance(source["proposals"], list):
        raise ValueError("proposal bundle proposals must be an array")
    _validate_digest(source, "proposal")
    request_by_digest = {request.request_digest: request for request in requests}
    if len(request_by_digest) != len(requests):
        raise ValueError("request bundle contains duplicate request digests")
    parsed: list[AgentProposal] = []
    seen: set[str] = set()
    for proposal_payload in source["proposals"]:
        if not isinstance(proposal_payload, Mapping):
            raise ValueError("proposal bundle contains a non-object proposal")
        request_digest = proposal_payload.get("request_digest")
        request = request_by_digest.get(request_digest)
        if request is None:
            raise ValueError("proposal contains an unknown or cross-run request digest")
        if request_digest in seen:
            raise ValueError("proposal bundle contains a duplicate proposal")
        try:
            parsed.append(AgentProposal.from_dict(proposal_payload, request=request))
        except (TypeError, ValueError) as error:
            raise ValueError(f"proposal bundle contains an invalid proposal: {error}") from error
        seen.add(request_digest)
    missing = set(request_by_digest) - seen
    if missing:
        raise ValueError("proposal bundle is missing a proposal")
    return tuple(parsed)


def build_recorded_fixture(request_bundle: Any, proposal_bundle: Any) -> dict[str, Any]:
    """外部応答をstrict検証し、recorded replay用fixtureへ固定する。"""

    requests_payload, requests = _parse_request_bundle(request_bundle)
    proposals = _parse_proposal_bundle(
        proposal_bundle, request_bundle=requests_payload, requests=requests
    )
    fixture: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "kind": RECORDED_FIXTURE_KIND,
        "seed": requests_payload["seed"],
        "mode": requests_payload["mode"],
        "turn_limit": requests_payload["turn_limit"],
        "request_bundle_digest": requests_payload["bundle_digest"],
        "proposals": [proposal.to_dict() for proposal in proposals],
    }
    fixture["bundle_digest"] = canonical_digest(fixture)
    return fixture


def _parse_fixture(payload: Any) -> dict[str, Any]:
    source = _require_exact_keys(payload, _FIXTURE_KEYS, "recorded fixture")
    if source["protocol_version"] != PROTOCOL_VERSION or source["kind"] != RECORDED_FIXTURE_KIND:
        raise ValueError("recorded fixture protocol marker is invalid")
    _validate_digest(source, "recorded fixture")
    if not isinstance(source["proposals"], list):
        raise ValueError("recorded fixture proposals must be an array")
    return dict(source)


def verify_recorded_fixture(fixture: Any) -> dict[str, Any]:
    """recorded proposalだけでruntimeを再実行し、replay-match bundleを返す。"""

    parsed = _parse_fixture(fixture)
    canonical_requests = build_request_bundle(
        seed=parsed["seed"], mode=parsed["mode"], turn_limit=parsed["turn_limit"]
    )
    if parsed["request_bundle_digest"] != canonical_requests["bundle_digest"]:
        raise ValueError("recorded fixture request bundle digest mismatch")
    _, requests = _parse_request_bundle(canonical_requests)
    proposal_bundle: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "kind": PROPOSAL_BUNDLE_KIND,
        "request_bundle_digest": canonical_requests["bundle_digest"],
        "proposals": parsed["proposals"],
    }
    proposal_bundle["bundle_digest"] = canonical_digest(proposal_bundle)
    proposals = _parse_proposal_bundle(
        proposal_bundle, request_bundle=canonical_requests, requests=requests
    )
    provider = RecordedProposalProvider([proposal.to_dict() for proposal in proposals])
    run = run_ensemble_scenario(
        requested_mode=parsed["mode"],
        seed=parsed["seed"],
        turn_limit=parsed["turn_limit"],
        proposal_provider=provider,
    )
    if any(
        outcome.reason_code == "proposal_missing"
        for round_result in run.agent_rounds
        for outcome in round_result.outcomes
    ):
        raise ValueError("recorded fixture did not apply every validated proposal")
    return build_verified_run_bundle(run)


def write_canonical_json(path: Path | None, payload: Any) -> str:
    # digest用のtagged-number projectionはwire formatではない。交換JSONは
    # strict parserがそのまま再読込できる、key順固定の通常JSONとして書く。
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return text


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_object)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ghost agent turn file exchange")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="agent request束を出力")
    export.add_argument("--seed", type=int, required=True)
    export.add_argument("--mode", choices=[mode.value for mode in ReplicaMode], required=True)
    export.add_argument("--turn-limit", type=int, required=True)
    export.add_argument("--output", type=Path, required=True)
    ingest = commands.add_parser("ingest", help="外部proposal束を検証してfixture化")
    ingest.add_argument("--requests", type=Path, required=True)
    ingest.add_argument("--proposals", type=Path, required=True)
    ingest.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="recorded fixtureをexact replay")
    verify.add_argument("--fixture", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "export":
        result = build_request_bundle(seed=args.seed, mode=args.mode, turn_limit=args.turn_limit)
    elif args.command == "ingest":
        result = build_recorded_fixture(_read_json(args.requests), _read_json(args.proposals))
    else:
        result = verify_recorded_fixture(_read_json(args.fixture))
    write_canonical_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
