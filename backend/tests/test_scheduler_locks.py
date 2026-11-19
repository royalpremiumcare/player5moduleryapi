"""Faz 6 Task 2: every unlocked scheduled job runs behind the distributed lock."""
import re
from pathlib import Path

import pytest

from financial import cron_jobs, distributed_lock

from tests.test_distributed_lock import LockRedis

FAIL_CLOSED_JOBS = [
    ("currency_shield_job", "currency_shield", 600),
    ("settlement_check_job", "settlement_check", 110),
    ("refund_reserve_release_job", "refund_reserve_release", 3300),
    ("wise_status_check_job", "wise_status_check", 1650),
    ("failed_webhook_retry_job", "failed_webhook_retry", 810),
    ("daily_reconciliation_job", "daily_reconciliation", 1800),
    ("refund_reconciliation_job", "refund_reconciliation", 270),
    ("wise_auto_convert_job", "wise_auto_convert", 3300),
]


class BodySpy:
    """Replaces the job body; `calls` shows whether the lock let the body run."""

    def __init__(self, monkeypatch, job):
        self.calls = []
        self.db = object()

        async def body(db):
            self.calls.append(db)

        monkeypatch.setattr(cron_jobs, f"_{job}_body", body)


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch):
    monkeypatch.setenv("WISE_ENVIRONMENT", "sandbox")


@pytest.fixture
def redis(monkeypatch):
    r = LockRedis()
    monkeypatch.setattr(distributed_lock, "_default_factory", lambda: r)
    monkeypatch.setattr(distributed_lock, "REDIS_TIMEOUT", 0.2)
    return r


@pytest.mark.parametrize("job,lock,ttl", FAIL_CLOSED_JOBS)
async def test_fail_closed_job_skips_when_lock_held(redis, monkeypatch, job, lock, ttl):
    redis.store[f"plann:lock:{lock}"] = "other-worker"
    spy = BodySpy(monkeypatch, job)
    await getattr(cron_jobs, job)(spy.db)
    assert spy.calls == []
    assert redis.store[f"plann:lock:{lock}"] == "other-worker"


@pytest.mark.parametrize("job,lock,ttl", FAIL_CLOSED_JOBS)
async def test_fail_closed_job_skips_when_redis_down(redis, monkeypatch, job, lock, ttl):
    redis.fail_set = True
    spy = BodySpy(monkeypatch, job)
    await getattr(cron_jobs, job)(spy.db)
    assert spy.calls == []


@pytest.mark.parametrize("job,lock,ttl", FAIL_CLOSED_JOBS)
async def test_job_runs_under_named_lock_with_ttl_and_releases(redis, monkeypatch, job, lock, ttl):
    spy = BodySpy(monkeypatch, job)
    await getattr(cron_jobs, job)(spy.db)
    assert spy.calls == [spy.db]
    assert redis.set_calls == [(f"plann:lock:{lock}", True, ttl * 1000)]
    # hold=True: key stays as the dedupe window until its TTL expires
    assert f"plann:lock:{lock}" in redis.store


async def test_quote_cleanup_skips_when_lock_held(redis, monkeypatch):
    redis.store["plann:lock:quote_cleanup"] = "other-worker"
    spy = BodySpy(monkeypatch, 'quote_cleanup_job')
    await cron_jobs.quote_cleanup_job(spy.db)
    assert spy.calls == []


async def test_quote_cleanup_runs_when_redis_down_fail_open(redis, monkeypatch):
    redis.fail_set = True
    spy = BodySpy(monkeypatch, 'quote_cleanup_job')
    await cron_jobs.quote_cleanup_job(spy.db)
    assert spy.calls == [spy.db]


async def test_quote_cleanup_runs_under_lock_and_releases(redis, monkeypatch):
    spy = BodySpy(monkeypatch, 'quote_cleanup_job')
    await cron_jobs.quote_cleanup_job(spy.db)
    assert spy.calls == [spy.db]
    assert redis.set_calls[0] == ("plann:lock:quote_cleanup", True, 3300 * 1000)
    assert "plann:lock:quote_cleanup" in redis.store


