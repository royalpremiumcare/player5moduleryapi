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
        "activities_enabled": True, "start_log": [], "day": None, **kw,
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


async def test_inactive_user_device_skipped():
    db = await make_db(users=[user("ali", status="passive")], devices=[device("d1", "ali")], apts=[apt("a", "10:20")])
    t = RecordingTransport()
    await sweep(db, t)
    assert t.sent == []


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
    assert start["alert"] == ("Sıradaki randevu", "Ayşe K. · Saç Kesimi · 10:20")
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


async def test_resync_swallows_errors(caplog):
    db = await make_db()

    def boom(*_a, **_kw):
        raise RuntimeError("mongo down")

    db.settings.find = boom
    with caplog.at_level(logging.ERROR, logger="live_activity.sweeper"):
        assert await sweeper.resync(db, ORG, transport=RecordingTransport(), now=NOW) is None
    assert "mongo down" in caplog.text
