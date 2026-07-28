"""
PLANN Pazarlama Otopilotu — WhatsApp müşteri geri-kazanım motoru.

Akış:
  1) Bir randevu "Tamamlandı" olduğunda (herhangi bir yoldan), ENQUEUE cron'u
     o randevuyu görür ve hizmete özel süreyi (varsayılan 21 gün) hesaplayarak
     ileri tarihli bir GÖREV (marketing_autopilot_tasks) oluşturur.
  2) DISPATCH cron'u her gün, zamanı gelen görevleri işler:
       - Son Dakika Kalkanı (Just-in-Time): müşteri, kaynak randevu tamamlandıktan
         SONRA yeni bir randevu oluşturmuşsa görev sessizce iptal edilir (skip).
       - Donanımsal Bütçe Koruması: aylık gönderim sayısı, işletmenin PLANN
         "Aylık Randevu Limiti"ni ASLA aşamaz (bulk sender'a dönüşmesin diye).
       - Aksi halde Meta "Marketing" şablonu gönderilir ("Randevu Oluştur" butonlu).

Tasarım notları:
  - Otopilot varsayılan KAPALI. Yalnızca settings.marketing_autopilot_enabled=True
    olan org'lar işlenir. enabled_at'ten SONRA tamamlanan randevular kuyruğa girer
    (otopilot açıldığında geçmişe patlama olmaz).
  - Çok worker (17 uvicorn) → her cron SADECE bir worker'da: Redis dağıtık kilit.
  - Booking quota'sı TÜKETİLMEZ (gerçek rezervasyonları bloklamamak için); bunun
    yerine gönderilen otopilot mesajları ay içinde ayrıca sayılıp limitle sınırlanır.
"""

import os
import re
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")

# Global kill-switch. Org bazında açık olsa bile bu KAPALI ise hiçbir gönderim olmaz.
MARKETING_AUTOPILOT_ENABLED = os.getenv(
    "MARKETING_AUTOPILOT_ENABLED", "true"
).strip().lower() in ("1", "true", "yes", "on")

DEFAULT_REACTIVATION_DAYS = 21
MIN_DAYS = 1
MAX_DAYS = 365
# Zamanı geçmiş görev, scheduled_for + bu kadar günden fazla beklemişse bayatlar
# (eski bir "seni özledik" mesajı atmanın anlamı yok) → skip:expired.
TASK_EXPIRE_DAYS = 7
DISPATCH_HOUR = 11  # Europe/Istanbul — gündüz, makul bir pazarlama saati
ENQUEUE_INTERVAL_MIN = 60
MAX_RETRIES = 3
# organization_plans.quota_limit yoksa kullanılacak güvenli varsayılan aylık tavan.
DEFAULT_MONTHLY_CAP = 100
# Sınırsız (kurumsal) planlarda dahi kötüye kullanımı önlemek için sabit güvenlik tavanı.
# "Sınırsız randevu" ≠ "sınırsız pazarlama mesajı"; ayda en fazla bu kadar mesaj gider.
UNLIMITED_AUTOPILOT_CAP = 1000

TASKS = "marketing_autopilot_tasks"
_CANCELLED_STATUSES = ("İptal", "İptal Edildi", "Cancelled")
_LOCK_TTL = 1800  # 30 dk


def clamp_days(value: Any, default: int = DEFAULT_REACTIVATION_DAYS) -> int:
    try:
        d = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_DAYS, min(MAX_DAYS, d))


async def ensure_indexes(db) -> None:
    """Görev kuyruğu indeksleri (idempotent)."""
    try:
        # Bir randevu için EN FAZLA bir görev → çift gönderim engeli.
        await db[TASKS].create_index(
            [("organization_id", 1), ("appointment_id", 1)], unique=True
        )
        await db[TASKS].create_index(
            [("organization_id", 1), ("status", 1), ("scheduled_for", 1)]
        )
        await db[TASKS].create_index([("status", 1), ("sent_at", 1)])
    except Exception as e:
        logger.debug("autopilot index creation skipped: %s", e)


