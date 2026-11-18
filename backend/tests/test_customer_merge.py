"""Merge engine (Faz 8): duplicate groups, classes, survivor, merge_into on FakeDB."""
import copy
import uuid

import pytest

from customer_merge import (
    DuplicateGroup,
    find_duplicate_groups,
    mark_not_duplicate,
    merge_into,
    reference_counts,
)
from tests.live_activity_fakes import FakeDB

ORG = "org-1"


def _cust(phone, name, created_at="2026-01-01T00:00:00+00:00", total=0, **kw):
    doc = {"id": str(uuid.uuid4()), "organization_id": ORG, "name": name, "phone": phone,
           "notes": "", "created_at": created_at,
           "total_appointments": total, "completed_appointments": 0}
    doc.update(kw)
    return doc


def _appt(phone, name, date, time="10:00", status="Bekliyor", org=ORG):
    return {"id": str(uuid.uuid4()), "organization_id": org, "phone": phone,
            "customer_name": name, "appointment_date": date, "appointment_time": time,
            "status": status}


async def _db(customers=(), **collections):
    db = FakeDB()
    for c in customers:
        await db.customers.insert_one(c)
    for name, docs in collections.items():
        for d in docs:
            await getattr(db, name).insert_one(d)
    return db


def _snapshot(db):
    return {name: copy.deepcopy(col.docs) for name, col in db._collections.items()}


def _by_key(groups):
    return {g.key: g for g in groups}


async def test_classification_A_B_CD():
    db = await _db([
        _cust("905551110001", "Canan Çelik"),
        _cust("05551110001", "Canan Çelik Müşteri"),
        _cust("905551110002", "Melek Hilal Kaplan"),
        _cust("05551110002", "Melek Hilal Ölmez Kaplan"),
        _cust("905551110003", "Makbule"),
        _cust("05551110003", "Kadir Burak"),
        _cust("905551110004", "Tek Kişi"),
    ])
    groups = _by_key(await find_duplicate_groups(db, ORG))
    assert set(groups) == {"905551110001", "905551110002", "905551110003"}
    assert groups["905551110001"].klass == "A"
    assert groups["905551110002"].klass == "B"
    assert groups["905551110003"].klass == "CD"
    assert all(isinstance(g, DuplicateGroup) and g.organization_id == ORG for g in groups.values())
    assert all(len(g.members) == 2 for g in groups.values())


async def test_class_is_pairwise_and_empty_names_are_not_A():
    db = await _db([
        # "ayse" ⊂ "ayse kaya" and ⊂ "ayse demir", but "ayse kaya" vs "ayse demir" fails.
        _cust("905551110005", "Ayşe"),
        _cust("05551110005", "Ayşe Kaya"),
        _cust("5551110005", "Ayşe Demir"),
        _cust("905551110006", ""),
        _cust("05551110006", "  "),
    ])
    groups = _by_key(await find_duplicate_groups(db, ORG))
    assert groups["905551110005"].klass == "CD"
    assert groups["905551110006"].klass == "CD"


async def test_survivor_most_appointments_then_oldest():
    most = _cust("05551110001", "Canan Çelik", created_at="2026-05-01T00:00:00+00:00", total=7)
    older = _cust("905551110001", "Canan Çelik", created_at="2025-01-01T00:00:00+00:00", total=3)
    oldest_tie = _cust("905551110002", "Melek", created_at="2025-01-01T00:00:00+00:00", total=2)
    newer_tie = _cust("05551110002", "Melek", created_at="2026-01-01T00:00:00+00:00", total=2)
    db = await _db([older, most, newer_tie, oldest_tie])
    groups = _by_key(await find_duplicate_groups(db, ORG))
    assert groups["905551110001"].survivor_id == most["id"]
    assert groups["905551110002"].survivor_id == oldest_tie["id"]


async def test_groups_by_computed_key_and_keeps_stored_key_on_survivor():
    # Created after deploy: already holds phone_key, but has fewer appointments.
    keyed = _cust("905551110001", "Canan Çelik", created_at="2026-12-01T00:00:00+00:00",
                  total=1, phone_key="905551110001")
    busy = _cust("05551110001", "Canan Çelik", created_at="2025-01-01T00:00:00+00:00", total=9)
    db = await _db([keyed, busy])
    (group,) = await find_duplicate_groups(db, ORG)
    assert group.key == "905551110001"
    assert {m["id"] for m in group.members} == {keyed["id"], busy["id"]}
    assert group.survivor_id == keyed["id"]


