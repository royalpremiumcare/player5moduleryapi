"""
Tests for financial.wise_service.prepare_batch_group — Wednesday batch preparation.

Mocks Wise HTTP calls to avoid network dependency.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from financial import wise_service


class FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, q):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return d
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return MagicMock(inserted_id=doc.get("id"))


class FakeDB:
    def __init__(self, settings_doc=None):
        self.settings = FakeColl([settings_doc] if settings_doc else [])
        self.wise_quotes = FakeColl()


@pytest.fixture
def gbp_batch():
    return {
        "id": "batch_test_gbp",
        "organization_id": "org_gbp",
        "base_currency": "GBP",
        "total_amount_minor": 50000,  # £500
        "item_transaction_ids": ["tx1", "tx2", "tx3"],
    }


@pytest.fixture
def try_batch():
    return {
        "id": "batch_test_try",
        "organization_id": "org_try",
        "base_currency": "TRY",
        "total_amount_minor": 1200000,  # ₺12,000
        "item_transaction_ids": ["tx_a", "tx_b"],
    }


@pytest.fixture
def gbp_db(gbp_batch):
    return FakeDB(settings_doc={
        "organization_id": "org_gbp",
        "base_currency": "GBP",
        "wise_recipient_id": "99988877",
        "company_name": "UK Test Shop",
    })


@pytest.fixture
def try_db():
    return FakeDB(settings_doc={
        "organization_id": "org_try",
        "base_currency": "TRY",
        "wise_recipient_id": "11122233",
        "company_name": "TR Test Kuaför",
    })


# ---------------------------------------------------------------------------
# Happy path — GBP (no conversion)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_batch_gbp_source_amount_used(gbp_db, gbp_batch, monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")

    fake_quote = {
        "quote_doc": {"wise_quote_id": "q_abc123"},
        "wise_quote_data": {"id": "q_abc123"},
    }
    fake_transfer = {"id": 777000, "status": "incoming_payment_waiting"}

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)) as cq, \
         patch.object(wise_service, "create_single_transfer", new=AsyncMock(return_value=fake_transfer)) as ct:

        result = await wise_service.prepare_batch_group(gbp_db, gbp_batch)

        # GBP merchant → source_amount used (target_amount = 0)
        call_kwargs = cq.call_args.kwargs
        assert call_kwargs["source_currency"] == "GBP"
        assert call_kwargs["target_currency"] == "GBP"
        assert call_kwargs["source_amount_minor"] == 50000
        assert call_kwargs["target_amount_minor"] == 0
        assert call_kwargs["payout_batch_id"] == "batch_test_gbp"

        # Single transfer (not batch group)
        t_kwargs = ct.call_args.kwargs
        assert t_kwargs["quote_id"] == "q_abc123"
        assert t_kwargs["recipient_id"] == "99988877"
        # Wise requires a plain UUID for customerTransactionId (no prefix)
        assert t_kwargs["customer_transaction_id"] == "batch_test_gbp"

        assert result["wise_quote_id"] == "q_abc123"
        assert result["wise_transfer_id"] == "777000"
        assert result["wise_batch_group_id"] is None
        assert result["target_currency"] == "GBP"
        assert result["total_amount_minor"] == 50000
        assert result["transfer_status"] == "incoming_payment_waiting"


# ---------------------------------------------------------------------------
# Happy path — TRY (cross-border, target_amount locks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_batch_try_target_amount_used(try_db, try_batch, monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")

    fake_quote = {
        "quote_doc": {"wise_quote_id": "q_try_999"},
        "wise_quote_data": {"id": "q_try_999"},
    }
    fake_transfer = {"id": 888000, "status": "incoming_payment_waiting"}

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)) as cq, \
         patch.object(wise_service, "create_single_transfer", new=AsyncMock(return_value=fake_transfer)):

        result = await wise_service.prepare_batch_group(try_db, try_batch)

        # TRY merchant → target_amount used (source_amount = 0, Wise computes GBP)
        call_kwargs = cq.call_args.kwargs
        assert call_kwargs["source_currency"] == "GBP"
        assert call_kwargs["target_currency"] == "TRY"
        assert call_kwargs["source_amount_minor"] == 0
        assert call_kwargs["target_amount_minor"] == 1200000

        assert result["target_currency"] == "TRY"
        assert result["total_amount_minor"] == 1200000


# ---------------------------------------------------------------------------
# Batch group flow (production-style)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_batch_uses_batch_group_when_enabled(gbp_db, gbp_batch, monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "true")

    fake_quote = {"quote_doc": {"wise_quote_id": "q_bg"}, "wise_quote_data": {"id": "q_bg"}}
    fake_bg = {"id": "bg_12345", "version": 0}
    fake_transfer = {"id": "t_99", "status": "incoming_payment_waiting"}
    fake_bg_latest = {"id": "bg_12345", "version": 1}

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)), \
         patch.object(wise_service, "create_batch_group", new=AsyncMock(return_value=fake_bg)) as cbg, \
         patch.object(wise_service, "add_transfer_to_batch", new=AsyncMock(return_value=fake_transfer)) as atb, \
         patch.object(wise_service, "get_batch_group", new=AsyncMock(return_value=fake_bg_latest)), \
         patch.object(wise_service, "complete_batch_group", new=AsyncMock(return_value={"version": 2})) as cmp_bg:

        result = await wise_service.prepare_batch_group(gbp_db, gbp_batch)

        cbg.assert_called_once()
        atb.assert_called_once()
        cmp_bg.assert_called_once()
        # complete is called with latest version (either positional or kwarg)
        call = cmp_bg.call_args
        version_value = call.kwargs.get("version") if "version" in call.kwargs else (call.args[1] if len(call.args) > 1 else None)
        assert version_value == 1

        assert result["wise_batch_group_id"] == "bg_12345"
        assert result["wise_transfer_id"] == "t_99"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_recipient_raises():
    db = FakeDB(settings_doc={
        "organization_id": "org_no_recipient",
        "base_currency": "GBP",
        # no wise_recipient_id
    })
    batch = {
        "id": "batch_bad",
        "organization_id": "org_no_recipient",
        "base_currency": "GBP",
        "total_amount_minor": 10000,
    }
    with pytest.raises(RuntimeError, match="wise_recipient_id missing"):
        await wise_service.prepare_batch_group(db, batch)


@pytest.mark.asyncio
async def test_zero_amount_raises(gbp_db):
    batch = {
        "id": "empty", "organization_id": "org_gbp",
        "base_currency": "GBP", "total_amount_minor": 0,
    }
    with pytest.raises(RuntimeError, match="no amount"):
        await wise_service.prepare_batch_group(gbp_db, batch)


@pytest.mark.asyncio
async def test_settings_not_found_raises():
    db = FakeDB(settings_doc=None)
    batch = {
        "id": "orphan", "organization_id": "org_unknown",
        "base_currency": "GBP", "total_amount_minor": 10000,
    }
    with pytest.raises(RuntimeError, match="settings not found"):
        await wise_service.prepare_batch_group(db, batch)


@pytest.mark.asyncio
async def test_quote_failure_wraps_runtime_error(gbp_db, gbp_batch, monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")

    async def boom(**kwargs):
        raise ConnectionError("Wise unreachable")

    with patch.object(wise_service, "create_quote", new=boom):
        with pytest.raises(RuntimeError, match="wise quote failed"):
            await wise_service.prepare_batch_group(gbp_db, gbp_batch)


@pytest.mark.asyncio
async def test_transfer_failure_wraps_runtime_error(gbp_db, gbp_batch, monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")

    fake_quote = {"quote_doc": {"wise_quote_id": "q_ok"}, "wise_quote_data": {"id": "q_ok"}}

    async def boom(**kwargs):
        raise ValueError("quote expired")

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)), \
         patch.object(wise_service, "create_single_transfer", new=boom):
        with pytest.raises(RuntimeError, match="wise transfer create failed"):
            await wise_service.prepare_batch_group(gbp_db, gbp_batch)


@pytest.mark.asyncio
async def test_empty_transfer_id_raises(gbp_db, gbp_batch, monkeypatch):
    """Wise must return an id; if it doesn't, we fail loudly."""
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")

    fake_quote = {"quote_doc": {"wise_quote_id": "q_ok"}, "wise_quote_data": {"id": "q_ok"}}
    fake_transfer = {"id": "", "status": "unknown"}  # malformed

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)), \
         patch.object(wise_service, "create_single_transfer", new=AsyncMock(return_value=fake_transfer)):
        with pytest.raises(RuntimeError, match="returned no id"):
            await wise_service.prepare_batch_group(gbp_db, gbp_batch)


# ---------------------------------------------------------------------------
# Reference truncation (Wise limit ~20 chars)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_long_company_name_is_truncated(monkeypatch):
    monkeypatch.setenv("WISE_USE_BATCH_GROUPS", "false")
    db = FakeDB(settings_doc={
        "organization_id": "org_long",
        "base_currency": "GBP",
        "wise_recipient_id": "42",
        "company_name": "A Very Long Company Name That Exceeds Wise Reference Limits",
    })
    batch = {
        "id": "b1", "organization_id": "org_long",
        "base_currency": "GBP", "total_amount_minor": 10000,
    }
    fake_quote = {"quote_doc": {"wise_quote_id": "q"}, "wise_quote_data": {"id": "q"}}
    fake_transfer = {"id": "t1", "status": "ok"}

    with patch.object(wise_service, "create_quote", new=AsyncMock(return_value=fake_quote)), \
         patch.object(wise_service, "create_single_transfer", new=AsyncMock(return_value=fake_transfer)) as ct:
        await wise_service.prepare_batch_group(db, batch)

        reference = ct.call_args.kwargs["reference"]
        assert len(reference) <= 18
        assert reference == "A Very Long Compan"