def test_old_acquire_lock_removed():
    assert not hasattr(cron_jobs, "_acquire_lock")


# server.py Step 4 lives inside the app lifespan and cannot run in isolation,
# so these are source-level guards on the registration block.
SERVER_SRC = (Path(__file__).resolve().parent.parent / "server.py").read_text()


def test_recurring_payment_job_not_registered():
    assert "id='recurring_payment_job'" not in SERVER_SRC
    assert 'id="recurring_payment_job"' not in SERVER_SRC
    assert not re.search(r"add_job\(\s*check_and_process_recurring_payments", SERVER_SRC)


def test_recurring_function_kept_with_why_docstring():
    m = re.search(r"async def check_and_process_recurring_payments\(\):\s+\"\"\"(.*?)\"\"\"", SERVER_SRC, re.S)
    assert m, "function must be kept"
    assert "PAYTR" in m.group(1) and "card_saved" in m.group(1)


@pytest.mark.parametrize("inner,lock,ttl", [
    ("run_expiry_crons(_db)", "expiry_crons", 3300),
    ("run_sla_monitor_cron(_db)", "refund_sla_monitor", 810),
])
def test_server_wrappers_use_fail_closed_lock(inner, lock, ttl):
    pat = (
        r"with_distributed_lock\(\s*['\"]%s['\"],\s*ttl=%d,\s*fail_closed=True,\s*hold=True\s*\)"
        r"\s*as\s+\w+:\s*if\s+\w+:\s*await %s" % (lock, ttl, re.escape(inner))
    )
    assert re.search(pat, SERVER_SRC)


def test_tuesday_and_dlq_wrappers_untouched_by_task2():
    # Controller ruling P1: those locks live inside the target functions (Task 3).
    assert "with_distributed_lock('tuesday_batch_prepare'" not in SERVER_SRC
    assert "with_distributed_lock('dlq_retry'" not in SERVER_SRC


# --- Fix round 1: lock must dedupe across sequential worker ticks ---------

@pytest.mark.parametrize("job,lock,ttl", FAIL_CLOSED_JOBS + [("quote_cleanup_job", "quote_cleanup", 3300)])
async def test_second_worker_tick_after_first_finished_is_skipped(redis, monkeypatch, job, lock, ttl):
    spy = BodySpy(monkeypatch, job)
    await getattr(cron_jobs, job)(spy.db)   # worker A ticks and finishes
    await getattr(cron_jobs, job)(spy.db)   # worker B ticks within the window
    assert len(spy.calls) == 1


async def test_server_style_wrapper_pattern_runs_body_once_across_workers(redis):
    calls = []

    async def run_expiry():  # same shape as server.py _run_expiry
        async with distributed_lock.with_distributed_lock(
            "expiry_crons", ttl=3300, fail_closed=True, hold=True
        ) as acquired:
            if acquired:
                calls.append(1)

    await run_expiry()
    await run_expiry()
    assert calls == [1]


def test_settlement_schedule_single_source_for_interval_and_ttl(monkeypatch):
    for env, interval_min, ttl in [("sandbox", 2, 110), ("production", 120, 6900)]:
        monkeypatch.setenv("WISE_ENVIRONMENT", env)
        assert cron_jobs._settlement_schedule() == (interval_min, ttl)
        assert ttl < interval_min * 60


def test_settlement_registration_uses_schedule_helper(monkeypatch):
    for env in ("sandbox", "production"):
        monkeypatch.setenv("WISE_ENVIRONMENT", env)
        added = {}

        class Sched:
            def add_job(self, fn, trigger, **kw):
                added[kw["id"]] = kw

        cron_jobs.register_financial_cron_jobs(Sched(), object())
        assert added["settlement_check_job"]["minutes"] == cron_jobs._settlement_schedule()[0]
