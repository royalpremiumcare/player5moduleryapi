import ast
import asyncio
import copy
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from live_activity import registry, sweeper
from live_activity.phase import TR_TZ
from live_activity.transport import RecordingTransport, SendResult
from tests.live_activity_fakes import WRITE_METHODS, DownRedis, FakeDB, FakeRedis

ORG = "org1"
TODAY = "2026-11-16"
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=TR_TZ)
UNREGISTERED = SendResult(ok=False, invalid_token=True, error="registration-token-not-registered")


def at(hhmm: str, sec: int = 0) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return NOW.replace(hour=h, minute=m, second=sec)


def apt(id, time, *, staff=None, status="Bekliyor", date=TODAY, duration=30, customer="Ayşe Kaya",
        service="Saç Kesimi", org=ORG):
    return {
        "organization_id": org, "id": id, "customer_name": customer, "service_name": service,
        "appointment_date": date, "appointment_time": time, "status": status,
        "staff_member_id": staff, "service_duration": duration,
        "phone": "05551112233", "notes": "private note", "service_price": 450.0,
    }


def user(username, role="admin", org=ORG, **kw):
    return {"organization_id": org, "id": f"id-{username}", "username": username, "role": role,
            "status": "active", "full_name": kw.pop("full_name", username.title()), **kw}


def device(device_id, username, org=ORG, **kw):
    return {
        "device_id": device_id, "organization_id": org, "user_id": f"id-{username}", "username": username,
        "fcm_token": f"fcm-{device_id}", "push_to_start_token": f"pts-{device_id}",
        "activities_enabled": True, "start_log": [], "day": None, "os_version": "26.0", **kw,
    }


def settings(org=ORG, enabled=True, **kw):
    return {"organization_id": org, "live_activity_enabled": enabled, **kw}


async def make_db(*, settings_=None, users=(), devices=(), apts=(), services=()):
    db = FakeDB()
    await registry.ensure_indexes(db)
    db.settings.docs.extend(settings_ if settings_ is not None else [settings()])
    db.users.docs.extend(users)
    db.live_activity_devices.docs.extend(devices)
    db.appointments.docs.extend(apts)
    db.services.docs.extend(services)
    db.log.clear()
    return db


def seed_slot(db, device_id, idx, aid, phase, *, state="active", token="tok", content_hash="old",
              started_at=None, version=3, day=TODAY):
    db.live_activity_slots.docs.append({
        "device_id": device_id, "slot_index": idx, "state": state, "appointment_id": aid,
        "phase_sent": phase, "content_hash": content_hash, "update_token": token,
        "activity_id": f"act-{idx}" if token else None,
        "started_at": started_at if started_at is not None else (NOW - timedelta(hours=1)).timestamp(),
        "version": version, "day": day,
    })


def slot(db, device_id, idx):
    return next(s for s in db.live_activity_slots.docs if s["device_id"] == device_id and s["slot_index"] == idx)


def dev(db, device_id):
    return next(d for d in db.live_activity_devices.docs if d["device_id"] == device_id)


async def sweep(db, t, now=NOW, **kw):
    return await sweeper.run_sweep(db, transport=t, now=now, **kw)


def events(t):
    return [(s["aps"]["event"], s["la_token"]) for s in t.sent]


# --- read-only guarantees -------------------------------------------------------------

FORBIDDEN_NAMES = {"_auto_complete_pending_for_org", "get_appointments", "transactions"}
LA_DIR = Path(__file__).resolve().parents[1] / "live_activity"


