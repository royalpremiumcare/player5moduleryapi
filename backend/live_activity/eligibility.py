"""Who sees which appointments in a Live Activity, and how many slots it shows."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from .phase import TR_TZ, Phase, appointment_window, compute_phase, resolve_duration

logger = logging.getLogger(__name__)

DEFAULT_SLOT_COUNT = 4
MIN_SLOTS, MAX_SLOTS = 1, 5
DEFAULT_LEAD_MIN = 30
MIN_LEAD_MIN, MAX_LEAD_MIN = 5, 120


@dataclass(frozen=True)
class VisibleAppt:
    id: str
    phase: Phase
    start: datetime
    end: datetime
    apt: dict


def is_manager(user: dict) -> bool:
    return bool(user.get("role") == "staff" and user.get("can_view_all_appointments"))


def effective_scope(
    user: dict, *, admin_provides_service: bool, org_has_staff: bool
) -> Literal["own", "all"]:
    pref = user.get("live_activity_scope")
    if user.get("role") == "admin":
        if not admin_provides_service and not org_has_staff:
            return "all"
        return "own" if pref == "own" else "all"
    if is_manager(user) and pref == "all":
        return "all"
    return "own"


def slot_count(user: dict, scope: str) -> int:
    if scope == "own" or (user.get("role") == "staff" and not is_manager(user)):
        return 1
    n = user.get("live_activity_slot_count")
    n = DEFAULT_SLOT_COUNT if n is None else n
    return max(MIN_SLOTS, min(MAX_SLOTS, n))


def effective_lead_minutes(lead: int | None) -> int:
    if lead is None:
        return DEFAULT_LEAD_MIN
    return max(MIN_LEAD_MIN, min(MAX_LEAD_MIN, lead))


def visible_for_user(
    apts: list[dict],
    user: dict,
    scope: str,
    *,
    now: datetime,
    services_by_id: dict,
    lead_min: int,
    day_open: bool,
    tz: ZoneInfo = TR_TZ,
) -> list[VisibleAppt]:
    is_admin = user.get("role") == "admin"
    today = now.astimezone(tz).date()
    lead = timedelta(minutes=lead_min)
    out: list[VisibleAppt] = []
    for apt in apts:
        if scope == "own":
            sm = apt.get("staff_member_id")
            if not (sm == user.get("username") or (is_admin and not sm)):
                continue
        try:
            duration = resolve_duration(apt, services_by_id)
            start, end = appointment_window(apt, duration, tz)
            phase = compute_phase(apt, now, duration, tz)
        except (KeyError, ValueError) as exc:
            logger.debug("skipping appointment %s: bad date/time (%s)", apt.get("id"), exc)
            continue
        if phase == Phase.PROCESSING:
            pass  # stays visible across midnight
        elif phase == Phase.UPCOMING:
            if start.date() != today:
                continue
            if not day_open and start - lead > now:
                continue
        else:
            continue
        out.append(VisibleAppt(id=apt.get("id"), phase=phase, start=start, end=end, apt=apt))
    out.sort(key=lambda v: (0, v.end) if v.phase == Phase.PROCESSING else (1, v.start))
    return out
