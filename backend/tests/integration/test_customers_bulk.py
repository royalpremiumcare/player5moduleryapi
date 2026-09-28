"""POST /api/customers/bulk — rehberden toplu müşteri ekleme.

Tekrar kuralı POST /customers ile aynı olmalı: numaranın 905… / 5… / 05… yazımlarından
herhangi biri organizasyonun randevularında ya da müşterilerinde varsa eklenmez.
"""
from __future__ import annotations

from typing import List

import pytest

import server
from server import UserInDB, get_current_user, app


class _PhoneColl:
    def __init__(self, docs: List[dict] | None = None):
        self.docs: List[dict] = list(docs or [])
        self.distinct_queries: List[dict] = []

    async def distinct(self, field: str, query: dict):
        self.distinct_queries.append(query)
        wanted = set(query["phone"]["$in"])
        return sorted({
            d[field] for d in self.docs
            if d.get("organization_id") == query["organization_id"] and d.get(field) in wanted
        })

    async def insert_many(self, docs: List[dict], ordered: bool = True):
        self.docs.extend(dict(d) for d in docs)


@pytest.fixture
def bulk_db(integration_db, org_id):
    integration_db.appointments = _PhoneColl([
        {"organization_id": org_id, "phone": "05321112233"},
        {"organization_id": "other_org", "phone": "905559998877"},
    ])
    integration_db.customers = _PhoneColl([
        {"organization_id": org_id, "phone": "5334445566"},
    ])
    integration_db.audit_logs = _PhoneColl()
    return integration_db


def _created(coll: _PhoneColl, org_id: str):
    return [d for d in coll.docs if d.get("organization_id") == org_id and "id" in d]


@pytest.mark.asyncio
async def test_creates_new_and_skips_existing_variants(integration_client, bulk_db, org_id):
    client, _redis, _db = integration_client

    resp = await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "Yeni Kişi", "phone": "+90 544 111 22 33"},  # istemci 90… biçimine çevirip gönderir
        {"name": "Randevulu", "phone": "905321112233"},     # randevuda 0532… olarak var
        {"name": "Müşteri", "phone": "905334445566"},       # müşterilerde 533… olarak var
        {"name": "Başka Org", "phone": "905559998877"},     # yalnız başka org'da var → eklenir
    ]})

    assert resp.status_code == 200
    assert resp.json() == {"created": 2, "duplicates": 2, "invalid": 0}
    phones = sorted(d["phone"] for d in _created(bulk_db.customers, org_id))
    assert phones == ["905441112233", "905559998877"]


@pytest.mark.asyncio
async def test_dedupes_within_batch_and_counts_invalid(integration_client, bulk_db, org_id):
    client, _redis, _db = integration_client

    resp = await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "Ali", "phone": "905441112233"},
        {"name": "Ali İş", "phone": "5441112233"},          # aynı numara, farklı yazım
        {"name": "", "phone": "905440000000"},              # isimsiz
        {"name": "Kısa", "phone": "12345"},                 # geçersiz numara
        {"name": "Boş"},                                    # numara yok
    ]})

    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "duplicates": 1, "invalid": 3}
    assert len(_created(bulk_db.customers, org_id)) == 1


@pytest.mark.asyncio
async def test_queries_are_scoped_to_organization(integration_client, bulk_db, org_id):
    client, _redis, _db = integration_client

    await client.post("/api/customers/bulk", json={"contacts": [{"name": "A", "phone": "905441112233"}]})

    for coll in (bulk_db.appointments, bulk_db.customers):
        assert coll.distinct_queries
        assert all(q["organization_id"] == org_id for q in coll.distinct_queries)
    for doc in _created(bulk_db.customers, org_id):
        assert doc["organization_id"] == org_id


@pytest.mark.asyncio
async def test_writes_one_audit_entry_per_customer(integration_client, bulk_db, org_id, monkeypatch):
    client, _redis, _db = integration_client
    monkeypatch.setattr(server, "AUDIT_LOGS_ENABLED", True)

    await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "A", "phone": "905441112233"},
        {"name": "B", "phone": "905441112244"},
    ]})

    created_ids = {d["id"] for d in _created(bulk_db.customers, org_id)}
    audit_ids = {d["resource_id"] for d in bulk_db.audit_logs.docs}
    assert audit_ids == created_ids
    assert all(d["action"] == "CREATE" and d["resource_type"] == "CUSTOMER" for d in bulk_db.audit_logs.docs)


@pytest.mark.asyncio
async def test_emits_single_socket_event(integration_client, bulk_db, monkeypatch):
    client, _redis, _db = integration_client
    events = []

    async def capture(org, event, data):
        events.append((event, data))

    monkeypatch.setattr(server, "emit_to_organization", capture)

    await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "A", "phone": "905441112233"},
        {"name": "B", "phone": "905441112244"},
        {"name": "C", "phone": "905441112255"},
    ]})

    assert events == [("customer_added", {"bulk": True, "count": 3})]


@pytest.mark.asyncio
async def test_rejects_non_admin(integration_client, bulk_db, org_id):
    client, _redis, _db = integration_client

    async def staff_user():
        return UserInDB(username="staff1", organization_id=org_id, role="staff")

    app.dependency_overrides[get_current_user] = staff_user
    resp = await client.post("/api/customers/bulk", json={"contacts": [{"name": "A", "phone": "905441112233"}]})

    assert resp.status_code == 403
    assert _created(bulk_db.customers, org_id) == []


@pytest.mark.asyncio
async def test_rejects_oversized_batch(integration_client, bulk_db):
    client, _redis, _db = integration_client
    contacts = [{"name": f"K{i}", "phone": f"9054400{i:05d}"} for i in range(server.CUSTOMER_BULK_MAX + 1)]

    resp = await client.post("/api/customers/bulk", json={"contacts": contacts})

    assert resp.status_code == 422


def test_phone_variants_match_single_create_rules():
    assert server._customer_phone_variants("905362231743") == ["905362231743", "5362231743", "05362231743"]
    assert server._customer_phone_variants("5362231743") == ["5362231743", "905362231743", "05362231743"]
    assert server._customer_phone_variants("447911123456") == ["447911123456"]
