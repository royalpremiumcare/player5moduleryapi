# Faz 6: Scheduler Locks and Payout Batch Safety — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Owner rule: every subagent invokes superpowers:test-driven-development, superpowers:systematic-debugging and superpowers:verification-before-completion (reviewers: verification-before-completion).

**Goal:** Every scheduled job runs in exactly one of the 17 uvicorn workers per run. Money-moving jobs never run without a lock. A payout batch can never be built twice, built for more than its reserved items, or funded after its reserve expired.

**Architecture:** One async lock helper, `financial/distributed_lock.py`. It does Redis `SET NX PX` with a random owner token, and releases through a Lua compare-and-delete. A failure to reach Redis is fail-closed for money jobs and fail-open only where the plan says so. Every unlocked job is wrapped. Payout batch correctness comes from Cursor's Oct 1 draft (branch `wip/cursor-oct1-faz6-faz7`, commit 7ee7dde0). The draft's financial files are a reference to finish, not code to trust.

**Spec:** The master plan, `/root/.cursor/plans/plann_master_uygulama_planı_bbedf5f9.plan.md`, sections "Faz 6", "Olay — mükerrer ödeme partileri", "Faz 6a" and "Faz 6b". It is the binding source. The owner said "faz 6yı erteleme düzelt": do it now. Merchant payments are currently paused (env `MERCHANT_PAYMENTS_PAUSED`, Wise account closed). This work makes the code correct for when payments return; it does not re-enable anything.

## Global Constraints
- Python 3.10; no new dependencies (`redis.asyncio` is already used in `financial/cron_jobs.py`).
- Lock keys: `plann:lock:<job_name>`. Values: a random token (uuid4 hex). TTL in milliseconds via `px`.
- Release must use a Lua script: `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`.
- Fail-closed (skip the job and log a WARNING) when Redis is unreachable, for these jobs: `currency_shield`, `daily_reconciliation`, `wise_auto_convert`, `refund_reconciliation`, `settlement_check`, `refund_reserve_release`, `wise_status_check`, `failed_webhook_retry`, `tuesday_batch_prepare`, `expiry_crons`, `dlq_retry`, `refund_sla_monitor`. Fail-open only for `quote_cleanup`. The jobs that already have their own locks (reminders, live activity, billing lifecycle, activation nudge, assistant) are untouched.
- `recurring_payment_job` (dead PayTR path with undefined `PAYTR_*` constants; 0 orgs have `card_saved: true`) is no longer registered. Keep the function, with a docstring saying why.
- No change to API response shapes. No DB writes to production in any task. Deploy happens from `git archive`, only on the owner's approval.
- Test command (prod image, read-only mount): `docker run --rm --network none -v $PWD/backend:/app:ro -w /app -e PYTHONDONTWRITEBYTECODE=1 player5moduleryapi-backend:6f778cd5 python -m pytest <paths> -q -p no:cacheprovider`. Run the full suite as `tests --ignore=tests/integration` plus `tests/integration`.

## Review Focus
1. Two workers enter the same job at once: exactly one runs it. (Task 1, Task 2)
2. Redis is down: money jobs do not run; `quote_cleanup` does. (Task 1, Task 2)
3. A job outlives its TTL and another worker takes the lock: the first worker's release must not delete the second worker's lock. (Task 1)
4. Concurrent batch preparation for the same org and day: one batch, whose amount is the sum of the reserved items. A second insert hits the unique `idempotency_key`, and its reserves are rolled back. (Task 3)
5. A batch whose reserve window passed, or whose items are no longer reserved: it cannot be funded and is marked expired. (Task 3)

---

