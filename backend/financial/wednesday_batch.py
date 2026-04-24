"""
Wednesday Batch Payout — Salı 23:00 UTC tarama → Çarşamba manuel fund.

Flow:
  1. Tuesday 23:00 UTC (tuesday_batch_prepare_cron):
     - Her `active` cüzdan için `available >= threshold` ise batch'e al
     - Available tx'leri `reserved_for_batch` state'ine taşı
     - `payout_batches` kaydı oluştur (status=draft → awaiting_admin)
  2. Wednesday 09:00 UTC (wednesday_reminder_cron):
     - SuperAdmin'e "batch hazır" email/Slack
  3. SuperAdmin manuel fund → her batch için "Wise'a Hazırla" butonu
     - Wise quote + transfer create (fund DEĞİL!)
     - state → queued_for_wise → wise_fund_pending
  4. SA "Manuel Fund Onayladım" → state → paid_out + wallet update
  5. Hata → state → wise_fund_failed → DLQ

Gated by env FEATURE_WEDNESDAY_BATCH.

See plan Bölüm 2.4, 6, 11.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .feature_flags import is_env_flag_enabled
from .money import get_tier_config
from .state_machine import StateMachine
from .wallet_debt_service import is_payout_eligible

logger = logging.getLogger(__name__)


BATCH_STATUS_DRAFT = "draft"
BATCH_STATUS_AWAITING_ADMIN = "awaiting_admin_fund"
BATCH_STATUS_QUEUED_FOR_WISE = "queued_for_wise"
BATCH_STATUS_WISE_FUND_PENDING = "wise_fund_pending"
BATCH_STATUS_COMPLETED = "completed"
BATCH_STATUS_FAILED = "failed"
BATCH_STATUS_PARTIAL_FAILURE = "partial_failure"


# ---------------------------------------------------------------------------
# Tier threshold resolution (with org override support)
# ---------------------------------------------------------------------------

async def get_payout_threshold(db, organization_id: str) -> int:
    """
    Return the payout threshold (minor units) for an org.
    Priority: org override in settings > tier default.
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        return 0
    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")

    override = settings.get("payout_threshold_override_minor")
    if override and override > 0:
        return int(override)

    try:
        cfg = get_tier_config(base_currency, tier)
        return cfg.limit_minor
    except Exception as e:
        logger.error("tier config lookup failed org=%s: %s", organization_id, e)
        return 0


# ---------------------------------------------------------------------------
# Tuesday prep cron: scan wallets → move to reserved_for_batch
# ---------------------------------------------------------------------------

async def tuesday_batch_prepare_cron(db) -> Dict[str, Any]:
    """Scan all eligible wallets and prepare batches for Wednesday manual fund."""
    if not is_env_flag_enabled("FEATURE_WEDNESDAY_BATCH"):
        logger.info("FEATURE_WEDNESDAY_BATCH disabled, skipping batch prep")
        return {"skipped": True, "reason": "feature_flag_off"}

    now = datetime.now(timezone.utc).isoformat()
    batches_created: List[Dict[str, Any]] = []
    sm = StateMachine(db)

    cursor = db.merchant_wallets.find({})
    async for wallet in cursor:
        org_id = wallet["organization_id"]
        available = int(wallet.get("available_balance_minor") or 0)
        eligible, reason = await is_payout_eligible(db, org_id)
        if not eligible:
            logger.info("batch_prep skip org=%s: %s", org_id, reason)
            continue

        threshold = await get_payout_threshold(db, org_id)
        if threshold <= 0 or available < threshold:
            continue

        # Collect available transactions up to the wallet's total available balance
        tx_cursor = db.merchant_transactions.find({
            "organization_id": org_id,
            "state": "available",
        }).sort("created_at", 1)

        item_ids: List[str] = []
        total_in_batch = 0
        async for tx in tx_cursor:
            amt = int(tx.get("amount_display_minor") or 0)
            if amt <= 0:
                continue
            item_ids.append(tx["id"])
            total_in_batch += amt

        if total_in_batch < threshold or not item_ids:
            continue

        batch_id = str(uuid.uuid4())
        # Transition each tx → reserved_for_batch
        reserved_ok: List[str] = []
        for tx_id in item_ids:
            try:
                await sm.transition(
                    tx_id=tx_id,
                    new_state="reserved_for_batch",
                    trigger="tuesday_batch_prepare",
                    metadata={
                        "payout_batch_id": batch_id,
                        "reserved_at": now,
                    },
                )
                reserved_ok.append(tx_id)
            except Exception as e:
                logger.warning("batch_prep transition failed tx=%s: %s", tx_id, e)

        if not reserved_ok:
            continue

        batch_doc = {
            "id": batch_id,
            "organization_id": org_id,
            "base_currency": wallet.get("base_currency", "TRY"),
            "status": BATCH_STATUS_AWAITING_ADMIN,
            "total_amount_minor": total_in_batch,
            "item_transaction_ids": reserved_ok,
            "item_count": len(reserved_ok),
            "threshold_at_creation": threshold,
            "created_at": now,
            "updated_at": now,
            "wise_transfer_id": None,
            "wise_quote_id": None,
            "wise_batch_group_id": None,
            "funded_at": None,
            "funded_by": None,
            "idempotency_key": f"batch:{org_id}:{now[:10]}",
        }
        try:
            await db.payout_batches.insert_one(batch_doc)
            batches_created.append({
                "id": batch_id,
                "organization_id": org_id,
                "total_amount_minor": total_in_batch,
                "item_count": len(reserved_ok),
            })
            logger.info(
                "batch_prep created: batch=%s org=%s total=%d items=%d",
                batch_id, org_id, total_in_batch, len(reserved_ok),
            )
        except Exception as e:
            logger.exception("batch insert failed org=%s: %s", org_id, e)

    return {
        "batches_created": len(batches_created),
        "items": batches_created,
        "ran_at": now,
    }


