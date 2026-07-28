"""
PLANN Financial Engine — Cron Jobs (APScheduler)

All scheduled financial jobs:
  - currency_shield_job       : 01:00 UTC nightly
  - settlement_check_job      : every 2 hours
  - refund_reserve_release_job: every hour
  - auto_payout_job           : every 2 hours
  - wise_status_check_job     : every 30 min
  - quote_cleanup_job         : every hour
  - failed_webhook_retry_job  : every 15 min
  - daily_reconciliation_job  : 23:30 UTC nightly
"""

import logging
import stripe
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from .state_machine import StateMachine, TRANSITIONS
from .currency_shield import fetch_current_rate, recalculate_try_tier_limits, check_rate_spike
from .payout_service import build_auto_payout_batches
from .compliance import update_refund_reserve
from .wise_service import get_transfer_status, map_wise_status_to_state
from .email_notifications import (
    send_reconciliation_alert,
    send_rate_spike_alert,
    send_payout_success_email,
    send_payout_failed_email,
)
from .money import format_display
import redis.asyncio as aioredis
import os

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://plann_redis:6379/0")


# ---------------------------------------------------------------------------
# Settlement timing helpers — Stripe iş günü (business day) mantığı
# ---------------------------------------------------------------------------

def _parse_iso(raw: Any) -> datetime:
    """ISO string → timezone-aware datetime (naive ise UTC varsay)."""
    s = raw.replace("Z", "+00:00") if isinstance(raw, str) else raw
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fetch_bt_fields(tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Stripe'tan balance_transaction'ı çekip denetim/settlement alanlarını döner.

    Checkout anında balance_transaction bazen henüz 'null' olur; bu yüzden gerçek
    Stripe ücreti/net/gross ve available_on capture'da yakalanamayabilir. Burada
    ID zinciri (balance_tx → charge → payment_intent) ile sonradan güvenle çekilir.
    Dönen dict: balance_tx_id, fee, net, gross, available_on(iso) — veya None.
    available_on, işlem daha 'pending' iken bile Stripe tarafından verilir.
    """
    try:
        bt_id = tx.get("stripe_balance_transaction_id")
        if not bt_id:
            cid = tx.get("stripe_charge_id")
            if cid:
                ch = stripe.Charge.retrieve(cid)
                _bt = ch.balance_transaction
                bt_id = _bt if isinstance(_bt, str) else getattr(_bt, "id", None)
            else:
                pi_id = tx.get("stripe_payment_intent_id")
                if pi_id:
                    pi = stripe.PaymentIntent.retrieve(pi_id, expand=["latest_charge"])
                    lc = pi.latest_charge
                    if lc and not isinstance(lc, str):
                        _bt = lc.balance_transaction
                        bt_id = _bt if isinstance(_bt, str) else getattr(_bt, "id", None)
        if not bt_id:
            return None
        bt = stripe.BalanceTransaction.retrieve(bt_id)
        ao = bt.available_on
        return {
            "stripe_balance_transaction_id": bt_id,
            "stripe_fee_gbp_minor": bt.fee,        # gerçek Stripe ücreti (GBP)
            "amount_settled_gbp_minor": bt.net,    # net (GBP)
            "gross_amount_gbp_minor": bt.amount,   # brüt (GBP)
            "stripe_available_on": (
                datetime.fromtimestamp(int(ao), tz=timezone.utc).isoformat() if ao else None
            ),
        }
    except Exception as e:
        logger.warning("balance_transaction Stripe'tan çekilemedi tx=%s: %s", tx.get("id"), e)
    return None


async def _resolve_settlement_due(db, tx: Dict[str, Any]) -> Optional[datetime]:
    """Bu işlem ne zaman 'settled' olabilir? (Stripe available_on = tek doğru kaynak)

    1) Kayıtlı `stripe_available_on` varsa onu kullan.
    2) Yoksa Stripe'tan balance_transaction'ı çek; available_on + gerçek ücret/net/
       gross'u tx'e KALICI yaz (eksikse). Böylece denetim paneli de doğru dolar.
    3) Stripe'tan da alınamazsa None → işlem 'captured' bırakılır, sonraki turda
       tekrar denenir. Güvenli yön: parayı asla erken 'available' göstermeyiz.
    """
    raw = tx.get("stripe_available_on")
    if raw:
        try:
            return _parse_iso(raw)
        except Exception:
            pass
    fields = _fetch_bt_fields(tx)
    if fields:
        # Yalnızca eksik olanları yaz (mevcut değerleri ezme).
        setd: Dict[str, Any] = {}
        for k, v in fields.items():
            if v is not None and not tx.get(k):
                setd[k] = v
        if setd:
            await db.merchant_transactions.update_one({"id": tx["id"]}, {"$set": setd})
        iso = fields.get("stripe_available_on")
        if iso:
            try:
                return _parse_iso(iso)
            except Exception:
                pass
    logger.warning(
        "Settlement due tarihi belirlenemedi (Stripe erişilemedi) — tx captured "
        "bırakılıyor, sonraki turda tekrar denenecek: %s", tx.get("id"),
    )
    return None

async def _acquire_lock(lock_name: str, ttl: int = 300) -> bool:
    """Try to acquire a Redis-based distributed lock. Returns True if acquired."""
    try:
        r = aioredis.from_url(REDIS_URL)
        acquired = await r.set(f"plann:lock:{lock_name}", "1", nx=True, ex=ttl)
        await r.aclose()
        return bool(acquired)
    except Exception:
        return True  # If Redis fails, allow job to run


# ---------------------------------------------------------------------------
# 1. Currency Shield Job — nightly 01:00 UTC
# ---------------------------------------------------------------------------

async def currency_shield_job(db) -> None:
    """Fetch GBP/TRY rate, recalculate TRY tier limits, alert on spike."""
    if not await _acquire_lock("currency_shield", ttl=600):
        logger.debug("Currency shield job skipped — another worker holds the lock")
        return
    try:
        rate_micro, source = await fetch_current_rate(db)

        spike = await check_rate_spike(db, rate_micro)
        if spike:
            logger.warning("Rate spike detected: %s", spike)
            send_rate_spike_alert(
                spike["old_rate_display"],
                spike["new_rate_display"],
                spike["change_pct"],
                spike["direction"],
            )

        await recalculate_try_tier_limits(db, rate_micro, source)
        logger.info("Currency shield job completed: rate_micro=%d source=%s", rate_micro, source)

    except Exception as e:
        logger.exception("Currency shield job failed: %s", e)


# ---------------------------------------------------------------------------
# 2. Settlement Check Job — every 6 hours
# ---------------------------------------------------------------------------

async def settlement_check_job(db) -> None:
    """
    Check Stripe settlements and advance transactions:
    captured → settled (after T+2) → available (after dispute window)

    In sandbox mode, delays are skipped for faster testing.
    """
    sm = StateMachine(db)
    now = datetime.now(timezone.utc)
    is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"

    # captured → settled: Stripe'ın available_on'u (iş günü + tatil hesaplı).
    # Statik takvim T+2 KULLANMA — Cuma alınan ödeme hafta sonu Stripe bakiyesine
    # geçmezken sistemde 'settled/available' göstermek, esnaf o parayı çekmeye
    # kalkınca kasadan sübvanse riskine yol açar. Her tx için gerçek settlement
    # tarihine ulaşıldığında ilerlet (sandbox'ta anında).
    captured_txs = await db.merchant_transactions.find({
        "state": "captured",
    }).to_list(length=1000)

    settled_count = 0
    for tx in captured_txs:
        try:
            if is_sandbox:
                due = True
            else:
                due_at = await _resolve_settlement_due(db, tx)
                due = due_at is not None and now >= due_at
            if due:
                await sm.transition(tx["id"], "settled", "settlement_check_job")
                settled_count += 1
        except Exception as e:
            logger.warning("Failed to settle tx %s: %s", tx["id"], e)

    # settled → available: transactions older than dispute window
    settings_cache = {}
    settled_txs = await db.merchant_transactions.find({
        "state": "settled",
    }).to_list(length=500)

    available_count = 0
    for tx in settled_txs:
        org_id = tx["organization_id"]
        if org_id not in settings_cache:
            settings_cache[org_id] = await db.settings.find_one({"organization_id": org_id})

        settings = settings_cache.get(org_id, {})
        refund_hours = 0 if is_sandbox else (settings or {}).get("refund_window_hours", 12)
        cutoff = (now - timedelta(hours=refund_hours)).isoformat()

        if tx.get("created_at", "") <= cutoff:
            try:
                await sm.transition(tx["id"], "available", "settlement_check_job")
                available_count += 1
            except Exception as e:
                logger.warning("Failed to make tx %s available: %s", tx["id"], e)

    logger.info("Settlement check: %d settled, %d available", settled_count, available_count)


# ---------------------------------------------------------------------------
# 3. Refund Reserve Release Job — every hour
# ---------------------------------------------------------------------------

async def refund_reserve_release_job(db) -> None:
    """Recalculate refund reserves for all wallets."""
    wallets = await db.merchant_wallets.find({}).to_list(length=5000)
    updated = 0
    for wallet in wallets:
        org_id = wallet.get("organization_id")
        if org_id:
            await update_refund_reserve(db, org_id)
            updated += 1

    logger.info("Refund reserve release: %d wallets updated", updated)


# ---------------------------------------------------------------------------
# 4. Auto Payout Job — interval (1 saat)
# ---------------------------------------------------------------------------

async def auto_payout_job(db) -> None:
    """Run auto-payout for all eligible merchants."""
    try:
        results = await build_auto_payout_batches(db, triggered_by="cron")
        logger.info(
            "Auto payout: GBP=%d TRY=%d skipped=%d",
            len(results.get("gbp_batches", [])),
            len(results.get("try_batches", [])),
            len(results.get("skipped", [])),
        )
        for sk in results.get("skipped", []):
            logger.info("Auto payout skipped org=%s reasons=%s", sk.get("organization_id"), sk.get("reasons"))
    except Exception as e:
        logger.exception("Auto payout job failed: %s", e)


# ---------------------------------------------------------------------------
# 5. Wise Status Check Job — every 30 min
# ---------------------------------------------------------------------------

async def wise_status_check_job(db) -> None:
    """Poll Wise for transfer status updates on processing batches."""
    sm = StateMachine(db)

    processing_batches = await db.payout_batches.find({
        "status": "processing",
    }).to_list(length=100)

    for batch in processing_batches:
        all_done = True
        has_failure = False

        for i, item in enumerate(batch.get("items", [])):
            transfer_id = item.get("wise_transfer_id")
            if not transfer_id or item.get("item_status") in ("completed", "failed"):
                continue

            try:
                status_data = await get_transfer_status(transfer_id)
                wise_status = status_data.get("status", "")
                new_state = map_wise_status_to_state(wise_status)

                if new_state == "paid_out":
                    batch["items"][i]["item_status"] = "completed"

                    tx = await db.merchant_transactions.find_one({
                        "wise_transfer_id": transfer_id,
                    })
                    if tx and tx["state"] == "reserved":
                        await sm.transition(tx["id"], "paid_out", f"wise.{wise_status}")

                elif new_state == "failed":
                    batch["items"][i]["item_status"] = "failed"
                    has_failure = True

                    tx = await db.merchant_transactions.find_one({
                        "wise_transfer_id": transfer_id,
                    })
                    if tx and tx["state"] == "reserved":
                        await sm.transition(tx["id"], "failed", f"wise.{wise_status}")

                else:
                    all_done = False

            except Exception as e:
                logger.warning("Failed to check Wise transfer %s: %s", transfer_id, e)
                all_done = False

        await db.payout_batches.update_one(
            {"id": batch["id"]},
            {"$set": {"items": batch["items"]}},
        )

        if all_done:
            final_status = "partial_failure" if has_failure else "completed"
            await db.payout_batches.update_one(
                {"id": batch["id"]},
                {"$set": {
                    "status": final_status,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    logger.info("Wise status check: %d batches checked", len(processing_batches))


# ---------------------------------------------------------------------------
# 6. Quote Cleanup Job — every hour
# ---------------------------------------------------------------------------

async def quote_cleanup_job(db) -> None:
    """Expire quotes past their expiration time."""
    now = datetime.now(timezone.utc).isoformat()

    result = await db.wise_quotes.update_many(
        {
            "status": "active",
            "quote_expires_at": {"$lte": now, "$ne": ""},
        },
        {"$set": {"status": "expired"}},
    )

    if result.modified_count > 0:
        logger.info("Quote cleanup: %d quotes expired", result.modified_count)


# ---------------------------------------------------------------------------
# 7. Failed Webhook Retry Job — every 15 min
# ---------------------------------------------------------------------------

async def failed_webhook_retry_job(db) -> None:
    """Retry failed webhook events (max 3 attempts)."""
    from .merchant_checkout import handle_stripe_merchant_webhook
    from .wise_service import handle_wise_webhook

    failed_events = await db.webhook_events.find({
        "processing_status": "failed",
        "attempt_count": {"$lt": 3},
    }).to_list(length=50)

    retried = 0
    for event in failed_events:
        source = event.get("source", "")
        raw_body = event.get("raw_body", "")
        raw_headers = event.get("raw_headers", {})

        try:
            if source == "stripe_merchant":
                sig = raw_headers.get("stripe-signature", "")
                await handle_stripe_merchant_webhook(db, raw_body.encode(), sig)
            elif source == "wise":
                sig = raw_headers.get("X-Signature-SHA256", "")
                await handle_wise_webhook(db, raw_body.encode(), sig)

            retried += 1
        except Exception as e:
            logger.warning("Webhook retry failed for event %s: %s", event.get("event_id"), e)

    if retried > 0:
        logger.info("Webhook retry: %d/%d events retried", retried, len(failed_events))


# ---------------------------------------------------------------------------
# 8. Daily Reconciliation Job — nightly 23:30 UTC
# ---------------------------------------------------------------------------

async def daily_reconciliation_job(db) -> None:
    """
    Gün sonu mutabakatı:
    1. Stripe settlement verileri vs wallet pending/settled bakiyeleri
    2. Wise transfer durumları vs wallet reserved/paid_out bakiyeleri
    3. Wallet bakiye tutarlılığı (sum of parts == expected)

    1 kuruş/pence bile uyuşmazlık varsa fatihsenyuz12@gmail.com'a alert mail gönder.
    """
    # KRİTİK: 17 uvicorn worker aynı anda bu job'ı çalıştırırsa aynı gece
    # 17 kopya mutabakat maili gider. Dağıtık kilit ile tek worker çalışsın.
    if not await _acquire_lock("daily_reconciliation", ttl=1800):
        logger.debug("Daily reconciliation skipped — another worker holds the lock")
        return

    now = datetime.now(timezone.utc)
    report_date = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    today = yesterday + timedelta(days=1)

    discrepancies: List[Dict[str, Any]] = []

    try:
        # Mevcut (silinmemiş) işletmelerin org_id kümesi. İşletme silinince
        # cüzdan DB'de kalabiliyor (orphan). Orphan cüzdanların beklenen bakiyesi
        # 0 olur ama gerçek bakiye dolu kalırsa her gece YANLIŞ uyuşmazlık maili
        # gider. Bu yüzden orphan cüzdanları mutabakattan hariç tutuyoruz.
        existing_org_ids = set()
        async for s in db.settings.find({}, {"_id": 0, "organization_id": 1}):
            if s.get("organization_id"):
                existing_org_ids.add(s["organization_id"])

        # --- Check 1: Wallet balance consistency ---
        wallets = await db.merchant_wallets.find({}).to_list(length=10000)
        orphan_wallets = []
        for wallet in wallets:
            org_id = wallet.get("organization_id", "")
            bc = wallet.get("base_currency", "TRY")

            # Silinmiş işletmenin cüzdanı → mutabakattan atla (mail gönderme).
            if org_id and org_id not in existing_org_ids:
                orphan_wallets.append(org_id)
                continue

            # Sum of all non-terminal transaction amounts should match wallet totals
            pipeline = [
                {"$match": {"organization_id": org_id}},
                {"$group": {
                    "_id": "$state",
                    "total": {"$sum": "$amount_display_minor"},
                }},
            ]
            state_totals = {}
            async for doc in db.merchant_transactions.aggregate(pipeline):
                state_totals[doc["_id"]] = doc["total"]

            # Expected wallet balances from transactions
            expected_pending = state_totals.get("captured", 0)
            expected_settled = state_totals.get("settled", 0)
            expected_available = state_totals.get("available", 0)
            expected_reserved = state_totals.get("reserved", 0)
            expected_frozen = state_totals.get("frozen", 0) + state_totals.get("disputed", 0)

            actual_pending = wallet.get("pending_balance_minor", 0)
            actual_settled = wallet.get("settled_balance_minor", 0)
            actual_available = wallet.get("available_balance_minor", 0)
            actual_reserved = wallet.get("reserved_balance_minor", 0)
            actual_frozen = wallet.get("frozen_balance_minor", 0)

            checks = [
                ("pending_balance", expected_pending, actual_pending),
                ("settled_balance", expected_settled, actual_settled),
                ("available_balance", expected_available, actual_available),
                ("reserved_balance", expected_reserved, actual_reserved),
                ("frozen_balance", expected_frozen, actual_frozen),
            ]

            for field, expected, actual in checks:
                if expected != actual:
                    diff = actual - expected
                    discrepancies.append({
                        "organization_id": org_id,
                        "source": f"wallet.{field}",
                        "expected": format_display(expected, bc),
                        "actual": format_display(actual, bc),
                        "diff": format_display(diff, bc),
                        "diff_minor": diff,
                    })

        # --- Check 2: Paid out transactions vs payout batch totals ---
        completed_batches = await db.payout_batches.find({
            "status": "completed",
            "completed_at": {
                "$gte": yesterday.isoformat(),
                "$lt": today.isoformat(),
            },
        }).to_list(length=500)

        for batch in completed_batches:
            batch_total = sum(
                item.get("amount_gbp_minor", 0)
                for item in batch.get("items", [])
                if item.get("item_status") == "completed"
            )

            # Cross-check with transactions
            tx_total = 0
            for item in batch.get("items", []):
                if item.get("item_status") != "completed":
                    continue
                tx = await db.merchant_transactions.find_one({
                    "wise_transfer_id": item.get("wise_transfer_id"),
                    "state": "paid_out",
                })
                if tx:
                    tx_total += tx.get("amount_settled_gbp_minor", 0) or tx.get("amount_display_minor", 0)

            if batch_total != tx_total:
                diff = tx_total - batch_total
                discrepancies.append({
                    "organization_id": f"batch_{batch.get('id', '')}",
                    "source": "payout_batch_vs_transactions",
                    "expected": format_display(batch_total, "GBP"),
                    "actual": format_display(tx_total, "GBP"),
                    "diff": format_display(diff, "GBP"),
                    "diff_minor": diff,
                })

        if orphan_wallets:
            logger.warning(
                "Reconciliation: %d orphan wallet (silinmiş işletme) atlandı: %s",
                len(orphan_wallets), orphan_wallets,
            )

        # --- Send alert if any discrepancies ---
        if discrepancies:
            logger.warning(
                "Reconciliation found %d discrepancies for %s",
                len(discrepancies), report_date,
            )
            send_reconciliation_alert(discrepancies, report_date)
        else:
            logger.info("Daily reconciliation passed: no discrepancies for %s", report_date)

        # --- Save reconciliation report ---
        await db.financial_audit_logs.insert_one({
            "id": str(__import__("uuid").uuid4()),
            "organization_id": "system",
            "actor": "system",
            "actor_role": "cron",
            "action": "daily_reconciliation",
            "details": {
                "report_date": report_date,
                "wallets_checked": len(wallets),
                "orphan_wallets_skipped": len(orphan_wallets),
                "batches_checked": len(completed_batches),
                "discrepancy_count": len(discrepancies),
                "discrepancies": discrepancies[:20],  # limit for storage
            },
            "created_at": now.isoformat(),
        })

    except Exception as e:
        logger.exception("Daily reconciliation job failed: %s", e)


# ---------------------------------------------------------------------------
# Refund reconciliation — Stripe iade sonrası iç DB kuyruğu
# ---------------------------------------------------------------------------

async def refund_reconciliation_job(db) -> None:
    """pending refund_reconciliation_pending kayıtlarını dene (kilit + retry)."""
    if not await _acquire_lock("refund_reconciliation", ttl=240):
        logger.debug("refund_reconciliation job skipped — lock held")
        return
    try:
        from financial.refund_reconciliation_service import run_refund_reconciliation_cron

        out = await run_refund_reconciliation_cron(db, limit=15)
        logger.info(
            "refund_reconciliation_job: finished processed=%s (satır bazlı ayrıntı refund_reconciliation_cron loglarında)",
            out.get("processed", 0),
        )
    except Exception as e:
        logger.exception("refund_reconciliation_job failed: %s", e)


# ---------------------------------------------------------------------------
# Register all jobs with APScheduler
# ---------------------------------------------------------------------------

def register_financial_cron_jobs(scheduler, db) -> None:
    """
    Register all financial cron jobs with APScheduler.
    Call this in server.py lifespan after scheduler is created.
    """
    scheduler.add_job(
        currency_shield_job, "cron",
        args=[db], hour=1, minute=0,
        id="currency_shield_job",
        replace_existing=True,
    )

    _is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"
    scheduler.add_job(
        settlement_check_job, "interval",
        args=[db], minutes=2 if _is_sandbox else 120,
        id="settlement_check_job",
        replace_existing=True,
    )

    scheduler.add_job(
        refund_reserve_release_job, "interval",
        args=[db], hours=1,
        id="refund_reserve_release_job",
        replace_existing=True,
    )

    # auto_payout_job disabled — replaced by Wednesday weekly batch cron.
    # Kept import + function for backwards compat + on-demand testing, but
    # not scheduled. Threshold-based instant payouts are intentionally
    # removed to enforce the weekly settlement cadence.
    # scheduler.add_job(
    #     auto_payout_job, "interval",
    #     args=[db], hours=1,
    #     id="auto_payout_job",
    #     replace_existing=True,
    # )

    scheduler.add_job(
        wise_status_check_job, "interval",
        args=[db], minutes=30,
        id="wise_status_check_job",
        replace_existing=True,
    )

    scheduler.add_job(
        quote_cleanup_job, "interval",
        args=[db], hours=1,
        id="quote_cleanup_job",
        replace_existing=True,
    )

    scheduler.add_job(
        failed_webhook_retry_job, "interval",
        args=[db], minutes=15,
        id="failed_webhook_retry_job",
        replace_existing=True,
    )

    scheduler.add_job(
        daily_reconciliation_job, "cron",
        args=[db], hour=23, minute=30,
        id="daily_reconciliation_job",
        replace_existing=True,
    )

    scheduler.add_job(
        refund_reconciliation_job, "interval",
        args=[db], minutes=5,
        id="refund_reconciliation_job",
        replace_existing=True,
    )

    logger.info("Financial cron jobs registered: 9 jobs")