def test_no_forbidden_names_or_appointment_writes_in_package():
    offenders = []
    for path in sorted(LA_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
                if isinstance(node.value, ast.Attribute) and node.value.attr in ("appointments", "transactions") \
                        and node.attr in WRITE_METHODS:
                    offenders.append((path.name, node.lineno, f"{node.value.attr}.{node.attr}"))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.append(node.value)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
                if "server" in mods:
                    offenders.append((path.name, node.lineno, "import server"))
            offenders += [(path.name, node.lineno, n) for n in names if n in FORBIDDEN_NAMES]
    assert offenders == []


async def test_sweep_never_writes_appointments_or_transactions():
    apts = [apt("a", "09:45"), apt("b", "10:20"), apt("e", "10:25"), apt("c", "11:00", status="İptal")]
    db = await make_db(users=[user("ali", live_activity_slot_count=3)], devices=[device("d1", "ali")], apts=apts)
    seed_slot(db, "d1", 2, "c", "upcoming")      # cancelled → switch
    seed_slot(db, "d1", 3, "gone", "upcoming")   # deleted → switch (read by id)
    seed_slot(db, "d1", 4, "x", "upcoming")      # above the slot count → end
    before = copy.deepcopy(db.appointments.docs)
    t = RecordingTransport()
    for minute in range(0, 6):
        await sweep(db, t, now=NOW + timedelta(minutes=minute))
        for s in db.live_activity_slots.docs:
            if s["state"] == "start_sent":
                await registry.record_slot_token(db, device_id="d1", slot_index=s["slot_index"],
                                                 activity_id="A", update_token=f"tok-{s['slot_index']}")
    assert {e for e, _ in events(t)} == {"start", "update", "end"}
    touched = {c for c, _m, _a in db.log}
    written = {c for c, m, _a in db.log if m in WRITE_METHODS}
    assert touched <= {"settings", "users", "services", "appointments", "live_activity_devices", "live_activity_slots"}
    assert written <= {"live_activity_devices", "live_activity_slots"}
    assert db.appointments.docs == before
    for c, m, args in db.log:
        if c == "appointments":
            assert m in ("find", "find_one")
            projection = args[1]
            assert projection and {"phone", "notes", "service_price"} <= {k for k, v in projection.items() if not v}


# --- concurrency ------------------------------------------------------------------------

async def test_hook_and_sweep_race_single_push():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await asyncio.gather(sweep(db, t), sweep(db, t, org_ids=[ORG]))
    assert events(t) == [("start", "pts-d1")]

    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A", update_token="tok")
    db.appointments.docs[0]["service_name"] = "Fön"   # cosmetic change → one p5 update
    t.sent.clear()
    later = NOW + timedelta(seconds=30)
    await asyncio.gather(sweep(db, t, now=later), sweep(db, t, now=later, org_ids=[ORG]))
    assert events(t) == [("update", "tok")]
    assert t.sent[0]["priority"] == 5


async def test_two_workers_one_lock():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t, r = RecordingTransport(), FakeRedis()
    stats = await asyncio.gather(sweep(db, t, redis=r), sweep(db, t, redis=r))
    assert sorted(s["locked"] for s in stats) == [False, True]
    assert events(t) == [("start", "pts-d1")]
    assert list(r.keys) == [f"live_activity_lock:{int(NOW.timestamp() // 30)}"]

    # The hook path (org_ids) skips the lock, even inside the same bucket.
    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A", update_token="tok")
    db.appointments.docs[0]["service_name"] = "Fön"
    stats = await sweep(db, t, redis=r, org_ids=[ORG])
    assert stats["locked"] is False
    assert events(t)[-1] == ("update", "tok")


async def test_redis_down_still_single_send():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    stats = await asyncio.gather(sweep(db, t, redis=DownRedis()), sweep(db, t, redis=DownRedis()))
    assert [s["locked"] for s in stats] == [False, False]
    assert events(t) == [("start", "pts-d1")]


# --- org / device selection -------------------------------------------------------------

async def test_flag_off_org_ignored():
    db = await make_db(
        settings_=[settings(), settings("org2", enabled=False), {"organization_id": "org3"}],
        users=[user("ali"), user("can", org="org2"), user("cem", org="org3")],
        devices=[device("d1", "ali"), device("d2", "can", org="org2"), device("d3", "cem", org="org3")],
        apts=[apt("a", "10:20"), apt("b", "10:20", org="org2"), apt("c", "10:20", org="org3")],
    )
    t = RecordingTransport()
    stats = await sweep(db, t)
    assert events(t) == [("start", "pts-d1")]
    assert stats["orgs"] == 1
    await sweep(db, t, org_ids=["org2", "org3"])
    assert len(t.sent) == 1


def assert_removed_end_now(sent):
    aps = sent["aps"]
    cs = aps["content-state"]
    assert (aps["event"], cs["phase"], aps["dismissal-date"]) == ("end", "removed", aps["timestamp"])
    assert (cs["customerDisplay"], cs["serviceName"], cs["staffName"], cs["startLabel"]) == (None, "", None, "")
    assert "Ayşe" not in str(aps) and "Saç" not in str(aps)


async def test_inactive_user_device_slots_ended():
    db = await make_db(users=[user("ali", status="passive")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    assert t.sent == []                       # nothing started for an inactive user

    seed_slot(db, "d1", 1, "a", "upcoming", token="tok1")
    seed_slot(db, "d1", 2, "a", "upcoming", state="start_sent", token=None)   # no token: cannot be ended
    seed_slot(db, "d1", 3, "a", "upcoming", state="ended", token="old")
    await sweep(db, t)
    assert events(t) == [("end", "tok1")]
    assert_removed_end_now(t.sent[0])
    assert slot(db, "d1", 1)["state"] == "ended"
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert len(t.sent) == 1                   # ended once


async def test_missing_user_device_slots_ended():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ghost")], apts=[apt("a", "10:20")])
    seed_slot(db, "d1", 1, "a", "upcoming", token="tok1")
    t = RecordingTransport()
    await sweep(db, t)
    assert events(t) == [("end", "tok1")]
    assert_removed_end_now(t.sent[0])
    assert slot(db, "d1", 1)["state"] == "ended"


async def test_flag_off_org_ends_live_slots():
    db = await make_db(
        settings_=[settings(), settings("org2", enabled=False), {"organization_id": "org3"}],   # org4: no settings
        users=[user("ali"), user("can", org="org2"), user("cem", org="org3"), user("dan", org="org4")],
        devices=[device("d1", "ali"), device("d2", "can", org="org2"), device("d3", "cem", org="org3"),
                 device("d4", "dan", org="org4"), device("d5", "can", org="org2")],
        apts=[apt("a", "10:20"), apt("b", "10:20", org="org2"), apt("c", "10:20", org="org3")],
    )
    seed_slot(db, "d2", 1, "b", "upcoming", token="tok2")
    seed_slot(db, "d2", 2, "b", "upcoming", state="ended", token="old2")
    seed_slot(db, "d3", 1, "c", "upcoming", state="start_sent", token="tok3")
    seed_slot(db, "d4", 1, "x", "upcoming", token="tok4")
    t = RecordingTransport()
    stats = await sweep(db, t)
    assert sorted(events(t)) == [("end", "tok2"), ("end", "tok3"), ("end", "tok4"), ("start", "pts-d1")]
    for sent in t.sent:
        if sent["aps"]["event"] == "end":
            assert_removed_end_now(sent)
    assert stats["orgs"] == 1
    assert {slot(db, d, 1)["state"] for d in ("d2", "d3", "d4")} == {"ended"}
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert len(t.sent) == 4                   # ended once; d5 (no slots) never touched

    # The change-hook path ends only the orgs it was asked about.
    db = await make_db(
        settings_=[settings("org2", enabled=False), settings("org3", enabled=False)],
        users=[user("can", org="org2"), user("cem", org="org3")],
        devices=[device("d2", "can", org="org2"), device("d3", "cem", org="org3")],
    )
    seed_slot(db, "d2", 1, "b", "upcoming", token="tok2")
    seed_slot(db, "d3", 1, "c", "upcoming", token="tok3")
    t = RecordingTransport()
    await sweep(db, t, org_ids=["org2"])
    assert events(t) == [("end", "tok2")]
    assert slot(db, "d3", 1)["state"] == "active"


# --- tokens -----------------------------------------------------------------------------

async def test_invalid_slot_token_cleared():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    seed_slot(db, "d1", 1, "a", "upcoming", token="dead", content_hash="stale")
    t = RecordingTransport(fail_tokens={"fcm-d1": UNREGISTERED})
    stats = await sweep(db, t)
    assert events(t) == [("update", "dead")]
    s = slot(db, "d1", 1)
    assert s["update_token"] is None
    assert s["state"] == "ended"           # the activity is gone; the index may reopen
    assert s["content_hash"] == "stale"    # not delivered, so not recorded as sent
    assert dev(db, "d1")["push_to_start_token"] == "pts-d1"
    assert stats["invalid_token"] == 1


async def test_invalid_push_to_start_token_cleared():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport(fail_tokens={"fcm-d1": UNREGISTERED})
    await sweep(db, t)
    assert events(t) == [("start", "pts-d1")]
    assert dev(db, "d1")["push_to_start_token"] is None
    assert dev(db, "d1")["day"] is None
    assert slot(db, "d1", 1)["state"] == "ended"
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert len(t.sent) == 1   # no push-to-start token any more → no start


async def test_failed_update_rolled_back_and_retried():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    seed_slot(db, "d1", 1, "a", "upcoming", content_hash="stale")
    t = RecordingTransport(fail_tokens={"fcm-d1": SendResult(False, False, "unavailable")})
    await sweep(db, t)
    s = slot(db, "d1", 1)
    assert (s["content_hash"], s["state"], s["update_token"]) == ("stale", "active", "tok")
    t.fail_tokens.clear()
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert events(t) == [("update", "tok"), ("update", "tok")]
    assert slot(db, "d1", 1)["content_hash"] != "stale"


async def test_fcm_success_does_not_mark_active():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    start = t.sent[0]
    assert start["alert"] == ("Sıradaki randevu", "Ayşe Kaya · Saç Kesimi · 10:20")
    assert start["priority"] == 10
    assert start["aps"]["attributes"] == {"slotId": "d1:1", "orgId": ORG}
    assert start["aps"]["input-push-token"] == 1
    s = slot(db, "d1", 1)
    assert (s["state"], s["update_token"], s["appointment_id"], s["phase_sent"]) == ("start_sent", None, "a", "upcoming")
    assert s["started_at"] == NOW.timestamp()
    assert s["version"] == 1 and start["aps"]["content-state"]["version"] == 1
    d = dev(db, "d1")
    assert d["day"] == TODAY
    assert d["start_log"] == [NOW.timestamp()]

    await sweep(db, t, now=NOW + timedelta(seconds=30))   # FCM ok is not an activity
    assert slot(db, "d1", 1)["state"] == "start_sent"
    assert await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A", update_token="tok")
    assert slot(db, "d1", 1)["state"] == "active"


async def test_token_arrival_applies_pending_switch():
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif")],
                       apts=[apt("a", "09:00", staff="elif", status="Tamamlandı"), apt("b", "10:20", staff="elif")])
    seed_slot(db, "d1", 1, "a", "processing", state="start_sent", token=None,
              started_at=(NOW - timedelta(seconds=30)).timestamp())
    t = RecordingTransport()
    await sweep(db, t)
    assert t.sent == []                     # switch due, no token yet: nothing sent, no crash

    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A", update_token="tok")
    await sweeper.resync(db, ORG, transport=t, now=NOW + timedelta(seconds=5))
    assert events(t) == [("update", "tok")]
    assert t.sent[0]["priority"] == 10 and t.sent[0]["alert"] is None
    assert t.sent[0]["aps"]["content-state"]["appointmentId"] == "b"
    assert (slot(db, "d1", 1)["appointment_id"], slot(db, "d1", 1)["phase_sent"]) == ("b", "upcoming")


async def test_lost_start_expires_after_120s():
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif", day=TODAY)],
                       apts=[apt("a", "10:20", staff="elif")])
    sent_at = NOW.timestamp()
    seed_slot(db, "d1", 1, "a", "upcoming", state="start_sent", token=None, started_at=sent_at, version=1)
    t = RecordingTransport()
    await sweep(db, t, now=NOW + timedelta(seconds=119))
    assert t.sent == [] and slot(db, "d1", 1)["state"] == "start_sent"

    later = NOW + timedelta(seconds=121)
    stats = await sweep(db, t, now=later)
    assert stats["expired_starts"] == 1
    assert events(t) == [("start", "pts-d1")]   # the index reopened
    s = slot(db, "d1", 1)
    assert (s["state"], s["started_at"], s["version"]) == ("start_sent", later.timestamp(), 3)

    # With the hourly start budget spent, the slot expires but stays closed.
    db2 = await make_db(users=[user("elif", role="staff")],
                        devices=[device("d1", "elif", day=TODAY, start_log=[sent_at - 60 * i for i in range(8)])],
                        apts=[apt("a", "10:20", staff="elif")])
    seed_slot(db2, "d1", 1, "a", "upcoming", state="start_sent", token=None, started_at=sent_at, version=1)
    t2 = RecordingTransport()
    await sweep(db2, t2, now=later)
    assert t2.sent == [] and slot(db2, "d1", 1)["state"] == "ended"


# --- multi-device and lifecycle ---------------------------------------------------------

async def test_two_admin_devices_independent():
    db = await make_db(users=[user("ali"), user("veli")],
                       devices=[device("d1", "ali"), device("d2", "veli")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    assert sorted(events(t)) == [("start", "pts-d1"), ("start", "pts-d2")]
    assert sorted(s["aps"]["attributes"]["slotId"] for s in t.sent) == ["d1:1", "d2:1"]

    await registry.apply_device_report(db, device_id="d1", slots=[{"slot_index": 1, "activity_id": "A1", "state": "dismissed"}],
                                       activities_enabled=True, complete=False, now=NOW)
    await registry.record_slot_token(db, device_id="d2", slot_index=1, activity_id="A2", update_token="tok2")
    db.appointments.docs[0]["service_name"] = "Fön"
    t.sent.clear()
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert events(t) == [("update", "tok2")]
    assert slot(db, "d1", 1)["state"] == "dismissed_by_user"
    assert slot(db, "d2", 1)["state"] == "active"


async def test_lazy_tamamlandi_no_extra_push():
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif")],
                       apts=[apt("a", "09:50", staff="elif")])
    t = RecordingTransport()
    await sweep(db, t, now=at("09:40"))
    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A", update_token="tok")
    await sweep(db, t, now=at("09:50", 30))
    await sweep(db, t, now=at("10:20", 30))    # derived end (status still Bekliyor)
    assert [(s["aps"]["event"], s["aps"]["content-state"]["phase"]) for s in t.sent] == [
        ("start", "upcoming"), ("update", "processing"), ("end", "completed"),
    ]
    end = t.sent[-1]["aps"]
    assert end["dismissal-date"] == int(at("10:20", 30).timestamp()) + 900

    db.appointments.docs[0]["status"] = "Tamamlandı"   # lazy auto-complete lands later
    await sweep(db, t, now=at("10:21"))
    await sweep(db, t, now=at("10:25"))
    assert len(t.sent) == 3


async def test_deleted_appointment_ends_removed_now():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", day=TODAY)], apts=[])
    seed_slot(db, "d1", 1, "gone", "upcoming")
    t = RecordingTransport()
    await sweep(db, t)
    aps = t.sent[0]["aps"]
    assert (aps["event"], aps["content-state"]["phase"], aps["dismissal-date"]) == ("end", "removed", int(NOW.timestamp()))
    assert slot(db, "d1", 1)["state"] == "ended"


async def test_cancelled_slot_end_shows_cancelled():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("a", "10:20", status="İptal")])
    seed_slot(db, "d1", 1, "a", "upcoming")
    t = RecordingTransport()
    await sweep(db, t)
    assert [(s["aps"]["event"], s["aps"]["content-state"]["phase"]) for s in t.sent] == [("end", "cancelled")]


