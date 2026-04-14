"""
PLANN Financial Engine — Compliance & Risk Controls

KYC verification, AML checks, IBAN/sort code cooldown enforcement,
dispute reserves, and payout eligibility rules.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

IBAN_CHANGE_COOLDOWN_HOURS = int(os.getenv("IBAN_CHANGE_COOLDOWN_HOURS", "48"))
PAYOUT_MANUAL_REVIEW_THRESHOLD = int(os.getenv("PAYOUT_MANUAL_REVIEW_THRESHOLD", "5000000"))
PAYOUT_MONTHLY_AML_THRESHOLD = int(os.getenv("PAYOUT_MONTHLY_AML_THRESHOLD", "20000000"))


# ---------------------------------------------------------------------------
# KYC
# ---------------------------------------------------------------------------

async def check_kyc_status(db, organization_id: str) -> Dict[str, Any]:
    """Check KYC verification status for an organization."""
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        return {"verified": False, "reason": "settings_not_found"}

    return {
        "verified": settings.get("kyc_verified", False),
        "wise_recipient_verified": settings.get("wise_recipient_verified", False),
        "base_currency": settings.get("base_currency", "TRY"),
    }


async def set_kyc_verified(
    db,
    organization_id: str,
    verified: bool,
    actor: str,
    ip_address: Optional[str] = None,
) -> None:
    """Set KYC verification status (SuperAdmin action)."""
    await db.settings.update_one(
        {"organization_id": organization_id},
        {"$set": {"kyc_verified": verified}},
    )

    # Also sync to wallet document so SuperAdmin dashboard reads it directly
    await db.merchant_wallets.update_one(
        {"organization_id": organization_id},
        {"$set": {"kyc_verified": verified}},
    )

    await _audit_log(db, organization_id, actor, "superadmin",
                     "kyc_verified_set", {"verified": verified}, ip_address)


# ---------------------------------------------------------------------------
# IBAN / Sort Code Cooldown
# ---------------------------------------------------------------------------

async def check_bank_details_cooldown(db, organization_id: str) -> Dict[str, Any]:
    """Check if bank details change cooldown is active."""
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        return {"cooldown_active": False}

    changed_at = settings.get("iban_changed_at")
    if not changed_at:
        return {"cooldown_active": False}

    changed_dt = datetime.fromisoformat(changed_at)
    cooldown_end = changed_dt + timedelta(hours=IBAN_CHANGE_COOLDOWN_HOURS)
    now = datetime.now(timezone.utc)

    if now < cooldown_end:
        remaining = cooldown_end - now
        return {
            "cooldown_active": True,
            "cooldown_ends_at": cooldown_end.isoformat(),
            "remaining_hours": round(remaining.total_seconds() / 3600, 1),
        }

    return {"cooldown_active": False}


async def update_bank_details(
    db,
    organization_id: str,
    actor: str,
    ip_address: Optional[str] = None,
    **bank_fields,
) -> Dict[str, Any]:
    """
    Update bank details with cooldown enforcement.
    Resets wise_recipient_verified to False (re-verification needed).
    First-time IBAN entry skips cooldown.
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    has_existing_iban = bool(settings and settings.get("iban"))

    if has_existing_iban:
        cooldown = await check_bank_details_cooldown(db, organization_id)
        if cooldown["cooldown_active"]:
            return {
                "success": False,
                "error": "cooldown_active",
                "cooldown_ends_at": cooldown["cooldown_ends_at"],
                "remaining_hours": cooldown["remaining_hours"],
            }

    now = datetime.now(timezone.utc).isoformat()
    update_fields = {
        "wise_recipient_verified": False,
        "wise_recipient_id": None,
    }
    if has_existing_iban:
        update_fields["iban_changed_at"] = now

    for key in ("iban", "account_holder_name", "sort_code", "account_number"):
        if key in bank_fields and bank_fields[key] is not None:
            update_fields[key] = bank_fields[key]

    await db.settings.update_one(
        {"organization_id": organization_id},
        {"$set": update_fields},
    )

    await _audit_log(db, organization_id, actor, "admin",
                     "bank_details_updated",
                     {"fields_changed": list(bank_fields.keys())}, ip_address)

    return {"success": True, "cooldown_starts": now}


# ---------------------------------------------------------------------------
# AML Checks
# ---------------------------------------------------------------------------

async def check_aml_limits(
    db,
    organization_id: str,
    payout_amount_minor: int,
    base_currency: str,
) -> Dict[str, Any]:
    """
    Check AML thresholds for a payout request.
    - Single payout > PAYOUT_MANUAL_REVIEW_THRESHOLD → needs superadmin review
    - Monthly total > PAYOUT_MONTHLY_AML_THRESHOLD → enhanced review
    """
    flags = []

    if base_currency == "TRY" and payout_amount_minor > PAYOUT_MANUAL_REVIEW_THRESHOLD:
        flags.append("single_payout_exceeds_review_threshold")

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pipeline = [
        {"$match": {
            "organization_id": organization_id,
            "type": "payout",
            "state": {"$in": ["reserved", "paid_out"]},
            "created_at": {"$gte": month_start.isoformat()},
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$amount_display_minor"},
        }},
    ]

    monthly_result = await db.merchant_transactions.aggregate(pipeline).to_list(length=1)
    monthly_total = monthly_result[0]["total"] if monthly_result else 0

    if base_currency == "TRY" and (monthly_total + payout_amount_minor) > PAYOUT_MONTHLY_AML_THRESHOLD:
        flags.append("monthly_total_exceeds_aml_threshold")

    return {
        "approved": len(flags) == 0,
        "flags": flags,
        "monthly_total_minor": monthly_total,
        "payout_amount_minor": payout_amount_minor,
        "needs_superadmin_review": len(flags) > 0,
    }


# ---------------------------------------------------------------------------
# Dispute & Refund Reserves
# ---------------------------------------------------------------------------

async def update_refund_reserve(db, organization_id: str) -> int:
    """
    Calculate and update refund reserve based on active refund windows.
    Returns the new refund_reserve_minor value.
    """
    is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"

    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        return 0

    refund_window_hours = 0 if is_sandbox else settings.get("refund_window_hours", 12)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=refund_window_hours)

    pipeline = [
        {"$match": {
            "organization_id": organization_id,
            "state": {"$in": ["captured", "settled", "available"]},
            "created_at": {"$gte": cutoff.isoformat()},
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$amount_display_minor"},
        }},
    ]

    result = await db.merchant_transactions.aggregate(pipeline).to_list(length=1)
    reserve = result[0]["total"] if result else 0

    await db.merchant_wallets.update_one(
        {"organization_id": organization_id},
        {"$set": {
            "refund_reserve_minor": reserve,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return reserve


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

async def _audit_log(
    db,
    organization_id: str,
    actor: str,
    actor_role: str,
    action: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None,
) -> None:
    """Write a financial audit log entry."""
    import uuid
    await db.financial_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "details": details,
        "ip_address": ip_address,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
