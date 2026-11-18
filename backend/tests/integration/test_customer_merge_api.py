"""Faz 8 suggestion + merge API: POST /customers/merge, POST /customers/{id}/not-duplicate."""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.live_activity_fakes import FakeCollection, FakeDB, _Cursor, _project, _match

OTHER_ORG = "org_someone_else"
DIFF_DETAIL = "Bu iki müşteri farklı numaralara sahip; birleştirilemez."


class _PagedCursor(_Cursor):
    def collation(self, _c):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self


class PagedCollection(FakeCollection):
    # ids whose next phone_key $set loses a race to a concurrent insert
    dup_key_set_for: set = set()

    async def update_one(self, flt, update, upsert=False):
        if flt.get("id") in self.dup_key_set_for and "phone_key" in update.get("$set", {}):
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("E11000 phone_key")
        return await super().update_one(flt, update, upsert)

    def find(self, flt=None, projection=None):
        return _PagedCursor([_project(d, projection) for d in self.docs if _match(d, flt or {})])


def _cust(org, cid, name, phone, **extra):
    return {"_id": f"oid-{cid}", "id": cid, "organization_id": org, "name": name, "phone": phone,
            "total_appointments": 0, "completed_appointments": 0, "notes": "", **extra}


@pytest_asyncio.fixture
async def world(integration_client, integration_db, org_id, monkeypatch):
    import server
    fake = FakeDB()
    fake._collections["customers"] = PagedCollection("customers", fake.log)
    fake._collections["customers"].dup_key_set_for = set()
    for attr in ("customers", "appointments", "settings", "customer_notes",
                 "marketing_autopilot_tasks", "merchant_transactions", "refund_requests",
                 "stripe_customers"):
        setattr(integration_db, attr, getattr(fake, attr))
    emitted = []

    async def fake_emit(org, event, payload):
        emitted.append((org, event, payload))

    monkeypatch.setattr(server, "emit_to_organization", fake_emit)
    client, _r, _d = integration_client
    return client, integration_db, emitted


def _as_staff(test_user):
    from server import app, get_current_user, UserInDB

    async def staff():
        return UserInDB(username="s", organization_id=test_user.organization_id, role="staff",
                        full_name="S", permitted_service_ids=[], can_view_all_appointments=True)
    app.dependency_overrides[get_current_user] = staff


@pytest.mark.asyncio
async def test_merge_endpoint_org_scoped(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", phone_key="905551112233"),
        _cust(OTHER_ORG, "x", "Ayşe", "905551112233", phone_key="905551112233"),
    ]
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "x"})
    assert r.status_code == 404
    r = await client.post("/api/customers/merge", json={"survivor_id": "x", "source_id": "a"})
    assert r.status_code == 404
    assert {d["id"] for d in db.customers.docs} == {"a", "x"}


@pytest.mark.asyncio
async def test_merge_endpoint_staff_403(world, test_user, org_id):
    client, db, _e = world
    db.customers.docs += [_cust(org_id, "a", "A", "905551112233"), _cust(org_id, "b", "A", "05551112233")]
    _as_staff(test_user)
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 403
    r = await client.post("/api/customers/a/not-duplicate")
    assert r.status_code == 403
    assert len(db.customers.docs) == 2


@pytest.mark.asyncio
async def test_not_duplicate_clears_suggestion(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", phone_key="905551112233"),
        _cust(org_id, "b", "Ayse Y", "905551112233", shared_phone=True, merge_suggestion_for="a"),
        _cust(OTHER_ORG, "z", "Z", "905551112233", merge_suggestion_for="a"),
    ]
    r = await client.post("/api/customers/b/not-duplicate")
    assert r.status_code == 200 and r.json() == {"ok": True}
    b = next(d for d in db.customers.docs if d["id"] == "b")
    assert "merge_suggestion_for" not in b and b["shared_phone"] is True
    assert (await client.post("/api/customers/z/not-duplicate")).status_code == 404
    z = next(d for d in db.customers.docs if d["id"] == "z")
    assert z["merge_suggestion_for"] == "a"


@pytest.mark.asyncio
async def test_list_includes_suggestion_fields_additively(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", phone_key="905551112233"),
        _cust(org_id, "b", "Ayse Y", "905551112233", shared_phone=True, merge_suggestion_for="a"),
    ]
    r = await client.get("/api/customers?limit=30")
    assert r.status_code == 200
    items = {i["id"]: i for i in r.json()["items"]}
    legacy_keys = {"id", "name", "phone", "notes", "total_appointments", "completed_appointments",
                   "last_appointment_at", "first_appointment_at", "is_pending"}
    assert set(items["a"]) == legacy_keys
    assert set(items["b"]) == legacy_keys | {"shared_phone", "merge_suggestion_for"}
    assert items["b"]["shared_phone"] is True and items["b"]["merge_suggestion_for"] == "a"


@pytest.mark.asyncio
async def test_merge_repoints_deletes_source_and_emits(world, org_id):
    client, db, emitted = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", phone_key="905551112233"),
        _cust(org_id, "b", "Ayse", "05551112233", shared_phone=True, merge_suggestion_for="a"),
    ]
    db.appointments.docs.append({"_id": "ap1", "organization_id": org_id, "phone": "05551112233",
                                 "customer_name": "Ayse", "status": "Tamamlandı"})
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 200 and r.json() == {"merged": True, "survivor_id": "a"}
    assert [d["id"] for d in db.customers.docs] == ["a"]
    assert db.appointments.docs[0]["phone"] == "905551112233"
    assert db.customers.docs[0]["total_appointments"] == 1
    events = {e for _o, e, _p in emitted}
    assert {"customer_updated", "customer_deleted", "appointments_bulk_updated"} <= events


