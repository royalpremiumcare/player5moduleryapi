"""
TestClient (httpx ASGI) + mock DB / Redis.
server import öncesi stub_imports uygulanır.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# JWT ve env (get_current_user / SECRET_KEY)
os.environ.setdefault("JWT_SECRET_KEY", "integration-test-secret-key-32chars!!")
os.environ.setdefault("MONGO_URL", "")
os.environ.setdefault("DB_NAME", "test_integration")

from .stub_imports import apply as stub_heavy_imports

stub_heavy_imports()

from httpx import ASGITransport, AsyncClient

from server import app, get_current_user
from server import UserInDB

from .mocks import FakeRedis, IntegrationDB


@pytest.fixture
def org_id():
    return "org_test_integration"


@pytest.fixture
def test_user(org_id) -> UserInDB:
    return UserInDB(
        username="admin_integration",
        organization_id=org_id,
        role="admin",
        full_name="Integration Admin",
        permitted_service_ids=["svc1"],
        can_view_all_appointments=True,
    )


@pytest.fixture
def integration_db(org_id) -> IntegrationDB:
    return IntegrationDB(org_id)


@pytest_asyncio.fixture
async def integration_client(test_user, integration_db, monkeypatch):
    """Mock DB, Redis, yan etkiler; gerçek ASGI uygulaması."""

    async def override_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_user

    redis = FakeRedis()
    app.state.redis_client = redis
    integration_db.organization_id = test_user.organization_id
    integration_db.services._doc["organization_id"] = test_user.organization_id
    app.db = integration_db

    async def fake_get_db_from_request(request):
        request.app.db = integration_db
        return integration_db

    import server

    monkeypatch.setattr(server, "get_db_from_request", fake_get_db_from_request)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(server, "invalidate_cache", noop)
    monkeypatch.setattr(server, "emit_to_organization", noop)
    monkeypatch.setattr(server, "create_audit_log", noop)

    import operation_audit

    monkeypatch.setattr(operation_audit, "log_operation_audit", AsyncMock())

    async def quota_ok(*a, **k):
        return True, ""

    monkeypatch.setattr(server, "check_quota_and_increment", quota_ok)

    def fake_create_task(coro):
        coro.close()
        return MagicMock()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    # httpx<0.28: ASGITransport'ta lifespan yok; startup Mongo bağlantısı yoksa sorun çıkmaz.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, redis, integration_db

    app.dependency_overrides.clear()


@pytest.fixture
def bulk_session_body():
    return {
        "customer_name": "Int Test",
        "phone": "905551234567",
        "service_id": "svc1",
        "staff_member_id": None,
        "notes": "",
        "session_group_id": "grp_integration_1",
        "starting_session_number": 2,
        "session_total": 4,
        "sessions": [{"date": "2026-09-01", "time": "10:00"}],
    }