async def test_staff_name_only_on_all_scope_and_privacy_mode():
    db = await make_db(
        settings_=[settings(lock_screen_name_mode="hidden")],
        users=[user("ali"), user("elif", role="staff", full_name="Elif Yılmaz")],
        devices=[device("d1", "ali"), device("d2", "elif")],
        apts=[apt("a", "10:20", staff="elif")],
    )
    t = RecordingTransport()
    await sweep(db, t)
    by_dev = {s["aps"]["attributes"]["slotId"]: s for s in t.sent}
    assert by_dev["d1:1"]["aps"]["content-state"]["staffName"] == "Elif Yılmaz"
    assert by_dev["d2:1"]["aps"]["content-state"]["staffName"] is None
    assert by_dev["d1:1"]["aps"]["content-state"]["customerDisplay"] is None
    assert by_dev["d1:1"]["alert"] == ("Sıradaki randevu", "Saç Kesimi · 10:20")


async def test_sector_sets_icon_token_in_content_state():
    db = await make_db(
        settings_=[settings(sector="Kuaför")],
        users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")],
    )
    t = RecordingTransport()
    await sweep(db, t)
    assert [s["aps"]["content-state"]["icon"] for s in t.sent] == ["hair"]


async def test_missing_sector_sends_generic_icon():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    assert [s["aps"]["content-state"]["icon"] for s in t.sent] == ["generic"]


