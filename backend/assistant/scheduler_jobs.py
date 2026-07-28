"""
PLANN Asistan — Zamanlayıcı işleri (APScheduler cron).

Üç tetikleyici (Europe/Istanbul):
  - Sabah brifingi   : her gün 08:30
  - Gece kapanışı    : Pzt–Cmt 22:00
  - Haftalık CEO özeti: Pazar 22:00 (o akşam gece kapanışı yerine bu gider)

Çoklu worker (17 uvicorn) ortamında her iş SADECE bir worker'da çalışsın diye
Redis dağıtık kilit (SET NX EX) kullanılır — WhatsApp reminder desenindeki gibi.
"""

import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .analytics_engine import collect_daily_metrics, collect_week_metrics, revenue_on_date, service_revenue_between
from .health_engine import build_morning_decision, build_night_decision, build_weekly_decision
from .notification_engine import process_and_notify
from .scenarios import WARMUP_DAYS

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")
ASSISTANT_ENABLED = os.getenv("ASSISTANT_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")

_LOCK_TTL = 1800  # 30 dk


async def _acquire_lock(redis_client, name: str) -> bool:
    """Dağıtık kilit. Redis yoksa True döner (tek worker varsayımı / fail-open)."""
    if not redis_client:
        return True
    try:
        key = f"plann:assistant_lock:{name}"
        ok = await redis_client.set(key, "1", nx=True, ex=_LOCK_TTL)
        return bool(ok)
    except Exception as e:
        logger.warning("Assistant lock unavailable (%s), proceeding: %s", name, e)
        return True


async def _orgs_with_push(db):
    """Sadece push aboneliği olan org'ları işle (boşuna sorgu/log üretme)."""
    try:
        return set(await db.push_subscriptions.distinct("organization_id"))
    except Exception:
        return set()


async def _settings_for(db, org_ids):
    if not org_ids:
        return []
    return await db.settings.find(
        {"organization_id": {"$in": list(org_ids)}}, {"_id": 0},
    ).to_list(10000)


async def _org_age_days(db, org_id: str, ref_date_str: str) -> int:
    first = await db.appointments.find(
        {"organization_id": org_id}, {"_id": 0, "appointment_date": 1},
    ).sort("appointment_date", 1).to_list(1)
    if not first:
        return 0
    try:
        d0 = datetime.strptime(first[0]["appointment_date"], "%Y-%m-%d")
        dr = datetime.strptime(ref_date_str, "%Y-%m-%d")
        return max(0, (dr - d0).days)
    except Exception:
        return 0


