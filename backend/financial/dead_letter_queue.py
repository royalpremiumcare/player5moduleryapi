"""
Dead-Letter Queue — unified retry orchestrator for failed financial operations.

Failure types:
  - wise_fund_failed
  - refund_failed
  - reconciliation_mismatch
  - webhook_processing_failed
  - payout_generic_failed

Each failure type has its own backoff schedule and max_retries.
On retry exhaustion → manual_review status → SuperAdmin alert.

See plan Bölüm 19.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure type registry — backoff and retry policy
# ---------------------------------------------------------------------------

class FailureType(str, Enum):
    WISE_FUND_FAILED = "wise_fund_failed"
    REFUND_FAILED = "refund_failed"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    WEBHOOK_PROCESSING_FAILED = "webhook_processing_failed"
    PAYOUT_GENERIC_FAILED = "payout_generic_failed"


# backoff in seconds per retry attempt (index = retry_count before this attempt)
_BACKOFF_SCHEDULES: Dict[str, List[int]] = {
    FailureType.WISE_FUND_FAILED.value:        [3600, 14400, 86400],                          # 1h, 4h, 24h
    FailureType.REFUND_FAILED.value:           [30, 120, 600, 3600, 21600],                   # 30s, 2m, 10m, 1h, 6h
    FailureType.RECONCILIATION_MISMATCH.value: [60, 300, 900, 3600, 14400, 21600, 43200, 86400, 86400, 86400],
    FailureType.WEBHOOK_PROCESSING_FAILED.value: [10, 30, 120, 600, 3600, 21600, 86400, 172800],
    FailureType.PAYOUT_GENERIC_FAILED.value:   [3600, 14400, 86400],
}


def _max_retries_for(failure_type: str) -> int:
    return len(_BACKOFF_SCHEDULES.get(failure_type, [3600, 14400, 86400]))


def _next_retry_at(failure_type: str, retry_count: int) -> Optional[str]:
    schedule = _BACKOFF_SCHEDULES.get(failure_type, [3600])
    idx = min(retry_count, len(schedule) - 1)
    if idx < 0:
        return None
    delta_seconds = schedule[idx]
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)).isoformat()


# ---------------------------------------------------------------------------
# DLQ CRUD
# ---------------------------------------------------------------------------

async def enqueue(
    db,
    *,
    failure_type: str,
    source_entity_type: str,
    source_entity_id: str,
    organization_id: str,
    error_message: str,
    error_code: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a failed operation to the DLQ (or increment existing)."""
    now = datetime.now(timezone.utc).isoformat()
    idem = idempotency_key or f"{failure_type}:{source_entity_type}:{source_entity_id}"
    max_retries = _max_retries_for(failure_type)

    # Upsert by idempotency_key
    doc_set = {
        "failure_type": failure_type,
        "source_entity_type": source_entity_type,
        "source_entity_id": source_entity_id,
        "organization_id": organization_id,
        "error_message": (error_message or "")[:2000],
        "error_code": error_code,
        "max_retries": max_retries,
        "next_retry_at": _next_retry_at(failure_type, 0),
    }
    doc_insert = {
        "id": str(uuid.uuid4()),
        "idempotency_key": idem,
        "retry_count": 0,
        "status": "pending",
        "manual_review_required": False,
        "manual_reviewer": None,
        "manual_resolution_note": None,
        "created_at": now,
        "resolved_at": None,
        "last_retry_at": None,
        "extra": extra or {},
    }

    result = await db.dead_letter_queue.find_one_and_update(
        {"idempotency_key": idem, "status": {"$in": ["pending", "retrying", "manual_review"]}},
        {
            "$set": {**doc_set, "updated_at": now},
            "$setOnInsert": doc_insert,
        },
        upsert=True,
        return_document=True,  # type: ignore[arg-type]
    )
    logger.warning(
        "DLQ enqueue: type=%s entity=%s:%s org=%s err=%s",
        failure_type, source_entity_type, source_entity_id, organization_id,
        error_message[:200],
    )
    return result or doc_insert


async def list_pending(db, limit: int = 20) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    cursor = (
        db.dead_letter_queue
        .find(
            {
                "status": "pending",
                "$or": [
                    {"next_retry_at": None},
                    {"next_retry_at": {"$exists": False}},
                    {"next_retry_at": {"$lte": now}},
                ],
            },
            {"_id": 0},
        )
        .sort("created_at", 1)
        .limit(limit)
    )
    return await cursor.to_list(limit)


async def _acquire_lock(db, dlq_id: str, locked_by: str, ttl_minutes: int = 15) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    stale_before = (now - timedelta(minutes=ttl_minutes)).isoformat()
    doc = await db.dead_letter_queue.find_one_and_update(
        {
            "id": dlq_id,
            "status": "pending",
            "$or": [
                {"locked_at": None},
                {"locked_at": {"$exists": False}},
                {"locked_at": {"$lt": stale_before}},
            ],
        },
        {
            "$set": {
                "status": "retrying",
                "locked_by": locked_by,
                "locked_at": now.isoformat(),
            }
        },
        return_document=True,  # type: ignore[arg-type]
    )
    return doc


async def mark_resolved(db, dlq_id: str, note: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.dead_letter_queue.update_one(
        {"id": dlq_id},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": now,
                "manual_resolution_note": note[:2000],
                "locked_at": None,
                "locked_by": None,
                "updated_at": now,
            }
        },
    )


