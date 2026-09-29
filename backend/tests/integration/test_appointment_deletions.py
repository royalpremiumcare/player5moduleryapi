"""Silinen randevu kaydı — istatistikteki "Silinen" sayacının kaynağı.

Randevular hard-delete edildiği için sayım `appointment_deletions` kaydına dayanır;
kayıt yazılamasa bile silme akışı bozulmamalı.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import List
from zoneinfo import ZoneInfo

import pytest

import server


class _Coll:
    def __init__(self, fail: bool = False):
        self.docs: List[dict] = []
        self.fail = fail

    async def insert_many(self, docs, ordered=True):
        if self.fail:
            raise RuntimeError("mongo down")
        self.docs.extend(docs)


@pytest.mark.asyncio
async def test_records_each_deleted_appointment_with_istanbul_date():
    db = SimpleNamespace(appointment_deletions=_Coll())
    apts = [
        {"id": "a1", "appointment_date": "2026-10-02", "status": "Bekliyor", "staff_member_id": "gizem@x.com"},
        {"id": "a2", "appointment_date": "2026-09-20", "status": "Tamamlandı", "staff_member_id": None},
    ]

    await server._record_appointment_deletions(db, "org_1", apts, "admin@x.com", "customer_delete")

    docs = db.appointment_deletions.docs
    assert [d["appointment_id"] for d in docs] == ["a1", "a2"]
    assert all(d["organization_id"] == "org_1" for d in docs)
    assert all(d["reason"] == "customer_delete" and d["deleted_by"] == "admin@x.com" for d in docs)
    today_ist = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Istanbul")).date().isoformat()
    assert all(d["deleted_date"] == today_ist for d in docs)
    assert docs[0]["status"] == "Bekliyor" and docs[0]["appointment_date"] == "2026-10-02"


@pytest.mark.asyncio
async def test_empty_list_writes_nothing():
    db = SimpleNamespace(appointment_deletions=_Coll())
    await server._record_appointment_deletions(db, "org_1", [], "admin@x.com", "appointment_delete")
    assert db.appointment_deletions.docs == []


@pytest.mark.asyncio
async def test_write_failure_does_not_raise():
    db = SimpleNamespace(appointment_deletions=_Coll(fail=True))
    await server._record_appointment_deletions(
        db, "org_1", [{"id": "a1"}], "admin@x.com", "appointment_delete"
    )
