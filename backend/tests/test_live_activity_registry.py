import asyncio
import copy
import hashlib
from datetime import datetime

import pytest
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from live_activity import registry
from live_activity.phase import TR_TZ


def _match(doc, flt):
    for k, v in flt.items():
        if isinstance(v, dict):
            for op, arg in v.items():
                if op == "$in" and doc.get(k) not in arg:
                    return False
                if op == "$exists" and (k in doc) != arg:
                    return False
                if op == "$lt" and not (k in doc and doc[k] < arg):
                    return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs
        self._sort = None

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    async def to_list(self, _length):
        return list(self._docs)

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d

        return gen()


class FakeCollection:
    """Minimal async Motor stand-in. Every call is atomic (no await inside)."""

    def __init__(self):
        self.docs = []
        self.unique = []

    async def create_index(self, keys, unique=False, **_kw):
        if unique:
            self.unique.append([k if isinstance(k, str) else k[0] for k in keys] if isinstance(keys, list) else [keys])
        return "idx"

    def _check_unique(self, doc, ignore=None):
        for fields in self.unique:
            for other in self.docs:
                if other is not ignore and all(other.get(f) == doc.get(f) for f in fields):
                    raise DuplicateKeyError("duplicate key")

    @staticmethod
    def _apply(doc, update):
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        for k, v in update.get("$inc", {}).items():
            doc[k] = doc.get(k, 0) + v
        for k, v in update.get("$push", {}).items():
            doc.setdefault(k, []).append(v)
        for k, cond in update.get("$pull", {}).items():
            lt = cond["$lt"]
            doc[k] = [x for x in doc.get(k, []) if not x < lt]

    def _insert_from(self, flt, update):
        doc = {k: v for k, v in flt.items() if not isinstance(v, dict)}
        doc.update(update.get("$setOnInsert", {}))
        self._apply(doc, update)
        self._check_unique(doc)
        self.docs.append(doc)
        return doc

    async def find_one(self, flt):
        for d in self.docs:
            if _match(d, flt):
                return copy.deepcopy(d)
        return None

    def find(self, flt=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs if _match(d, flt or {})])

    async def find_one_and_update(self, flt, update, upsert=False, return_document=ReturnDocument.BEFORE):
        for d in self.docs:
            if _match(d, flt):
                before = copy.deepcopy(d)
                self._apply(d, update)
                return copy.deepcopy(d) if return_document == ReturnDocument.AFTER else before
        if upsert:
            doc = self._insert_from(flt, update)
            return copy.deepcopy(doc) if return_document == ReturnDocument.AFTER else None
        return None

    async def update_one(self, flt, update, upsert=False):
        for d in self.docs:
            if _match(d, flt):
                self._apply(d, update)
                return _Result(1)
        if upsert:
            self._insert_from(flt, update)
        return _Result(0)

    async def update_many(self, flt, update):
        n = 0
        for d in self.docs:
            if _match(d, flt):
                self._apply(d, update)
                n += 1
        return _Result(n)


class _Result:
    def __init__(self, n):
        self.matched_count = n
        self.modified_count = n


class FakeDB:
    def __init__(self):
        self.live_activity_devices = FakeCollection()
        self.live_activity_slots = FakeCollection()


@pytest.fixture
async def db():
    d = FakeDB()
    await registry.ensure_indexes(d)
    return d


DEVICE = dict(
    device_id="dev1", organization_id="org1", user_id="u1", username="ali",
    os_version="18.1", app_build="100", fcm_token="fcm", push_to_start_token="pts",
    activities_enabled=True,
)


async def _seed_slot(db, idx=1, state="active", **extra):
    ok = await registry.claim_slot(
        db, device_id="dev1", slot_index=idx, expect_version=None,
        set_fields={"state": state, "activity_id": f"act{idx}", **extra},
    )
    assert ok


async def test_claim_slot_is_cas(db):
    await _seed_slot(db, state="start_sent")
    results = await asyncio.gather(*[
        registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=1,
                            set_fields={"appointment_id": f"a{i}"})
        for i in range(2)
    ])
    assert sorted(results) == [False, True]
    slot = (await registry.slots_for_device(db, "dev1"))[0]
    assert slot["version"] == 2


async def test_claim_slot_insert_twice_returns_false(db):
    await _seed_slot(db)
    again = await registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=None, set_fields={})
    assert again is False


