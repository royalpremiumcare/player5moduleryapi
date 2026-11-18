"""Rollout script (scripts/customer_phone_key.py) against a real throwaway MongoDB.

Skipped unless PK_TEST_MONGO_URL is set. Every test uses its own database and drops it.
"""
import asyncio
import os
import re
import subprocess
import sys
import uuid

import pytest
import pytest_asyncio
from pymongo.errors import OperationFailure

from customer_indexes import INDEX_MARKER, INDEX_NAME, PARTIAL_FILTER, ensure_customer_indexes

MONGO_URL = os.environ.get("PK_TEST_MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="PK_TEST_MONGO_URL not set")

ORG_TR = "a1b2c3d4-0000-4000-8000-00000000aaaa"
ORG_UK = "e5f6a7b8-0000-4000-8000-00000000bbbb"
COLLECTIONS = ("customers", "appointments", "customer_notes", "marketing_autopilot_tasks",
               "merchant_transactions", "refund_requests", "stripe_customers", "settings",
               "migration_log")
DONE = "Tamamlandı"


# ---------------------------------------------------------------- fixtures / helpers

@pytest_asyncio.fixture
async def env(monkeypatch):
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    name = f"pk_script_test_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MONGO_URL", MONGO_URL)
    monkeypatch.setenv("DB_NAME", name)
    try:
        yield client[name], name
    finally:
        await client.drop_database(name)
        client.close()


def _cpk():
    from scripts import customer_phone_key
    return customer_phone_key


async def _run(capsys, *argv):
    code = await _cpk().amain(list(argv))
    out = capsys.readouterr()
    return code, out.out + out.err


def _cust(phone, name, org=ORG_TR, total=0, completed=0, created="2025-01-01T00:00:00+00:00",
          **kw):
    doc = {"id": str(uuid.uuid4()), "organization_id": org, "name": name, "phone": phone,
           "notes": "", "created_at": created,
           "total_appointments": total, "completed_appointments": completed}
    doc.update(kw)
    return doc


def _appts(phone, name, n, org=ORG_TR, status="Bekliyor", day=1):
    return [{"id": str(uuid.uuid4()), "organization_id": org, "phone": phone,
             "customer_name": name, "appointment_date": f"2026-03-{day + i:02d}",
             "appointment_time": "10:00", "status": status} for i in range(n)]


class Seed:
    pass


