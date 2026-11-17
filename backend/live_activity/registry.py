"""Device and slot registry for Live Activities (Motor/MongoDB)."""

import hashlib
import hmac
import secrets
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from live_activity.phase import TR_TZ

START_WINDOW_SEC = 3600
# Ending every slot (owner change, logout) also forgets the day's dismissed appointments.
FORGET_DISMISSALS = {"dismissed_day": "", "dismissed_ids": ""}


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def ensure_indexes(db) -> None:
    await db.live_activity_devices.create_index("device_id", unique=True)
    await db.live_activity_slots.create_index([("device_id", 1), ("slot_index", 1)], unique=True)


async def upsert_device(
    db, *, device_id: str, organization_id: str, user_id: str, username: str,
    os_version: str, app_build: str, fcm_token: str | None,
    push_to_start_token: str | None, activities_enabled: bool,
    ended_slots: list[dict] | None = None,
) -> tuple[dict, str | None]:
    """Create/refresh a device row. Returns (row, new_secret); the secret is
    issued only on first registration or when the owner changes.

    On an owner change every slot is ended; the ones that were live with a token are appended
    (as they were before) to `ended_slots`, if given, so the caller can end their cards."""
    existing = await db.live_activity_devices.find_one({"device_id": device_id})
    owner_changed = existing is not None and (
        existing.get("user_id") != user_id or existing.get("organization_id") != organization_id
    )
    fields = {
        "organization_id": organization_id, "user_id": user_id, "username": username,
        "os_version": os_version, "app_build": app_build, "fcm_token": fcm_token,
        "push_to_start_token": push_to_start_token, "activities_enabled": activities_enabled,
        "updated_at": datetime.now(TR_TZ),
    }
    new_secret = None
    if existing is None or owner_changed:
        new_secret = secrets.token_urlsafe(32)
        fields["secret_sha256"] = _hash_secret(new_secret)
        fields["day"] = None
    update = {"$set": fields}
    if existing is None:
        update["$setOnInsert"] = {"start_log": []}
    if owner_changed:
        if ended_slots is not None:
            ended_slots.extend(await _live_slots(db, device_id))
        # $inc: a sweep still holding the old owner's slot snapshot then fails its claim_slot CAS
        await db.live_activity_slots.update_many(
            {"device_id": device_id}, {"$set": {"state": "ended"}, "$unset": FORGET_DISMISSALS, "$inc": {"version": 1}}
        )
    row = await db.live_activity_devices.find_one_and_update(
        {"device_id": device_id}, update, upsert=True, return_document=ReturnDocument.AFTER
    )
    return row, new_secret


async def verify_device_secret(db, device_id: str, secret: str) -> dict | None:
    device = await db.live_activity_devices.find_one({"device_id": device_id})
    if not device or not device.get("secret_sha256"):
        return None
    if hmac.compare_digest(device["secret_sha256"], _hash_secret(secret)):
        return device
    return None


async def slots_for_device(db, device_id: str) -> list[dict]:
    slots = await db.live_activity_slots.find({"device_id": device_id}).to_list(None)
    return sorted(slots, key=lambda s: s["slot_index"])


async def _live_slots(db, device_id: str) -> list[dict]:
    """Slots whose card may still be on screen and can be ended by its token."""
    return [s for s in await slots_for_device(db, device_id)
            if s.get("state") in ("start_sent", "active") and s.get("update_token")]


