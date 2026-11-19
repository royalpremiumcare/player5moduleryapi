"""Faz 6 Task 3: payout batch correctness.

- One batch per org per day (partial unique index on idempotency_key); a losing
  worker rolls back only its own reservations.
- Batch total == sum of the items this worker actually reserved.
- Reserve expiry closes open batches that are left with no held items.
- Funding paths refuse stale or no-longer-held batches.
- tuesday_batch_prepare and dlq_retry run once across workers (lock inside the function).
"""
import asyncio
import importlib
from datetime import datetime, timedelta, timezone

import pytest
from pymongo.errors import DuplicateKeyError

from financial import dead_letter_queue, distributed_lock, wednesday_batch
from financial.migrations import runner
from tests.payout_batch_fakes import FakeDB
from tests.test_distributed_lock import LockRedis

ORG = "org-1"
OTHER_BATCH = "batch-other"
MIGRATION = "20261119_payout_batch_idempotency_index"


def _iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _today_key(org=ORG):
    return f"batch:{org}:{datetime.now(timezone.utc).isoformat()[:10]}"


def _install_unique_index(db):
    """The index prod has after the migration (spec asserted separately below)."""
    db.payout_batches.indexes["idempotency_key_enforced_unique"] = {
        "key": [("idempotency_key", 1)],
        "unique": True,
        "partialFilterExpression": {"idempotency_enforced": True},
    }


def _seed_wallet(db, amounts, threshold, *, org=ORG, extra_reserved=0):
    db.settings.docs.append({
        "organization_id": org, "base_currency": "TRY",
        "payout_threshold_override_minor": threshold,
    })
    db.merchant_wallets.docs.append({
        "organization_id": org, "base_currency": "TRY", "wallet_status": "active",
        "available_balance_minor": sum(amounts), "reserved_balance_minor": extra_reserved,
    })
    for i, amt in enumerate(amounts, start=1):
        db.merchant_transactions.docs.append({
            "id": f"t{i}", "organization_id": org, "state": "available",
            "amount_display_minor": amt, "base_currency": "TRY",
            "created_at": f"2026-11-0{i}T10:00:00+00:00", "state_history": [],
        })


def _tx(db, tx_id):
    return next(d for d in db.merchant_transactions.docs if d["id"] == tx_id)


def _wallet(db, org=ORG):
    return next(d for d in db.merchant_wallets.docs if d["organization_id"] == org)


def _batch(db, batch_id):
    return next(d for d in db.payout_batches.docs if d["id"] == batch_id)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("FEATURE_WEDNESDAY_BATCH", "true")
    from financial import notifications_v2
    monkeypatch.setattr(notifications_v2, "send_slack", lambda *a, **k: False)
    d = FakeDB()
    _install_unique_index(d)
    return d


def _reservation_pause(db, *, after_n):
    """Pause the first worker after it reserved `after_n` items; returns (paused, gate)."""
    paused, gate = asyncio.Event(), asyncio.Event()
    state = {"batch": None, "count": 0}

    async def hook(flt, update):
        s = update.get("$set", {})
        if s.get("state") != "reserved_for_batch":
            return
        if state["batch"] is None:
            state["batch"] = s["payout_batch_id"]
        if s["payout_batch_id"] != state["batch"]:
            return
        state["count"] += 1
        if state["count"] == after_n:
            paused.set()
            await gate.wait()

    db.merchant_transactions.after_update.append(hook)
    return paused, gate


# ---------------------------------------------------------------------------
# Prepare: idempotency + amount
# ---------------------------------------------------------------------------

async def test_concurrent_prepare_one_batch_amount_equals_reserved(db):
    _seed_wallet(db, [100, 100, 100, 100], threshold=150)
    paused, gate = _reservation_pause(db, after_n=2)

    first = asyncio.create_task(wednesday_batch._tuesday_batch_prepare_body(db))
    await paused.wait()                                   # worker 1 holds t1, t2
    await wednesday_batch._tuesday_batch_prepare_body(db)  # worker 2 takes t3, t4
    gate.set()
    await first                                           # worker 1 loses t3, t4

    assert len(db.payout_batches.docs) == 1
    batch = db.payout_batches.docs[0]
    held = [d for d in db.merchant_transactions.docs
            if d["state"] == "reserved_for_batch" and d.get("payout_batch_id") == batch["id"]]
    assert sorted(d["id"] for d in held) == ["t3", "t4"]
    assert sorted(batch["item_transaction_ids"]) == ["t3", "t4"]
    assert batch["total_amount_minor"] == 200
    assert batch["idempotency_enforced"] is True
    assert _tx(db, "t1")["state"] == "available"
    assert _tx(db, "t2")["state"] == "available"
    assert _wallet(db)["reserved_balance_minor"] == 200
    assert _wallet(db)["available_balance_minor"] == 200