# ---------------------------------------------------------------------------
# SuperAdmin manual actions (called from endpoints)
# ---------------------------------------------------------------------------

async def list_batches_awaiting_admin(
    db, limit: int = 100, include_failed: bool = False,
    include_completed: bool = False,
) -> List[Dict[str, Any]]:
    """
    List batches requiring SuperAdmin attention.

    Normalizes both legacy (items[] with per-org data) and PLANN v2 (flat
    organization_id + total_amount_minor) schemas so the UI can render
    uniformly.

    Args:
        include_failed: If True, includes historical `failed` batches too.
            Default False to keep the panel focused on actionable items.
        include_completed: If True, includes `completed` and `partial_failure`
            batches too (geçmiş başarılar).
    """
    statuses = [
        BATCH_STATUS_AWAITING_ADMIN,
        BATCH_STATUS_QUEUED_FOR_WISE,
        BATCH_STATUS_WISE_FUND_PENDING,
    ]
    if include_failed:
        statuses.append(BATCH_STATUS_FAILED)
    if include_completed:
        statuses.append(BATCH_STATUS_COMPLETED)
        statuses.append(BATCH_STATUS_PARTIAL_FAILURE)

    cursor = (
        db.payout_batches
        .find({"status": {"$in": statuses}}, {"_id": 0})
        .sort("created_at", 1)
        .limit(limit)
    )
    raw = await cursor.to_list(limit)

    # Normalize response shape for UI
    normalized: List[Dict[str, Any]] = []
    for b in raw:
        items = b.get("items") or []
        # Derive top-level fields from items[] if missing (legacy batches)
        org_id = b.get("organization_id")
        total = b.get("total_amount_minor")
        currency = b.get("base_currency")
        item_count = b.get("item_count")

        if items:
            item_count = item_count if item_count is not None else len(items)
            if not org_id:
                org_ids = {i.get("organization_id") for i in items if i.get("organization_id")}
                org_id = next(iter(org_ids)) if len(org_ids) == 1 else f"multi:{len(org_ids)}"
            if total is None:
                total = sum(int(i.get("amount_display_minor") or 0) for i in items)
            if not currency:
                currency = next((i.get("base_currency") for i in items if i.get("base_currency")), None)

        b["organization_id"] = org_id or "-"
        b["total_amount_minor"] = int(total or 0)
        b["base_currency"] = currency or b.get("payout_market") or "-"
        b["item_count"] = item_count if item_count is not None else 0
        normalized.append(b)

    # Enrich with organization display name (settings.company_name → business_name → admin user)
    org_ids_lookup = [
        b["organization_id"] for b in normalized
        if b.get("organization_id") and not b["organization_id"].startswith("multi:") and b["organization_id"] != "-"
    ]
    org_name_map: Dict[str, str] = {}
    if org_ids_lookup:
        settings_list = await db.settings.find(
            {"organization_id": {"$in": org_ids_lookup}},
            {"_id": 0, "organization_id": 1, "company_name": 1, "business_name": 1},
        ).to_list(len(org_ids_lookup))
        for s in settings_list:
            name = s.get("company_name") or s.get("business_name") or ""
            if name:
                org_name_map[s["organization_id"]] = name
        missing = [oid for oid in org_ids_lookup if oid not in org_name_map]
        if missing:
            admins = await db.users.find(
                {"organization_id": {"$in": missing}, "role": "admin"},
                {"_id": 0, "organization_id": 1, "full_name": 1, "username": 1},
            ).to_list(len(missing))
            for a in admins:
                if a["organization_id"] not in org_name_map:
                    org_name_map[a["organization_id"]] = a.get("full_name") or a.get("username") or ""

    for b in normalized:
        oid = b["organization_id"]
        if oid.startswith("multi:"):
            b["organization_name"] = f"Çoklu işletme ({oid.split(':', 1)[1]})"
        else:
            b["organization_name"] = org_name_map.get(oid) or oid

    return normalized


