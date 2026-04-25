"""
Stripe iade başarılı; iç DB/state güncellemesi başarısız kaldığında `refund_reconciliation_pending` kuyruğu.

Kilitle → yeniden dene → resolved / retry_count + next_retry_at.
Cron ve superadmin POST aynı `resolve_refund_reconciliation_by_id` yolunu kullanır.

Yetkili kaynak (kısmi iade): Her `stripe_refund_id` için en fazla bir `type: refund` child satırı doğruluğu taşır
(sparse unique index); child varsa merchant tarafı tamamdır ve duplicate insert’te cüzdan tekrar düşmez,
child yoksa `partial_refund_total_minor` ile `snapshot_prev_partial_minor + refund_amount_minor` eşlemesi
eksik adımı deterministik seçer.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from financial.state_machine import StateMachine

logger = logging.getLogger(__name__)

STALE_LOCK_MINUTES = 15
MAX_AUTO_RETRIES = 40
BACKOFF_CAP_SECONDS = 86400


def _backoff_seconds(retry_count: int) -> int:
    base = min(60 * (2 ** min(retry_count, 10)), BACKOFF_CAP_SECONDS)
    return max(30, base)


async def try_acquire_reconciliation_lock(db, doc_id: str, locked_by: str) -> Optional[Dict[str, Any]]:
    """pending + kilit yok veya eski kilit → atomik kilitle."""
    now = datetime.now(timezone.utc)
    stale_before = (now - timedelta(minutes=STALE_LOCK_MINUTES)).isoformat()
    doc = await db.refund_reconciliation_pending.find_one_and_update(
        {
            "id": doc_id,
            "status": "pending",
            "$or": [
                {"locked_at": None},
                {"locked_at": {"$exists": False}},
                {"locked_at": {"$lt": stale_before}},
            ],
        },
        {"$set": {"locked_by": locked_by, "locked_at": now.isoformat()}},
        return_document=ReturnDocument.AFTER,
    )
    return doc


async def _mark_resolved(db, doc_id: str, note: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.refund_reconciliation_pending.update_one(
        {"id": doc_id},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": now,
                "resolution_note": note[:2000] if note else "applied",
                "locked_by": None,
                "locked_at": None,
                "next_retry_at": None,
            }
        },
    )


async def _mark_retry_or_fail(db, doc: Dict[str, Any], error: str) -> Dict[str, Any]:
    """Kilidi bırak, retry_count artır, next_retry_at ayarla; üst sınımda failed."""
    doc_id = doc["id"]
    retry = int(doc.get("retry_count") or 0) + 1
    now = datetime.now(timezone.utc)
    err_short = str(error)[:2000]

    if retry >= MAX_AUTO_RETRIES:
        await db.refund_reconciliation_pending.update_one(
            {"id": doc_id},
            {
                "$set": {
                    "status": "failed",
                    "failed_at": now.isoformat(),
                    "last_resolution_error": err_short,
                    "locked_by": None,
                    "locked_at": None,
                    "retry_count": retry,
                    "next_retry_at": None,
                }
            },
        )
        logger.info(
            "refund_reconciliation: give_up reconciliation_id=%s failed_step=%s retry_count=%s stripe_refund_id=%s error=%s",
            doc_id,
            doc.get("failed_step"),
            retry,
            doc.get("stripe_refund_id"),
            err_short[:500],
        )
        return {
            "ok": False,
            "status": "failed",
            "retry_count": retry,
            "error": err_short,
            "failed_step": doc.get("failed_step"),
        }

    nxt = now + timedelta(seconds=_backoff_seconds(retry - 1))
    await db.refund_reconciliation_pending.update_one(
        {"id": doc_id},
        {
            "$set": {
                "retry_count": retry,
                "next_retry_at": nxt.isoformat(),
                "last_resolution_error": err_short,
                "locked_by": None,
                "locked_at": None,
            }
        },
    )
    logger.info(
        "refund_reconciliation: retry_scheduled reconciliation_id=%s failed_step=%s retry_count=%s next_retry_at=%s stripe_refund_id=%s error=%s",
        doc_id,
        doc.get("failed_step"),
        retry,
        nxt.isoformat(),
        doc.get("stripe_refund_id"),
        err_short[:500],
    )
    return {
        "ok": False,
        "status": "retry_scheduled",
        "retry_count": retry,
        "next_retry_at": nxt.isoformat(),
        "error": err_short,
        "failed_step": doc.get("failed_step"),
    }


async def _apply_appointments_cancel_and_quota(
    db,
    *,
    organization_id: str,
    appointment_ids: List[str],
    session_group_id: str,
) -> None:
    k = len(appointment_ids)
    await db.appointments.update_many(
        {"id": {"$in": appointment_ids}, "organization_id": organization_id},
        {"$set": {"status": "İptal Edildi", "payment_status": "refunded"}},
    )
    try:
        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {"$inc": {"quota_usage": -k}},
        )
    except Exception as qe:
        logger.warning(f"quota adjust on reconciliation: {qe}")


async def _finalize_side_effects(
    organization_id: str,
    session_group_id: str,
    appointment_ids: List[str],
    request: Any,
) -> None:
    """Opsiyonel cache + socket (request varsa)."""
    try:
        from cache import invalidate_cache, get_cache_key

        if request is not None and hasattr(request, "app"):
            redis_client = getattr(request.app.state, "redis_client", None)
            if redis_client:
                for prefix in ("dashboard_stats", "customers_list"):
                    key = get_cache_key(prefix, organization_id)
                    try:
                        await redis_client.delete(key)
                        keys = await redis_client.keys(f"{key}*")
                        if keys:
                            await redis_client.delete(*keys)
                    except Exception as ce:
                        logger.warning(f"reconciliation cache delete {prefix}: {ce}")
    except Exception as e:
        logger.warning(f"reconciliation cache path: {e}")

    try:
        from server import emit_to_organization

        await emit_to_organization(
            organization_id,
            "appointments_bulk_updated",
            {
                "session_group_id": session_group_id,
                "cancelled": len(appointment_ids),
                "appointment_ids": appointment_ids,
                "source": "refund_reconciliation",
            },
        )
    except Exception as e:
        logger.warning(f"reconciliation emit: {e}")


async def _apply_internal_state(db, doc: Dict[str, Any]) -> None:
    """Stripe iade zaten yapılmış; iç state'i tamamla (retry)."""
    org_id = doc["organization_id"]
    failed_step = doc["failed_step"]
    ids = list(doc["appointment_ids"])
    group_id = doc["session_group_id"]
    tx_id = doc["merchant_transaction_id"]
    refund_amt = int(doc["refund_amount_minor"])
    stripe_refund_id = doc["stripe_refund_id"]
    is_full = bool(doc.get("is_full_refund"))

    txn = await db.merchant_transactions.find_one({"id": tx_id})
    if not txn:
        raise RuntimeError(f"merchant_transaction not found: {tx_id}")

    if failed_step == "state_machine":
        if not is_full:
            raise RuntimeError("state_machine failed_step with is_full_refund=False")
        st = txn.get("state")
        if st != "refunded":
            sm = StateMachine(db)
            await sm.transition(
                tx_id=tx_id,
                new_state="refunded",
                trigger="cancel_selected_refund_reconcile",
                metadata={
                    "stripe_refund_id": stripe_refund_id,
                    "refund_amount_minor": refund_amt,
                    "appointment_ids": ids,
                    "reconciliation_id": doc["id"],
                },
            )
        await _apply_appointments_cancel_and_quota(
            db, organization_id=org_id, appointment_ids=ids, session_group_id=group_id
        )
        return

    if failed_step == "appointments_cancel":
        await _apply_appointments_cancel_and_quota(
            db, organization_id=org_id, appointment_ids=ids, session_group_id=group_id
        )
        return

    if failed_step == "partial_merchant_updates":
        await _retry_partial_merchant(db, doc, txn)
        await _apply_appointments_cancel_and_quota(
            db, organization_id=org_id, appointment_ids=ids, session_group_id=group_id
        )
        return

    raise RuntimeError(f"unknown failed_step: {failed_step}")


