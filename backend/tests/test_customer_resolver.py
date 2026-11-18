"""Resolver: one customer per canonical phone key; counters follow the matched record."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest
from pymongo.errors import DuplicateKeyError

import customer_resolver
from customer_resolver import find_customer_for, org_country, resolve_customer
from customer_identity import names_match, normalize_name, phone_key
from tests.live_activity_fakes import FakeDB
from tests.test_live_activity_wiring import _block

ORG = "org-1"


def _load_delta():
    ns = {
        "datetime": datetime, "timezone": timezone, "uuid": uuid, "logging": logging,
        "Optional": Optional, "find_customer_for": customer_resolver.find_customer_for,
        "org_country": customer_resolver.org_country, "phone_key": phone_key,
        "names_match": names_match, "normalize_name": normalize_name,
        "DuplicateKeyError": DuplicateKeyError,
    }
    exec(_block(r"^def _appointment_datetime_iso", r"\n(?=(?:async def|def|class|@)\b)"), ns)
    exec(_block(r"^async def _apply_customer_delta", r"\n(?=(?:async def|def|class|@)\b)"), ns)
    return ns["_apply_customer_delta"]


apply_delta = _load_delta()


def _cust(phone, name, **kw):
    doc = {"id": str(uuid.uuid4()), "organization_id": ORG, "name": name, "phone": phone,
           "notes": "", "created_at": "2026-01-01T00:00:00+00:00",
           "total_appointments": 0, "completed_appointments": 0}
    doc.update(kw)
    return doc


def _db(*customers, currency=None):
    db = FakeDB()
    db.customers.docs.extend(customers)
    if currency:
        db.settings.docs.append({"organization_id": ORG, "base_currency": currency})
    return db


async def test_org_country_from_currency():
    assert await org_country(_db(currency="GBP"), ORG) == "UK"
    assert await org_country(_db(currency="TRY"), ORG) == "TR"
    assert await org_country(_db(), ORG) == "TR"


async def test_format_variant_reuses_keyed_customer():
    existing = _cust("905551112233", "Ayşe", phone_key="905551112233")
    db = _db(existing)
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=1)
    assert len(db.customers.docs) == 1
    assert db.customers.docs[0]["total_appointments"] == 1
    assert db.customers.docs[0]["phone"] == "905551112233"


async def test_new_keyed_number_upserts_with_phone_key():
    db = _db()
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=1)
    (doc,) = db.customers.docs
    assert doc["phone_key"] == "905551112233"
    assert doc["phone"] == "05551112233"
    assert doc["total_appointments"] == 1


async def test_walk_in_zero_stays_unkeyed():
    db = _db()
    await apply_delta(db, ORG, "0", "Walk-in", delta_total=1)
    (doc,) = db.customers.docs
    assert "phone_key" not in doc
    assert doc["phone"] == "0"


async def test_shared_number_counters_follow_name():
    keyed = _cust("05551112233", "Makbule", phone_key="905551112233")
    shared = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, shared)
    await apply_delta(db, ORG, "05551112233", "Kadir Burak", delta_total=1)
    by_name = {d["name"]: d for d in db.customers.docs}
    assert by_name["Kadir Burak"]["total_appointments"] == 1
    assert by_name["Makbule"]["total_appointments"] == 0


async def test_negative_delta_clamps_on_matched_record():
    db = _db(_cust("905551112233", "Ayşe", phone_key="905551112233"))
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=-1)
    assert db.customers.docs[0]["total_appointments"] == 0


async def test_delta_swallows_errors():
    class Boom:
        def __getattr__(self, _):
            raise RuntimeError("db down")
    await apply_delta(Boom(), ORG, "05551112233", "Ayşe", delta_total=1)


async def test_public_name_mismatch_creates_shared_suggestion():
    keyed = _cust("905551112233", "Makbule Yılmaz", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Kadir Burak", mode="public")
    assert created is True
    assert doc["shared_phone"] is True
    assert doc["merge_suggestion_for"] == keyed["id"]
    assert "phone_key" not in doc
    assert "allow_shared_phone" not in doc
    assert len(db.customers.docs) == 2


async def test_public_same_name_variant_reuses():
    keyed = _cust("905551112233", "Makbule Yılmaz", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "makbule yilmaz", mode="public")
    assert created is False and doc["id"] == keyed["id"]


async def test_public_single_token_matches_when_only_customer():
    keyed = _cust("905551112233", "Alara Kaya", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Alara", mode="public")
    assert created is False and doc["id"] == keyed["id"]


async def test_public_subset_not_used_when_number_has_several_customers():
    keyed = _cust("05551112233", "Alara Kaya", phone_key="905551112233")
    other = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, other)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Alara", mode="public")
    assert created is True and doc["shared_phone"] is True


async def test_admin_reuses_whatever_the_name():
    keyed = _cust("905551112233", "Makbule", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Başka Biri", mode="admin")
    assert created is False and doc["id"] == keyed["id"]
    assert len(db.customers.docs) == 1


async def test_appointment_name_mismatch_creates_shared_suggestion():
    """R15: an admin appointment for a known number under another name asks, never merges."""
    keyed = _cust("905551112233", "Makbule Yılmaz", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Kadir Burak", mode="appointment")
    assert created is True
    assert doc["shared_phone"] is True
    assert doc["merge_suggestion_for"] == keyed["id"]
    assert doc["phone"] == "05551112233" and doc["name"] == "Kadir Burak"
    assert "phone_key" not in doc
    assert len(db.customers.docs) == 2


async def test_appointment_suggestion_points_at_the_keyed_record():
    unkeyed_old = _cust("05551112233", "Zeynep", shared_phone=True)
    keyed = _cust("905551112233", "Makbule", phone_key="905551112233")
    db = _db(unkeyed_old, keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Kadir", mode="appointment")
    assert created is True and doc["merge_suggestion_for"] == keyed["id"]


async def test_appointment_single_token_matches_when_only_customer():
    keyed = _cust("905551112233", "Alara Kaya", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(db, ORG, "05551112233", "alara", mode="appointment")
    assert created is False and doc["id"] == keyed["id"]
    assert len(db.customers.docs) == 1


async def test_appointment_subset_not_used_when_number_has_several_customers():
    keyed = _cust("05551112233", "Alara Kaya", phone_key="905551112233")
    other = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, other)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Alara", mode="appointment")
    assert created is True and doc["shared_phone"] is True
    assert doc["merge_suggestion_for"] == keyed["id"]


async def test_appointment_exact_name_reuses_the_shared_record():
    keyed = _cust("05551112233", "Makbule", phone_key="905551112233")
    shared = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, shared)
    doc, created = await resolve_customer(db, ORG, "905551112233", "Kadir Burak", mode="appointment")
    assert created is False and doc["id"] == shared["id"]
    assert len(db.customers.docs) == 2


async def test_appointment_unkeyed_number_still_reuses_whatever_the_name():
    """R15 covers keyed numbers only; an unkeyed number keeps the old appointment behaviour."""
    old = _cust("12345", "Makbule")
    db = _db(old)
    doc, created = await resolve_customer(db, ORG, "12345", "Başka", mode="appointment")
    assert created is False and doc["id"] == old["id"]
    assert len(db.customers.docs) == 1


async def test_appointment_shared_record_then_counters_follow_each_name():
    """R15 + delta: after the shared record exists, _pick sends each name's counters home."""
    keyed = _cust("905551112233", "Makbule Yılmaz", phone_key="905551112233")
    db = _db(keyed)
    shared, _ = await resolve_customer(db, ORG, "05551112233", "Kadir Burak", mode="appointment")
    await apply_delta(db, ORG, "05551112233", "Kadir Burak", delta_total=1)
    await apply_delta(db, ORG, "0555 111 22 33", "Makbule Yılmaz", delta_total=1)
    by_id = {d["id"]: d for d in db.customers.docs}
    assert by_id[shared["id"]]["total_appointments"] == 1
    assert by_id[keyed["id"]]["total_appointments"] == 1
    assert by_id[keyed["id"]]["name"] == "Makbule Yılmaz"
    assert customer_resolver.phone_for_appointment(shared["phone"], "05551112233") == "05551112233"