async def prepare_batch_for_wise(
    db, *, batch_id: str, admin_id: str, wise_prepare_fn
) -> Dict[str, Any]:
    """
    Admin clicks "Wise'a Hazırla".
    wise_prepare_fn(batch) → {"wise_quote_id", "wise_transfer_id", ...}
    On success: state → queued_for_wise → wise_fund_pending
    On failure: state → failed + DLQ enqueue
    """
    now = datetime.now(timezone.utc).isoformat()
    batch = await db.payout_batches.find_one({"id": batch_id})
    if not batch:
        return {"ok": False, "error": "batch_not_found"}
    if batch["status"] != BATCH_STATUS_AWAITING_ADMIN:
        return {"ok": False, "error": f"invalid_batch_status:{batch['status']}"}

    sm = StateMachine(db)
    tx_ids = batch.get("item_transaction_ids") or []

    # Move each tx to queued_for_wise
    for tx_id in tx_ids:
        try:
            await sm.transition(
                tx_id=tx_id,
                new_state="queued_for_wise",
                trigger="admin_prepare_wise",
                metadata={"admin_id": admin_id},
            )
        except Exception as e:
            logger.warning("prepare_for_wise tx transition failed tx=%s: %s", tx_id, e)

    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {"status": BATCH_STATUS_QUEUED_FOR_WISE, "updated_at": now}},
    )

    try:
        result = wise_prepare_fn(batch)
        if hasattr(result, "__await__"):
            result = await result
    except Exception as e:
        logger.exception("wise_prepare_fn failed batch=%s: %s", batch_id, e)
        # Rollback: transition to failed
        for tx_id in tx_ids:
            try:
                await sm.transition(
                    tx_id=tx_id, new_state="failed",
                    trigger="wise_prepare_failed",
                    metadata={"error": str(e)[:500]},
                )
            except Exception:
                pass
        await db.payout_batches.update_one(
            {"id": batch_id},
            {"$set": {"status": BATCH_STATUS_FAILED, "updated_at": now, "error": str(e)[:1000]}},
        )
        # DLQ enqueue
        try:
            from .dead_letter_queue import enqueue as dlq_enqueue, FailureType
            await dlq_enqueue(
                db,
                failure_type=FailureType.WISE_FUND_FAILED.value,
                source_entity_type="payout_batch",
                source_entity_id=batch_id,
                organization_id=batch.get("organization_id", ""),
                error_message=str(e),
                idempotency_key=f"batch_prepare:{batch_id}",
            )
        except Exception:
            pass
        return {"ok": False, "error": "wise_prepare_failed", "detail": str(e)}

    # Success: transition to wise_fund_pending
    for tx_id in tx_ids:
        try:
            await sm.transition(
                tx_id=tx_id,
                new_state="wise_fund_pending",
                trigger="wise_prepare_success",
                metadata={
                    "wise_quote_id": result.get("wise_quote_id"),
                    "wise_transfer_id": result.get("wise_transfer_id"),
                },
            )
        except Exception as e:
            logger.warning("wise_fund_pending transition failed tx=%s: %s", tx_id, e)

    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {
            "status": BATCH_STATUS_WISE_FUND_PENDING,
            "wise_quote_id": result.get("wise_quote_id"),
            "wise_transfer_id": result.get("wise_transfer_id"),
            "wise_batch_group_id": result.get("wise_batch_group_id"),
            "wise_prepared_by": admin_id,
            "wise_prepared_at": now,
            "updated_at": now,
        }},
    )
    logger.info("batch prepared for Wise: batch=%s admin=%s", batch_id, admin_id)
    return {"ok": True, "wise_quote_id": result.get("wise_quote_id")}


