"""Pure builders for Live Activity content state and APS payloads (no DB, no network)."""

import json
from datetime import datetime
from typing import Literal

from .phase import Phase

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
    """`settings.lock_screen_name_mode` as stored by the tenant; anything unknown is "initials"."""
    return mode if mode in NAME_MODES else "initials"


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


def relevance(phase: Phase, start: datetime, now: datetime) -> float:
    if phase is Phase.PROCESSING:
        return 100
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