async def test_admin_allow_shared_creates_unkeyed():
    keyed = _cust("905551112233", "Makbule", phone_key="905551112233")
    db = _db(keyed)
    doc, created = await resolve_customer(
        db, ORG, "05551112233", "Kadir", mode="admin", allow_shared=True)
    assert created is True
    assert doc["shared_phone"] is True and "phone_key" not in doc
    assert len(db.customers.docs) == 2


async def test_new_number_inserts_keyed_record_with_standard_shape():
    db = _db()
    doc, created = await resolve_customer(db, ORG, "05551112233", "Ayşe", mode="admin")
    assert created is True
    assert doc["phone_key"] == "905551112233" and doc["phone"] == "05551112233"
    for f in ("id", "organization_id", "name", "created_at", "notes"):
        assert f in doc
    assert "shared_phone" not in doc


async def test_concurrent_resolve_one_record():
    db = _db()
    # a unique partial index like the production one
    await db.customers.create_index(
        [("organization_id", 1), ("phone_key", 1)], unique=True,
        partialFilterExpression={"phone_key": {"$exists": True}})
    (a, ca), (b, cb) = await asyncio.gather(
        resolve_customer(db, ORG, "05551112233", "Ayşe", mode="admin"),
        resolve_customer(db, ORG, "5551112233", "Ayşe", mode="admin"),
    )
    assert len(db.customers.docs) == 1
    assert a["id"] == b["id"]
    assert sorted([ca, cb]) == [False, True]


