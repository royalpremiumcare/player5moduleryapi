"""
20261119_payout_batch_idempotency_index — one payout batch per org per day.

Unique index on payout_batches.idempotency_key, partial on {idempotency_enforced: true}.
New batches (financial/wednesday_batch.py) set the flag; the 3 legacy partial_failure
batches that share a key do not, so the build does not fail on them.

Startup-safe: the explicit name never collides with an auto-named `idempotency_key_1`
index, and Mongo lets a partial index coexist with a non-partial one on the same key.
Re-running with the same spec is a no-op (every worker runs pending migrations), and an
equivalent index under another name is accepted.
"""

from pymongo.errors import OperationFailure

from financial.schemas import PAYOUT_BATCH_IDEMPOTENCY_INDEX as SPEC

REVERSIBLE = True
DESCRIPTION = "payout_batches: partial unique index on idempotency_key (idempotency_enforced: true)"


async def _equivalent_index_exists(db) -> bool:
    for idx in (await db.payout_batches.index_information()).values():
        if (
            list(idx.get("key", [])) == list(SPEC["keys"])
            and idx.get("unique")
            and idx.get("partialFilterExpression") == SPEC["partialFilterExpression"]
        ):
            return True
    return False


async def up(db):
    try:
        await db.payout_batches.create_index(
            SPEC["keys"],
            name=SPEC["name"],
            unique=True,
            partialFilterExpression=SPEC["partialFilterExpression"],
        )
    except OperationFailure as e:
        # 85 IndexOptionsConflict: the same index exists under another name (hand-made).
        # The guarantee is already in place; anything else is a real conflict.
        if e.code == 85 and await _equivalent_index_exists(db):
            return
        raise


async def down(db):
    try:
        await db.payout_batches.drop_index(SPEC["name"])
    except OperationFailure:
        pass  # already gone