async def _retry_partial_merchant(db, doc: Dict[str, Any], txn: Dict[str, Any]) -> None:
    """Kısmi iade (modül docstring’deki yetkili kaynak kuralına göre dallanır)."""
    org_id = doc["organization_id"]
    stripe_refund_id = doc["stripe_refund_id"]
    refund_amt = int(doc["refund_amount_minor"])
    snap = doc.get("snapshot_prev_partial_minor")
    if snap is None:
        snap = int(txn.get("partial_refund_total_minor") or 0)

    child = await db.merchant_transactions.find_one(
        {"organization_id": org_id, "stripe_refund_id": stripe_refund_id, "type": "refund"}
    )
    if child:
        return

    target_partial = snap + refund_amt
    cur = int(txn.get("partial_refund_total_minor") or 0)
    now_iso = datetime.now(timezone.utc).isoformat()
    tx_id = txn["id"]

    if cur < target_partial:
        await db.merchant_transactions.update_one(
            {"id": tx_id},
            {
                "$set": {"partial_refund_total_minor": target_partial, "updated_at": now_iso},
                "$push": {"state_history": {
                    "state": "partial_refund",
                    "timestamp": now_iso,
                    "trigger": "cancel_selected_partial_reconcile",
                    "refund_amount_minor": refund_amt,
                    "stripe_refund_id": stripe_refund_id,
                    "appointment_ids": doc["appointment_ids"],
                }},
            },
        )
        refund_tx_doc = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "base_currency": txn.get("base_currency", "TRY"),
            "type": "refund",
            "state": "refunded",
            "amount_display_minor": refund_amt,
            "fee_amount_minor": 0,
            "stripe_refund_id": stripe_refund_id,
            "stripe_payment_intent_id": txn.get("stripe_payment_intent_id"),
            "session_group_id": doc["session_group_id"],
            "parent_transaction_id": tx_id,
            "customer_name": txn.get("customer_name"),
            "customer_phone": txn.get("customer_phone"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "state_history": [{"state": "refunded", "timestamp": now_iso, "trigger": "cancel_selected_partial_reconcile"}],
        }
        try:
            await db.merchant_transactions.insert_one(refund_tx_doc)
        except DuplicateKeyError:
            logger.info("partial reconciliation: child duplicate (ilk dal)")
            return
        await db.merchant_wallets.update_one(
            {"organization_id": org_id},
            {"$inc": {"available_balance_minor": -refund_amt, "total_refunded_minor": refund_amt}, "$set": {"updated_at": now_iso}},
        )
        return

    # Parent tutar güncellenmiş, child yok: yalnızca child + cüzdan
    refund_tx_doc = {
        "id": str(uuid.uuid4()),
        "organization_id": org_id,
        "base_currency": txn.get("base_currency", "TRY"),
        "type": "refund",
        "state": "refunded",
        "amount_display_minor": refund_amt,
        "fee_amount_minor": 0,
        "stripe_refund_id": stripe_refund_id,
        "stripe_payment_intent_id": txn.get("stripe_payment_intent_id"),
        "session_group_id": doc["session_group_id"],
        "parent_transaction_id": tx_id,
        "customer_name": txn.get("customer_name"),
        "customer_phone": txn.get("customer_phone"),
        "created_at": now_iso,
        "updated_at": now_iso,
        "state_history": [{"state": "refunded", "timestamp": now_iso, "trigger": "cancel_selected_partial_reconcile"}],
    }
    try:
        await db.merchant_transactions.insert_one(refund_tx_doc)
    except DuplicateKeyError:
        logger.info("partial reconciliation: child refund duplicate (wallet atlanır)")
        return
    await db.merchant_wallets.update_one(
        {"organization_id": org_id},
        {"$inc": {"available_balance_minor": -refund_amt, "total_refunded_minor": refund_amt}, "$set": {"updated_at": now_iso}},
    )


