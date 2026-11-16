"""Live Activity sweeper: load data, plan each device, claim slots, send, persist.

Read-only on `settings`, `users`, `services` and `appointments`; writes only
`live_activity_devices` and `live_activity_slots`. Duplicate sends are prevented by
the per-slot `claim_slot` CAS, taken before every send; the Redis bucket lock only
saves work when several workers run the periodic sweep.
"""

import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from . import registry
from .content import (
    PayloadTooLarge,
    StaleStartRejected,
    build_aps,
    build_content_state,
    format_alert,
    name_mode,
    stale_epoch,
)
from .eligibility import (
    MAX_SLOTS,
    VisibleAppt,
    effective_lead_minutes,
    effective_scope,
    slot_count,
    visible_for_user,
)
from .phase import TR_TZ, Phase, appointment_window, compute_phase, resolve_duration
from .planner import USABLE_STATES, Action, plan_device
from .transport import FcmLiveActivityTransport, LiveActivityTransport

logger = logging.getLogger(__name__)

DEFAULT_POLL_SECONDS = 30
DEFAULT_START_BUDGET = 8
LOST_START_SEC = 120
END_SOON_SEC = 900  # owner decision: an idle / day-end card lingers 15 min
FINAL_PHASES = (Phase.COMPLETED, Phase.CANCELLED)

APT_PROJECTION = {"_id": 0, "phone": 0, "notes": 0, "service_price": 0}
USER_PROJECTION = {
    "_id": 0, "id": 1, "organization_id": 1, "username": 1, "full_name": 1, "role": 1, "status": 1,
    "can_view_all_appointments": 1, "live_activity_scope": 1, "live_activity_slot_count": 1,
    "live_activity_start_alert": 1,
}
SERVICE_PROJECTION = {"_id": 0, "id": 1, "duration": 1}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def poll_seconds() -> int:
    return max(1, _env_int("LIVE_ACTIVITY_POLL_SECONDS", DEFAULT_POLL_SECONDS))


def start_budget() -> int:
    return _env_int("LIVE_ACTIVITY_START_BUDGET_PER_HOUR", DEFAULT_START_BUDGET)


def content_hash(content: dict) -> str:
    """Hash of what the card shows; `version` is excluded so it alone never triggers a push."""
    shown = {k: v for k, v in content.items() if k != "version"}
    return hashlib.sha256(json.dumps(shown, sort_keys=True).encode()).hexdigest()


def _active(user: dict) -> bool:
    return "status" not in user or user["status"] == "active"


def _supports_input_push_token(os_version) -> bool:
    """`input-push-token` on a push-to-start is iOS 18+ only (spec §5.3); unknown → False."""
    try:
        return int(str(os_version).strip().split(".")[0]) >= 18
    except (TypeError, ValueError):
        return False


def _slot_attributes(device_id: str, slot_index: int, org_id: str) -> dict:
    return {"slotId": f"{device_id}:{slot_index}", "orgId": org_id}


@dataclass
class _Org:
    org_id: str
    apts: list[dict]
    apts_by_id: dict[str, dict | None]  # None: looked up and not found (deleted)
    services_by_id: dict
    users_by_username: dict[str, dict]
    admin_provides_service: bool
    org_has_staff: bool
    lead_min: int
    privacy_mode: str

    def duration(self, apt: dict) -> int:
        return resolve_duration(apt, self.services_by_id)

    def staff_name(self, apt: dict) -> str | None:
        staff = self.users_by_username.get(apt.get("staff_member_id"))
        if staff is None:
            return None
        return staff.get("full_name") or staff.get("username")


@dataclass
class _Stats:
    locked: bool = False
    orgs: int = 0
    devices: int = 0
    actions: int = 0
    sent: int = 0
    failed: int = 0
    invalid_token: int = 0
    claim_lost: int = 0
    skipped: int = 0
    expired_starts: int = 0
    owner_changed: int = 0
    errors: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


