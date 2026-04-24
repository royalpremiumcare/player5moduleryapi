"""
Refund Requests — admin-approved refund workflow.

Flow:
  1. Merchant creates a refund_request (pending + priority + SLA deadline)
  2. SuperAdmin reviews:
     - approve → Stripe refund call → reconciliation pipeline
     - reject  → reason recorded
  3. SLA monitor cron escalates overdue requests

See plan Bölüm 4 + 14.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLA thresholds (hours) — plan Bölüm 14.2
# ---------------------------------------------------------------------------

SLA_HOURS = {
    "urgent": 1,
    "high": 4,
    "normal": 12,
}

ESCALATION_SLA_MULT = {
    # hours at which to trigger warning/yellow
    "warn": 1.0,
    # hours at which to escalate red
    "red": 4.0,
}

# Abuse protection
URGENT_DAILY_QUOTA_PER_ORG = 2


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _sla_deadline_iso(priority: str, created_at: datetime) -> str:
    hours = SLA_HOURS.get(priority, SLA_HOURS["normal"])
    return (created_at + timedelta(hours=hours)).isoformat()


async def _count_urgent_today(db, organization_id: str) -> int:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return await db.refund_requests.count_documents({
        "organization_id": organization_id,
        "priority": "urgent",
        "created_at": {"$gte": today_start},
    })


# ---------------------------------------------------------------------------
# Merchant-facing operations
# ---------------------------------------------------------------------------

async def create_refund_request(
    db,
    *,
    organization_id: str,
    requested_by_user_id: str,
    merchant_transaction_id: str,
    refund_amount_minor: int,
    reason: str,
    appointment_ids: Optional[List[str]] = None,
    priority: str = "normal",
    customer_waiting: bool = False,
    note: str = "",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merchant creates a new refund request.
    Raises ValueError for invalid inputs.
    """
    if refund_amount_minor <= 0:
        raise ValueError("refund_amount must be positive")
    if not reason or len(reason.strip()) < 3:
        raise ValueError("reason is required (min 3 chars)")
    if priority not in SLA_HOURS:
        raise ValueError(f"invalid priority: {priority}")

    # Early idempotency check: if a doc with the same key already exists, return it
    # without re-running duplicate-request or fully-refunded guards (retries must be
    # safely no-op).
    if idempotency_key:
        prior = await db.refund_requests.find_one(
            {"idempotency_key": idempotency_key}, {"_id": 0},
        )
        if prior:
            return prior

    # Load underlying transaction for customer info + validation
    tx = await db.merchant_transactions.find_one({
        "id": merchant_transaction_id,
        "organization_id": organization_id,
    })
    if not tx:
        raise ValueError(f"merchant_transaction not found: {merchant_transaction_id}")

    # Guard: cannot refund a transaction that's already fully refunded
    original_amount = int(tx.get("amount_display_minor") or 0)
    already_refunded = int(tx.get("refunded_amount_minor") or 0)
    if tx.get("state") == "refunded" or already_refunded >= original_amount:
        raise ValueError("Bu işlem zaten tamamen iade edilmiş.")
    remaining = original_amount - already_refunded
    if refund_amount_minor > remaining:
        raise ValueError(
            f"İade tutarı bu işlemin kalan iade edilebilir tutarını aşıyor "
            f"(kalan: {remaining / 100:.2f}, talep edilen: {refund_amount_minor / 100:.2f})."
        )

    # Guard: block if there's already a pending/approved (not yet executed) request for this tx
    existing_open = await db.refund_requests.find_one({
        "merchant_transaction_id": merchant_transaction_id,
        "organization_id": organization_id,
        "status": {"$in": ["pending", "approved"]},
    }, {"_id": 0, "id": 1, "status": 1})
    if existing_open:
        raise ValueError(
            f"Bu işlem için zaten bekleyen bir iade talebi var "
            f"(durum: {existing_open['status']})."
        )

    # Abuse protection: downgrade urgent if quota exceeded
    effective_priority = priority
    if priority == "urgent":
        used = await _count_urgent_today(db, organization_id)
        if used >= URGENT_DAILY_QUOTA_PER_ORG:
            effective_priority = "high"
            logger.warning(
                "refund_request: urgent quota exceeded for org=%s, downgraded to high",
                organization_id,
            )

    now = datetime.now(timezone.utc)
    req_id = str(uuid.uuid4())
    # Default idempotency key encodes (org, tx, amount, date, retry-count).
    # retry-count = number of rejected/failed attempts for the same tx, so a
    # resubmission after a rejection generates a new key (and thus a new row)
    # while an accidental double-submit in the same moment still collapses
    # onto the open pending request via the unique index.
    if idempotency_key:
        idem = idempotency_key
    else:
        rejected_count = await db.refund_requests.count_documents({
            "organization_id": organization_id,
            "merchant_transaction_id": merchant_transaction_id,
            "status": {"$in": ["rejected", "failed"]},
        })
        suffix = f":retry{rejected_count}" if rejected_count else ""
        idem = (
            f"refund_req:{organization_id}:{merchant_transaction_id}:"
            f"{refund_amount_minor}:{now.date()}{suffix}"
        )

    doc = {
        "id": req_id,
        "organization_id": organization_id,
        "requested_by_user_id": requested_by_user_id,
        "appointment_ids": appointment_ids or [],
        "merchant_transaction_id": merchant_transaction_id,
        "stripe_payment_intent_id": tx.get("stripe_payment_intent_id"),
        "base_currency": tx.get("base_currency", "TRY"),
        "refund_amount_minor": int(refund_amount_minor),
        "reason": reason.strip()[:1000],
        "note": (note or "")[:2000],
        "customer_name": tx.get("customer_name"),
        "customer_phone": tx.get("customer_phone"),
        "priority": effective_priority,
        "priority_requested": priority,  # what merchant originally asked
        "customer_waiting": bool(customer_waiting),
        "sla_deadline": _sla_deadline_iso(effective_priority, now),
        "escalated": False,
        "escalated_at": None,
        "age_hours_at_review": None,
        "status": "pending",
        "idempotency_key": idem,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "stripe_refund_id": None,
        "reconciliation_id": None,
    }

    try:
        await db.refund_requests.insert_one(doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            existing = await db.refund_requests.find_one(
                {"idempotency_key": idem}, {"_id": 0},
            )
            return existing or {k: v for k, v in doc.items() if k != "_id"}
        raise

    logger.info(
        "refund_request created: id=%s org=%s tx=%s amount=%d priority=%s",
        req_id, organization_id, merchant_transaction_id, refund_amount_minor, effective_priority,
    )
    doc.pop("_id", None)

    # Notify SuperAdmin (fire-and-forget, non-blocking)
    try:
        await _notify_superadmin_new_refund_request(db, doc)
    except Exception as e:
        logger.warning("superadmin refund notification failed (non-blocking): %s", e)

    return doc


async def list_org_refund_requests(
    db, organization_id: str, status: Optional[str] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"organization_id": organization_id}
    if status:
        query["status"] = status
    cursor = db.refund_requests.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)


