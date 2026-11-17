import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from live_activity import endpoints, widget_keys
from tests.live_activity_fakes import CountingRedis, DownRedis, FakeDB
from tests.test_live_activity_endpoints import NOW, ORG, apt, user_doc

HEADER = "X-Plann-Widget-Key"
T0 = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def env(monkeypatch):
    """Real dependencies (no overrides): JWT 'valid' resolves ali's stored user row."""
    db = FakeDB()
    run(widget_keys.ensure_indexes(db))
    db.settings.docs.append({"organization_id": ORG, "live_activity_enabled": True})
    db.users.docs.append(user_doc("ali"))
    db.appointments.docs.append(apt("a1", "11:00"))

    async def load_user(_request, username, db_):
        """Stands in for server.get_user_from_db: the one loader both auth paths share
        (UserInDB defaults: role admin, status active, a default organization_id)."""
        doc = await db_.users.find_one({"username": username}, {"_id": 0})
        return None if doc is None else {"role": "admin", "status": "active", "organization_id": "default-org", **doc}

    async def get_current_user(request, token, db_):
        if token != "valid":
            raise endpoints._unauthorized()
        return await load_user(request, "ali", db_)

    async def get_db(_request):
        return db

    endpoints.configure(get_current_user, get_db, get_user_by_username=load_user)
    monkeypatch.setattr(endpoints, "_now", lambda: NOW)
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api")
    app.state.redis_client = None
    client = TestClient(app)
    return SimpleNamespace(db=db, client=client, app=app, jwt={"Authorization": "Bearer valid"})


def issue(env):
    resp = env.client.post("/api/widget/key", headers=env.jwt)
    assert resp.status_code == 200
    return resp.json()["key"]


def get_summary(env, key):
    return env.client.get("/api/widget/summary", headers={HEADER: key})


def test_issue_returns_raw_key_and_stores_only_hash(env):
    body = env.client.post("/api/widget/key", headers=env.jwt).json()
    raw = body["key"]
    assert len(raw) >= 43 and datetime.fromisoformat(body["expires_at"])
    (row,) = env.db.widget_keys.docs
    assert row["key_hash"] == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in repr(row)
    assert row["username"] == "ali" and row["organization_id"] == ORG
    ttl = row["expires_at"] - row["created_at"]
    assert ttl == timedelta(days=90)


def test_sixth_key_revokes_oldest(env):
    keys = []
    for i in range(6):
        raw, _ = run(widget_keys.issue_key(env.db, {"username": "ali", "organization_id": ORG},
                                           now=T0 + timedelta(minutes=i)))
        keys.append(raw)
    assert len(env.db.widget_keys.docs) == 5
    assert run(widget_keys.resolve(env.db, keys[0], now=T0 + timedelta(hours=1))) is None
    assert run(widget_keys.resolve(env.db, keys[5], now=T0 + timedelta(hours=1))) is not None


def test_summary_with_valid_key_200_and_same_body_as_jwt(env):
    key = issue(env)
    via_key = get_summary(env, key)
    via_jwt = env.client.get("/api/widget/summary", headers=env.jwt)
    assert via_key.status_code == 200 and via_key.json() == via_jwt.json()
    assert via_key.json()["items"]


def test_unknown_revoked_expired_key_401(env):
    assert get_summary(env, "nope").status_code == 401
    key = issue(env)
    assert env.client.request("DELETE", "/api/widget/key", headers=env.jwt, json={"key": key}).status_code == 204
    assert get_summary(env, key).status_code == 401
    key2 = issue(env)
    env.db.widget_keys.docs[0]["expires_at"] = NOW - timedelta(seconds=1)
    assert get_summary(env, key2).status_code == 401


@pytest.mark.parametrize("change", ["deleted", "inactive"])
def test_deleted_or_inactive_user_key_401(env, change):
    key = issue(env)
    assert get_summary(env, key).status_code == 200
    if change == "deleted":
        env.db.users.docs.clear()
    else:
        env.db.users.docs[0]["status"] = "inactive"
    assert get_summary(env, key).status_code == 401