async def _acquire_lock(redis, now: datetime) -> bool:
    poll = poll_seconds()
    key = f"live_activity_lock:{int(now.timestamp() // poll)}"
    try:
        return bool(await redis.set(key, "1", nx=True, ex=poll + 10))
    except Exception as exc:  # Redis down: run without the lock; the slot CAS still guards sends
        logger.warning("live activity lock unavailable, proceeding without it: %s", exc)
        return True


async def load_org(db, settings: dict, now: datetime) -> _Org:
    """Read-only snapshot of one org: yesterday's and today's appointments, services, users, settings."""
    org_id = settings["organization_id"]
    local = now.astimezone(TR_TZ)
    days = [(local - timedelta(days=1)).strftime("%Y-%m-%d"), local.strftime("%Y-%m-%d")]
    apts = await db.appointments.find(
        {"organization_id": org_id, "appointment_date": {"$in": days}}, APT_PROJECTION
    ).to_list(None)
    services = await db.services.find({"organization_id": org_id}, SERVICE_PROJECTION).to_list(None)
    users = await db.users.find({"organization_id": org_id}, USER_PROJECTION).to_list(None)
    return _Org(
        org_id=org_id,
        apts=apts,
        apts_by_id={a.get("id"): a for a in apts},
        services_by_id={s.get("id"): s.get("duration") for s in services},
        users_by_username={u.get("username"): u for u in users},
        admin_provides_service=settings.get("admin_provides_service", True),
        org_has_staff=any(u.get("role") == "staff" and _active(u) for u in users),
        lead_min=effective_lead_minutes(settings.get("live_activity_lead_minutes")),
        privacy_mode=name_mode(settings.get("lock_screen_name_mode")),
    )


async def _load_slot_appointments(db, org: _Org, slots: list[dict]) -> None:
    """Fetch (read-only) slot appointments outside yesterday/today, e.g. rescheduled away."""
    missing = [s["appointment_id"] for s in slots
               if s.get("appointment_id") and s["appointment_id"] not in org.apts_by_id]
    if not missing:
        return
    found = await db.appointments.find(
        {"organization_id": org.org_id, "id": {"$in": missing}}, APT_PROJECTION
    ).to_list(None)
    by_id = {a.get("id"): a for a in found}
    for aid in missing:
        org.apts_by_id[aid] = by_id.get(aid)


async def _same_owner(db, device: dict) -> bool:
    """True when the device row still belongs to the user/org the sweep planned for."""
    current = await db.live_activity_devices.find_one(
        {"device_id": device["device_id"]}, {"_id": 0, "user_id": 1, "organization_id": 1}
    )
    return current is not None and all(current.get(k) == device.get(k) for k in ("user_id", "organization_id"))


async def _expire_lost_starts(db, device_id: str, slots: list[dict], now_epoch: float, stats: _Stats) -> bool:
    """A push-to-start whose token never arrived must not lock its slot all day."""
    touched = False
    for s in slots:
        if s.get("state") == "start_sent" and not s.get("update_token") \
                and now_epoch - (s.get("started_at") or 0) > LOST_START_SEC:
            touched = True
            if await registry.claim_slot(db, device_id=device_id, slot_index=s["slot_index"],
                                         expect_version=s.get("version"), set_fields={"state": "ended"}):
                stats.expired_starts += 1
    return touched


def _final_phases(org: _Org, slots: list[dict], visible_ids: set, now: datetime) -> dict[str, Phase]:
    out: dict[str, Phase] = {}
    for s in slots:
        aid = s.get("appointment_id")
        apt = org.apts_by_id.get(aid) if aid and aid not in visible_ids else None
        if apt is None:
            continue
        try:
            phase = compute_phase(apt, now, org.duration(apt))
        except (KeyError, ValueError):
            continue
        if phase in FINAL_PHASES:
            out[aid] = phase
    return out