async def test_duplicate_key_rolls_back_orphan_reserves(db):
    _seed_wallet(db, [100, 100], threshold=150, extra_reserved=500)
    # Another worker already built today's batch from an item outside this scan.
    db.merchant_transactions.docs.append({
        "id": "t9", "organization_id": ORG, "state": "reserved_for_batch",
        "payout_batch_id": OTHER_BATCH, "amount_display_minor": 500, "state_history": [],
    })
    db.payout_batches.docs.append({
        "id": OTHER_BATCH, "organization_id": ORG, "status": "awaiting_admin_fund",
        "item_transaction_ids": ["t9"], "total_amount_minor": 500,
        "idempotency_key": _today_key(), "idempotency_enforced": True, "created_at": _iso(),
    })

    result = await wednesday_batch._tuesday_batch_prepare_body(db)

    assert result["batches_created"] == 0
    assert [b["id"] for b in db.payout_batches.docs] == [OTHER_BATCH]
    assert _tx(db, "t1")["state"] == "available"
    assert _tx(db, "t2")["state"] == "available"
    assert _tx(db, "t9")["state"] == "reserved_for_batch"
    assert _tx(db, "t9")["payout_batch_id"] == OTHER_BATCH
    assert _wallet(db)["available_balance_minor"] == 200
    assert _wallet(db)["reserved_balance_minor"] == 500


async def test_under_threshold_after_race_rolls_back(db):
    _seed_wallet(db, [100, 100, 100, 100], threshold=300)
    paused, gate = _reservation_pause(db, after_n=1)

    task = asyncio.create_task(wednesday_batch._tuesday_batch_prepare_body(db))
    await paused.wait()
    # A dispute freezes t3 and t4 while the worker is mid-reservation.
    from financial.state_machine import StateMachine
    sm = StateMachine(db)
    await sm.transition(tx_id="t3", new_state="frozen", trigger="test_dispute")
    await sm.transition(tx_id="t4", new_state="frozen", trigger="test_dispute")
    gate.set()
    result = await task

    assert result["batches_created"] == 0
    assert db.payout_batches.docs == []
    assert _tx(db, "t1")["state"] == "available"
    assert _tx(db, "t2")["state"] == "available"
    assert _wallet(db)["available_balance_minor"] == 200
    assert _wallet(db)["reserved_balance_minor"] == 0


def _failing_insert(db, monkeypatch, *, write_first, read_back_fails=False):
    """insert_one raises a network error; with write_first the server applied it first
    (standalone mongod: pymongo does not retry writes, so this reaches the caller)."""
    from pymongo.errors import AutoReconnect
    coll = db.payout_batches
    real_insert, real_find_one = coll.insert_one, coll.find_one

    async def insert_one(doc):
        if write_first:
            await real_insert(doc)
        raise AutoReconnect("connection reset by peer")

    async def find_one(*a, **k):
        if read_back_fails:
            raise AutoReconnect("still down")
        return await real_find_one(*a, **k)

    monkeypatch.setattr(coll, "insert_one", insert_one)
    monkeypatch.setattr(coll, "find_one", find_one)


async def test_insert_error_after_server_write_keeps_the_real_batch(db, monkeypatch):
    _seed_wallet(db, [100, 100], threshold=150)
    _failing_insert(db, monkeypatch, write_first=True)

    result = await wednesday_batch._tuesday_batch_prepare_body(db)

    assert len(db.payout_batches.docs) == 1
    batch = db.payout_batches.docs[0]
    assert result["batches_created"] == 1 and result["items"][0]["id"] == batch["id"]
    for t in ("t1", "t2"):
        assert _tx(db, t)["state"] == "reserved_for_batch"
        assert _tx(db, t)["payout_batch_id"] == batch["id"]


