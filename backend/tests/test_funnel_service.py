"""
funnel_service unit tests — ownership enforcement + idempotent ledger insert.

Gerçek MongoDB istemez: `db.funnel_events.insert_one` AsyncMock ile mocklanır.
Duplicate-key durumunu simüle etmek için `E11000` mesajlı Exception fırlatılır.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from funnel_service import record_funnel_event, track_webhook_event


def _make_db(insert_side_effect=None):
    """Minimum Motor-ish mock: db.funnel_events.insert_one AsyncMock."""
    db = MagicMock()
    db.funnel_events = MagicMock()
    db.funnel_events.insert_one = AsyncMock(side_effect=insert_side_effect)
    return db


# ---------------------------------------------------------------------------
# record_funnel_event — frontend-owned events only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_frontend_event_inserts_into_ledger():
    db = _make_db()
    ok = await record_funnel_event(
        db,
        event_name="aha_appointment_created",
        insert_id="abc123456",
        distinct_id="user-uuid",
        organization_id="org-1",
        user_id="user-uuid",
        properties={"wa_status": "ok"},
    )
    assert ok is True
    db.funnel_events.insert_one.assert_awaited_once()
    doc = db.funnel_events.insert_one.await_args.args[0]
    assert doc["event_name"] == "aha_appointment_created"
    assert doc["owner"] == "frontend"
    assert doc["insert_id"] == "abc123456"
    assert doc["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_record_rejects_webhook_owned_event():
    """Frontend endpoint'i subscription_completed yazamamalı."""
    db = _make_db()
    ok = await record_funnel_event(
        db,
        event_name="subscription_completed",
        insert_id="x" * 10,
        distinct_id="user-uuid",
        organization_id="org-1",
        user_id="user-uuid",
    )
    assert ok is False
    db.funnel_events.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_rejects_unknown_event():
    db = _make_db()
    ok = await record_funnel_event(
        db,
        event_name="totally_made_up",
        insert_id="x" * 10,
        distinct_id="u",
        organization_id="o",
        user_id="u",
    )
    assert ok is False
    db.funnel_events.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_duplicate_key_returns_true():
    """E11000 dup key → idempotent başarı (no-op)."""
    dup_exc = Exception("E11000 duplicate key error collection: funnel_events")
    db = _make_db(insert_side_effect=dup_exc)
    ok = await record_funnel_event(
        db,
        event_name="signup_completed",
        insert_id="same-insert-id",
        distinct_id="u",
        organization_id="o",
        user_id="u",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_record_non_dup_error_returns_false():
    """Genel DB hatası → False."""
    db = _make_db(insert_side_effect=RuntimeError("connection refused"))
    ok = await record_funnel_event(
        db,
        event_name="signup_completed",
        insert_id="unique-id-xyz",
        distinct_id="u",
        organization_id="o",
        user_id="u",
    )
    assert ok is False


# ---------------------------------------------------------------------------
# track_webhook_event — webhook-owned events only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_webhook_event_inserts_ledger_with_owner_webhook():
    db = _make_db()
    ok = await track_webhook_event(
        db,
        event_name="subscription_completed",
        distinct_id="user-uuid",
        organization_id="org-1",
        user_id="user-uuid",
        insert_id="stripe_evt_123",
        properties={"plan_id": "pro"},
    )
    assert ok is True
    db.funnel_events.insert_one.assert_awaited_once()
    doc = db.funnel_events.insert_one.await_args.args[0]
    assert doc["event_name"] == "subscription_completed"
    assert doc["owner"] == "webhook"
    assert doc["insert_id"] == "stripe_evt_123"
    assert doc["source"] == "webhook"


@pytest.mark.asyncio
async def test_track_webhook_rejects_frontend_owned_event():
    """Backend 'aha_appointment_created' emit edemez (frontend owned)."""
    db = _make_db()
    ok = await track_webhook_event(
        db,
        event_name="aha_appointment_created",
        distinct_id="u",
        organization_id="o",
        user_id="u",
    )
    assert ok is False
    db.funnel_events.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_webhook_duplicate_key_is_idempotent():
    dup_exc = Exception("E11000 duplicate key")
    db = _make_db(insert_side_effect=dup_exc)
    ok = await track_webhook_event(
        db,
        event_name="subscription_completed",
        distinct_id="u",
        organization_id="o",
        user_id="u",
        insert_id="stripe_evt_same",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_track_webhook_auto_generates_insert_id_when_missing():
    """insert_id verilmezse UUID üretilir ve doc'a yazılır."""
    db = _make_db()
    ok = await track_webhook_event(
        db,
        event_name="subscription_completed",
        distinct_id="u",
        organization_id="o",
        user_id="u",
    )
    assert ok is True
    doc = db.funnel_events.insert_one.await_args.args[0]
    assert isinstance(doc["insert_id"], str)
    assert len(doc["insert_id"]) >= 10