async def resolve_refund_reconciliation_by_id(
    db,
    reconciliation_id: str,
    *,
    locked_by: str,
    request: Any = None,
) -> Dict[str, Any]:
    """
    Tek kaydı çöz: kilit al, iç state uygula, resolved veya retry.
    """
    row = await db.refund_reconciliation_pending.find_one({"id": reconciliation_id})
    if not row:
        return {"ok": False, "http_status": 404, "error": "reconciliation_not_found"}

    if row.get("status") != "pending":
        return {
            "ok": False,
            "http_status": 400,
            "error": "not_pending",
            "status": row.get("status"),
        }

    locked = await try_acquire_reconciliation_lock(db, reconciliation_id, locked_by)
    if not locked:
        return {"ok": False, "http_status": 409, "error": "lock_not_acquired"}

    logger.info(
        "refund_reconciliation: locked reconciliation_id=%s failed_step=%s retry_count=%s next_retry_at=%s stripe_refund_id=%s locked_by=%s",
        locked["id"],
        locked.get("failed_step"),
        locked.get("retry_count", 0),
        locked.get("next_retry_at"),
        locked.get("stripe_refund_id"),
        locked_by,
    )

    try:
        await _apply_internal_state(db, locked)
    except Exception as e:
        logger.exception("reconciliation apply failed: %s", e)
        return await _mark_retry_or_fail(db, locked, e)

    await _mark_resolved(db, reconciliation_id, note="reconciled")
    org_id = locked["organization_id"]
    await _finalize_side_effects(
        org_id,
        locked["session_group_id"],
        list(locked["appointment_ids"]),
        request,
    )
    logger.info(
        "refund_reconciliation: resolved reconciliation_id=%s failed_step=%s locked_by=%s",
        reconciliation_id,
        locked.get("failed_step"),
        locked_by,
    )
    return {"ok": True, "status": "resolved", "id": reconciliation_id}