async def test_removed_stub_sends_generic_icon():
    db = await make_db(settings_=[settings(sector="Kuaför")], users=[user("ali")],
                       devices=[device("d1", "ali", day=TODAY)], apts=[])
    seed_slot(db, "d1", 1, "gone", "upcoming")
    t = RecordingTransport()
    await sweep(db, t)
    assert t.sent[0]["aps"]["content-state"]["icon"] == "generic"


async def test_resync_swallows_errors(caplog):
    db = await make_db()

    def boom(*_a, **_kw):
        raise RuntimeError("mongo down")

    db.settings.find = boom
    with caplog.at_level(logging.ERROR, logger="live_activity.sweeper"):
        assert await sweeper.resync(db, ORG, transport=RecordingTransport(), now=NOW) is None
    assert "mongo down" in caplog.text


async def test_token_arriving_during_expiry_keeps_slot_active(monkeypatch):
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif", day=TODAY)],
                       apts=[apt("a", "10:20", staff="elif")])
    seed_slot(db, "d1", 1, "a", "upcoming", state="start_sent", token=None,
              started_at=(NOW - timedelta(seconds=200)).timestamp(), version=1)
    real = registry.slots_for_device
    calls = []

    async def snapshot_then_token(db_, device_id):
        slots = await real(db_, device_id)
        if not calls:  # the token lands right after the sweep's first snapshot
            assert await registry.record_slot_token(db_, device_id=device_id, slot_index=1,
                                                    activity_id="A", update_token="live")
        calls.append(device_id)
        return slots

    monkeypatch.setattr(registry, "slots_for_device", snapshot_then_token)
    t = RecordingTransport()
    stats = await sweep(db, t)
    # No second push-to-start for the same appointment; the live activity just gets its update.
    assert events(t) == [("update", "live")]
    assert stats["expired_starts"] == 0 and stats["claim_lost"] == 0
    s = slot(db, "d1", 1)
    assert (s["state"], s["update_token"], s["activity_id"]) == ("active", "live", "A")


