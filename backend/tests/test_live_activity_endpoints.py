import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from live_activity import endpoints, registry
from live_activity.phase import TR_TZ
from live_activity.transport import RecordingTransport
from tests.live_activity_fakes import WRITE_METHODS, FakeDB

ORG = "org1"
TODAY = "2026-11-16"
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=TR_TZ)
SECRET_HEADER = "X-Plann-Device-Secret"


class FakeUser(BaseModel):
    """Shape of server.User as far as these endpoints read it."""
    id: str
    username: str
    role: str = "admin"
    organization_id: str = ORG
    full_name: str | None = None
    can_view_all_appointments: bool = False


def jwt_user(username, role="admin", org=ORG, **kw):
    return FakeUser(id=f"id-{username}", username=username, role=role, organization_id=org,
                    full_name=username.title(), **kw)


def user_doc(username, role="admin", org=ORG, **kw):
    return {"organization_id": org, "id": f"id-{username}", "username": username, "role": role,
            "status": "active", "full_name": kw.pop("full_name", username.title()), **kw}


def apt(id, time, *, staff=None, status="Bekliyor", date=TODAY, duration=30, customer="Ayşe Kaya",
        service="Saç Kesimi", org=ORG):
    return {
        "organization_id": org, "id": id, "customer_name": customer, "service_name": service,
        "appointment_date": date, "appointment_time": time, "status": status,
        "staff_member_id": staff, "service_duration": duration, "customer_id": "cust-secret-id",
        "phone": "05551112233", "notes": "private note", "service_price": 450.0,
    }


def device_doc(device_id, username, org=ORG, **kw):
    return {
        "device_id": device_id, "organization_id": org, "user_id": f"id-{username}", "username": username,
        "fcm_token": f"fcm-{device_id}", "push_to_start_token": f"pts-{device_id}",
        "activities_enabled": True, "start_log": [], "day": None,
        "secret_sha256": registry._hash_secret(f"secret-{device_id}"), **kw,
    }


def seed_slot(db, device_id, idx, *, state="active", activity_id=None, token=None, aid="a1",
              phase="upcoming", version=3):
    db.live_activity_slots.docs.append({
        "device_id": device_id, "slot_index": idx, "state": state, "appointment_id": aid,
        "phase_sent": phase, "content_hash": "h", "activity_id": activity_id, "update_token": token,
        "started_at": (NOW - timedelta(hours=1)).timestamp(), "version": version, "day": TODAY,
    })


def slot(db, device_id, idx):
    return next(s for s in db.live_activity_slots.docs if s["device_id"] == device_id and s["slot_index"] == idx)


def _refuse(*_a, **_kw):
    raise AssertionError("configured dependency used instead of the test override")


@pytest.fixture
def env(monkeypatch):
    db = FakeDB()
    asyncio.run(registry.ensure_indexes(db))
    db.settings.docs.append({"organization_id": ORG, "live_activity_enabled": True})
    transport = RecordingTransport()
    current = {"user": jwt_user("ali"), "jwt": None}

    async def get_current_user(_request, token, _db):  # stands in for server.get_current_user
        if token == "valid" and current["jwt"] is not None:
            return current["jwt"]
        raise endpoints._unauthorized()

    endpoints.configure(get_current_user, _refuse, transport=transport)
    resyncs = []

    def fake_resync(db_, org_id, **_kw):
        resyncs.append((db_, org_id))
        return asyncio.sleep(0)

    monkeypatch.setattr(endpoints, "resync", fake_resync)
    monkeypatch.setattr(endpoints, "_now", lambda: NOW)
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api")
    app.dependency_overrides[endpoints._current_user] = lambda: current["user"]
    app.dependency_overrides[endpoints._db] = lambda: db
    db.log.clear()
    return SimpleNamespace(db=db, client=TestClient(app), transport=transport, resyncs=resyncs, current=current)


def writes(db):
    return [entry for entry in db.log if entry[1] in WRITE_METHODS]


# --- devices -----------------------------------------------------------------------------------

REGISTER = {"device_id": "d1", "os_version": "18.1", "app_build": "100", "fcm_token": "fcm-d1",
            "push_to_start_token": "pts-d1", "activities_enabled": True}


