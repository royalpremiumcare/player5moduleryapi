"""Redis distributed lock with owner token, for scheduled jobs.

The backend runs many uvicorn workers; each scheduled job must run once per tick.
`with_distributed_lock` yields True when this caller holds the lock. Release is
compare-and-delete (Lua) so an expired lock taken over by another worker is
never deleted by the previous holder.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Callable, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Same source as REDIS_URL in financial/cron_jobs.py
REDIS_URL = os.getenv("REDIS_URL", "redis://plann_redis:6379/0")
LOCK_PREFIX = "plann:lock:"
# Seconds; bounds every Redis call so a black-holed Redis cannot hang the scheduler.
REDIS_TIMEOUT = 5

RELEASE_SCRIPT = (
    'if redis.call("get", KEYS[1]) == ARGV[1] then '
    'return redis.call("del", KEYS[1]) else return 0 end'
)


def _default_factory():
    return aioredis.from_url(
        REDIS_URL, socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT
    )


@asynccontextmanager
async def with_distributed_lock(
    name: str,
    *,
    ttl: int,
    fail_closed: bool,
    redis_factory: Optional[Callable] = None,
):
    """Yield True if the lock was acquired. `ttl` is in seconds.

    Redis error on acquire yields `not fail_closed`. Release errors are logged,
    never raised.
    """
    key = f"{LOCK_PREFIX}{name}"
    token = uuid.uuid4().hex
    client = None
    acquired = False
    try:
        client = (redis_factory or _default_factory)()
        acquired = bool(
            await asyncio.wait_for(
                client.set(key, token, nx=True, px=int(ttl * 1000)), timeout=REDIS_TIMEOUT
            )
        )
        holds_lock = acquired
    except Exception as exc:
        holds_lock = False
        acquired = not fail_closed
        if fail_closed:
            logger.warning("Lock %s: Redis unreachable (%r); skipping run (fail-closed)", name, exc)
        else:
            logger.warning("Lock %s: Redis unreachable (%r); running without lock (fail-open)", name, exc)
    try:
        yield acquired
    finally:
        if client is not None:
            if holds_lock:
                try:
                    await asyncio.wait_for(
                        client.eval(RELEASE_SCRIPT, 1, key, token), timeout=REDIS_TIMEOUT
                    )
                except Exception as exc:
                    logger.warning("Lock %s: release failed: %r", name, exc)
            try:
                await asyncio.wait_for(client.aclose(), timeout=REDIS_TIMEOUT)
            except Exception as exc:
                logger.warning("Lock %s: close failed: %r", name, exc)