async def mark_retry_or_review(db, doc: Dict[str, Any], error: str) -> Dict[str, Any]:
    """Failed again — schedule next retry or promote to manual_review."""
    dlq_id = doc["id"]
    retry = int(doc.get("retry_count") or 0) + 1
    max_r = int(doc.get("max_retries") or 3)
    now = datetime.now(timezone.utc).isoformat()
    err_short = str(error)[:2000]

    if retry >= max_r:
        await db.dead_letter_queue.update_one(
            {"id": dlq_id},
            {
                "$set": {
                    "status": "manual_review",
                    "manual_review_required": True,
                    "retry_count": retry,
                    "error_message": err_short,
                    "last_retry_at": now,
                    "locked_at": None,
                    "locked_by": None,
                    "next_retry_at": None,
                    "updated_at": now,
                }
            },
        )
        logger.error(
            "DLQ manual_review: id=%s type=%s retry_count=%s err=%s",
            dlq_id, doc.get("failure_type"), retry, err_short[:400],
        )
        return {"ok": False, "status": "manual_review", "retry_count": retry}

    next_at = _next_retry_at(doc["failure_type"], retry)
    await db.dead_letter_queue.update_one(
        {"id": dlq_id},
        {
            "$set": {
                "status": "pending",
                "retry_count": retry,
                "error_message": err_short,
                "last_retry_at": now,
                "next_retry_at": next_at,
                "locked_at": None,
                "locked_by": None,
                "updated_at": now,
            }
        },
    )
    logger.info(
        "DLQ retry_scheduled: id=%s type=%s retry_count=%s next_at=%s",
        dlq_id, doc.get("failure_type"), retry, next_at,
    )
    return {"ok": False, "status": "pending", "retry_count": retry, "next_retry_at": next_at}


# ---------------------------------------------------------------------------
# Dispatcher — failure_type → handler registry
# ---------------------------------------------------------------------------

# Handlers are registered at startup by other modules. Signature:
#   async def handler(db, doc) -> None   # raises on failure
_HANDLERS: Dict[str, Callable] = {}


def register_handler(failure_type: str, handler: Callable) -> None:
    """Register a retry handler for a failure type (called at app startup)."""
    _HANDLERS[failure_type] = handler
    logger.info("DLQ handler registered: %s", failure_type)


async def run_retry_cron(db, *, locked_by: str = "cron:dlq", limit: int = 20) -> Dict[str, Any]:
    """Process pending DLQ entries whose retry time has come."""
    items = await list_pending(db, limit=limit)
    processed: List[Dict[str, Any]] = []
    logger.info("DLQ cron: batch_start count=%d", len(items))

    for item in items:
        dlq_id = item["id"]
        locked = await _acquire_lock(db, dlq_id, locked_by=locked_by)
        if not locked:
            continue

        handler = _HANDLERS.get(locked["failure_type"])
        if not handler:
            logger.error("DLQ no handler for type: %s (id=%s)", locked["failure_type"], dlq_id)
            await mark_retry_or_review(db, locked, f"no_handler_registered:{locked['failure_type']}")
            processed.append({"id": dlq_id, "status": "no_handler"})
            continue

        try:
            await handler(db, locked)
            await mark_resolved(db, dlq_id, note="retry_success")
            processed.append({"id": dlq_id, "status": "resolved"})
        except Exception as e:
            logger.exception("DLQ retry handler failed: id=%s type=%s", dlq_id, locked["failure_type"])
            result = await mark_retry_or_review(db, locked, str(e))
            processed.append({"id": dlq_id, **result})

    return {"processed": len(processed), "items": processed}


# ---------------------------------------------------------------------------
# SuperAdmin manual actions
# ---------------------------------------------------------------------------

async def manual_retry(db, dlq_id: str, reviewer: str) -> Dict[str, Any]:
    """Admin clicks 'Retry Now' — reset status to pending, next_retry_at = now."""
    now = datetime.now(timezone.utc).isoformat()
    res = await db.dead_letter_queue.update_one(
        {"id": dlq_id, "status": {"$in": ["manual_review", "pending"]}},
        {
            "$set": {
                "status": "pending",
                "next_retry_at": now,
                "manual_reviewer": reviewer,
                "updated_at": now,
                "locked_at": None,
                "locked_by": None,
            }
        },
    )
    return {"ok": res.modified_count > 0}


async def manual_resolve(db, dlq_id: str, reviewer: str, note: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    res = await db.dead_letter_queue.update_one(
        {"id": dlq_id},
        {
            "$set": {
                "status": "resolved",
                "manual_reviewer": reviewer,
                "manual_resolution_note": note[:2000],
                "resolved_at": now,
                "updated_at": now,
            }
        },
    )
    return {"ok": res.modified_count > 0}


async def manual_abandon(db, dlq_id: str, reviewer: str, reason: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    res = await db.dead_letter_queue.update_one(
        {"id": dlq_id},
        {
            "$set": {
                "status": "abandoned",
                "manual_reviewer": reviewer,
                "manual_resolution_note": reason[:2000],
                "resolved_at": now,
                "updated_at": now,
            }
        },
    )
    return {"ok": res.modified_count > 0}
