"""Admin customer endpoints decide duplicates by the canonical phone key (Faz 7)."""
from __future__ import annotations

import pytest

DUP_DETAIL = "Bu telefon numarasına sahip bir müşteri zaten var"


def _match(doc: dict, query: dict) -> bool:
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, sub) for sub in v):
                return False
        elif isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif isinstance(v, dict) and "$ne" in v:
            if doc.get(k) == v["$ne"]:
                return False
        elif isinstance(v, dict) and "$exists" in v:
            if (k in doc) != v["$exists"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, items):
        self._items = items

    async def to_list(self, length=None):
        return list(self._items)


class KeyedCustomers:
    """Minimal customers collection: equality, $or, $in, $ne, $exists, $set/$unset."""

    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]

    def find(self, query, projection=None, *a, **k):
        return _Cursor([{x: y for x, y in d.items() if x != "_id"}
                        for d in self.docs if _match(d, query)])

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if _match(d, query):
                return {x: y for x, y in d.items() if x != "_id"}
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def insert_many(self, docs, ordered=True):
        self.docs.extend(dict(d) for d in docs)

    async def distinct(self, field, query):
        return sorted({d[field] for d in self.docs if field in d and _match(d, query)})

    async def update_one(self, query, update):
        for d in self.docs:
            if _match(d, query):
                d.update(update.get("$set", {}))
                for f in update.get("$unset", {}):
                    d.pop(f, None)
                break


class _Audit:
    async def insert_many(self, docs, ordered=True):
        pass

    async def insert_one(self, doc):
        pass


async def _no_distinct(field, query):
    return []


@pytest.fixture
def cust(integration_db, org_id):
    integration_db.customers = KeyedCustomers([
        {"id": "c1", "organization_id": org_id, "name": "Ayşe Yılmaz", "phone": "905551112233",
         "phone_key": "905551112233"},
    ])
    integration_db.audit_logs = _Audit()
    integration_db.appointments.distinct = _no_distinct
    return integration_db.customers


