"""
PLANN Asistan — Analytics Engine (Katman 1)

Ham günlük veriyi toplar (ciro, randevu, yeni müşteri, boomerang, doluluk%,
kesintisiz boşluk). Profil/ton mantığı İÇERMEZ — sadece sayılar.

Multi-tenant: her sorgu organization_id ile filtrelenir.
Tüm tarih hesapları Europe/Istanbul üzerinden yapılır.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")

# Randevu durumları (proje kuralı: Türkçe)
CANCELLED_STATUSES = {"İptal", "İptal Edildi", "Cancelled", "Canceled"}
NOSHOW_STATUSES = {"Gelmedi"}
PENDING_PAYMENT_STATUSES = {"Ödeme Bekleniyor"}
COMPLETED_STATUSES = {"Tamamlandı"}
# "Aktif" = iptal/no-show/ödeme bekleyen DIŞINDAKİ tüm randevular.
INACTIVE_STATUSES = CANCELLED_STATUSES | NOSHOW_STATUSES | PENDING_PAYMENT_STATUSES

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_DURATION_MIN = 30


def _to_minutes(hhmm) -> int:
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _minutes_to_hhmm(mins: int) -> str:
    mins = max(0, int(mins))
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _duration(apt) -> int:
    d = apt.get("service_duration")
    try:
        d = int(d)
        return d if d > 0 else DEFAULT_DURATION_MIN
    except (TypeError, ValueError):
        return DEFAULT_DURATION_MIN


def _business_hours_for(settings: dict, day_name: str):
    """(is_open, open_min, close_min) döner."""
    bh = (settings or {}).get("business_hours") or {}
    day = bh.get(day_name) or {}
    is_open = day.get("is_open", True)
    open_str = day.get("open_time", "09:00")
    close_str = day.get("close_time", "18:00")
    open_min = _to_minutes(open_str)
    close_min = _to_minutes(close_str)
    if close_min == 0:  # "00:00" = gün sonu
        close_min = 24 * 60
    if close_min <= open_min:
        close_min = open_min + 8 * 60
    return bool(is_open), open_min, close_min


async def _working_staff_count(db, org_id: str, settings: dict, day_name: str) -> int:
    """O gün çalışan (izinli olmayan) hizmet veren personel sayısı (min 1)."""
    admin_provides = (settings or {}).get("admin_provides_service", True)
    users = await db.users.find(
        {"organization_id": org_id},
        {"_id": 0, "role": 1, "days_off": 1},
    ).to_list(1000)
    count = 0
    for u in users:
        role = u.get("role")
        if role in ("superadmin", "marketing"):
            continue
        if role == "admin" and not admin_provides:
            continue
        if day_name in (u.get("days_off") or []):
            continue
        count += 1
    return max(1, count)


def _merge_intervals(intervals):
    """[(start,end)] listesini birleştirip sıralı, çakışmasız döner."""
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _largest_gap(busy, open_min, close_min):
    """
    Meşgul aralıkların TAMAMLAYICISINDAKI en büyük boşluğu döner.
    "Boşluk" = dükkanda HİÇ randevu olmayan (bütün koltuklar boş) süre.
    Döner: (gap_start, gap_end, gap_minutes) veya None.
    """
    free = []
    cursor = open_min
    for s, e in busy:
        s = max(s, open_min)
        e = min(e, close_min)
        if s > cursor:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < close_min:
        free.append((cursor, close_min))
    if not free:
        return None
    best = max(free, key=lambda iv: iv[1] - iv[0])
    return best[0], best[1], best[1] - best[0]


async def collect_daily_metrics(db, org_id: str, settings: dict, date_str: str) -> dict:
    """
    Belirli bir gün (YYYY-MM-DD) için ham metrikleri toplar.

    Döner (özet):
      total_appointments, completed_count, cancelled_count, noshow_count,
      revenue_completed, revenue_scheduled, new_customers, returning_customers,
      boomerang_customers, returning_fraction, unique_customers,
      first_appointment_time, fullness_pct, has_gap, gap_start/gap_end/gap_minutes,
      gap_type ('early'|'late'), lead_time_minutes
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = DAY_NAMES[d.weekday()]
    except Exception:
        day_name = "monday"

    appts = await db.appointments.find(
        {"organization_id": org_id, "appointment_date": date_str},
        {"_id": 0, "status": 1, "appointment_time": 1, "service_duration": 1,
         "service_price": 1, "phone": 1, "service_name": 1},
    ).to_list(3000)

    active = [a for a in appts if (a.get("status") or "") not in INACTIVE_STATUSES]
    completed = [a for a in active if (a.get("status") or "") in COMPLETED_STATUSES]

    total_appointments = len(active)
    completed_count = len(completed)
    cancelled_count = sum(1 for a in appts if (a.get("status") or "") in CANCELLED_STATUSES)
    noshow_count = sum(1 for a in appts if (a.get("status") or "") in NOSHOW_STATUSES)

    revenue_completed = sum(float(a.get("service_price") or 0) for a in completed)
    revenue_scheduled = sum(float(a.get("service_price") or 0) for a in active)

    # İlk randevu saati
    times = sorted([a.get("appointment_time") for a in active if a.get("appointment_time")])
    first_time = times[0] if times else None

    # Müşteri kırılımı (yeni / dönen / boomerang)
    phones = {(a.get("phone") or "").strip() for a in active if (a.get("phone") or "").strip()}
    new_customers = returning_customers = boomerang_customers = 0
    for ph in phones:
        prev = await db.appointments.find(
            {
                "organization_id": org_id,
                "phone": ph,
                "appointment_date": {"$lt": date_str},
                "status": {"$nin": list(CANCELLED_STATUSES)},
            },
            {"_id": 0, "appointment_date": 1},
        ).sort("appointment_date", -1).to_list(1)
        if not prev:
            new_customers += 1
            continue
        returning_customers += 1
        try:
            gap_days = (d - datetime.strptime(prev[0].get("appointment_date"), "%Y-%m-%d")).days
        except Exception:
            gap_days = 0
        from .scenarios import BOOMERANG_INACTIVE_DAYS
        if gap_days >= BOOMERANG_INACTIVE_DAYS:
            boomerang_customers += 1
    unique_customers = len(phones)
    returning_fraction = (returning_customers / unique_customers) if unique_customers else 0.0

    # Doluluk (kapasite) ve boşluk analizi
    is_open, open_min, close_min = _business_hours_for(settings, day_name)
    staff_count = await _working_staff_count(db, org_id, settings, day_name)
    open_minutes = max(1, close_min - open_min)
    capacity_minutes = staff_count * open_minutes
    booked_minutes = sum(_duration(a) for a in active)
    fullness_pct = round(min(100.0, booked_minutes / capacity_minutes * 100.0), 1) if capacity_minutes else 0.0

    busy = _merge_intervals([
        (_to_minutes(a.get("appointment_time")), _to_minutes(a.get("appointment_time")) + _duration(a))
        for a in active if a.get("appointment_time")
    ])
    gap = _largest_gap(busy, open_min, close_min) if is_open else None

    from .scenarios import MORNING_ANCHOR_MIN, GAP_EARLY_LATE_LEAD_MINUTES, GAP_MIN_MINUTES
    has_gap = bool(gap and gap[2] >= GAP_MIN_MINUTES)
    gap_start = gap[0] if gap else None
    gap_end = gap[1] if gap else None
    gap_minutes = gap[2] if gap else 0
    lead_time = (gap_start - MORNING_ANCHOR_MIN) if gap_start is not None else None
    gap_type = None
    if has_gap:
        gap_type = "early" if (lead_time is not None and lead_time < GAP_EARLY_LATE_LEAD_MINUTES) else "late"

    return {
        "date": date_str,
        "day_name": day_name,
        "is_open": is_open,
        "total_appointments": total_appointments,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "noshow_count": noshow_count,
        "revenue_completed": round(revenue_completed, 2),
        "revenue_scheduled": round(revenue_scheduled, 2),
        # Gece hikâyesinde "ciro" = gerçekleşen; hiç tamamlanmış yoksa planlanan.
        "revenue": round(revenue_completed if revenue_completed > 0 else revenue_scheduled, 2),
        "new_customers": new_customers,
        "returning_customers": returning_customers,
        "boomerang_customers": boomerang_customers,
        "unique_customers": unique_customers,
        "returning_fraction": round(returning_fraction, 3),
        "first_appointment_time": first_time,
        "staff_count": staff_count,
        "capacity_minutes": capacity_minutes,
        "booked_minutes": booked_minutes,
        "fullness_pct": fullness_pct,
        "open_time": _minutes_to_hhmm(open_min),
        "close_time": _minutes_to_hhmm(close_min),
        "has_gap": has_gap,
        "gap_start": _minutes_to_hhmm(gap_start) if gap_start is not None else None,
        "gap_end": _minutes_to_hhmm(gap_end) if gap_end is not None else None,
        "gap_minutes": gap_minutes,
        "gap_type": gap_type,
        "lead_time_minutes": lead_time,
    }