### Task 1: Lock helper
**Files:** Create `backend/financial/distributed_lock.py`; Test `backend/tests/test_distributed_lock.py`.
**Produces:** `with_distributed_lock(name: str, *, ttl: int, fail_closed: bool, redis_factory=None)`, an async context manager that yields `acquired: bool`. `redis_factory` is injectable for tests and defaults to `redis.asyncio.from_url(REDIS_URL)`. The lock is released on exit only if this caller owns it. A Redis error on acquire yields `not fail_closed`. A Redis error on release is logged and never raised.
- [ ] Failing tests:
  - `test_second_concurrent_holder_is_refused` (two `asyncio.gather` entries → exactly one `True`);
  - `test_release_only_deletes_own_token` (simulate TTL expiry plus a takeover → the first exit leaves the second's key);
  - `test_redis_down_fail_closed_skips` and `test_redis_down_fail_open_runs`;
  - `test_release_error_never_raises`;
  - `test_lock_released_after_body_exception` (the body raises → the lock is freed and the exception propagates).
  
  Use a fake Redis with `set(nx, px)`, `eval` and `aclose`. Extend `tests/live_activity_fakes.py` only if it is backward compatible.
- [ ] RED → implement → GREEN → full suite → commit `feat(financial): distributed lock with owner token and fail-closed mode`.

### Task 2: Wrap every unlocked job; replace `_acquire_lock`; stop PayTR recurring
**Files:**
- Modify `backend/financial/cron_jobs.py`: replace `_acquire_lock` with the helper (fail-closed) and wrap `settlement_check_job`, `refund_reserve_release_job`, `wise_status_check_job`, `quote_cleanup_job` (fail-open) and `failed_webhook_retry_job`.
- Modify `backend/server.py` (Step 4 scheduler block, ~1336-1535): wrap `_run_expiry`, `_run_tuesday_batch`, `_run_refund_sla` and `_run_dlq_retry`, and remove the `recurring_payment_job` registration. Alternatively wrap them inside their target functions, as the Cursor draft did for `tuesday_batch_prepare_cron` and `run_retry_cron`. Pick one place per job, never both.
- Test: `backend/tests/test_scheduler_locks.py`.
- [ ] Failing tests:
  - for each job in the Global Constraints list: with the lock held elsewhere, the job body is not called; with Redis down, fail-closed jobs don't run and `quote_cleanup` does;
  - `test_recurring_payment_job_not_registered` (inspect what Step 4 registers through a fake scheduler, or a source-level guard if the startup block can't be run in isolation; explain the choice).
- [ ] RED → implement → GREEN → full suite → commit.

### Task 3: Payout batch correctness (finish the Cursor draft)
**Files:** `backend/financial/wednesday_batch.py`, `backend/financial/expiry_service.py`, `backend/financial/dead_letter_queue.py`, `backend/financial/migration.py` (index definitions) and the financial index list (find where `payout_batches` indexes are defined: `financial/schemas.py` `FINANCIAL_INDEXES` or similar). Test: `backend/tests/test_payout_batch_safety.py`. Reference: `git show 7ee7dde0 -- backend/financial` (Cursor draft); its lock calls must use the Task 1 helper.
- [ ] Requirements (master plan Faz 6a items 3–5):
  - **Unique index:** `payout_batches.idempotency_key` unique with `partialFilterExpression: {idempotency_enforced: true}`, so the 3 legacy `partial_failure` batches sharing a key don't block it. New batches set `idempotency_enforced: true`. A duplicate-key insert rolls back that worker's reserved items to `available`.
  - **Amount:** the batch total equals the sum of the items this worker actually reserved (`reserved_ok`). If that total is below the threshold, roll back and skip.
  - **Expiry:** when reserve expiry rolls items back, any open batch (draft / awaiting_admin_fund / queued_for_wise) left with no held items becomes `expired`.
  - **Funding guard:** `prepare_batch_for_wise`, `bulk_prepare_batches_for_wise` and `confirm_manual_fund` refuse a batch older than the reserve window, or one whose items are not all still held. The batch is marked `expired` where applicable and returns `{ok: False, error: ...}`.
- [ ] Failing tests:
  - `test_concurrent_prepare_one_batch_amount_equals_reserved` (two concurrent prepares, the second losing some items);
  - `test_duplicate_key_rolls_back_orphan_reserves`;
  - `test_under_threshold_after_race_rolls_back`;
  - `test_expired_reserve_expires_open_batch`;
  - `test_fund_refused_for_stale_or_unheld_batch` (all three funding paths);
  - `test_legacy_duplicate_keys_do_not_block_index` (index spec has the partial filter).
- [ ] RED → implement → GREEN → full suite → commit.
