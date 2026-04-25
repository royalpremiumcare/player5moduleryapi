"""
Expiry / TTL Service — timed lifecycle management.

Rules (PLANN v2 plan Bölüm 18):
  - Wise quote internal validity: 5 minutes (strict)
  - Stripe exchange rate assumption: 10 minutes (refresh beyond)
  - reserved_for_batch expiry: 7 days → auto-rollback to available

Cron: run_expiry_crons() every hour.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# Constants
WISE_QUOTE_TTL_SECONDS = 5 * 60            # 5 minutes (strict internal)
EXCHANGE_RATE_TTL_SECONDS = 10 * 60        # 10 minutes
RESERVE_EXPIRY_DAYS = 7                    # reserved_for_batch auto-rollback


# ---------------------------------------------------------------------------
# Wise Quote Expiry
# ---------------------------------------------------------------------------

def compute_quote_internal_expiry(quote_locked_at: str) -> str:
    """Return ISO timestamp when a quote becomes internally stale (5dk)."""
    locked = datetime.fromisoformat(quote_locked_at.replace("Z", "+00:00"))
    return (locked + timedelta(seconds=WISE_QUOTE_TTL_SECONDS)).isoformat()


async def is_quote_fresh(db, wise_quote_id: str) -> bool:
    """Check whether an active Wise quote is still within internal TTL."""
    doc = await db.wise_quotes.find_one({"wise_quote_id": wise_quote_id})
    if not doc:
        return False
    expiry = doc.get("expires_at_internal") or compute_quote_internal_expiry(
        doc.get("quote_locked_at") or datetime.now(timezone.utc).isoformat()
    )
    return datetime.fromisoformat(expiry.replace("Z", "+00:00")) > datetime.now(timezone.utc)


async def invalidate_stale_quotes(db) -> int:
    """Mark all active quotes past internal TTL as expired."""
    now_iso = datetime.now(timezone.utc).isoformat()
    # Compute a cutoff (any quote older than 5dk)
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=WISE_QUOTE_TTL_SECONDS)).isoformat()
    res = await db.wise_quotes.update_many(
        {
            "status": "active",
            "$or": [
                {"expires_at_internal": {"$lt": now_iso}},
                {"expires_at_internal": {"$exists": False}, "quote_locked_at": {"$lt": cutoff}},
            ],
        },
        {"$set": {"status": "expired", "expired_at": now_iso}},
    )
    if res.modified_count:
        logger.info("wise_quotes expired: count=%d", res.modified_count)
    return res.modified_count


# ---------------------------------------------------------------------------
# Exchange Rate Freshness
# ---------------------------------------------------------------------------

async def is_rate_fresh(db, pair: str = "GBP_TRY") -> bool:
    doc = await db.exchange_rates.find_one({"pair": pair, "is_current": True})
    if not doc:
        return False
    fetched = datetime.fromisoformat((doc.get("fetched_at") or "").replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age < EXCHANGE_RATE_TTL_SECONDS


# ---------------------------------------------------------------------------
# Reserve Expiry (reserved_for_batch → available rollback)
# ---------------------------------------------------------------------------

async def expire_stale_reserves(db) -> Dict[str, Any]:
    """
    Find reserved_for_batch transactions older than 7 days and roll back to available.
    Called hourly by reserve_expiry_cron.
    """
    from .state_machine import StateMachine

    cutoff = (datetime.now(timezone.utc) - timedelta(days=RESERVE_EXPIRY_DAYS)).isoformat()
    cursor = db.merchant_transactions.find({
        "state": {"$in": ["reserved_for_batch", "reserved"]},
        "$or": [
            {"reserved_at": {"$lt": cutoff}},
            # Fallback: state_history entry
            {"updated_at": {"$lt": cutoff}, "reserved_at": {"$exists": False}},
        ],
    }).limit(200)

    expired_txs: List[Dict[str, Any]] = []
    sm = StateMachine(db)
    async for tx in cursor:
        tx_id = tx["id"]
        try:
            await sm.transition(
                tx_id=tx_id,
                new_state="available",
                trigger="reserve_expiry_rollback",
                metadata={"expiry_rollback_at": datetime.now(timezone.utc).isoformat()},
            )
            expired_txs.append({
                "tx_id": tx_id,
                "organization_id": tx.get("organization_id"),
                "amount_minor": tx.get("amount_display_minor", 0),
            })
        except Exception as e:
            logger.warning("reserve expiry rollback failed tx=%s err=%s", tx_id, e)

    if expired_txs:
        logger.info("reserve_expiry: rolled_back=%d", len(expired_txs))

        # Group by organization for a single email per merchant
        try:
            from .notifications_v2 import send_slack
            by_org: Dict[str, int] = {}
            for item in expired_txs:
                oid = item.get("organization_id") or ""
                by_org[oid] = by_org.get(oid, 0) + int(item.get("amount_minor") or 0)
            for org_id, total_minor in by_org.items():
                if not org_id:
                    continue
                send_slack(
                    f":recycle: Rezerv süresi doldu (geri alındı): org={org_id[:12]}",
                    fields={"Tutar (minor)": total_minor, "İşlem sayısı": sum(
                        1 for x in expired_txs if x.get("organization_id") == org_id
                    )},
                )
        except Exception as e:
            logger.warning("reserve_expiry notification failed (non-blocking): %s", e)

    return {"expired_count": len(expired_txs), "items": expired_txs}


# ---------------------------------------------------------------------------
# Unified entry
# ---------------------------------------------------------------------------

async def run_expiry_crons(db) -> Dict[str, Any]:
    """Single entry point called hourly by APScheduler."""
    try:
        stale_quotes = await invalidate_stale_quotes(db)
    except Exception as e:
        logger.exception("invalidate_stale_quotes failed: %s", e)
        stale_quotes = 0

    try:
        reserve_result = await expire_stale_reserves(db)
    except Exception as e:
        logger.exception("expire_stale_reserves failed: %s", e)
        reserve_result = {"error": str(e)}

    return {
        "stale_quotes_expired": stale_quotes,
        "reserve_expiry": reserve_result,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