async def revenue_on_date(db, org_id: str, date_str: str) -> float:
    """Tek günün gerçekleşen (Tamamlandı) cirosu — baseline hesapları için."""
    appts = await db.appointments.find(
        {"organization_id": org_id, "appointment_date": date_str, "status": "Tamamlandı"},
        {"_id": 0, "service_price": 1},
    ).to_list(3000)
    return round(sum(float(a.get("service_price") or 0) for a in appts), 2)


async def service_revenue_between(db, org_id: str, start_str: str, end_str: str) -> dict:
    """[start,end] (dahil) aralığında hizmet adı → gerçekleşen ciro sözlüğü."""
    appts = await db.appointments.find(
        {
            "organization_id": org_id,
            "appointment_date": {"$gte": start_str, "$lte": end_str},
            "status": "Tamamlandı",
        },
        {"_id": 0, "service_name": 1, "service_price": 1},
    ).to_list(10000)
    agg = {}
    for a in appts:
        name = (a.get("service_name") or "Hizmet").strip() or "Hizmet"
        agg[name] = agg.get(name, 0.0) + float(a.get("service_price") or 0)
    return agg


async def collect_week_metrics(db, org_id: str, settings: dict, week_start_str: str, week_end_str: str) -> dict:
    """
    Haftalık toplu metrik (Pazartesi–Pazar). Günlük metriklerin toplamı +
    hizmet bazlı ciro kırılımı (haftalık "neden" analizi için).
    """
    start = datetime.strptime(week_start_str, "%Y-%m-%d")
    end = datetime.strptime(week_end_str, "%Y-%m-%d")

    total_appointments = new_customers = boomerang_customers = 0
    revenue = 0.0
    cursor = start
    while cursor <= end:
        ds = cursor.strftime("%Y-%m-%d")
        m = await collect_daily_metrics(db, org_id, settings, ds)
        total_appointments += m["total_appointments"]
        new_customers += m["new_customers"]
        boomerang_customers += m["boomerang_customers"]
        revenue += m["revenue_completed"]
        cursor += timedelta(days=1)

    service_rev = await service_revenue_between(db, org_id, week_start_str, week_end_str)
    return {
        "week_start": week_start_str,
        "week_end": week_end_str,
        "total_appointments": total_appointments,
        "new_customers": new_customers,
        "boomerang_customers": boomerang_customers,
        "revenue": round(revenue, 2),
        "revenue_completed": round(revenue, 2),
        "service_revenue": service_rev,
    }