async def test_find_customer_for_prefers_name_then_keyed():
    keyed = _cust("05551112233", "Makbule", phone_key="905551112233")
    shared = _cust("05551112233", "Kadir", shared_phone=True)
    db = _db(shared, keyed)
    assert (await find_customer_for(db, ORG, "05551112233", "Kadir"))["id"] == shared["id"]
    assert (await find_customer_for(db, ORG, "05551112233", "Zeynep"))["id"] == keyed["id"]
    assert await find_customer_for(db, ORG, "05559998877", "X") is None


async def test_delta_finds_unkeyed_variant_record_and_leaves_it_unkeyed():
    old = _cust("905551112233", "Ayşe")  # pre-backfill: no key
    db = _db(old)
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=1)
    assert len(db.customers.docs) == 1
    assert db.customers.docs[0]["total_appointments"] == 1
    assert "phone_key" not in db.customers.docs[0]


async def test_shared_record_found_in_another_phone_format():
    keyed = _cust("05551112233", "Makbule", phone_key="905551112233")
    shared = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, shared)
    await apply_delta(db, ORG, "905551112233", "Kadir Burak", delta_total=1)
    assert len(db.customers.docs) == 2
    assert {d["name"]: d["total_appointments"] for d in db.customers.docs} == {
        "Makbule": 0, "Kadir Burak": 1}


async def test_public_repeat_booking_other_format_reuses_shared_record():
    keyed = _cust("05551112233", "Makbule", phone_key="905551112233")
    shared = _cust("05551112233", "Kadir Burak", shared_phone=True)
    db = _db(keyed, shared)
    doc, created = await resolve_customer(db, ORG, "905551112233", "Kadir Burak", mode="public")
    assert created is False and doc["id"] == shared["id"]
    assert len(db.customers.docs) == 2


async def test_public_unkeyed_variant_record_same_name_not_duplicated():
    old = _cust("905551112233", "Ayşe")
    db = _db(old)
    doc, created = await resolve_customer(db, ORG, "05551112233", "Ayşe", mode="public")
    assert created is False and doc["id"] == old["id"]
    assert len(db.customers.docs) == 1