async def bulk_prepare_batches_for_wise(
    db, *, batch_ids: Optional[List[str]], admin_id: str, unified_prepare_fn,
) -> Dict[str, Any]:
    """Admin clicks "Tümünü Wise'a Hazırla".

    Unified flow: all awaiting_admin_fund batches become transfers inside
    ONE Wise batch group, so Wise panel shows a single "N GBP Transfer batch"
    entry the admin can fund in one click.

    If batch_ids is None, processes ALL awaiting_admin_fund batches.

    On success: all tx's → wise_fund_pending, all batches → wise_fund_pending
    with shared wise_batch_group_id but unique wise_transfer_id each.

    On failure: all tx's → failed (wallet rollback), all batches → failed,
    per-batch DLQ entries. The partially-created Wise batch group id (if any)
    is surfaced so admin can clean up manually from the Wise panel.
    """
    q: Dict[str, Any] = {"status": BATCH_STATUS_AWAITING_ADMIN}
    if batch_ids:
        q["id"] = {"$in": batch_ids}

    batches: List[Dict[str, Any]] = []
    async for b in db.payout_batches.find(q):
        b.pop("_id", None)
        batches.append(b)

    if not batches:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "items": [], "mode": "unified"}

    now = datetime.now(timezone.utc).isoformat()
    sm = StateMachine(db)

    # Step 1: move every tx of every batch to queued_for_wise
    all_tx_ids: List[str] = []
    batch_tx_map: Dict[str, List[str]] = {}
    for b in batches:
        tx_ids = b.get("item_transaction_ids") or b.get("transaction_ids") or []
        batch_tx_map[b["id"]] = tx_ids
        all_tx_ids.extend(tx_ids)
        for tx_id in tx_ids:
            try:
                await sm.transition(
                    tx_id=tx_id,
                    new_state="queued_for_wise",
                    trigger="admin_bulk_prepare_wise",
                    metadata={"admin_id": admin_id, "batch_id": b["id"]},
                )
            except Exception as e:
                logger.warning("bulk queued_for_wise tx=%s failed: %s", tx_id, e)
        await db.payout_batches.update_one(
            {"id": b["id"]},
            {"$set": {"status": BATCH_STATUS_QUEUED_FOR_WISE, "updated_at": now}},
        )

    # Step 2: call unified Wise prep (single batch group)
    try:
        result = unified_prepare_fn(batches)
        if hasattr(result, "__await__"):
            result = await result
    except Exception as e:
        logger.exception("bulk unified prep failed: %s", e)
        # Rollback: every tx → failed, every batch → failed, DLQ per batch
        for b in batches:
            for tx_id in batch_tx_map.get(b["id"], []):
                try:
                    await sm.transition(
                        tx_id=tx_id, new_state="failed",
                        trigger="wise_bulk_prepare_failed",
                        metadata={"error": str(e)[:500]},
                    )
                except Exception:
                    pass
            await db.payout_batches.update_one(
                {"id": b["id"]},
                {"$set": {
                    "status": BATCH_STATUS_FAILED,
                    "updated_at": now,
                    "error": str(e)[:1000],
                }},
            )
            # DLQ enqueue per batch
            try:
                from .dead_letter_queue import enqueue as dlq_enqueue, FailureType
                await dlq_enqueue(
                    db,
                    failure_type=FailureType.WISE_FUND_FAILED.value,
                    source_entity_type="payout_batch",
                    source_entity_id=b["id"],
                    organization_id=b.get("organization_id", ""),
                    error_message=str(e),
                    idempotency_key=f"bulk_prepare:{b['id']}",
                )
            except Exception:
                pass
        return {
            "ok": False,
            "processed": len(batches),
            "success": 0,
            "failed": len(batches),
            "error": str(e)[:500],
            "mode": "unified",
        }

    # Step 3: success — persist Wise ids per batch, transition everything
    wise_group_id = result.get("wise_batch_group_id")
    per_batch = result.get("per_batch", {})

    success_count = 0
    items: List[Dict[str, Any]] = []
    for b in batches:
        bid = b["id"]
        info = per_batch.get(bid) or {}
        if not info.get("wise_transfer_id"):
            # should not happen; mark failed just in case
            logger.warning("bulk: no wise info returned for batch=%s", bid)
            items.append({"batch_id": bid, "ok": False, "error": "no_wise_info"})
            continue

        for tx_id in batch_tx_map.get(bid, []):
            try:
                await sm.transition(
                    tx_id=tx_id,
                    new_state="wise_fund_pending",
                    trigger="wise_bulk_prepare_success",
                    metadata={
                        "wise_quote_id": info.get("wise_quote_id"),
                        "wise_transfer_id": info.get("wise_transfer_id"),
                        "wise_batch_group_id": wise_group_id,
                    },
                )
            except Exception as e:
                logger.warning("bulk wise_fund_pending tx=%s failed: %s", tx_id, e)

        await db.payout_batches.update_one(
            {"id": bid},
            {"$set": {
                "status": BATCH_STATUS_WISE_FUND_PENDING,
                "wise_quote_id": info.get("wise_quote_id"),
                "wise_transfer_id": info.get("wise_transfer_id"),
                "wise_batch_group_id": wise_group_id,
                "wise_prepared_by": admin_id,
                "wise_prepared_at": now,
                "updated_at": now,
            }},
        )
        success_count += 1
        items.append({
            "batch_id": bid,
            "ok": True,
            "wise_quote_id": info.get("wise_quote_id"),
            "wise_transfer_id": info.get("wise_transfer_id"),
        })

    logger.info(
        "bulk unified prep success: wise_group=%s batches=%d",
        wise_group_id, success_count,
    )

    return {
        "ok": True,
        "processed": len(batches),
        "success": success_count,
        "failed": len(batches) - success_count,
        "wise_batch_group_id": wise_group_id,
        "items": items,
        "mode": "unified",
    }