# ---------------------------------------------------------------------------
# SuperAdmin operations
# ---------------------------------------------------------------------------

async def _enrich_refund_rows(db, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach organization_name + customer_name to each refund_request row."""
    if not items:
        return items

    org_ids = list({it.get("organization_id") for it in items if it.get("organization_id")})
    tx_ids = list({it.get("merchant_transaction_id") for it in items if it.get("merchant_transaction_id")})

    # Fetch org names in one pass
    org_name_by_id: Dict[str, str] = {}
    if org_ids:
        async for s in db.settings.find(
            {"organization_id": {"$in": org_ids}},
            {"_id": 0, "organization_id": 1, "company_name": 1, "business_name": 1},
        ):
            org_name_by_id[s["organization_id"]] = (
                s.get("company_name") or s.get("business_name") or s["organization_id"]
            )

    # Fetch customer names from the underlying transactions
    cust_by_tx: Dict[str, Dict[str, Any]] = {}
    if tx_ids:
        async for tx in db.merchant_transactions.find(
            {"id": {"$in": tx_ids}},
            {"_id": 0, "id": 1, "customer_name": 1, "customer_phone": 1},
        ):
            cust_by_tx[tx["id"]] = tx

    for it in items:
        it["organization_name"] = org_name_by_id.get(
            it.get("organization_id", ""), it.get("organization_id", "")
        )
        tx = cust_by_tx.get(it.get("merchant_transaction_id") or "", {})
        it["customer_name"] = tx.get("customer_name") or "-"
        it["customer_phone"] = tx.get("customer_phone") or ""
    return items


async def list_pending_for_admin(db, limit: int = 100) -> List[Dict[str, Any]]:
    """Pending refund requests for SuperAdmin — sorted by SLA deadline (most urgent first)."""
    cursor = (
        db.refund_requests
        .find({"status": "pending"}, {"_id": 0})
        .sort("sla_deadline", 1)
        .limit(limit)
    )
    items = await cursor.to_list(limit)
    return await _enrich_refund_rows(db, items)


async def list_completed_for_admin(
    db, *, status: Optional[str] = None, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Non-pending refund requests (executed / rejected / failed) for the history
    panel — sorted newest-first. `status` can narrow the filter; otherwise all
    terminal states are returned.
    """
    if status:
        q = {"status": status}
    else:
        q = {"status": {"$in": ["executed", "rejected", "failed"]}}
    cursor = (
        db.refund_requests
        .find(q, {"_id": 0})
        .sort("updated_at", -1)
        .limit(limit)
    )
    items = await cursor.to_list(limit)
    return await _enrich_refund_rows(db, items)


async def approve_refund_request(
    db,
    *,
    request_id: str,
    reviewer_id: str,
    stripe_refund_call,  # callable: (stripe_payment_intent_id, amount_minor) -> refund_id (sync or coroutine)
) -> Dict[str, Any]:
    """
    Approve a refund request:
      1. Transition status pending → approved
      2. Call Stripe refund
      3. Mark executed with stripe_refund_id

    `stripe_refund_call` is injected so the core logic stays unit-testable.
    """
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    req = await db.refund_requests.find_one({"id": request_id, "status": "pending"})
    if not req:
        return {"ok": False, "error": "not_found_or_not_pending"}

    # Compute how long we took to review
    created_at = datetime.fromisoformat(req["created_at"].replace("Z", "+00:00"))
    age_hours = (now_dt - created_at).total_seconds() / 3600.0

    await db.refund_requests.update_one(
        {"id": request_id, "status": "pending"},
        {"$set": {
            "status": "approved",
            "reviewed_by": reviewer_id,
            "reviewed_at": now,
            "age_hours_at_review": round(age_hours, 2),
            "updated_at": now,
        }},
    )

    # Call Stripe
    try:
        result = stripe_refund_call(
            req.get("stripe_payment_intent_id"),
            int(req["refund_amount_minor"]),
        )
        # Allow coroutine or dict
        if hasattr(result, "__await__"):
            result = await result
        refund_id = (
            result.get("id") if isinstance(result, dict) else getattr(result, "id", str(result))
        )
    except Exception as e:
        logger.exception("Stripe refund call failed for request %s: %s", request_id, e)
        await db.refund_requests.update_one(
            {"id": request_id},
            {"$set": {
                "status": "failed",
                "rejection_reason": f"stripe_call_failed: {str(e)[:500]}",
                "updated_at": now,
            }},
        )
        return {"ok": False, "error": "stripe_refund_failed", "detail": str(e)}

    # Ledger update: write refund tx + mark original payment as refunded + debit wallet
    try:
        await _apply_refund_to_ledger(db, req, refund_id)
    except Exception as e:
        logger.error(
            "refund_request %s: Stripe refund succeeded but ledger update failed — "
            "reconciliation_pending flagged. stripe_refund_id=%s err=%s",
            request_id, refund_id, e, exc_info=True,
        )
        # Continue so status is marked executed — reconciliation cron will repair.
        await db.refund_reconciliation_pending.insert_one({
            "id": str(uuid.uuid4()),
            "refund_request_id": request_id,
            "stripe_refund_id": refund_id,
            "merchant_transaction_id": req.get("merchant_transaction_id"),
            "organization_id": req.get("organization_id"),
            "refund_amount_minor": int(req["refund_amount_minor"]),
            "error": str(e)[:500],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    await db.refund_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "executed",
            "stripe_refund_id": refund_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    logger.info(
        "refund_request approved+executed: id=%s reviewer=%s stripe_refund_id=%s",
        request_id, reviewer_id, refund_id,
    )

    # Notification (non-blocking)
    try:
        await _notify_refund_outcome(db, req, approved=True)
    except Exception as e:
        logger.warning("refund_approved notification failed (non-blocking): %s", e)

    return {"ok": True, "stripe_refund_id": refund_id, "status": "executed"}


async def reject_refund_request(
    db, *, request_id: str, reviewer_id: str, reason: str
) -> Dict[str, Any]:
    if not reason or len(reason.strip()) < 3:
        return {"ok": False, "error": "reason_required"}
    now = datetime.now(timezone.utc).isoformat()
    res = await db.refund_requests.update_one(
        {"id": request_id, "status": "pending"},
        {"$set": {
            "status": "rejected",
            "reviewed_by": reviewer_id,
            "reviewed_at": now,
            "rejection_reason": reason.strip()[:1000],
            "updated_at": now,
        }},
    )
    if res.modified_count == 0:
        return {"ok": False, "error": "not_found_or_not_pending"}
    logger.info("refund_request rejected: id=%s reviewer=%s", request_id, reviewer_id)

    # Notification (non-blocking)
    try:
        req = await db.refund_requests.find_one({"id": request_id})
        if req:
            await _notify_refund_outcome(db, req, approved=False, rejection_reason=reason)
    except Exception as e:
        logger.warning("refund_rejected notification failed (non-blocking): %s", e)

    return {"ok": True, "status": "rejected"}


# ---------------------------------------------------------------------------
# Ledger helper — writes refund tx + updates parent tx + debits wallet pending
# ---------------------------------------------------------------------------

async def _apply_refund_to_ledger(
    db, req: Dict[str, Any], stripe_refund_id: str,
) -> None:
    """
    Atomically record refund in merchant ledger after Stripe refund succeeds:
      1. Insert a new merchant_transactions row (type=refund, negative amount)
      2. Mark the original payment tx as refunded (partial tracked via refunded_amount_minor)
      3. Debit the wallet pending_balance_minor (since the funds will not arrive)

    Idempotent via unique-ish stripe_refund_id check.
    """
    now = datetime.now(timezone.utc).isoformat()
    org_id = req["organization_id"]
    parent_tx_id = req["merchant_transaction_id"]
    amount = int(req["refund_amount_minor"])
    currency = req.get("base_currency", "TRY")

    # Idempotency: skip if already recorded
    existing = await db.merchant_transactions.find_one(
        {"stripe_refund_id": stripe_refund_id, "type": "refund"},
        {"_id": 0, "id": 1},
    )
    if existing:
        logger.info(
            "refund ledger already applied (idempotent): refund_id=%s tx=%s",
            stripe_refund_id, existing["id"],
        )
        return

    # 1) Insert refund tx (negative amount, type=refund, state=captured).
    # NOTE: We do NOT set stripe_payment_intent_id on the refund row because the
    # merchant_transactions collection has a unique index on that field; the
    # original payment tx already owns it. We link back via parent_transaction_id.
    refund_tx = {
        "id": str(uuid.uuid4()),
        "organization_id": org_id,
        "type": "refund",
        "state": "captured",
        "base_currency": currency,
        "amount_display_minor": -amount,
        "parent_transaction_id": parent_tx_id,
        "parent_stripe_payment_intent_id": req.get("stripe_payment_intent_id"),
        "stripe_refund_id": stripe_refund_id,
        "customer_name": req.get("customer_name"),
        "customer_phone": req.get("customer_phone"),
        "reason": req.get("reason", "")[:500],
        "refund_request_id": req.get("id"),
        "created_at": now,
        "updated_at": now,
    }
    await db.merchant_transactions.insert_one(refund_tx)

    # 2) Update parent payment tx with refund tracking
    parent = await db.merchant_transactions.find_one(
        {"id": parent_tx_id, "organization_id": org_id},
        {"_id": 0, "amount_display_minor": 1, "refunded_amount_minor": 1, "state": 1},
    )
    if parent:
        new_refunded = int(parent.get("refunded_amount_minor") or 0) + amount
        full_refund = new_refunded >= int(parent.get("amount_display_minor") or 0)
        parent_update = {
            "refunded_amount_minor": new_refunded,
            "last_refund_id": stripe_refund_id,
            "updated_at": now,
        }
        if full_refund:
            parent_update["state"] = "refunded"
        await db.merchant_transactions.update_one(
            {"id": parent_tx_id, "organization_id": org_id},
            {"$set": parent_update},
        )

    # 3) Debit wallet pending_balance + total_earned (funds won't arrive — reverse the pending)
    await db.merchant_wallets.update_one(
        {"organization_id": org_id},
        {"$inc": {
            "pending_balance_minor": -amount,
            "total_earned_minor": -amount,
            "total_refunded_minor": amount,
        },
         "$set": {"updated_at": now}},
    )

    logger.info(
        "refund ledger applied: org=%s parent_tx=%s refund_tx=%s amount=%d stripe_refund=%s",
        org_id, parent_tx_id, refund_tx["id"], amount, stripe_refund_id,
    )


# ---------------------------------------------------------------------------
# Notification helper (non-blocking)
# ---------------------------------------------------------------------------

async def _notify_refund_outcome(
    db, req_doc: Dict[str, Any], *, approved: bool, rejection_reason: str = "",
) -> None:
    """Fire-and-forget email to merchant about refund request outcome."""
    import asyncio

    try:
        from .notifications_v2 import (
            send_refund_approved_email, send_refund_rejected_email, send_slack,
        )
    except Exception:
        return  # notification module optional

    org_id = req_doc.get("organization_id", "")
    admin_user = await db.users.find_one({"organization_id": org_id, "role": "admin"}, {"_id": 0})
    if not admin_user:
        return
    to_email = admin_user.get("username") or admin_user.get("email")
    if not to_email:
        return
    settings = await db.settings.find_one({"organization_id": org_id}) or {}
    merchant_name = settings.get("company_name", "İşletme")
    currency = req_doc.get("base_currency", "TRY")
    amount = int(req_doc.get("refund_amount_minor") or 0)

    if approved:
        await asyncio.to_thread(
            send_refund_approved_email,
            to_email, merchant_name, amount, currency, req_doc.get("reason", ""),
        )
        send_slack(
            f":white_check_mark: İade onaylandı: {merchant_name}",
            fields={
                "Tutar (minor)": amount,
                "Para birimi": currency,
                "Talep ID": req_doc.get("id"),
            },
        )
    else:
        await asyncio.to_thread(
            send_refund_rejected_email,
            to_email, merchant_name, amount, currency,
            rejection_reason or req_doc.get("rejection_reason") or "(sebep yok)",
        )
        send_slack(
            f":x: İade reddedildi: {merchant_name}",
            fields={
                "Tutar (minor)": amount,
                "Para birimi": currency,
                "Talep ID": req_doc.get("id"),
                "Red sebebi": (rejection_reason or req_doc.get("rejection_reason") or "-")[:200],
            },
        )


# ---------------------------------------------------------------------------
# SuperAdmin notification on new refund_request
# ---------------------------------------------------------------------------

SUPERADMIN_ALERT_EMAIL = "fatihsenyuz12@gmail.com"


async def _notify_superadmin_new_refund_request(db, req_doc: Dict[str, Any]) -> None:
    """Fire-and-forget email + Slack to SuperAdmin when a merchant files a refund."""
    import asyncio

    try:
        from .notifications_v2 import send_slack
    except Exception:
        return

    org_id = req_doc.get("organization_id") or ""
    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    merchant_name = (
        settings.get("company_name") or settings.get("business_name") or org_id
    )
    currency = req_doc.get("base_currency", "TRY")
    amount = int(req_doc.get("refund_amount_minor") or 0)
    priority = req_doc.get("priority", "normal")
    priority_tr = {"urgent": "Acil", "high": "Yüksek", "normal": "Normal"}.get(priority, priority)
    request_id = req_doc.get("id", "")

    # Slack alert (critical if urgent)
    send_slack(
        f":warning: Yeni iade talebi: {merchant_name} ({priority_tr})",
        critical=(priority == "urgent"),
        fields={
            "İşletme": merchant_name,
            "Tutar (minor)": amount,
            "Para birimi": currency,
            "Öncelik": priority_tr,
            "Müşteri bekliyor": "Evet" if req_doc.get("customer_waiting") else "Hayır",
            "Sebep": (req_doc.get("reason") or "-")[:200],
            "Talep ID": request_id,
        },
    )

    # Email to SuperAdmin
    try:
        from .email_notifications import _send_email  # type: ignore
    except Exception:
        try:
            from .notifications_v2 import _send_email  # type: ignore
        except Exception:
            return

    from .money import format_display
    amount_display = format_display(amount, currency)
    subject = f"[PLANN] Yeni İade Talebi — {merchant_name} ({amount_display})"
    customer_waiting_tr = "Evet" if req_doc.get("customer_waiting") else "Hayır"
    body = f"""
<p>Yeni bir iade talebi incelemeye alınmak üzere gönderildi.</p>
<table style="border-collapse:collapse;font-size:14px">
  <tr><td style="padding:4px 12px"><strong>İşletme</strong></td><td>{merchant_name}</td></tr>
  <tr><td style="padding:4px 12px"><strong>Tutar</strong></td><td>{amount_display}</td></tr>
  <tr><td style="padding:4px 12px"><strong>Öncelik</strong></td><td>{priority_tr}</td></tr>
  <tr><td style="padding:4px 12px"><strong>Müşteri bekliyor</strong></td><td>{customer_waiting_tr}</td></tr>
  <tr><td style="padding:4px 12px"><strong>Sebep</strong></td><td>{(req_doc.get('reason') or '-')[:500]}</td></tr>
  <tr><td style="padding:4px 12px"><strong>Talep ID</strong></td><td><code>{request_id}</code></td></tr>
</table>
<p style="margin-top:16px">
  <a href="https://plannapp.co/superadmin/financial-v2"
     style="background:#111;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none">
    SuperAdmin Panelinde Aç
  </a>
</p>
<hr><p style="color:#888">New refund request — please review in the SuperAdmin panel.</p>
"""
    try:
        await asyncio.to_thread(
            _send_email, SUPERADMIN_ALERT_EMAIL, "PLANN SuperAdmin", subject, body,
        )
    except Exception as e:
        logger.warning("superadmin refund email failed: %s", e)


# ---------------------------------------------------------------------------
# SLA Monitor
# ---------------------------------------------------------------------------

async def run_sla_monitor_cron(db) -> Dict[str, Any]:
    """
    Called every 15 minutes.
    Finds pending requests whose sla_deadline has passed and marks them escalated.
    Triggers SuperAdmin alerts (caller wires email/Slack hooks via return value).
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    overdue_cursor = db.refund_requests.find({
        "status": "pending",
        "escalated": {"$ne": True},
        "sla_deadline": {"$lt": now_iso},
    }).limit(200)

    escalations: List[Dict[str, Any]] = []
    async for req in overdue_cursor:
        await db.refund_requests.update_one(
            {"id": req["id"]},
            {"$set": {
                "escalated": True,
                "escalated_at": now_iso,
                "updated_at": now_iso,
            }},
        )
        escalations.append({
            "id": req["id"],
            "organization_id": req["organization_id"],
            "priority": req["priority"],
            "sla_deadline": req["sla_deadline"],
            "age_hours": round(
                (now - datetime.fromisoformat(req["created_at"].replace("Z", "+00:00")))
                .total_seconds() / 3600.0, 2
            ),
        })

    if escalations:
        logger.error(
            "refund_sla_monitor: escalated=%d first=%s",
            len(escalations),
            escalations[0],
        )
        # Slack alert (critical if 2x+ SLA passed)
        try:
            from .notifications_v2 import send_slack
            for esc in escalations[:5]:  # first 5 in one message
                critical = (esc.get("age_hours") or 0) >= (2 * SLA_HOURS.get(esc.get("priority") or "normal", 12))
                priority_tr = {"urgent": "Acil", "high": "Yüksek", "normal": "Normal"}.get(
                    esc.get("priority") or "normal", esc.get("priority") or "normal"
                )
                send_slack(
                    f":hourglass_flowing_sand: İade SLA aşıldı: {esc['id'][:8]} ({priority_tr})",
                    critical=critical,
                    fields={
                        "Org ID": esc["organization_id"],
                        "Bekleme süresi (saat)": esc["age_hours"],
                        "SLA tarihi": esc["sla_deadline"],
                    },
                )
        except Exception as e:
            logger.warning("SLA Slack alert failed (non-blocking): %s", e)

    return {"escalated": len(escalations), "items": escalations}


# ---------------------------------------------------------------------------
# Customer search (merchant refund modal)
# ---------------------------------------------------------------------------

async def search_customer_payments(
    db,
    *,
    organization_id: str,
    query: str,
    by: str = "name",  # name | phone | amount | date
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """
    Search merchant's customer payments for the refund request modal.
    Returns matching merchant_transactions with customer metadata.
    """
    # Only include payments that are refundable: captured/paid/settled/available and
    # not already fully refunded. Exclude pending/failed/refunded/canceled states so
    # the merchant can't accidentally open a second refund on a reversed payment.
    q: Dict[str, Any] = {
        "organization_id": organization_id,
        "type": "payment",
        "state": {"$in": ["captured", "paid", "settled", "available", "reserved"]},
    }
    if by == "name" and query:
        q["customer_name"] = {"$regex": query[:80], "$options": "i"}
    elif by == "phone" and query:
        q["customer_phone"] = {"$regex": query[:30].replace("+", r"\+"), "$options": "i"}
    elif by == "amount" and query:
        try:
            amt = int(float(query) * 100)
            q["amount_display_minor"] = amt
        except ValueError:
            return []
    elif by == "date" and query:
        # Expect YYYY-MM-DD
        q["created_at"] = {"$regex": f"^{query[:10]}"}

    cursor = db.merchant_transactions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)