async def test_insert_error_without_write_releases_this_workers_reserves(db, monkeypatch):
    _seed_wallet(db, [100, 100], threshold=150)
    _failing_insert(db, monkeypatch, write_first=False)

    result = await wednesday_batch._tuesday_batch_prepare_body(db)

    assert result["batches_created"] == 0
    assert db.payout_batches.docs == []
    assert [_tx(db, t)["state"] for t in ("t1", "t2")] == ["available", "available"]
    assert _wallet(db)["available_balance_minor"] == 200
    assert _wallet(db)["reserved_balance_minor"] == 0


async def test_insert_error_with_unreadable_outcome_keeps_reserves(db, monkeypatch):
    # Cannot tell whether the batch exists: keep the hold; reserve expiry recovers it.
    _seed_wallet(db, [100, 100], threshold=150)
    _failing_insert(db, monkeypatch, write_first=False, read_back_fails=True)

    result = await wednesday_batch._tuesday_batch_prepare_body(db)

    assert result["batches_created"] == 0
    assert [_tx(db, t)["state"] for t in ("t1", "t2")] == ["reserved_for_batch"] * 2


async def test_late_landing_batch_after_release_is_refused_at_funding(db):
    # Residual window: the read-back saw nothing, items were released, then the delayed
    # insert landed. The batch must never be funded.
    _wallet_for(db, reserved=0)
    _seed_batch(db, "b-late", ["z1", "z2"], created_days_ago=0, tx_state="available")
    spy = PrepareSpy()
    res = await wednesday_batch.prepare_batch_for_wise(
        db, batch_id="b-late", admin_id="sa", wise_prepare_fn=spy.single)
    assert res == {"ok": False, "error": "batch_items_not_held"}
    assert spy.calls == []
    assert _batch(db, "b-late")["status"] == "expired"


async def test_rollback_never_releases_another_batch_reservation(db):
    _seed_wallet(db, [100], threshold=50, extra_reserved=100)
    t1 = _tx(db, "t1")
    t1.update(state="reserved_for_batch", payout_batch_id="batch-B")

    await wednesday_batch._release_reservations(db, ["t1"], batch_id="batch-A", trigger="test")

    assert _tx(db, "t1")["state"] == "reserved_for_batch"
    assert _tx(db, "t1")["payout_batch_id"] == "batch-B"


async def test_rollback_race_reservation_moves_between_read_and_write(db, monkeypatch):
    # Worker A reads t1 as its own reservation; before A writes, t1 is expired and
    # re-reserved by batch B. A's conditional write must not match.
    _seed_wallet(db, [100], threshold=50, extra_reserved=100)
    _tx(db, "t1").update(state="reserved_for_batch", payout_batch_id="batch-A")
    coll = db.merchant_transactions
    real_find_one = coll.find_one

    async def find_one_then_steal(flt=None, *a, **k):
        doc = await real_find_one(flt, *a, **k)
        if flt == {"id": "t1"}:
            _tx(db, "t1")["payout_batch_id"] = "batch-B"
        return doc

    monkeypatch.setattr(coll, "find_one", find_one_then_steal)
    await wednesday_batch._release_reservations(db, ["t1"], batch_id="batch-A", trigger="test")

    assert _tx(db, "t1")["state"] == "reserved_for_batch"
    assert _tx(db, "t1")["payout_batch_id"] == "batch-B"
    assert _wallet(db)["reserved_balance_minor"] == 100


# ---------------------------------------------------------------------------
# Reserve expiry closes open batches with no held items
# ---------------------------------------------------------------------------

def _seed_batch(db, batch_id, items, *, status="awaiting_admin_fund", created_days_ago=0,
                tx_state="reserved_for_batch", reserved_days_ago=None, amount=100):
    reserved_days_ago = created_days_ago if reserved_days_ago is None else reserved_days_ago
    for tx_id in items:
        db.merchant_transactions.docs.append({
            "id": tx_id, "organization_id": ORG, "state": tx_state,
            "payout_batch_id": batch_id, "reserved_at": _iso(reserved_days_ago),
            "updated_at": _iso(reserved_days_ago),
            "amount_display_minor": amount, "base_currency": "TRY", "state_history": [],
        })
    db.payout_batches.docs.append({
        "id": batch_id, "organization_id": ORG, "status": status,
        "item_transaction_ids": list(items), "item_count": len(items),
        "total_amount_minor": amount * len(items), "created_at": _iso(created_days_ago),
        "idempotency_key": f"batch:{ORG}:{batch_id}", "idempotency_enforced": True,
    })