def test_device_reowned_rotates_secret(env):
    first = env.client.post("/api/live-activities/devices", json=REGISTER)
    assert first.status_code == 200
    s1 = first.json()["device_secret"]
    assert s1

    again = env.client.post("/api/live-activities/devices", json=REGISTER)
    assert again.status_code == 200
    assert again.json().get("device_secret") is None  # same owner: no new secret

    env.current["user"] = jwt_user("veli")
    second = env.client.post("/api/live-activities/devices", json=REGISTER)
    s2 = second.json()["device_secret"]
    assert s2 and s2 != s1

    token = {"device_id": "d1", "slot_index": 1, "activity_id": "A", "update_token": "T"}
    assert env.client.post("/api/live-activities/token", json=token, headers={SECRET_HEADER: s1}).status_code == 401
    assert env.client.post("/api/live-activities/token", json=token, headers={SECRET_HEADER: s2}).status_code == 204
    row = env.db.live_activity_devices.docs[0]
    assert (row["user_id"], row["username"], row["organization_id"]) == ("id-veli", "veli", ORG)
    assert "secret_sha256" in row and s2 not in json.dumps(row, default=str)


def test_logout_removes_device_ends_slots_and_revokes_secret(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, activity_id="A", token="tok-1")
    seed_slot(env.db, "d1", 2, state="ended", activity_id="B", token=None)

    env.current["user"] = jwt_user("veli")
    assert env.client.delete("/api/live-activities/devices/d1").status_code == 403
    assert env.db.live_activity_devices.docs

    env.current["user"] = jwt_user("ali")
    assert env.client.delete("/api/live-activities/devices/d1").status_code == 204
    assert env.db.live_activity_devices.docs == []
    assert {s["state"] for s in env.db.live_activity_slots.docs} == {"ended"}
    assert slot(env.db, "d1", 1)["version"] == 4  # bumped: an in-flight sweep loses its claim
    assert [(m["la_token"], m["aps"]["event"]) for m in env.transport.sent] == [("tok-1", "end")]
    assert env.transport.sent[0]["aps"]["content-state"]["customerDisplay"] is None

    token = {"device_id": "d1", "slot_index": 1, "activity_id": "A", "update_token": "T"}
    resp = env.client.post("/api/live-activities/token", json=token, headers={SECRET_HEADER: "secret-d1"})
    assert resp.status_code == 401
    assert env.client.delete("/api/live-activities/devices/d1").status_code == 204  # idempotent


# --- token -------------------------------------------------------------------------------------

TOKEN = {"device_id": "d1", "slot_index": 1, "activity_id": "A", "update_token": "T"}


