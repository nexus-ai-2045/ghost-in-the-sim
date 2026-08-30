from dataclasses import replace

import pytest

from ghost_in_the_sim.operative import AttentionAllocation, MIKAGE_DEFAULT_PLAN, PartnerAction, evaluate_operative
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
