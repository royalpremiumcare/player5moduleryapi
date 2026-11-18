import logging

import pytest
from pymongo.errors import DuplicateKeyError, OperationFailure

from customer_indexes import INDEX_NAME, ensure_customer_indexes

KEYS = [("organization_id", 1), ("phone_key", 1)]
PARTIAL = {"phone_key": {"$exists": True}}


class _Customers:
    def __init__(self, info=None, error=None):
        self.calls = []
        self.info = info or {}
        self.error = error

    async def index_information(self):
        return self.info

    async def create_index(self, keys, **kw):
        self.calls.append((list(keys), kw))
        if self.error:
            raise self.error
        return kw.get("name")


class _DB:
    def __init__(self, customers):
        self.customers = customers


def _exact_info():
    return {INDEX_NAME: {"key": KEYS, "unique": True, "partialFilterExpression": PARTIAL}}


async def test_partial_index_spec_exact():
    c = _Customers()
    assert await ensure_customer_indexes(_DB(c)) == "created"
    assert c.calls == [(KEYS, {"name": "customers_org_phone_key_unique", "unique": True,
                               "partialFilterExpression": PARTIAL})]


async def test_no_plain_unique_attempt():
    c = _Customers()
    await ensure_customer_indexes(_DB(c))
    for keys, kw in c.calls:
        assert not (kw.get("unique") and keys == [("organization_id", 1), ("phone", 1)])


async def test_existing_exact_index_returns_exists_without_create():
    c = _Customers(info=_exact_info())
    assert await ensure_customer_indexes(_DB(c)) == "exists"
    assert c.calls == []


@pytest.mark.parametrize("err", [
    DuplicateKeyError("E11000 dup"),
    OperationFailure("E11000 dup", code=11000),
])
async def test_duplicate_keys_logged_not_raised(err, caplog):
    c = _Customers(error=err)
    with caplog.at_level(logging.WARNING):
        assert await ensure_customer_indexes(_DB(c)) == "skipped_duplicates"
    recs = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(recs) == 1 and INDEX_NAME in recs[0].getMessage()


async def test_spec_conflict_with_exact_existing_is_exists():
    c = _Customers(error=OperationFailure("conflict", code=85))
    # index appears only after the race: first info empty, then exact
    infos = [{}, _exact_info()]

    async def info():
        return infos.pop(0) if len(infos) > 1 else infos[0]

    c.index_information = info
    assert await ensure_customer_indexes(_DB(c)) == "exists"


async def test_spec_conflict_with_different_spec_logs_error_not_raised(caplog):
    other = {INDEX_NAME: {"key": KEYS, "unique": True}}
    c = _Customers(info=other, error=OperationFailure("conflict", code=86))
    with caplog.at_level(logging.ERROR):
        assert await ensure_customer_indexes(_DB(c)) == "skipped_duplicates"
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_unexpected_error_never_raises(caplog):
    c = _Customers(error=RuntimeError("boom"))
    with caplog.at_level(logging.ERROR):
        assert await ensure_customer_indexes(_DB(c)) == "skipped_duplicates"
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_server_startup_wiring():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "server.py").read_text(encoding="utf-8")
    assert "customers_org_phone_unique" not in src
    assert "ensure_customer_indexes" in src
    assert "customers_org_phone_nonunique" in src
