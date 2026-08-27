"""Faz 5 — login intercept.

Sözleşme: 401 gövdesindeki `detail` metni sabit kalır (sahadaki donmuş mobil
build'ler onu gösteriyor). `code` yalnızca additive bir alandır ve hesabın hiç
bulunmadığı durumda, IP başına ifşa bütçesi dolmamışsa eklenir.
"""
from __future__ import annotations

import pytest

import server
from server import UserInDB

LOGIN_DETAIL = "Incorrect username or password"


class _FakeRequest:
    """`_may_disclose_unknown_account` için minimal Request ikamesi."""

    def __init__(self, app, ip="203.0.113.7"):
        self.app = app
        self.headers = {"X-Forwarded-For": ip}
        self.client = None


class _App:
    def __init__(self, redis_client=None):
        self.state = type("S", (), {"redis_client": redis_client})()


# ── Yanıt şekli ───────────────────────────────────────────────────────────


def test_failure_response_detail_is_frozen():
    body = server._login_failure_response().body.decode()
    assert LOGIN_DETAIL in body
    assert "code" not in body


def test_failure_response_adds_code_additively():
    import json

    payload = json.loads(server._login_failure_response("USER_NOT_FOUND").body)
    assert payload["detail"] == LOGIN_DETAIL
    assert payload["code"] == "USER_NOT_FOUND"


def test_failure_response_keeps_www_authenticate_header():
    resp = server._login_failure_response("USER_NOT_FOUND")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


# ── İfşa bütçesi ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disclosure_budget_exhausts_then_stays_closed():
    from tests.integration.mocks import FakeRedis

    request = _FakeRequest(_App(FakeRedis()))

    allowed = 0
    for _ in range(server.LOGIN_DISCLOSE_LIMIT + 5):
        if await server._may_disclose_unknown_account(request):
            allowed += 1

    assert allowed == server.LOGIN_DISCLOSE_LIMIT


@pytest.mark.asyncio
async def test_disclosure_budget_is_per_ip():
    from tests.integration.mocks import FakeRedis

    app = _App(FakeRedis())
    for _ in range(server.LOGIN_DISCLOSE_LIMIT):
        await server._may_disclose_unknown_account(_FakeRequest(app, ip="198.51.100.1"))

    # Bütçesi tükenen IP başkasını etkilemez.
    assert await server._may_disclose_unknown_account(_FakeRequest(app, ip="198.51.100.2")) is True


@pytest.mark.asyncio
async def test_no_redis_means_no_disclosure():
    """Fail-closed: Redis yoksa hesabın yokluğu açıklanmaz."""
    assert await server._may_disclose_unknown_account(_FakeRequest(_App(None))) is False


@pytest.mark.asyncio
async def test_redis_error_means_no_disclosure():
    class BrokenRedis:
        async def incr(self, *a, **k):
            raise RuntimeError("redis down")

    assert await server._may_disclose_unknown_account(_FakeRequest(_App(BrokenRedis()))) is False


# ── Endpoint davranışı ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_account_returns_code(integration_client, monkeypatch):
    client, _redis, _db = integration_client

    async def no_user(*a, **k):
        return None

    monkeypatch.setattr(server, "get_user_from_db", no_user)

    resp = await client.post(
        "/api/token",
        data={"username": "yok@example.com", "password": "whatever"},
    )

    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"] == LOGIN_DETAIL
    assert body["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_wrong_password_never_reveals_account(integration_client, monkeypatch):
    """Hesap VAR ama şifre yanlış → `code` yok, mesaj genel."""
    client, _redis, _db = integration_client

    async def existing_user(*a, **k):
        return UserInDB(
            username="var@example.com",
            organization_id="org_test_integration",
            role="admin",
            hashed_password="$2b$12$notarealhashvalueusedfortests",
        )

    monkeypatch.setattr(server, "get_user_from_db", existing_user)
    monkeypatch.setattr(server, "verify_password", lambda *a, **k: False)

    resp = await client.post(
        "/api/token",
        data={"username": "var@example.com", "password": "yanlis"},
    )

    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"] == LOGIN_DETAIL
    assert "code" not in body