async def _seed(db) -> Seed:
    s = Seed()
    await db.settings.insert_many([
        {"organization_id": ORG_TR, "base_currency": "TRY"},
        {"organization_id": ORG_UK, "base_currency": "GBP"},
    ])
    # Class A: format variant, notes on both (joined), stripe on both (source row kept).
    s.canan = _cust("905551110001", "Canan Çelik", total=3, completed=1, notes="VIP",
                    created="2024-01-01T00:00:00+00:00")
    s.canan_src = _cust("05551110001", "Canan Çelik Müşteri", total=2, completed=1,
                        notes="Alerji", created="2026-01-01T00:00:00+00:00")
    # Class B: shortened name, spaced +90 phone.
    s.ayse = _cust("905552220002", "Ayşe Yılmaz", total=2)
    s.ayse_src = _cust("+90 555 222 00 02", "Ayşe", total=1, created="2026-02-01T00:00:00+00:00")
    # Class CD: mother and daughter on one number.
    s.mehmet = _cust("905553330003", "Mehmet Kaya", total=2)
    s.zeynep = _cust("05553330003", "Zeynep Kaya", total=1, created="2026-02-01T00:00:00+00:00")
    # A record created after deploy already holds the key: it must stay the survivor.
    s.ali_new = _cust("905554440004", "Ali Veli", phone_key="905554440004",
                      created="2026-11-19T00:00:00+00:00")
    s.ali_old = _cust("05554440004", "Ali Veli", total=3, created="2024-01-01T00:00:00+00:00")
    # Two sources share one exact string: the shared-phone guard defers the first merge.
    s.selin = _cust("905556660006", "Selin Ak", total=3, created="2026-01-01T00:00:00+00:00")
    s.selin_1 = _cust("05556660006", "Selin Ak", total=1, created="2025-06-01T00:00:00+00:00")
    s.selin_2 = _cust("05556660006", "Selin Ak", total=1, created="2025-07-01T00:00:00+00:00")
    # Different people, the one with more appointments is a shared_phone record.
    s.ece = _cust("905558880008", "Ece Su", total=1)
    s.mert = _cust("905558880008", "Mert Su", total=2, shared_phone=True,
                   created="2024-01-01T00:00:00+00:00")
    # Singles.
    s.deniz = _cust("0090 555 777 00 07", "Deniz Ar", total=1)
    s.ofis = _cust("2121234567", "Ofis Tel")            # R6 landline, 10 digits
    s.ev = _cust("0216 123 45 67", "Ev Tel")            # landline, 0 + 10 digits
    s.walkin = _cust("0", "Walk In", total=2)
    s.empty = _cust("", "Bos Kayit")
    s.short = _cust("12345", "Kisa Numara")
    s.odd = _cust("0123456789012", "Garip Numara")
    # UK org.
    s.john = _cust("07700900123", "John Smith", org=ORG_UK, total=1,
                   created="2024-01-01T00:00:00+00:00")
    s.john_src = _cust("447700900123", "John Smith", org=ORG_UK, total=1,
                       created="2025-01-01T00:00:00+00:00")
    s.jane = _cust("7700900456", "Jane Doe", org=ORG_UK)
    s.all = [v for k, v in vars(s).items() if isinstance(v, dict)]
    await db.customers.insert_many([dict(c) for c in s.all])

    appts = (
        _appts("905551110001", "Canan Çelik", 2) + _appts("905551110001", "Canan Çelik", 1, status=DONE)
        + _appts("05551110001", "Canan Çelik Müşteri", 1)
        + _appts("05551110001", "Canan Çelik Müşteri", 1, status=DONE)
        + _appts("905552220002", "Ayşe Yılmaz", 2) + _appts("+90 555 222 00 02", "Ayşe", 1)
        + _appts("905553330003", "Mehmet Kaya", 2) + _appts("05553330003", "Zeynep Kaya", 1)
        + _appts("05554440004", "Ali Veli", 3)
        + _appts("905556660006", "Selin Ak", 3) + _appts("05556660006", "Selin Ak", 2)
        + _appts("905558880008", "Ece Su", 1) + _appts("905558880008", "Mert Su", 2)
        + _appts("0090 555 777 00 07", "Deniz Ar", 1)
        + _appts("0", "Walk In", 2)
        + _appts("07700900123", "John Smith", 1, org=ORG_UK)
        + _appts("447700900123", "John Smith", 1, org=ORG_UK)
    )
    await db.appointments.insert_many(appts)
    await db.customer_notes.insert_many([
        {"organization_id": ORG_TR, "phone": "905551110001", "notes": "Kısa kesim"},
        {"organization_id": ORG_TR, "phone": "05551110001", "notes": "Boya yok"},
    ])
    await db.stripe_customers.insert_many([
        {"organization_id": ORG_TR, "customer_phone": "905551110001", "stripe_id": "cus_a"},
        {"organization_id": ORG_TR, "customer_phone": "05551110001", "stripe_id": "cus_b"},
    ])
    await db.marketing_autopilot_tasks.insert_one(
        {"organization_id": ORG_TR, "phone": "05551110001", "customer_name": "Canan Çelik Müşteri"})
    await db.merchant_transactions.insert_many([
        {"organization_id": ORG_TR, "customer_phone": "05551110001", "amount": 100},
        {"organization_id": ORG_TR, "customer_phone": "05556660006", "amount": 70},
    ])
    await db.refund_requests.insert_one(
        {"organization_id": ORG_TR, "customer_phone": "05551110001", "amount": 50})
    # Prod already logs the financial migrations here; the index marker lands next to them.
    await db.migration_log.insert_one({"name": "20260421_bootstrap_indexes",
                                       "status": "completed", "reversible": False})
    return s