async def test_owner_change_during_sweep_sends_nothing_for_old_owner(monkeypatch):
    db = await make_db(users=[user("ali"), user("veli")], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("a", "10:20"), apt("b", "10:40")])
    seed_slot(db, "d1", 1, "a", "upcoming", content_hash="stale")   # would get an update
    seed_slot(db, "d1", 2, "x", "upcoming", state="ended", token=None)  # would be reopened by a start
    real = registry.slots_for_device
    reowned = []

    async def snapshot_then_reown(db_, device_id):
        slots = await real(db_, device_id)
        if not reowned:  # the phone is signed in by someone else right after the snapshot
            _, secret = await registry.upsert_device(
                db_, device_id="d1", organization_id=ORG, user_id="id-veli", username="veli",
                os_version="18.1", app_build="100", fcm_token="fcm-d1", push_to_start_token="pts-d1",
                activities_enabled=True)
            reowned.append(secret)
        return slots

    monkeypatch.setattr(registry, "slots_for_device", snapshot_then_reown)
    t = RecordingTransport()
    stats = await sweep(db, t)
    assert reowned and reowned[0]          # the owner really changed (new secret issued)
    assert t.sent == []                    # nothing of ali's reaches veli's phone
    assert stats["claim_lost"] == 2
    assert {s["state"] for s in db.live_activity_slots.docs} == {"ended"}


