"""Appointment and public write paths resolve the customer by phone key (Faz 7, Task 4).

Decision 1: when a write path matches an existing customer, the appointment is stored with
that customer's stored ``phone`` string. Public booking never fails because of a customer write.
"""
from __future__ import annotations

import json
import logging

import pytest

from tests.live_activity_fakes import FakeDB

STORED = "905551112233"  # how the salon saved Ayşe
TYPED = "0555 111 22 33"  # how the same number arrives from a form
FUTURE = "2099-03-10"


@pytest.fixture
def integration_db(org_id):
    """Overrides the conftest mock with the shared async Mongo fake (operators, upsert, indexes)."""
    db = FakeDB()
    db.services._doc = {}  # conftest writes the org id here

    async def insert_many(docs, ordered=True, session=None):  # bulk-session path
        for d in docs:
            await db.appointments.insert_one(d)

    db.appointments.insert_many = insert_many
    db.services.docs.append({"id": "svc1", "organization_id": org_id, "name": "Saç", "duration": 30, "price": 100})
    db.settings.docs.append({"organization_id": org_id, "base_currency": "TRY", "company_name": "Salon"})
    db.customers.docs.append({"id": "c1", "organization_id": org_id, "name": "Ayşe Yılmaz", "phone": STORED,
                              "phone_key": STORED, "total_appointments": 2, "completed_appointments": 1})
    return db


@pytest.fixture(autouse=True)
def _quiet_side_effects(monkeypatch):
    import server

    async def noop(*a, **k):
        return None

    async def turnstile_ok(*a, **k):
        return True

    monkeypatch.setattr(server, "_send_appointment_confirmations", noop)
    monkeypatch.setattr(server, "invalidate_availability_cache", noop)
    monkeypatch.setattr(server, "verify_turnstile", turnstile_ok)
    monkeypatch.setattr(server, "get_geo_country", noop)
    monkeypatch.setattr(server, "send_push_notification", noop)
    monkeypatch.setattr(server, "emit_to_organization", noop)
    monkeypatch.setattr(server, "send_whatsapp_template", lambda *a, **k: "wamid.test")


def _customers(db, org_id):
    return [d for d in db.customers.docs if d["organization_id"] == org_id]


def _c1(db):
    return next(d for d in db.customers.docs if d["id"] == "c1")


# ── Admin create paths ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_appointment_with_variant_phone_stored_as_customer_phone(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post("/api/appointments", json={
        "customer_name": "Ayşe", "phone": TYPED, "service_id": "svc1", "staff_member_id": "admin_integration",
        "appointment_date": FUTURE, "appointment_time": "10:00", "skip_confirmation_whatsapp": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone"] == STORED
    assert db.appointments.docs[0]["phone"] == STORED
    assert len(_customers(db, org_id)) == 1  # no duplicate for the variant
    assert _c1(db)["total_appointments"] == 3
    assert _c1(db)["name"] == "Ayşe Yılmaz"  # R8: a shorter matching name never shortens it


@pytest.mark.asyncio
async def test_walk_in_zero_keeps_one_record_per_name(integration_client, org_id):
    """Unkeyed walk-ins ("0") keep today's behaviour: a different name gets its own record."""
    client, _r, db = integration_client
    db.customers.docs.append({"id": "w1", "organization_id": org_id, "name": "Mehmet", "phone": "0",
                              "total_appointments": 1, "completed_appointments": 0})
    resp = await client.post("/api/appointments", json={
        "customer_name": "Hasan", "phone": "0", "service_id": "svc1", "staff_member_id": "admin_integration",
        "appointment_date": FUTURE, "appointment_time": "12:00",
    })
    assert resp.status_code == 200, resp.text
    walk_ins = [d for d in _customers(db, org_id) if d["phone"] == "0"]
    assert sorted(d["name"] for d in walk_ins) == ["Hasan", "Mehmet"]
    assert all("phone_key" not in d and "shared_phone" not in d for d in walk_ins)
    assert next(d for d in walk_ins if d["id"] == "w1")["total_appointments"] == 1


