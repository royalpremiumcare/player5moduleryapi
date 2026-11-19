import asyncio
import logging

import pytest

from financial import distributed_lock
from financial.distributed_lock import RELEASE_SCRIPT, with_distributed_lock


class LockRedis:
    """Minimal fake: set(nx, px), eval (compare-and-delete Lua), aclose."""

    def __init__(self):
        self.store = {}
        self.set_calls = []
        self.closed = False
        self.fail_set = False
        self.fail_eval = False
        self.hang_set = False
        self.hang_eval = False
        self.hang_close = False

    async def set(self, key, value, nx=False, px=None):
        self.set_calls.append((key, nx, px))
        if self.hang_set:
            await asyncio.sleep(3600)
        if self.fail_set:
            raise ConnectionError("redis down")
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def eval(self, script, numkeys, key, token):
        assert script == RELEASE_SCRIPT
        assert numkeys == 1
        if self.hang_eval:
            await asyncio.sleep(3600)
        if self.fail_eval:
            raise ConnectionError("redis down")
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def aclose(self):
        if self.hang_close:
            await asyncio.sleep(3600)
        self.closed = True


def factory_for(redis):
    return lambda: redis


async def test_second_concurrent_holder_is_refused():
    redis = LockRedis()
    results = []

    async def worker():
        async with with_distributed_lock(
            "job_a", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
        ) as acquired:
            results.append(acquired)
            await asyncio.sleep(0.05)

    await asyncio.gather(worker(), worker())
    assert sorted(results) == [False, True]
    assert redis.set_calls[0] == ("plann:lock:job_a", True, 60000)
    assert redis.store == {}


async def test_release_only_deletes_own_token():
    redis = LockRedis()
    async with with_distributed_lock(
        "job_b", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
    ) as acquired:
        assert acquired is True
        # TTL expiry then another holder takes over
        redis.store["plann:lock:job_b"] = "other-token"
    assert redis.store == {"plann:lock:job_b": "other-token"}


async def test_redis_down_fail_closed_skips(caplog):
    redis = LockRedis()
    redis.fail_set = True
    with caplog.at_level(logging.WARNING):
        async with with_distributed_lock(
            "job_c", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
        ) as acquired:
            assert acquired is False
    assert any(r.levelno == logging.WARNING and "job_c" in r.getMessage() for r in caplog.records)


async def test_redis_down_fail_open_runs():
    redis = LockRedis()
    redis.fail_set = True
    async with with_distributed_lock(
        "quote_cleanup", ttl=60, fail_closed=False, redis_factory=factory_for(redis)
    ) as acquired:
        assert acquired is True


async def test_release_error_never_raises(caplog):
    redis = LockRedis()
    with caplog.at_level(logging.WARNING):
        async with with_distributed_lock(
            "job_d", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
        ) as acquired:
            assert acquired is True
            redis.fail_eval = True
    assert any(r.levelno == logging.WARNING and "job_d" in r.getMessage() for r in caplog.records)
    assert redis.closed is True


@pytest.fixture
def short_timeout(monkeypatch):
    monkeypatch.setattr(distributed_lock, "REDIS_TIMEOUT", 0.05)


async def test_hung_acquire_fail_closed_skips(short_timeout):
    redis = LockRedis()
    redis.hang_set = True
    async with with_distributed_lock(
        "job_f", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
    ) as acquired:
        assert acquired is False


async def test_hung_acquire_fail_open_runs(short_timeout):
    redis = LockRedis()
    redis.hang_set = True
    async with with_distributed_lock(
        "quote_cleanup", ttl=60, fail_closed=False, redis_factory=factory_for(redis)
    ) as acquired:
        assert acquired is True


async def test_hung_release_never_raises_or_blocks(short_timeout, caplog):
    redis = LockRedis()
    with caplog.at_level(logging.WARNING):
        async with with_distributed_lock(
            "job_g", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
        ) as acquired:
            assert acquired is True
            redis.hang_eval = True
    assert any(r.levelno == logging.WARNING and "job_g" in r.getMessage() for r in caplog.records)


async def test_hung_close_never_raises_or_blocks(short_timeout):
    redis = LockRedis()
    redis.hang_close = True
    async with with_distributed_lock(
        "job_h", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
    ) as acquired:
        assert acquired is True


async def test_lock_released_after_body_exception():
    redis = LockRedis()
    with pytest.raises(ValueError):
        async with with_distributed_lock(
            "job_e", ttl=60, fail_closed=True, redis_factory=factory_for(redis)
        ):
            raise ValueError("boom")
    assert redis.store == {}
    assert redis.closed is True


async def test_hold_keeps_key_after_normal_exit():
    redis = LockRedis()
    async with with_distributed_lock("job", ttl=60, fail_closed=True, hold=True,
                                     redis_factory=factory_for(redis)) as acquired:
        assert acquired is True
    assert "plann:lock:job" in redis.store
    assert redis.closed is True


async def test_hold_keeps_key_when_body_raises_and_exception_propagates():
    redis = LockRedis()
    with pytest.raises(RuntimeError):
        async with with_distributed_lock("job", ttl=60, fail_closed=True, hold=True,
                                         redis_factory=factory_for(redis)):
            raise RuntimeError("boom")
    assert "plann:lock:job" in redis.store


async def test_hold_second_sequential_entry_within_ttl_is_refused():
    redis = LockRedis()
    results = []
    for _ in range(2):
        async with with_distributed_lock("job", ttl=60, fail_closed=True, hold=True,
                                         redis_factory=factory_for(redis)) as acquired:
            results.append(acquired)
    assert results == [True, False]


async def test_default_still_releases_after_exit():
    redis = LockRedis()
    async with with_distributed_lock("job", ttl=60, fail_closed=True,
                                     redis_factory=factory_for(redis)):
        pass
    assert "plann:lock:job" not in redis.store
