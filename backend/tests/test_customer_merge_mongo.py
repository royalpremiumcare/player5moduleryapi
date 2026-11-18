"""Merge engine against a real throwaway MongoDB (skipped unless PK_TEST_MONGO_URL is set)."""
import os
import uuid

import pytest
import pytest_asyncio

from customer_merge import find_duplicate_groups, merge_into, restore_from_backup

MONGO_URL = os.environ.get("PK_TEST_MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="PK_TEST_MONGO_URL not set")

ORG = "org-1"
OTHER = "org-2"
COLLECTIONS = ("customers", "appointments", "customer_notes", "marketing_autopilot_tasks",
               "merchant_transactions", "refund_requests", "stripe_customers", "settings")


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    name = f"pk_merge_test_{uuid.uuid4().hex[:12]}"
    try:
        yield client[name]
    finally:
        await client.drop_database(name)
        client.close()


def _cust(phone, name, org=ORG, **kw):
    doc = {"id": str(uuid.uuid4()), "organization_id": org, "name": name, "phone": phone,
           "notes": "", "created_at": "2026-01-01T00:00:00+00:00",
           "total_appointments": 0, "completed_appointments": 0}
    doc.update(kw)
    return doc


def _appt(phone, name, date, time="10:00", status="Bekliyor", org=ORG):
    return {"id": str(uuid.uuid4()), "organization_id": org, "phone": phone,
            "customer_name": name, "appointment_date": date, "appointment_time": time,
            "status": status}


async def _seed(db):
    survivor = _cust("905551110001", "Canan Çelik", total=5, notes="VIP",
                     created_at="2025-01-01T00:00:00+00:00")
    source = _cust("05551110001", "Canan Çelik Müşteri", total=1, notes="Alerji")
    await db.customers.insert_many([
        survivor, source,
        _cust("05551110001", "Canan Çelik", org=OTHER),  # another org: untouched
    ])
    await db.appointments.insert_many([
        _appt("905551110001", "Canan Çelik", "2026-02-01", "09:30", "Tamamlandı"),
        _appt("05551110001", "Canan Çelik Müşteri", "2026-01-15", "", "Tamamlandı"),
        _appt("05551110001", "Canan Çelik Müşteri", "2026-03-01", "14:00"),
        _appt("05551110001", "Canan Çelik", "2026-03-02", org=OTHER),
    ])
    await db.customer_notes.insert_one(
        {"organization_id": ORG, "phone": "05551110001", "notes": "Kısa kesim"})
    await db.marketing_autopilot_tasks.insert_one(
        {"organization_id": ORG, "phone": "05551110001", "customer_name": "Canan Çelik Müşteri"})
    await db.merchant_transactions.insert_one(
        {"organization_id": ORG, "customer_phone": "05551110001", "amount": 100})
    await db.refund_requests.insert_one(
        {"organization_id": ORG, "customer_phone": "05551110001", "amount": 50})
    await db.stripe_customers.insert_one(
        {"organization_id": ORG, "customer_phone": "05551110001", "stripe_id": "cus_1"})
    await db.merchant_transactions.insert_one(
        {"organization_id": OTHER, "customer_phone": "05551110001", "amount": 7})
    return survivor, source


async def _dump(db):
    out = {}
    for name in COLLECTIONS:
        out[name] = sorted(await db[name].find({}).to_list(None), key=lambda d: str(d["_id"]))
    return out


async def test_merge_repoints_all_references_and_recomputes(db):
    survivor, source = await _seed(db)
    (group,) = await find_duplicate_groups(db, ORG)
    assert group.klass == "A" and group.survivor_id == survivor["id"]

    summary = await merge_into(db, ORG, survivor["id"], source["id"])
    assert summary["merged"] is True

    assert await db.customers.count_documents({"organization_id": ORG}) == 1
    cust = await db.customers.find_one({"id": survivor["id"]})
    assert cust["phone"] == "905551110001"
    assert cust["notes"] == "VIP\nAlerji"
    assert cust["total_appointments"] == 3
    assert cust["completed_appointments"] == 2
    assert cust["first_appointment_at"] == "2026-01-15T00:00:00"
    assert cust["last_appointment_at"] == "2026-03-01T14:00:00"

    org_appts = await db.appointments.find({"organization_id": ORG}).to_list(None)
    assert {a["phone"] for a in org_appts} == {"905551110001"}
    assert "Canan Çelik Müşteri" in {a["customer_name"] for a in org_appts}
    for coll, field in (("customer_notes", "phone"), ("marketing_autopilot_tasks", "phone"),
                        ("merchant_transactions", "customer_phone"),
                        ("refund_requests", "customer_phone"),
                        ("stripe_customers", "customer_phone")):
        docs = await db[coll].find({"organization_id": ORG}).to_list(None)
        assert docs and {d[field] for d in docs} == {"905551110001"}, coll

    # The other org is untouched.
    assert await db.customers.count_documents({"organization_id": OTHER}) == 1
    assert (await db.appointments.find_one({"organization_id": OTHER}))["phone"] == "05551110001"
    assert (await db.merchant_transactions.find_one(
        {"organization_id": OTHER}))["customer_phone"] == "05551110001"


async def test_merge_backup_restores_exact_state(db):
    survivor, source = await _seed(db)
    before = await _dump(db)
    backup: list = []
    await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    assert await _dump(db) != before
    await restore_from_backup(db, backup)
    assert await _dump(db) == before


async def test_merge_rerun_after_merge_is_noop(db):
    survivor, source = await _seed(db)
    backup: list = []
    await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    after, n = await _dump(db), len(backup)
    again = await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    assert again["merged"] is False
    assert await _dump(db) == after and len(backup) == n