async def test_owner_change_during_sweep_fresh_slot_index_sends_nothing(monkeypatch):
    # No slot rows yet: the start's claim is an insert, which no version bump can stop.
    db = await make_db(users=[user("ali"), user("veli")], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("a", "10:20")])
    real = registry.slots_for_device
    reowned = []

    async def snapshot_then_reown(db_, device_id):
        slots = await real(db_, device_id)
        if not reowned:
            await registry.upsert_device(
                db_, device_id="d1", organization_id=ORG, user_id="id-veli", username="veli",
                os_version="18.1", app_build="100", fcm_token="fcm-d1", push_to_start_token="pts-d1",
                activities_enabled=True)
            reowned.append(True)
        return slots

    monkeypatch.setattr(registry, "slots_for_device", snapshot_then_reown)
    t = RecordingTransport()
    stats = await sweep(db, t)
    assert reowned
    assert t.sent == []                       # ali's appointment never reaches veli's phone
    assert stats["owner_changed"] == 1
    assert slot(db, "d1", 1)["state"] == "ended"
    assert dev(db, "d1")["start_log"] == []   # a start that was never sent is not counted
    assert dev(db, "d1")["day"] is None       # reset by the re-own; the unsent start did not reopen it


async def test_device_gone_before_send_sends_nothing(monkeypatch):
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    real = registry.slots_for_device

    async def snapshot_then_delete(db_, device_id):
        slots = await real(db_, device_id)
        db_.live_activity_devices.docs.clear()   # logout removed the device mid-sweep
        return slots

    monkeypatch.setattr(registry, "slots_for_device", snapshot_then_delete)
    t = RecordingTransport()
    await sweep(db, t)
    assert t.sent == []
    assert slot(db, "d1", 1)["state"] == "ended"


# --- final review fixes -------------------------------------------------------------------

async def test_reassigned_away_ends_now_with_removed_stub():
    db = await make_db(users=[user("elif", role="staff"), user("can", role="staff")],
                       devices=[device("d1", "elif", day=TODAY)],
                       apts=[apt("a", "10:20", staff="can")])   # reassigned Elif -> Can
    seed_slot(db, "d1", 1, "a", "upcoming", content_hash="x")
    t = RecordingTransport()
    await sweep(db, t)
    assert events(t) == [("end", "tok")]
    aps = t.sent[0]["aps"]
    cs = aps["content-state"]
    assert aps["dismissal-date"] == aps["timestamp"]           # immediately
    assert cs["phase"] == "removed"
    assert (cs["customerDisplay"], cs["serviceName"], cs["staffName"], cs["startLabel"]) == (None, "", None, "")
    assert "Ayşe" not in str(aps) and "Saç" not in str(aps)
    assert slot(db, "d1", 1)["state"] == "ended"


async def test_completed_still_ends_soon_with_final_content():
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif", day=TODAY)],
                       apts=[apt("a", "09:40", staff="elif", status="Tamamlandı")])
    seed_slot(db, "d1", 1, "a", "processing")
    t = RecordingTransport()
    await sweep(db, t)
    aps = t.sent[0]["aps"]
    assert (aps["event"], aps["content-state"]["phase"]) == ("end", "completed")
    assert aps["content-state"]["customerDisplay"] == "Ayşe Kaya"
    assert aps["dismissal-date"] == int(NOW.timestamp()) + 900


