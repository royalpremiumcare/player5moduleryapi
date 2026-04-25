"""
Paket kalan seansları — haftalık hedef + dalga (wave) saat sırası + personel fallback.

- Takvim adayı ızgarası: 15 dk (09:00, 09:15, 09:30, …).
- İki turlu dalga: önce hizmet süresi adımı (temiz bloklar), sonra 15 dk adımı (kalan tüm grid).
- Önce hedef gün + hedef saatte (anchor) tüm personel sırayla; olmazsa wave taraması.
- Döngü: dış dalga SAAT, iç PERSONEL (aynı saatte A doluysa B).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# İşletme takvim tabanı — randevu başlangıç adayları 15 dakika aralıklıdır.
CALENDAR_GRID_MINUTES = 15

MAX_DAY_OFFSET = 7

DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _time_to_minutes(time_str: str) -> int:
    try:
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    except (ValueError, AttributeError):
        return 0


def _minutes_to_time(total: int) -> str:
    h = total // 60
    m = total % 60
    return f"{str(h).zfill(2)}:{str(m).zfill(2)}"


def _normalize_time(t: str) -> str:
    if not t or not isinstance(t, str):
        return "10:00"
    p = t.strip().split(":")
    h = min(23, max(0, int(p[0]) if p[0] else 0))
    m = min(59, max(0, int(p[1]) if len(p) > 1 else 0))
    return f"{str(h).zfill(2)}:{str(m).zfill(2)}"


def _symmetric_slots_from_anchor(
    eff: int,
    s_set: set,
    step: int,
) -> List[int]:
    """eff etrafında step adımıyla simetrik sıra (yalnızca s_set içindeki dakikalar)."""
    step = max(5, min(180, int(step)))
    out: List[int] = []
    seen = set()

    def add(m: int) -> None:
        if m in s_set and m not in seen:
            out.append(m)
            seen.add(m)

    add(eff)

    max_i = (24 * 60) // step + 2
    for i in range(1, max_i):
        back = eff - i * step
        fwd = eff + i * step
        add(back)
        add(fwd)
        if len(seen) >= len(s_set):
            break

    return out


def order_slots_around_anchor_symmetric(
    anchor_min: int,
    slot_mins: List[int],
    primary_wave_step: int,
) -> List[int]:
    """
    İki turlu (Primary + Secondary) simetrik dalga birleştirmesi.

    Tur 1 — öncelik: primary_wave_step = hizmet süresi (örn. 30 dk).
      Örn: 12:00, 11:30, 12:30, 11:00, 13:00, …

    Tur 2 — tam tarama: CALENDAR_GRID_MINUTES (15 dk) ile ikinci simetrik liste.
      Örn: 12:00, 11:45, 12:15, 11:30, 12:30, …

    Birleştirme: önce Tur 1 sırası; ardından Tur 2'de olup Tur 1'de olmayanlar (sıra korunur).
    """
    s_set = set(x for x in slot_mins if isinstance(x, int))
    if not s_set:
        return []

    primary_wave_step = max(5, min(180, int(primary_wave_step)))

    if anchor_min in s_set:
        eff = anchor_min
    else:
        eff = min(s_set, key=lambda x: abs(x - anchor_min))

    tur1 = _symmetric_slots_from_anchor(eff, s_set, primary_wave_step)
    seen_primary = set(tur1)

    tur2 = _symmetric_slots_from_anchor(eff, s_set, CALENDAR_GRID_MINUTES)

    out = list(tur1)
    for m in tur2:
        if m not in seen_primary:
            out.append(m)
            seen_primary.add(m)

    return out


def _day_config_for_date(business_hours: dict, date_str: str) -> Optional[Dict[str, Any]]:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    idx = d.weekday()
    day_name = DAY_NAMES[idx]
    raw = business_hours.get(day_name) or {}
    if raw.get("enabled") is False or raw.get("is_open") is False:
        return None
    start = raw.get("start") or raw.get("open_time") or "09:00"
    end = raw.get("end") or raw.get("close_time") or "18:00"
    return {"start": start, "end": end}


def _add_days_iso(date_str: str, delta: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=delta)
    return d.strftime("%Y-%m-%d")


def _slot_starts_for_day(
    start_str: str,
    end_str: str,
    service_duration: int,
    grid_minutes: int = CALENDAR_GRID_MINUTES,
) -> List[int]:
    """
    Olası başlangıç dakikaları — işletme açılışından itibaren SABİT 15 dk ızgarası.
    (09:00, 09:15, 09:30, …) — kapanışa kadar; t + service_duration <= kapanış.
    """
    open_m = _time_to_minutes(start_str)
    close_m = _time_to_minutes(end_str)
    if close_m <= open_m:
        return []
    step = max(5, min(60, int(grid_minutes)))
    out: List[int] = []
    t = open_m
    while t + service_duration <= close_m:
        out.append(t)
        t += step
    return out


async def plan_wave_remaining_sessions(
    db,
    organization_id: str,
    service_id: str,
    first_session_date: str,
    first_session_time: str,
    remaining_count: int,
    settings: dict,
    staff_members: List[dict],
    preferred_staff_username: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    import server as srv  # noqa: WPS433

    service = await db.services.find_one(
        {"id": service_id, "organization_id": organization_id},
        {"_id": 0, "duration": 1},
    )
    if not service:
        return [], remaining_count

    service_duration = int(service.get("duration", 30) or 30)
    business_hours = settings.get("business_hours") or settings.get("working_hours") or {}

    eligible = list(staff_members or [])
    if preferred_staff_username:
        eligible.sort(
            key=lambda u: (0 if u.get("username") == preferred_staff_username else 1, u.get("username") or "")
        )

    anchor_time_norm = _normalize_time(first_session_time)
    anchor_min = _time_to_minutes(anchor_time_norm)

    # Simetrik dalga atlama adımı = hizmet süresi (15 dk takvim ızgarasından bağımsız).
    wave_step = max(5, min(180, service_duration))

    results: List[Dict[str, Any]] = []
    unplanned = 0

    for k in range(remaining_count):
        target_date = _add_days_iso(first_session_date, 7 * (k + 1))
        placed = False

        for day_offset in range(MAX_DAY_OFFSET):
            probe_date = _add_days_iso(target_date, day_offset)
            day_cfg = _day_config_for_date(business_hours, probe_date)
            if not day_cfg:
                continue

            slot_mins = _slot_starts_for_day(
                day_cfg["start"],
                day_cfg["end"],
                service_duration,
                CALENDAR_GRID_MINUTES,
            )
            if not slot_mins:
                continue

            close_m = _time_to_minutes(day_cfg["end"])
            preferred_min = anchor_min
            tried_preferred = preferred_min in slot_mins

            async def try_staff_at_minute(sm: int) -> bool:
                if sm + service_duration > close_m:
                    return False
                t_str = _minutes_to_time(sm)
                e_str = _minutes_to_time(sm + service_duration)
                for staff in eligible:
                    sid = staff.get("username")
                    if not sid:
                        continue
                    try:
                        wd = datetime.strptime(probe_date, "%Y-%m-%d").weekday()
                        day_nm = DAY_NAMES[wd]
                        if day_nm in (staff.get("days_off") or []):
                            continue
                    except ValueError:
                        pass
                    st_busy = await srv._check_slot_conflict(
                        db, organization_id, sid, probe_date, t_str, service_duration
                    )
                    if st_busy:
                        continue
                    has_brk = await srv.check_break_conflict(
                        db, sid, probe_date, t_str, e_str, organization_id
                    )
                    if has_brk:
                        continue
                    results.append(
                        {
                            "date": probe_date,
                            "time": t_str,
                            "staff_member_id": sid,
                        }
                    )
                    return True
                return False

            # Tur A: hedef saat (anchor) — önce saat değiştirmeden tüm eligible personel
            if tried_preferred:
                placed = await try_staff_at_minute(preferred_min)
            else:
                placed = False

            # Tur B: dalga — anchor doluysa veya grid dışındaysa simetrik tarama
            if not placed:
                if tried_preferred:
                    logger.info(
                        "Conflict found on %s, starting wave search (anchor=%s)...",
                        probe_date,
                        _minutes_to_time(preferred_min),
                    )
                else:
                    logger.info(
                        "Preferred time outside grid on %s, starting wave search...",
                        probe_date,
                    )

                wave = order_slots_around_anchor_symmetric(anchor_min, slot_mins, wave_step)
                for sm in wave:
                    if tried_preferred and sm == preferred_min:
                        continue
                    placed = await try_staff_at_minute(sm)
                    if placed:
                        break

            if placed:
                break

        if not placed:
            unplanned += 1
            results.append(
                {
                    "date": None,
                    "time": None,
                    "staff_member_id": None,
                    "unplanned": True,
                }
            )

    return results, unplanned