def test_key_rejected_on_other_endpoints(env):
    key = issue(env)
    h = {HEADER: key}
    assert env.client.get("/api/live-activities/preferences", headers=h).status_code == 401
    assert env.client.post("/api/live-activities/devices", headers=h, json={
        "device_id": "d1", "os_version": "18", "app_build": "1", "activities_enabled": True}).status_code == 401
    assert env.client.post("/api/live-activities/reconcile", headers=h,
                           json={"device_id": "d1", "activities_enabled": True, "complete": True}).status_code == 401
    assert env.client.post("/api/widget/key", headers=h).status_code == 401


def test_rate_limit_429_after_120_in_hour(env):
    redis = CountingRedis()
    env.app.state.redis_client = redis
    key = issue(env)
    for _ in range(120):
        assert get_summary(env, key).status_code == 200
    assert get_summary(env, key).status_code == 429
    (rl_key,) = redis.counts
    assert rl_key.startswith("widget_rl:") and rl_key.endswith(":2026111610")
    assert redis.expiries[rl_key] == 3700


def test_rate_limit_allows_when_redis_down(env):
    env.app.state.redis_client = DownRedis()
    key = issue(env)
    assert get_summary(env, key).status_code == 200
    assert run(widget_keys.within_rate_limit(None, "h", now=NOW)) is True
    assert run(widget_keys.within_rate_limit(DownRedis(), "h", now=NOW)) is True


def test_last_used_updated_at_most_every_10_min(env):
    key = issue(env)
    row = env.db.widget_keys.docs[0]
    first = run(widget_keys.resolve(env.db, key, now=T0))
    stamp = row["last_used_at"]
    assert stamp == T0 and first is not None
    run(widget_keys.resolve(env.db, key, now=T0 + timedelta(minutes=9)))
    assert row["last_used_at"] == T0
    run(widget_keys.resolve(env.db, key, now=T0 + timedelta(minutes=11)))
    assert row["last_used_at"] == T0 + timedelta(minutes=11)


def test_delete_without_key_revokes_all_for_user(env):
    k1, k2 = issue(env), issue(env)
    env.db.widget_keys.docs.append({"key_hash": "other", "username": "veli", "organization_id": ORG,
                                    "expires_at": NOW + timedelta(days=1)})
    assert env.client.request("DELETE", "/api/widget/key", headers=env.jwt).status_code == 204
    assert get_summary(env, k1).status_code == 401 and get_summary(env, k2).status_code == 401
    assert [d["username"] for d in env.db.widget_keys.docs] == ["veli"]


def test_key_path_normalises_user_like_jwt_path(env):
    del env.db.users.docs[0]["role"]  # legacy row: the loader defaults it to admin
    key = issue(env)
    via_key = get_summary(env, key)
    via_jwt = env.client.get("/api/widget/summary", headers=env.jwt)
    assert via_key.status_code == 200
    assert via_key.json() == via_jwt.json()
    assert [i["id"] for i in via_key.json()["items"]] == ["a1"]


def test_key_for_other_organization_row_401(env):
    key = issue(env)
    env.db.widget_keys.docs[0]["organization_id"] = "org-elsewhere"
    assert get_summary(env, key).status_code == 401


def test_summary_with_key_when_org_live_activity_flag_off(env):
    env.db.settings.docs[0]["live_activity_enabled"] = False
    assert get_summary(env, issue(env)).status_code == 200
    env.db.settings.docs.clear()
    assert get_summary(env, issue(env)).status_code == 200


def test_ensure_indexes_unique_key_hash_and_ttl(env):
    created = [e for e in env.db.log if e[0] == "widget_keys" and e[1] == "create_index"]
    assert ["key_hash"] in env.db.widget_keys.unique
    assert any(a[0] == "expires_at" and a[1].get("expireAfterSeconds") == 0 for _, _, a in created)


def test_rate_limit_counter_always_gets_expiry():
    redis = CountingRedis()
    run(widget_keys.within_rate_limit(redis, "h", now=NOW))
    run(widget_keys.within_rate_limit(redis, "h", now=NOW))
    assert redis.expiries["widget_rl:h:2026111610"] == 3700 and len(redis.expire_calls) == 2


def test_eviction_tiebreak_on_id_when_created_at_equal(env):
    user = {"username": "ali", "organization_id": ORG}
    keys = [run(widget_keys.issue_key(env.db, user, now=T0))[0] for _ in range(6)]
    assert run(widget_keys.resolve(env.db, keys[0], now=T0)) is None
    assert all(run(widget_keys.resolve(env.db, k, now=T0)) for k in keys[1:])