@pytest.mark.asyncio
async def test_appointment_new_number_creates_keyed_customer(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post("/api/appointments", json={
        "customer_name": "Zeynep Kaya", "phone": "0544 222 33 44", "service_id": "svc1",
        "staff_member_id": "admin_integration", "appointment_date": FUTURE, "appointment_time": "11:00",
    })
    assert resp.status_code == 200, resp.text
    new = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert len(new) == 1
    assert new[0]["phone"] == "0544 222 33 44"
    assert new[0]["phone_key"] == "905442223344"
    assert new[0]["total_appointments"] == 1
    assert db.appointments.docs[0]["phone"] == "0544 222 33 44"


@pytest.mark.asyncio
async def test_bulk_session_variant_phone_stored_as_customer_phone(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post("/api/appointments/bulk-session", json={
        "customer_name": "Ayşe Yılmaz", "phone": "05551112233", "service_id": "svc1",
        "staff_member_id": None, "notes": "", "session_group_id": "grp1",
        "starting_session_number": 1, "session_total": 2,
        "sessions": [{"date": FUTURE, "time": "10:00"}, {"date": "2099-03-17", "time": "10:00"}],
    })
    assert resp.status_code == 201, resp.text
    assert {a["phone"] for a in db.appointments.docs} == {STORED}
    assert len(_customers(db, org_id)) == 1
    assert _c1(db)["total_appointments"] == 4


@pytest.mark.asyncio
async def test_appointment_other_name_on_known_number_creates_shared_suggestion(integration_client, org_id):
    """R15: an admin appointment for Ayşe's number under another name never lands on Ayşe."""
    client, _r, db = integration_client
    resp = await client.post("/api/appointments", json={
        "customer_name": "Kadir Burak", "phone": TYPED, "service_id": "svc1",
        "staff_member_id": "admin_integration", "appointment_date": FUTURE, "appointment_time": "13:00",
    })
    assert resp.status_code == 200, resp.text
    (new,) = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert new["name"] == "Kadir Burak" and new["shared_phone"] is True
    assert new["merge_suggestion_for"] == "c1" and "phone_key" not in new
    assert new["total_appointments"] == 1
    assert _c1(db)["total_appointments"] == 2 and _c1(db)["name"] == "Ayşe Yılmaz"
    assert db.appointments.docs[0]["phone"] == TYPED


@pytest.mark.asyncio
async def test_bulk_session_other_name_on_known_number_creates_shared_suggestion(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post("/api/appointments/bulk-session", json={
        "customer_name": "Kadir Burak", "phone": "05551112233", "service_id": "svc1",
        "staff_member_id": None, "notes": "", "session_group_id": "grp2",
        "starting_session_number": 1, "session_total": 2,
        "sessions": [{"date": FUTURE, "time": "14:00"}, {"date": "2099-03-17", "time": "14:00"}],
    })
    assert resp.status_code == 201, resp.text
    (new,) = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert new["shared_phone"] is True and new["merge_suggestion_for"] == "c1"
    assert new["total_appointments"] == 2
    assert _c1(db)["total_appointments"] == 2
    assert {a["phone"] for a in db.appointments.docs} == {"05551112233"}


@pytest.mark.asyncio
async def test_register_owner_seed_is_keyed(org_id):
    import server

    db = FakeDB()
    await server._seed_owner_customer(db, "org_new", "0532 000 11 22", "Salon Sahibi", "user-1")
    [doc] = db.customers.docs
    assert doc["phone"] == "0532 000 11 22"
    assert doc["phone_key"] == "905320001122"
    assert doc["is_owner_profile"] is True
    assert doc["owner_user_id"] == "user-1"
    assert doc["source"] == "owner_self_seed"
    assert doc["name"] == "Salon Sahibi"


# ── Public booking ────────────────────────────────────────────────────────


def _public_body(name, phone=TYPED):
    return {"customer_name": name, "phone": phone, "service_id": "svc1", "staff_member_id": "staff1",
            "appointment_date": FUTURE, "appointment_time": "14:00"}


@pytest.mark.asyncio
async def test_public_booking_typo_name_succeeds_and_flags_suggestion(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post(f"/api/public/appointments?organization_id={org_id}",
                             json=_public_body("Ayse Yilmazz"))
    assert resp.status_code == 200, resp.text
    shared = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert len(shared) == 1
    assert shared[0]["shared_phone"] is True
    assert shared[0]["merge_suggestion_for"] == "c1"
    assert "phone_key" not in shared[0]
    assert shared[0]["total_appointments"] == 1  # counters follow the new record, not Ayşe's
    assert _c1(db)["total_appointments"] == 2
    assert _c1(db)["name"] == "Ayşe Yılmaz"
    assert db.appointments.docs[0]["phone"] == TYPED  # the shared record's own phone


@pytest.mark.asyncio
async def test_public_booking_matching_name_reuses_customer_phone(integration_client, org_id):
    client, _r, db = integration_client
    resp = await client.post(f"/api/public/appointments?organization_id={org_id}",
                             json=_public_body("ayşe  yılmaz"))
    assert resp.status_code == 200, resp.text
    assert len(_customers(db, org_id)) == 1
    assert db.appointments.docs[0]["phone"] == STORED
    assert _c1(db)["total_appointments"] == 3


def _boom(monkeypatch):
    import server

    async def broken(*a, **k):
        raise RuntimeError("customers write exploded")

    monkeypatch.setattr(server, "resolve_customer", broken)


@pytest.mark.asyncio
async def test_public_booking_never_raises_on_customer_write_error(integration_client, org_id, monkeypatch, caplog):
    client, _r, db = integration_client
    _boom(monkeypatch)
    with caplog.at_level(logging.ERROR):
        resp = await client.post(f"/api/public/appointments?organization_id={org_id}",
                                 json=_public_body("Ayşe Yılmaz"))
    assert resp.status_code == 200, resp.text
    assert db.appointments.docs[0]["phone"] == TYPED  # falls back to the typed phone
    assert "customers write exploded" in caplog.text


class _HashRedis:
    """Enough of redis.asyncio for the code-verification flows."""

    def __init__(self, pending: dict):
        self.h = {"plann:pending:ABC123": pending}
        self.kv = {}

    async def hgetall(self, key):
        return dict(self.h.get(key, {}))

    async def delete(self, *keys):
        for k in keys:
            self.h.pop(k, None)
            self.kv.pop(k, None)

    async def setex(self, key, ttl, value):
        self.kv[key] = value


def _pending(org_id, name, phone=TYPED):
    return {
        "phone": phone, "org_id": org_id,
        "appointment_data": json.dumps({
            "customer_name": name, "phone": phone, "service_id": "svc1", "service_ids": ["svc1"],
            "appointment_date": FUTURE, "appointment_time": "15:00", "notes": "", "staff_member_id": None,
        }),
    }


@pytest.fixture
def code_client(integration_client, org_id):
    from server import app

    client, _r, db = integration_client

    def use(name):
        app.state.redis_client = _HashRedis(_pending(org_id, name))
        return client, db

    return use


@pytest.mark.asyncio
async def test_verify_code_matching_name_uses_customer_phone(code_client, org_id):
    client, db = code_client("Ayşe")
    resp = await client.post("/api/public/verify-code", json={"code": "ABC123", "phone": TYPED})
    assert resp.status_code == 200, resp.text
    assert len(_customers(db, org_id)) == 1
    assert _c1(db)["total_appointments"] == 3
    assert _c1(db)["name"] == "Ayşe Yılmaz"  # R8
    assert db.appointments.docs[0]["phone"] == STORED


@pytest.mark.asyncio
async def test_verify_code_typo_name_flags_suggestion(code_client, org_id):
    client, db = code_client("Ayse Yilmazz")
    resp = await client.post("/api/public/verify-code", json={"code": "ABC123", "phone": TYPED})
    assert resp.status_code == 200, resp.text
    shared = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert len(shared) == 1 and shared[0]["merge_suggestion_for"] == "c1"
    assert _c1(db)["name"] == "Ayşe Yılmaz"


@pytest.mark.asyncio
async def test_verify_code_never_raises_on_customer_write_error(code_client, org_id, monkeypatch, caplog):
    client, db = code_client("Ayşe Yılmaz")
    _boom(monkeypatch)
    with caplog.at_level(logging.ERROR):
        resp = await client.post("/api/public/verify-code", json={"code": "ABC123", "phone": TYPED})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "verified"
    assert db.appointments.docs[0]["phone"] == TYPED
    assert "customers write exploded" in caplog.text


@pytest.mark.asyncio
async def test_whatsapp_verification_uses_customer_phone(integration_db, org_id, monkeypatch):
    import server

    monkeypatch.setattr(server, "check_quota_and_increment", _quota_ok)
    redis = _HashRedis(_pending(org_id, "Ayşe Yılmaz"))
    out = await server._process_whatsapp_verification(integration_db, redis, STORED, "ABC123")
    assert out == {"reply": ""}
    db = integration_db
    assert len(_customers(db, org_id)) == 1
    assert _c1(db)["name"] == "Ayşe Yılmaz"
    assert db.appointments.docs[0]["phone"] == STORED


@pytest.mark.asyncio
async def test_whatsapp_verification_never_raises_on_customer_write_error(integration_db, org_id, monkeypatch, caplog):
    import server

    monkeypatch.setattr(server, "check_quota_and_increment", _quota_ok)
    _boom(monkeypatch)
    redis = _HashRedis(_pending(org_id, "Ayşe Yılmaz"))
    with caplog.at_level(logging.ERROR):
        out = await server._process_whatsapp_verification(integration_db, redis, STORED, "ABC123")
    assert out == {"reply": ""}
    assert integration_db.appointments.docs[0]["phone"] == TYPED
    assert "customers write exploded" in caplog.text


async def _quota_ok(*a, **k):
    return True, ""


# ── Update path (Review Focus 5) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_appointment_phone_change_moves_counters(integration_client, org_id):
    client, _r, db = integration_client
    db.customers.docs.append({"id": "c2", "organization_id": org_id, "name": "Ayşe Yılmaz",
                              "phone": "905449998877", "phone_key": "905449998877",
                              "total_appointments": 0, "completed_appointments": 0})
    db.appointments.docs.append({
        "id": "apt1", "organization_id": org_id, "customer_name": "Ayşe Yılmaz", "phone": STORED,
        "service_id": "svc1", "service_name": "Saç", "service_price": 100, "appointment_date": FUTURE,
        "appointment_time": "09:00", "status": "Bekliyor", "staff_member_id": "admin_integration",
        "created_at": "2026-11-18T08:00:00+00:00",
    })
    resp = await client.put("/api/appointments/apt1", json={"phone": "0544 999 88 77"})
    assert resp.status_code == 200, resp.text
    c2 = next(d for d in db.customers.docs if d["id"] == "c2")
    assert _c1(db)["total_appointments"] == 1
    assert c2["total_appointments"] == 1
    assert db.appointments.docs[0]["phone"] == "905449998877"
    assert len(_customers(db, org_id)) == 2


# ── AI tool ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_tool_customer_uses_resolver(integration_db, org_id):
    import ai_service

    db = integration_db
    dup = await ai_service.add_customer_tool(db, org_id, "Ayşe", "0555 111 22 33")
    assert dup["success"] is False
    assert len(_customers(db, org_id)) == 1

    ok = await ai_service.add_customer_tool(db, org_id, "Zeynep", "0544 222 33 44")
    assert ok["success"] is True
    [new] = [d for d in _customers(db, org_id) if d["id"] != "c1"]
    assert new["phone_key"] == "905442223344"
    assert new["phone"] == "0544 222 33 44"


# ── R7: stored phone only when it reaches the same WhatsApp recipient ─────

UK_STORED = "07700900123"  # local UK form: format_phone_number gives an invalid recipient
UK_TYPED = "+447700900123"


def _uk(db, org_id):
    db.settings.docs[0]["base_currency"] = "GBP"
    db.customers.docs.append({"id": "u1", "organization_id": org_id, "name": "John Smith", "phone": UK_STORED,
                              "phone_key": "447700900123", "total_appointments": 0, "completed_appointments": 0})
    return lambda: next(d for d in db.customers.docs if d["id"] == "u1")


@pytest.mark.asyncio
async def test_uk_local_stored_customer_keeps_typed_international_phone(integration_client, org_id):
    client, _r, db = integration_client
    u1 = _uk(db, org_id)
    resp = await client.post("/api/appointments", json={
        "customer_name": "John Smith", "phone": UK_TYPED, "service_id": "svc1",
        "staff_member_id": "admin_integration", "appointment_date": FUTURE, "appointment_time": "10:00",
    })
    assert resp.status_code == 200, resp.text
    assert db.appointments.docs[0]["phone"] == UK_TYPED
    assert u1()["total_appointments"] == 1  # counters still reach the stored customer by key
    assert len(_customers(db, org_id)) == 2  # c1 + u1, no duplicate


@pytest.mark.asyncio
async def test_bulk_session_uk_keeps_typed_phone_for_session_package(integration_client, org_id):
    client, _r, db = integration_client
    u1 = _uk(db, org_id)
    resp = await client.post("/api/appointments/bulk-session", json={
        "customer_name": "John Smith", "phone": UK_TYPED, "service_id": "svc1", "staff_member_id": None,
        "notes": "", "session_group_id": "grpuk", "starting_session_number": 1, "session_total": 1,
        "sessions": [{"date": FUTURE, "time": "10:00"}],
    })
    assert resp.status_code == 201, resp.text
    assert db.appointments.docs[0]["phone"] == UK_TYPED  # SESSION_PACKAGE reads this phone
    assert u1()["total_appointments"] == 1


@pytest.mark.asyncio
async def test_public_booking_uk_keeps_typed_phone(integration_client, org_id):
    client, _r, db = integration_client
    u1 = _uk(db, org_id)
    resp = await client.post(f"/api/public/appointments?organization_id={org_id}",
                             json=_public_body("John Smith", UK_TYPED))
    assert resp.status_code == 200, resp.text
    assert db.appointments.docs[0]["phone"] == UK_TYPED
    assert u1()["total_appointments"] == 1
    assert len(_customers(db, org_id)) == 2


def _apt(org_id, phone, **kw):
    doc = {"id": "apt1", "organization_id": org_id, "customer_name": "Ayşe Yılmaz", "phone": phone,
           "service_id": "svc1", "service_name": "Saç", "service_price": 100, "appointment_date": FUTURE,
           "appointment_time": "09:00", "status": "Bekliyor", "staff_member_id": "admin_integration",
           "created_at": "2026-11-18T08:00:00+00:00"}
    doc.update(kw)
    return doc


@pytest.mark.asyncio
async def test_phone_change_uk_keeps_typed_phone(integration_client, org_id):
    client, _r, db = integration_client
    u1 = _uk(db, org_id)
    db.appointments.docs.append(_apt(org_id, STORED, customer_name="John Smith"))
    resp = await client.put("/api/appointments/apt1", json={"phone": UK_TYPED})
    assert resp.status_code == 200, resp.text
    assert db.appointments.docs[0]["phone"] == UK_TYPED
    assert u1()["total_appointments"] == 1


# ── R9: decrements never create phantom records ───────────────────────────


@pytest.mark.asyncio
async def test_phone_change_from_unknown_phone_creates_no_phantom(integration_client, org_id):
    client, _r, db = integration_client
    db.appointments.docs.append(_apt(org_id, "05329998877"))  # nobody saved under this number
    resp = await client.put("/api/appointments/apt1", json={"phone": TYPED})
    assert resp.status_code == 200, resp.text
    assert [d["id"] for d in _customers(db, org_id)] == ["c1"]
    assert _c1(db)["total_appointments"] == 3


# ── R10: AI tool appointment follows decision 1 / R7 ──────────────────────


@pytest.fixture
def ai_db(integration_db, org_id, monkeypatch):
    import server

    import ai_service

    monkeypatch.setattr(server, "send_sms", lambda *a, **k: None)
    monkeypatch.setattr(ai_service, "sio", None)  # no socket.io publish in tests
    integration_db.users.docs.append({"username": "staff1", "organization_id": org_id, "full_name": "Staff"})
    return integration_db


@pytest.mark.asyncio
async def test_ai_appointment_uses_customer_phone(ai_db, org_id):
    import ai_service

    out = await ai_service.create_appointment_tool(ai_db, org_id, "Ayşe", "05551112233", service_id="svc1",
                                                   apt_date=FUTURE, apt_time="10:00", staff_id="staff1")
    assert out["success"] is True, out
    assert ai_db.appointments.docs[0]["phone"] == STORED


@pytest.mark.asyncio
async def test_ai_appointment_uk_keeps_typed_phone(ai_db, org_id):
    import ai_service

    _uk(ai_db, org_id)
    out = await ai_service.create_appointment_tool(ai_db, org_id, "John Smith", UK_TYPED, service_id="svc1",
                                                   apt_date=FUTURE, apt_time="10:00", staff_id="staff1")
    assert out["success"] is True, out
    assert ai_db.appointments.docs[0]["phone"] == UK_TYPED
