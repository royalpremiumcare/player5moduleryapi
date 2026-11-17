"""Service renames and customer edits reach active appointments and open dashboards."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from name_sync import (
    APPOINTMENTS_CHANGED_EVENT,
    istanbul_today,
    propagate_service_rename,
    sync_customer_to_appointments,
)
from tests.live_activity_fakes import FakeDB
from tests.test_live_activity_wiring import _block

ORG = "org-1"
TODAY = "2026-11-17"


class EmitSpy:
    def __init__(self):
        self.calls = []

    async def __call__(self, org_id, event, data):
        self.calls.append((org_id, event, data))


def _apt(apt_id, **kw):
    doc = {
        "id": apt_id, "organization_id": ORG, "phone": "5550000000", "customer_name": "Ayşe",
        "service_id": "svc-a", "service_name": "Kesim", "appointment_date": TODAY,
        "appointment_time": "10:00", "status": "Bekliyor",
        "services": [{"service_id": "svc-a", "sequence": 0, "name_snapshot": "Kesim",
                      "slug_snapshot": "kesim", "duration_snapshot": 30, "price_snapshot": 100.0,
                      "service_version": 1}],
    }
    doc.update(kw)
    return doc


def _by_id(db):
    return {d["id"]: d for d in db.appointments.docs}


# --- service rename -----------------------------------------------------------

async def test_service_rename_updates_today_and_future_active_appointments_only():
    db = FakeDB()
    db.appointments.docs.extend([
        _apt("today"),
        _apt("future", appointment_date="2026-12-01", status="Onaylandı"),
        _apt("legacy-future", appointment_date="2026-11-20", services=None),
        _apt("past", appointment_date="2026-11-16"),
        _apt("done", status="Tamamlandı"),
        _apt("cancel-1", status="İptal"),
        _apt("cancel-2", status="İptal Edildi"),
        _apt("cancel-en", status="Cancelled"),
        _apt("done-en", status="Completed"),
        _apt("other-org", organization_id="org-2"),
        _apt("other-svc", service_id="svc-b", service_name="Boya",
             services=[{"service_id": "svc-b", "sequence": 0, "name_snapshot": "Boya"}]),
    ])
    emit = EmitSpy()

    changed = await propagate_service_rename(db, ORG, "svc-a", "Saç Kesimi", emit=emit, today=TODAY)

    docs = _by_id(db)
    assert sorted(changed) == ["future", "legacy-future", "today"]
    for k in ("today", "future", "legacy-future"):
        assert docs[k]["service_name"] == "Saç Kesimi"
    assert docs["today"]["services"][0]["name_snapshot"] == "Saç Kesimi"
    assert docs["future"]["services"][0]["name_snapshot"] == "Saç Kesimi"
    assert docs["today"]["services"][0]["slug_snapshot"] == "kesim"  # analytics key stays stable
    assert docs["legacy-future"]["services"] is None
    for k in ("past", "done", "cancel-1", "cancel-2", "cancel-en", "done-en", "other-org"):
        assert docs[k]["service_name"] == "Kesim", k
        assert docs[k]["services"][0]["name_snapshot"] == "Kesim", k
    assert docs["other-svc"]["service_name"] == "Boya"
    assert docs["other-svc"]["services"][0]["name_snapshot"] == "Boya"
    assert emit.calls == [(ORG, APPOINTMENTS_CHANGED_EVENT,
                           {"reason": "service_renamed", "service_id": "svc-a",
                            "appointment_ids": changed})]


async def test_service_rename_rebuilds_multi_service_combined_name():
    db = FakeDB()
    lines = [
        {"service_id": "svc-b", "sequence": 0, "name_snapshot": "Boya"},
        {"service_id": "svc-a", "sequence": 1, "name_snapshot": "Kesim"},
        {"service_id": "svc-c", "sequence": 2, "name_snapshot": "Fön"},
    ]
    # svc-a is the second service, so the appointment's own service_id is svc-b
    db.appointments.docs.append(_apt("multi", service_id="svc-b", service_name="Boya + Kesim + Fön",
                                     services=lines))
    db.appointments.docs.append(_apt("multi-past", appointment_date="2026-11-01", service_id="svc-b",
                                     service_name="Boya + Kesim + Fön",
                                     services=[dict(x) for x in lines]))
    emit = EmitSpy()

    changed = await propagate_service_rename(db, ORG, "svc-a", "Saç Kesimi", emit=emit, today=TODAY)

    docs = _by_id(db)
    assert changed == ["multi"]
    assert docs["multi"]["service_name"] == "Boya + Saç Kesimi + Fön"
    assert [x["name_snapshot"] for x in docs["multi"]["services"]] == ["Boya", "Saç Kesimi", "Fön"]
    assert docs["multi-past"]["service_name"] == "Boya + Kesim + Fön"
    assert len(emit.calls) == 1


async def test_service_rename_without_matching_appointments_emits_nothing():
    db = FakeDB()
    db.appointments.docs.append(_apt("past", appointment_date="2026-01-01"))
    emit = EmitSpy()

    changed = await propagate_service_rename(db, ORG, "svc-a", "Saç Kesimi", emit=emit, today=TODAY)

    assert changed == []
    assert emit.calls == []
    assert not [c for c in db.log if c[1] == "update_many"]


async def test_service_rename_writes_are_org_scoped_and_batched():
    db = FakeDB()
    db.appointments.docs.extend(_apt(f"a{i}", appointment_date="2026-11-2%d" % i) for i in range(5))
    emit = EmitSpy()

    await propagate_service_rename(db, ORG, "svc-a", "Saç Kesimi", emit=emit, today=TODAY)

    writes = [c for c in db.log if c[1] == "update_many"]
    assert len(writes) == 1  # one write for the whole group, not one per appointment
    for _coll, _m, args in writes:
        assert args[0]["organization_id"] == ORG


def test_istanbul_today_uses_istanbul_calendar_day():
    # 22:30 UTC on the 16th is already 01:30 on the 17th in Istanbul
    assert istanbul_today(datetime(2026, 11, 16, 22, 30, tzinfo=ZoneInfo("UTC"))) == "2026-11-17"


# --- customer edit ------------------------------------------------------------

async def test_customer_rename_emits_one_org_event_when_appointments_changed():
    db = FakeDB()
    db.appointments.docs.extend([_apt("a1"), _apt("a2", appointment_date="2026-01-01"),
                                 _apt("x", organization_id="org-2")])
    emit = EmitSpy()

    n = await sync_customer_to_appointments(db, ORG, "5550000000", new_name="Ayşe Yılmaz", emit=emit)

    docs = _by_id(db)
    assert n == 2
    assert docs["a1"]["customer_name"] == "Ayşe Yılmaz"
    assert docs["a2"]["customer_name"] == "Ayşe Yılmaz"  # existing behaviour: every appointment
    assert docs["x"]["customer_name"] == "Ayşe"
    assert len(emit.calls) == 1
    org, event, _data = emit.calls[0]
    assert (org, event) == (ORG, APPOINTMENTS_CHANGED_EVENT)


async def test_customer_rename_without_appointments_emits_nothing():
    db = FakeDB()
    db.appointments.docs.append(_apt("x", organization_id="org-2"))
    emit = EmitSpy()

    n = await sync_customer_to_appointments(db, ORG, "5550000000", new_name="Ayşe Yılmaz", emit=emit)

    assert n == 0
    assert emit.calls == []


async def test_customer_phone_and_name_change_emit_exactly_once():
    db = FakeDB()
    db.appointments.docs.append(_apt("a1"))
    emit = EmitSpy()

    await sync_customer_to_appointments(db, ORG, "5550000000", new_phone="5551111111",
                                        new_name="Ayşe Yılmaz", emit=emit)

    doc = _by_id(db)["a1"]
    assert (doc["phone"], doc["customer_name"]) == ("5551111111", "Ayşe Yılmaz")
    assert len(emit.calls) == 1


async def test_emit_failure_does_not_break_the_update():
    db = FakeDB()
    db.appointments.docs.append(_apt("a1"))

    async def boom(*_a):
        raise RuntimeError("socket down")

    n = await sync_customer_to_appointments(db, ORG, "5550000000", new_name="Yeni", emit=boom)
    assert n == 1
    changed = await propagate_service_rename(db, ORG, "svc-a", "Yeni Hizmet", emit=boom, today=TODAY)
    assert changed == ["a1"]


# --- server.py wiring (read as text; importing server.py has heavy side effects) --

EMIT_ARG = "emit=_org_emit_after_stats_refresh(request, current_user)"


def test_update_service_propagates_name_change():
    body = _block(r"^async def update_service\(", r"^@api_router")
    assert "propagate_service_rename(" in body
    assert EMIT_ARG in body
    # only after the service itself is saved
    assert body.index("db.services.update_one(") < body.index("propagate_service_rename(")


def test_update_customer_uses_sync_helper_with_org_event():
    body = _block(r"^async def update_customer\(", r"^@api_router")
    assert "sync_customer_to_appointments(" in body
    assert EMIT_ARG in body
    assert "db.appointments.update_many(" not in body  # one code path for the propagation


def test_emit_wrapper_refreshes_dashboard_stats_before_emitting():
    # dashboard_stats caches today's customer/service names; the reload the event
    # triggers must not be served the stale cache.
    body = _block(r"^def _org_emit_after_stats_refresh\(", r"\n(?=\S)")
    assert '"dashboard_stats"' in body
    assert body.index('"dashboard_stats"') < body.index("await emit_to_organization(")


def test_changed_event_runs_live_activity_resync():
    body = _block(r"^async def emit_to_organization", r"\n(?=\S)")
    assert f'"{APPOINTMENTS_CHANGED_EVENT}"' in body
