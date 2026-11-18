"""A service still stored as online/deposit must book as pay-at-salon while payments are paused,
or the appointment sticks in "Ödeme Bekleniyor" with no checkout possible."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from .test_public_booking_service_resolution import _DB


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["online", "deposit"])
async def test_resolve_services_reads_stored_online_rule_as_on_site(monkeypatch, rule):
    from server import resolve_services

    monkeypatch.setenv("MERCHANT_PAYMENTS_PAUSED", "true")
    db = _DB([{"id": "s1", "organization_id": "org1", "name": "Saç", "duration": 30, "price": 900,
               "payment_rule": rule, "deposit_amount": 200}])
    _, _, _, merged, _ = await resolve_services(db, "org1", SimpleNamespace(service_id="s1", service_ids=None),
                                                multi_enabled=True)
    assert merged["payment_rule"] == "on_site"


@pytest.mark.asyncio
async def test_resolve_services_keeps_rule_when_not_paused(monkeypatch):
    from server import resolve_services

    monkeypatch.setenv("MERCHANT_PAYMENTS_PAUSED", "false")
    db = _DB([{"id": "s1", "organization_id": "org1", "name": "Saç", "duration": 30, "price": 900,
               "payment_rule": "online"}])
    _, _, _, merged, _ = await resolve_services(db, "org1", SimpleNamespace(service_id="s1", service_ids=None),
                                                multi_enabled=True)
    assert merged["payment_rule"] == "online"
