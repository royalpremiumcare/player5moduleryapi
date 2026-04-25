"""
Webhook Replay Guard — ikincil koruma katmanı.

Mevcut `webhook_events.event_id` unique idempotency anahtarının yanında,
payload_hash + processing_status ile davranışsal replay kontrolü yapar.

Davranış:
  - Yeni event → işle (processed/failed işaretle)
  - Aynı event_id tekrar geldiyse:
      - processed + aynı hash → 200 dön (skip)
      - processed + farklı hash → ALERT (replay attack şüphesi), 200 dön
      - processing → 409 dön (başka worker işliyor)
      - failed → tekrar dene

See plan Bölüm 20.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ReplayDecision(str, Enum):
    PROCESS_NEW = "process_new"              # yeni event, normal işle
    PROCESS_RETRY = "process_retry"          # önceden başarısız, tekrar dene
    SKIP_ALREADY_PROCESSED = "skip_already_processed"  # 200 dön, işleme
    SKIP_REPLAY_MISMATCH = "skip_replay_mismatch"      # payload değişmiş → alert + 200
    CONFLICT_IN_PROGRESS = "conflict_in_progress"      # 409 dön


def compute_payload_hash(payload: Any) -> str:
    """Deterministic sha256 of webhook payload (canonical JSON)."""
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def guard_webhook(
    db,
    *,
    source: str,
    event_id: str,
    event_type: str,
    payload: Any,
    raw_body: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Tuple[ReplayDecision, Optional[Dict[str, Any]]]:
    """
    Check and atomically mark a webhook event for processing.

    Returns:
      (decision, existing_doc)

    Caller behavior:
      - PROCESS_NEW / PROCESS_RETRY: run handler, then call `mark_processed` / `mark_failed`
      - SKIP_* : return 200 to the webhook source immediately (no handler run)
      - CONFLICT_IN_PROGRESS: return 409 (source will retry)
    """
    now = datetime.now(timezone.utc).isoformat()
    payload_hash = compute_payload_hash(payload)
    body_sha = hashlib.sha256((raw_body or "").encode("utf-8")).hexdigest() if raw_body else ""

    existing = await db.webhook_events.find_one({"event_id": event_id})

    if not existing:
        # Atomik insert — race durumunda duplicate key → mevcut kaydı oku
        doc = {
            "id": _uuid(),
            "source": source,
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload if isinstance(payload, dict) else {"_raw": str(payload)},
            "raw_body": raw_body or "",
            "body_sha256": body_sha,
            "payload_hash": payload_hash,
            "signature_verified": True,  # caller should verify before this
            "processing_status": "processing",
            "attempt_count": 1,
            "organization_id": organization_id,
            "received_at": now,
            "last_attempt_at": now,
        }
        try:
            await db.webhook_events.insert_one(doc)
            return ReplayDecision.PROCESS_NEW, doc
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                existing = await db.webhook_events.find_one({"event_id": event_id})
            else:
                logger.exception("webhook_events insert failed: %s", e)
                raise

    assert existing is not None
    status = existing.get("processing_status", "received")

    # processed — idempotent replay
    if status == "processed":
        stored_hash = existing.get("payload_hash")
        if stored_hash and stored_hash != payload_hash:
            logger.error(
                "WEBHOOK REPLAY MISMATCH: event_id=%s stored_hash=%s new_hash=%s",
                event_id, stored_hash, payload_hash,
            )
            await db.webhook_events.update_one(
                {"event_id": event_id},
                {
                    "$inc": {"attempt_count": 1},
                    "$set": {"last_attempt_at": now},
                    "$push": {
                        "replay_anomalies": {
                            "at": now,
                            "new_hash": payload_hash,
                            "stored_hash": stored_hash,
                        }
                    },
                },
            )
            return ReplayDecision.SKIP_REPLAY_MISMATCH, existing

        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$inc": {"attempt_count": 1}, "$set": {"last_attempt_at": now}},
        )
        return ReplayDecision.SKIP_ALREADY_PROCESSED, existing

    if status == "processing":
        return ReplayDecision.CONFLICT_IN_PROGRESS, existing

    if status == "failed":
        # Retry — mark processing
        await db.webhook_events.update_one(
            {"event_id": event_id, "processing_status": "failed"},
            {
                "$inc": {"attempt_count": 1},
                "$set": {
                    "processing_status": "processing",
                    "last_attempt_at": now,
                    "payload_hash": payload_hash,  # update if re-received
                },
            },
        )
        return ReplayDecision.PROCESS_RETRY, existing

    # received / skipped / unknown → treat as new
    await db.webhook_events.update_one(
        {"event_id": event_id},
        {
            "$set": {
                "processing_status": "processing",
                "payload_hash": payload_hash,
                "last_attempt_at": now,
            },
            "$inc": {"attempt_count": 1},
        },
    )
    return ReplayDecision.PROCESS_RETRY, existing


async def mark_processed(
    db, event_id: str, *, result_snapshot: Optional[Dict[str, Any]] = None
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    update: Dict[str, Any] = {
        "processing_status": "processed",
        "processed_at": now,
        "processing_error": None,
    }
    if result_snapshot is not None:
        update["result_snapshot"] = result_snapshot
    await db.webhook_events.update_one({"event_id": event_id}, {"$set": update})


async def mark_failed(db, event_id: str, error: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.webhook_events.update_one(
        {"event_id": event_id},
        {
            "$set": {
                "processing_status": "failed",
                "processing_error": str(error)[:2000],
                "last_attempt_at": now,
            }
        },
    )


def _uuid() -> str:
    import uuid as _u
    return str(_u.uuid4())