def _wallet_for(db, reserved):
    db.merchant_wallets.docs.append({
        "organization_id": ORG, "base_currency": "TRY", "wallet_status": "active",
        "available_balance_minor": 0, "reserved_balance_minor": reserved,
    })


async def test_expired_reserve_expires_open_batch(db):
    _wallet_for(db, reserved=600)
    _seed_batch(db, "b-stale", ["a1", "a2"], created_days_ago=8)
    _seed_batch(db, "b-partial", ["p1"], created_days_ago=8)
    db.merchant_transactions.docs.append({   # still held by b-partial (fresh)
        "id": "p2", "organization_id": ORG, "state": "reserved_for_batch",
        "payout_batch_id": "b-partial", "reserved_at": _iso(0), "updated_at": _iso(0),
        "amount_display_minor": 100, "state_history": [],
    })
    _seed_batch(db, "b-fresh", ["f1"], created_days_ago=0)
    _seed_batch(db, "b-at-wise", ["w1"], status="wise_fund_pending", created_days_ago=8,
                tx_state="wise_fund_pending")

    from financial.expiry_service import expire_stale_reserves
    await expire_stale_reserves(db)

    assert _tx(db, "a1")["state"] == "available"
    assert _tx(db, "a2")["state"] == "available"
    assert _batch(db, "b-stale")["status"] == "expired"
    assert _batch(db, "b-partial")["status"] == "awaiting_admin_fund"
    assert _batch(db, "b-fresh")["status"] == "awaiting_admin_fund"
    assert _batch(db, "b-at-wise")["status"] == "wise_fund_pending"


async def test_expiry_does_not_release_a_reservation_that_moved_to_another_batch(db, monkeypatch):
    # The expiry cursor saw a1 as a stale reservation of b-stale; by the time it
    # writes, a1 was released and re-reserved (fresh) by batch-B.
    _wallet_for(db, reserved=100)
    _seed_batch(db, "b-stale", ["a1"], created_days_ago=8)
    coll = db.merchant_transactions
    real_find_one = coll.find_one

    async def find_one_after_rereserve(flt=None, *a, **k):
        if flt == {"id": "a1"}:
            _tx(db, "a1").update(payout_batch_id="batch-B", reserved_at=_iso(0))
        return await real_find_one(flt, *a, **k)

    monkeypatch.setattr(coll, "find_one", find_one_after_rereserve)
    from financial.expiry_service import expire_stale_reserves
    await expire_stale_reserves(db)

    assert _tx(db, "a1")["state"] == "reserved_for_batch"
    assert _tx(db, "a1")["payout_batch_id"] == "batch-B"
    assert _wallet(db)["reserved_balance_minor"] == 100


# ---------------------------------------------------------------------------
# Funding guard
# ---------------------------------------------------------------------------

class PrepareSpy:
    def __init__(self):
        self.calls = []

    async def single(self, batch):
        self.calls.append([batch["id"]])
        return {"wise_quote_id": "q1", "wise_transfer_id": "tr1"}

    async def unified(self, batches):
        self.calls.append([b["id"] for b in batches])
        return {
            "wise_batch_group_id": "g1",
            "per_batch": {b["id"]: {"wise_quote_id": "q", "wise_transfer_id": f"tr-{b['id']}"}
                          for b in batches},
        }