async def claim_slot(
    db, *, device_id: str, slot_index: int, expect_version: int | None, set_fields: dict
) -> bool:
    """Compare-and-set on slot `version`. With expect_version None, creates the slot."""
    key = {"device_id": device_id, "slot_index": slot_index}
    if expect_version is None:
        try:
            await db.live_activity_slots.find_one_and_update(
                {**key, "version": {"$exists": False}},
                {"$set": set_fields, "$setOnInsert": {"version": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return False
        return True
    result = await db.live_activity_slots.update_one(
        {**key, "version": expect_version}, {"$set": set_fields, "$inc": {"version": 1}}
    )
    return result.matched_count == 1


async def record_slot_token(
    db, *, device_id: str, slot_index: int, activity_id: str, update_token: str
) -> bool:
    result = await db.live_activity_slots.update_one(
        {"device_id": device_id, "slot_index": slot_index, "state": "start_sent"},
        {"$set": {"state": "active", "activity_id": activity_id, "update_token": update_token},
         "$inc": {"version": 1}},  # a sweep holding the start_sent snapshot then fails its CAS
    )
    return result.matched_count == 1


async def refresh_slot_token(
    db, *, device_id: str, slot_index: int, activity_id: str, update_token: str
) -> bool:
    """A running activity re-sent or rotated its push token. True if the slot holds that activity."""
    key = {"device_id": device_id, "slot_index": slot_index, "state": "active", "activity_id": activity_id}
    slot = await db.live_activity_slots.find_one(key)
    if slot is None:
        return False
    if slot.get("update_token") == update_token:
        return True
    result = await db.live_activity_slots.update_one(
        key, {"$set": {"update_token": update_token}, "$inc": {"version": 1}}
    )
    return result.matched_count == 1


async def remove_device(db, device_id: str) -> list[dict]:
    """Logout: end every slot and delete the device row (and with it the secret).
    Returns the slots that were live with a token, as they were before, so the caller can end them."""
    live = await _live_slots(db, device_id)
    # $inc: a sweep holding a slot snapshot then fails its claim_slot CAS
    await db.live_activity_slots.update_many(
        {"device_id": device_id}, {"$set": {"state": "ended"}, "$unset": FORGET_DISMISSALS, "$inc": {"version": 1}}
    )
    await db.live_activity_devices.delete_one({"device_id": device_id})
    return live


async def apply_device_report(
    db, *, device_id: str, slots: list[dict], activities_enabled: bool, complete: bool, now: datetime
) -> list[dict]:
    """Reconcile slot states with what the device reports. Returns changed slot docs."""
    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    await db.live_activity_devices.update_one(
        {"device_id": device_id}, {"$set": {"activities_enabled": activities_enabled}}
    )
    reported = {s["slot_index"]: s for s in slots}
    changed = []
    for slot in await slots_for_device(db, device_id):
        report = reported.get(slot["slot_index"])
        if report is not None:
            new_state = {"dismissed": "dismissed_by_user", "ended": "ended", "active": "active"}.get(
                report.get("state")
            )
            # "active" only lists the slot: the token callback alone makes a slot active, so a
            # report can neither revive an ended slot nor pre-empt a pending start's token.
            if new_state in (None, "active") or new_state == slot["state"]:
                continue
            fields = {"state": new_state}
            if new_state == "dismissed_by_user":
                fields["day"] = today
                # The slot may be reused today for another appointment; the planner keeps every
                # appointment dismissed today hidden through this list.
                earlier = (slot.get("dismissed_ids") or []) if slot.get("dismissed_day") == today else []
                fields["dismissed_day"] = today
                fields["dismissed_ids"] = [*earlier, slot.get("appointment_id")]
        elif complete and slot["state"] in ("start_sent", "active"):
            fields = {"state": "ended"}
        else:
            continue
        await db.live_activity_slots.update_one(
            {"device_id": device_id, "slot_index": slot["slot_index"]},
            {"$set": fields, "$inc": {"version": 1}},  # a concurrent sweep's claim_slot CAS then fails
        )
        changed.append({**slot, **fields})
    return changed


async def record_start(db, device_id: str, now_epoch: float) -> None:
    await db.live_activity_devices.update_one({"device_id": device_id}, {"$push": {"start_log": now_epoch}})
    await db.live_activity_devices.update_one(
        {"device_id": device_id}, {"$pull": {"start_log": {"$lt": now_epoch - START_WINDOW_SEC}}}
    )


def starts_last_hour(device: dict, now_epoch: float) -> int:
    return sum(1 for t in device.get("start_log", []) if now_epoch - t < START_WINDOW_SEC)
