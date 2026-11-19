"""Payout batch idempotency index against a real throwaway MongoDB.

Skipped unless PK_TEST_MONGO_URL is set (same switch as the other *_mongo tests).
"""
import importlib
import os
import uuid

import pytest
import pytest_asyncio
from pymongo.errors import DuplicateKeyError

from financial.migrations import runner

MONGO_URL = os.environ.get("PK_TEST_MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="PK_TEST_MONGO_URL not set")

MIGRATION = "20261119_payout_batch_idempotency_index"
LEGACY_KEY = "batch:org-legacy:2026-05-05"


def _migration():
    return importlib.import_module(f"financial.migrations.{MIGRATION}")


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    name = f"payout_idx_test_{uuid.uuid4().hex[:12]}"
    try:
        yield client[name]
    finally:
        await client.drop_database(name)
        client.close()


async def _seed_legacy(db):
    await db.payout_batches.insert_many([
        {"id": f"legacy-{i}", "status": "partial_failure", "idempotency_key": LEGACY_KEY}
        for i in range(3)
    ])


async def _assert_enforced(db):
    info = await db.payout_batches.index_information()
    idx = info["idempotency_key_enforced_unique"]
    assert idx["key"] == [("idempotency_key", 1)]
    assert idx["unique"] is True
    assert idx["partialFilterExpression"] == {"idempotency_enforced": True}
    await db.payout_batches.insert_one({"id": "n1", "idempotency_key": LEGACY_KEY, "idempotency_enforced": True})
    with pytest.raises(DuplicateKeyError):
        await db.payout_batches.insert_one({"id": "n2", "idempotency_key": LEGACY_KEY, "idempotency_enforced": True})
    # legacy-style docs (no flag) are still accepted
    await db.payout_batches.insert_one({"id": "l4", "idempotency_key": LEGACY_KEY})


async def test_runner_builds_index_over_three_legacy_duplicates(db):
    await _seed_legacy(db)
    result = await runner.apply_all(db)
    assert result["errors"] == []
    assert MIGRATION in result["applied"]
    await _assert_enforced(db)


async def test_up_coexists_with_plain_idempotency_key_index_and_is_rerunnable(db):
    await _seed_legacy(db)
    await db.payout_batches.create_index("idempotency_key")  # auto-named idempotency_key_1
    await _migration().up(db)
    await _migration().up(db)  # 17 workers each run pending migrations
    assert "idempotency_key_1" in await db.payout_batches.index_information()
    await _assert_enforced(db)


async def test_up_accepts_equivalent_index_under_another_name(db):
    await _seed_legacy(db)
    await db.payout_batches.create_index(
        "idempotency_key", name="handmade", unique=True,
        partialFilterExpression={"idempotency_enforced": True},
    )
    await _migration().up(db)  # Mongo raises IndexOptionsConflict; same guarantee exists
    await db.payout_batches.insert_one({"id": "n1", "idempotency_key": "k", "idempotency_enforced": True})
    with pytest.raises(DuplicateKeyError):
        await db.payout_batches.insert_one({"id": "n2", "idempotency_key": "k", "idempotency_enforced": True})


async def test_up_still_fails_on_a_real_conflict(db):
    from pymongo.errors import OperationFailure
    await db.payout_batches.create_index("idempotency_key", name="idempotency_key_enforced_unique")
    with pytest.raises(OperationFailure):
        await _migration().up(db)


async def test_down_drops_only_its_index(db):
    await _seed_legacy(db)
    await _migration().up(db)
    await _migration().down(db)
    await _migration().down(db)
    assert "idempotency_key_enforced_unique" not in await db.payout_batches.index_information()
