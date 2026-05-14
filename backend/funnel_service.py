"""
Funnel Service — MongoDB ledger + PostHog dispatcher.

İki ana sorumluluk:
  1. `record_funnel_event(...)` — frontend-owned event'ler için MongoDB ledger insert
     (frontend zaten PostHog'a yazdı; biz sadece ground-truth ledger'a yazıyoruz).
  2. `track_webhook_event(...)` — webhook-owned event'ler için PostHog Python SDK
     + MongoDB ledger insert (backend tek sahip).

PostHog `posthog-python` paketi yoksa (development) sessizce no-op olur; MongoDB
ledger her durumda yazılır.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from funnel_registry import (
    EVENT_REGISTRY,
    is_frontend_owned,
    is_valid_event,
    is_webhook_owned,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PostHog Python SDK (lazy import; opsiyonel)
# ---------------------------------------------------------------------------
_posthog_client = None
_posthog_init_attempted = False


def _get_posthog():
    """PostHog client'ı lazy init eder. Paket veya API key yoksa None döner."""
    global _posthog_client, _posthog_init_attempted
    if _posthog_init_attempted:
        return _posthog_client

    _posthog_init_attempted = True
    api_key = os.environ.get("POSTHOG_API_KEY")
    if not api_key:
        logger.info("POSTHOG_API_KEY not set; backend funnel events will only hit MongoDB ledger.")
        return None

    try:
        from posthog import Posthog  # type: ignore
        host = os.environ.get("POSTHOG_HOST", "https://eu.posthog.com")
        _posthog_client = Posthog(api_key, host=host)
        logger.info(f"PostHog client initialised (host={host})")
    except ImportError:
        logger.warning("posthog package not installed; backend events skip PostHog.")
        _posthog_client = None
    except Exception as exc:
        logger.error(f"PostHog init failed: {exc}")
        _posthog_client = None
    return _posthog_client


# ---------------------------------------------------------------------------
# MongoDB ledger
# ---------------------------------------------------------------------------
async def _insert_ledger(
    db,
    *,
    event_name: str,
    insert_id: str,
    distinct_id: str,
    owner: str,
    source: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    properties: Dict[str, Any],
) -> bool:
    """
    `funnel_events` koleksiyonuna idempotent insert yapar.
    `insert_id` unique index'i nedeniyle E11000 dup-key fırlarsa True döner ama yazmaz.
    """
    doc = {
        "event_name": event_name,
        "insert_id": insert_id,
        "distinct_id": distinct_id,
        "owner": owner,
        "source": source,
        "organization_id": organization_id,
        "user_id": user_id,
        "properties": properties or {},
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await db.funnel_events.insert_one(doc)
        return True
    except Exception as exc:
        # Duplicate key (idempotent retry) — tamam, normal
        msg = str(exc)
        if "E11000" in msg or "duplicate key" in msg.lower():
            logger.debug(f"funnel_events dup insert ignored for {event_name} {insert_id}")
            return True
        logger.error(f"funnel_events insert failed for {event_name}: {exc}")
        return False


async def record_funnel_event(
    db,
    *,
    event_name: str,
    insert_id: str,
    distinct_id: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    source: str = "frontend",
    properties: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Frontend-owned event'leri MongoDB ledger'a yazar (PostHog yazımı tarayıcıda yapılır).

    Returns: True başarılı/idempotent dup, False kalıcı hata.
    """
    if not is_valid_event(event_name):
        logger.warning(f"Unknown funnel event_name rejected: {event_name}")
        return False

    if not is_frontend_owned(event_name):
        logger.warning(
            f"Event '{event_name}' is webhook-owned; cannot be recorded via record_funnel_event "
            "(use track_webhook_event)."
        )
        return False

    props = dict(properties or {})
    props.setdefault("source", source)

    return await _insert_ledger(
        db,
        event_name=event_name,
        insert_id=insert_id,
        distinct_id=distinct_id,
        owner="frontend",
        source=source,
        organization_id=organization_id,
        user_id=user_id,
        properties=props,
    )


async def track_webhook_event(
    db,
    *,
    event_name: str,
    distinct_id: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    properties: Optional[Dict[str, Any]] = None,
    insert_id: Optional[str] = None,
) -> bool:
    """
    Webhook-owned event'leri hem PostHog'a hem MongoDB ledger'a yazar.
    Frontend bu event'leri **asla** emit etmez (ör. subscription_completed).

    Returns: True başarılı, False kalıcı hata.
    """
    if not is_valid_event(event_name):
        logger.warning(f"Unknown webhook event rejected: {event_name}")
        return False

    if not is_webhook_owned(event_name):
        logger.warning(
            f"Event '{event_name}' is frontend-owned; cannot be tracked via track_webhook_event."
        )
        return False

    iid = insert_id or str(uuid.uuid4())
    props = dict(properties or {})
    props.setdefault("source", "webhook")

    # 1. PostHog (best-effort; başarısız olsa bile ledger yazılır)
    client = _get_posthog()
    if client is not None:
        try:
            client.capture(
                distinct_id=distinct_id,
                event=event_name,
                properties=props,
                disable_geoip=True,
                # PostHog 24h içinde aynı $insert_id'yi dedupe eder
                uuid=iid,
            )
        except Exception as exc:
            logger.error(f"PostHog capture failed for webhook event {event_name}: {exc}")

    # 2. MongoDB ledger (ground truth)
    return await _insert_ledger(
        db,
        event_name=event_name,
        insert_id=iid,
        distinct_id=distinct_id,
        owner="webhook",
        source="webhook",
        organization_id=organization_id,
        user_id=user_id,
        properties=props,
    )


# ---------------------------------------------------------------------------
# Index helper — startup'ta çağrılır
# ---------------------------------------------------------------------------
async def ensure_funnel_indexes(db) -> None:
    """`funnel_events` koleksiyonunun zorunlu indekslerini oluşturur (idempotent)."""
    try:
        await db.funnel_events.create_index("insert_id", unique=True, name="insert_id_unique")
        await db.funnel_events.create_index(
            [("organization_id", 1), ("created_at", -1)],
            name="org_created_idx",
        )
        await db.funnel_events.create_index("event_name", name="event_name_idx")
        logger.info("funnel_events indexes ensured.")
    except Exception as exc:
        logger.error(f"Failed to ensure funnel_events indexes: {exc}")
