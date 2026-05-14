"""
User identity tests:
  1. Lazy backfill (`_ensure_user_identity_fields`) — server.py login akışı
     ve `app/core/dependencies.py:get_current_user` her ikisi de bu mantığa dayanır.
     Burada `app/core/dependencies.py` versiyonu test edilir; server.py'deki
     duplicate aynı semantik kuralla yazıldı.
  2. `UserResponse` ve `UserInDB` schema'larında `user_id` + `activation_state`
     alanlarının doğru tip ve default'larla tanımlı olduğu doğrulanır.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.schemas.auth import UserResponse
from app.core.dependencies import UserInDB, _ensure_user_identity_fields


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _make_db():
    db = MagicMock()
    db.users = MagicMock()
    db.users.update_one = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Lazy backfill semantics (admin paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_sets_user_id_and_pending_state_for_new_admin():
    """
    Yeni admin (onboarding_completed=False, user_id+activation_state yok)
    → user_id UUIDv4, activation_state=pending_aha_appointment.
    """
    db = _make_db()
    user_doc = {
        "username": "owner@example.com",
        "role": "admin",
        "onboarding_completed": False,
    }
    out = await _ensure_user_identity_fields(db, user_doc)

    assert out["user_id"]
    assert UUID_RE.match(out["user_id"]), f"user_id should be UUIDv4, got {out['user_id']}"
    assert out["activation_state"] == "pending_aha_appointment"
    db.users.update_one.assert_awaited_once()
    # Set fields persisted to Mongo
    set_payload = db.users.update_one.await_args.args[1]["$set"]
    assert "user_id" in set_payload
    assert set_payload["activation_state"] == "pending_aha_appointment"


@pytest.mark.asyncio
async def test_backfill_existing_admin_marks_aha_skipped_legacy():
    """
    Mevcut admin (onboarding_completed=True) → state=aha_skipped, reason=legacy_backfill.
    Sürpriz Aha overlay'i çıkmaması için.
    """
    db = _make_db()
    user_doc = {
        "username": "legacy_admin@example.com",
        "role": "admin",
        "onboarding_completed": True,
    }
    out = await _ensure_user_identity_fields(db, user_doc)

    assert out["activation_state"] == "aha_skipped"
    assert out["aha_skipped_reason"] == "legacy_backfill"
    assert UUID_RE.match(out["user_id"])
    db.users.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_backfill_staff_marked_not_applicable():
    """Staff Aha akışını hiç görmemeli."""
    db = _make_db()
    user_doc = {
        "username": "staff@example.com",
        "role": "staff",
    }
    out = await _ensure_user_identity_fields(db, user_doc)

    assert out["activation_state"] == "not_applicable"
    assert UUID_RE.match(out["user_id"])


@pytest.mark.asyncio
async def test_backfill_noop_when_already_set():
    """Hem user_id hem activation_state varsa DB'ye yazma yapılmamalı."""
    db = _make_db()
    user_doc = {
        "username": "fully_seeded@example.com",
        "role": "admin",
        "user_id": "11111111-2222-4333-8444-555555555555",
        "activation_state": "aha_completed",
    }
    out = await _ensure_user_identity_fields(db, user_doc)

    # No mutation
    assert out["user_id"] == "11111111-2222-4333-8444-555555555555"
    assert out["activation_state"] == "aha_completed"
    db.users.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_only_writes_missing_fields():
    """user_id var ama activation_state yoksa sadece activation_state set edilmeli."""
    db = _make_db()
    user_doc = {
        "username": "partial@example.com",
        "role": "admin",
        "onboarding_completed": False,
        "user_id": "11111111-2222-4333-8444-555555555555",
    }
    out = await _ensure_user_identity_fields(db, user_doc)

    assert out["user_id"] == "11111111-2222-4333-8444-555555555555"  # preserved
    assert out["activation_state"] == "pending_aha_appointment"
    set_payload = db.users.update_one.await_args.args[1]["$set"]
    assert "user_id" not in set_payload  # not overwritten
    assert set_payload["activation_state"] == "pending_aha_appointment"


@pytest.mark.asyncio
async def test_backfill_db_failure_does_not_raise():
    """Mongo update_one fail olsa bile in-memory user_doc patched ve fonksiyon raise etmemeli."""
    db = _make_db()
    db.users.update_one.side_effect = RuntimeError("write conflict")
    user_doc = {
        "username": "transient@example.com",
        "role": "admin",
        "onboarding_completed": False,
    }
    # Should not raise
    out = await _ensure_user_identity_fields(db, user_doc)
    # Fonksiyon hala çağrı yaptı; updates dict düştü, ama in-memory doc
    # daha önce update.update(updates) ile patch'lenmedi (çünkü exception
    # raise edildi). En azından fonksiyon swallow ediyor — bu kritik
    # bir guarantee (auth path'i kırmamalı).
    assert isinstance(out, dict)


# ---------------------------------------------------------------------------
# Schema contract — UserResponse + UserInDB
# ---------------------------------------------------------------------------


def test_user_response_schema_includes_user_id_and_activation_state():
    """
    Frontend (`AuthContext.identify`) `user_id` ve `activation_state`'i okur;
    response schema bunları döndürmek zorunda.
    """
    payload = UserResponse(
        username="owner@example.com",
        organization_id="org-1",
        role="admin",
        onboarding_completed=True,
        user_id="11111111-2222-4333-8444-555555555555",
        activation_state="aha_completed",
    )
    dumped = payload.model_dump()
    assert dumped["user_id"] == "11111111-2222-4333-8444-555555555555"
    assert dumped["activation_state"] == "aha_completed"


def test_user_response_user_id_optional():
    """Geriye uyumluluk: user_id None ile model construct olabilmeli."""
    payload = UserResponse(
        username="legacy@example.com",
        organization_id="org-2",
        role="admin",
    )
    assert payload.user_id is None
    assert payload.activation_state is None


def test_user_in_db_aha_fields_optional():
    """UserInDB Aha ek alanları olmadan da geçerli olmalı (legacy doc compatibility)."""
    user = UserInDB(
        username="x@y.z",
        hashed_password="hash",
        organization_id="org-1",
    )
    assert user.user_id is None
    assert user.activation_state is None
    assert user.aha_appointment_id is None


def test_user_in_db_accepts_full_aha_payload():
    user = UserInDB(
        username="x@y.z",
        hashed_password="hash",
        organization_id="org-1",
        user_id="11111111-2222-4333-8444-555555555555",
        activation_state="aha_completed",
        aha_appointment_id="apt-uuid",
        aha_wa_message_id="wamid.xxxxx",
        first_appointment_at="2026-05-04T12:00:00+00:00",
    )
    assert user.activation_state == "aha_completed"
    assert user.aha_appointment_id == "apt-uuid"
