"""The partial unique customers phone_key index (created by the rollout script, re-ensured
at startup only once the rollout marked it applied)."""
import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError, OperationFailure

logger = logging.getLogger(__name__)

INDEX_NAME = "customers_org_phone_key_unique"
INDEX_KEYS = [("organization_id", 1), ("phone_key", 1)]
PARTIAL_FILTER = {"phone_key": {"$exists": True}}
_SPEC_CONFLICT_CODES = (85, 86)


def _is_exact(info) -> bool:
    if not info:
        return False
    keys = [tuple(k) for k in info.get("key", [])]
    return (
        keys == INDEX_KEYS
        and info.get("unique") is True
        and info.get("partialFilterExpression") == PARTIAL_FILTER
    )


async def _existing(customers):
    return (await customers.index_information()).get(INDEX_NAME)


async def ensure_customer_indexes(db) -> str:
    """Returns "created", "exists" or "skipped_duplicates". Never raises."""
    try:
        customers = db.customers
        if _is_exact(await _existing(customers)):
            return "exists"
        try:
            await customers.create_index(
                INDEX_KEYS,
                name=INDEX_NAME,
                unique=True,
                partialFilterExpression=PARTIAL_FILTER,
            )
            return "created"
        except DuplicateKeyError as exc:
            return _duplicates(exc)
        except OperationFailure as exc:
            if exc.code == 11000:
                return _duplicates(exc)
            if exc.code in _SPEC_CONFLICT_CODES and _is_exact(await _existing(customers)):
                return "exists"
            raise
    except Exception:
        logger.exception("%s could not be ensured (not created)", INDEX_NAME)
        return "skipped_duplicates"


def _duplicates(exc) -> str:
    logger.warning("%s skipped: duplicate phone_key values exist (%s)", INDEX_NAME, exc)
    return "skipped_duplicates"


# Written to ``db.migration_log`` by ``scripts/customer_phone_key.py index --apply`` once the
# index exists (rollout step 4). Until then startup must not build the index by itself.
INDEX_MARKER = "customer_phone_key_index"
INDEX_MARKER_STATUS = "applied"


async def write_index_marker(db) -> None:
    """Upsert the marker; an already applied marker is left as it is (re-runs write nothing)."""
    if await db.migration_log.find_one({"name": INDEX_MARKER, "status": INDEX_MARKER_STATUS},
                                       {"_id": 1}):
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.migration_log.update_one(
        {"name": INDEX_MARKER},
        {"$set": {"name": INDEX_MARKER, "status": INDEX_MARKER_STATUS, "applied_at": now,
                  "reversible": False, "note": f"{INDEX_NAME} created by the rollout script",
                  "rolled_back_at": None}},
        upsert=True,
    )


async def ensure_customer_indexes_if_applied(db) -> str:
    """Startup entry: ensure the index only after the rollout's index step marked it.

    Returns ``"skipped_no_marker"`` without touching the index otherwise. Never raises.
    """
    try:
        marker = await db.migration_log.find_one(
            {"name": INDEX_MARKER, "status": INDEX_MARKER_STATUS}, {"_id": 1})
    except Exception:
        logger.exception("%s: could not read the rollout marker; index not ensured", INDEX_NAME)
        return "skipped_no_marker"
    if marker is None:
        logger.info("%s not ensured at startup: rollout index step not applied yet", INDEX_NAME)
        return "skipped_no_marker"
    return await ensure_customer_indexes(db)
