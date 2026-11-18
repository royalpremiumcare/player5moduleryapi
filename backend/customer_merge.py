"""Faz 8 merge engine: duplicate groups by canonical phone key, classes, survivor, merge.

Customers link to other data by the exact phone string, so a merge re-points every
reference from the source's phone to the survivor's phone (the stored ``phone`` of the
survivor is never rewritten). Every touched document's prior state is appended to
``backup`` so ``restore_from_backup`` can put the data back exactly.

Never imports server.py.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from customer_identity import names_match, normalize_name, phone_key, phone_variants
from customer_resolver import _candidates, _pick, org_country

Klass = Literal["A", "B", "CD"]

# collection -> field holding the customer's phone string (spec, "Backfill and merge" 3).
REFERENCE_FIELDS = {
    "appointments": "phone",
    "customer_notes": "phone",
    "marketing_autopilot_tasks": "phone",
    "merchant_transactions": "customer_phone",
    "refund_requests": "customer_phone",
    "stripe_customers": "customer_phone",
}
# References that carry a customer name, so they can be told apart on a shared number.
_NAMED = {"appointments", "marketing_autopilot_tasks"}
_COMPLETED = "Tamamlandı"


@dataclass
class DuplicateGroup:
    organization_id: str
    key: str
    members: list
    klass: Klass
    survivor_id: str


def _classify(members: list) -> Klass:
    names = [normalize_name(m.get("name")) for m in members]
    if names[0] and all(n == names[0] for n in names):
        return "A"
    pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
    if all(names_match(a.get("name"), b.get("name"), allow_subset=True) for a, b in pairs):
        return "B"
    return "CD"


def _created_sort_value(value) -> tuple:
    if isinstance(value, datetime):
        value = value.isoformat()
    return (not value, str(value or ""))


def _survivor(members: list) -> dict:
    """Most appointments, then oldest ``created_at``; a member that already stores the
    key wins outright, so a stored ``phone_key`` never moves to another document."""
    keyed = [m for m in members if m.get("phone_key")]
    pool = keyed or members
    return min(pool, key=lambda m: (-int(m.get("total_appointments") or 0),
                                    *_created_sort_value(m.get("created_at"))))


async def find_duplicate_groups(db, organization_id: Optional[str] = None) -> list:
    flt = {"organization_id": organization_id} if organization_id else {}
    customers = await db.customers.find(flt, {"_id": 0}).to_list(None)
    countries: dict = {}
    buckets: dict = defaultdict(list)
    for c in customers:
        org = c.get("organization_id")
        if org not in countries:
            countries[org] = await org_country(db, org)
        key = phone_key(c.get("phone"), countries[org]) or c.get("phone_key")
        if key:
            buckets[(org, key)].append(c)
    groups = []
    for (org, key), members in buckets.items():
        if len(members) < 2:
            continue
        groups.append(DuplicateGroup(org, key, members, _classify(members),
                                     _survivor(members)["id"]))
    return groups


async def reference_counts(db, group: DuplicateGroup) -> dict:
    """References a merge of this group would re-point (non-survivor phone strings)."""
    survivor = next(m for m in group.members if m["id"] == group.survivor_id)
    phones = sorted({m.get("phone") for m in group.members
                     if m["id"] != group.survivor_id and m.get("phone")} - {survivor.get("phone")})
    counts = {}
    for coll, field in REFERENCE_FIELDS.items():
        docs = await getattr(db, coll).find(
            {"organization_id": group.organization_id, field: {"$in": phones}}, {"_id": 1}
        ).to_list(None)
        counts[coll] = len(docs)
    return counts


def _join(first: Optional[str], second: Optional[str]) -> str:
    """Concatenate with a newline; re-running never appends the same text twice."""
    first, second = first or "", second or ""
    if not second.strip() or second in first:
        return first
    if not first.strip():
        return second
    return f"{first}\n{second}"


def _appt_iso(date_str: str, time_str: str) -> Optional[str]:
    """Same rule as ``scripts/backfill_customers._appt_iso`` (naive ISO, broken -> None)."""
    try:
        if not date_str:
            return None
        return datetime.strptime(f"{date_str} {time_str or '00:00'}", "%Y-%m-%d %H:%M").isoformat()
    except Exception:
        return None


def _remember(backup: Optional[list], collection: str, doc: dict) -> None:
    if backup is not None:
        backup.append({"collection": collection, "filter": {"_id": doc["_id"]}, "doc": doc})


async def _recount(db, organization_id: str, survivor: dict, source: dict, key: str) -> dict:
    """Counters for the survivor from appointments, attributed with ``find_customer_for``
    semantics as if the source were already gone (backfill rules for totals and dates)."""
    country = await org_country(db, organization_id)
    phones = {*phone_variants(key), survivor["phone"], source["phone"]}
    for c in await _candidates(db, organization_id, survivor["phone"], key):
        phones.add(c.get("phone"))
    appts = await db.appointments.find(
        {"organization_id": organization_id, "phone": {"$in": sorted(p for p in phones if p)}},
        {"_id": 0},
    ).to_list(None)
    cands_by_phone: dict = {}
    total = completed = 0
    first = last = None
    for a in appts:
        phone = a.get("phone")
        if phone not in cands_by_phone:
            cands = await _candidates(db, organization_id, phone, phone_key(phone, country))
            cands_by_phone[phone] = [c for c in cands if c.get("id") != source["id"]]
        owner = _pick(cands_by_phone[phone], a.get("customer_name"))
        if not owner or owner.get("id") != survivor["id"]:
            continue
        total += 1
        completed += a.get("status") == _COMPLETED
        lo = _appt_iso(a.get("appointment_date") or "", a.get("appointment_time") or "00:00")
        hi = _appt_iso(a.get("appointment_date") or "", a.get("appointment_time") or "23:59")
        first = lo if lo and (first is None or lo < first) else first
        last = hi if hi and (last is None or hi > last) else last
    out = {"total_appointments": total, "completed_appointments": completed}
    if first:
        out["first_appointment_at"] = first
    if last:
        out["last_appointment_at"] = last
    return out


async def merge_into(
    db,
    organization_id: str,
    survivor_id: str,
    source_id: str,
    *,
    backup: Optional[list] = None,
) -> dict:
    """Merge customer ``source_id`` into ``survivor_id`` (same org, same phone key).

    Idempotent: once the source is gone a re-run changes nothing. Safe to resume after a
    crash: re-pointing matches nothing twice, note texts are never appended twice, and the
    source is deleted last.
    """
    if survivor_id == source_id:
        raise ValueError("survivor and source are the same customer")
    summary: dict = {"survivor_id": survivor_id, "source_id": source_id, "merged": False,
                     "repointed": {c: 0 for c in REFERENCE_FIELDS},
                     "stripe_customers_left": 0, "left_for_shared_phone": []}
    org = {"organization_id": organization_id}
    source = await db.customers.find_one({**org, "id": source_id})
    if source is None:
        summary["reason"] = "source_missing"
        return summary
    survivor = await db.customers.find_one({**org, "id": survivor_id})
    if survivor is None:
        raise ValueError("survivor not found")
    country = await org_country(db, organization_id)
    key = phone_key(survivor.get("phone"), country)
    if not key or phone_key(source.get("phone"), country) != key:
        raise ValueError("survivor and source do not share a phone key")

    old, new = source["phone"], survivor["phone"]
    if old != new:
        # Someone else still holds the source's exact string: keep their references.
        others = await db.customers.find(
            {**org, "phone": old, "id": {"$nin": [survivor_id, source_id]}}, {"_id": 0}
        ).to_list(None)
        for coll, field in REFERENCE_FIELDS.items():
            if others and coll not in _NAMED:
                summary["left_for_shared_phone"].append(coll)
                continue
            col = getattr(db, coll)
            docs = await col.find({**org, field: old}).to_list(None)
            if others:
                docs = [d for d in docs if not any(
                    names_match(o.get("name"), d.get("customer_name"), allow_subset=False)
                    for o in others)]
            if coll == "stripe_customers" and docs:
                if await col.find_one({**org, field: new}, {"_id": 1}):
                    summary["stripe_customers_left"] = len(docs)
                    continue
            if coll == "customer_notes" and docs:
                target = await col.find_one({**org, field: new})
                if target is not None:
                    _remember(backup, coll, target)
                    for d in docs:
                        _remember(backup, coll, d)
                    text = target.get("notes")
                    for d in docs:
                        text = _join(text, d.get("notes"))
                    await col.update_one({"_id": target["_id"]}, {"$set": {"notes": text}})
                    for d in docs:
                        await col.delete_one({"_id": d["_id"]})
                    summary["repointed"][coll] = len(docs)
                    continue
            if not docs:
                continue
            for d in docs:
                _remember(backup, coll, d)
            await col.update_many({"_id": {"$in": [d["_id"] for d in docs]}},
                                  {"$set": {field: new}})
            summary["repointed"][coll] = len(docs)

    counters = await _recount(db, organization_id, survivor, source, key)
    _remember(backup, "customers", survivor)
    update = {**counters, "notes": _join(survivor.get("notes"), source.get("notes")),
              "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.customers.update_one({"_id": survivor["_id"]}, {"$set": update})
    _remember(backup, "customers", source)
    await db.customers.delete_one({"_id": source["_id"]})
    summary.update(merged=True, counters=counters)
    return summary


async def mark_not_duplicate(db, organization_id: str, customer_id: str) -> None:
    """"Farklı kişi": drop the merge suggestion; the record stays a shared-number record."""
    await db.customers.update_one({"organization_id": organization_id, "id": customer_id},
                                  {"$unset": {"merge_suggestion_for": ""}})


async def restore_from_backup(db, backup: list) -> None:
    """Put every backed-up document back as it was (newest entry first, so the earliest
    prior state of a document touched twice wins)."""
    for entry in reversed(backup):
        await getattr(db, entry["collection"]).replace_one(entry["filter"], entry["doc"],
                                                           upsert=True)