@pytest.mark.parametrize("os_version,expected", [
    ("17.5", False), ("17.4.1", False), (None, False), ("", False), ("beta", False),
    ("18.0", True), ("18", True), ("26.0", True), (" 18.2 ", True),
])
async def test_input_push_token_only_on_ios18_plus(os_version, expected):
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", os_version=os_version)],
                       apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    assert events(t) == [("start", "pts-d1")]
    assert ("input-push-token" in t.sent[0]["aps"]) is expected


async def test_start_locally_items_carry_attributes():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", push_to_start_token=None)],
                       apts=[apt("a", "10:20")])
    out = await sweeper.start_locally(db, "d1", now=NOW)
    assert [o["slot_index"] for o in out] == [1]
    assert out[0]["attributes"] == {"slotId": "d1:1", "orgId": ORG}


async def test_start_locally_does_not_spend_push_to_start_budget():
    db = await make_db(users=[user("ali", live_activity_slot_count=2)],
                       devices=[device("d1", "ali", push_to_start_token=None)],
                       apts=[apt("a", "10:20"), apt("b", "10:25")])
    out = await sweeper.start_locally(db, "d1", now=NOW)
    assert [o["slot_index"] for o in out] == [1, 2]
    assert dev(db, "d1")["start_log"] == []     # the push-to-start budget does not apply
    assert dev(db, "d1")["day"] == TODAY


async def test_switch_to_todays_appointment_opens_the_day():
    # A slot carried over from yesterday switches to today's first appointment (no start today).
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif", day="2026-11-15")],
                       apts=[apt("y", "23:00", staff="elif", date="2026-11-15", status="Tamamlandı"),
                             apt("b", "10:20", staff="elif"), apt("c", "13:00", staff="elif")])
    seed_slot(db, "d1", 1, "y", "processing", day="2026-11-15")
    t = RecordingTransport()
    await sweep(db, t)
    assert events(t) == [("update", "tok")]
    assert t.sent[0]["aps"]["content-state"]["appointmentId"] == "b"
    assert dev(db, "d1")["day"] == TODAY
    # with the day open, the 13:00 appointment (outside the lead window) follows b
    db.appointments.docs[1]["status"] = "Tamamlandı"
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert t.sent[-1]["aps"]["content-state"]["appointmentId"] == "c"


async def test_update_of_yesterdays_appointment_does_not_open_the_day():
    db = await make_db(users=[user("elif", role="staff")], devices=[device("d1", "elif", day="2026-11-15")],
                       apts=[apt("y", "23:30", staff="elif", date="2026-11-15", duration=720)])  # processing past midnight
    seed_slot(db, "d1", 1, "y", "processing", content_hash="stale", day="2026-11-15")
    t = RecordingTransport()
    await sweep(db, t)
    assert events(t) == [("update", "tok")]
    assert dev(db, "d1")["day"] == "2026-11-15"


async def test_non_int_duration_does_not_kill_device_sweep():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("bad", "10:10", duration="45"), apt("a", "10:20")])
    seed_slot(db, "d1", 1, "bad", "upcoming")   # a slot already holding the unreadable one
    t = RecordingTransport()
    stats = await sweep(db, t)
    assert stats["errors"] == 0
    assert events(t) == [("update", "tok")]
    assert t.sent[0]["aps"]["content-state"]["appointmentId"] == "a"


# --- across midnight ---------------------------------------------------------------------

LATE = datetime(2026, 11, 16, 23, 50, tzinfo=TR_TZ)
TOMORROW = "2026-11-17"


async def test_load_org_includes_tomorrow():
    db = await make_db(apts=[apt("n", "00:15", date=TOMORROW), apt("far", "09:00", date="2026-11-18")])
    org = await sweeper.load_org(db, settings(), LATE)
    assert {a["id"] for a in org.apts} == {"n"}


async def test_tomorrow_appointment_starts_inside_lead_without_opening_old_day():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", day=None)],
                       apts=[apt("n", "00:15", date=TOMORROW)])
    t = RecordingTransport()
    await sweep(db, t, now=LATE)
    assert [e for e, _ in events(t)] == ["start"]
    assert t.sent[0]["aps"]["content-state"]["appointmentId"] == "n"
    assert dev(db, "d1")["day"] != TODAY


async def test_tomorrow_appointment_outside_lead_gets_no_start():
    db = await make_db(users=[user("ali")], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("n", "00:15", date=TOMORROW)])
    t = RecordingTransport()
    await sweep(db, t, now=datetime(2026, 11, 16, 22, 0, tzinfo=TR_TZ))
    assert events(t) == []


