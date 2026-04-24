"""
Tests for financial.refund_requests — admin-approved refund workflow.

Uses a minimal in-memory DB fake to avoid motor dependency in unit tests.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import pytest

from financial.refund_requests import (
    SLA_HOURS,
    URGENT_DAILY_QUOTA_PER_ORG,
    create_refund_request,
    approve_refund_request,
    reject_refund_request,
    list_pending_for_admin,
    run_sla_monitor_cron,
)


# ---------------------------------------------------------------------------
# In-memory DB fake
# ---------------------------------------------------------------------------

class FakeCursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = list(items)

    def sort(self, field, direction=1):
        reverse = direction == -1
        self._items.sort(key=lambda d: (d.get(field) or ""), reverse=reverse)
        return self

    def limit(self, n):
        self._items = self._items[:n]
        return self

    async def to_list(self, n):
        return list(self._items[:n])

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc):
        # Simulate unique index on idempotency_key
        idem = doc.get("idempotency_key")
        if idem and any(d.get("idempotency_key") == idem for d in self.docs):
            raise Exception("E11000 duplicate key error")
        self.docs.append(dict(doc))
        return type("Res", (), {"inserted_id": doc.get("id")})

    async def find_one(self, q, projection=None):
        # projection ignored — fake docs don't have _id
        for d in self.docs:
            if self._match(d, q):
                return d
        return None

    def find(self, q, projection=None):
        # projection (e.g. {"_id": 0}) ignored in tests — fake docs don't have _id
        return FakeCursor([d for d in self.docs if self._match(d, q)])

    async def update_one(self, q, update):
        for d in self.docs:
            if self._match(d, q):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                return type("Res", (), {"modified_count": 1})
        return type("Res", (), {"modified_count": 0})

    async def count_documents(self, q):
        return sum(1 for d in self.docs if self._match(d, q))

    @staticmethod
    def _match(doc, q):
        for k, v in q.items():
            if isinstance(v, dict):
                if "$regex" in v:
                    if not re.search(v["$regex"], str(doc.get(k, "")), flags=re.I):
                        return False
                    continue
                if "$gte" in v:
                    if not (doc.get(k) and doc.get(k) >= v["$gte"]):
                        return False
                    continue
                if "$lt" in v:
                    if not (doc.get(k) and doc.get(k) < v["$lt"]):
                        return False
                    continue
                if "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
                    continue
                if "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                    continue
            else:
                if doc.get(k) != v:
                    return False
        return True


class FakeDB:
    def __init__(self):
        self.refund_requests = FakeCollection()
        self.merchant_transactions = FakeCollection()
        self.merchant_wallets = FakeCollection()
        self.refund_reconciliation_pending = FakeCollection()
        self.settings = FakeCollection()


@pytest.fixture
def db():
    return FakeDB()


async def _make_tx(db, *, amount=5000, state="available"):
    tx = {
        "id": str(uuid.uuid4()),
        "organization_id": "org1",
        "type": "payment",
        "state": state,
        "base_currency": "GBP",
        "amount_display_minor": amount,
        "customer_name": "Test Customer",
        "customer_phone": "+441234567890",
        "stripe_payment_intent_id": f"pi_test_{uuid.uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.merchant_transactions.insert_one(tx)
    return tx


@pytest.fixture
async def sample_tx(db):
    return await _make_tx(db)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_refund_request_valid(db, sample_tx):
    req = await create_refund_request(
        db,
        organization_id="org1",
        requested_by_user_id="user1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000,
        reason="Customer asked for cancellation",
        priority="normal",
    )
    assert req["status"] == "pending"
    assert req["priority"] == "normal"
    assert req["sla_deadline"] > req["created_at"]
    assert req["idempotency_key"]


@pytest.mark.asyncio
async def test_reason_required(db, sample_tx):
    with pytest.raises(ValueError):
        await create_refund_request(
            db, organization_id="org1", requested_by_user_id="u1",
            merchant_transaction_id=sample_tx["id"],
            refund_amount_minor=5000, reason="", priority="normal",
        )


@pytest.mark.asyncio
async def test_invalid_priority_raises(db, sample_tx):
    with pytest.raises(ValueError):
        await create_refund_request(
            db, organization_id="org1", requested_by_user_id="u1",
            merchant_transaction_id=sample_tx["id"],
            refund_amount_minor=5000, reason="bad", priority="super-urgent",
        )


@pytest.mark.asyncio
async def test_urgent_quota_downgrade(db):
    for i in range(URGENT_DAILY_QUOTA_PER_ORG):
        tx_i = await _make_tx(db)
        await create_refund_request(
            db, organization_id="org1", requested_by_user_id="u1",
            merchant_transaction_id=tx_i["id"],
            refund_amount_minor=5000, reason=f"urgent {i}", priority="urgent",
            idempotency_key=f"key{i}",
        )
    # Next urgent (on a new tx) should be downgraded
    tx_extra = await _make_tx(db)
    downgraded = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=tx_extra["id"],
        refund_amount_minor=5000, reason="too many", priority="urgent",
        idempotency_key="key_extra",
    )
    assert downgraded["priority"] == "high"
    assert downgraded["priority_requested"] == "urgent"


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate(db, sample_tx):
    idem = "my-fixed-key"
    r1 = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="once", priority="normal",
        idempotency_key=idem,
    )
    r2 = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="twice", priority="normal",
        idempotency_key=idem,
    )
    assert r1["id"] == r2["id"]
    # Only one doc in DB
    count = await db.refund_requests.count_documents({"organization_id": "org1"})
    assert count == 1


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_calls_stripe_and_marks_executed(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="okay please refund", priority="normal",
    )

    def fake_stripe(payment_intent_id, amount):
        assert payment_intent_id.startswith("pi_test_")
        assert amount == 5000
        return {"id": "re_abc123"}

    result = await approve_refund_request(
        db, request_id=req["id"], reviewer_id="admin1",
        stripe_refund_call=fake_stripe,
    )
    assert result["ok"] is True
    assert result["stripe_refund_id"] == "re_abc123"

    stored = await db.refund_requests.find_one({"id": req["id"]})
    assert stored["status"] == "executed"
    assert stored["stripe_refund_id"] == "re_abc123"
    assert stored["age_hours_at_review"] is not None


@pytest.mark.asyncio
async def test_approve_stripe_failure_marks_failed(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="okay please refund", priority="normal",
    )

    def fake_stripe(pi_id, amount):
        raise RuntimeError("stripe_down")

    result = await approve_refund_request(
        db, request_id=req["id"], reviewer_id="admin1",
        stripe_refund_call=fake_stripe,
    )
    assert result["ok"] is False
    stored = await db.refund_requests.find_one({"id": req["id"]})
    assert stored["status"] == "failed"


@pytest.mark.asyncio
async def test_reject_requires_reason(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="okay please refund", priority="normal",
    )
    r = await reject_refund_request(db, request_id=req["id"], reviewer_id="a", reason="")
    assert r["ok"] is False


@pytest.mark.asyncio
async def test_reject_valid(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="okay please refund", priority="normal",
    )
    r = await reject_refund_request(
        db, request_id=req["id"], reviewer_id="admin1",
        reason="Service was already delivered",
    )
    assert r["ok"] is True
    stored = await db.refund_requests.find_one({"id": req["id"]})
    assert stored["status"] == "rejected"


# ---------------------------------------------------------------------------
# SLA monitor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sla_monitor_escalates_overdue(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="old", priority="urgent",
    )
    # Force the SLA deadline into the past
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    await db.refund_requests.update_one({"id": req["id"]}, {"$set": {"sla_deadline": past}})

    result = await run_sla_monitor_cron(db)
    assert result["escalated"] == 1

    stored = await db.refund_requests.find_one({"id": req["id"]})
    assert stored["escalated"] is True


@pytest.mark.asyncio
async def test_sla_monitor_skips_non_pending(db, sample_tx):
    req = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=sample_tx["id"],
        refund_amount_minor=5000, reason="skip me", priority="urgent",
    )
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    await db.refund_requests.update_one(
        {"id": req["id"]}, {"$set": {"sla_deadline": past, "status": "executed"}},
    )

    result = await run_sla_monitor_cron(db)
    assert result["escalated"] == 0


@pytest.mark.asyncio
async def test_list_pending_sorted_by_sla_deadline(db):
    tx1 = await _make_tx(db)
    tx2 = await _make_tx(db)
    r1 = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=tx1["id"],
        refund_amount_minor=5000, reason="first request", priority="normal", idempotency_key="k1",
    )
    r2 = await create_refund_request(
        db, organization_id="org1", requested_by_user_id="u1",
        merchant_transaction_id=tx2["id"],
        refund_amount_minor=5000, reason="second request", priority="urgent", idempotency_key="k2",
    )
    items = await list_pending_for_admin(db)
    assert len(items) == 2
    # urgent (1h) should be first
    assert items[0]["priority"] == "urgent"