async def test_fund_refused_for_stale_or_unheld_batch(db):
    _wallet_for(db, reserved=10_000)
    # stale: older than the 7-day reserve window, items still reserved (expiry cron not run yet)
    _seed_batch(db, "b-stale", ["s1", "s2"], created_days_ago=8)
    # unheld: u2 was re-reserved by another batch after an expiry rollback
    _seed_batch(db, "b-unheld", ["u1", "u2"], created_days_ago=1)
    _tx(db, "u2")["payout_batch_id"] = OTHER_BATCH
    spy = PrepareSpy()

    # 1) prepare_batch_for_wise
    for batch_id, error in [("b-stale", "batch_reserve_expired"), ("b-unheld", "batch_items_not_held")]:
        res = await wednesday_batch.prepare_batch_for_wise(
            db, batch_id=batch_id, admin_id="sa", wise_prepare_fn=spy.single)
        assert res == {"ok": False, "error": error}
        assert _batch(db, batch_id)["status"] == "expired"
    assert spy.calls == []
    # this batch's own reservations are released; another batch's never are
    assert [_tx(db, t)["state"] for t in ("s1", "s2", "u1")] == ["available"] * 3
    assert _tx(db, "u2")["state"] == "reserved_for_batch"
    assert _tx(db, "u2")["payout_batch_id"] == OTHER_BATCH

    # 2) bulk_prepare_batches_for_wise: refused batches drop out, good ones still go
    _seed_batch(db, "b2-stale", ["x1"], created_days_ago=8)
    _seed_batch(db, "b2-good", ["g1"], created_days_ago=1)
    res = await wednesday_batch.bulk_prepare_batches_for_wise(
        db, batch_ids=None, admin_id="sa", unified_prepare_fn=spy.unified)
    assert spy.calls == [["b2-good"]]
    assert res["ok"] is True and res["success"] == 1 and res["failed"] == 1
    assert {"batch_id": "b2-stale", "ok": False, "error": "batch_reserve_expired"} in res["items"]
    assert _batch(db, "b2-stale")["status"] == "expired"
    assert _batch(db, "b2-good")["status"] == "wise_fund_pending"

    # bulk with only refused batches
    _seed_batch(db, "b3-stale", ["y1"], created_days_ago=8)
    spy.calls.clear()
    res = await wednesday_batch.bulk_prepare_batches_for_wise(
        db, batch_ids=["b3-stale"], admin_id="sa", unified_prepare_fn=spy.unified)
    assert spy.calls == []
    assert res["ok"] is False and res["success"] == 0 and res["failed"] == 1

    # 3) confirm_manual_fund: an item no longer wise_fund_pending -> refused, nothing paid out
    _seed_batch(db, "b-wise", ["k1", "k2"], status="wise_fund_pending", created_days_ago=1,
                tx_state="wise_fund_pending")
    _tx(db, "k2")["state"] = "wise_fund_failed"
    res = await wednesday_batch.confirm_manual_fund(db, batch_id="b-wise", admin_id="sa")
    assert res == {"ok": False, "error": "batch_items_not_held"}
    assert _tx(db, "k1")["state"] == "wise_fund_pending"
    # the Wise transfer exists: the batch stays in front of the admin, not expired
    assert _batch(db, "b-wise")["status"] == "wise_fund_pending"


async def test_confirm_fund_not_refused_by_age_once_sent_to_wise(db):
    # Deliberate: a wise_fund_pending batch has a live Wise transfer that may already be
    # funded. Reserve expiry never touches its items, so age alone must not block marking
    # it paid (that would strand money that already left).
    _wallet_for(db, reserved=200)
    _seed_batch(db, "b-old-wise", ["o1", "o2"], status="wise_fund_pending", created_days_ago=9,
                tx_state="wise_fund_pending")
    res = await wednesday_batch.confirm_manual_fund(db, batch_id="b-old-wise", admin_id="sa")
    assert res["ok"] is True and res["status"] == "completed"
    assert _tx(db, "o1")["state"] == "paid_out"


async def test_good_batch_prepares_normally(db):
    _wallet_for(db, reserved=200)
    _seed_batch(db, "b-ok", ["n1", "n2"], created_days_ago=1)
    spy = PrepareSpy()
    res = await wednesday_batch.prepare_batch_for_wise(
        db, batch_id="b-ok", admin_id="sa", wise_prepare_fn=spy.single)
    assert res == {"ok": True, "wise_quote_id": "q1"}
    assert _batch(db, "b-ok")["status"] == "wise_fund_pending"


# ---------------------------------------------------------------------------
# Index: partial unique, legacy duplicates tolerated
# ---------------------------------------------------------------------------

def _migration():
    return importlib.import_module(f"financial.migrations.{MIGRATION}")