async def _acquire_lock(redis_client, name: str) -> bool:
    if not redis_client:
        return True
    try:
        ok = await redis_client.set(f"plann:autopilot_lock:{name}", "1", nx=True, ex=_LOCK_TTL)
        return bool(ok)
    except Exception as e:
        logger.warning("autopilot lock unavailable (%s), proceeding: %s", name, e)
        return True


async def _enabled_orgs(db) -> List[Dict[str, Any]]:
    return await db.settings.find(
        {"marketing_autopilot_enabled": True}, {"_id": 0}
    ).to_list(10000)


def _parse_iso(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _service_days(settings: Dict[str, Any], service_id: str) -> int:
    days_map = settings.get("marketing_autopilot_days") or {}
    return clamp_days(days_map.get(service_id), DEFAULT_REACTIVATION_DAYS)


# ---------------------------------------------------------------------------
# 1) ENQUEUE — tamamlanan randevulardan ileri tarihli görev üret
# ---------------------------------------------------------------------------

async def enqueue_tasks(db) -> int:
    """Her enabled org için, enabled_at'ten sonra tamamlanan ve henüz kuyruğa
    girmemiş randevuları görev olarak yazar. Oluşturulan görev sayısını döner."""
    created = 0
    for settings in await _enabled_orgs(db):
        org_id = settings.get("organization_id")
        if not org_id:
            continue
        enabled_at = settings.get("marketing_autopilot_enabled_at")
        # enabled_at yoksa geçmişe patlamayı önlemek için hiçbir şey enqueue etme.
        if not enabled_at:
            continue

        cursor = db.appointments.find({
            "organization_id": org_id,
            "status": "Tamamlandı",
            "autopilot_task_created": {"$ne": True},
            "completed_at": {"$gte": enabled_at},
        }, {"_id": 0}).limit(2000)

        async for apt in cursor:
            try:
                apt_id = apt.get("id")
                phone = apt.get("phone")
                completed_at = apt.get("completed_at")
                if not apt_id or not phone or not completed_at:
                    continue
                comp_dt = _parse_iso(completed_at)
                if not comp_dt:
                    continue
                service_id = apt.get("service_id") or ""
                days = _service_days(settings, service_id)
                scheduled_for = (comp_dt.astimezone(TZ).date() + timedelta(days=days)).isoformat()

                task = {
                    "id": f"{org_id}:{apt_id}",
                    "organization_id": org_id,
                    "appointment_id": apt_id,
                    "customer_name": apt.get("customer_name") or "",
                    "phone": phone,
                    "service_id": service_id,
                    "service_name": apt.get("service_name") or "",
                    "completed_at": completed_at,
                    "days": days,
                    "scheduled_for": scheduled_for,
                    "status": "pending",
                    "retry_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                # appointment_id benzersiz → var olan görevi ezmeden ekle.
                await db[TASKS].update_one(
                    {"organization_id": org_id, "appointment_id": apt_id},
                    {"$setOnInsert": task},
                    upsert=True,
                )
                await db.appointments.update_one(
                    {"organization_id": org_id, "id": apt_id},
                    {"$set": {"autopilot_task_created": True}},
                )
                created += 1
            except Exception as e:
                logger.warning("autopilot enqueue failed org=%s apt=%s: %s", org_id, apt.get("id"), e)
    if created:
        logger.info("autopilot: %s görev kuyruğa alındı", created)
    return created


# ---------------------------------------------------------------------------
# 2) DISPATCH — zamanı gelen görevleri gönder (JIT + bütçe koruması)
# ---------------------------------------------------------------------------

def _plan_monthly_limit(plan_id: str) -> Optional[int]:
    """PLANS tanımından planın aylık randevu limitini döner. -1 = sınırsız.
    server.py çalışırken zaten yüklüdür; runtime lazy import güvenlidir."""
    try:
        from server import PLANS
        info = next((p for p in PLANS if p.get("id") == plan_id), None)
        if info is not None:
            return info.get("quota_monthly_appointments")
    except Exception:
        pass
    return None


async def _monthly_cap(db, org_id: str) -> int:
    """İşletmenin aylık gönderim tavanı = PLANN aylık randevu limiti. -1 = sınırsız.

    Öncelik: (1) plan SINIRSIZ ise (-1) → -1, DB'deki quota_limit'ten bağımsız.
    (2) organization_plans.quota_limit varsa onu kullan.
    (3) yoksa PLANS'taki plan varsayılanına düş; o da yoksa güvenli varsayılan.
    """
    plan = await db.organization_plans.find_one({"organization_id": org_id}, {"_id": 0})
    if not plan:
        return DEFAULT_MONTHLY_CAP
    plan_default = _plan_monthly_limit(plan.get("plan_id"))
    # Plan tanımı sınırsız ise (-1) sabit güvenlik tavanı uygula (suistimal önlemi).
    if plan_default == -1:
        return UNLIMITED_AUTOPILOT_CAP
    limit = plan.get("quota_limit")
    if limit is None:
        limit = plan_default if plan_default is not None else DEFAULT_MONTHLY_CAP
    if limit == -1:
        return UNLIMITED_AUTOPILOT_CAP
    try:
        return int(limit)
    except (TypeError, ValueError):
        return DEFAULT_MONTHLY_CAP


async def _sent_this_month(db, org_id: str) -> int:
    now_ist = datetime.now(TZ)
    month_start = now_ist.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_iso = month_start.astimezone(timezone.utc).isoformat()
    return await db[TASKS].count_documents({
        "organization_id": org_id,
        "status": "sent",
        "sent_at": {"$gte": month_start_iso},
    })


async def _has_rebooked(db, org_id: str, phone: str, completed_at: str, source_apt_id: str) -> bool:
    """Son Dakika Kalkanı: müşteri tamamlanan randevudan SONRA yeni (iptal olmayan)
    bir randevu oluşturmuş mu? Telefon eşleşmesi son 9 haneyle yapılır."""
    tail = re.sub(r"\D", "", phone or "")[-9:]
    if not tail:
        return False
    q = {
        "organization_id": org_id,
        "phone": {"$regex": f"{re.escape(tail)}$"},
        "created_at": {"$gt": completed_at},
        "id": {"$ne": source_apt_id},
        "status": {"$nin": list(_CANCELLED_STATUSES)},
    }
    return (await db.appointments.count_documents(q)) > 0


async def dispatch_tasks(db) -> Dict[str, int]:
    """Zamanı gelen görevleri işler. İstatistik döner."""
    stats = {"sent": 0, "skipped": 0, "expired": 0, "failed": 0, "capped": 0}
    today = datetime.now(TZ).date()
    today_iso = today.isoformat()

    for settings in await _enabled_orgs(db):
        org_id = settings.get("organization_id")
        slug = settings.get("slug")
        company_name = settings.get("company_name") or "İşletmeniz"
        sector = settings.get("sector")
        if not org_id or not slug:
            # slug yoksa public booking linki üretilemez → bu org'u atla.
            continue

        cap = await _monthly_cap(db, org_id)
        sent = await _sent_this_month(db, org_id)
        remaining = cap - sent
        if remaining <= 0:
            stats["capped"] += 1
            continue

        due = await db[TASKS].find({
            "organization_id": org_id,
            "status": "pending",
            "scheduled_for": {"$lte": today_iso},
        }, {"_id": 0}).sort("scheduled_for", 1).to_list(2000)

        for task in due:
            if remaining <= 0:
                stats["capped"] += 1
                break
            task_id = task.get("id")
            try:
                # Bayat görev? (çok gecikmiş) → gönderme, expired işaretle.
                sched = datetime.fromisoformat(task["scheduled_for"]).date()
                if today > sched + timedelta(days=TASK_EXPIRE_DAYS):
                    await db[TASKS].update_one(
                        {"id": task_id},
                        {"$set": {"status": "skipped", "skip_reason": "expired",
                                  "resolved_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    stats["expired"] += 1
                    continue

                # Son Dakika Kalkanı
                if await _has_rebooked(db, org_id, task["phone"], task["completed_at"], task["appointment_id"]):
                    await db[TASKS].update_one(
                        {"id": task_id},
                        {"$set": {"status": "skipped", "skip_reason": "rebooked",
                                  "resolved_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    stats["skipped"] += 1
                    continue

                # Gönderim (mesaj metni günü İÇERMEZ; gün yalnızca ZAMANLAMAYI belirler)
                from whatsapp_service import send_reactivation_template
                import asyncio
                msg_id = await asyncio.to_thread(
                    send_reactivation_template,
                    task["phone"], task.get("customer_name") or "",
                    company_name, slug, sector,
                )
                await db[TASKS].update_one(
                    {"id": task_id},
                    {"$set": {"status": "sent", "wa_message_id": msg_id,
                              "sent_at": datetime.now(timezone.utc).isoformat()}},
                )
                stats["sent"] += 1
                remaining -= 1
            except Exception as e:
                retry = int(task.get("retry_count", 0)) + 1
                new_status = "failed" if retry >= MAX_RETRIES else "pending"
                await db[TASKS].update_one(
                    {"id": task_id},
                    {"$set": {"status": new_status, "last_error": str(e)[:400],
                              "retry_count": retry,
                              "last_retry_at": datetime.now(timezone.utc).isoformat()}},
                )
                stats["failed"] += 1
                logger.warning("autopilot send failed org=%s task=%s: %s", org_id, task_id, e)

    if any(stats.values()):
        logger.info("autopilot dispatch: %s", stats)
    return stats


async def get_org_stats(db, org_id: str) -> Dict[str, Any]:
    """UI için özet: kuyruktaki, bu ay gönderilen ve aylık tavan."""
    pending = await db[TASKS].count_documents({"organization_id": org_id, "status": "pending"})
    sent_month = await _sent_this_month(db, org_id)
    cap = await _monthly_cap(db, org_id)
    return {
        "queued": pending,
        "sent_this_month": sent_month,
        "monthly_cap": cap,
    }


# ---------------------------------------------------------------------------
# Cron kaydı
# ---------------------------------------------------------------------------

def register_autopilot_jobs(scheduler, db, redis_client=None) -> None:
    """APScheduler'a enqueue (saatlik) + dispatch (günlük 11:00 Istanbul) işlerini kaydeder."""
    if not MARKETING_AUTOPILOT_ENABLED:
        logger.info("Pazarlama Otopilotu global olarak KAPALI (MARKETING_AUTOPILOT_ENABLED).")
        return

    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger

    async def _enqueue_job():
        if not await _acquire_lock(redis_client, "enqueue"):
            return
        try:
            await enqueue_tasks(db)
        except Exception as e:
            logger.error("autopilot enqueue job hata: %s", e, exc_info=True)

    async def _dispatch_job():
        if not await _acquire_lock(redis_client, "dispatch"):
            return
        try:
            await dispatch_tasks(db)
        except Exception as e:
            logger.error("autopilot dispatch job hata: %s", e, exc_info=True)

    scheduler.add_job(
        _enqueue_job, IntervalTrigger(minutes=ENQUEUE_INTERVAL_MIN),
        id="marketing_autopilot_enqueue", replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        _dispatch_job, CronTrigger(hour=DISPATCH_HOUR, minute=0, timezone=TZ),
        id="marketing_autopilot_dispatch", replace_existing=True, max_instances=1,
    )
    logger.info("✅ Pazarlama Otopilotu cron kaydedildi (enqueue saatlik / dispatch %02d:00 Istanbul)", DISPATCH_HOUR)