async def _dump(db):
    out = {"_collections": sorted(await db.list_collection_names())}
    for name in COLLECTIONS:
        out[name] = sorted(await db[name].find({}).to_list(None), key=lambda d: str(d["_id"]))
    out["_indexes"] = await db.customers.index_information()
    return out


async def _by_id(db, doc):
    return await db.customers.find_one({"id": doc["id"]}, {"_id": 0})


async def _apply(capsys, cmd, backup_dir, *extra):
    """``--apply`` with the plan id of a dry run taken right before (backfill/merge)."""
    argv = [cmd, "--apply", "--backup-dir", str(backup_dir), *extra]
    if cmd in ("backfill", "merge"):
        code, out = await _run(capsys, cmd, "--dry-run", *extra)
        assert code == 0, out
        argv += ["--plan-id", re.search(r"plan id: (\w+)", out).group(1)]
    return await _run(capsys, *argv)


async def _apply_all(capsys, tmp_path, tag=""):
    outputs = []
    for cmd in ("backfill", "merge", "index"):
        code, out = await _apply(capsys, cmd, tmp_path / f"{cmd}{tag}")
        assert code == 0, out
        outputs.append(out)
    return outputs


# ---------------------------------------------------------------- brief tests

async def test_dry_run_writes_nothing(env, capsys, tmp_path):
    db, name = env
    await _seed(db)
    before = await _dump(db)
    for cmd in ("backfill", "merge", "index", "verify"):
        code, out = await _run(capsys, cmd, "--dry-run")
        assert f"Target DB: {name}" in out, out
        assert "DRY RUN" in out
    assert await _dump(db) == before
    assert not any(tmp_path.iterdir())


async def test_backfill_then_merge_then_index_then_verify_clean(env, capsys, tmp_path):
    db, name = env
    s = await _seed(db)

    code, out = await _run(capsys, "backfill", "--dry-run")
    assert code == 0, out
    # TR: 5 group survivors + 3 singles; UK: 1 survivor + 1 single. Ali's survivor is pre-keyed.
    assert re.search(r"TOTAL .*to_key=10\b", out), out
    assert re.search(r"landline_keys=2\b", out), out
    assert re.search(r"group_member=7\b", out), out

    code, out = await _apply(capsys, "backfill", tmp_path / "b")
    assert code == 0, out
    keys = {c["id"]: (await _by_id(db, c)).get("phone_key") for c in s.all}
    # Singles: punctuation, 0090, landlines (R6), UK 10-digit.
    assert keys[s.deniz["id"]] == "905557770007"
    assert keys[s.ofis["id"]] == "902121234567"
    assert keys[s.ev["id"]] == "902161234567"
    assert keys[s.jane["id"]] == "447700900456"
    # Unusable numbers and shared records stay unkeyed.
    for c in (s.walkin, s.empty, s.short, s.odd, s.mert):
        assert keys[c["id"]] is None, c["name"]
    # Inside groups only the survivor is keyed; the pre-keyed record stays the survivor.
    assert keys[s.canan["id"]] == "905551110001" and keys[s.canan_src["id"]] is None
    assert keys[s.ayse["id"]] == "905552220002" and keys[s.ayse_src["id"]] is None
    assert keys[s.mehmet["id"]] == "905553330003" and keys[s.zeynep["id"]] is None
    assert keys[s.ali_new["id"]] == "905554440004" and keys[s.ali_old["id"]] is None
    assert keys[s.selin["id"]] == "905556660006"
    assert keys[s.selin_1["id"]] is None and keys[s.selin_2["id"]] is None
    assert keys[s.ece["id"]] == "905558880008"
    assert keys[s.john["id"]] == "447700900123" and keys[s.john_src["id"]] is None
    assert (tmp_path / "b" / "backup.jsonl").exists()
    assert (tmp_path / "b" / "restore.py").exists()

    code, out = await _apply(capsys, "merge", tmp_path / "m")
    assert code == 0, out
    tr = {c["id"]: c for c in await db.customers.find({"organization_id": ORG_TR}, {"_id": 0}).to_list(None)}
    for gone in (s.canan_src, s.ayse_src, s.ali_old, s.selin_1, s.selin_2):
        assert gone["id"] not in tr
    assert tr[s.canan["id"]]["total_appointments"] == 5
    assert tr[s.canan["id"]]["completed_appointments"] == 2
    assert tr[s.ali_new["id"]]["total_appointments"] == 3
    assert tr[s.selin["id"]]["total_appointments"] == 5
    assert tr[s.ayse["id"]]["total_appointments"] == 3
    # CD: survivor keyed, the other person flagged shared and unkeyed.
    assert tr[s.mehmet["id"]]["phone_key"] == "905553330003"
    assert tr[s.zeynep["id"]]["shared_phone"] is True and "phone_key" not in tr[s.zeynep["id"]]
    assert tr[s.ece["id"]]["phone_key"] == "905558880008"
    assert tr[s.mert["id"]]["shared_phone"] is True and "phone_key" not in tr[s.mert["id"]]
    # Every survivor holds its key.
    for c in (s.canan, s.ayse, s.ali_new, s.selin):
        assert tr[c["id"]].get("phone_key"), c["name"]
    uk = await db.customers.find({"organization_id": ORG_UK}, {"_id": 0}).to_list(None)
    assert {c["id"] for c in uk} == {s.john["id"], s.jane["id"]}
    assert (await _by_id(db, s.john))["phone_key"] == "447700900123"
    # References re-pointed.
    assert {a["phone"] for a in await db.appointments.find(
        {"customer_name": {"$regex": "^Canan"}}).to_list(None)} == {"905551110001"}
    assert (await db.customer_notes.count_documents({})) == 1
    assert (await db.stripe_customers.count_documents({"customer_phone": "05551110001"})) == 1

    code, out = await _run(capsys, "index", "--apply", "--backup-dir", str(tmp_path / "i"))
    assert code == 0, out
    info = (await db.customers.index_information())[INDEX_NAME]
    assert info["unique"] is True and info["partialFilterExpression"] == PARTIAL_FILTER

    code, out = await _run(capsys, "verify", "--dry-run")
    assert code == 0, out
    assert "keyed duplicates: 0" in out
    assert "unresolved appointment phones: 0" in out
    assert "counter mismatches: 0" in out
    assert "unkeyed keyable customers: 0" in out


