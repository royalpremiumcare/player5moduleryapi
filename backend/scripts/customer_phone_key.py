#!/usr/bin/env python3
"""PLANN — customer phone key rollout (Faz 7 + Faz 8). Owner-gated.

Steps, in this order, each one first with --dry-run (writes nothing), then with --apply
after the owner has reviewed the dry-run report:

    backfill  set ``phone_key`` on every customer whose number gives a key. Inside a
              duplicate group only the proposed survivor is keyed (decision 6).
    merge     classes A and B: merge every other member into the survivor
              (``customer_merge.merge_into``), then key the survivor.
              Class CD: never merged; the others get ``shared_phone: true`` and no key.
    index     create ``customers_org_phone_key_unique``; fails (exit 1) while any keyed
              duplicate remains.
    verify    read-only: keyed duplicates, appointment phones that resolve to no
              customer, counters that differ from a recount. Reports, never fixes.

Usage (inside the backend container, MONGO_URL and DB_NAME come from the environment):

    python -m scripts.customer_phone_key backfill --dry-run
    python -m scripts.customer_phone_key backfill --apply --backup-dir /backups/pk-backfill \
        --plan-id <id printed by the dry run>
    python -m scripts.customer_phone_key merge --dry-run
    python -m scripts.customer_phone_key merge --apply --backup-dir /backups/pk-merge --plan-id <id>
    python -m scripts.customer_phone_key index --apply --backup-dir /backups/pk-index
    python -m scripts.customer_phone_key verify --dry-run

Take each step's dry run right before its apply: backfill changes the merge plan (the
survivors then already hold their key), so the merge plan id is only known after backfill.
--plan-id is required with backfill/merge --apply and refuses a plan that differs from
the reviewed dry run. Set PK_SCRIPT_DEBUG=1 to see a crash's traceback (it can contain
customer data; keep it out of chat).

Every --apply needs a --backup-dir that does not exist yet. It receives ``backup.jsonl``
(prior state of every touched document, written before each write), ``meta.json`` and
``restore.py`` (``python <backup-dir>/restore.py`` puts the documents back with
``customer_merge.restore_from_backup``; restore the newest run first).

Reports are pasted into chat: they show org ids as 8-character prefixes, names as
initials and at most the last 2 digits of a number. Exit codes: 0 ok, 1 a check failed or
an apply step failed, 2 usage or configuration error.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from bson import json_util  # noqa: E402  (pymongo ships bson)
from pymongo.errors import DuplicateKeyError  # noqa: E402

from customer_identity import names_match, phone_key  # noqa: E402
from customer_indexes import INDEX_NAME, _is_exact, ensure_customer_indexes  # noqa: E402
from customer_merge import (  # noqa: E402
    _NAMED, REFERENCE_FIELDS, _survivor, find_duplicate_groups, merge_into,
)
from customer_resolver import find_customer_for, org_country  # noqa: E402

COMPLETED = "Tamamlandı"
APPLY_COMMANDS = ("backfill", "merge", "index")


# ------------------------------------------------------------------ masking (chat-safe)

def org8(org_id) -> str:
    return str(org_id or "?")[:8]


def initials(name) -> str:
    words = str(name or "").split()
    return "".join(w[0].upper() + "." for w in words) or "?"


def tail2(phone) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return "…" + digits[-2:] if digits else "-"


def who(c: dict) -> str:
    return f"{initials(c.get('name'))} {tail2(c.get('phone'))}"


def fingerprint(items) -> str:
    blob = json.dumps(sorted(items), ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


# ------------------------------------------------------------------ backup journal

class Journal(list):
    """A backup list that writes each entry to disk (and fsyncs) before it is used.

    ``merge_into`` appends the prior state of a document right before writing it, so a
    crash mid-run still leaves every touched document in ``backup.jsonl``.
    """

    def __init__(self, path: str):
        super().__init__()
        self._fh = open(path, "a", encoding="utf-8")

    def append(self, entry) -> None:
        self._fh.write(json_util.dumps(entry, json_options=json_util.CANONICAL_JSON_OPTIONS))
        self._fh.write("\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        super().append(entry)

    def close(self) -> None:
        self._fh.close()


def remember(backup: list, collection: str, doc: dict) -> None:
    backup.append({"collection": collection, "filter": {"_id": doc["_id"]}, "doc": doc})


RESTORE_PY = '''#!/usr/bin/env python3
"""Restore the documents touched by one customer_phone_key --apply run.

    MONGO_URL=... DB_NAME=... python {backup_dir}/restore.py [--drop-index]

