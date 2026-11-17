"""HTTP endpoints for Live Activities and the widget summary (mounted under /api by server.py).

server.py injects its auth and db dependencies with `configure(...)`, so this module never
imports server. Tests override `_current_user` and `_db`; reconcile's JWT branch calls the
configured `get_current_user` directly, only when no device secret is sent.

Writes go only to `live_activity_devices`, `live_activity_slots` and the user's own
`live_activity_*` fields; nothing here writes appointments or auto-completes.
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from . import registry, widget_keys
from .content import build_aps
from .eligibility import MAX_SLOTS, MIN_SLOTS, effective_scope, is_manager, slot_count
from .phase import TR_TZ
from .sweeper import removed_content, resync, start_locally
from .transport import FcmLiveActivityTransport, LiveActivityTransport
from .widget_summary import build_summary, load_org_snapshot, user_view

logger = logging.getLogger(__name__)

router = APIRouter()

SECRET_HEADER = "X-Plann-Device-Secret"
WIDGET_KEY_HEADER = "X-Plann-Widget-Key"
INACTIVE_STATUSES = {"inactive", "passive", "deactivated", "disabled", "suspended", "deleted"}
USABLE_STATES = ("start_sent", "active")
ALIVE_REPORT_STATES = {"active", "stale", "pending"}  # ActivityKit states of a card still on screen

_get_current_user = None
_get_db = None
_transport: LiveActivityTransport | None = None
_background: set[asyncio.Task] = set()
# Same token URL as server.oauth2_scheme; auto_error off so reconcile can fall back to the device secret.
_bearer = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)


def configure(get_current_user, get_db, *, transport: LiveActivityTransport | None = None) -> None:
    """Bind server.get_current_user(request, token, db) and server.get_db(request)."""
    global _get_current_user, _get_db, _transport
    _get_current_user, _get_db, _transport = get_current_user, get_db, transport


def _now() -> datetime:
    return datetime.now(TR_TZ)


def _push_transport() -> LiveActivityTransport:
    global _transport
    if _transport is None:
        _transport = FcmLiveActivityTransport()
    return _transport


async def _db(request: Request):
    if _get_db is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Live Activities not configured")
    return await _get_db(request)


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials",
                         headers={"WWW-Authenticate": "Bearer"})


async def _resolve_jwt(request: Request, token: str | None, db):
    if not token:
        raise _unauthorized()
    if _get_current_user is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Live Activities not configured")
    return await _get_current_user(request, token, db)


async def _current_user(request: Request, token: str | None = Depends(_bearer), db=Depends(_db)):
    return await _resolve_jwt(request, token, db)


def _user_dict(user) -> dict:
    if isinstance(user, dict):
        return dict(user)
    if hasattr(user, "model_dump"):
        return user.model_dump()
    return dict(vars(user))


def _user_id(user: dict) -> str:
    return user.get("id") or user.get("user_id") or user["username"]


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)  # keep a reference until done; the loop holds tasks only weakly
    task.add_done_callback(_background.discard)


def _resync_soon(db, org_id: str) -> None:
    _spawn(resync(db, org_id, transport=_push_transport()))


async def _end_now(device: dict, update_token: str, *, version: int, now: datetime) -> None:
    """Dismiss one activity at once with the removed stub (no customer data). Best effort."""
    if not device.get("fcm_token"):
        return
    now_epoch = int(now.timestamp())
    content = removed_content(None, now, version=version)
    aps = build_aps("end", content, now_epoch=now_epoch, relevance=0, stale_epoch=None,
                    dismissal_epoch=now_epoch, slot_id=None, org_id=None, input_push_token=False)
    result = await _push_transport().send(fcm_token=device["fcm_token"], la_token=update_token, aps=aps,
                                          alert=None, priority=10)
    if not result.ok:
        logger.info("live activity end for %s failed: %s", device.get("device_id"), result.error)


async def _owned_device(db, device_id: str, user: dict) -> dict | None:
    device = await db.live_activity_devices.find_one({"device_id": device_id})
    if device is None:
        return None
    if device.get("user_id") != _user_id(user) or device.get("organization_id") != user.get("organization_id"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device belongs to another user")
    return device


# --- devices -----------------------------------------------------------------------------------

class DeviceRegistration(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    os_version: str = Field(max_length=32)
    app_build: str = Field(max_length=32)
    fcm_token: str | None = Field(default=None, max_length=4096)
    push_to_start_token: str | None = Field(default=None, max_length=4096)
    activities_enabled: bool


@router.post("/live-activities/devices")
async def register_device(body: DeviceRegistration, user=Depends(_current_user), db=Depends(_db)):
    u = _user_dict(user)
    previous_owner_slots: list[dict] = []
    row, secret = await registry.upsert_device(
        db, device_id=body.device_id, organization_id=u["organization_id"], user_id=_user_id(u),
        username=u["username"], os_version=body.os_version, app_build=body.app_build,
        fcm_token=body.fcm_token, push_to_start_token=body.push_to_start_token,
        activities_enabled=body.activities_enabled, ended_slots=previous_owner_slots,
    )
    # Shared phone: the previous owner's cards must not stay on the new owner's lock screen.
    now = _now()
    for s in previous_owner_slots:
        await _end_now(row, s["update_token"], version=(s.get("version") or 0) + 1, now=now)
    return {"device_secret": secret}  # None unless first registration or a new owner


@router.delete("/live-activities/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(device_id: str, user=Depends(_current_user), db=Depends(_db)):
    device = await _owned_device(db, device_id, _user_dict(user))
    if device is not None:
        now = _now()
        for s in await registry.remove_device(db, device_id):
            await _end_now(device, s["update_token"], version=(s.get("version") or 0) + 1, now=now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- token callback (device secret only) -------------------------------------------------------

class SlotToken(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    slot_index: int = Field(ge=MIN_SLOTS, le=MAX_SLOTS)
    activity_id: str = Field(min_length=1, max_length=256)
    update_token: str = Field(min_length=1, max_length=4096)


@router.post("/live-activities/token", status_code=status.HTTP_204_NO_CONTENT)
async def slot_token(body: SlotToken, db=Depends(_db),
                     device_secret: str | None = Header(default=None, alias=SECRET_HEADER)):
    device = await registry.verify_device_secret(db, body.device_id, device_secret) if device_secret else None
    if device is None:
        raise _unauthorized()
    args = dict(device_id=body.device_id, slot_index=body.slot_index, activity_id=body.activity_id,
                update_token=body.update_token)
    if await registry.record_slot_token(db, **args) or await registry.refresh_slot_token(db, **args):
        _resync_soon(db, device["organization_id"])  # a switch waiting for this token lands now
    else:
        # Late token: the slot already expired or ended, so no card may linger for it.
        slot = await db.live_activity_slots.find_one({"device_id": body.device_id, "slot_index": body.slot_index})
        await _end_now(device, body.update_token, version=((slot or {}).get("version") or 0) + 1, now=_now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- reconcile (device secret or the owner's JWT) ----------------------------------------------

class SlotReport(BaseModel):
    slot_index: int = Field(ge=MIN_SLOTS, le=MAX_SLOTS)
    activity_id: str | None = Field(default=None, max_length=256)
    state: str = Field(max_length=32)


class Reconcile(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    activities_enabled: bool
    complete: bool
    push_to_start_token: str | None = Field(default=None, max_length=4096)
    slots: list[SlotReport] = Field(default_factory=list, max_length=32)


def _sort_reports(reports: list[SlotReport], slots: list[dict]) -> tuple[list[dict], list[int], list[str]]:
    """Split the device's list into what the registry applies, the slots whose tracked activity the
    device must end, and the untracked activities it must end.

    A card still on screen is kept only if it is the activity the server tracks for its slot (or
    the slot awaits its token). An untracked sibling at the same index is ended by its activity id
    and never drops the tracked activity's report. An ended or dismissed report applies only to
    the tracked activity, never to a newer one in the same slot.
    """
    by_index = {s["slot_index"]: s for s in slots}
    apply: dict[int, dict] = {}
    end: set[int] = set()
    end_activities: list[str] = []
    for r in reports:
        s = by_index.get(r.slot_index)
        tracked = s.get("activity_id") if s else None
        is_tracked = tracked is not None and tracked == r.activity_id
        if r.state in ALIVE_REPORT_STATES:
            if s is not None and s.get("state") in USABLE_STATES and (tracked is None or is_tracked):
                apply[r.slot_index] = r.model_dump()
            elif is_tracked or (r.activity_id is None and s is not None and s.get("state") not in USABLE_STATES):
                end.add(r.slot_index)  # the server already ended this slot's own activity
            elif r.activity_id is not None and r.activity_id not in end_activities:
                end_activities.append(r.activity_id)
        elif s is not None and is_tracked:
            apply[r.slot_index] = r.model_dump()
    return list(apply.values()), sorted(end), end_activities


@router.post("/live-activities/reconcile")
async def reconcile(body: Reconcile, request: Request, db=Depends(_db), token: str | None = Depends(_bearer),
                    device_secret: str | None = Header(default=None, alias=SECRET_HEADER)):
    # The secret is checked first: the app's shared HTTP client may also attach a stale bearer,
    # which must neither block a valid secret nor trigger its 401-logout.
    if device_secret is not None:
        device = await registry.verify_device_secret(db, body.device_id, device_secret)
        if device is None:
            raise _unauthorized()
    else:
        user = await _resolve_jwt(request, token, db)
        device = await _owned_device(db, body.device_id, _user_dict(user))
        if device is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Device belongs to another user")

    now = _now()
    if body.push_to_start_token:
        await db.live_activity_devices.update_one(
            {"device_id": body.device_id}, {"$set": {"push_to_start_token": body.push_to_start_token}}
        )
    reports, end, end_activities = _sort_reports(body.slots, await registry.slots_for_device(db, body.device_id))
    changed = await registry.apply_device_report(
        db, device_id=body.device_id, slots=reports, activities_enabled=body.activities_enabled,
        complete=body.complete, now=now,
    )
    starts = await start_locally(db, body.device_id, now=now)  # [] unless the device lacks push-to-start
    if changed:
        _resync_soon(db, device["organization_id"])  # e.g. a dismissed slot frees room for the next card
    return {"end": end, "end_activities": end_activities, "start_locally": starts}


# --- preferences -------------------------------------------------------------------------------

class Preferences(BaseModel):
    scope: Literal["own", "all"] | None = None
    slot_count: int | None = None
    start_alert: bool | None = None


@router.get("/live-activities/preferences")
async def get_preferences(user=Depends(_current_user), db=Depends(_db)):
    """Read-only: the effective values plus which controls the server lets this user change."""
    u = _user_dict(user)
    org = await load_org_snapshot(db, u["organization_id"], _now())
    settings = await db.settings.find_one({"organization_id": u["organization_id"]}, {"_id": 0}) or {}
    viewer = user_view(org, u)
    scope = effective_scope(viewer, admin_provides_service=org.admin_provides_service,
                            org_has_staff=org.org_has_staff)
    is_admin = viewer.get("role") == "admin"
    forced_all = is_admin and not org.admin_provides_service and not org.org_has_staff
    privileged = is_admin or is_manager(viewer)
    return {"enabled": settings.get("live_activity_enabled") is True, "scope": scope,
            "slot_count": slot_count(viewer, scope), "start_alert": bool(viewer.get("live_activity_start_alert")),
            "can_choose_scope": privileged and not forced_all, "can_choose_slots": privileged}


@router.put("/live-activities/preferences")
async def update_preferences(body: Preferences, user=Depends(_current_user), db=Depends(_db)):
    u = _user_dict(user)
    org = await load_org_snapshot(db, u["organization_id"], _now())
    viewer = user_view(org, u)
    plain_staff = viewer.get("role") == "staff" and not is_manager(viewer)
    if plain_staff and (body.scope == "all" or (body.slot_count is not None and body.slot_count > 1)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff can show only their own next appointment")

    fields: dict = {}
    if body.scope is not None:
        fields["live_activity_scope"] = body.scope
    if body.slot_count is not None:
        fields["live_activity_slot_count"] = max(MIN_SLOTS, min(MAX_SLOTS, body.slot_count))
    if body.start_alert is not None:
        fields["live_activity_start_alert"] = body.start_alert
    if fields:
        await db.users.update_one({"organization_id": u["organization_id"], "username": u["username"]},
                                  {"$set": fields})
    viewer.update(fields)
    scope = effective_scope(viewer, admin_provides_service=org.admin_provides_service,
                            org_has_staff=org.org_has_staff)
    return {"scope": scope, "slot_count": slot_count(viewer, scope),
            "start_alert": bool(viewer.get("live_activity_start_alert"))}


# --- widget ------------------------------------------------------------------------------------

def _user_is_active(doc: dict) -> bool:
    return str(doc.get("status") or "active").lower() not in INACTIVE_STATUSES and doc.get("is_active") is not False


async def _summary_user(request: Request, key: str | None = Header(default=None, alias=WIDGET_KEY_HEADER),
                        token: str | None = Depends(_bearer), db=Depends(_db)):
    """The summary accepts a widget key (checked first) or the login JWT. A key is resolved to the
    user's current stored row, so role, status and preferences are always today's."""
    if not key:
        return await _resolve_jwt(request, token, db)
    now = _now()
    row = await widget_keys.resolve(db, key, now=now)
    if row is None:
        raise _unauthorized()
    redis = getattr(request.app.state, "redis_client", None)
    if not await widget_keys.within_rate_limit(redis, row["key_hash"], now=now):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many widget requests")
    doc = await db.users.find_one({"username": row["username"]}, {"_id": 0})
    if doc is None or not _user_is_active(doc):
        raise _unauthorized()
    return doc


@router.get("/widget/summary")
async def widget_summary(scope: Literal["own", "all"] | None = Query(default=None),
                         user=Depends(_summary_user), db=Depends(_db)):
    return await build_summary(db, _user_dict(user), scope, now=_now())


class WidgetKeyRevoke(BaseModel):
    key: str | None = Field(default=None, max_length=256)


@router.post("/widget/key")
async def issue_widget_key(user=Depends(_current_user), db=Depends(_db)):
    raw, expires_at = await widget_keys.issue_key(db, _user_dict(user), now=_now())
    return {"key": raw, "expires_at": expires_at.isoformat()}


@router.delete("/widget/key", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_widget_key(body: WidgetKeyRevoke | None = None, user=Depends(_current_user), db=Depends(_db)):
    await widget_keys.revoke(db, _user_dict(user)["username"], body.key if body else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