async def test_groups_use_org_country_and_scope():
    db = await _db([
        _cust("07700900123", "John Smith", organization_id="org-uk"),
        _cust("447700900123", "John Smith", organization_id="org-uk"),
        _cust("905551110001", "Canan", organization_id="org-2"),
        _cust("05551110001", "Canan", organization_id="org-2"),
        _cust("0", "Walk-in"), _cust("0", "Walk-in"),
    ])
    await db.settings.insert_one({"organization_id": "org-uk", "base_currency": "GBP"})
    all_groups = await find_duplicate_groups(db)
    assert {(g.organization_id, g.key) for g in all_groups} == {
        ("org-uk", "447700900123"), ("org-2", "905551110001")}
    assert [g.organization_id for g in await find_duplicate_groups(db, "org-2")] == ["org-2"]


async def test_reference_counts_lists_what_would_change():
    survivor = _cust("905551110001", "Canan Çelik", total=2)
    source = _cust("05551110001", "Canan Çelik Müşteri")
    db = await _db(
        [survivor, source],
        appointments=[_appt("05551110001", "Canan", "2026-01-01"),
                      _appt("05551110001", "Canan", "2026-01-02"),
                      _appt("905551110001", "Canan", "2026-01-03"),
                      _appt("05551110001", "Canan", "2026-01-04", org="org-other")],
        customer_notes=[{"organization_id": ORG, "phone": "05551110001", "notes": "x"}],
        marketing_autopilot_tasks=[{"organization_id": ORG, "phone": "05551110001"}],
        merchant_transactions=[{"organization_id": ORG, "customer_phone": "05551110001"}],
        refund_requests=[],
        stripe_customers=[{"organization_id": ORG, "customer_phone": "05551110001"}],
    )
    (group,) = await find_duplicate_groups(db, ORG)
    assert await reference_counts(db, group) == {
        "appointments": 2, "customer_notes": 1, "marketing_autopilot_tasks": 1,
        "merchant_transactions": 1, "refund_requests": 0, "stripe_customers": 1,
    }


async def _merge_fixture():
    survivor = _cust("905551110001", "Canan Çelik", total=1, notes="VIP", phone_key="905551110001")
    source = _cust("05551110001", "Canan Çelik Müşteri", total=2, notes="Alerji: lateks")
    db = await _db(
        [survivor, source],
        appointments=[_appt("905551110001", "Canan Çelik", "2026-02-01", "09:30", "Tamamlandı"),
                      _appt("05551110001", "Canan Çelik Müşteri", "2026-01-15", "", "Tamamlandı"),
                      _appt("05551110001", "Canan Çelik Müşteri", "2026-03-01", "14:00")],
        customer_notes=[{"organization_id": ORG, "phone": "905551110001", "notes": "Sarı saç"},
                        {"organization_id": ORG, "phone": "05551110001", "notes": "Kısa kesim"}],
        stripe_customers=[{"organization_id": ORG, "customer_phone": "905551110001", "sid": "s1"},
                          {"organization_id": ORG, "customer_phone": "05551110001", "sid": "s2"}],
    )
    return db, survivor, source


async def test_merge_concatenates_notes_and_keeps_survivor_stripe_row():
    db, survivor, source = await _merge_fixture()
    summary = await merge_into(db, ORG, survivor["id"], source["id"])
    assert summary["merged"] is True
    (cust,) = db.customers.docs
    assert cust["id"] == survivor["id"] and cust["phone"] == "905551110001"
    assert cust["notes"] == "VIP\nAlerji: lateks"
    (note,) = db.customer_notes.docs
    assert note["phone"] == "905551110001" and note["notes"] == "Sarı saç\nKısa kesim"
    assert sorted((s["sid"], s["customer_phone"]) for s in db.stripe_customers.docs) == [
        ("s1", "905551110001"), ("s2", "05551110001")]
    assert summary["stripe_customers_left"] == 1


async def test_merge_recomputes_counters_from_appointments():
    db, survivor, source = await _merge_fixture()
    await merge_into(db, ORG, survivor["id"], source["id"])
    (cust,) = db.customers.docs
    assert cust["total_appointments"] == 3
    assert cust["completed_appointments"] == 2
    assert cust["first_appointment_at"] == "2026-01-15T00:00:00"
    assert cust["last_appointment_at"] == "2026-03-01T14:00:00"
    assert {a["phone"] for a in db.appointments.docs} == {"905551110001"}
    assert {a["customer_name"] for a in db.appointments.docs} == {
        "Canan Çelik", "Canan Çelik Müşteri"}