async def _night_baseline(db, org_id: str, date_str: str, mode: str) -> float:
    """Gece hikâyesi için ciro referansı."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    if mode == "motivation":
        # Isınma dönemi: düne göre kıyasla.
        return await revenue_on_date(db, org_id, (d - timedelta(days=1)).strftime("%Y-%m-%d"))
    # Zeka modu: aynı haftagününün son 4 haftalık ortalaması.
    vals = []
    for k in (1, 2, 3, 4):
        ds = (d - timedelta(days=7 * k)).strftime("%Y-%m-%d")
        vals.append(await revenue_on_date(db, org_id, ds))
    nonzero = [v for v in vals if v > 0]
    return round(sum(nonzero) / len(nonzero), 2) if nonzero else 0.0


async def _week_revenue(db, org_id: str, start_str: str, end_str: str) -> float:
    agg = await service_revenue_between(db, org_id, start_str, end_str)
    return round(sum(agg.values()), 2)


# ---------------------------------------------------------------------------
# İş fonksiyonları
# ---------------------------------------------------------------------------
async def morning_briefing_job(db, redis_client=None, push_fn=None):
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    if not await _acquire_lock(redis_client, f"morning:{date_str}"):
        logger.info("Assistant morning skipped — lock held by another worker")
        return
    org_ids = await _orgs_with_push(db)
    settings_list = await _settings_for(db, org_ids)
    logger.info("Assistant morning: %s org", len(settings_list))
    sent = 0
    for s in settings_list:
        org_id = s.get("organization_id")
        try:
            metrics = await collect_daily_metrics(db, org_id, s, date_str)
            packet = build_morning_decision(metrics)
            res = await process_and_notify(db, org_id, s, "morning", metrics, packet, date_str, push_fn=push_fn)
            if res.get("status") == "sent":
                sent += 1
        except Exception as e:
            logger.error("Assistant morning failed org=%s: %s", org_id, e, exc_info=True)
    logger.info("Assistant morning done — sent=%s", sent)


async def night_closing_job(db, redis_client=None, push_fn=None):
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    if not await _acquire_lock(redis_client, f"night:{date_str}"):
        logger.info("Assistant night skipped — lock held by another worker")
        return
    org_ids = await _orgs_with_push(db)
    settings_list = await _settings_for(db, org_ids)
    logger.info("Assistant night: %s org", len(settings_list))
    sent = 0
    for s in settings_list:
        org_id = s.get("organization_id")
        try:
            metrics = await collect_daily_metrics(db, org_id, s, date_str)
            await _store_snapshot(db, org_id, date_str, metrics)
            age = await _org_age_days(db, org_id, date_str)
            mode = "motivation" if age < WARMUP_DAYS else "intelligence"
            baseline = await _night_baseline(db, org_id, date_str, mode)
            packet = build_night_decision(metrics, baseline, mode)
            res = await process_and_notify(db, org_id, s, "night", metrics, packet, date_str, push_fn=push_fn)
            if res.get("status") == "sent":
                sent += 1
        except Exception as e:
            logger.error("Assistant night failed org=%s: %s", org_id, e, exc_info=True)
    logger.info("Assistant night done — sent=%s", sent)


async def weekly_summary_job(db, redis_client=None, push_fn=None):
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    if not await _acquire_lock(redis_client, f"weekly:{date_str}"):
        logger.info("Assistant weekly skipped — lock held by another worker")
        return
    today = datetime.strptime(date_str, "%Y-%m-%d")
    week_start = today - timedelta(days=today.weekday())   # Pazartesi
    week_end = today                                       # Pazar
    ws, we = week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
    prev_ws = (week_start - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_we = (week_end - timedelta(days=7)).strftime("%Y-%m-%d")

    org_ids = await _orgs_with_push(db)
    settings_list = await _settings_for(db, org_ids)
    logger.info("Assistant weekly: %s org (%s..%s)", len(settings_list), ws, we)
    sent = 0
    for s in settings_list:
        org_id = s.get("organization_id")
        try:
            week_metrics = await collect_week_metrics(db, org_id, s, ws, we)
            # Önceki 4 haftanın ortalaması (baseline)
            prev_totals = []
            for k in (1, 2, 3, 4):
                pks = (week_start - timedelta(days=7 * k)).strftime("%Y-%m-%d")
                pke = (week_end - timedelta(days=7 * k)).strftime("%Y-%m-%d")
                prev_totals.append(await _week_revenue(db, org_id, pks, pke))
            nz = [v for v in prev_totals if v > 0]
            prev_avg = round(sum(nz) / len(nz), 2) if nz else 0.0
            prev_service = await service_revenue_between(db, org_id, prev_ws, prev_we)
            packet = build_weekly_decision(week_metrics, prev_avg, prev_service)
            res = await process_and_notify(db, org_id, s, "weekly", week_metrics, packet, date_str, push_fn=push_fn)
            if res.get("status") == "sent":
                sent += 1
        except Exception as e:
            logger.error("Assistant weekly failed org=%s: %s", org_id, e, exc_info=True)
    logger.info("Assistant weekly done — sent=%s", sent)


async def _store_snapshot(db, org_id: str, date_str: str, metrics: dict):
    """Günlük ham metrik snapshot'u (gözlemlenebilirlik + gelecekteki analizler)."""
    try:
        await db.assistant_daily_snapshots.update_one(
            {"organization_id": org_id, "date": date_str},
            {"$set": {
                "organization_id": org_id,
                "date": date_str,
                "metrics": metrics,
                "updated_at": datetime.now(TZ).isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug("snapshot store failed org=%s: %s", org_id, e)


# ---------------------------------------------------------------------------
# Kayıt
# ---------------------------------------------------------------------------
def register_assistant_jobs(scheduler, db, redis_client=None, push_fn=None) -> bool:
    """
    APScheduler'a asistan cron işlerini ekler. ASSISTANT_ENABLED kapalıysa hiçbir
    şey yapmaz. server.py lifespan Step 4'ten çağrılır.
    """
    if not ASSISTANT_ENABLED:
        logger.info("PLANN Asistan devre dışı (ASSISTANT_ENABLED=false)")
        return False

    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        morning_briefing_job, CronTrigger(hour=8, minute=30, timezone=TZ),
        args=(db, redis_client, push_fn),
        id="assistant_morning_briefing", replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        night_closing_job, CronTrigger(day_of_week="mon-sat", hour=22, minute=0, timezone=TZ),
        args=(db, redis_client, push_fn),
        id="assistant_night_closing", replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        weekly_summary_job, CronTrigger(day_of_week="sun", hour=22, minute=0, timezone=TZ),
        args=(db, redis_client, push_fn),
        id="assistant_weekly_summary", replace_existing=True, max_instances=1,
    )
    logger.info("✅ PLANN Asistan: 3 cron işi kaydedildi (08:30 / 22:00 / Pazar 22:00, Europe/Istanbul)")
    return True
