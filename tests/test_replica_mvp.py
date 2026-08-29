from __future__ import annotations

from pathlib import Path

import pytest

from ghost_in_the_sim.decision import (
    DecisionContext,
    DecisionStatus,
    RecordedDecisionEngine,
    ReplicaAction,
    ReplicaMode,
    RuleDecisionEngine,
)
from ghost_in_the_sim.actual_trace import load_actual_ai_trace
from ghost_in_the_sim.replica import DEFAULT_SEEDS, run_replica_batch, run_replica_scenario


def test_rule_engine_is_deterministic_and_maps_all_modes() -> None:
    engine = RuleDecisionEngine()
    decisions = []
    for mode in ReplicaMode:
        context = DecisionContext.for_run(mode=mode, seed=42, turn=1)
        first = engine.decide(context)
        second = engine.decide(context)
        assert first == second
        assert first.action is {
            ReplicaMode.CENTRALIZED: ReplicaAction.PROTECT_CONTINUITY,
            ReplicaMode.PLURAL: ReplicaAction.REQUEST_VERIFICATION,
            ReplicaMode.AUTONOMOUS: ReplicaAction.REQUEST_COOPERATION,
        }[mode]
        decisions.append(first.decision_id)
    assert len(set(decisions)) == 3


def test_recorded_engine_replays_valid_ai_fixture_with_provenance() -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=17, turn=1)
    fixture = RuleDecisionEngine(model="fixture-ai-v1", prompt_hash="sha256:prompt-v1").decide(context).with_updates(
        decision_source="llm_generated_in_codex_session",
        model_id="unavailable_to_agent",
        temperature="unavailable_to_agent",
    )
    replay = RecordedDecisionEngine([fixture.to_dict()]).decide(context)

    assert replay == fixture
    assert replay.model_id == "unavailable_to_agent"
    assert replay.decision_source == "llm_generated_in_codex_session"
    assert replay.prompt_hash == "sha256:prompt-v1"
    assert replay.fixture_hash.startswith("sha256:")


@pytest.mark.parametrize("failure", ["invalid", "stale", "revoked", "unknown"])
def test_untrusted_decisions_fail_closed_with_audited_fallback(failure: str) -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=17, turn=1)
    valid = RuleDecisionEngine(model="fixture-ai-v1", prompt_hash="sha256:prompt-v1").decide(context)
    if failure == "invalid":
        payload = {**valid.to_dict(), "action": "execute_unbounded_command"}
    elif failure == "stale":
        payload = valid.with_updates(issued_at_turn=0).to_dict()
    elif failure == "revoked":
        payload = valid.with_updates(status=DecisionStatus.REVOKED).to_dict()
    else:
        payload = []

    outcome = run_replica_scenario(
        requested_mode=ReplicaMode.AUTONOMOUS,
        seed=17,
        turn_limit=2,
        decision_engine=RecordedDecisionEngine([payload] if isinstance(payload, dict) else payload),
    )

    assert outcome.decisions[0].action is ReplicaAction.ABSTAIN
    assert outcome.effective_mode is ReplicaMode.PLURAL
    assert outcome.audit.fallback_applied is True
    assert outcome.audit.reason_code == f"decision_{failure}"
    assert outcome.audit.requested_mode is ReplicaMode.AUTONOMOUS


def test_batch_runs_three_modes_across_fixed_seeds_and_replays() -> None:
    first = run_replica_batch(turn_limit=3)
    second = run_replica_batch(turn_limit=3)

    assert len(first.runs) == len(ReplicaMode) * len(DEFAULT_SEEDS) == 9
    assert first.to_dict() == second.to_dict()
    assert {(run.requested_mode, run.seed) for run in first.runs} == {
        (mode, seed) for mode in ReplicaMode for seed in DEFAULT_SEEDS
    }
    assert all(run.result.manifest()["scenario_id"] == "harbor-loop-replica-crisis-01" for run in first.runs)
    assert {run.result.condition_id for run in first.runs} == {"centralized", "plural", "autonomous"}
    assert all(decision.model_id and decision.prompt_hash for run in first.runs for decision in run.decisions)


def test_autonomous_is_a_first_class_condition_not_an_overconnected_alias() -> None:
    run = run_replica_scenario(requested_mode=ReplicaMode.AUTONOMOUS, seed=42, turn_limit=3)

    assert run.result.condition_id == "autonomous"
    assert [event.action_type for event in run.result.events] == [
        "coordinate_local_response",
        "coordinate_local_response",
        "request_peer_sync",
    ]
    assert "policy-autonomous" in run.result.manifest()["policy_reference_ids"]
    assert all(
        ref in run.result.manifest()["policy_reference_ids"] or ref.startswith("obs-")
        for event in run.result.events
        for ref in event.rationale_refs
    )


def test_actual_ai_trace_replays_nine_decisions_without_claiming_live_api() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "actual-ai-trace-seed42.json"
    records = load_actual_ai_trace(fixture)
    batch = run_replica_batch(
        seeds=(42,),
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in records),
    )

    assert len(records) == 9
    assert len(batch.runs) == 3
    assert all(not run.audit.fallback_applied for run in batch.runs)
    assert all(decision.actual_ai_participated for run in batch.runs for decision in run.decisions)
    assert all(not decision.external_model_api_called for run in batch.runs for decision in run.decisions)
    assert all(decision.model_id == "unavailable_to_agent" for run in batch.runs for decision in run.decisions)


def test_two_valid_action_traces_causally_change_events_and_metrics() -> None:
    contexts = [DecisionContext.for_run(mode=ReplicaMode.CENTRALIZED, seed=42, turn=turn) for turn in (1, 2, 3)]
    baseline_records = [RuleDecisionEngine().decide(context) for context in contexts]
    changed_records = [
        record.with_updates(action=ReplicaAction.ABSTAIN, confidence=0.9)
        if record.issued_at_turn == 2
        else record
        for record in baseline_records
    ]

    baseline = run_replica_scenario(
        requested_mode=ReplicaMode.CENTRALIZED,
        seed=42,
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in baseline_records),
    )
    changed = run_replica_scenario(
        requested_mode=ReplicaMode.CENTRALIZED,
        seed=42,
        turn_limit=3,
        decision_engine=RecordedDecisionEngine(record.to_dict() for record in changed_records),
    )

    assert not baseline.audit.fallback_applied and not changed.audit.fallback_applied
    assert baseline.result.run_id != changed.result.run_id
    assert [event.state_after for event in baseline.result.events] != [event.state_after for event in changed.result.events]
    assert baseline.result.metrics != changed.result.metrics


def test_recorded_engine_rejects_duplicate_decision_id_even_if_records_match() -> None:
    context = DecisionContext.for_run(mode=ReplicaMode.PLURAL, seed=42, turn=1)
    record = RuleDecisionEngine().decide(context).to_dict()
    engine = RecordedDecisionEngine([record, dict(record)])

    with pytest.raises(ValueError, match="exactly one"):
        engine.decide(context)


def test_duplicate_decision_id_causes_audited_fallback() -> None:
    records = [
        RuleDecisionEngine().decide(DecisionContext.for_run(mode=ReplicaMode.AUTONOMOUS, seed=42, turn=turn)).to_dict()
        for turn in (1, 2, 3)
    ]
    engine = RecordedDecisionEngine([records[0], records[0], *records[1:]])

    run = run_replica_scenario(
        requested_mode=ReplicaMode.AUTONOMOUS, seed=42, turn_limit=3, decision_engine=engine
    )

    assert run.audit.fallback_applied
    assert run.audit.reason_code == "decision_invalid"
    assert run.effective_mode is ReplicaMode.PLURAL
