"""Read-only home-screen widget snapshot: today's counts and the next appointments (spec §7.1).

Never writes and never auto-completes: phases are derived from the stored status plus the
clock, exactly as for Live Activities.
"""

from datetime import datetime
from typing import Literal

from .content import build_content_state
from .eligibility import effective_scope, in_scope, visible_for_user
from .phase import TR_TZ, Phase, compute_phase
from .sweeper import load_org

MAX_ITEMS = 6
ITEM_KEYS = ("startLabel", "endLabel", "startEpoch", "endEpoch", "phase", "customerDisplay", "serviceName")


async def load_org_snapshot(db, org_id: str, now: datetime):
    """The sweeper's org snapshot, whether or not Live Activities are enabled for the org."""
    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    return await load_org(db, {**settings, "organization_id": org_id}, now)


def user_view(org, user: dict) -> dict:
    """The signed-in user merged with their stored row, which carries the Live Activity preferences."""
    return {**user, **(org.users_by_username.get(user.get("username")) or {})}


async def build_summary(db, user: dict, requested_scope: Literal["own", "all"] | None, *, now: datetime) -> dict:
    org = await load_org_snapshot(db, user["organization_id"], now)
    viewer = user_view(org, user)
    if requested_scope is not None:
        viewer["live_activity_scope"] = requested_scope
    scope = effective_scope(viewer, admin_provides_service=org.admin_provides_service,
                            org_has_staff=org.org_has_staff)

    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    todays = [a for a in org.apts if a.get("appointment_date") == today and in_scope(a, viewer, scope)]
    phases = []
    for apt in todays:
        try:
            phases.append(compute_phase(apt, now, org.duration(apt)))
        except (KeyError, ValueError, TypeError):
            continue
    completed = sum(p is Phase.COMPLETED for p in phases)
    remaining = sum(p in (Phase.UPCOMING, Phase.PROCESSING) for p in phases)

    items = []
    for v in visible_for_user(todays, viewer, scope, now=now, services_by_id=org.services_by_id,
                              lead_min=org.lead_min, day_open=True)[:MAX_ITEMS]:
        staff = org.staff_name(v.apt) if scope == "all" else None
        content = build_content_state(v.apt, v.phase, v.start, v.end, privacy_mode=org.privacy_mode,
                                      staff_name=staff, version=0)
        item = {"id": content["appointmentId"], **{k: content[k] for k in ITEM_KEYS}}
        if scope == "all":
            item["staffName"] = content["staffName"]
        items.append(item)

    return {
        "generatedAt": now.isoformat(),
        "scope": scope,
        "privacyMode": org.privacy_mode,
        "counts": {"total": completed + remaining, "completed": completed, "remaining": remaining},
        "items": items,
    }
