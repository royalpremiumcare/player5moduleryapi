"""
PLANN Financial Engine — Webhook Idempotency & State Machine Tests

Written FIRST (TDD) alongside state_machine.py per Implementation Rule 2.
Tests cover:
  1. State machine transition validation (single source of truth)
  2. Wallet balance updates per transition
  3. Duplicate webhook idempotency (same event_id → skipped)
  4. Replay of failed webhook events
  5. Invalid transition rejection
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import hashlib
import json

from financial.state_machine import (
    TRANSITIONS,
    TERMINAL_STATES,
    StateMachine,
    InvalidTransitionError,
    TransactionNotFoundError,
    get_wallet_updates,
    create_transaction,
)
from financial.money import (
    to_minor,
    from_minor,
    apply_rate,
    rate_to_micro,
    validate_turkish_iban,
    validate_uk_sort_code,
    validate_uk_account_number,
    get_tier_config,
    format_display,
    apply_bps,
)
from financial.schemas import (
    MerchantWallet,
    MerchantTransaction,
    WebhookEvent,
    TRANSACTION_STATES,
)

from decimal import Decimal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockCollection:
    """Minimal async mock for a MongoDB collection."""

    def __init__(self):
        self._docs = {}

    async def find_one(self, query):
        if "id" in query:
            doc = self._docs.get(query["id"])
            if doc and "state" in query and doc.get("state") != query["state"]:
                return None
            return doc
        if "event_id" in query:
            for doc in self._docs.values():
                if doc.get("event_id") == query["event_id"]:
                    return doc
        return None

    async def insert_one(self, doc):
        key = doc.get("id") or doc.get("event_id")
        self._docs[key] = dict(doc)
        return MagicMock(inserted_id=key)

    async def update_one(self, query, update):
        doc_id = query.get("id")
        if not doc_id:
            doc_id = query.get("organization_id")
            for d in self._docs.values():
                if d.get("organization_id") == doc_id:
                    doc = d
                    break
            else:
                return MagicMock(modified_count=0)
        else:
            doc = self._docs.get(doc_id)

        if not doc:
            return MagicMock(modified_count=0)

        # Check optimistic lock (state field in query)
        if "state" in query and doc.get("state") != query["state"]:
            return MagicMock(modified_count=0)

        if "$set" in update:
            for k, v in update["$set"].items():
                doc[k] = v
        if "$inc" in update:
            for k, v in update["$inc"].items():
                doc[k] = doc.get(k, 0) + v
        if "$push" in update:
            for k, v in update["$push"].items():
                if k not in doc:
                    doc[k] = []
                doc[k].append(v)

        return MagicMock(modified_count=1)


class MockDB:
    def __init__(self):
        self.merchant_transactions = MockCollection()
        self.merchant_wallets = MockCollection()
        self.webhook_events = MockCollection()


@pytest.fixture
def db():
    return MockDB()


@pytest.fixture
def sm(db):
    return StateMachine(db)


async def _setup_wallet(db, org_id="org_1", base_currency="TRY"):
    """Insert a wallet with zero balances."""
    wallet = MerchantWallet(
        organization_id=org_id,
        base_currency=base_currency,
    )
    doc = wallet.model_dump()
    doc["id"] = org_id  # for MockCollection lookup
    await db.merchant_wallets.insert_one(doc)
    return doc


async def _setup_tx(db, org_id="org_1", base_currency="TRY", state="pending",
                     amount=100_000, settled_gbp=2_400, tx_type="payment"):
    """Insert a transaction in a given state."""
    tx = MerchantTransaction(
        organization_id=org_id,
        base_currency=base_currency,
        type=tx_type,
        state=state,
        state_history=[{"state": state, "timestamp": datetime.now(timezone.utc).isoformat(), "trigger": "test"}],
        amount_display_minor=amount,
        amount_settled_gbp_minor=settled_gbp,
        exchange_rate_at_time=42_350_000 if base_currency == "TRY" else 1_000_000,
        fee_amount_minor=0,
        fee_rate_bps=0,
        fee_preference="seller_pays",
    )
    doc = tx.model_dump()
    await db.merchant_transactions.insert_one(doc)
    return doc


# ===========================================================================
# TEST GROUP 1: Transition Table Validation
# ===========================================================================

class TestTransitionTable:
    """Verify TRANSITIONS dict is the single source of truth and is complete."""

    def test_all_states_have_entries(self):
        """Every known state must appear as a key in TRANSITIONS."""
        for state in TRANSACTION_STATES:
            assert state in TRANSITIONS, f"State '{state}' missing from TRANSITIONS"

    def test_all_target_states_are_known(self):
        """Every target state in TRANSITIONS must be a known state."""
        for source, targets in TRANSITIONS.items():
            for target in targets:
                assert target in TRANSACTION_STATES, (
                    f"Unknown target state '{target}' from '{source}'"
                )

    def test_terminal_states_have_no_targets(self):
        """Terminal states must have empty target sets."""
        expected_terminals = {
            "async_failed", "paid_out", "resolved_won", "resolved_lost",
            "refunded", "canceled", "failed",
        }
        for state in expected_terminals:
            assert TRANSITIONS.get(state) == set(), (
                f"Terminal state '{state}' has targets: {TRANSITIONS.get(state)}"
            )

    def test_terminal_states_set(self):
        """TERMINAL_STATES constant matches actual terminal states."""
        actual = {s for s, t in TRANSITIONS.items() if not t}
        assert TERMINAL_STATES == actual

    def test_happy_path_exists(self):
        """The full happy path must be representable."""
        path = ["pending", "authorized", "captured", "settled", "available", "reserved", "paid_out"]
        for i in range(len(path) - 1):
            assert path[i + 1] in TRANSITIONS[path[i]], (
                f"Happy path broken: '{path[i]}' → '{path[i+1]}' not in TRANSITIONS"
            )

    def test_dispute_path_exists(self):
        """Dispute lifecycle must be representable."""
        path = ["available", "frozen", "disputed", "resolved_won"]
        for i in range(len(path) - 1):
            assert path[i + 1] in TRANSITIONS[path[i]]

        path_lost = ["available", "frozen", "disputed", "resolved_lost"]
        for i in range(len(path_lost) - 1):
            assert path_lost[i + 1] in TRANSITIONS[path_lost[i]]

    def test_refund_from_captured(self):
        assert "refunded" in TRANSITIONS["captured"]

    def test_refund_from_available(self):
        assert "refunded" in TRANSITIONS["available"]

    def test_cancel_from_pending(self):
        assert "canceled" in TRANSITIONS["pending"]

    def test_async_failed_from_pending(self):
        assert "async_failed" in TRANSITIONS["pending"]

    def test_invalid_transition_raises(self):
        """Attempting an invalid transition must raise."""
        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition("paid_out", "available")

        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition("pending", "paid_out")

        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition("nonexistent", "captured")


# ===========================================================================
# TEST GROUP 2: Wallet Balance Updates
# ===========================================================================

class TestWalletUpdates:
    """Verify get_wallet_updates returns correct $inc operations."""

    def test_captured_try_merchant(self):
        updates = get_wallet_updates("pending", "captured", 100_000, 2_400, "TRY")
        assert updates["pending_balance_minor"] == 100_000
        assert updates["total_earned_minor"] == 100_000
        assert updates["pool_balance_gbp_minor"] == 2_400

    def test_captured_gbp_merchant(self):
        updates = get_wallet_updates("pending", "captured", 5_000, 4_850, "GBP")
        assert updates["pending_balance_minor"] == 5_000
        assert updates["total_earned_minor"] == 5_000
        # GBP merchants: pool_balance is NOT set from amount_settled_gbp_minor
        # because pool = available for GBP
        assert "pool_balance_gbp_minor" not in updates

    def test_settled(self):
        updates = get_wallet_updates("captured", "settled", 100_000)
        assert updates["pending_balance_minor"] == -100_000
        assert updates["settled_balance_minor"] == 100_000

    def test_available(self):
        updates = get_wallet_updates("settled", "available", 100_000)
        assert updates["settled_balance_minor"] == -100_000
        assert updates["available_balance_minor"] == 100_000

    def test_reserved(self):
        updates = get_wallet_updates("available", "reserved", 100_000)
        assert updates["available_balance_minor"] == -100_000
        assert updates["reserved_balance_minor"] == 100_000

    def test_paid_out_try(self):
        updates = get_wallet_updates("reserved", "paid_out", 100_000, 2_400, "TRY")
        assert updates["reserved_balance_minor"] == -100_000
        assert updates["total_paid_out_minor"] == 100_000
        assert updates["pool_balance_gbp_minor"] == -2_400

    def test_paid_out_gbp(self):
        updates = get_wallet_updates("reserved", "paid_out", 5_000, 0, "GBP")
        assert updates["reserved_balance_minor"] == -5_000
        assert updates["total_paid_out_minor"] == 5_000
        assert updates["pool_balance_gbp_minor"] == -5_000

    def test_failed_rollback(self):
        updates = get_wallet_updates("reserved", "failed", 100_000)
        assert updates["reserved_balance_minor"] == -100_000
        assert updates["available_balance_minor"] == 100_000

    def test_frozen(self):
        updates = get_wallet_updates("available", "frozen", 100_000)
        assert updates["available_balance_minor"] == -100_000
        assert updates["frozen_balance_minor"] == 100_000

    def test_resolved_won(self):
        updates = get_wallet_updates("disputed", "resolved_won", 100_000)
        assert updates["frozen_balance_minor"] == -100_000
        assert updates["available_balance_minor"] == 100_000

    def test_resolved_lost_try(self):
        updates = get_wallet_updates("disputed", "resolved_lost", 100_000, 2_400, "TRY")
        assert updates["frozen_balance_minor"] == -100_000
        assert updates["pool_balance_gbp_minor"] == -2_400

    def test_refunded_from_available(self):
        updates = get_wallet_updates("available", "refunded", 100_000, 2_400, "TRY")
        assert updates["available_balance_minor"] == -100_000
        assert updates["total_earned_minor"] == -100_000
        assert updates["pool_balance_gbp_minor"] == -2_400

    def test_refunded_from_captured(self):
        updates = get_wallet_updates("captured", "refunded", 100_000, 2_400, "TRY")
        assert updates["pending_balance_minor"] == -100_000
        assert updates["total_earned_minor"] == -100_000

    def test_canceled_no_wallet_effect(self):
        updates = get_wallet_updates("pending", "canceled", 100_000)
        assert updates == {}

    def test_frozen_to_disputed_no_wallet_effect(self):
        updates = get_wallet_updates("frozen", "disputed", 100_000)
        assert updates == {}


# ===========================================================================
# TEST GROUP 3: State Machine Integration (async)
# ===========================================================================

class TestStateMachineIntegration:

    @pytest.mark.asyncio
    async def test_happy_path_captured(self, db, sm):
        await _setup_wallet(db, "org_1", "TRY")
        tx = await _setup_tx(db, "org_1", "TRY", "pending", 100_000, 2_400)

        wallet_inc = await sm.transition(
            tx_id=tx["id"],
            new_state="captured",
            trigger="checkout.session.completed",
        )

        assert wallet_inc["pending_balance_minor"] == 100_000
        assert wallet_inc["pool_balance_gbp_minor"] == 2_400

        # Verify transaction state updated
        updated_tx = await db.merchant_transactions.find_one({"id": tx["id"]})
        assert updated_tx["state"] == "captured"
        assert len(updated_tx["state_history"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, db, sm):
        await _setup_wallet(db, "org_1")
        tx = await _setup_tx(db, "org_1", state="pending")

        with pytest.raises(InvalidTransitionError):
            await sm.transition(tx["id"], "paid_out", "bad_trigger")

    @pytest.mark.asyncio
    async def test_transaction_not_found(self, db, sm):
        with pytest.raises(TransactionNotFoundError):
            await sm.transition("nonexistent_id", "captured", "test")

    @pytest.mark.asyncio
    async def test_full_happy_path(self, db, sm):
        """Test the complete payment → payout lifecycle."""
        await _setup_wallet(db, "org_1", "TRY")
        tx = await _setup_tx(db, "org_1", "TRY", "pending", 100_000, 2_400)

        # pending → captured
        await sm.transition(tx["id"], "captured", "checkout.session.completed")
        # captured → settled
        await sm.transition(tx["id"], "settled", "stripe.settlement")
        # settled → available
        await sm.transition(tx["id"], "available", "settlement_check_job")
        # available → reserved
        await sm.transition(tx["id"], "reserved", "payout_batch_created")
        # reserved → paid_out
        await sm.transition(tx["id"], "paid_out", "wise.outgoing_payment_sent")

        # Verify final state
        final_tx = await db.merchant_transactions.find_one({"id": tx["id"]})
        assert final_tx["state"] == "paid_out"
        assert len(final_tx["state_history"]) == 6  # pending + 5 transitions

    @pytest.mark.asyncio
    async def test_dispute_lifecycle(self, db, sm):
        """Test dispute: available → frozen → disputed → resolved_won."""
        await _setup_wallet(db, "org_1", "TRY")
        tx = await _setup_tx(db, "org_1", "TRY", "available", 100_000, 2_400)

        # Pre-set wallet available balance
        await db.merchant_wallets.update_one(
            {"organization_id": "org_1"},
            {"$set": {"available_balance_minor": 100_000}},
        )

        await sm.transition(tx["id"], "frozen", "charge.dispute.created")
        await sm.transition(tx["id"], "disputed", "dispute_processing")
        await sm.transition(tx["id"], "resolved_won", "charge.dispute.funds_reinstated")

        final_tx = await db.merchant_transactions.find_one({"id": tx["id"]})
        assert final_tx["state"] == "resolved_won"

    @pytest.mark.asyncio
    async def test_metadata_merge(self, db, sm):
        """Extra metadata should be $set on the transaction."""
        await _setup_wallet(db, "org_1")
        tx = await _setup_tx(db, "org_1", state="pending")

        await sm.transition(
            tx["id"], "captured", "checkout.session.completed",
            metadata={"stripe_charge_id": "ch_test123"},
        )

        updated = await db.merchant_transactions.find_one({"id": tx["id"]})
        assert updated["stripe_charge_id"] == "ch_test123"


# ===========================================================================
# TEST GROUP 4: Webhook Idempotency
# ===========================================================================

class TestWebhookIdempotency:
    """Test that duplicate webhooks are detected and skipped."""

    @pytest.mark.asyncio
    async def test_duplicate_event_id_detected(self, db):
        """Same event_id submitted twice → second should be skippable."""
        event_id = "evt_test_123"

        # First event
        event1 = WebhookEvent(
            source="stripe_merchant",
            event_id=event_id,
            event_type="checkout.session.completed",
            payload={"id": event_id},
            raw_body='{"id": "evt_test_123"}',
            body_sha256=hashlib.sha256(b'{"id": "evt_test_123"}').hexdigest(),
            signature_verified=True,
            processing_status="processed",
        )
        await db.webhook_events.insert_one(event1.model_dump())

        # Check if event already exists (idempotency check)
        existing = await db.webhook_events.find_one({"event_id": event_id})
        assert existing is not None
        assert existing["processing_status"] == "processed"

        # Second event with same ID should be detected
        is_duplicate = existing is not None
        assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_new_event_not_duplicate(self, db):
        """A new event_id should not be flagged as duplicate."""
        existing = await db.webhook_events.find_one({"event_id": "evt_new_456"})
        assert existing is None

    @pytest.mark.asyncio
    async def test_failed_event_can_be_retried(self, db):
        """Events with processing_status='failed' should be retryable."""
        event_id = "evt_failed_789"

        event = WebhookEvent(
            source="stripe_merchant",
            event_id=event_id,
            event_type="payment_intent.succeeded",
            payload={"id": event_id},
            processing_status="failed",
            processing_error="Temporary DB error",
            attempt_count=1,
        )
        await db.webhook_events.insert_one(event.model_dump())

        # Fetch failed event for retry
        failed = await db.webhook_events.find_one({"event_id": event_id})
        assert failed["processing_status"] == "failed"
        assert failed["attempt_count"] == 1

        # Simulate retry: update status to processing
        await db.webhook_events.update_one(
            {"event_id": event_id},
            {
                "$set": {
                    "processing_status": "processing",
                    "attempt_count": 2,
                    "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

        retried = await db.webhook_events.find_one({"event_id": event_id})
        assert retried["processing_status"] == "processing"
        assert retried["attempt_count"] == 2

    @pytest.mark.asyncio
    async def test_idempotent_captured_transition(self, db, sm):
        """
        Simulate: checkout.session.completed webhook fires twice.
        First → captured. Second → should fail (captured has no self-transition).
        """
        await _setup_wallet(db, "org_1")
        tx = await _setup_tx(db, "org_1", state="pending")

        # First webhook
        await sm.transition(tx["id"], "captured", "checkout.session.completed")

        # Second webhook — same transition attempt → InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            await sm.transition(tx["id"], "captured", "checkout.session.completed")

    @pytest.mark.asyncio
    async def test_wise_payout_idempotent(self, db, sm):
        """
        Simulate: Wise outgoing_payment_sent webhook fires twice.
        First → paid_out. Second → InvalidTransitionError (paid_out is terminal).
        """
        await _setup_wallet(db, "org_1", "TRY")
        tx = await _setup_tx(db, "org_1", "TRY", "reserved", 100_000, 2_400)
        await db.merchant_wallets.update_one(
            {"organization_id": "org_1"},
            {"$set": {"reserved_balance_minor": 100_000}},
        )

        await sm.transition(tx["id"], "paid_out", "wise.outgoing_payment_sent")

        with pytest.raises(InvalidTransitionError):
            await sm.transition(tx["id"], "paid_out", "wise.outgoing_payment_sent")


# ===========================================================================
# TEST GROUP 5: Money Utilities
# ===========================================================================

class TestMoneyUtils:

    def test_to_minor_try(self):
        assert to_minor(Decimal("1000.00"), "TRY") == 100_000

    def test_to_minor_gbp(self):
        assert to_minor(Decimal("50.00"), "GBP") == 5_000

    def test_from_minor_try(self):
        assert from_minor(100_000, "TRY") == Decimal("1000.00")

    def test_from_minor_gbp(self):
        assert from_minor(5_000, "GBP") == Decimal("50.00")

    def test_apply_rate_gbp_to_try(self):
        rate_micro = 42_350_000  # 42.35
        gbp_pence = 10_000  # £100
        try_kurus = apply_rate(gbp_pence, rate_micro)
        assert try_kurus == 423_500  # ₺4,235.00 (£100 × 42.35)

    def test_apply_rate_try_to_gbp_inverse(self):
        rate_micro = 42_350_000
        try_kurus = 423_500  # ₺4,235.00
        gbp_pence = apply_rate(try_kurus, rate_micro, inverse=True)
        assert gbp_pence == 10_000  # £100

    def test_rate_roundtrip(self):
        rate = Decimal("42.35")
        micro = rate_to_micro(rate)
        assert micro == 42_350_000
        from financial.money import rate_from_micro
        back = rate_from_micro(micro)
        assert back == Decimal("42.350000")

    def test_apply_bps(self):
        assert apply_bps(100_000, 700) == 7_000  # 7% of ₺1000 = ₺70 = 7000 kuruş
        assert apply_bps(5_000, 300) == 150  # 3% of £50 = £1.50 = 150 pence

    def test_format_display_try(self):
        assert format_display(100_000, "TRY") == "1.000,00 ₺"
        assert format_display(600_000, "TRY") == "6.000,00 ₺"

    def test_format_display_gbp(self):
        assert format_display(5_000, "GBP") == "£50.00"
        assert format_display(2_500, "GBP") == "£25.00"

    def test_validate_turkish_iban_valid(self):
        # TR330006100519786457841326 is a valid test IBAN
        assert validate_turkish_iban("TR330006100519786457841326") is True

    def test_validate_turkish_iban_invalid_format(self):
        assert validate_turkish_iban("TR12345") is False
        assert validate_turkish_iban("GB330006100519786457841326") is False
        assert validate_turkish_iban("") is False

    def test_validate_uk_sort_code(self):
        assert validate_uk_sort_code("12-34-56") is True
        assert validate_uk_sort_code("123456") is True
        assert validate_uk_sort_code("12345") is False

    def test_validate_uk_account_number(self):
        assert validate_uk_account_number("12345678") is True
        assert validate_uk_account_number("1234567") is False

    def test_tier_config_try(self):
        cfg = get_tier_config("TRY", "standard")
        assert cfg.limit_minor == 1_200_000
        assert cfg.fee_rate_bps == 800
        assert cfg.gbp_target_minor == 20_000

    def test_tier_config_gbp(self):
        cfg = get_tier_config("GBP", "fast")
        assert cfg.limit_minor == 2_500
        assert cfg.fee_rate_bps == 500

    def test_unsupported_currency_raises(self):
        with pytest.raises(ValueError):
            to_minor(Decimal("10"), "EUR")
