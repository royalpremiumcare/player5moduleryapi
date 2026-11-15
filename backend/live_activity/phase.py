"""Derive a Live Activity phase for an appointment from its stored fields and the clock."""

from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

TR_TZ = ZoneInfo("Europe/Istanbul")

DEFAULT_DURATION_MIN = 30
CANCELLED_STATUSES = {"İptal", "İptal Edildi", "Cancelled"}
PAYMENT_PENDING_STATUS = "Ödeme Bekleniyor"
COMPLETED_STATUS = "Tamamlandı"


class Phase(str, Enum):
    UPCOMING = "upcoming"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REMOVED = "removed"
    INELIGIBLE = "ineligible"


def resolve_duration(apt: dict, services_by_id: dict[str, int]) -> int:
    """Appointment's own duration, else its service's duration, else the default."""
    return apt.get("service_duration") or services_by_id.get(apt.get("service_id")) or DEFAULT_DURATION_MIN


def appointment_window(
    apt: dict, duration_min: int, tz: ZoneInfo = TR_TZ
) -> tuple[datetime, datetime]:
    """Start and end of the appointment in ``tz``. Raises ValueError on malformed date/time."""
    start = datetime.strptime(f"{apt['appointment_date']} {apt['appointment_time']}", "%Y-%m-%d %H:%M")
    start = start.replace(tzinfo=tz)
    return start, start + timedelta(minutes=duration_min)


def compute_phase(
    apt: dict | None, now: datetime, duration_min: int, tz: ZoneInfo = TR_TZ
) -> Phase:
    if apt is None:
        return Phase.REMOVED
    status = apt.get("status")
    if status in CANCELLED_STATUSES:
        return Phase.CANCELLED
    if status == PAYMENT_PENDING_STATUS:
        return Phase.INELIGIBLE
    if status == COMPLETED_STATUS:
        return Phase.COMPLETED
    start, end = appointment_window(apt, duration_min, tz)
    if now < start:
        return Phase.UPCOMING
    if now < end:
        return Phase.PROCESSING
    return Phase.COMPLETED