def _end_content(org: _Org | None, action: Action, now: datetime, *, staff_name, version: int) -> tuple[dict, bool]:
    """Final content for an `end`. Returns (content, removed); a deleted appointment, or one that
    left the user's scope (planned with phase `removed`), is `removed`."""
    removed_phase = action.phase is Phase.REMOVED
    apt = org.apts_by_id.get(action.appointment_id) if action.appointment_id and not removed_phase else None
    if apt is not None:
        try:
            start, end = appointment_window(apt, org.duration(apt))
            phase = action.phase or compute_phase(apt, now, org.duration(apt))
            return build_content_state(apt, phase, start, end, privacy_mode=org.privacy_mode,
                                       staff_name=staff_name(apt), version=version), False
        except (KeyError, ValueError):
            pass
    # Deleted, out of scope or unreadable: no data left to show; dismissed immediately (spec §1.2).
    return removed_content(action.appointment_id, now, version=version), True


def removed_content(appointment_id: str | None, now: datetime, *, version: int) -> dict:
    """Final content for a card with nothing left to show (deleted appointment, orphan, logout)."""
    stub = {"id": appointment_id or "", "appointment_time": "", "customer_name": None, "service_name": ""}
    return build_content_state(stub, Phase.REMOVED, now, now, privacy_mode="hidden", staff_name=None, version=version)


def _start_fields(v: VisibleAppt, content: dict, now: datetime) -> dict:
    """Slot fields claimed for a start; a reused slot drops the previous activity's token."""
    return {"appointment_id": v.id, "phase_sent": v.phase.value, "content_hash": content_hash(content),
            "state": "start_sent", "started_at": now.timestamp(), "day": now.astimezone(TR_TZ).strftime("%Y-%m-%d"),
            "update_token": None, "activity_id": None}


async def _execute(db, org: _Org | None, device: dict, slot: dict | None, action: Action, visible: VisibleAppt | None,
                   *, transport: LiveActivityTransport, now: datetime, stats: _Stats, content_for, staff_name) -> None:
    device_id = device["device_id"]
    now_epoch = int(now.timestamp())
    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    expect = slot.get("version") if slot else None
    new_version = (expect or 0) + 1

    try:
        if action.kind == "end":
            content, removed = _end_content(org, action, now, staff_name=staff_name, version=new_version)
            dismiss_now = removed or action.dismissal == "now"
            aps = build_aps("end", content, now_epoch=now_epoch, relevance=action.relevance, stale_epoch=None,
                            dismissal_epoch=now_epoch + (0 if dismiss_now else END_SOON_SEC),
                            slot_id=None, org_id=None, input_push_token=False)
            fields = {"state": "ended", "phase_sent": content["phase"], "content_hash": content_hash(content)}
            la_token = slot.get("update_token") if slot else None
        else:
            v = visible
            content = content_for(v, new_version)
            stale = stale_epoch(v.phase, v.start, v.end)
            fields = {"appointment_id": v.id, "phase_sent": v.phase.value, "content_hash": content_hash(content)}
            if action.kind == "start":
                attrs = _slot_attributes(device_id, action.slot_index, org.org_id)
                aps = build_aps("start", content, now_epoch=now_epoch, relevance=action.relevance,
                                stale_epoch=stale, dismissal_epoch=None, slot_id=attrs["slotId"],
                                org_id=attrs["orgId"],
                                input_push_token=_supports_input_push_token(device.get("os_version")))
                fields = _start_fields(v, content, now)
                la_token = device.get("push_to_start_token")
            else:
                aps = build_aps("update", content, now_epoch=now_epoch, relevance=action.relevance,
                                stale_epoch=stale, dismissal_epoch=None, slot_id=None, org_id=None,
                                input_push_token=False)
                la_token = slot.get("update_token") if slot else None
    except (StaleStartRejected, PayloadTooLarge) as exc:
        logger.info("live activity %s skipped for %s:%s: %s", action.kind, device_id, action.slot_index, exc)
        stats.skipped += 1
        return
    if not la_token:
        stats.skipped += 1
        return

    alert = format_alert(action.alert, content) if action.alert else None
    claim = dict(device_id=device_id, slot_index=action.slot_index)
    if not await registry.claim_slot(db, **claim, expect_version=expect, set_fields=fields):
        stats.claim_lost += 1  # another sweep or a device report got there first
        return
    # A first-use slot index is claimed by insert, which no version bump can stop, so the
    # owner is checked once more right before the push leaves (re-owned phone, logout).
    if not await _same_owner(db, device):
        stats.owner_changed += 1
        logger.info("live activity %s dropped for %s:%s: device owner changed or device removed",
                    action.kind, device_id, action.slot_index)
        await registry.claim_slot(db, **claim, expect_version=new_version, set_fields={"state": "ended"})
        return

    result = await transport.send(fcm_token=device["fcm_token"], la_token=la_token, aps=aps,
                                  alert=alert, priority=action.priority)
    if action.kind == "start":
        await registry.record_start(db, device_id, now.timestamp())  # budget counts every attempt

    if result.ok:
        stats.sent += 1
        # The first start of the day opens it; so does a switch/update onto one of today's
        # appointments (a slot carried over from yesterday never starts again today).
        opens_day = action.kind == "start" or (
            action.kind == "update" and visible is not None
            and visible.start.astimezone(TR_TZ).strftime("%Y-%m-%d") == today)
        if opens_day and device.get("day") != today:
            await db.live_activity_devices.update_one({"device_id": device_id}, {"$set": {"day": today}})
            device["day"] = today
        return

    previous = {k: (slot or {}).get(k) for k in fields}
    if result.invalid_token:
        stats.invalid_token += 1
        if action.kind == "start":
            await db.live_activity_devices.update_one(
                {"device_id": device_id, "push_to_start_token": la_token},
                {"$set": {"push_to_start_token": None}},
            )
            revert = {"state": "ended"}
        else:
            # The activity behind this token is gone: free the index so it can reopen.
            revert = {**previous, "update_token": None, "state": "ended"}
        await registry.claim_slot(db, **claim, expect_version=new_version, set_fields=revert)
        return

    stats.failed += 1
    logger.warning("live activity %s failed for %s:%s: %s", action.kind, device_id, action.slot_index, result.error)
    if action.kind != "start":
        # Not delivered: restore what was sent before so the next sweep retries.
        await registry.claim_slot(db, **claim, expect_version=new_version, set_fields=previous)
    # A failed start stays `start_sent`; delivery may be ambiguous, and the lost-start
    # expiry reopens the index after LOST_START_SEC if no token arrives.


