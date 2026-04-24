"""
Multi-Layer Rate Limiter — IP + account + phone + device.

Redis-based sliding counters with configurable limits per endpoint.
Gated by FEATURE_MULTI_LAYER_RATE_LIMIT env flag (fallback: slowapi only).

Usage:
    @app.post("/api/public/appointments")
    async def create_appointment(request: Request, body: ...):
        await enforce_multi_layer(
            request,
            redis_client,
            limits={
                "ip": ("plann:rate:ip:appt:{ip}", "15/12h"),
                "phone": ("plann:rate:phone:appt:{phone}", "5/1h"),
            },
            context={"phone": body.customer_phone},
        )

See plan Bölüm 7.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


_WINDOW_PATTERN = re.compile(r"^(\d+)/(\d+)?([smhd])?$")


def _parse_limit(spec: str) -> Tuple[int, int]:
    """
    Parse '15/12h' → (15, 43200). '5/1h' → (5, 3600). '10/min' → (10, 60).
    Returns (max_requests, window_seconds).
    """
    spec = spec.strip().lower().replace(" ", "")
    # Handle '10/minute' etc.
    unit_aliases = {"sec": "s", "second": "s", "seconds": "s",
                    "min": "m", "minute": "m", "minutes": "m",
                    "hour": "h", "hours": "h", "day": "d", "days": "d"}
    for alias, short in unit_aliases.items():
        spec = spec.replace(f"/{alias}", f"/1{short}")

    m = _WINDOW_PATTERN.match(spec)
    if not m:
        raise ValueError(f"invalid rate limit spec: {spec!r}")
    max_req = int(m.group(1))
    mult = int(m.group(2) or "1")
    unit = m.group(3) or "s"
    unit_sec = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return max_req, mult * unit_sec


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("X-Real-IP")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def _device_id(request: Request) -> str:
    return request.headers.get("X-Device-Id") or "anon"


def _normalize_phone(phone: str) -> str:
    """Keep only last 10 digits for cross-country normalization."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if digits else ""


async def _check_redis_counter(
    redis_client, key: str, max_req: int, window_sec: int
) -> Tuple[bool, int, int]:
    """
    Redis-based sliding window counter (simple fixed-window variant using INCR + EXPIRE).
    Returns (allowed, current_count, retry_after_seconds).
    """
    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_sec, nx=True)  # only set TTL if new
        results = await pipe.execute()
        count = int(results[0])
        if count > max_req:
            ttl = await redis_client.ttl(key)
            return False, count, max(1, ttl)
        return True, count, 0
    except Exception as e:
        # Fail-open: if Redis is down, allow the request but log
        logger.error("rate_limit Redis error (allowing): %s", e)
        return True, 0, 0


async def enforce_multi_layer(
    request: Request,
    redis_client,
    *,
    limits: Dict[str, Tuple[str, str]],
    context: Optional[Dict[str, Any]] = None,
    allow_if_redis_down: bool = True,
) -> None:
    """
    Enforce a set of rate-limit layers. Raises HTTPException(429) if any layer is exceeded.

    Args:
        limits: {"layer_name": ("redis_key_template", "15/12h"), ...}
            Key template may contain placeholders: {ip}, {phone}, {account}, {device}
        context: Extra values for key template ({phone}, {account})
    """
    from financial.feature_flags import is_env_flag_enabled

    if not is_env_flag_enabled("FEATURE_MULTI_LAYER_RATE_LIMIT"):
        return  # short-circuit if flag off

    if redis_client is None:
        if allow_if_redis_down:
            return
        raise HTTPException(status_code=503, detail="rate_limiter_unavailable")

    ctx = dict(context or {})
    ctx.setdefault("ip", _client_ip(request))
    ctx.setdefault("device", _device_id(request))
    if "phone" in ctx:
        ctx["phone"] = _normalize_phone(ctx["phone"])

    for layer_name, (key_template, limit_spec) in limits.items():
        try:
            key = key_template.format(**{k: (v or "-") for k, v in ctx.items()})
        except KeyError as e:
            logger.warning("rate_limit missing context for layer=%s: %s", layer_name, e)
            continue

        # Skip layer if the relevant context is empty
        if any(sentinel in key for sentinel in ("{", "}-phone-", ":-:")):
            continue

        try:
            max_req, window = _parse_limit(limit_spec)
        except ValueError as e:
            logger.error("rate_limit parse error: %s", e)
            continue

        allowed, count, retry_after = await _check_redis_counter(
            redis_client, key, max_req, window,
        )
        if not allowed:
            logger.warning(
                "rate_limit exceeded: layer=%s key=%s count=%d max=%d retry_after=%d",
                layer_name, key, count, max_req, retry_after,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "layer": layer_name,
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )


# ---------------------------------------------------------------------------
# Preset limit profiles per plan Bölüm 7
# ---------------------------------------------------------------------------

LIMIT_PROFILES = {
    "login": {
        "ip": ("plann:rl:ip:login:{ip}", "5/min"),
        "account": ("plann:rl:acc:login:{account}", "10/min"),
    },
    "whatsapp_verify": {
        "ip": ("plann:rl:ip:waverify:{ip}", "3/min"),
        "phone": ("plann:rl:phone:waverify:{phone}", "3/hour"),
    },
    "public_booking": {
        "ip": ("plann:rl:ip:booking:{ip}", "15/12h"),
        "phone": ("plann:rl:phone:booking:{phone}", "5/hour"),
    },
    "customer_register": {
        "ip": ("plann:rl:ip:custreg:{ip}", "10/hour"),
        "phone": ("plann:rl:phone:custreg:{phone}", "5/hour"),
    },
    "ai_chat": {
        "ip": ("plann:rl:ip:ai:{ip}", "60/min"),
        "account": ("plann:rl:acc:ai:{account}", "300/min"),
        "device": ("plann:rl:dev:ai:{device}", "100/min"),
    },
    "payment_checkout": {
        "ip": ("plann:rl:ip:checkout:{ip}", "10/min"),
        "account": ("plann:rl:acc:checkout:{account}", "30/hour"),
    },
    "refund_request": {
        "account": ("plann:rl:acc:refundreq:{account}", "5/hour"),
    },
    "customer_search": {
        "ip": ("plann:rl:ip:custsearch:{ip}", "30/min"),
        "account": ("plann:rl:acc:custsearch:{account}", "200/hour"),
    },
}


def get_profile(name: str) -> Dict[str, Tuple[str, str]]:
    return LIMIT_PROFILES.get(name, {})
