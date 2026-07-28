"""
PLANN Asistan — Notification Engine (Katman 3)

Health Engine'in ürettiği karar paketini alır:
  1) organizasyonun profilini (ses tonu) sector'den türetir,
  2) uygun metin havuzundan son 5 günde KULLANILMAMIŞ bir varyasyon seçer,
  3) placeholder'ları senaryo-bilinçli (aliasing) doldurur,
  4) push bildirimi gönderir (tap → Dashboard deep-link),
  5) gönderimi assistant_notifications'a kaydeder (dedup + geçmiş).

Push gönderimi server.send_push_notification üzerinden yapılır (lazy import,
döngüsel bağımlılığı önlemek için).
"""

import re
import random
import logging
import uuid
from datetime import datetime, timedelta, timezone

from .scenarios import resolve_profile, is_sincere, PROFILE_FALLBACK, randevu_sayisi_source

logger = logging.getLogger(__name__)

DEDUP_WINDOW_DAYS = 5
PUSH_TITLE = "PLANN Asistan"


def _lazy_push_fn():
    from server import send_push_notification
    return send_push_notification


def _format_try(value) -> str:
    """12000.0 → '12.000' (Türkçe binlik ayraç, kuruş yok)."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = 0
    return f"{n:,}".replace(",", ".")


def _format_name(full_name: str, username: str, profile: str) -> str:
    """
    SINCERE_* → sadece İSİM (ilk kelime). "tatlım/şef" ile birlikte kullanılır.
    PROFESSIONAL → SOYİSİM (son kelime); metinde zaten "Sayın {isim}" geçer.
    """
    name = (full_name or "").strip()
    if not name:
        # Kullanıcı adı (genelde email) — profesyonelde riskli, boş bırak.
        return "" if not is_sincere(profile) else (username or "").split("@")[0]
    parts = [p for p in name.split() if p]
    if not parts:
        return name
    return parts[0] if is_sincere(profile) else parts[-1]


def _safe_format(text: str, mapping: dict) -> str:
    """{key} sadece bilinen anahtarlar için değiştirilir; bilinmeyen aynen kalır."""
    def repl(m):
        k = m.group(1)
        return str(mapping[k]) if k in mapping and mapping[k] is not None else m.group(0)
    return re.sub(r"\{(\w+)\}", repl, text)


async def _recent_used_message_ids(db, org_id: str, scenario: str, ref_date: datetime):
    cutoff = (ref_date - timedelta(days=DEDUP_WINDOW_DAYS)).isoformat()
    rows = await db.assistant_notifications.find(
        {"organization_id": org_id, "scenario": scenario, "sent_at": {"$gte": cutoff}},
        {"_id": 0, "message_id": 1},
    ).to_list(200)
    return {r.get("message_id") for r in rows if r.get("message_id")}


async def _select_message(db, org_id: str, scenario: str, lang: str, profile: str, ref_date: datetime):
    """
    Profil çuvalından (fallback sırasıyla) son 5 günde kullanılmamış bir metin seç.
    Hepsi kullanıldıysa tüm havuzdan rastgele seçime izin ver.
    """
    used = await _recent_used_message_ids(db, org_id, scenario, ref_date)
    for prof in PROFILE_FALLBACK.get(profile, [profile]):
        candidates = await db.assistant_messages.find(
            {"scenario": scenario, "lang": lang, "profile": prof, "is_active": True},
            {"_id": 0, "id": 1, "text": 1, "variation_index": 1},
        ).to_list(200)
        if not candidates:
            continue
        fresh = [c for c in candidates if c.get("id") not in used]
        pool = fresh if fresh else candidates
        chosen = random.choice(pool)
        chosen["_profile_used"] = prof
        chosen["_recycled"] = not bool(fresh)
        return chosen
    return None


def build_placeholders(scenario: str, metrics: dict, packet: dict, name: str) -> dict:
    """
    Placeholder → değer eşlemesi. {randevu_sayisi} senaryoya göre aliaslanır.
    """
    src = randevu_sayisi_source(scenario)
    randevu_sayisi = metrics.get(src, metrics.get("total_appointments", 0))

    insight = packet.get("insight") or {}
    gap = packet.get("gap_details") or {}

    return {
        "isim": name,
        "randevu_sayisi": randevu_sayisi,
        "ilk_randevu_saati": metrics.get("first_appointment_time") or "—",
        "ciro": _format_try(metrics.get("revenue", 0)),
        "hizmet_adi": insight.get("service_name") or "hizmetleriniz",
        "oran": insight.get("rate_pct", 0),
        "bos_baslangic": gap.get("gap_start") or "—",
        "bos_bitis": gap.get("gap_end") or "—",
    }


async def get_owner_user(db, org_id: str):
    """Bildirim alıcısı: organizasyon sahibi (admin rolü)."""
    return await db.users.find_one(
        {"organization_id": org_id, "role": "admin"},
        {"_id": 0, "username": 1, "full_name": 1},
    )


async def process_and_notify(db, org_id: str, settings: dict, period: str,
                             metrics: dict, packet: dict, date_str: str,
                             push_fn=None, dry_run: bool = False,
                             ref_now: datetime = None) -> dict:
    """
    Karar paketini bildirime çevirip gönderir. dry_run=True → sadece önizleme.
    """
    ref_now = ref_now or datetime.now(timezone.utc)
    profile = resolve_profile((settings or {}).get("sector"))
    scenario = packet["scenario"]
    lang = "tr"

    owner = await get_owner_user(db, org_id)
    if not owner:
        return {"status": "skipped", "reason": "no_admin", "scenario": scenario}

    name = _format_name(owner.get("full_name"), owner.get("username"), profile)
    msg = await _select_message(db, org_id, scenario, lang, profile, ref_now)
    if not msg:
        return {"status": "skipped", "reason": "no_message", "scenario": scenario, "profile": profile}

    placeholders = build_placeholders(scenario, metrics, packet, name)
    text = _safe_format(msg["text"], placeholders).strip()

    data = {
        "type": "assistant",
        "action": "OPEN_DASHBOARD",
        "period": period,
        "scenario": scenario,
    }

    result = {
        "status": "previewed" if dry_run else "sent",
        "period": period,
        "scenario": scenario,
        "profile": profile,
        "profile_used": msg.get("_profile_used"),
        "message_id": msg.get("id"),
        "recycled": msg.get("_recycled", False),
        "user_id": owner.get("username"),
        "title": PUSH_TITLE,
        "text": text,
        "day_context": packet.get("day_context"),
        "health_score": packet.get("health_score"),
        "confidence_score": packet.get("confidence_score"),
    }

    if dry_run:
        return result

    try:
        fn = push_fn or _lazy_push_fn()
        await fn(db, org_id, PUSH_TITLE, text, data, user_id=owner.get("username"))
    except Exception as e:
        logger.error("Assistant push failed org=%s scenario=%s: %s", org_id, scenario, e, exc_info=True)
        result["status"] = "push_error"
        result["error"] = str(e)

    try:
        await db.assistant_notifications.insert_one({
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "user_id": owner.get("username"),
            "period": period,
            "scenario": scenario,
            "profile": profile,
            "message_id": msg.get("id"),
            "text": text,
            "date": date_str,
            "day_context": packet.get("day_context"),
            "health_score": packet.get("health_score"),
            "confidence_score": packet.get("confidence_score"),
            "primary_metric": packet.get("primary_metric"),
            "insight_reason": packet.get("insight_reason"),
            "status": result["status"],
            "sent_at": ref_now.isoformat(),
        })
    except Exception as e:
        logger.error("Assistant notification log failed org=%s: %s", org_id, e)

    return result