async def test_apply_requires_fresh_backup_dir(env, capsys, tmp_path):
    db, _ = env
    await _seed(db)
    before = await _dump(db)
    for cmd in ("backfill", "merge", "index"):
        code, out = await _run(capsys, cmd, "--apply")
        assert code == 2 and "--backup-dir" in out, out
        existing = tmp_path / f"exists-{cmd}"
        existing.mkdir()
        code, out = await _run(capsys, cmd, "--apply", "--backup-dir", str(existing))
        assert code == 2 and "already exists" in out, out
        assert not any(existing.iterdir())
    code, out = await _run(capsys, "backfill")
    assert code == 2, out
    code, out = await _run(capsys, "verify", "--apply", "--backup-dir", str(tmp_path / "v"))
    assert code == 2, out
    assert await _dump(db) == before


async def test_rerun_is_noop(env, capsys, tmp_path):
    db, _ = env
    await _seed(db)
    await _apply_all(capsys, tmp_path)
    after = await _dump(db)
    await _apply_all(capsys, tmp_path, tag="-again")
    assert await _dump(db) == after
    for cmd in ("backfill", "merge", "index"):
        assert (tmp_path / f"{cmd}-again" / "backup.jsonl").read_text() == ""


# ---------------------------------------------------------------- carry-over tests

async def test_merge_dry_run_counts_equal_what_merge_into_does(env, capsys):
    db, _ = env
    await _seed(db)
    cpk = _cpk()
    plans = await cpk.plan_merge(db)
    predicted = {(p.organization_id, src.source_id): src
                 for p in plans for src in p.sources}
    results = await cpk.apply_merge(db, plans, backup=[])
    actual = {(r["organization_id"], r["source_id"]): r for r in results if r["kind"] == "merge"}
    assert set(predicted) == set(actual) and len(actual) == 6
    for k, src in predicted.items():
        assert src.repointed == actual[k]["repointed"], k
        assert src.stripe_left == actual[k]["stripe_customers_left"], k
        assert src.left_for_shared_phone == actual[k]["left_for_shared_phone"], k
    canan = next(src for p in plans for src in p.sources if src.notes_joined)
    assert canan.repointed["appointments"] == 2 and canan.stripe_left == 1
    # The guard defers the first of two same-string sources to the second.
    selin = [p for p in plans if len(p.sources) == 2][0]
    assert [src.repointed["appointments"] for src in selin.sources] == [0, 2]