def _legacy(db, n=3, key="batch:org-legacy:2026-05-05"):
    for i in range(n):
        db.payout_batches.docs.append({
            "id": f"legacy-{i}", "organization_id": "org-legacy", "status": "partial_failure",
            "idempotency_key": key,
        })
    return key


async def test_legacy_duplicate_keys_do_not_block_index():
    db = FakeDB()
    key = _legacy(db)

    await _migration().up(db)
    await _migration().up(db)  # every worker runs pending migrations at startup

    info = await db.payout_batches.index_information()
    specs = [s for s in info.values() if s["key"] == [("idempotency_key", 1)]]
    assert specs == [{
        "key": [("idempotency_key", 1)], "unique": True,
        "partialFilterExpression": {"idempotency_enforced": True},
    }]
    # legacy docs are outside the filter; new batches with that key are enforced
    await db.payout_batches.insert_one({"id": "n1", "idempotency_key": key, "idempotency_enforced": True})
    with pytest.raises(DuplicateKeyError):
        await db.payout_batches.insert_one({"id": "n2", "idempotency_key": key, "idempotency_enforced": True})
    assert all("idempotency_enforced" not in d for d in db.payout_batches.docs if d["id"].startswith("legacy"))
    assert MIGRATION in runner._discover_migration_modules()


async def test_failed_index_build_only_logs_and_retries_next_startup():
    # Characterization of the startup path (server.py 4c.1 -> runner.apply_all): a failing
    # up() is returned in `errors`, not raised, and not recorded, so the next start retries.
    db = FakeDB()
    for name in runner._discover_migration_modules():
        if name != MIGRATION:
            db.migration_log.docs.append({"name": name, "status": "completed"})
    for i in range(2):  # enforced duplicates make the unique build fail
        db.payout_batches.docs.append({"id": f"e{i}", "idempotency_key": "k", "idempotency_enforced": True})

    result = await runner.apply_all(db)

    assert result["applied"] == []
    assert [e["name"] for e in result["errors"]] == [MIGRATION]
    assert await db.migration_log.find_one({"name": MIGRATION, "status": "completed"}) is None


async def test_legacy_index_list_carries_partial_filter():
    from financial.migration import _create_indexes
    db = FakeDB()
    _legacy(db)
    await _create_indexes(db)
    info = await db.payout_batches.index_information()
    specs = [s for s in info.values() if s["key"] == [("idempotency_key", 1)]]
    assert specs == [{
        "key": [("idempotency_key", 1)], "unique": True,
        "partialFilterExpression": {"idempotency_enforced": True},
    }]


async def test_migration_down_drops_only_its_index():
    db = FakeDB()
    await db.payout_batches.create_index([("status", 1)])
    await _migration().up(db)
    await _migration().down(db)
    await _migration().down(db)  # safe when already gone
    assert list((await db.payout_batches.index_information()).keys()) == ["status_1"]


# ---------------------------------------------------------------------------
# Locks inside the functions (controller ruling P1)
# ---------------------------------------------------------------------------

@pytest.fixture
def redis(monkeypatch):
    r = LockRedis()
    monkeypatch.setattr(distributed_lock, "_default_factory", lambda: r)
    monkeypatch.setattr(distributed_lock, "REDIS_TIMEOUT", 0.2)
    return r


LOCKED_JOBS = [
    # module, public fn, body attr, lock name, ttl seconds
    (wednesday_batch, "tuesday_batch_prepare_cron", "_tuesday_batch_prepare_body", "tuesday_batch_prepare", 1800),
    (dead_letter_queue, "run_retry_cron", "_run_retry_cron_body", "dlq_retry", 270),
]


def _spy(monkeypatch, module, body_attr):
    calls = []

    async def body(db, **kw):
        calls.append(db)
        return {"ran": True}

    monkeypatch.setattr(module, body_attr, body)
    return calls


@pytest.mark.parametrize("module,fn,body,lock,ttl", LOCKED_JOBS)
async def test_locked_job_skips_when_lock_held(redis, monkeypatch, module, fn, body, lock, ttl):
    redis.store[f"plann:lock:{lock}"] = "other-worker"
    calls = _spy(monkeypatch, module, body)
    await getattr(module, fn)(object())
    assert calls == []
    assert redis.store[f"plann:lock:{lock}"] == "other-worker"


