"""
Wallet Debt Service — negative balance & payout-stop logic.

When a refund or dispute loss exceeds available balance, the system does NOT
create a true negative ledger. Instead:
  1. pending_debt_minor is increased to cover the shortfall
  2. wallet_status = "payout_stopped" (or "suspended" for severe cases)
  3. Future earnings first reduce pending_debt, then restore available

Gated by env flag FEATURE_NEGATIVE_BALANCE.

See plan Bölüm 2.3, 11.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .feature_flags import is_env_flag_enabled

logger = logging.getLogger(__name__)


WALLET_STATUS_ACTIVE = "active"
WALLET_STATUS_PAYOUT_STOPPED = "payout_stopped"
WALLET_STATUS_SUSPENDED = "suspended"


async def apply_debit(
    db,
    organization_id: str,
    amount_minor: int,
    *,
    reason: str,
    source: str,  # "refund" | "dispute_lost" | "manual"
    source_entity_id: str = "",
) -> Dict[str, Any]:
    """
    Apply a debit to a wallet, creating pending_debt if it exceeds available balance.
    Returns a summary dict with applied/debt amounts and new wallet_status.
    """
    if amount_minor <= 0:
        return {"applied": 0, "debt_created": 0, "status": "noop"}

    wallet = await db.merchant_wallets.find_one({"organization_id": organization_id})
    if not wallet:
        logger.error("wallet not found for debit: org=%s", organization_id)
        return {"applied": 0, "debt_created": amount_minor, "status": "no_wallet"}

    available = int(wallet.get("available_balance_minor") or 0)
    existing_debt = int(wallet.get("pending_debt_minor") or 0)
    now = datetime.now(timezone.utc).isoformat()

    if not is_env_flag_enabled("FEATURE_NEGATIVE_BALANCE"):
        # Legacy behaviour: allow available to go negative (pre-v2)
        await db.merchant_wallets.update_one(
            {"organization_id": organization_id},
            {"$inc": {"available_balance_minor": -amount_minor}, "$set": {"updated_at": now}},
        )
        logger.info(
            "wallet_debit (legacy): org=%s amount=%d reason=%s",
            organization_id, amount_minor, reason,
        )
        return {
            "applied": amount_minor, "debt_created": 0,
            "status": "legacy_allowed_negative",
        }

    # V2 behaviour: partial debit + pending_debt
    can_absorb = max(0, available)
    debit_from_available = min(can_absorb, amount_minor)
    debt_created = amount_minor - debit_from_available

    update_inc: Dict[str, int] = {
        "available_balance_minor": -debit_from_available,
    }
    if debt_created:
        update_inc["pending_debt_minor"] = debt_created

    update_set: Dict[str, Any] = {"updated_at": now}
    new_status = wallet.get("wallet_status") or WALLET_STATUS_ACTIVE
    if debt_created > 0 or (existing_debt + debt_created) > 0:
        new_status = WALLET_STATUS_PAYOUT_STOPPED
        update_set["wallet_status"] = new_status
        update_set["payout_stopped_reason"] = (
            f"pending_debt_from_{source}: {reason[:200]}"
        )
        update_set["payout_stopped_at"] = now

    await db.merchant_wallets.update_one(
        {"organization_id": organization_id},
        {"$inc": update_inc, "$set": update_set},
    )

    logger.warning(
        "wallet_debit applied: org=%s amount=%d from_available=%d debt_created=%d status=%s source=%s",
        organization_id, amount_minor, debit_from_available, debt_created, new_status, source,
    )

    # Audit log
    try:
        await db.financial_audit_log.insert_one({
            "id": f"audit_{now}_{organization_id[:8]}",
            "organization_id": organization_id,
            "actor": "system",
            "actor_role": "system",
            "action": "wallet_debit_applied",
            "details": {
                "amount_minor": amount_minor,
                "from_available": debit_from_available,
                "debt_created": debt_created,
                "source": source,
                "source_entity_id": source_entity_id,
                "reason": reason[:500],
                "new_status": new_status,
            },
            "created_at": now,
        })
    except Exception as e:
        logger.warning("audit log insert failed: %s", e)

    return {
        "applied": debit_from_available,
        "debt_created": debt_created,
        "status": new_status,
        "total_debt": existing_debt + debt_created,
    }


async def apply_credit(
    db,
    organization_id: str,
    amount_minor: int,
    *,
    source: str = "earnings",
) -> Dict[str, Any]:
    """
    Apply a credit. If there is pending_debt, reduce it first, remainder → available.
    When debt reaches 0, auto-lift payout_stopped status.
    """
    if amount_minor <= 0:
        return {"applied_to_debt": 0, "applied_to_available": 0, "status": "noop"}

    wallet = await db.merchant_wallets.find_one({"organization_id": organization_id})
    if not wallet:
        return {"applied_to_debt": 0, "applied_to_available": amount_minor, "status": "no_wallet"}

    existing_debt = int(wallet.get("pending_debt_minor") or 0)
    now = datetime.now(timezone.utc).isoformat()

    applied_to_debt = min(existing_debt, amount_minor)
    applied_to_available = amount_minor - applied_to_debt

    update_inc: Dict[str, int] = {}
    if applied_to_debt:
        update_inc["pending_debt_minor"] = -applied_to_debt
    if applied_to_available:
        update_inc["available_balance_minor"] = applied_to_available

    update_set: Dict[str, Any] = {"updated_at": now}
    if existing_debt > 0 and applied_to_debt == existing_debt:
        # Debt cleared — unfreeze status if still payout_stopped due to debt
        current_status = wallet.get("wallet_status") or WALLET_STATUS_ACTIVE
        if current_status == WALLET_STATUS_PAYOUT_STOPPED:
            update_set["wallet_status"] = WALLET_STATUS_ACTIVE
            update_set["payout_stopped_reason"] = None
            update_set["payout_stopped_at"] = None

    await db.merchant_wallets.update_one(
        {"organization_id": organization_id},
        {"$inc": update_inc, "$set": update_set},
    )

    return {
        "applied_to_debt": applied_to_debt,
        "applied_to_available": applied_to_available,
        "status": update_set.get("wallet_status") or wallet.get("wallet_status") or WALLET_STATUS_ACTIVE,
    }


async def is_payout_eligible(db, organization_id: str) -> tuple[bool, Optional[str]]:
    """Check whether a wallet is allowed to initiate payouts."""
    wallet = await db.merchant_wallets.find_one({"organization_id": organization_id})
    if not wallet:
        return False, "no_wallet"
    status = wallet.get("wallet_status") or WALLET_STATUS_ACTIVE
    if status != WALLET_STATUS_ACTIVE:
        return False, wallet.get("payout_stopped_reason") or status
    return True, None