async def test_merge_same_phone_string_leaves_appointments_untouched():
    survivor = _cust("905551110001", "Makbule Yılmaz", phone_key="905551110001")
    source = _cust("905551110001", "Makbule Yilmaz", shared_phone=True,
                   merge_suggestion_for=survivor["id"])
    db = await _db([survivor, source],
                   appointments=[_appt("905551110001", "Makbule Yilmaz", "2026-01-01")])
    before = copy.deepcopy(db.appointments.docs)
    summary = await merge_into(db, ORG, survivor["id"], source["id"])
    assert db.appointments.docs == before
    assert summary["repointed"]["appointments"] == 0
    (cust,) = db.customers.docs
    assert cust["id"] == survivor["id"] and cust["total_appointments"] == 1


async def test_merge_keeps_third_party_on_the_same_phone_string():
    survivor = _cust("905551110001", "Makbule Yılmaz", phone_key="905551110001")
    source = _cust("05551110001", "Makbule Yilmaz", shared_phone=True)
    other = _cust("05551110001", "Kadir Burak", shared_phone=True)
    db = await _db(
        [survivor, source, other],
        appointments=[_appt("05551110001", "Makbule Yilmaz", "2026-01-01"),
                      _appt("05551110001", "Kadir Burak", "2026-01-02")],
        customer_notes=[{"organization_id": ORG, "phone": "05551110001", "notes": "ortak"}],
    )
    summary = await merge_into(db, ORG, survivor["id"], source["id"])
    phones = {a["customer_name"]: a["phone"] for a in db.appointments.docs}
    assert phones == {"Makbule Yilmaz": "905551110001", "Kadir Burak": "05551110001"}
    assert db.customer_notes.docs[0]["phone"] == "05551110001"
    assert "customer_notes" in summary["left_for_shared_phone"]
    names = {c["name"]: c for c in db.customers.docs}
    assert set(names) == {"Makbule Yılmaz", "Kadir Burak"}
    assert names["Makbule Yılmaz"]["total_appointments"] == 1


async def test_merge_refuses_different_numbers_and_self():
    a = _cust("905551110001", "Canan")
    b = _cust("905551119999", "Canan")
    db = await _db([a, b])
    with pytest.raises(ValueError):
        await merge_into(db, ORG, a["id"], b["id"])
    with pytest.raises(ValueError):
        await merge_into(db, ORG, a["id"], a["id"])
    assert len(db.customers.docs) == 2


async def test_merge_idempotent_second_run_noop():
    db, survivor, source = await _merge_fixture()
    backup: list = []
    first = await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    assert first["merged"] is True and backup
    state, n_backup = _snapshot(db), len(backup)
    second = await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    assert second["merged"] is False
    assert _snapshot(db) == state
    assert len(backup) == n_backup


async def test_merge_resumed_after_crash_does_not_append_notes_twice():
    db, survivor, source = await _merge_fixture()
    backup: list = []
    await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    # Crash before the source delete: the source and its note row are still there.
    gone = [e["doc"] for e in backup if e["doc"].get("id") == source["id"]
            or e["doc"].get("notes") == "Kısa kesim"]
    await db.customers.insert_one(next(d for d in gone if d.get("id") == source["id"]))
    await db.customer_notes.insert_one(next(d for d in gone if d.get("notes") == "Kısa kesim"))
    await merge_into(db, ORG, survivor["id"], source["id"])
    (cust,) = db.customers.docs
    assert cust["notes"] == "VIP\nAlerji: lateks"
    (note,) = db.customer_notes.docs
    assert note["notes"] == "Sarı saç\nKısa kesim"


async def test_merge_backup_holds_prior_state_of_every_touched_doc():
    db, survivor, source = await _merge_fixture()
    before = _snapshot(db)
    backup: list = []
    await merge_into(db, ORG, survivor["id"], source["id"], backup=backup)
    for entry in backup:
        assert set(entry) == {"collection", "filter", "doc"}
        assert entry["doc"] in before[entry["collection"]]
    touched = {(e["collection"], e["doc"]["_id"]) for e in backup}
    after = _snapshot(db)
    changed = {(name, d["_id"]) for name, docs in before.items() for d in docs
               if d not in after.get(name, [])}
    assert changed and changed <= touched


async def test_mark_not_duplicate_clears_suggestion_keeps_shared_flag():
    keyed = _cust("905551110001", "Makbule", phone_key="905551110001")
    shared = _cust("905551110001", "Kadir Burak", shared_phone=True,
                   merge_suggestion_for=keyed["id"])
    db = await _db([keyed, shared])
    await mark_not_duplicate(db, ORG, shared["id"])
    doc = next(c for c in db.customers.docs if c["id"] == shared["id"])
    assert "merge_suggestion_for" not in doc
    assert doc["shared_phone"] is True
