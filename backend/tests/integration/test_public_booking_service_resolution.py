"""
Public booking WhatsApp doğrulama regresyonu:

Pending payload (create_pending_verification) tekil hizmette bile hem service_id
hem service_ids=[id] kaydediyor. /public/verify-code bunu resolve_services'e
verince "service_id ve service_ids aynı anda gönderilemez" 400'ü dönüyordu ve
WhatsApp doğrulaması gereken TÜM public randevular onay adımında kırılıyordu.

Fix: resolve_services, ikisi TUTARLIYSA (service_id ∈ service_ids) service_ids'i
otoritatif kabul eder; yalnızca GERÇEKTEN çelişen girdide 400 döner.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class _Cursor:
    def __init__(self, items):
        self._items = items

    async def to_list(self, n=None):
        return list(self._items)


class _ServicesColl:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query, projection=None):
        ids = (query.get("id") or {}).get("$in", [])
        org = query.get("organization_id")
        return _Cursor([d for d in self._docs if d["id"] in ids and d["organization_id"] == org])


class _DB:
    def __init__(self, docs):
        self.services = _ServicesColl(docs)


@pytest.mark.asyncio
async def test_consistent_service_id_and_ids_single_service():
    """Tekil hizmet: service_id=id + service_ids=[id] -> 400 DEĞİL, çözülmeli."""
    from server import resolve_services

    org = "org1"
    db = _DB([{"id": "s1", "organization_id": org, "name": "Saç", "duration": 30, "price": 100}])
    appt = SimpleNamespace(service_id="s1", service_ids=["s1"])

    snap, dur, price, merged, ids = await resolve_services(db, org, appt, multi_enabled=True)
    assert ids == ["s1"]
    assert dur == 30


@pytest.mark.asyncio
async def test_consistent_service_id_and_ids_multi_service():
    """Çoklu hizmet: service_id=ilk + service_ids=[a,b] -> service_ids otoritatif."""
    from server import resolve_services

    org = "org1"
    db = _DB([
        {"id": "a", "organization_id": org, "name": "A", "duration": 30, "price": 100},
        {"id": "b", "organization_id": org, "name": "B", "duration": 20, "price": 50},
    ])
    appt = SimpleNamespace(service_id="a", service_ids=["a", "b"])

    snap, dur, price, merged, ids = await resolve_services(db, org, appt, multi_enabled=True)
    assert ids == ["a", "b"]
    assert dur == 50
    assert price == 150.0


@pytest.mark.asyncio
async def test_conflicting_service_id_and_ids_still_rejected():
    """Gerçek çelişki: service_id listede yok -> 400 korunmalı."""
    from server import resolve_services

    org = "org1"
    db = _DB([
        {"id": "a", "organization_id": org, "name": "A", "duration": 30, "price": 100},
        {"id": "b", "organization_id": org, "name": "B", "duration": 20, "price": 50},
    ])
    appt = SimpleNamespace(service_id="b", service_ids=["a"])

    with pytest.raises(HTTPException) as exc:
        await resolve_services(db, org, appt, multi_enabled=True)
    assert exc.value.status_code == 400
