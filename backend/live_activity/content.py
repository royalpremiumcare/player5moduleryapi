"""Pure builders for Live Activity content state and APS payloads (no DB, no network)."""

import json
from datetime import datetime
from typing import Literal

from .phase import TR_TZ, Phase

ALERT_START = ("Sıradaki randevu", "{name} · {service} · {time}")
ALERT_PROCESSING = ("Randevu başladı", "{name} · {service}")

ATTRIBUTES_TYPE = "PlannAppointmentAttributes"
MAX_PAYLOAD_BYTES = 4096
SERVICE_NAME_MAX = 40
MIN_START_STALE_SECONDS = 60


class PayloadTooLarge(Exception):
    pass


class StaleStartRejected(Exception):
    pass


def _tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def _tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def _capitalize(word: str) -> str:
    return _tr_upper(word[0]) + _tr_lower(word[1:])


NAME_MODES = ("initials", "full", "hidden")


def name_mode(mode) -> Literal["initials", "full", "hidden"]:
    """`settings.lock_screen_name_mode` as stored by the tenant.

    Missing/None means "full" (the default); an explicit "initials"/"hidden" is honoured;
    any other (bogus) string falls back to the privacy-safe "initials".
    """
    if mode is None:
        return "full"
    return mode if mode in NAME_MODES else "initials"


SECTOR_ICONS = {
    "Kuaför": "hair",
    "Güzellik Salonu": "beauty",
    "Masaj / SPA": "spa",
    "Diyetisyen": "diet",
    "Psikolog / Danışmanlık": "therapy",
    "Diş Klinikleri": "dental",
}


def sector_icon(sector: str | None) -> str:
    """Semantic icon token for `settings.sector`; anything unknown/missing is "generic"."""
    return SECTOR_ICONS.get(sector, "generic") if isinstance(sector, str) else "generic"


def display_name(full: str | None, mode: Literal["initials", "full", "hidden"]) -> str | None:
    mode = name_mode(mode)
    words = (full or "").split()
    if mode == "hidden" or not words:
        return None
    if mode == "full":
        return " ".join(_capitalize(w) for w in words)
    if len(words) == 1:
        return _capitalize(words[0])
    return f"{_capitalize(words[0])} {_tr_upper(words[-1][0])}."


def _processing_relevance(start: datetime, end: datetime | None) -> float:
    """100..199, higher for an earlier end; independent of the push time.

    Minutes are counted from the appointment's local (Europe/Istanbul) midnight,
    so an end at/after the next midnight clamps to 1440 and scores the floor, 100.
    """
    if end is None:
        return 100
    midnight = start.astimezone(TR_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    minutes = (end.astimezone(TR_TZ) - midnight).total_seconds() / 60
    minutes = min(max(minutes, 0), 1440)
    return 100 + 99 * (1 - minutes / 1440)


def relevance(phase: Phase, start: datetime, now: datetime, end: datetime | None = None) -> float:
    if phase is Phase.PROCESSING:
        return _processing_relevance(start, end)
    if phase is Phase.UPCOMING:
        minutes_to_start = (start - now).total_seconds() / 60
        return max(1, 50 - minutes_to_start / 10)
    return 0


def build_content_state(
    apt: dict,
    phase: Phase,
    start: datetime,
    end: datetime,
    *,
    privacy_mode: str,
    staff_name: str | None,
    version: int,
    icon: str = "generic",
) -> dict:
    return {
        "phase": phase.value,
        "startEpoch": float(start.timestamp()),
        "endEpoch": float(end.timestamp()),
        "startLabel": apt["appointment_time"],
        "endLabel": end.strftime("%H:%M"),
        "customerDisplay": display_name(apt.get("customer_name"), privacy_mode),
        "serviceName": (apt.get("service_name") or "")[:SERVICE_NAME_MAX],
        "staffName": staff_name,
        "version": version,
        "appointmentId": str(apt["id"]),
        "icon": icon,
    }


def stale_epoch(phase: Phase, start: datetime, end: datetime) -> int | None:
    if phase is Phase.UPCOMING:
        return int(start.timestamp())
    if phase is Phase.PROCESSING:
        return int(end.timestamp())
    return None


def format_alert(kind: Literal["start", "processing"], content: dict) -> tuple[str, str]:
    title, body = ALERT_START if kind == "start" else ALERT_PROCESSING
    name = content.get("customerDisplay")
    if name is None:
        body = body.replace("{name} · ", "")
    return title, body.format(
        name=name, service=content["serviceName"], time=content["startLabel"]
    )


def build_aps(
    event: Literal["start", "update", "end"],
    content: dict,
    *,
    now_epoch: int,
    relevance: float,
    stale_epoch: int | None,
    dismissal_epoch: int | None,
    slot_id: str | None,
    org_id: str | None,
    input_push_token: bool,
) -> dict:
    if event == "start" and (
        stale_epoch is None or stale_epoch - now_epoch < MIN_START_STALE_SECONDS
    ):
        raise StaleStartRejected(f"stale-date {stale_epoch} too close to now {now_epoch}")
    aps: dict = {
        "timestamp": now_epoch,
        "event": event,
        "content-state": content,
        "relevance-score": relevance,
    }
    if stale_epoch is not None:
        aps["stale-date"] = stale_epoch
    if event == "end" and dismissal_epoch is not None:
        aps["dismissal-date"] = dismissal_epoch
    if event == "start":
        aps["attributes-type"] = ATTRIBUTES_TYPE
        aps["attributes"] = {"slotId": slot_id, "orgId": org_id}
        if input_push_token:
            aps["input-push-token"] = 1
    if len(json.dumps(aps, ensure_ascii=False).encode()) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge("APS payload exceeds 4KB")
    return aps
