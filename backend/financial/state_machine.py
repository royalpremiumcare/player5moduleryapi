"""
PLANN Financial Engine — Transaction State Machine

SINGLE SOURCE OF TRUTH for all valid state transitions.
Every webhook handler, payout service, and cron job calls StateMachine.transition().
No state changes happen outside this module.

States:
    pending → authorized → captured → settled → available → reserved → paid_out
    pending → canceled
    pending → async_failed
    captured → refunded
    available → refunded
    available → frozen → disputed → resolved_won (→ available)
    available → frozen → disputed → resolved_lost (→ permanent loss)
    reserved → paid_out
    reserved → failed (→ available rollback)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transition Table — THE SINGLE SOURCE OF TRUTH
# Key: current_state → Value: set of valid next states
# ---------------------------------------------------------------------------

TRANSITIONS: Dict[str, set] = {
    "pending":            {"authorized", "captured", "canceled", "async_failed"},
    "authorized":         {"captured", "canceled"},
    "captured":           {"settled", "refunded"},
    "async_failed":       set(),  # terminal
    "settled":            {"available"},
    # `available` can go into batch pipeline (new) or legacy `reserved` (alias)
    "available":          {"reserved", "reserved_for_batch", "frozen", "refunded"},
    # Legacy state — kept for backward compatibility. Treated as `reserved_for_batch`.
    "reserved":           {"paid_out", "failed", "queued_for_wise"},
    # New batch pipeline states (PLANN v2)
    "reserved_for_batch": {"queued_for_wise", "failed", "available"},  # available = expiry rollback
    "queued_for_wise":    {"wise_fund_pending", "failed"},
    "wise_fund_pending":  {"paid_out", "wise_fund_failed"},
    "wise_fund_failed":   {"queued_for_wise", "failed"},  # retry or give up
    "paid_out":           set(),  # terminal
    "frozen":             {"disputed"},
    "disputed":           {"resolved_won", "resolved_lost"},
    "resolved_won":       set(),  # terminal — funds returned to available via wallet op
    "resolved_lost":      set(),  # terminal — permanent loss
    "refunded":           set(),  # terminal
    "canceled":           set(),  # terminal
    "failed":             set(),  # terminal — rollback handled separately
}

# States that are terminal (no further transitions)
TERMINAL_STATES = {state for state, targets in TRANSITIONS.items() if not targets}

# States that affect wallet balances
WALLET_CREDIT_STATES = {"captured", "settled", "available", "resolved_won"}
WALLET_DEBIT_STATES = {"refunded", "resolved_lost", "paid_out"}
WALLET_HOLD_STATES = {"reserved", "reserved_for_batch", "queued_for_wise", "wise_fund_pending", "frozen"}
WALLET_RELEASE_STATES = {"failed"}  # reserved → available rollback

# Alias map for legacy state names during rename migration
STATE_ALIASES = {
    # Old name → new canonical name (not auto-substituted; used for dual-read)
    "reserved": "reserved_for_batch",
}


def canonical_state(state: str) -> str:
    """Return the canonical state name if legacy, else the input."""
    return STATE_ALIASES.get(state, state)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_state: str, target_state: str, tx_id: str = ""):
        self.current_state = current_state
        self.target_state = target_state
        self.tx_id = tx_id
        msg = (
            f"Invalid transition: '{current_state}' → '{target_state}'"
            f"{f' (tx: {tx_id})' if tx_id else ''}"
        )
        super().__init__(msg)


class TransactionNotFoundError(Exception):
    """Raised when a transaction is not found in the database."""
    pass


# ---------------------------------------------------------------------------
# Wallet Balance Operations
# Each state transition has a corresponding wallet balance effect.
# ---------------------------------------------------------------------------

def get_wallet_updates(
    old_state: str,
    new_state: str,
    amount_display_minor: int,
    amount_settled_gbp_minor: int = 0,
    base_currency: str = "TRY",
) -> Dict[str, int]:
    """
    Calculate the wallet $inc operations for a state transition.
    Returns a dict of field_name → increment_value (can be negative).
    """
    updates: Dict[str, int] = {}

    # --- Payment lifecycle ---
    if old_state == "pending" and new_state == "captured":
        updates["pending_balance_minor"] = amount_display_minor
        updates["total_earned_minor"] = amount_display_minor
        if base_currency == "TRY" and amount_settled_gbp_minor > 0:
            updates["pool_balance_gbp_minor"] = amount_settled_gbp_minor

    elif old_state == "captured" and new_state == "settled":
        updates["pending_balance_minor"] = -amount_display_minor
        updates["settled_balance_minor"] = amount_display_minor

    elif old_state == "settled" and new_state == "available":
        updates["settled_balance_minor"] = -amount_display_minor
        updates["available_balance_minor"] = amount_display_minor

    # --- Payout lifecycle ---
    elif old_state == "available" and new_state in ("reserved", "reserved_for_batch"):
        updates["available_balance_minor"] = -amount_display_minor
        updates["reserved_balance_minor"] = amount_display_minor

    # Intra-pipeline transitions (reserved_for_batch → queued_for_wise → wise_fund_pending):
    # Balance stays in reserved_balance_minor — no $inc needed.
    elif (old_state, new_state) in (
        ("reserved", "queued_for_wise"),
        ("reserved_for_batch", "queued_for_wise"),
        ("queued_for_wise", "wise_fund_pending"),
        ("wise_fund_pending", "wise_fund_failed"),
        ("wise_fund_failed", "queued_for_wise"),
    ):
        pass  # money stays reserved

    elif old_state in ("reserved", "wise_fund_pending") and new_state == "paid_out":
        updates["reserved_balance_minor"] = -amount_display_minor
        updates["total_paid_out_minor"] = amount_display_minor
        if base_currency == "TRY" and amount_settled_gbp_minor > 0:
            updates["pool_balance_gbp_minor"] = -amount_settled_gbp_minor
        elif base_currency == "GBP":
            updates["pool_balance_gbp_minor"] = -amount_display_minor

    elif old_state in (
        "reserved", "reserved_for_batch", "queued_for_wise",
        "wise_fund_pending", "wise_fund_failed",
    ) and new_state == "failed":
        # Rollback: any in-flight payout state → available
        updates["reserved_balance_minor"] = -amount_display_minor
        updates["available_balance_minor"] = amount_display_minor

    elif old_state == "reserved_for_batch" and new_state == "available":
        # Reserve expiry rollback (7-day cron)
        updates["reserved_balance_minor"] = -amount_display_minor
        updates["available_balance_minor"] = amount_display_minor

    # --- Dispute lifecycle ---
    elif old_state == "available" and new_state == "frozen":
        updates["available_balance_minor"] = -amount_display_minor
        updates["frozen_balance_minor"] = amount_display_minor

    elif old_state == "disputed" and new_state == "resolved_won":
        updates["frozen_balance_minor"] = -amount_display_minor
        updates["available_balance_minor"] = amount_display_minor

    elif old_state == "disputed" and new_state == "resolved_lost":
        updates["frozen_balance_minor"] = -amount_display_minor
        # Permanent loss — total_earned stays, but the money is gone
        if base_currency == "TRY" and amount_settled_gbp_minor > 0:
            updates["pool_balance_gbp_minor"] = -amount_settled_gbp_minor
        elif base_currency == "GBP":
            updates["pool_balance_gbp_minor"] = -amount_display_minor

    # --- Refund ---
    elif new_state == "refunded":
        if old_state == "captured":
            updates["pending_balance_minor"] = -amount_display_minor
        elif old_state == "available":
            updates["available_balance_minor"] = -amount_display_minor
        updates["total_earned_minor"] = -amount_display_minor
        if base_currency == "TRY" and amount_settled_gbp_minor > 0:
            updates["pool_balance_gbp_minor"] = -amount_settled_gbp_minor
        elif base_currency == "GBP":
            updates["pool_balance_gbp_minor"] = -amount_display_minor

    # frozen → disputed has no balance effect (stays frozen)
    # pending → canceled / async_failed has no balance effect

    return updates


# ---------------------------------------------------------------------------
# State Machine Core
# ---------------------------------------------------------------------------

class StateMachine:
    """
    Transaction State Machine.

    Usage:
        sm = StateMachine(db)
        wallet_updates = await sm.transition(
            tx_id="...",
            new_state="captured",
            trigger="checkout.session.completed",
            metadata={"stripe_charge_id": "ch_xxx"}
        )
    """

    def __init__(self, db):
        """
        Args:
            db: AsyncIOMotorDatabase instance
        """
        self.db = db

    @staticmethod
    def validate_transition(current_state: str, new_state: str, tx_id: str = "") -> bool:
        """
        Check if a transition is valid without performing it.
        Raises InvalidTransitionError if invalid.
        Returns True if valid.
        """
        if current_state not in TRANSITIONS:
            raise InvalidTransitionError(current_state, new_state, tx_id)

        valid_targets = TRANSITIONS[current_state]
        if new_state not in valid_targets:
            raise InvalidTransitionError(current_state, new_state, tx_id)

        return True

    @staticmethod
    def is_terminal(state: str) -> bool:
        """Check if a state is terminal (no further transitions possible)."""
        return state in TERMINAL_STATES

    @staticmethod
    def get_valid_transitions(current_state: str) -> set:
        """Return the set of valid next states from current_state."""
        return TRANSITIONS.get(current_state, set()).copy()

    async def transition(
        self,
        tx_id: str,
        new_state: str,
        trigger: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Perform an atomic state transition on a transaction.

        1. Load the transaction
        2. Validate the transition
        3. Update transaction state + state_history
        4. Calculate and apply wallet balance changes
        5. Return the wallet update dict

        Args:
            tx_id: merchant_transactions.id
            new_state: Target state
            trigger: What caused this transition (e.g. "checkout.session.completed")
            metadata: Additional fields to $set on the transaction

        Returns:
            Dict of wallet $inc updates that were applied

        Raises:
            TransactionNotFoundError: if tx not found
            InvalidTransitionError: if transition is not valid
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Load transaction
        tx = await self.db.merchant_transactions.find_one({"id": tx_id})
        if not tx:
            raise TransactionNotFoundError(f"Transaction not found: {tx_id}")

        current_state = tx["state"]
        org_id = tx["organization_id"]

        # 2. Validate
        self.validate_transition(current_state, new_state, tx_id)

        # 3. Build state history entry
        history_entry = {
            "state": new_state,
            "timestamp": now,
            "trigger": trigger,
        }

        # 4. Build transaction update
        tx_update: Dict[str, Any] = {
            "$set": {
                "state": new_state,
                "updated_at": now,
            },
            "$push": {
                "state_history": history_entry,
            },
        }

        # Merge additional metadata into $set
        if metadata:
            for key, value in metadata.items():
                if key not in ("state", "state_history", "updated_at"):
                    tx_update["$set"][key] = value

        # 5. Calculate wallet updates
        wallet_inc = get_wallet_updates(
            old_state=current_state,
            new_state=new_state,
            amount_display_minor=tx.get("amount_display_minor", 0),
            amount_settled_gbp_minor=tx.get("amount_settled_gbp_minor", 0),
            base_currency=tx.get("base_currency", "TRY"),
        )

        # 6. Apply transaction update
        result = await self.db.merchant_transactions.update_one(
            {"id": tx_id, "state": current_state},  # Optimistic lock on current state
            tx_update,
        )

        if result.modified_count == 0:
            # Race condition: state was changed by another process
            logger.warning(
                "State transition race condition: tx=%s, expected=%s, target=%s",
                tx_id, current_state, new_state,
            )
            raise InvalidTransitionError(current_state, new_state, tx_id)

        # 7. Apply wallet updates atomically
        if wallet_inc:
            wallet_update_result = await self.db.merchant_wallets.update_one(
                {"organization_id": org_id},
                {
                    "$inc": wallet_inc,
                    "$set": {"updated_at": now},
                },
            )
            if wallet_update_result.modified_count == 0:
                logger.error(
                    "Wallet update failed for org=%s after transition tx=%s %s→%s",
                    org_id, tx_id, current_state, new_state,
                )

        logger.info(
            "State transition: tx=%s %s→%s trigger=%s wallet_updates=%s",
            tx_id, current_state, new_state, trigger, wallet_inc,
        )

        return wallet_inc


# ---------------------------------------------------------------------------
# Convenience: Create initial transaction with pending state
# ---------------------------------------------------------------------------

async def create_transaction(
    db,
    organization_id: str,
    base_currency: str,
    tx_type: str,
    amount_display_minor: int,
    amount_settled_gbp_minor: int = 0,
    exchange_rate_at_time: int = 1_000_000,
    fee_amount_minor: int = 0,
    fee_rate_bps: int = 0,
    fee_preference: str = "seller_pays",
    appointment_id: Optional[str] = None,
    customer_phone: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None,
    **extra_fields,
) -> Dict[str, Any]:
    """
    Create a new transaction in 'pending' state and insert into DB.
    Returns the inserted document dict.
    """
    from .schemas import MerchantTransaction

    now = datetime.now(timezone.utc).isoformat()

    tx = MerchantTransaction(
        organization_id=organization_id,
        base_currency=base_currency,
        type=tx_type,
        state="pending",
        state_history=[{"state": "pending", "timestamp": now, "trigger": "created"}],
        amount_display_minor=amount_display_minor,
        amount_settled_gbp_minor=amount_settled_gbp_minor,
        exchange_rate_at_time=exchange_rate_at_time,
        fee_amount_minor=fee_amount_minor,
        fee_rate_bps=fee_rate_bps,
        fee_preference=fee_preference,
        appointment_id=appointment_id,
        customer_phone=customer_phone,
        stripe_checkout_session_id=stripe_checkout_session_id,
        stripe_payment_intent_id=stripe_payment_intent_id,
    )

    doc = tx.model_dump()
    # Remove None-valued sparse-indexed fields so MongoDB sparse unique
    # indexes skip this document instead of rejecting duplicate nulls.
    for sparse_key in (
        "stripe_payment_intent_id", "stripe_charge_id",
        "stripe_checkout_session_id", "stripe_refund_id",
        "stripe_dispute_id", "wise_transfer_id", "wise_quote_id",
        "payout_batch_id",
    ):
        if doc.get(sparse_key) is None:
            doc.pop(sparse_key, None)

    # Merge any extra fields (overwrite if doc value is None)
    for key, value in extra_fields.items():
        if key not in doc or doc[key] is None:
            doc[key] = value

    await db.merchant_transactions.insert_one(doc)
    logger.info("Created transaction: id=%s org=%s type=%s amount=%d %s",
                doc["id"], organization_id, tx_type, amount_display_minor, base_currency)
    return doc