@pytest.mark.asyncio
async def test_merge_carries_source_key_to_unkeyed_survivor(world, org_id):
    """Source holds the key, survivor is the shared-number record: key must move over."""
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "s", "Ayse", "05551112233", shared_phone=True, merge_suggestion_for="k"),
        _cust(org_id, "k", "Ayşe", "905551112233", phone_key="905551112233"),
    ]
    r = await client.post("/api/customers/merge", json={"survivor_id": "s", "source_id": "k"})
    assert r.status_code == 200
    assert len(db.customers.docs) == 1
    s = db.customers.docs[0]
    assert s["id"] == "s" and s["phone_key"] == "905551112233"
    assert "shared_phone" not in s and "merge_suggestion_for" not in s


@pytest.mark.asyncio
async def test_merge_refuses_two_different_keys(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "A", "905551112233", phone_key="905551112233"),
        _cust(org_id, "b", "B", "905441112233", phone_key="905441112233"),
    ]
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 400 and r.json()["detail"] == DIFF_DETAIL
    assert len(db.customers.docs) == 2


@pytest.mark.asyncio
async def test_merge_refuses_different_unkeyed_numbers_and_self(world, org_id):
    client, db, _e = world
    db.customers.docs += [_cust(org_id, "a", "A", "905551112233"), _cust(org_id, "b", "B", "905441112233")]
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 400 and r.json()["detail"] == DIFF_DETAIL
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "a"})
    assert r.status_code == 400
    assert len(db.customers.docs) == 2


RACE_DETAIL = "Bu numara az önce başka bir kayıtta kullanıldı. Lütfen listeyi yenileyip tekrar deneyin."


def _carry_pair(org_id):
    return [
        _cust(org_id, "s", "Ayse", "05551112233", shared_phone=True),
        _cust(org_id, "k", "Ayşe", "905551112233", phone_key="905551112233"),
    ]


@pytest.mark.asyncio
async def test_carry_race_on_survivor_set_is_409_and_key_goes_back(world, org_id):
    client, db, _e = world
    db.customers.docs += _carry_pair(org_id)
    db.customers.dup_key_set_for = {"s"}
    r = await client.post("/api/customers/merge", json={"survivor_id": "s", "source_id": "k"})
    assert r.status_code == 409 and r.json()["detail"] == RACE_DETAIL
    by_id = {d["id"]: d for d in db.customers.docs}
    assert set(by_id) == {"s", "k"}
    assert by_id["k"]["phone_key"] == "905551112233" and "phone_key" not in by_id["s"]


@pytest.mark.asyncio
async def test_carry_race_when_key_cannot_go_back_stays_409_unkeyed(world, org_id):
    client, db, _e = world
    db.customers.docs += _carry_pair(org_id)
    db.customers.dup_key_set_for = {"s", "k"}
    r = await client.post("/api/customers/merge", json={"survivor_id": "s", "source_id": "k"})
    assert r.status_code == 409 and r.json()["detail"] == RACE_DETAIL
    assert all("phone_key" not in d for d in db.customers.docs)


@pytest.mark.asyncio
async def test_rollback_after_merge_refusal_survives_duplicate_key(world, org_id, monkeypatch):
    import server
    client, db, _e = world
    db.customers.docs += _carry_pair(org_id)

    async def refuse(*a, **k):
        db.customers.dup_key_set_for = {"k"}  # the rollback $set onto the source loses a race
        raise ValueError("no shared key")

    monkeypatch.setattr(server, "merge_into", refuse)
    r = await client.post("/api/customers/merge", json={"survivor_id": "s", "source_id": "k"})
    assert r.status_code == 400 and r.json()["detail"] == DIFF_DETAIL


@pytest.mark.asyncio
async def test_404_after_carry_leaves_key_on_survivor(world, org_id, monkeypatch):
    import server
    client, db, _e = world
    db.customers.docs += _carry_pair(org_id)

    async def vanished(*a, **k):
        return {"merged": False, "reason": "source_missing"}

    monkeypatch.setattr(server, "merge_into", vanished)
    r = await client.post("/api/customers/merge", json={"survivor_id": "s", "source_id": "k"})
    assert r.status_code == 404
    by_id = {d["id"]: d for d in db.customers.docs}
    assert by_id["s"]["phone_key"] == "905551112233"


@pytest.mark.asyncio
async def test_merge_repoints_third_record_suggestions(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", phone_key="905551112233"),
        _cust(org_id, "b", "Ayse", "905551112233", shared_phone=True, merge_suggestion_for="a"),
        _cust(org_id, "c", "Ayshe", "905551112233", shared_phone=True, merge_suggestion_for="b"),
    ]
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 200
    by_id = {d["id"]: d for d in db.customers.docs}
    assert by_id["c"]["merge_suggestion_for"] == "a"
    assert "merge_suggestion_for" not in by_id["a"]


@pytest.mark.asyncio
async def test_merge_unkeyed_survivor_drops_third_record_suggestions(world, org_id):
    client, db, _e = world
    db.customers.docs += [
        _cust(org_id, "a", "Ayşe", "905551112233", shared_phone=True),
        _cust(org_id, "b", "Ayse", "905551112233", shared_phone=True),
        _cust(org_id, "c", "Ayshe", "905551112233", shared_phone=True, merge_suggestion_for="b"),
    ]
    r = await client.post("/api/customers/merge", json={"survivor_id": "a", "source_id": "b"})
    assert r.status_code == 200
    assert "merge_suggestion_for" not in next(d for d in db.customers.docs if d["id"] == "c")