async def confirm_manual_fund(
    db, *, batch_id: str, admin_id: str, note: str = ""
) -> Dict[str, Any]:
    """Admin clicks 'Manuel Fund Onayladım' — finalize paid_out."""
    now = datetime.now(timezone.utc).isoformat()
    batch = await db.payout_batches.find_one({"id": batch_id})
    if not batch:
        return {"ok": False, "error": "batch_not_found"}
    if batch["status"] != BATCH_STATUS_WISE_FUND_PENDING:
        return {"ok": False, "error": f"invalid_batch_status:{batch['status']}"}

    sm = StateMachine(db)
    tx_ids = batch.get("item_transaction_ids") or []
    paid_out_count = 0
    errors: List[str] = []

    for tx_id in tx_ids:
        try:
            await sm.transition(
                tx_id=tx_id,
                new_state="paid_out",
                trigger="admin_manual_fund_confirm",
                metadata={
                    "admin_id": admin_id,
                    "funded_at": now,
                    "note": note[:500],
                },
            )
            paid_out_count += 1
        except Exception as e:
            errors.append(f"{tx_id}:{str(e)[:100]}")
            logger.warning("paid_out transition failed tx=%s: %s", tx_id, e)

    new_status = (
        BATCH_STATUS_COMPLETED
        if paid_out_count == len(tx_ids)
        else BATCH_STATUS_PARTIAL_FAILURE
    )
    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {
            "status": new_status,
            "funded_at": now,
            "funded_by": admin_id,
            "fund_note": note[:2000],
            "updated_at": now,
            "errors": errors,
        }},
    )

    # Audit log
    try:
        await db.financial_audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "organization_id": batch.get("organization_id", ""),
            "actor": admin_id,
            "actor_role": "superadmin",
            "action": "batch_funded",
            "details": {
                "batch_id": batch_id,
                "paid_out_count": paid_out_count,
                "total_items": len(tx_ids),
                "errors": errors,
            },
            "created_at": now,
        })
    except Exception as e:
        logger.warning("audit log insert failed: %s", e)

    logger.info(
        "batch funded: batch=%s admin=%s status=%s paid_out=%d/%d",
        batch_id, admin_id, new_status, paid_out_count, len(tx_ids),
    )

    # Notify merchant (non-blocking)
    try:
        await _notify_batch_outcome(db, batch, funded=True, new_status=new_status, errors=errors)
    except Exception as e:
        logger.warning("batch_funded notification failed: %s", e)

    return {
        "ok": new_status == BATCH_STATUS_COMPLETED,
        "status": new_status,
        "paid_out_count": paid_out_count,
        "total_items": len(tx_ids),
        "errors": errors,
    }


