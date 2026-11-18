"""Startup creation of the partial unique customers phone_key index."""
import logging

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