async def run_refund_reconciliation_cron(db, *, limit: int = 15) -> Dict[str, Any]:
    """Zamanı gelen pending kayıtları işle (cron)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    q = {
        "status": "pending",
        "$or": [
            {"next_retry_at": None},
            {"next_retry_at": {"$exists": False}},
            {"next_retry_at": {"$lte": now_iso}},
        ],
    }
    cursor = db.refund_reconciliation_pending.find(q).sort("created_at", 1).limit(limit)
    items = await cursor.to_list(limit)
    results: List[Dict[str, Any]] = []
    logger.info(
        "refund_reconciliation_cron: batch_start count=%s limit=%s",
        len(items),
        limit,
    )
    for doc in items:
        rid = doc["id"]
        logger.info(
            "refund_reconciliation_cron: item_begin reconciliation_id=%s failed_step=%s retry_count=%s next_retry_at=%s stripe_refund_id=%s",
            rid,
            doc.get("failed_step"),
            doc.get("retry_count", 0),
            doc.get("next_retry_at"),
            doc.get("stripe_refund_id"),
        )
        out = await resolve_refund_reconciliation_by_id(
            db, rid, locked_by="cron:refund_reconciliation", request=None
        )
        results.append({"id": rid, **out})
        logger.info(
            "refund_reconciliation_cron: item_end reconciliation_id=%s ok=%s status=%s failed_step=%s retry_count=%s next_retry_at=%s error=%s",
            rid,
            out.get("ok"),
            out.get("status"),
            out.get("failed_step") or doc.get("failed_step"),
            out.get("retry_count"),
            out.get("next_retry_at"),
            (out.get("error") or "")[:400],
        )
    return {"processed": len(results), "results": results}
