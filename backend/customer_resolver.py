"""One shared customer resolver: canonical phone key, shared-number records, races.

Never imports server.py; reads ``settings`` directly.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pymongo.errors import DuplicateKeyError

from customer_identity import country_for_currency, names_match, phone_key

Mode = Literal["admin", "appointment", "public"]


async def org_country(db, organization_id: str) -> str:
    settings = await db.settings.find_one(
        {"organization_id": organization_id}, {"_id": 0, "base_currency": 1}
    )
    return country_for_currency((settings or {}).get("base_currency"))


async def _candidates(db, organization_id: str, phone: str, key: Optional[str]) -> list:
    flt: dict = {"organization_id": organization_id}
    if key:
        flt["$or"] = [{"phone_key": key}, {"phone": phone}]
    else:
        flt["phone"] = phone
    return await db.customers.find(flt, {"_id": 0}).to_list(50)


def _pick(candidates: list, name: Optional[str]) -> Optional[dict]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    for c in candidates:
        if names_match(c.get("name"), name, allow_subset=False):
            return c
    for c in candidates:
        if c.get("phone_key"):
            return c
    return candidates[0]


async def find_customer_for(db, organization_id: str, phone: str, name: Optional[str]) -> Optional[dict]:
    key = phone_key(phone, await org_country(db, organization_id))
    return _pick(await _candidates(db, organization_id, phone, key), name)


def _new_doc(organization_id: str, phone: str, name: Optional[str], extra: dict) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "name": (name or "").strip(),
        "phone": phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": "",
        "total_appointments": 0,
        "completed_appointments": 0,
    }
    doc.update(extra)
    return doc


async def resolve_customer(
    db,
    organization_id: str,
    phone: str,
    name: Optional[str],
    *,
    mode: Mode,
    allow_shared: bool = False,
) -> tuple:
    """Return ``(customer_doc, created)``; see the Faz 7 design for the rules."""
    key = phone_key(phone, await org_country(db, organization_id))
    candidates = await _candidates(db, organization_id, phone, key)

    if allow_shared:
        doc = _new_doc(organization_id, phone, name, {"shared_phone": True})
        await db.customers.insert_one(dict(doc))
        return doc, True

    if candidates:
        if mode != "public":
            return _pick(candidates, name), False
        exact = [c for c in candidates if names_match(c.get("name"), name, allow_subset=False)]
        if exact:
            return _pick(exact, name), False
        if len(candidates) == 1 and names_match(candidates[0].get("name"), name, allow_subset=True):
            return candidates[0], False
        if key is None:
            return _pick(candidates, name), False  # unkeyed phone: today's behaviour
        keyed = next((c for c in candidates if c.get("phone_key")), candidates[0])
        doc = _new_doc(organization_id, phone, name,
                       {"shared_phone": True, "merge_suggestion_for": keyed["id"]})
        await db.customers.insert_one(dict(doc))
        return doc, True

    doc = _new_doc(organization_id, phone, name, {"phone_key": key} if key else {})
    try:
        await db.customers.insert_one(dict(doc))
    except DuplicateKeyError:
        winner = await db.customers.find_one(
            {"organization_id": organization_id, "phone_key": key}, {"_id": 0})
        if winner is None:
            raise
        return winner, False
    return doc, True
