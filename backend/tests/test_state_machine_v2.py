"""
Tests for PLANN v2 state machine extensions.

Covers:
  - New states: reserved_for_batch, queued_for_wise, wise_fund_pending, wise_fund_failed
  - Legacy alias (`reserved`) compatibility
  - Wallet balance invariants for new transitions
  - Failed rollback from any pipeline state
  - Reserve expiry rollback (reserved_for_batch → available)
"""

import pytest

from financial.state_machine import (
    TRANSITIONS,
    TERMINAL_STATES,
    StateMachine,
    InvalidTransitionError,
    canonical_state,
    get_wallet_updates,
)


# ---------------------------------------------------------------------------
# Transition table invariants
# ---------------------------------------------------------------------------

def test_new_states_are_registered():
    for s in ("reserved_for_batch", "queued_for_wise", "wise_fund_pending", "wise_fund_failed"):
        assert s in TRANSITIONS, f"Missing new state: {s}"


def test_legacy_reserved_still_present():
    assert "reserved" in TRANSITIONS  # backward compatibility


def test_canonical_state_alias():
    assert canonical_state("reserved") == "reserved_for_batch"
    assert canonical_state("reserved_for_batch") == "reserved_for_batch"
    assert canonical_state("paid_out") == "paid_out"


def test_paid_out_terminal():
    assert "paid_out" in TERMINAL_STATES


def test_available_can_go_to_new_pipeline():
    assert "reserved_for_batch" in TRANSITIONS["available"]
    assert "reserved" in TRANSITIONS["available"]  # legacy alias still accepted


def test_wise_fund_failed_can_retry_or_fail():
    assert TRANSITIONS["wise_fund_failed"] == {"queued_for_wise", "failed"}


# ---------------------------------------------------------------------------
# Wallet balance invariants
# ---------------------------------------------------------------------------

def test_available_to_reserved_for_batch_moves_balance():
    u = get_wallet_updates("available", "reserved_for_batch", 1000)
    assert u["available_balance_minor"] == -1000
    assert u["reserved_balance_minor"] == 1000


def test_intra_pipeline_no_balance_change():
    for old, new in (
        ("reserved_for_batch", "queued_for_wise"),
        ("queued_for_wise", "wise_fund_pending"),
        ("wise_fund_pending", "wise_fund_failed"),
        ("wise_fund_failed", "queued_for_wise"),
    ):
        u = get_wallet_updates(old, new, 1000)
        assert u == {}, f"transition {old}→{new} must not change balance, got {u}"


def test_wise_fund_pending_to_paid_out():
    u = get_wallet_updates("wise_fund_pending", "paid_out", 1000, base_currency="GBP")
    assert u["reserved_balance_minor"] == -1000
    assert u["total_paid_out_minor"] == 1000
    assert u["pool_balance_gbp_minor"] == -1000


def test_any_pipeline_state_failed_rollback():
    for state in ("reserved_for_batch", "queued_for_wise", "wise_fund_pending", "wise_fund_failed"):
        u = get_wallet_updates(state, "failed", 1000)
        assert u["reserved_balance_minor"] == -1000
        assert u["available_balance_minor"] == 1000


def test_reserve_expiry_rollback():
    """reserved_for_batch → available (7-day expiry cron)"""
    u = get_wallet_updates("reserved_for_batch", "available", 500)
    assert u["reserved_balance_minor"] == -500
    assert u["available_balance_minor"] == 500


def test_try_payout_decrements_pool_gbp():
    u = get_wallet_updates(
        "wise_fund_pending", "paid_out",
        amount_display_minor=100_000,
        amount_settled_gbp_minor=25_000,
        base_currency="TRY",
    )
    assert u["reserved_balance_minor"] == -100_000
    assert u["total_paid_out_minor"] == 100_000
    assert u["pool_balance_gbp_minor"] == -25_000


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validate_transition_ok():
    assert StateMachine.validate_transition("available", "reserved_for_batch") is True
    assert StateMachine.validate_transition("reserved_for_batch", "queued_for_wise") is True
    assert StateMachine.validate_transition("queued_for_wise", "wise_fund_pending") is True
    assert StateMachine.validate_transition("wise_fund_pending", "paid_out") is True


def test_validate_transition_invalid_raises():
    with pytest.raises(InvalidTransitionError):
        StateMachine.validate_transition("available", "paid_out")
    with pytest.raises(InvalidTransitionError):
        StateMachine.validate_transition("pending", "queued_for_wise")


def test_validate_skip_through_pipeline_not_allowed():
    # Can't jump from reserved_for_batch straight to paid_out — must go through pipeline
    with pytest.raises(InvalidTransitionError):
        StateMachine.validate_transition("reserved_for_batch", "paid_out")


def test_terminal_states_have_no_targets():
    for term in TERMINAL_STATES:
        assert TRANSITIONS[term] == set()
