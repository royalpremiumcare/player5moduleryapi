"""Read-only, revocable widget keys. A key authorises only GET /api/widget/summary.

Only the sha256 of a key is stored; the raw value is returned once, at issue time.
Revoking deletes the row, so "revoked" and "unknown" are the same state.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

KEY_TTL = timedelta(days=90)
MAX_KEYS_PER_USER = 5
LAST_USED_EVERY = timedelta(minutes=10)
RATE_LIMIT = 120
RATE_WINDOW_SECONDS = 3700


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _utc(moment: datetime) -> datetime:
    """Mongo hands datetimes back naive (UTC); treat those as UTC."""
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


async def ensure_indexes(db) -> None:
    await db.widget_keys.create_index("key_hash", unique=True)
    await db.widget_keys.create_index("expires_at", expireAfterSeconds=0)
    await db.widget_keys.create_index([("username", 1), ("created_at", 1)])


async def issue_key(db, user: dict, *, now: datetime) -> tuple[str, datetime]:
    """Create a key for `user` and drop the oldest ones beyond MAX_KEYS_PER_USER."""
    now = _utc(now)
    expires_at = now + KEY_TTL
    while True:
        raw = secrets.token_urlsafe(32)
        try:
            await db.widget_keys.insert_one({
                "key_hash": hash_key(raw), "username": user["username"],
                "organization_id": user.get("organization_id"),
                "created_at": now, "last_used_at": None, "expires_at": expires_at,
            })
            break
        except DuplicateKeyError:  # astronomically unlikely; draw again
            continue
    rows = await db.widget_keys.find({"username": user["username"]}, {"_id": 1, "key_hash": 1, "created_at": 1}) \
        .sort([("created_at", 1), ("_id", 1)]).to_list(None)
    for old in rows[:-MAX_KEYS_PER_USER]:
        await db.widget_keys.delete_one({"key_hash": old["key_hash"]})
    return raw, expires_at


async def revoke(db, username: str, key: str | None) -> int:
    """Revoke one key of `username`, or all of them when `key` is None. Returns how many."""
    flt = {"username": username}
    if key is not None:
        flt["key_hash"] = hash_key(key)
    return (await db.widget_keys.delete_many(flt)).deleted_count


async def resolve(db, raw_key: str, *, now: datetime) -> dict | None:
    """The stored row for a live key, or None when unknown, revoked or expired.
    Bumps last_used_at at most once per LAST_USED_EVERY."""
    now = _utc(now)
    row = await db.widget_keys.find_one({"key_hash": hash_key(raw_key)})
    if row is None or _utc(row["expires_at"]) <= now:
        return None
    last = row.get("last_used_at")
    if last is None or _utc(last) <= now - LAST_USED_EVERY:
        await db.widget_keys.update_one({"key_hash": row["key_hash"]}, {"$set": {"last_used_at": now}})
    return row


async def within_rate_limit(redis, key_hash: str, *, now: datetime) -> bool:
    """Fixed window of RATE_LIMIT per key per hour. Never blocks when Redis is missing or down."""
    if not redis:
        return True
    window = f"widget_rl:{key_hash}:{now.strftime('%Y%m%d%H')}"
    try:
        count = await redis.incr(window)
        await redis.expire(window, RATE_WINDOW_SECONDS)  # every call: a lost EXPIRE can't orphan the counter
        return count <= RATE_LIMIT
    except Exception as exc:  # the widget must never break because of Redis
        logger.warning("widget rate limit skipped: %s", exc)
        return True