@dataclass
class _DeviceView:
    """What one device should show now: shared by the sweep and the reconcile's local starts."""
    user: dict
    n_slots: int
    slots: list[dict]
    visible: list[VisibleAppt]
    by_id: dict[str, VisibleAppt]
    staff_name: Callable[[dict], str | None]
    content_for: Callable[[VisibleAppt, int], dict]


async def _device_view(db, org: _Org, device: dict, *, now: datetime, stats: _Stats) -> _DeviceView | None:
    user = org.users_by_username.get(device.get("username"))
    if user is None or not _active(user):
        return None
    device_id = device["device_id"]
    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    scope = effective_scope(user, admin_provides_service=org.admin_provides_service, org_has_staff=org.org_has_staff)

    slots = await registry.slots_for_device(db, device_id)
    if await _expire_lost_starts(db, device_id, slots, now.timestamp(), stats):
        slots = await registry.slots_for_device(db, device_id)
    await _load_slot_appointments(db, org, slots)

    visible = visible_for_user(org.apts, user, scope, now=now, services_by_id=org.services_by_id,
                               lead_min=org.lead_min, day_open=device.get("day") == today)

    def staff_name(apt: dict) -> str | None:
        return org.staff_name(apt) if scope == "all" else None

    def content_for(v: VisibleAppt, version: int) -> dict:
        return build_content_state(v.apt, v.phase, v.start, v.end, privacy_mode=org.privacy_mode,
                                   staff_name=staff_name(v.apt), version=version)

    return _DeviceView(user=user, n_slots=slot_count(user, scope), slots=slots, visible=visible,
                       by_id={v.id: v for v in visible}, staff_name=staff_name, content_for=content_for)