async def test_widget_summary_still_today_only_near_midnight():
    from live_activity.widget_summary import build_summary
    db = await make_db(users=[user("ali")],
                       apts=[apt("n", "00:15", date=TOMORROW), apt("t", "23:55", date=TODAY)])
    body = await build_summary(db, {"organization_id": ORG, "username": "ali", "role": "admin"}, None, now=LATE)
    assert body["counts"]["total"] == 1
    assert [i["id"] for i in body["items"]] == ["t"]


async def test_start_into_dismissed_today_slot_is_recorded_and_keeps_the_dismissal():
    db = await make_db(users=[user("ali", live_activity_slot_count=2)], devices=[device("d1", "ali")],
                       apts=[apt("a", "10:20"), apt("b", "10:25"), apt("c", "10:28")])
    t = RecordingTransport()
    await sweep(db, t)                                   # a -> slot 1
    await sweep(db, t, now=NOW + timedelta(seconds=30))  # b -> slot 2
    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A1", update_token="t1")
    await registry.record_slot_token(db, device_id="d1", slot_index=2, activity_id="A2", update_token="t2")
    await registry.apply_device_report(db, device_id="d1", slots=[{"slot_index": 1, "activity_id": "A1",
                                                                   "state": "dismissed"}],
                                       activities_enabled=True, complete=False, now=NOW + timedelta(seconds=40))
    version = slot(db, "d1", 1)["version"]
    t.sent.clear()

    await sweep(db, t, now=NOW + timedelta(seconds=60))  # c (inside the lead) reopens the dismissed slot 1
    assert events(t) == [("start", "pts-d1")]
    assert t.sent[0]["aps"]["content-state"]["appointmentId"] == "c"
    assert t.sent[0]["aps"]["attributes"]["slotId"] == "d1:1"
    s = slot(db, "d1", 1)
    assert (s["state"], s["appointment_id"], s["update_token"], s["activity_id"], s["day"]) == (
        "start_sent", "c", None, None, TODAY)
    assert s["version"] == version + 1
    assert (s["dismissed_day"], s["dismissed_ids"]) == (TODAY, ["a"])

    # a stays hidden: when b's slot frees up, a does not come back in either slot
    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A3", update_token="t3")
    db.appointments.docs[:] = [d for d in db.appointments.docs if d["id"] != "b"]
    t.sent.clear()
    for k in range(2, 5):
        await sweep(db, t, now=NOW + timedelta(seconds=60 * k))
    assert all(x["aps"]["content-state"].get("appointmentId") != "a" for x in t.sent)
    assert [e for e, _ in events(t)] == ["end"]  # b's card is removed; nothing else is sent


def sent_ids(t):
    return [x["aps"]["content-state"].get("appointmentId") for x in t.sent]


async def test_start_into_pre_deploy_dismissed_slot_keeps_its_appointment_hidden():
    # A dismissal recorded before dismissed_ids existed: only the slot's state says a was dismissed.
    db = await make_db(users=[user("ali", live_activity_slot_count=1)], devices=[device("d1", "ali", day=TODAY)],
                       apts=[apt("a", "10:20"), apt("b", "10:25")])
    seed_slot(db, "d1", 1, "a", "upcoming", state="dismissed_by_user", token=None)
    t = RecordingTransport()
    await sweep(db, t)
    assert (events(t), sent_ids(t)) == ([("start", "pts-d1")], ["b"])
    s = slot(db, "d1", 1)
    assert (s["state"], s["appointment_id"], s["dismissed_day"], s["dismissed_ids"]) == (
        "start_sent", "b", TODAY, ["a"])
    await registry.record_slot_token(db, device_id="d1", slot_index=1, activity_id="A1", update_token="t1")
    db.users.docs[0]["live_activity_slot_count"] = 2  # a free index: a must still not come back
    t.sent.clear()
    await sweep(db, t, now=NOW + timedelta(seconds=30))
    assert events(t) == []


async def test_start_locally_into_pre_deploy_dismissed_slot_keeps_its_appointment_hidden():
    db = await make_db(users=[user("ali", live_activity_slot_count=1)],
                       devices=[device("d1", "ali", push_to_start_token=None, day=TODAY)],
                       apts=[apt("a", "10:20"), apt("b", "10:25")])
    seed_slot(db, "d1", 1, "a", "upcoming", state="dismissed_by_user", token=None)
    out = await sweeper.start_locally(db, "d1", now=NOW)
    assert [(o["slot_index"], o["content"]["appointmentId"]) for o in out] == [(1, "b")]
    assert (slot(db, "d1", 1)["dismissed_day"], slot(db, "d1", 1)["dismissed_ids"]) == (TODAY, ["a"])
    db.users.docs[0]["live_activity_slot_count"] = 2
    assert await sweeper.start_locally(db, "d1", now=NOW + timedelta(seconds=30)) == []