async def bulk_confirm_manual_fund(
    db, *, batch_ids: Optional[List[str]], admin_id: str, note: str = "",
) -> Dict[str, Any]:
    """Admin clicks "Tümünü Fonlandı İşaretle" — confirm manual fund for every
    wise_fund_pending batch (or the subset in batch_ids) in one call.

    Iterates confirm_manual_fund per batch; aggregates results.
    """
    q: Dict[str, Any] = {"status": BATCH_STATUS_WISE_FUND_PENDING}
    if batch_ids:
        q["id"] = {"$in": batch_ids}

    target_ids: List[str] = []
    async for b in db.payout_batches.find(q, {"id": 1}):
        target_ids.append(b["id"])

    items: List[Dict[str, Any]] = []
    success = 0
    failed = 0
    for bid in target_ids:
        try:
            res = await confirm_manual_fund(
                db, batch_id=bid, admin_id=admin_id, note=note,
            )
            items.append({"batch_id": bid, **res})
            if res.get("ok"):
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.exception("bulk confirm_fund failed batch=%s: %s", bid, e)
            items.append({"batch_id": bid, "ok": False, "error": str(e)[:300]})
            failed += 1

    return {
        "ok": failed == 0,
        "processed": len(target_ids),
        "success": success,
        "failed": failed,
        "items": items,
    }


async def mark_batch_failed(
    db, *, batch_id: str, admin_id: str, reason: str
) -> Dict[str, Any]:
    """Admin clicks 'Başarısız İşaretle' — rollback reserved to available."""
    now = datetime.now(timezone.utc).isoformat()
    batch = await db.payout_batches.find_one({"id": batch_id})
    if not batch:
        return {"ok": False, "error": "batch_not_found"}

    sm = StateMachine(db)
    tx_ids = batch.get("item_transaction_ids") or []
    rolled_back = 0
    for tx_id in tx_ids:
        try:
            await sm.transition(
                tx_id=tx_id,
                new_state="failed",
                trigger="admin_mark_batch_failed",
                metadata={"admin_id": admin_id, "reason": reason[:500]},
            )
            rolled_back += 1
        except Exception as e:
            logger.warning("mark_failed transition failed tx=%s: %s", tx_id, e)

    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {
            "status": BATCH_STATUS_FAILED,
            "failed_by": admin_id,
            "failed_at": now,
            "failure_reason": reason[:2000],
            "updated_at": now,
        }},
    )
    # DLQ
    try:
        from .dead_letter_queue import enqueue as dlq_enqueue, FailureType
        await dlq_enqueue(
            db,
            failure_type=FailureType.WISE_FUND_FAILED.value,
            source_entity_type="payout_batch",
            source_entity_id=batch_id,
            organization_id=batch.get("organization_id", ""),
            error_message=reason[:500],
            idempotency_key=f"batch_manual_fail:{batch_id}",
        )
    except Exception:
        pass
    logger.error("batch marked failed: batch=%s reason=%s", batch_id, reason[:200])

    # Notify (non-blocking)
    try:
        await _notify_batch_outcome(db, batch, funded=False, new_status=BATCH_STATUS_FAILED, errors=[reason])
    except Exception as e:
        logger.warning("batch_failed notification failed: %s", e)

    return {"ok": True, "status": BATCH_STATUS_FAILED, "rolled_back": rolled_back}


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------