def _plan(org: _Org, device: dict, view: _DeviceView, *, now: datetime, has_push_to_start: bool,
          start_alert_enabled: bool) -> list[Action]:
    return plan_device(
        slots=view.slots, visible=view.visible, n_slots=view.n_slots, now=now,
        starts_last_hour=registry.starts_last_hour(device, now.timestamp()), start_budget=start_budget(),
        start_alert_enabled=start_alert_enabled, has_push_to_start=has_push_to_start,
        content_hash=lambda v: content_hash(view.content_for(v, 0)),
        final_phases=_final_phases(org, view.slots, set(view.by_id), now),
    )


async def _end_live_slots(db, device: dict, *, transport: LiveActivityTransport, now: datetime,
                          stats: _Stats) -> None:
    """End every live card of a device that may show nothing any more (org flag off or settings
    gone, user inactive or deleted): removed stub, dismissed now (spec §1.2). Each end goes
    through the same claim-then-send path, owner re-check included."""
    if not device.get("fcm_token"):
        return
    for s in await registry.slots_for_device(db, device["device_id"]):
        if s.get("state") not in USABLE_STATES or not s.get("update_token"):
            continue
        stats.actions += 1
        action = Action("end", s["slot_index"], s.get("appointment_id"), Phase.REMOVED, 10, None, 0.0, "now")
        await _execute(db, None, device, s, action, None, transport=transport, now=now, stats=stats,
                       content_for=None, staff_name=None)


async def _end_disabled_orgs(db, enabled_ids: set, org_ids: list[str] | None, *,
                             transport: LiveActivityTransport, now: datetime, stats: _Stats) -> None:
    """End the live cards left in orgs whose flag is off (or whose settings are missing).

    Only enabled orgs open slots, so live slots are few: they are listed first, and their
    devices are looked up only when there are any. With `org_ids` (the change hook) only
    those orgs are considered."""
    live = await db.live_activity_slots.find(
        {"state": {"$in": sorted(USABLE_STATES)}}, {"_id": 0, "device_id": 1, "update_token": 1}
    ).to_list(None)
    device_ids = sorted({s["device_id"] for s in live if s.get("update_token")})
    if not device_ids:
        return
    for device in await db.live_activity_devices.find({"device_id": {"$in": device_ids}}).to_list(None):
        org_id = device.get("organization_id")
        if org_id in enabled_ids or (org_ids is not None and org_id not in org_ids):
            continue
        try:
            await _end_live_slots(db, device, transport=transport, now=now, stats=stats)
        except Exception:
            stats.errors += 1
            logger.exception("live activity sweep: ending device %s of disabled org failed", device.get("device_id"))


async def _sweep_device(db, org: _Org, device: dict, *, transport: LiveActivityTransport, now: datetime,
                        stats: _Stats) -> None:
    if not device.get("fcm_token"):
        return
    user = org.users_by_username.get(device.get("username"))
    if user is None or not _active(user):
        await _end_live_slots(db, device, transport=transport, now=now, stats=stats)
        return
    view = await _device_view(db, org, device, now=now, stats=stats)
    if view is None:
        return
    stats.devices += 1
    actions = _plan(
        org, device, view, now=now,
        has_push_to_start=bool(device.get("push_to_start_token")) and device.get("activities_enabled") is not False,
        start_alert_enabled=bool(view.user.get("live_activity_start_alert")),
    )
    by_index = {s["slot_index"]: s for s in view.slots}
    for action in actions:
        stats.actions += 1
        await _execute(db, org, device, by_index.get(action.slot_index), action, view.by_id.get(action.appointment_id),
                       transport=transport, now=now, stats=stats, content_for=view.content_for,
                       staff_name=view.staff_name)


