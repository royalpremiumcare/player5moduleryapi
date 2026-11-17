"""Carry service renames and customer edits onto the appointments that show them.

Appointments keep their own copy of the service name (``service_name`` plus a
``name_snapshot`` per line in ``services``) and of the customer's name/phone, so
editing a service or customer does not reach them by itself. These helpers write
the change through in a few org-scoped ``update_many`` calls and then emit the
org's existing bulk appointment event, which open dashboards reload on and which
``emit_to_organization`` uses to resync Live Activity cards.
"""

import logging
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TR_TZ = ZoneInfo("Europe/Istanbul")

# Listened to by App.js and Dashboard.js (reload appointments + stats) and in the
# Live Activity change hook inside server.emit_to_organization.
APPOINTMENTS_CHANGED_EVENT = "appointments_bulk_updated"

# Finished appointments keep the name they were done under (revenue/history).
# Both the Turkish and English UI status strings are stored.
FINISHED_STATUSES = ["Tamamlandı", "Completed", "İptal", "İptal Edildi", "Cancelled"]

# Same separator resolve_services() uses for a multi-service appointment's name.
SERVICE_NAME_SEPARATOR = " + "


def istanbul_today(now: datetime | None = None) -> str:
    """Today's date in Istanbul as the ``YYYY-MM-DD`` string appointments store."""
    return (now or datetime.now(TR_TZ)).astimezone(TR_TZ).strftime("%Y-%m-%d")


async def _emit_safely(emit, org_id: str, data: dict) -> None:
    try:
        await emit(org_id, APPOINTMENTS_CHANGED_EVENT, data)
    except Exception as exc:  # a socket problem must not fail the edit itself
        logger.warning("appointment change event for org %s failed: %s", org_id, exc)


async def propagate_service_rename(db, org_id: str, service_id: str, new_name: str, *,
                                   emit, today: str | None = None) -> list[str]:
    """Rename ``service_id`` on the org's active appointments dated today or later.

    Past, completed and cancelled appointments keep the old name. Multi-service
    appointments get the matching line renamed and their combined name rebuilt the
    way creation builds it. Returns the ids of the appointments that changed and
    emits one org event when there are any.
    """
    active = {
        "organization_id": org_id,
        "appointment_date": {"$gte": today or istanbul_today()},
        "status": {"$nin": FINISHED_STATUSES},
    }
    candidates = await db.appointments.find(
        {**active, "$or": [{"service_id": service_id}, {"services.service_id": service_id}]},
        {"_id": 0, "id": 1, "service_id": 1, "service_name": 1, "services": 1},
    ).to_list(None)

    # (new combined name, has a services line to rename) -> appointment ids
    groups: dict[tuple[str, bool], list[str]] = defaultdict(list)
    for apt in candidates:
        lines = apt.get("services") or []
        if any(line.get("service_id") == service_id for line in lines):
            name = SERVICE_NAME_SEPARATOR.join(
                new_name if line.get("service_id") == service_id else (line.get("name_snapshot") or "")
                for line in lines
            )
            groups[(name, True)].append(apt["id"])
        elif not lines and apt.get("service_id") == service_id:  # pre-multi-service appointment
            groups[(new_name, False)].append(apt["id"])

    changed: list[str] = []
    for (name, has_lines), ids in groups.items():
        update = {"$set": {"service_name": name}}
        kwargs = {}
        if has_lines:
            update["$set"]["services.$[line].name_snapshot"] = new_name
            kwargs["array_filters"] = [{"line.service_id": service_id}]
        await db.appointments.update_many({**active, "id": {"$in": ids}}, update, **kwargs)
        changed.extend(ids)

    if changed:
        await _emit_safely(emit, org_id, {
            "reason": "service_renamed", "service_id": service_id, "appointment_ids": changed,
        })
    return changed


async def sync_customer_to_appointments(db, org_id: str, phone: str, *, new_phone: str | None = None,
                                        new_name: str | None = None, emit) -> int:
    """Copy a customer's new phone and/or name onto all of their appointments in the org.

    Emits one org event when any appointment changed. Returns how many changed
    (an appointment whose phone and name both changed counts once).
    """
    modified = 0
    match_phone = phone
    if new_phone and new_phone != phone:
        res = await db.appointments.update_many(
            {"phone": phone, "organization_id": org_id}, {"$set": {"phone": new_phone}}
        )
        modified += res.modified_count
        match_phone = new_phone
    if new_name:
        res = await db.appointments.update_many(
            {"phone": match_phone, "organization_id": org_id}, {"$set": {"customer_name": new_name}}
        )
        modified = max(modified, res.modified_count)  # same appointments; count each once
    if modified:
        await _emit_safely(emit, org_id, {"reason": "customer_updated", "updated": modified})
    return modified