@pytest.mark.parametrize("module,fn,body,lock,ttl", LOCKED_JOBS)
async def test_locked_job_skips_when_redis_down(redis, monkeypatch, module, fn, body, lock, ttl):
    redis.fail_set = True
    calls = _spy(monkeypatch, module, body)
    await getattr(module, fn)(object())
    assert calls == []


@pytest.mark.parametrize("module,fn,body,lock,ttl", LOCKED_JOBS)
async def test_locked_job_runs_once_across_worker_ticks(redis, monkeypatch, module, fn, body, lock, ttl):
    calls = _spy(monkeypatch, module, body)
    db = object()
    first = await getattr(module, fn)(db)    # worker A ticks and finishes
    await getattr(module, fn)(db)            # worker B ticks within the window
    assert calls == [db]
    assert first == {"ran": True}
    assert redis.set_calls[0] == (f"plann:lock:{lock}", True, ttl * 1000)
    assert f"plann:lock:{lock}" in redis.store  # hold=True: kept until TTL


# ---------------------------------------------------------------------------
# Final-review fix wave: f (mark_batch_failed owner-scoped), g (abort before Wise)
# ---------------------------------------------------------------------------

async def test_mark_failed_on_stale_batch_leaves_items_now_reserved_by_another_batch(db):
    _wallet_for(db, reserved=300)
    # b-old's items: m1 still its own; m2 was released and re-reserved by batch-B.
    _seed_batch(db, "b-old", ["m1", "m2"], created_days_ago=8)
    _tx(db, "m2")["payout_batch_id"] = "batch-B"

    res = await wednesday_batch.mark_batch_failed(db, batch_id="b-old", admin_id="sa", reason="stale")

    assert res["ok"] is True and res["rolled_back"] == 1
    assert _tx(db, "m1")["state"] == "failed"
    assert _tx(db, "m2")["state"] == "reserved_for_batch"
    assert _tx(db, "m2")["payout_batch_id"] == "batch-B"


@pytest.mark.parametrize("status", ["completed", "failed", "partial_failure", "expired"])
async def test_mark_failed_refuses_terminal_or_expired_batch(db, status):
    _wallet_for(db, reserved=100)
    _seed_batch(db, "b-done", ["d1"], status=status, created_days_ago=1)

    res = await wednesday_batch.mark_batch_failed(db, batch_id="b-done", admin_id="sa", reason="again")

    assert res == {"ok": False, "error": f"invalid_batch_status:{status}"}
    assert _tx(db, "d1")["state"] == "reserved_for_batch"
    assert _batch(db, "b-done")["status"] == status


def _release_after_guard(db, monkeypatch, tx_id):
    """Reserve expiry releases `tx_id` right after the funding guard counted it as held
    (the 7-day boundary race), so its queued_for_wise transition fails."""
    coll = db.merchant_transactions
    real_count = coll.count_documents

    async def count_documents(flt):
        n = await real_count(flt)
        if tx_id in (flt.get("id") or {}).get("$in", []):  # this batch's guard count
            _tx(db, tx_id).update(state="available")
        return n

    monkeypatch.setattr(coll, "count_documents", count_documents)


async def test_prepare_aborts_before_wise_when_an_item_transition_fails(db, monkeypatch):
    _wallet_for(db, reserved=200)
    _seed_batch(db, "b-race", ["r1", "r2"], created_days_ago=1)
    _release_after_guard(db, monkeypatch, "r2")
    spy = PrepareSpy()

    res = await wednesday_batch.prepare_batch_for_wise(
        db, batch_id="b-race", admin_id="sa", wise_prepare_fn=spy.single)

    assert spy.calls == []
    assert res == {"ok": False, "error": "batch_item_transition_failed"}
    assert _tx(db, "r1")["state"] == "reserved_for_batch"       # this call's transition reverted
    assert _tx(db, "r1")["payout_batch_id"] == "b-race"
    assert _tx(db, "r2")["state"] == "available"                # not ours to touch
    assert _batch(db, "b-race")["status"] == "awaiting_admin_fund"
    assert _wallet(db)["reserved_balance_minor"] == 200         # revert moves no money


