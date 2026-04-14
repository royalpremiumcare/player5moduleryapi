"""
PLANN Financial Engine — Currency Shield

Only active for TRY market. GBP market has no FX risk.
Fetches current GBP/TRY rate, recalculates TRY tier limits so that
each tier's payout threshold always covers the target GBP equivalent
plus Wise cross-border fees.

Runs nightly via currency_shield_job cron.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

import requests

from .money import (
    rate_to_micro,
    rate_from_micro,
    apply_rate,
    update_try_tier_limit,
    get_all_tiers,
    RATE_MULTIPLIER,
)
from .schemas import ExchangeRate

logger = logging.getLogger(__name__)

WISE_API_BASE = "https://api.transferwise.com"
WISE_SANDBOX_API_BASE = "https://api.sandbox.transferwise.tech"
FAWAZ_CURRENCY_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/gbp.json"

SPIKE_THRESHOLD_PERCENT = 10
SAFETY_BUFFER_BPS = 200  # +2.0% buffer on mid-market rate to cover Wise spread + GBP/TRY volatility


def _wise_api_base() -> str:
    env = os.getenv("WISE_ENVIRONMENT", "sandbox")
    return WISE_SANDBOX_API_BASE if env == "sandbox" else WISE_API_BASE


def _wise_headers() -> dict:
    token = os.getenv("WISE_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def fetch_current_rate(db) -> Tuple[int, str]:
    """
    Fetch current GBP/TRY rate.
    Primary: open.er-api.com (free, reliable, mid-market)
    Fallback 1: ECB (exchangerate.host)
    Fallback 2: Wise API

    A safety buffer (+2.0%) is applied to the mid-market rate to cover
    Wise's cross-border spread and GBP/TRY volatility.
    Returns (rate_micro_with_buffer, source).
    """
    rate_micro, source = _fetch_tcmb_rate()  # open.er-api.com (primary)
    if rate_micro == 0:
        rate_micro, source = _fetch_fawaz_rate()  # jsdelivr CDN fallback
    if rate_micro == 0:
        rate_micro, source = _fetch_wise_rate()
    if rate_micro == 0:
        logger.error("Failed to fetch GBP/TRY rate from all sources")
        raise RuntimeError("Could not fetch exchange rate")

    # Apply safety buffer: rate * (1 + 2.0%) so TRY tier limits are slightly
    # higher than the raw mid-market rate, covering Wise spread + volatility.
    buffered = rate_micro + (rate_micro * SAFETY_BUFFER_BPS + 5_000) // 10_000
    logger.info(
        "Currency Shield: raw rate=%d buffered(+%dbps)=%d source=%s",
        rate_micro, SAFETY_BUFFER_BPS, buffered, source,
    )
    return buffered, source


def _fetch_wise_rate() -> Tuple[int, str]:
    """Fetch rate from Wise API."""
    try:
        url = f"{_wise_api_base()}/v1/rates?source=GBP&target=TRY"
        resp = requests.get(url, headers=_wise_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data and len(data) > 0:
            from decimal import Decimal
            rate = Decimal(str(data[0]["rate"]))
            return rate_to_micro(rate), "wise_rate"
    except Exception as e:
        logger.warning("Wise rate fetch failed: %s", e)
    return 0, ""


def _fetch_tcmb_rate() -> Tuple[int, str]:
    """Fallback: fetch GBP/TRY rate from open.er-api.com (free, reliable)."""
    try:
        resp = requests.get(
            "https://open.er-api.com/v6/latest/GBP",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") == "success" and "TRY" in data.get("rates", {}):
            from decimal import Decimal
            rate = Decimal(str(data["rates"]["TRY"]))
            return rate_to_micro(rate), "open_er_api"
    except Exception as e:
        logger.warning("open.er-api rate fetch failed: %s", e)
    return 0, ""


def _fetch_fawaz_rate() -> Tuple[int, str]:
    """Fallback: fetch rate from fawazahmed0 currency API (jsdelivr CDN)."""
    try:
        resp = requests.get(FAWAZ_CURRENCY_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        try_rate = data.get("gbp", {}).get("try")
        if try_rate:
            from decimal import Decimal
            rate = Decimal(str(try_rate))
            return rate_to_micro(rate), "fawaz_cdn"
    except Exception as e:
        logger.warning("Fawaz CDN rate fetch failed: %s", e)
    return 0, ""


async def recalculate_try_tier_limits(
    db,
    new_rate_micro: int,
    source: str = "wise_rate",
) -> Dict[str, Any]:
    """
    Recalculate TRY tier payout limits based on new GBP/TRY rate.

    For each tier:
      new_limit_kurus = (gbp_target_pence * rate_micro) / RATE_MULTIPLIER

    Persists new exchange_rates document and updates in-memory tier config.
    Returns the saved exchange_rate document.
    """
    now = datetime.now(timezone.utc).isoformat()
    try_tiers = get_all_tiers("TRY")
    new_limits = {}
    tier_targets = {}

    for tier_name, cfg in try_tiers.items():
        new_limit = apply_rate(cfg.gbp_target_minor, new_rate_micro)
        # Round up to nearest 1000 kuruş (₺10) for clean UX
        new_limit = ((new_limit + 99_999) // 100_000) * 100_000
        new_limits[tier_name] = new_limit
        tier_targets[tier_name] = cfg.gbp_target_minor

        update_try_tier_limit(tier_name, new_limit)
        logger.info(
            "Currency Shield: TRY tier '%s' limit updated to %d kuruş (target: %d pence)",
            tier_name, new_limit, cfg.gbp_target_minor,
        )

    # Mark old rates as not current
    await db.exchange_rates.update_many(
        {"is_current": True},
        {"$set": {"is_current": False}},
    )

    # Save new rate
    rate_doc = ExchangeRate(
        pair="GBP_TRY",
        rate_micro=new_rate_micro,
        source=source,
        try_tier_limits_minor=new_limits,
        try_tier_targets_gbp_minor=tier_targets,
        fetched_at=now,
        is_current=True,
    ).model_dump()

    await db.exchange_rates.insert_one(rate_doc)

    return rate_doc


async def check_rate_spike(db, new_rate_micro: int) -> Optional[Dict[str, Any]]:
    """
    Check if the new rate represents a significant spike from the previous rate.
    Returns spike info dict if spike detected, None otherwise.
    """
    prev = await db.exchange_rates.find_one(
        {"pair": "GBP_TRY"},
        sort=[("fetched_at", -1)],
    )

    if not prev or prev.get("rate_micro", 0) == 0:
        return None

    old_rate = prev["rate_micro"]
    change_pct = abs(new_rate_micro - old_rate) * 100 / old_rate

    if change_pct >= SPIKE_THRESHOLD_PERCENT:
        return {
            "old_rate_micro": old_rate,
            "new_rate_micro": new_rate_micro,
            "change_pct": round(change_pct, 2),
            "direction": "up" if new_rate_micro > old_rate else "down",
            "old_rate_display": str(rate_from_micro(old_rate)),
            "new_rate_display": str(rate_from_micro(new_rate_micro)),
        }

    return None


async def get_current_rate(db) -> Optional[Dict[str, Any]]:
    """Get the most recent exchange rate document from DB."""
    return await db.exchange_rates.find_one(
        {"pair": "GBP_TRY"},
        sort=[("fetched_at", -1)],
    )


async def ensure_fresh_exchange_rate(
    db,
    max_age_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    SuperAdmin / finans ekranı için: DB'deki kur çok eskiyse yeniden çek.
    Varsayılan 300 sn (5 dk) — cron yerine panel açılışında güncel kur.
    """
    doc = await get_current_rate(db)
    now = datetime.now(timezone.utc)
    need_fetch = doc is None
    if doc and doc.get("fetched_at"):
        try:
            ft = doc["fetched_at"]
            if isinstance(ft, str):
                fetched = datetime.fromisoformat(ft.replace("Z", "+00:00"))
            elif isinstance(ft, datetime):
                fetched = ft if ft.tzinfo else ft.replace(tzinfo=timezone.utc)
            else:
                fetched = None
            if fetched and (now - fetched).total_seconds() < max_age_seconds:
                need_fetch = False
        except Exception:
            need_fetch = True
    if not need_fetch:
        return doc
    try:
        rate_micro, source = await fetch_current_rate(db)
        await recalculate_try_tier_limits(db, rate_micro, source)
    except Exception as e:
        logger.warning("ensure_fresh_exchange_rate: yenileme başarısız: %s", e, exc_info=True)
    return await get_current_rate(db)
