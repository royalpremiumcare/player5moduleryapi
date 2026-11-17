import asyncio
import hashlib
from datetime import datetime

import pytest

from live_activity import registry
from live_activity.phase import TR_TZ
from tests.live_activity_fakes import FakeDB


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


async def test_reowned_device_exposes_live_slots_to_end(db):
    await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db, 1, update_token="tok-1")
    await _seed_slot(db, 2, state="start_sent")                  # no token: nothing to end
    await _seed_slot(db, 3, state="ended", update_token="old")
    same: list = []
    await registry.upsert_device(db, **{**DEVICE, "fcm_token": "new"}, ended_slots=same)
    assert same == []                                            # same owner: nothing ended
    ended: list = []
    row, secret = await registry.upsert_device(db, **{**DEVICE, "user_id": "u2"}, ended_slots=ended)
    assert secret and row["user_id"] == "u2"
    assert [(s["slot_index"], s["update_token"], s["version"]) for s in ended] == [(1, "tok-1", 1)]


async def test_record_token_moves_start_sent_to_active(db):
    await _seed_slot(db, state="start_sent")
    assert await registry.record_slot_token(db, device_id="dev1", slot_index=1, activity_id="A", update_token="T")
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["state"], s["activity_id"], s["update_token"]) == ("active", "A", "T")
    assert s["version"] == 2  # a sweep holding the start_sent snapshot must lose its CAS


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


async def test_report_bumps_version_so_stale_claim_fails(db):
    await _seed_slot(db)  # version 1
    await registry.apply_device_report(
        db, device_id="dev1", slots=[{"slot_index": 1, "activity_id": "act1", "state": "dismissed"}],
        activities_enabled=True, complete=False, now=NOW)
    # A sweep that read the slot before the report still holds version 1.
    stale = await registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=1,
                                      set_fields={"state": "start_sent", "appointment_id": "x"})
    assert stale is False
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["state"], s["version"]) == ("dismissed_by_user", 2)


async def test_active_report_never_changes_state(db):
    await _seed_slot(db, 1, state="start_sent")
    await _seed_slot(db, 2, state="ended")
    changed = await registry.apply_device_report(
        db, device_id="dev1", activities_enabled=True, complete=True, now=NOW,
        slots=[{"slot_index": 1, "activity_id": "x", "state": "active"},
               {"slot_index": 2, "activity_id": "act2", "state": "active"}])
    assert changed == []
    assert [s["state"] for s in await registry.slots_for_device(db, "dev1")] == ["start_sent", "ended"]
    assert await registry.record_slot_token(db, device_id="dev1", slot_index=1, activity_id="A", update_token="T")


async def test_refresh_slot_token_only_for_tracked_active_activity(db):
    await _seed_slot(db, 1, update_token="old")  # version 1, activity act1
    args = dict(device_id="dev1", slot_index=1, update_token="new")
    assert await registry.refresh_slot_token(db, activity_id="other", **args) is False
    assert await registry.refresh_slot_token(db, activity_id="act1", **args) is True
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["update_token"], s["version"]) == ("new", 2)
    assert await registry.refresh_slot_token(db, activity_id="act1", **args) is True  # same token: no bump
    assert (await registry.slots_for_device(db, "dev1"))[0]["version"] == 2


async def test_remove_device_ends_slots_and_deletes_row(db):
    await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db, 1, update_token="t1")
    await _seed_slot(db, 2, state="ended", update_token="t2")
    await _seed_slot(db, 3, state="start_sent")
    live = await registry.remove_device(db, "dev1")
    assert [(s["slot_index"], s["update_token"]) for s in live] == [(1, "t1")]
    assert await db.live_activity_devices.find_one({"device_id": "dev1"}) is None
    assert {(s["state"], s["version"]) for s in await registry.slots_for_device(db, "dev1")} == {("ended", 2)}
    _, secret = await registry.upsert_device(db, **DEVICE)
    assert secret  # re-registering after logout issues a fresh secret


async def _dismiss(db, idx, now):
    await registry.apply_device_report(
        db, device_id="dev1", slots=[{"slot_index": idx, "activity_id": f"act{idx}", "state": "dismissed"}],
        activities_enabled=True, complete=False, now=now)


async def test_report_dismissed_remembers_the_days_dismissed_appointments(db):
    # The slot may be restarted for another appointment; the dismissed ones must stay known.
    await _seed_slot(db, 1, appointment_id="a")
    await _dismiss(db, 1, NOW)
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["dismissed_day"], s["dismissed_ids"]) == ("2026-11-16", ["a"])
    # restarted for b (as the sweeper's start claim does), then dismissed again the same day
    assert await registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=s["version"],
                                     set_fields={"state": "active", "appointment_id": "b"})
    await _dismiss(db, 1, NOW)
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["state"], s["dismissed_day"], s["dismissed_ids"]) == ("dismissed_by_user", "2026-11-16", ["a", "b"])
    # a new day starts a fresh list
    await registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=s["version"],
                              set_fields={"state": "active", "appointment_id": "c"})
    await _dismiss(db, 1, datetime(2026, 11, 17, 9, 0, tzinfo=TR_TZ))
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert (s["dismissed_day"], s["dismissed_ids"]) == ("2026-11-17", ["c"])


async def test_owner_change_and_logout_forget_dismissals(db):
    await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db, 1, appointment_id="a")
    await _dismiss(db, 1, NOW)
    await registry.upsert_device(db, **{**DEVICE, "user_id": "u2"})
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert "dismissed_ids" not in s and "dismissed_day" not in s
    await registry.claim_slot(db, device_id="dev1", slot_index=1, expect_version=s["version"],
                              set_fields={"state": "active", "appointment_id": "b"})
    await _dismiss(db, 1, NOW)
    await registry.remove_device(db, "dev1")
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert "dismissed_ids" not in s and "dismissed_day" not in s


async def test_dismissal_write_does_not_drop_a_concurrently_recorded_id(db, monkeypatch):
    await _seed_slot(db, 1, appointment_id="b", dismissed_day="2026-11-16", dismissed_ids=["a"])
    real = registry.slots_for_device

    async def snapshot_then_concurrent_write(db_, device_id):
        slots = await real(db_, device_id)
        # another writer records x for this slot right after the report's snapshot
        await db_.live_activity_slots.update_one({"device_id": device_id, "slot_index": 1},
                                                 {"$set": {"dismissed_ids": ["a", "x"]}, "$inc": {"version": 1}})
        monkeypatch.setattr(registry, "slots_for_device", real)
        return slots

    monkeypatch.setattr(registry, "slots_for_device", snapshot_then_concurrent_write)
    await _dismiss(db, 1, NOW)
    s = (await real(db, "dev1"))[0]
    assert (s["state"], s["dismissed_ids"]) == ("dismissed_by_user", ["a", "x", "b"])


async def test_new_device_row_forgets_dismissals_left_by_a_stale_report(db):
    await registry.upsert_device(db, **DEVICE)
    await _seed_slot(db, 1, appointment_id="a")
    await registry.remove_device(db, "dev1")
    # a report racing the logout still marks the (now ended) slot... as a late dismissal would
    await db.live_activity_slots.update_one({"device_id": "dev1", "slot_index": 1},
                                            {"$set": {"dismissed_day": "2026-11-16", "dismissed_ids": ["a"]}})
    await registry.upsert_device(db, **{**DEVICE, "user_id": "u2"})
    s = (await registry.slots_for_device(db, "dev1"))[0]
    assert "dismissed_ids" not in s and "dismissed_day" not in s