async def start_locally(db, device_id: str, *, now: datetime) -> list[dict]:
    """Starts for a device without push-to-start (iOS 16.2–17.1), handed to the foregrounded app
    instead of pushed. The planner decides them exactly as for a sweep; each slot is claimed
    `start_sent` before it is returned, so the activity's token callback is accepted (and an
    unused claim expires after LOST_START_SEC like a lost push-to-start)."""
    device = await db.live_activity_devices.find_one({"device_id": device_id})
    if device is None or device.get("push_to_start_token") or device.get("activities_enabled") is False:
        return []
    settings = await db.settings.find_one(
        {"organization_id": device.get("organization_id"), "live_activity_enabled": True}, {"_id": 0}
    )
    if not settings:
        return []
    org = await load_org(db, settings, now)
    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    out: list[dict] = []
    for _ in range(MAX_SLOTS):  # the planner opens one slot per pass
        view = await _device_view(db, org, device, now=now, stats=_Stats())
        if view is None:
            break
        actions = _plan(org, device, view, now=now, has_push_to_start=True, start_alert_enabled=False)
        start = next((a for a in actions if a.kind == "start"), None)
        if start is None:
            break
        v = view.by_id[start.appointment_id]
        slot = next((s for s in view.slots if s["slot_index"] == start.slot_index), None)
        expect = slot.get("version") if slot else None
        content = view.content_for(v, (expect or 0) + 1)
        claim = dict(device_id=device_id, slot_index=start.slot_index)
        if not await registry.claim_slot(db, **claim, expect_version=expect, set_fields=_start_fields(v, content, now)):
            break  # a concurrent sweep or report changed the slot; the next reconcile retries
        if not await _same_owner(db, device):
            await registry.claim_slot(db, **claim, expect_version=(expect or 0) + 1, set_fields={"state": "ended"})
            break
        # No record_start: the push-to-start budget does not apply to a start the app makes itself.
        if device.get("day") != today:
            await db.live_activity_devices.update_one({"device_id": device_id}, {"$set": {"day": today}})
        out.append({"slot_index": start.slot_index, "content": content,
                    "attributes": _slot_attributes(device_id, start.slot_index, org.org_id),
                    "stale_epoch": stale_epoch(v.phase, v.start, v.end), "relevance": start.relevance})
        device = await db.live_activity_devices.find_one({"device_id": device_id})
        if device is None:
            break
    return out


async def run_sweep(db, *, transport: LiveActivityTransport, now: datetime, redis=None,
                    org_ids: list[str] | None = None) -> dict:
    """One pass over every enabled org (or only `org_ids`, the change-hook path, which skips the lock)."""
    stats = _Stats()
    if org_ids is None and redis is not None and not await _acquire_lock(redis, now):
        stats.locked = True
        return stats.as_dict()

    flt: dict = {"live_activity_enabled": True}
    if org_ids is not None:
        flt["organization_id"] = {"$in": list(org_ids)}
    enabled = [s for s in await db.settings.find(flt, {"_id": 0}).to_list(None) if s.get("organization_id")]
    for settings in enabled:
        stats.orgs += 1
        try:
            org = await load_org(db, settings, now)
            devices = await db.live_activity_devices.find({"organization_id": org.org_id}).to_list(None)
        except Exception:
            stats.errors += 1
            logger.exception("live activity sweep: loading org %s failed", settings.get("organization_id"))
            continue
        for device in devices:
            try:
                await _sweep_device(db, org, device, transport=transport, now=now, stats=stats)
            except Exception:
                stats.errors += 1
                logger.exception("live activity sweep: device %s failed", device.get("device_id"))
    try:
        await _end_disabled_orgs(db, {s["organization_id"] for s in enabled}, org_ids,
                                 transport=transport, now=now, stats=stats)
    except Exception:
        stats.errors += 1
        logger.exception("live activity sweep: ending cards of disabled orgs failed")
    return stats.as_dict()


async def resync(db, org_id: str, *, transport: LiveActivityTransport | None = None,
                 now: datetime | None = None) -> None:
    """Change-hook entry point: sweep one org now. Never raises (fire-and-forget)."""
    try:
        await run_sweep(db, transport=transport or FcmLiveActivityTransport(),
                        now=now or datetime.now(TR_TZ), org_ids=[org_id])
    except Exception as exc:
        logger.error("live activity resync for org %s failed: %s", org_id, exc, exc_info=True)