@pytest.mark.asyncio
async def test_create_with_zero_prefixed_duplicate_is_400(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.post("/api/customers", json={"name": "Ayşe", "phone": "05551112233"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == DUP_DETAIL


@pytest.mark.asyncio
async def test_create_sets_phone_key(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.post("/api/customers", json={"name": "Yeni", "phone": "0544 111 22 33"})
    assert resp.status_code == 200
    doc = next(d for d in cust.docs if d["id"] == resp.json()["id"])
    assert doc["phone_key"] == "905441112233"
    assert "allow_shared_phone" not in doc
    assert "shared_phone" not in doc


@pytest.mark.asyncio
async def test_allow_shared_phone_creates_second_record(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.post("/api/customers", json={
        "name": "Fatma", "phone": "05551112233", "allow_shared_phone": True})
    assert resp.status_code == 200
    doc = next(d for d in cust.docs if d["id"] == resp.json()["id"])
    assert doc["shared_phone"] is True
    assert "phone_key" not in doc
    assert "allow_shared_phone" not in doc
    assert len(cust.docs) == 2


@pytest.mark.asyncio
async def test_create_landline_without_zero_matches_stored_zero_form(integration_client, cust, org_id):
    client, _r, _d = integration_client
    cust.docs.append({"id": "c9", "organization_id": org_id, "name": "Hat", "phone": "02121234567"})
    resp = await client.post("/api/customers", json={"name": "Hat", "phone": "2121234567"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == DUP_DETAIL


@pytest.mark.asyncio
async def test_create_unkeyed_number_matches_stored_variant(integration_client, cust, org_id, monkeypatch):
    import server
    monkeypatch.setattr(server, "phone_key", lambda *a, **k: None)
    client, _r, _d = integration_client
    cust.docs.append({"id": "c9", "organization_id": org_id, "name": "Hat", "phone": "02121234567"})
    resp = await client.post("/api/customers", json={"name": "Hat", "phone": "2121234567"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == DUP_DETAIL


@pytest.mark.asyncio
async def test_allow_shared_without_holder_creates_normal_keyed_record(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.post("/api/customers", json={
        "name": "Yeni", "phone": "05441112233", "allow_shared_phone": True})
    assert resp.status_code == 200
    doc = next(d for d in cust.docs if d["id"] == resp.json()["id"])
    assert doc["phone_key"] == "905441112233"
    assert "shared_phone" not in doc


@pytest.mark.asyncio
async def test_bulk_write_error_counts_failed_rows_as_duplicates(integration_client, cust, monkeypatch):
    from pymongo.errors import BulkWriteError
    client, _r, _d = integration_client
    emitted = []

    async def fake_emit(org, ev, payload):
        emitted.append(payload)

    import server
    monkeypatch.setattr(server, "emit_to_organization", fake_emit)

    async def boom(docs, ordered=True):
        cust.docs.append(dict(docs[0]))  # first row landed, second lost a race
        raise BulkWriteError({"nInserted": 1, "writeErrors": [{"index": 1, "code": 11000}]})

    cust.insert_many = boom
    resp = await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "A", "phone": "905441112233"}, {"name": "B", "phone": "905331112233"}]})
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "duplicates": 1, "invalid": 0}
    assert emitted == [{"bulk": True, "count": 1}]


@pytest.mark.asyncio
async def test_put_without_stored_id_excludes_itself_by_phone(integration_client, cust):
    client, _r, _d = integration_client
    del cust.docs[0]["id"]
    resp = await client.put("/api/customers/905551112233", json={"phone": "05551112233"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_still_blocks_number_only_in_appointments(integration_client, cust, org_id):
    client, _r, db = integration_client
    db.appointments.docs.append({"organization_id": org_id, "phone": "905321110000"})
    resp = await client.post("/api/customers", json={"name": "X", "phone": "5321110000"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == DUP_DETAIL


@pytest.mark.asyncio
async def test_bulk_counts_keyed_number_as_duplicate(integration_client, cust, integration_db):
    client, _r, _d = integration_client
    integration_db.customers.docs[0]["phone"] = "+905551112233"  # stored with a plus sign
    resp = await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "Ayşe", "phone": "05551112233"},
        {"name": "Yeni", "phone": "905441112233"},
    ]})
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "duplicates": 1, "invalid": 0}
    new = [d for d in cust.docs if d["id"] != "c1"]
    assert len(new) == 1 and new[0]["phone_key"] == "905441112233"


@pytest.mark.asyncio
async def test_bulk_dedupes_variants_within_batch(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.post("/api/customers/bulk", json={"contacts": [
        {"name": "A", "phone": "905441112233"},
        {"name": "B", "phone": "05441112233"},
    ]})
    assert resp.json() == {"created": 1, "duplicates": 1, "invalid": 0}


@pytest.mark.asyncio
async def test_put_phone_change_to_existing_key_is_400(integration_client, cust, org_id):
    client, _r, _d = integration_client
    cust.docs.append({"id": "c2", "organization_id": org_id, "name": "Mehmet",
                      "phone": "905441112233", "phone_key": "905441112233"})
    resp = await client.put("/api/customers/905441112233", json={"phone": "05551112233"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_put_phone_change_recomputes_key(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.put("/api/customers/905551112233", json={"phone": "05367778899"})
    assert resp.status_code == 200
    doc = cust.docs[0]
    assert doc["phone"] == "05367778899"
    assert doc["phone_key"] == "905367778899"


@pytest.mark.asyncio
async def test_put_reformatting_own_number_is_allowed(integration_client, cust):
    client, _r, _d = integration_client
    resp = await client.put("/api/customers/905551112233", json={"phone": "05551112233"})
    assert resp.status_code == 200
    assert cust.docs[0]["phone_key"] == "905551112233"


@pytest.mark.asyncio
async def test_response_shapes_unchanged(integration_client, cust):
    client, _r, _d = integration_client
    c = await client.post("/api/customers", json={"name": "Yeni", "phone": "905441112233"})
    assert set(c.json()) == {"id", "name", "phone", "message"}
    b = await client.post("/api/customers/bulk", json={"contacts": [{"name": "Z", "phone": "905331112233"}]})
    assert set(b.json()) == {"created", "duplicates", "invalid"}
    p = await client.put("/api/customers/905551112233", json={"phone": "05367778899"})
    assert set(p.json()) == {"message", "updates"}
    assert set(p.json()["updates"]) == {"phone"}
