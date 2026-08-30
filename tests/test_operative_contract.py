from dataclasses import replace

import pytest

from ghost_in_the_sim.operative import (
    AttentionAllocation, MIKAGE_DEFAULT_PLAN, OperationalFocus, PartnerAction, PauseResponse,
    RevocationTarget, build_gameplay_plan, evaluate_operative,
)
from ghost_in_the_sim.scenario import KAGAMISHIO


def test_mikage_is_high_performance_but_attention_is_finite() -> None:
    plan = MIKAGE_DEFAULT_PLAN
    assert plan.scenario_id == KAGAMISHIO.scenario_id
    assert plan.base_capability == pytest.approx(0.96)
    assert sum(plan.attention.to_dict().values()) == 100
    state = evaluate_operative(plan, completed_turns=12)
    assert state.body_integrity >= 0.8
    assert state.cognitive_integrity >= 0.8
    assert state.option_preservation < 1.0
    assert state.replica_divergence > 0.0


def test_makabe_pause_is_typed_and_preserved() -> None:
    assert MIKAGE_DEFAULT_PLAN.partner_actions == (PartnerAction(turn=8, action="request_pause", reason="irreversible_authority_revocation"),)


def test_attention_budget_fails_closed() -> None:
    with pytest.raises(ValueError, match="sum to 100"):
        AttentionAllocation(20, 20, 20, 20, 20, 20)


def test_attention_allocation_changes_operative_state_without_weakening_base_capability() -> None:
    verification_focused = replace(
        MIKAGE_DEFAULT_PLAN,
        attention=AttentionAllocation(14, 28, 14, 18, 10, 16),
    )
    baseline = evaluate_operative(MIKAGE_DEFAULT_PLAN, completed_turns=12)
    changed = evaluate_operative(verification_focused, completed_turns=12)
    assert verification_focused.base_capability == MIKAGE_DEFAULT_PLAN.base_capability == pytest.approx(0.96)
    assert changed != baseline
    assert changed.replica_divergence != baseline.replica_divergence


def test_gameplay_focus_maps_to_finite_attention_and_revocation_target() -> None:
    hospital = build_gameplay_plan(focus=OperationalFocus.HOSPITAL, pause_response=PauseResponse.HOLD)
    port = build_gameplay_plan(focus=OperationalFocus.PORT, pause_response=PauseResponse.HOLD)
    assert sum(hospital.attention.to_dict().values()) == sum(port.attention.to_dict().values()) == 100
    assert hospital.attention.civilian_impact > port.attention.civilian_impact
    assert port.attention.replica_sync > hospital.attention.replica_sync
    assert hospital.revocation_target is RevocationTarget.PORT
    assert port.revocation_target is RevocationTarget.HOSPITAL


def test_pause_response_changes_option_preservation_deterministically() -> None:
    hold = build_gameplay_plan(focus=OperationalFocus.HOSPITAL, pause_response=PauseResponse.HOLD)
    proceed = build_gameplay_plan(focus=OperationalFocus.HOSPITAL, pause_response=PauseResponse.PROCEED)
    assert evaluate_operative(hold, completed_turns=8).option_preservation > evaluate_operative(proceed, completed_turns=8).option_preservation


def test_gameplay_plan_decode_fails_closed_for_unknown_choices() -> None:
    payload = MIKAGE_DEFAULT_PLAN.to_dict()
    payload["focus"] = "moon"
    with pytest.raises(ValueError):
        type(MIKAGE_DEFAULT_PLAN).from_dict(payload)
