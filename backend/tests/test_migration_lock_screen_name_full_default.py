"""One-time migration: a stored "initials" lock_screen_name_mode is a default artifact.

No UI has ever let an org choose the mode, so every stored "initials" came from the old
model default. Removing it lets the "missing means full" rule apply (owner decision).
"""

import importlib

from financial.migrations import runner
from tests.live_activity_fakes import FakeDB

NAME = "20261116_lock_screen_name_full_default"


def _migration():
    return importlib.import_module(f"financial.migrations.{NAME}")


def _seed(db):
    db.settings.docs = [
        {"organization_id": "org-initials", "lock_screen_name_mode": "initials"},
        {"organization_id": "org-full", "lock_screen_name_mode": "full"},
        {"organization_id": "org-hidden", "lock_screen_name_mode": "hidden"},
        {"organization_id": "org-missing"},
    ]


def _modes(db):
    return {d["organization_id"]: d.get("lock_screen_name_mode", "<missing>") for d in db.settings.docs}


async def test_up_unsets_only_the_stored_initials():
    db = FakeDB()
    _seed(db)

    await _migration().up(db)

    assert _modes(db) == {
        "org-initials": "<missing>",
        "org-full": "full",
        "org-hidden": "hidden",
        "org-missing": "<missing>",
    }
    writes = [entry for entry in db.log if entry[1] != "find"]
    assert writes == [(
        "settings",
        "update_many",
        ({"lock_screen_name_mode": "initials"}, {"$unset": {"lock_screen_name_mode": ""}}),
    )]


async def test_up_is_idempotent():
    db = FakeDB()
    _seed(db)

    await _migration().up(db)
    after_first = _modes(db)
    await _migration().up(db)

    assert _modes(db) == after_first


async def test_runner_applies_it_once_and_records_it():
    db = FakeDB()
    _seed(db)
    # Earlier migrations already ran in every environment; isolate this one.
    for name in runner._discover_migration_modules():
        if name != NAME:
            db.migration_log.docs.append({"name": name, "status": "completed"})

    first = await runner.apply_all(db)
    db.settings.docs.append({"organization_id": "org-late", "lock_screen_name_mode": "initials"})
    second = await runner.apply_all(db)

    assert first["applied"] == [NAME] and first["errors"] == []
    assert second["applied"] == []
    record = next(d for d in db.migration_log.docs if d["name"] == NAME)
    assert record["status"] == "completed"
    assert _modes(db)["org-initials"] == "<missing>"
    # Recorded as run: the runner never touches settings again.
    assert _modes(db)["org-late"] == "initials"