def test_token_requires_secret(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    env.db.live_activity_devices.docs.append(device_doc("d2", "ali"))
    seed_slot(env.db, "d1", 1, state="start_sent")

    assert env.client.post("/api/live-activities/token", json=TOKEN).status_code == 401
    for bad in ("wrong", "secret-d2", ""):
        resp = env.client.post("/api/live-activities/token", json=TOKEN, headers={SECRET_HEADER: bad})
        assert resp.status_code == 401
    # A JWT alone is not enough for this endpoint.
    env.current["jwt"] = jwt_user("ali")
    assert env.client.post("/api/live-activities/token", json=TOKEN, headers=BEARER).status_code == 401
    assert slot(env.db, "d1", 1)["state"] == "start_sent"
    assert env.resyncs == []

    resp = env.client.post("/api/live-activities/token", json=TOKEN, headers={SECRET_HEADER: "secret-d1"})
    assert resp.status_code == 204
    s = slot(env.db, "d1", 1)
    assert (s["state"], s["activity_id"], s["update_token"]) == ("active", "A", "T")


def test_token_triggers_resync(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, state="start_sent")
    resp = env.client.post("/api/live-activities/token", json=TOKEN, headers={SECRET_HEADER: "secret-d1"})
    assert resp.status_code == 204
    assert env.resyncs == [(env.db, ORG)]
    assert env.transport.sent == []


def test_token_rotation_updates_active_slot(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, state="active", activity_id="A", token="old")
    resp = env.client.post("/api/live-activities/token", json=TOKEN, headers={SECRET_HEADER: "secret-d1"})
    assert resp.status_code == 204
    s = slot(env.db, "d1", 1)
    assert (s["state"], s["update_token"], s["version"]) == ("active", "T", 4)
    assert env.transport.sent == []  # the live card is not ended


def test_late_token_ends_orphan_activity(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, state="ended", activity_id=None, token=None)  # lost-start expiry ran
    resp = env.client.post("/api/live-activities/token", json=TOKEN, headers={SECRET_HEADER: "secret-d1"})
    assert resp.status_code == 204
    s = slot(env.db, "d1", 1)
    assert (s["state"], s["update_token"]) == ("ended", None)  # not resurrected

    assert len(env.transport.sent) == 1
    sent = env.transport.sent[0]
    assert (sent["fcm_token"], sent["la_token"], sent["alert"]) == ("fcm-d1", "T", None)
    aps = sent["aps"]
    now_epoch = int(NOW.timestamp())
    assert (aps["event"], aps["dismissal-date"], aps["relevance-score"]) == ("end", now_epoch, 0)
    assert aps["content-state"]["phase"] == "removed"
    assert aps["content-state"]["customerDisplay"] is None
    assert env.resyncs == []


# --- reconcile ---------------------------------------------------------------------------------

BEARER = {"Authorization": "Bearer valid"}
EMPTY = {"end": [], "end_activities": [], "start_locally": []}


def reconcile(env, slots, *, complete, device_id="d1", secret="secret-d1", bearer=None, **extra):
    body = {"device_id": device_id, "activities_enabled": True, "complete": complete, "slots": slots, **extra}
    headers = {SECRET_HEADER: secret} if secret is not None else {}
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    return env.client.post("/api/live-activities/reconcile", json=body, headers=headers)


def test_reconcile_partial_does_not_end_unlisted(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, activity_id="A1", token="t1")
    seed_slot(env.db, "d1", 2, activity_id="A2", token="t2")

    resp = reconcile(env, [{"slot_index": 1, "activity_id": "A1", "state": "active"}], complete=False)
    assert resp.status_code == 200
    assert resp.json() == EMPTY
    assert (slot(env.db, "d1", 1)["state"], slot(env.db, "d1", 2)["state"]) == ("active", "active")

    resp = reconcile(env, [{"slot_index": 1, "activity_id": "A1", "state": "active"}], complete=True)
    assert resp.status_code == 200
    assert (slot(env.db, "d1", 1)["state"], slot(env.db, "d1", 2)["state"]) == ("active", "ended")


def test_reconcile_ends_unknown_and_ignores_stale_reports(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, activity_id="A1", token="t1")
    seed_slot(env.db, "d1", 2, state="ended", activity_id="A2", token=None)
    seed_slot(env.db, "d1", 3, state="start_sent")
    resp = reconcile(env, [
        {"slot_index": 1, "activity_id": "OLD", "state": "ended"},   # an older activity of slot 1
        {"slot_index": 1, "activity_id": "A1", "state": "active"},
        {"slot_index": 2, "activity_id": "A2", "state": "active"},   # server already ended it
        {"slot_index": 3, "activity_id": "A3", "state": "active"},   # push-to-start landed, token pending
        {"slot_index": 4, "activity_id": "X", "state": "active"},    # unknown to the server
    ], complete=True)
    assert resp.status_code == 200
    assert (resp.json()["end"], resp.json()["end_activities"]) == ([2], ["X"])
    assert slot(env.db, "d1", 1)["state"] == "active"
    assert slot(env.db, "d1", 2)["state"] == "ended"
    assert slot(env.db, "d1", 3)["state"] == "start_sent"  # the token callback still lands
    resp = env.client.post("/api/live-activities/token", headers={SECRET_HEADER: "secret-d1"},
                           json={"device_id": "d1", "slot_index": 3, "activity_id": "A3", "update_token": "t3"})
    assert resp.status_code == 204
    assert slot(env.db, "d1", 3)["state"] == "active"

    # Alone, a report that an older activity of a slot ended (or was dismissed) changes nothing.
    for state in ("ended", "dismissed"):
        resp = reconcile(env, [{"slot_index": 1, "activity_id": "OLD", "state": state}], complete=False)
        assert resp.json()["end"] == []
        assert slot(env.db, "d1", 1)["state"] == "active"
    resp = reconcile(env, [{"slot_index": 1, "activity_id": "A1", "state": "dismissed"}], complete=False)
    assert slot(env.db, "d1", 1)["state"] == "dismissed_by_user"
    assert env.resyncs == [(env.db, ORG)] * 2  # token callback, then the dismissal


def test_reconcile_auth_secret_or_owner_jwt(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    assert reconcile(env, [], complete=False, secret=None).status_code == 401
    assert reconcile(env, [], complete=False, secret="wrong").status_code == 401
    assert reconcile(env, [], complete=False, secret="").status_code == 401

    env.current["jwt"] = jwt_user("veli")
    assert reconcile(env, [], complete=False, secret=None, bearer="valid").status_code == 403
    env.current["jwt"] = jwt_user("ali", org="org2")
    assert reconcile(env, [], complete=False, secret=None, bearer="valid").status_code == 403
    env.current["jwt"] = jwt_user("ali")
    assert reconcile(env, [], complete=False, secret=None, bearer="valid", device_id="nope").status_code == 403
    assert reconcile(env, [], complete=False, secret=None, bearer="stale").status_code == 401
    assert reconcile(env, [], complete=False, secret=None, bearer="valid").status_code == 200
    # A wrong secret is never rescued by a valid JWT.
    assert reconcile(env, [], complete=False, secret="wrong", bearer="valid").status_code == 401


def test_reconcile_valid_secret_with_stale_bearer_200(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, activity_id="A1", token="t1")
    resp = reconcile(env, [{"slot_index": 1, "activity_id": "A1", "state": "active"}], complete=True,
                     bearer="stale")
    assert resp.status_code == 200
    assert resp.json() == EMPTY
    assert slot(env.db, "d1", 1)["state"] == "active"
    # Without a secret the stale bearer is still refused.
    assert reconcile(env, [], complete=False, secret=None, bearer="stale").status_code == 401


def test_reconcile_same_index_stale_sibling_keeps_tracked(env):
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    seed_slot(env.db, "d1", 1, activity_id="A1", token="t1")
    for order in (["OLD", "A1"], ["A1", "OLD"]):
        resp = reconcile(env, [{"slot_index": 1, "activity_id": a, "state": "active"} for a in order],
                         complete=True)
        assert resp.status_code == 200
        assert (resp.json()["end"], resp.json()["end_activities"]) == ([], ["OLD"])
        assert slot(env.db, "d1", 1)["state"] == "active"
    assert slot(env.db, "d1", 1)["version"] == 3  # untouched


def test_reconcile_start_locally_only_without_push_to_start(env):
    env.db.users.docs.append(user_doc("ali"))
    env.db.appointments.docs.append(apt("a1", "10:20"))
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    env.db.live_activity_devices.docs.append(device_doc("d2", "ali", push_to_start_token=None))

    resp = reconcile(env, [], complete=True)
    assert resp.json()["start_locally"] == []
    assert env.db.live_activity_slots.docs == []

    resp = reconcile(env, [], complete=True, device_id="d2", secret="secret-d2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["start_locally"]) == 1
    start = body["start_locally"][0]
    start_epoch = int(NOW.replace(minute=20).timestamp())
    assert (start["slot_index"], start["stale_epoch"]) == (1, start_epoch)
    assert start["relevance"] == pytest.approx(48.0)
    content = start["content"]
    assert (content["appointmentId"], content["phase"], content["customerDisplay"]) == ("a1", "upcoming", "Ayşe K.")
    assert env.transport.sent == []  # handed to the app, never pushed

    s = slot(env.db, "d2", 1)
    assert (s["state"], s["appointment_id"], s["update_token"]) == ("start_sent", "a1", None)
    resp = env.client.post("/api/live-activities/token", headers={SECRET_HEADER: "secret-d2"},
                           json={"device_id": "d2", "slot_index": 1, "activity_id": "L1", "update_token": "lt"})
    assert resp.status_code == 204
    assert slot(env.db, "d2", 1)["state"] == "active"
    assert env.transport.sent == []

    # Already started: the next foreground reconcile asks for nothing new.
    resp = reconcile(env, [{"slot_index": 1, "activity_id": "L1", "state": "active"}], complete=True,
                     device_id="d2", secret="secret-d2")
    assert resp.json() == EMPTY


def test_reconcile_start_locally_respects_disabled(env):
    env.db.users.docs.append(user_doc("ali"))
    env.db.appointments.docs.append(apt("a1", "10:20"))
    env.db.live_activity_devices.docs.append(device_doc("d2", "ali", push_to_start_token=None))
    body = {"device_id": "d2", "activities_enabled": False, "complete": True, "slots": []}
    resp = env.client.post("/api/live-activities/reconcile", json=body, headers={SECRET_HEADER: "secret-d2"})
    assert resp.json()["start_locally"] == []
    env.db.settings.docs[0]["live_activity_enabled"] = False
    assert reconcile(env, [], complete=True, device_id="d2", secret="secret-d2").json()["start_locally"] == []
    assert env.db.live_activity_slots.docs == []


# --- preferences -------------------------------------------------------------------------------

def test_preferences_staff_cannot_choose_all_or_slots(env):
    env.db.users.docs.extend([user_doc("ali"), user_doc("elif", role="staff"),
                              user_doc("elif", role="staff", org="org2")])
    env.current["user"] = jwt_user("elif", role="staff")
    url = "/api/live-activities/preferences"
    assert env.client.put(url, json={"scope": "all"}).status_code == 403
    assert env.client.put(url, json={"slot_count": 3}).status_code == 403
    assert env.client.put(url, json={"scope": "everything"}).status_code == 422
    assert writes(env.db) == []

    resp = env.client.put(url, json={"scope": "own", "slot_count": 1, "start_alert": True})
    assert resp.status_code == 200
    assert resp.json() == {"scope": "own", "slot_count": 1, "start_alert": True}
    [(coll, method, (flt, update))] = writes(env.db)
    assert (coll, method, flt) == ("users", "update_one", {"organization_id": ORG, "username": "elif"})
    assert update == {"$set": {"live_activity_scope": "own", "live_activity_slot_count": 1,
                               "live_activity_start_alert": True}}
    assert "live_activity_scope" not in env.db.users.docs[2]  # same username, other org


def test_preferences_admin_slot_count_clamped(env):
    env.db.users.docs.extend([user_doc("ali"), user_doc("elif", role="staff")])
    url = "/api/live-activities/preferences"
    resp = env.client.put(url, json={"slot_count": 9})
    assert resp.json() == {"scope": "all", "slot_count": 5, "start_alert": False}
    assert env.db.users.docs[0]["live_activity_slot_count"] == 5
    assert env.client.put(url, json={"slot_count": 0}).json()["slot_count"] == 1
    assert env.client.put(url, json={"slot_count": 3, "scope": "own"}).json() == \
        {"scope": "own", "slot_count": 1, "start_alert": False}

    env.db.users.docs.append(user_doc("can", role="staff", can_view_all_appointments=True))
    env.current["user"] = jwt_user("can", role="staff", can_view_all_appointments=True)
    assert env.client.put(url, json={"scope": "all", "slot_count": 3}).json() == \
        {"scope": "all", "slot_count": 3, "start_alert": False}


# --- widget ------------------------------------------------------------------------------------

def seed_day(env, **settings):
    env.db.settings.docs[0].update(settings)
    env.db.users.docs.extend([
        user_doc("ali"), user_doc("elif", role="staff", full_name="Elif Demir"),
        user_doc("can", role="staff", can_view_all_appointments=True, full_name="Can Yıldız"),
    ])
    env.db.appointments.docs.extend([
        apt("done", "08:00", staff="elif", status="Tamamlandı"),
        apt("past", "09:00", staff="can"),                       # derived completed
        apt("proc", "09:50", staff="elif", customer="Mehmet Öz"),  # processing
        apt("cancel", "11:00", staff="elif", status="İptal"),
        apt("pay", "11:30", staff="elif", status="Ödeme Bekleniyor"),
        apt("can1", "12:00", staff="can"),
        apt("unas", "13:00", staff=None),
        apt("e2", "14:00", staff="elif"),
        apt("e3", "15:00", staff="elif"),
        apt("e4", "16:00", staff="elif"),
        apt("e5", "17:00", staff="elif"),
        apt("tomorrow", "10:30", staff="elif", date="2026-11-17"),
        apt("other-org", "10:30", staff="elif", org="org2"),
    ])


def test_widget_admin_default_all_manager_default_own(env):
    seed_day(env)
    body = env.client.get("/api/widget/summary").json()
    assert body["scope"] == "all"
    assert [i["id"] for i in body["items"]] == ["proc", "can1", "unas", "e2", "e3", "e4"]
    assert body["counts"] == {"total": 9, "completed": 2, "remaining": 7}
    assert body["items"][0]["staffName"] == "Elif Demir"
    assert body["items"][0]["phase"] == "processing"
    assert body["generatedAt"] == NOW.isoformat()
    assert body["privacyMode"] == "initials"

    env.current["user"] = jwt_user("can", role="staff", can_view_all_appointments=True)
    body = env.client.get("/api/widget/summary").json()
    assert body["scope"] == "own"
    assert [i["id"] for i in body["items"]] == ["can1"]
    assert body["counts"] == {"total": 2, "completed": 1, "remaining": 1}
    assert "staffName" not in body["items"][0]
    assert env.client.get("/api/widget/summary?scope=all").json()["scope"] == "all"

    env.current["user"] = jwt_user("elif", role="staff")
    body = env.client.get("/api/widget/summary?scope=all").json()  # plain staff cannot widen
    assert body["scope"] == "own"
    assert [i["id"] for i in body["items"]] == ["proc", "e2", "e3", "e4", "e5"]
    assert body["counts"] == {"total": 6, "completed": 1, "remaining": 5}


def test_widget_invalid_scope_422(env):
    seed_day(env)
    assert env.client.get("/api/widget/summary?scope=everyone").status_code == 422
    assert env.client.get("/api/widget/summary?scope=").status_code == 422


def test_widget_includes_unassigned_for_admin(env):
    seed_day(env)
    own = env.client.get("/api/widget/summary?scope=own").json()
    assert own["scope"] == "own"
    assert [i["id"] for i in own["items"]] == ["unas"]
    assert own["counts"] == {"total": 1, "completed": 0, "remaining": 1}
    assert "unas" in [i["id"] for i in env.client.get("/api/widget/summary").json()["items"]]


def test_widget_payload_has_no_phone_notes_price(env):
    seed_day(env, lock_screen_name_mode="full")
    resp = env.client.get("/api/widget/summary")
    raw = resp.text
    for leak in ("05551112233", "private note", "450.0", "cust-secret-id", "phone", "notes", "price",
                 "customer_id", "customer_name"):
        assert leak not in raw
    allowed = {"id", "startLabel", "endLabel", "startEpoch", "endEpoch", "phase", "customerDisplay",
               "serviceName", "staffName"}
    for item in resp.json()["items"]:
        assert set(item) <= allowed
    assert resp.json()["items"][0]["customerDisplay"] == "Mehmet Öz"


def test_widget_hidden_mode_nulls_names(env):
    seed_day(env, lock_screen_name_mode="hidden")
    body = env.client.get("/api/widget/summary").json()
    assert body["privacyMode"] == "hidden"
    assert body["items"] and all(i["customerDisplay"] is None for i in body["items"])
    assert "Mehmet" not in json.dumps(body, ensure_ascii=False)


def test_widget_writes_nothing(env):
    seed_day(env)
    env.db.live_activity_devices.docs.append(device_doc("d1", "ali"))
    env.db.log.clear()
    assert env.client.get("/api/widget/summary").status_code == 200
    assert writes(env.db) == []
    assert env.resyncs == [] and env.transport.sent == []


def test_configured_dependencies_are_used(monkeypatch):
    """Without overrides, the router runs server.get_current_user(request, token, db) and get_db(request)."""
    db = FakeDB()
    db.settings.docs.append({"organization_id": ORG})
    calls = []

    async def get_db(request):
        return db

    async def get_current_user(request, token, db_):
        calls.append((token, db_))
        if token != "good":
            raise endpoints._unauthorized()
        return jwt_user("ali")

    endpoints.configure(get_current_user, get_db, transport=RecordingTransport())
    monkeypatch.setattr(endpoints, "_now", lambda: NOW)
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api")
    client = TestClient(app)
    assert client.get("/api/widget/summary").status_code == 401
    assert client.get("/api/widget/summary", headers={"Authorization": "Bearer bad"}).status_code == 401
    resp = client.get("/api/widget/summary", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 200 and resp.json()["scope"] == "all"
    assert calls == [("bad", db), ("good", db)]
    body = {"device_id": "d1", "activities_enabled": True, "complete": False, "slots": []}
    assert client.post("/api/live-activities/reconcile", json=body).status_code == 401
    resp = client.post("/api/live-activities/reconcile", json=body, headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401
