"""Merchant payments are paused (2026-11-18): PLANN may not hold money on behalf of businesses.

While paused no new online payment can start, and services can only be pay-at-salon, even when an
old app build sends an online / deposit rule.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from financial import payments_pause
from financial.financial_endpoints import _require_admin, router


@pytest.mark.parametrize("value,expected", [
    (None, True), ("", True), ("true", True), ("1", True), ("yes", True),
    ("false", False), ("0", False), ("no", False), ("FALSE", False),
])
def test_paused_by_default_and_switchable(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("MERCHANT_PAYMENTS_PAUSED", raising=False)
    else:
        monkeypatch.setenv("MERCHANT_PAYMENTS_PAUSED", value)
    assert payments_pause.payments_paused() is expected


@pytest.mark.parametrize("rule,deposit", [("online", None), ("deposit", 250.0)])
def test_online_rules_become_pay_at_salon_while_paused(rule, deposit):
    assert payments_pause.coerce_payment_rule(rule, deposit, paused=True) == ("on_site", None)


def test_rules_untouched_when_not_paused_or_already_on_site():
    assert payments_pause.coerce_payment_rule("deposit", 250.0, paused=False) == ("deposit", 250.0)
    assert payments_pause.coerce_payment_rule("on_site", None, paused=True) == ("on_site", None)
    assert payments_pause.coerce_payment_rule(None, None, paused=True) == (None, None)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MERCHANT_PAYMENTS_PAUSED", "true")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_require_admin] = lambda: None
    return TestClient(app)


def test_public_checkout_refused_while_paused(client):
    resp = client.post("/api/public/checkout", json={
        "organization_id": "org", "service_id": "svc", "appointment_id": "apt",
        "customer_phone": "905551112233",
    })
    assert resp.status_code == 403
    assert resp.json()["detail"] == payments_pause.PAUSED_DETAIL


def test_payment_link_refused_while_paused(client):
    resp = client.post("/api/merchant/payment-links", json={
        "customer_phone": "905551112233", "customer_name": "Ayşe", "description": "Boya", "amount": 500,
    })
    assert resp.status_code == 403
    assert resp.json()["detail"] == payments_pause.PAUSED_DETAIL


@pytest.mark.parametrize("rule", ["online", "deposit", "full_online"])
def test_stored_online_rules_read_as_pay_at_salon_while_paused(rule):
    assert payments_pause.effective_payment_rule(rule, paused=True) == "on_site"
    assert payments_pause.effective_payment_rule(rule, paused=False) == rule
    assert payments_pause.effective_payment_rule(None, paused=True) is None