async def test_merge_report_lists_groups_with_initials_only(env, capsys):
    db, _ = env
    await _seed(db)
    code, out = await _run(capsys, "merge", "--dry-run")
    assert code == 0, out
    group_lines = [line for line in out.splitlines() if line.startswith("[")]
    assert len(group_lines) == 7, out
    assert sum(line.startswith("[A]") for line in group_lines) == 4
    assert sum(line.startswith("[B]") for line in group_lines) == 1
    assert sum(line.startswith("[CD]") for line in group_lines) == 2
    assert any("org=a1b2c3d4" in line and "members=3" in line for line in group_lines)
    assert "C.Ç." in out
    assert "plan id:" in out


async def test_reports_never_print_full_names_or_phones(env, capsys, tmp_path):
    db, name = env
    s = await _seed(db)
    outputs = []
    for cmd in ("backfill", "merge", "index", "verify"):
        outputs.append((await _run(capsys, cmd, "--dry-run"))[1])
    outputs += await _apply_all(capsys, tmp_path)
    outputs.append((await _run(capsys, "verify", "--dry-run"))[1])
    text = "\n".join(outputs).replace(str(tmp_path), "<tmp>").replace(name, "<db>")
    text = re.sub(r"plan id: \w+", "plan id: <id>", text)
    # At most the last 2 digits of a number: no run of 4+ digits anywhere in the reports.
    assert not re.findall(r"\d{4,}", text), re.findall(r"\d{4,}", text)
    for c in s.all:
        if len(c["phone"]) >= 5:
            assert c["phone"] not in text, c["phone"]
        for word in c["name"].split():
            if len(word) >= 3:
                assert not re.search(rf"\b{re.escape(word)}\b", text), word
    for org in (ORG_TR, ORG_UK):
        assert org not in text