async def _notify_batch_outcome(
    db, batch: Dict[str, Any], *, funded: bool, new_status: str, errors: Optional[List[str]] = None,
) -> None:
    """Email merchant + Slack SuperAdmin about batch fund outcome."""
    import asyncio

    try:
        from .notifications_v2 import (
            send_payout_failed_v2_email, send_slack,
        )
        from .email_notifications import send_payout_success_email
    except Exception:
        return

    org_id = batch.get("organization_id", "")
    settings = await db.settings.find_one({"organization_id": org_id}) or {}
    admin_user = await db.users.find_one({"organization_id": org_id, "role": "admin"}, {"_id": 0})
    if not admin_user:
        return
    to_email = admin_user.get("username") or admin_user.get("email")
    if not to_email:
        return

    merchant_name = settings.get("company_name", "İşletme")
    amount = int(batch.get("total_amount_minor") or 0)
    currency = batch.get("base_currency") or settings.get("base_currency", "TRY")
    batch_id = batch.get("id", "")

    if funded and new_status == "completed":
        await asyncio.to_thread(
            send_payout_success_email, to_email, merchant_name, amount, currency, "wise",
        )
        send_slack(
            f":moneybag: Batch ödemesi yapıldı: {merchant_name}",
            fields={"Batch ID": batch_id, "Tutar (minor)": amount, "Para birimi": currency},
        )
    else:
        error_code = ";".join((errors or [])[:3])[:300]
        await asyncio.to_thread(
            send_payout_failed_v2_email, to_email, merchant_name, amount, currency, batch_id, error_code,
        )
        send_slack(
            f":rotating_light: Batch ödemesi BAŞARISIZ: {merchant_name}",
            critical=True,
            fields={"Batch ID": batch_id, "Tutar (minor)": amount, "Hata": error_code},
        )


# ---------------------------------------------------------------------------
# Merchant-facing wallet status helper
# ---------------------------------------------------------------------------

async def compute_wallet_status(db, organization_id: str) -> Dict[str, Any]:
    """
    Compute merchant-facing wallet status for UI:
      - under_threshold: Bu Çarşamba ödeme için X kadar kaldı
      - queued: Batch oluşturuldu, ödeme için hazır
      - wise_pending: Wise'da işleniyor
      - paid_out: Son ödeme başarıyla yapıldı
    """
    wallet = await db.merchant_wallets.find_one({"organization_id": organization_id})
    if not wallet:
        return {"status": "no_wallet"}

    available = int(wallet.get("available_balance_minor") or 0)
    reserved = int(wallet.get("reserved_balance_minor") or 0)
    threshold = await get_payout_threshold(db, organization_id)
    wallet_status = wallet.get("wallet_status") or "active"

    # Next Wednesday (for merchant display)
    now = datetime.now(timezone.utc)
    days_ahead = (2 - now.weekday()) % 7  # 2 = Wednesday
    if days_ahead == 0 and now.hour >= 9:
        days_ahead = 7
    next_batch = (now + timedelta(days=days_ahead)).date().isoformat()

    # Active batches for this org
    active_batch = await db.payout_batches.find_one({
        "organization_id": organization_id,
        "status": {"$in": [
            BATCH_STATUS_AWAITING_ADMIN, BATCH_STATUS_QUEUED_FOR_WISE,
            BATCH_STATUS_WISE_FUND_PENDING,
        ]},
    })

    if wallet_status == "suspended":
        status = "suspended"
    elif wallet_status == "payout_stopped":
        status = "payout_stopped"
    elif active_batch and active_batch["status"] == BATCH_STATUS_WISE_FUND_PENDING:
        status = "wise_pending"
    elif active_batch and active_batch["status"] in (BATCH_STATUS_AWAITING_ADMIN, BATCH_STATUS_QUEUED_FOR_WISE):
        status = "queued"
    elif available >= threshold and threshold > 0:
        status = "threshold_met"
    else:
        status = "under_threshold"

    progress_bps = 0
    if threshold > 0:
        progress_bps = min(10_000, int(available * 10_000 / threshold))

    # Last payout
    last_payout = await db.payout_batches.find_one(
        {"organization_id": organization_id, "status": BATCH_STATUS_COMPLETED},
        sort=[("funded_at", -1)],
    )

    return {
        "status": status,
        "wallet_status": wallet_status,
        "available_balance_minor": available,
        "reserved_balance_minor": reserved,
        "pending_debt_minor": int(wallet.get("pending_debt_minor") or 0),
        "threshold_minor": threshold,
        "progress_bps": progress_bps,
        "remaining_to_threshold_minor": max(0, threshold - available),
        "next_batch_date": next_batch,
        "active_batch": (
            {
                "id": active_batch["id"],
                "status": active_batch["status"],
                "total_amount_minor": active_batch.get("total_amount_minor", 0),
                "created_at": active_batch.get("created_at"),
            } if active_batch else None
        ),
        "last_payout": (
            {
                "id": last_payout["id"],
                "total_amount_minor": last_payout.get("total_amount_minor", 0),
                "funded_at": last_payout.get("funded_at"),
            } if last_payout else None
        ),
    }