async def test_slots_ordered_by_index(db):
    await _seed_slot(db, 3)
    await _seed_slot(db, 1)
    assert [s["slot_index"] for s in await registry.slots_for_device(db, "dev1")] == [1, 3]


async def test_secret_stored_hashed(db):
    row, secret = await registry.upsert_device(db, **DEVICE)
    assert secret
    assert row["secret_sha256"] == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in str(row)
    assert await registry.verify_device_secret(db, "dev1", secret)
    assert await registry.verify_device_secret(db, "dev1", "wrong") is None
    assert await registry.verify_device_secret(db, "nope", secret) is None


async def test_same_owner_keeps_secret_and_updates_fields(db):
    _, secret = await registry.upsert_device(db, **DEVICE)
    row, again = await registry.upsert_device(db, **{**DEVICE, "fcm_token": "new"})
    assert again is None
    assert row["fcm_token"] == "new"
    assert await registry.verify_device_secret(db, "dev1", secret)


async def test_reowned_device_rotates_secret_and_ends_slots(db):
    _, old = await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db)
    row, new = await registry.upsert_device(db, **{**DEVICE, "user_id": "u2"})
    assert new and new != old
    assert await registry.verify_device_secret(db, "dev1", old) is None
    assert await registry.verify_device_secret(db, "dev1", new)
    assert row["day"] is None
    assert [s["state"] for s in await registry.slots_for_device(db, "dev1")] == ["ended"]


async def test_record_token_moves_start_sent_to_active(db):
    await _seed_slot(db, state="start_sent")
    assert await registry.record_slot_token(db, device_id="dev1", slot_index=1, activity_id="A", update_token="T")
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["state"], s["activity_id"], s["update_token"]) == ("active", "A", "T")


async def test_record_token_unknown_slot_false(db):
    assert not await registry.record_slot_token(db, device_id="dev1", slot_index=4, activity_id="A", update_token="T")


NOW = datetime(2026, 11, 16, 23, 30, tzinfo=TR_TZ)


async def test_report_dismissed_marks_for_today(db):
    await _seed_slot(db)
    changed = await registry.apply_device_report(
        db, device_id="dev1", slots=[{"slot_index": 1, "activity_id": "act1", "state": "dismissed"}],
        activities_enabled=True, complete=True, now=NOW)
    assert changed[0]["state"] == "dismissed_by_user"
    assert changed[0]["day"] == "2026-11-16"


async def test_partial_report_does_not_end_unlisted(db):
    await _seed_slot(db, 1)
    await _seed_slot(db, 2, state="start_sent")
    changed = await registry.apply_device_report(
        db, device_id="dev1", slots=[], activities_enabled=True, complete=False, now=NOW)
    assert changed == []
    assert {s["state"] for s in await registry.slots_for_device(db, "dev1")} == {"active", "start_sent"}


async def test_complete_report_ends_unlisted(db):
    await _seed_slot(db, 1)
    await _seed_slot(db, 2, state="start_sent")
    await _seed_slot(db, 3, state="ended")
    changed = await registry.apply_device_report(
        db, device_id="dev1", slots=[], activities_enabled=False, complete=True, now=NOW)
    assert sorted(c["slot_index"] for c in changed) == [1, 2]
    assert {s["state"] for s in await registry.slots_for_device(db, "dev1")} == {"ended"}


async def test_report_sets_activities_enabled_and_listed_ended(db):
    await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db)
    await registry.apply_device_report(
        db, device_id="dev1", slots=[{"slot_index": 1, "activity_id": "act1", "state": "ended"}],
        activities_enabled=False, complete=False, now=NOW)
    assert (await db.live_activity_devices.find_one({"device_id": "dev1"}))["activities_enabled"] is False
    assert (await registry.slots_for_device(db, "dev1"))[0]["state"] == "ended"


async def test_start_log_prunes_older_than_hour(db):
    await registry.upsert_device(db, **DEVICE)
    await registry.record_start(db, "dev1", 1000.0)
    await registry.record_start(db, "dev1", 2000.0)
    await registry.record_start(db, "dev1", 5000.0)
    dev = await db.live_activity_devices.find_one({"device_id": "dev1"})
    assert dev["start_log"] == [2000.0, 5000.0]
    assert registry.starts_last_hour(dev, 5000.0) == 2
    assert registry.starts_last_hour(dev, 5600.0) == 1
    assert registry.starts_last_hour({}, 5000.0) == 0