async def test_bulk_prepare_sends_only_batches_whose_transitions_all_succeeded(db, monkeypatch):
    _wallet_for(db, reserved=300)
    _seed_batch(db, "b-ok", ["o1"], created_days_ago=1)
    _seed_batch(db, "b-race", ["r1", "r2"], created_days_ago=1)
    _release_after_guard(db, monkeypatch, "r2")
    spy = PrepareSpy()

    res = await wednesday_batch.bulk_prepare_batches_for_wise(
        db, batch_ids=["b-ok", "b-race"], admin_id="sa", unified_prepare_fn=spy.unified)

    assert spy.calls == [["b-ok"]]
    assert {"batch_id": "b-race", "ok": False, "error": "batch_item_transition_failed"} in res["items"]
    assert res["success"] == 1 and res["failed"] == 1
    assert _tx(db, "r1")["state"] == "reserved_for_batch"
    assert _batch(db, "b-race")["status"] == "awaiting_admin_fund"
    assert _batch(db, "b-ok")["status"] == "wise_fund_pending"


async def test_bulk_prepare_with_every_batch_aborted_calls_wise_zero_times(db, monkeypatch):
    _wallet_for(db, reserved=200)
    _seed_batch(db, "b-race", ["r1", "r2"], created_days_ago=1)
    _release_after_guard(db, monkeypatch, "r2")
    spy = PrepareSpy()

    res = await wednesday_batch.bulk_prepare_batches_for_wise(
        db, batch_ids=None, admin_id="sa", unified_prepare_fn=spy.unified)

    assert spy.calls == []
    assert res["ok"] is False and res["success"] == 0 and res["failed"] == 1
    assert res["items"] == [{"batch_id": "b-race", "ok": False, "error": "batch_item_transition_failed"}]


# ---------------------------------------------------------------------------
# R7: Tuesday prep must never pull an item that left `available` after the scan
# (queued_for_wise -> reserved_for_batch is a valid edge for the abort revert only)
# ---------------------------------------------------------------------------

def _queue_into_batch_a_after_scan(db, monkeypatch):
    """Between the Tuesday scan and its transition, t1 is reserved by batch A and moved
    to queued_for_wise by an admin prepare (Wise call in flight)."""
    coll = db.merchant_transactions
    real_find_one = coll.find_one
    fired = []

    async def find_one(flt=None, *a, **k):
        if flt == {"id": "t1"} and not fired:
            fired.append(1)
            w = _wallet(db)
            w["available_balance_minor"] -= 100
            w["reserved_balance_minor"] += 100
            _tx(db, "t1").update(state="queued_for_wise", payout_batch_id="A")
        return await real_find_one(flt, *a, **k)

    monkeypatch.setattr(coll, "find_one", find_one)


async def test_tuesday_prep_does_not_pull_a_queued_item_into_a_new_batch(db, monkeypatch):
    _seed_wallet(db, [100], threshold=100)
    _queue_into_batch_a_after_scan(db, monkeypatch)

    result = await wednesday_batch._tuesday_batch_prepare_body(db)

    assert _tx(db, "t1")["state"] == "queued_for_wise"
    assert _tx(db, "t1")["payout_batch_id"] == "A"
    # skipped item: no reserved_ok, no batch, no amount
    assert result["batches_created"] == 0
    assert db.payout_batches.docs == []
    assert _wallet(db)["reserved_balance_minor"] == 100
    assert _wallet(db)["available_balance_minor"] == 0


async def test_tuesday_prep_duplicate_key_never_releases_a_queued_item(db, monkeypatch):
    _seed_wallet(db, [100], threshold=100)
    db.payout_batches.docs.append({   # batch A owns today's key and t1
        "id": "A", "organization_id": ORG, "status": "queued_for_wise",
        "item_transaction_ids": ["t1"], "total_amount_minor": 100,
        "idempotency_key": _today_key(), "idempotency_enforced": True, "created_at": _iso(),
    })
    _queue_into_batch_a_after_scan(db, monkeypatch)

    await wednesday_batch._tuesday_batch_prepare_body(db)

    # Not released and credited while batch A's Wise transfer contains it.
    assert _tx(db, "t1")["state"] == "queued_for_wise"
    assert _tx(db, "t1")["payout_batch_id"] == "A"
    assert _wallet(db)["available_balance_minor"] == 0
    assert _wallet(db)["reserved_balance_minor"] == 100
    assert [b["id"] for b in db.payout_batches.docs] == ["A"]