async def test_delta_does_not_rename_a_fallback_record_with_other_name():
    keyed = _cust("905551112233", "Makbule", phone_key="905551112233")
    db = _db(keyed, _cust("05551112233", "Zeynep", shared_phone=True))
    await apply_delta(db, ORG, "05551112233", "Kadir", delta_total=1)
    assert [d["name"] for d in db.customers.docs] == ["Makbule", "Zeynep"]
    assert db.customers.docs[0]["total_appointments"] == 1


async def test_delta_still_updates_name_spelling_on_matching_record():
    db = _db(_cust("905551112233", "ayse", phone_key="905551112233"))
    await apply_delta(db, ORG, "05551112233", "Ayşe Hanım".replace(" Hanım", ""), delta_total=1)
    assert db.customers.docs[0]["name"] == "Ayşe"


async def test_delta_never_shortens_stored_name():
    """R8: "Ayşe" matches "Ayşe Yılmaz" but must not shorten it; counters still apply."""
    db = _db(_cust("905551112233", "Ayşe Yılmaz", phone_key="905551112233"))
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=1)
    assert db.customers.docs[0]["name"] == "Ayşe Yılmaz"
    assert db.customers.docs[0]["total_appointments"] == 1


async def test_delta_equal_length_name_fix_applies():
    """R8 guard: same token count (a spelling or case fix) still updates the name."""
    db = _db(_cust("905551112233", "ayşe yılmaz", phone_key="905551112233"))
    await apply_delta(db, ORG, "05551112233", "Ayşe Yılmaz", delta_total=1)
    assert db.customers.docs[0]["name"] == "Ayşe Yılmaz"


async def test_negative_only_delta_without_customer_is_noop():
    """R9: a decrement for a number nobody has never creates a zero-count record."""
    db = _db()
    await apply_delta(db, ORG, "05551112233", "Ayşe", delta_total=-1, delta_completed=-1)
    assert db.customers.docs == []


def test_phone_for_appointment_uses_stored_phone_for_same_recipient():
    assert customer_resolver.phone_for_appointment("905551112233", "0555 111 22 33") == "905551112233"


def test_phone_for_appointment_keeps_typed_when_recipient_differs():
    """R7: UK local "07…" formats to an invalid WhatsApp recipient, so the typed "+44…" stays."""
    assert customer_resolver.phone_for_appointment("07700900123", "+447700900123") == "+447700900123"
    assert customer_resolver.phone_for_appointment(None, "05551112233") == "05551112233"


async def test_public_unkeyed_phone_other_name_gets_plain_new_record():
    db = _db(_cust("0", "Walk-in A"))
    doc, created = await resolve_customer(db, ORG, "0", "Başka", mode="public")
    assert created is True
    assert "phone_key" not in doc and "shared_phone" not in doc and "merge_suggestion_for" not in doc
    assert len(db.customers.docs) == 2


async def test_delta_on_a_customer_without_id_updates_it_by_phone():
    """Legacy records can lack ``id``: the delta must update them by stored phone, not crash."""
    legacy = _cust("905551112233", "Ayşe Yılmaz", phone_key="905551112233", total_appointments=2)
    legacy.pop("id")
    other_org = _cust("905551112233", "Ayşe Yılmaz", organization_id="org-2")
    other_org.pop("id")
    db = _db(legacy, other_org)
    await apply_delta(db, ORG, "0555 111 22 33", "Ayşe Yılmaz", delta_total=1)
    assert len(db.customers.docs) == 2
    assert db.customers.docs[0]["total_appointments"] == 3
    assert db.customers.docs[1]["total_appointments"] == 0
    await apply_delta(db, ORG, "05551112233", "Ayşe Yılmaz", delta_total=-5)
    assert db.customers.docs[0]["total_appointments"] == 0  # clamp uses the same filter