async def test_restore_scripts_put_every_document_back(env, capsys, tmp_path):
    db, name = env
    await _seed(db)
    before = await _dump(db)
    await _apply_all(capsys, tmp_path)
    assert await _dump(db) != before
    child_env = {**os.environ, "MONGO_URL": MONGO_URL, "DB_NAME": name}
    for cmd in ("index", "merge", "backfill"):  # newest run first
        proc = subprocess.run([sys.executable, str(tmp_path / cmd / "restore.py")],
                              env=child_env, capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert f"Target DB: {name}" in proc.stdout
    assert await _dump(db) == before


async def test_restore_refuses_another_db(env, capsys, tmp_path):
    db, name = env
    await _seed(db)
    await _apply(capsys, "backfill", tmp_path / "b")
    child_env = {**os.environ, "MONGO_URL": MONGO_URL, "DB_NAME": name + "_other"}
    proc = subprocess.run([sys.executable, str(tmp_path / "b" / "restore.py")],
                          env=child_env, capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0
    assert name in proc.stdout + proc.stderr


async def test_merge_without_backfill_keys_survivors_and_unkeys_cd_others(env, capsys, tmp_path):
    db, _ = env
    a_surv = _cust("905551110001", "Canan Çelik", total=1)
    a_src = _cust("05551110001", "Canan Çelik", created="2026-01-01T00:00:00+00:00")
    # A race left two keyed records for two different people on one number.
    cd_surv = _cust("905553330003", "Mehmet Kaya", total=1, phone_key="905553330003")
    cd_other = _cust("05553330003", "Zeynep Kaya", phone_key="905553330003",
                     created="2026-01-01T00:00:00+00:00")
    await db.customers.insert_many([a_surv, a_src, cd_surv, cd_other])
    await db.appointments.insert_many(_appts("905551110001", "Canan Çelik", 1)
                                      + _appts("905553330003", "Mehmet Kaya", 1))
    code, out = await _apply(capsys, "merge", tmp_path / "m")
    assert code == 0, out
    assert (await _by_id(db, a_surv))["phone_key"] == "905551110001"
    assert await _by_id(db, a_src) is None
    other = await _by_id(db, cd_other)
    assert other["shared_phone"] is True and "phone_key" not in other
    assert (await _by_id(db, cd_surv))["phone_key"] == "905553330003"
    code, out = await _run(capsys, "index", "--apply", "--backup-dir", str(tmp_path / "i"))
    assert code == 0, out


async def test_plan_id_guard_refuses_a_changed_plan(env, capsys, tmp_path):
    db, _ = env
    await _seed(db)
    code, out = await _run(capsys, "merge", "--dry-run")
    plan_id = re.search(r"plan id: (\w+)", out).group(1)
    await db.customers.insert_one(_cust("05559990009", "Yeni Kisi", total=0))
    await db.customers.insert_one(_cust("905559990009", "Yeni Kisi", total=0))
    before = await _dump(db)
    code, out = await _run(capsys, "merge", "--apply", "--backup-dir", str(tmp_path / "m"),
                           "--plan-id", plan_id)
    assert code == 1 and "plan changed" in out, out
    assert await _dump(db) == before


async def test_index_apply_fails_loudly_on_keyed_duplicates(env, capsys, tmp_path):
    db, _ = env
    await db.customers.insert_many([
        _cust("905551110001", "A Bir", phone_key="905551110001"),
        _cust("05551110001", "B Iki", phone_key="905551110001"),
    ])
    code, out = await _run(capsys, "index", "--dry-run")
    assert code == 1 and "keyed duplicates: 1" in out, out
    code, out = await _run(capsys, "index", "--apply", "--backup-dir", str(tmp_path / "i"))
    assert code == 1 and "FAIL" in out and "keyed duplicates: 1" in out, out
    assert INDEX_NAME not in await db.customers.index_information()
    assert await db.migration_log.find_one({"name": INDEX_MARKER}) is None


async def test_index_apply_writes_the_startup_marker(env, capsys, tmp_path):
    db, _ = env
    await _seed(db)
    for cmd in ("backfill", "merge"):
        code, out = await _apply(capsys, cmd, tmp_path / cmd)
        assert code == 0, out
    assert await db.migration_log.find_one({"name": INDEX_MARKER}) is None
    code, out = await _run(capsys, "index", "--dry-run")
    assert code == 0, out
    assert await db.migration_log.find_one({"name": INDEX_MARKER}) is None
    code, out = await _run(capsys, "index", "--apply", "--backup-dir", str(tmp_path / "i"))
    assert code == 0, out
    marker = await db.migration_log.find_one({"name": INDEX_MARKER}, {"_id": 0})
    assert marker["status"] == "applied" and isinstance(marker["applied_at"], str), marker
    assert "marker" in out
    # Re-running keeps exactly one marker.
    code, out = await _run(capsys, "index", "--apply", "--backup-dir", str(tmp_path / "i2"))
    assert code == 0, out
    assert await db.migration_log.count_documents({"name": INDEX_MARKER}) == 1


async def test_restore_of_the_index_run_removes_the_marker(env, capsys, tmp_path):
    db, name = env
    await _seed(db)
    await _apply_all(capsys, tmp_path)
    assert await db.migration_log.find_one({"name": INDEX_MARKER}) is not None
    child_env = {**os.environ, "MONGO_URL": MONGO_URL, "DB_NAME": name}
    proc = subprocess.run([sys.executable, str(tmp_path / "index" / "restore.py")],
                          env=child_env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert INDEX_NAME not in await db.customers.index_information()
    assert await db.migration_log.find_one({"name": INDEX_MARKER}) is None
    assert await db.migration_log.count_documents({}) == 1  # other entries untouched


async def test_verify_reports_problems_without_fixing(env, capsys):
    db, _ = env
    await db.customers.insert_many([
        _cust("905551110001", "A Bir", phone_key="905551110001", total=1),
        _cust("05551110001", "B Iki", phone_key="905551110001"),
        _cust("905552220002", "C Uc", phone_key="905552220002", total=5),  # counter 5, has 1
        _cust("905554440004", "D Dort", phone_key="905554440004"),
        _cust("0", "E Bes"),                                     # walk-in: not keyable
        _cust("905556660006", "F Alti"),                         # keyable, no key, not shared
    ])
    await db.appointments.insert_many(
        _appts("905551110001", "A Bir", 1) + _appts("905552220002", "C Uc", 1)
        + _appts("905553330003", "Nobody Here", 2))
    before = await _dump(db)
    code, out = await _run(capsys, "verify", "--dry-run")
    assert code == 1, out
    assert "keyed duplicates: 1" in out
    assert "unresolved appointment phones: 1" in out
    assert "counter mismatches: 1" in out
    assert "unkeyed keyable customers: 1" in out
    assert re.search(r"org=a1b2c3d4 F\.A\. …06", out), out
    assert "C.U." in out and "stored total=5" in out and "recomputed total=1" in out
    assert await _dump(db) == before


# ---------------------------------------------------------------- ensure_customer_indexes on real Mongo

async def test_ensure_index_spec_as_read_back(env):
    db, _ = env
    assert await ensure_customer_indexes(db) == "created"
    info = (await db.customers.index_information())[INDEX_NAME]
    assert [tuple(k) for k in info["key"]] == [("organization_id", 1), ("phone_key", 1)]
    assert info["unique"] is True
    assert info["partialFilterExpression"] == {"phone_key": {"$exists": True}}
    assert await ensure_customer_indexes(db) == "exists"
    # Partial: unkeyed duplicates allowed, keyed duplicates refused.
    await db.customers.insert_many([_cust("0", "W A"), _cust("0", "W B")])
    await db.customers.insert_one(_cust("905551110001", "K A", phone_key="905551110001"))
    with pytest.raises(OperationFailure) as exc:
        await db.customers.insert_one(_cust("05551110001", "K B", phone_key="905551110001"))
    assert exc.value.code == 11000


async def test_ensure_index_build_over_duplicates(env):
    db, _ = env
    await db.customers.insert_many([
        _cust("905551110001", "A Bir", phone_key="905551110001"),
        _cust("05551110001", "B Iki", phone_key="905551110001"),
    ])
    with pytest.raises(OperationFailure) as exc:  # DuplicateKeyError is a subclass
        await db.customers.create_index(
            [("organization_id", 1), ("phone_key", 1)], name=INDEX_NAME, unique=True,
            partialFilterExpression=PARTIAL_FILTER)
    assert exc.value.code == 11000
    assert await ensure_customer_indexes(db) == "skipped_duplicates"
    assert INDEX_NAME not in await db.customers.index_information()


async def test_concurrent_ensure_customer_indexes(env):
    db, _ = env
    await db.customers.insert_many([_cust(f"9055500000{i:02d}", f"N {i}") for i in range(50)])
    results = await asyncio.gather(*(ensure_customer_indexes(db) for _ in range(4)))
    assert set(results) <= {"created", "exists"} and "created" in results, results
    info = (await db.customers.index_information())[INDEX_NAME]
    assert info["unique"] is True and info["partialFilterExpression"] == PARTIAL_FILTER


# ---------------------------------------------------------------- fix round 1

async def test_apply_requires_plan_id(env, capsys, tmp_path):
    db, _ = env
    await _seed(db)
    before = await _dump(db)
    for cmd in ("backfill", "merge"):
        code, out = await _run(capsys, cmd, "--apply", "--backup-dir", str(tmp_path / cmd))
        assert code == 2 and "--plan-id" in out, out
        assert not (tmp_path / cmd).exists()
    assert await _dump(db) == before


async def test_merge_never_merges_shared_phone_records(env, capsys, tmp_path):
    """R12: a "Farklı kişi" record is never merged by the script, even with the same name."""
    db, _ = env
    surv = _cust("905551110001", "Canan Çelik", total=1)
    plain = _cust("+90 555 111 00 01", "Canan Çelik", created="2026-01-01T00:00:00+00:00")
    shared = _cust("05551110001", "Canan Çelik", shared_phone=True,
                   created="2026-02-01T00:00:00+00:00")
    await db.customers.insert_many([surv, plain, shared])
    await db.appointments.insert_many(_appts("905551110001", "Canan Çelik", 1))
    shared_before = await _by_id(db, shared)
    code, out = await _run(capsys, "merge", "--dry-run")
    assert code == 0, out
    assert "shared, skipped: C.Ç. …01" in out, out
    assert "merge 1 into survivor" in out, out
    code, out = await _apply(capsys, "merge", tmp_path / "m")
    assert code == 0, out
    assert await _by_id(db, plain) is None
    assert await _by_id(db, shared) == shared_before
    assert (await _by_id(db, surv))["phone_key"] == "905551110001"


async def test_merge_error_is_reported_without_exception_text(env, capsys, tmp_path, monkeypatch):
    db, _ = env
    await _seed(db)
    cpk = _cpk()

    async def boom(*a, **kw):
        raise ValueError(f"E11000 dup key {ORG_TR} 905551110001 Canan Çelik")

    monkeypatch.setattr(cpk, "merge_into", boom)
    code, out = await _apply(capsys, "merge", tmp_path / "m")
    assert code == 1, out
    assert "ValueError" in out
    for secret in ("E11000", ORG_TR, "905551110001", "Canan"):
        assert secret not in out, secret


async def test_crash_is_reported_without_exception_text(env, capsys, tmp_path, monkeypatch):
    db, _ = env
    await _seed(db)
    cpk = _cpk()

    async def boom(*a, **kw):
        raise RuntimeError(f"dup key {ORG_TR} 905551110001 Canan Çelik")

    monkeypatch.setattr(cpk, "apply_backfill", boom)
    code, out = await _apply(capsys, "backfill", tmp_path / "b")
    assert code == 1, out
    assert "CRASHED" in out and "RuntimeError" in out
    for secret in (ORG_TR, "905551110001", "Canan"):
        assert secret not in out, secret
    import json
    assert json.loads((tmp_path / "b" / "meta.json").read_text())["status"] == "crashed"


class _StaleCustomers:
    """find_one returns the survivor as it was before someone keyed it meanwhile."""

    def __init__(self, real):
        self.real = real

    async def find_one(self, *a, **kw):
        doc = await self.real.find_one(*a, **kw)
        if doc:
            doc.pop("phone_key", None)
        return doc

    async def update_one(self, *a, **kw):
        return await self.real.update_one(*a, **kw)


class _StaleDB:
    def __init__(self, db):
        self.customers = _StaleCustomers(db.customers)


async def test_set_survivor_key_says_set_only_when_it_wrote(env):
    db, _ = env
    cpk = _cpk()
    surv = _cust("905551110001", "Canan Çelik", phone_key="905551110001")
    await db.customers.insert_one(dict(surv))
    plan = cpk.GroupPlan(ORG_TR, "905551110001", "A", [surv], surv, set_survivor_key=True)
    assert await cpk._set_survivor_key(_StaleDB(db), plan, []) != "set"


async def test_index_rejects_org_id(env, capsys, tmp_path):
    for argv in (["index", "--dry-run", "--org-id", ORG_TR],
                 ["index", "--apply", "--backup-dir", str(tmp_path / "i"), "--org-id", ORG_TR]):
        code, out = await _run(capsys, *argv)
        assert code == 2 and "--org-id" in out, out
    assert not (tmp_path / "i").exists()


async def test_verify_fails_on_an_unkeyed_keyable_customer_alone(env, capsys):
    db, _ = env
    await db.customers.insert_many([_cust("905556660006", "F Alti"), _cust("0", "E Bes")])
    code, out = await _run(capsys, "verify", "--dry-run")
    assert "keyed duplicates: 0" in out and "counter mismatches: 0" in out, out
    assert "unkeyed keyable customers: 1" in out
    assert code == 1 and "VERIFY FAIL" in out, out