Restore the newest run first (index, then merge, then backfill). It reads MONGO_URL and
DB_NAME from the environment, refuses any database other than the one this run wrote to,
asks nothing, and replaces each backed-up document with its prior state
(customer_merge.restore_from_backup). --drop-index drops {index_name} first; a restored
record can need that, because the index refuses two keyed records with the same number.
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = {backend!r}
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from bson import json_util
from motor.motor_asyncio import AsyncIOMotorClient

from customer_merge import restore_from_backup

INDEX_NAME = {index_name!r}


async def main() -> int:
    with open(os.path.join(HERE, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    url, name = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not name:
        print("MONGO_URL and DB_NAME must be set")
        return 2
    print(f"Target DB: {{name}}")
    if name != meta["db_name"]:
        print(f"REFUSED: this backup belongs to DB {{meta['db_name']}}, not {{name}}")
        return 2
    with open(os.path.join(HERE, "backup.jsonl"), encoding="utf-8") as fh:
        entries = [json_util.loads(line) for line in fh if line.strip()]
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=10000)
    db = client[name]
    try:
        drop = "--drop-index" in sys.argv[1:] or meta.get("index_created_by_this_run")
        if drop and INDEX_NAME in await db.customers.index_information():
            await db.customers.drop_index(INDEX_NAME)
            print(f"dropped index {{INDEX_NAME}}")
        await restore_from_backup(db, entries)
        print(f"restored {{len(entries)}} backup entries from {{meta['command']}} run "
              f"{{meta['started_at']}}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
'''


class BackupDir:
    def __init__(self, path: str, command: str, db_name: str):
        os.makedirs(path)  # must not exist yet (checked before, raises if it appeared)
        self.path = path
        self.meta = {"command": command, "db_name": db_name,
                     "started_at": datetime.now(timezone.utc).isoformat(),
                     "status": "running", "index_created_by_this_run": False}
        self._write_meta()
        with open(os.path.join(path, "restore.py"), "w", encoding="utf-8") as fh:
            fh.write(RESTORE_PY.format(backup_dir=path, backend=_BACKEND, index_name=INDEX_NAME))
        self.journal = Journal(os.path.join(path, "backup.jsonl"))

    def _write_meta(self) -> None:
        with open(os.path.join(self.path, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, indent=2)

    def finish(self, status: str, **extra) -> None:
        self.journal.close()
        self.meta.update(status=status, finished_at=datetime.now(timezone.utc).isoformat(),
                         entries=len(self.journal), **extra)
        self._write_meta()


# ------------------------------------------------------------------ shared planning

def effective_survivor(group) -> Optional[dict]:
    """``find_duplicate_groups``' survivor, except that a ``shared_phone`` record never
    becomes the keyed survivor while a non-shared member exists (a shared record has no key
    by definition). ``None`` when every member is a shared record."""
    by_id = {m["id"]: m for m in group.members}
    chosen = by_id[group.survivor_id]
    if not chosen.get("shared_phone"):
        return chosen
    plain = [m for m in group.members if not m.get("shared_phone")]
    return _survivor(plain) if plain else None


def _created_key(c: dict) -> tuple:
    return (str(c.get("created_at") or ""), str(c.get("id")))


async def load_customers(db, organization_id: Optional[str]) -> list:
    flt = {"organization_id": organization_id} if organization_id else {}
    return await db.customers.find(flt, {"_id": 0}).to_list(None)


def missing_ids(customers: list) -> int:
    return sum(1 for c in customers if not c.get("id"))


# ------------------------------------------------------------------ backfill

def unkeyed_reason(phone) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return "empty"
    if len(digits[2:] if digits.startswith("00") else digits) < 10:
        return "too_short"
    return "unrecognised"


def is_landline(key: str, country: str) -> bool:
    return country == "TR" and key.startswith("90") and len(key) == 12 and key[2] in "2348"


@dataclass
class BackfillItem:
    organization_id: str
    customer_id: str
    phone: str
    key: str
    landline: bool
    survivor: bool


@dataclass
class BackfillPlan:
    items: list = field(default_factory=list)
    per_org: dict = field(default_factory=dict)
    countries: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    @property
    def plan_id(self) -> str:
        return fingerprint([(i.customer_id, i.key) for i in self.items])


async def plan_backfill(db, organization_id: Optional[str] = None) -> BackfillPlan:
    plan = BackfillPlan()
    customers = await load_customers(db, organization_id)
    groups = await find_duplicate_groups(db, organization_id)
    role: dict = {}  # customer id -> ("survivor", key) | ("member", key)
    for g in groups:
        surv = effective_survivor(g)
        keyed = [m for m in g.members if m.get("phone_key")]
        if len(keyed) > 1:
            plan.warnings.append(f"org={org8(g.organization_id)} group {tail2(g.key)} has "
                                 f"{len(keyed)} keyed members (merge resolves it)")
        for m in g.members:
            is_surv = surv is not None and m["id"] == surv["id"]
            role[m["id"]] = ("survivor" if is_surv else "member", g.key)
    countries: dict = {}
    for c in customers:
        org = c.get("organization_id")
        if org not in countries:
            countries[org] = await org_country(db, org)
        country = plan.countries[org] = countries[org]
        stats = plan.per_org.setdefault(org, Counter())
        stats["customers"] += 1
        if c.get("phone_key"):
            stats["already_keyed"] += 1
            computed = phone_key(c.get("phone"), country)
            if computed and computed != c["phone_key"]:
                stats["stored_key_differs"] += 1
            continue
        if c.get("shared_phone"):
            stats["unkeyed:shared_phone"] += 1
            continue
        key = phone_key(c.get("phone"), country)
        r = role.get(c.get("id"))
        if r and r[0] == "member":
            stats["unkeyed:group_member"] += 1
            continue
        if r:
            key = r[1]  # the group's key (the survivor's own number, or its stored key)
        if not key:
            stats["unkeyed:" + unkeyed_reason(c.get("phone"))] += 1
            continue
        landline = is_landline(key, country)
        plan.items.append(BackfillItem(org, c["id"], c.get("phone"), key, landline, bool(r)))
        stats["to_key"] += 1
        stats["landline_keys"] += landline
        stats["group_survivors"] += bool(r)
    return plan


def print_backfill(plan: BackfillPlan, out) -> None:
    cols = ("customers", "already_keyed", "to_key", "landline_keys", "group_survivors",
            "unkeyed:group_member", "unkeyed:shared_phone", "unkeyed:empty",
            "unkeyed:too_short", "unkeyed:unrecognised", "stored_key_differs")
    total: Counter = Counter()
    for org, stats in sorted(plan.per_org.items(), key=lambda kv: str(kv[0])):
        out(f"org={org8(org)} country={plan.countries[org]} " + " ".join(
            f"{c.split(':')[-1]}={stats.get(c, 0)}" for c in cols))
        total.update({c: stats.get(c, 0) for c in cols})
    out(f"TOTAL orgs={len(plan.per_org)} " + " ".join(
        f"{c.split(':')[-1]}={total.get(c, 0)}" for c in cols))
    out("  (to_key includes landline_keys: TR landline numbers, 2/3/4/8 after the 90, R6)")
    for w in plan.warnings:
        out("WARNING " + w)
    out(f"plan id: {plan.plan_id}")


async def apply_backfill(db, plan: BackfillPlan, backup: list) -> Counter:
    done: Counter = Counter()
    for item in plan.items:
        doc = await db.customers.find_one({"organization_id": item.organization_id,
                                           "id": item.customer_id})
        if (doc is None or doc.get("phone_key") or doc.get("shared_phone")
                or doc.get("phone") != item.phone):
            done["skipped_changed"] += 1
            continue
        remember(backup, "customers", doc)
        try:
            res = await db.customers.update_one(
                {"_id": doc["_id"], "phone": item.phone, "phone_key": {"$exists": False}},
                {"$set": {"phone_key": item.key}})
        except DuplicateKeyError:
            done["conflict"] += 1
            continue
        done["keyed" if res.modified_count else "skipped_changed"] += 1
    return done


# ------------------------------------------------------------------ merge

@dataclass
class SourcePlan:
    source_id: str
    label: str
    repointed: dict
    stripe_left: int = 0
    left_for_shared_phone: list = field(default_factory=list)
    left_docs: dict = field(default_factory=dict)
    notes_joined: int = 0
    error: Optional[str] = None


@dataclass
class GroupPlan:
    organization_id: str
    key: str
    klass: str
    members: list
    survivor: Optional[dict]
    sources: list = field(default_factory=list)       # A/B
    mark_shared: list = field(default_factory=list)   # CD: member dicts
    shared_skipped: list = field(default_factory=list)  # A/B: shared_phone members (R12)
    set_survivor_key: bool = False
    skip_reason: Optional[str] = None

    @property
    def actionable(self) -> bool:
        return not self.skip_reason and bool(self.sources or self.mark_shared
                                             or self.set_survivor_key)


async def _predict_sources(db, org: str, survivor: dict, sources: list, country: str) -> list:
    """Simulate ``merge_into`` for each source in order, reading only.

    Mirrors its rules: the shared-phone guard (another customer still holds the source's
    exact string), a stripe row kept when the survivor already has one, notes joined into
    the survivor's note row. References re-pointed by an earlier source move to the
    survivor's phone, so later sources see the updated state.
    """
    new = survivor.get("phone")
    key = phone_key(new, country)
    phones = sorted({s.get("phone") for s in sources if s.get("phone")} | {new or ""})
    refs: dict = {}
    for coll, fld in REFERENCE_FIELDS.items():
        docs = await getattr(db, coll).find(
            {"organization_id": org, fld: {"$in": phones}},
            {"_id": 1, fld: 1, "customer_name": 1}).to_list(None)
        refs[coll] = {d["_id"]: {"phone": d.get(fld), "name": d.get("customer_name")}
                      for d in docs}
    out, gone = [], []
    for src in sources:
        sp = SourcePlan(src["id"], who(src), {c: 0 for c in REFERENCE_FIELDS})
        out.append(sp)
        if not key or phone_key(src.get("phone"), country) != key:
            sp.error = "survivor and source do not share a phone key"
            continue
        old = src["phone"]
        if old != new:
            others = await db.customers.find(
                {"organization_id": org, "phone": old,
                 "id": {"$nin": [survivor["id"], src["id"], *gone]}}, {"_id": 0}).to_list(None)
            for coll in REFERENCE_FIELDS:
                current = {i: d for i, d in refs[coll].items() if d["phone"] == old}
                if others and coll not in _NAMED:
                    sp.left_for_shared_phone.append(coll)
                    if current:
                        sp.left_docs[coll] = len(current)
                    continue
                docs = current
                if others:
                    docs = {i: d for i, d in current.items() if not any(
                        names_match(o.get("name"), d["name"], allow_subset=False)
                        for o in others)}
                    if len(docs) < len(current):
                        sp.left_docs[coll] = len(current) - len(docs)
                if not docs:
                    continue
                has_new = any(d["phone"] == new for d in refs[coll].values())
                if coll == "stripe_customers" and has_new:
                    sp.stripe_left = len(docs)
                    continue
                if coll == "customer_notes" and has_new:
                    for i in docs:
                        del refs[coll][i]
                    sp.notes_joined = len(docs)
                    sp.repointed[coll] = len(docs)
                    continue
                for i in docs:
                    refs[coll][i]["phone"] = new
                sp.repointed[coll] = len(docs)
        gone.append(src["id"])
    return out


async def plan_merge(db, organization_id: Optional[str] = None) -> list:
    plans = []
    countries: dict = {}
    for g in await find_duplicate_groups(db, organization_id):
        org = g.organization_id
        if org not in countries:
            countries[org] = await org_country(db, org)
        surv = effective_survivor(g)
        gp = GroupPlan(org, g.key, g.klass, g.members, surv)
        plans.append(gp)
        if surv is None:
            gp.skip_reason = "every member is a shared_phone record"
            continue
        gp.set_survivor_key = not surv.get("phone_key")
        others = sorted((m for m in g.members if m["id"] != surv["id"]), key=_created_key)
        if g.klass == "CD":
            gp.mark_shared = [m for m in others
                              if not m.get("shared_phone") or m.get("phone_key")]
            continue
        # R12: a shared_phone record is an owner's "Farklı kişi"; name similarity never
        # overrides it. It merges only through the in-app suggestion.
        gp.shared_skipped = [m for m in others if m.get("shared_phone")]
        others = [m for m in others if not m.get("shared_phone")]
        gp.sources = await _predict_sources(db, org, surv, others, countries[org])
        bad = [s for s in gp.sources if s.error]
        if bad:
            gp.skip_reason = bad[0].error
    plans.sort(key=lambda p: (str(p.organization_id), p.klass, p.key))
    return plans


def merge_plan_id(plans: list) -> str:
    return fingerprint([
        (p.organization_id, p.klass, (p.survivor or {}).get("id"),
         [s.source_id for s in p.sources], [m["id"] for m in p.mark_shared],
         p.set_survivor_key, p.skip_reason)
        for p in plans if p.actionable or p.skip_reason])


_SHORT = {"appointments": "appts", "customer_notes": "notes",
          "marketing_autopilot_tasks": "marketing", "merchant_transactions": "merchant_tx",
          "refund_requests": "refunds", "stripe_customers": "stripe"}


def print_merge(plans: list, out) -> None:
    out("Reference counts are what merge_into will do on the current data, simulated in "
        "order: references kept for another customer on the same string (shared-phone "
        "guard), a stripe row kept because the survivor has one, notes joined into the "
        "survivor's note row.")
    totals: Counter = Counter()
    for p in plans:
        surv = p.survivor
        head = (f"[{p.klass}] org={org8(p.organization_id)} members={len(p.members)} "
                f"number={tail2(p.key)}")
        if surv:
            head += (f" survivor={who(surv)} appts={int(surv.get('total_appointments') or 0)}"
                     f" key={'set' if p.set_survivor_key else 'kept'}")
        if p.skip_reason:
            out(head + f" SKIPPED ({p.skip_reason})")
            totals["skipped_groups"] += 1
            continue
        if p.klass == "CD":
            names = ", ".join(who(m) for m in p.mark_shared) or "none (already shared)"
            out(head + f" no merge; shared_phone + no key: {names}")
            totals["cd_groups"] += 1
            totals["marked_shared"] += len(p.mark_shared)
            continue
        if p.shared_skipped:
            head += " | shared, skipped: " + ", ".join(who(m) for m in p.shared_skipped)
            totals["shared_skipped"] += len(p.shared_skipped)
        out(head + f" merge {len(p.sources)} into survivor")
        totals["merge_groups"] += 1
        for s in p.sources:
            refs = " ".join(f"{_SHORT[c]}={n}" for c, n in s.repointed.items())
            extra = []
            if s.notes_joined:
                extra.append(f"notes joined={s.notes_joined}")
            if s.stripe_left:
                extra.append(f"stripe kept={s.stripe_left}")
            if s.left_docs:
                extra.append("left for shared number: " + " ".join(
                    f"{_SHORT[c]}={n}" for c, n in s.left_docs.items()))
            out(f"    source {s.label}: {refs}" + (" | " + "; ".join(extra) if extra else ""))
            totals["merged_records"] += 1
            totals.update({"ref:" + _SHORT[c]: n for c, n in s.repointed.items()})
    by_class = Counter(p.klass for p in plans)
    out(f"TOTAL groups={len(plans)} A={by_class['A']} B={by_class['B']} CD={by_class['CD']} "
        f"merge_groups={totals['merge_groups']} merged_records={totals['merged_records']} "
        f"cd_groups={totals['cd_groups']} marked_shared={totals['marked_shared']} "
        f"skipped={totals['skipped_groups']} shared_skipped={totals['shared_skipped']} "
        "refs: " + " ".join(
            f"{v}={totals['ref:' + v]}" for v in _SHORT.values()))
    out(f"plan id: {merge_plan_id(plans)}")


async def _set_survivor_key(db, plan: GroupPlan, backup: list) -> str:
    doc = await db.customers.find_one({"organization_id": plan.organization_id,
                                       "id": plan.survivor["id"]})
    if doc is None:
        return "survivor missing"
    if doc.get("phone_key"):
        return "kept"
    remember(backup, "customers", doc)
    try:
        res = await db.customers.update_one({"_id": doc["_id"], "phone_key": {"$exists": False}},
                                            {"$set": {"phone_key": plan.key}})
    except DuplicateKeyError:
        return "key conflict"
    return "set" if res.modified_count == 1 else "not set (record changed meanwhile)"


async def apply_merge(db, plans: list, backup: list) -> list:
    """Returns one result per A/B source (merge_into's summary plus org id) and one per
    CD group (``kind: "cd"``)."""
    results = []
    for p in plans:
        if not p.actionable:
            continue
        org = p.organization_id
        if p.klass == "CD":
            marked = 0
            for m in p.mark_shared:
                doc = await db.customers.find_one({"organization_id": org, "id": m["id"]})
                if doc is None or (doc.get("shared_phone") is True and "phone_key" not in doc):
                    continue
                remember(backup, "customers", doc)
                await db.customers.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"shared_phone": True}, "$unset": {"phone_key": ""}})
                marked += 1
            key = await _set_survivor_key(db, p, backup) if p.set_survivor_key else "kept"
            results.append({"kind": "cd", "organization_id": org, "marked_shared": marked,
                            "survivor_key": key})
            continue
        failed = False
        for s in p.sources:
            try:
                summary = await merge_into(db, org, p.survivor["id"], s.source_id, backup=backup)
            except Exception as exc:  # stop this group; others continue
                # No str(exc): it can carry dup-key values and full ids (report goes to chat).
                results.append({"kind": "merge", "organization_id": org,
                                "source_id": s.source_id, "error": type(exc).__name__,
                                "hint": f"merging {s.label} into {who(p.survivor)}"})
                failed = True
                break
            results.append({"kind": "merge", "organization_id": org, **summary})
        if not failed:
            key = await _set_survivor_key(db, p, backup)
            results.append({"kind": "survivor_key", "organization_id": org,
                            "survivor_id": p.survivor["id"], "survivor_key": key})
    return results


# ------------------------------------------------------------------ index / verify

async def keyed_duplicates(db, organization_id: Optional[str] = None) -> list:
    match: dict = {"phone_key": {"$exists": True}}
    if organization_id:
        match["organization_id"] = organization_id
    return await db.customers.aggregate([
        {"$match": match},
        {"$group": {"_id": {"org": "$organization_id", "key": "$phone_key"},
                    "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
    ]).to_list(None)


def print_keyed_duplicates(dups: list, out) -> None:
    out(f"keyed duplicates: {len(dups)}")
    for d in dups[:50]:
        out(f"    org={org8(d['_id']['org'])} number={tail2(d['_id']['key'])} records={d['n']}")


async def recount(db, organization_id: Optional[str]) -> tuple:
    """Attribute every appointment with ``find_customer_for`` (the live delta's rule)."""
    flt = {"organization_id": organization_id} if organization_id else {}
    counts: dict = defaultdict(Counter)
    unresolved: Counter = Counter()
    no_phone = 0
    owners: dict = {}
    async for a in db.appointments.find(flt, {"_id": 0, "organization_id": 1, "phone": 1,
                                              "customer_name": 1, "status": 1}):
        org, phone = a.get("organization_id"), (a.get("phone") or "").strip()
        if not org or not phone:
            no_phone += 1
            continue
        k = (org, phone, a.get("customer_name") or "")
        if k not in owners:
            found = await find_customer_for(db, org, phone, a.get("customer_name"))
            owners[k] = found["id"] if found else None
        if owners[k] is None:
            unresolved[(org, phone)] += 1
            continue
        counts[owners[k]]["total"] += 1
        counts[owners[k]]["completed"] += a.get("status") == COMPLETED
    return counts, unresolved, no_phone


async def run_verify(db, organization_id: Optional[str], out) -> bool:
    dups = await keyed_duplicates(db, organization_id)
    print_keyed_duplicates(dups, out)
    counts, unresolved, no_phone = await recount(db, organization_id)
    out(f"unresolved appointment phones: {len(unresolved)} "
        f"(appointments: {sum(unresolved.values())}; without phone, ignored: {no_phone})")
    for (org, phone), n in sorted(unresolved.items())[:50]:
        out(f"    org={org8(org)} number={tail2(phone)} appointments={n}")
    customers = await load_customers(db, organization_id)
    mismatches = []
    for c in customers:
        got = counts.get(c.get("id"), Counter())
        stored = (int(c.get("total_appointments") or 0), int(c.get("completed_appointments") or 0))
        if stored != (got["total"], got["completed"]):
            mismatches.append((c, stored, got))
    out(f"counter mismatches: {len(mismatches)}")
    for c, stored, got in mismatches[:50]:
        out(f"    org={org8(c.get('organization_id'))} {who(c)} stored total={stored[0]} "
            f"completed={stored[1]} recomputed total={got['total']} "
            f"completed={got['completed']}")
    unkeyed = []
    countries: dict = {}
    for c in customers:
        if c.get("phone_key") or c.get("shared_phone"):
            continue
        org = c.get("organization_id")
        if org not in countries:
            countries[org] = await org_country(db, org)
        if phone_key(c.get("phone"), countries[org]):
            unkeyed.append(c)
    out(f"unkeyed keyable customers: {len(unkeyed)} (no phone_key, not shared_phone)")
    for c in unkeyed[:50]:
        out(f"    org={org8(c.get('organization_id'))} {who(c)}")
    info = (await db.customers.index_information()).get(INDEX_NAME)
    out(f"index {INDEX_NAME}: {'present' if _is_exact(info) else 'MISSING'} (info only)")
    ok = not dups and not unresolved and not mismatches and not unkeyed
    out("VERIFY " + ("OK" if ok else "FAIL (reported only, nothing was changed)"))
    return ok


async def run_index(db, apply: bool, backup: Optional[BackupDir], out) -> bool:
    dups = await keyed_duplicates(db)
    print_keyed_duplicates(dups, out)
    before = _is_exact((await db.customers.index_information()).get(INDEX_NAME))
    out(f"index {INDEX_NAME}: {'present' if before else 'missing'}")
    if dups:
        out(f"FAIL: {len(dups)} keyed duplicate number(s) remain; run merge first. "
            "The index was not " + ("created." if apply else "checked further."))
        return False
    if not apply:
        out("would create the index" if not before else "nothing to do")
        return True
    result = await ensure_customer_indexes(db)
    after = _is_exact((await db.customers.index_information()).get(INDEX_NAME))
    out(f"ensure_customer_indexes: {result}")
    if not after:
        out(f"FAIL: {INDEX_NAME} is not in place after ensure_customer_indexes ({result}).")
        return False
    if backup is not None and not before:
        backup.meta["index_created_by_this_run"] = True
    out(f"index {INDEX_NAME}: present")
    return True


# ------------------------------------------------------------------ CLI

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="customer_phone_key",
        description="Customer phone key rollout: backfill, merge, index, verify.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("backfill", "merge", "index", "verify"):
        p = sub.add_parser(name)
        mode = p.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="report only, write nothing")
        mode.add_argument("--apply", action="store_true", help="write (needs --backup-dir)")
        p.add_argument("--backup-dir", help="new directory for the backup (must not exist)")
        p.add_argument("--org-id", help="limit to one organization")
        if name in ("backfill", "merge"):
            p.add_argument("--plan-id", help="required with --apply: the id printed by the "
                                             "reviewed dry run; refuses a changed plan")
    return parser


async def amain(argv=None) -> int:
    def out(line: str = "") -> None:
        print(line, flush=True)

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.command == "index" and args.org_id:
        out("index is global (one index over all orgs): --org-id is not accepted")
        return 2
    if args.command == "verify" and args.apply:
        out("verify is read-only: use --dry-run")
        return 2
    if args.apply and args.command in APPLY_COMMANDS:
        if not args.backup_dir:
            out("--apply requires --backup-dir <new directory>")
            return 2
        if os.path.exists(args.backup_dir):
            out(f"--backup-dir {args.backup_dir} already exists; pass a new directory")
            return 2
        if args.command in ("backfill", "merge") and not args.plan_id:
            out(f"{args.command} --apply requires --plan-id <id printed by the dry run you "
                "reviewed>")
            return 2

    url, db_name = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not db_name:
        out("MONGO_URL and DB_NAME must be set in the environment")
        return 2

    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    mode = "APPLY" if args.apply else "DRY RUN (nothing is written)"
    out(f"Target DB: {db_name}")
    out(f"Command: {args.command} — {mode}"
        + (f" — org={org8(args.org_id)}" if args.org_id else ""))
    try:
        return await _dispatch(db, db_name, args, out)
    finally:
        client.close()


async def _dispatch(db, db_name: str, args, out) -> int:
    org = args.org_id
    if args.command == "verify":
        return 0 if await run_verify(db, org, out) else 1

    if args.command in ("backfill", "merge"):
        no_id = missing_ids(await load_customers(db, org))
        if no_id:
            out(f"FAIL: {no_id} customer(s) have no id; fix them before {args.command}.")
            return 1

    if args.command == "backfill":
        plan = await plan_backfill(db, org)
        print_backfill(plan, out)
        plan_id = plan.plan_id
    elif args.command == "merge":
        plans = await plan_merge(db, org)
        print_merge(plans, out)
        plan_id = merge_plan_id(plans)
    else:
        plan_id = None

    if not args.apply:
        if args.command == "index":
            return 0 if await run_index(db, False, None, out) else 1
        return 0

    if plan_id and args.plan_id != plan_id:
        out(f"REFUSED: plan changed since the dry run (expected {args.plan_id}, now "
            f"{plan_id}). Nothing was written. Review a new dry run.")
        return 1

    backup = BackupDir(args.backup_dir, args.command, db_name)
    ok = True
    try:
        if args.command == "backfill":
            done = await apply_backfill(db, plan, backup.journal)
            out("APPLIED backfill: " + " ".join(f"{k}={v}" for k, v in sorted(done.items()))
                if done else "APPLIED backfill: nothing to do")
            ok = not done.get("conflict")
            if not ok:
                out("FAIL: some keys conflicted with a record written meanwhile; re-run "
                    "backfill --dry-run.")
        elif args.command == "merge":
            ok = _report_merge_results(await apply_merge(db, plans, backup.journal), out)
        else:
            ok = await run_index(db, True, backup, out)
    except BaseException as exc:
        backup.finish("crashed", error=type(exc).__name__)
        out(f"CRASHED ({type(exc).__name__}; details withheld from the report) — the backup "
            f"so far is in {backup.path}; restore with "
            f"python {os.path.join(backup.path, 'restore.py')}")
        if os.environ.get("PK_SCRIPT_DEBUG") == "1":
            raise
        return 1
    backup.finish("ok" if ok else "failed")
    out(f"backup: {len(backup.journal)} document state(s) in "
        f"{os.path.join(backup.path, 'backup.jsonl')}")
    out(f"restore: MONGO_URL=... DB_NAME={db_name} python "
        f"{os.path.join(backup.path, 'restore.py')}  (newest run first)")
    return 0 if ok else 1


def _report_merge_results(results: list, out) -> bool:
    ok = True
    merged = Counter()
    for r in results:
        org = org8(r["organization_id"])
        if r.get("error"):
            out(f"ERROR org={org}: merge stopped for this group: {r['error']} while "
                f"{r.get('hint', '?')}")
            ok = False
        elif r["kind"] == "merge":
            merged["merged" if r.get("merged") else "already_gone"] += 1
            merged.update({"ref:" + _SHORT[c]: n for c, n in r["repointed"].items()})
            merged["stripe_kept"] += r.get("stripe_customers_left", 0)
        elif r["kind"] == "cd":
            merged["cd_marked_shared"] += r["marked_shared"]
            if r["survivor_key"] not in ("set", "kept"):
                out(f"ERROR org={org}: CD survivor key {r['survivor_key']}")
                ok = False
            merged["survivor_keys_set"] += r["survivor_key"] == "set"
        elif r["kind"] == "survivor_key":
            if r["survivor_key"] not in ("set", "kept"):
                out(f"ERROR org={org}: survivor key {r['survivor_key']}")
                ok = False
            merged["survivor_keys_set"] += r["survivor_key"] == "set"
    out("APPLIED merge: " + (" ".join(f"{k}={v}" for k, v in sorted(merged.items()))
                             or "nothing to do"))
    return ok


def main(argv=None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    sys.exit(main())
