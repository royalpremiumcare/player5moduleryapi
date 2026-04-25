"""
Migration Runner — applies reversible migrations with checkpointing.

Usage:
    from financial.migrations import runner
    await runner.apply_all(db)          # forward (up)
    await runner.rollback_last(db)      # rollback (down) the last applied migration
    status = await runner.status(db)    # list applied vs pending
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from datetime import datetime, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

_MIGRATION_PACKAGE = "financial.migrations"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _discover_migration_modules() -> List[str]:
    """Find migration modules named YYYYMMDD_<name>.py in the package."""
    import financial.migrations as pkg

    names: List[str] = []
    for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if ispkg:
            continue
        if modname in ("runner", "__init__"):
            continue
        # Expect YYYYMMDD_... format
        if len(modname) < 9 or not modname[:8].isdigit() or modname[8] != "_":
            logger.debug("Skipping non-migration module: %s", modname)
            continue
        names.append(modname)
    names.sort()
    return names


def _load_module(modname: str):
    return importlib.import_module(f"{_MIGRATION_PACKAGE}.{modname}")


# ---------------------------------------------------------------------------
# Log operations
# ---------------------------------------------------------------------------

async def _ensure_indexes(db) -> None:
    await db.migration_log.create_index("name", unique=True)
    await db.migration_log.create_index([("applied_at", -1)])


async def _record_up(db, name: str, reversible: bool, note: str = "") -> None:
    await db.migration_log.update_one(
        {"name": name},
        {
            "$set": {
                "name": name,
                "status": "completed",
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "reversible": reversible,
                "note": note,
                "rolled_back_at": None,
            }
        },
        upsert=True,
    )


async def _record_down(db, name: str) -> None:
    await db.migration_log.update_one(
        {"name": name},
        {
            "$set": {
                "status": "rolled_back",
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )


async def _is_applied(db, name: str) -> bool:
    doc = await db.migration_log.find_one({"name": name, "status": "completed"})
    return doc is not None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def apply_all(db, dry_run: bool = False) -> Dict[str, Any]:
    """Apply all pending migrations in order."""
    await _ensure_indexes(db)
    pending: List[str] = []
    applied: List[str] = []
    errors: List[Dict[str, str]] = []

    for modname in _discover_migration_modules():
        if await _is_applied(db, modname):
            continue
        pending.append(modname)

    if dry_run:
        return {"pending": pending, "would_apply": len(pending), "dry_run": True}

    for modname in pending:
        mod = _load_module(modname)
        reversible = bool(getattr(mod, "REVERSIBLE", True))
        try:
            logger.info("migration: up %s", modname)
            await mod.up(db)
            await _record_up(db, modname, reversible, getattr(mod, "DESCRIPTION", ""))
            applied.append(modname)
        except Exception as e:
            logger.exception("migration failed: %s", modname)
            errors.append({"name": modname, "error": str(e)})
            break  # stop on first failure

    return {"applied": applied, "errors": errors, "pending_before": pending}


async def rollback_last(db) -> Dict[str, Any]:
    """Rollback the most recently applied reversible migration."""
    await _ensure_indexes(db)
    doc = await db.migration_log.find_one(
        {"status": "completed", "reversible": True},
        sort=[("applied_at", -1)],
    )
    if not doc:
        return {"rolled_back": None, "reason": "no_reversible_migration_applied"}

    modname = doc["name"]
    mod = _load_module(modname)
    if not hasattr(mod, "down"):
        return {"rolled_back": None, "reason": f"migration {modname} has no down()"}

    try:
        logger.info("migration: down %s", modname)
        await mod.down(db)
        await _record_down(db, modname)
        return {"rolled_back": modname}
    except Exception as e:
        logger.exception("migration rollback failed: %s", modname)
        return {"rolled_back": None, "error": str(e), "name": modname}


async def status(db) -> Dict[str, Any]:
    await _ensure_indexes(db)
    all_names = _discover_migration_modules()
    applied_names: set = set()
    async for doc in db.migration_log.find({"status": "completed"}):
        applied_names.add(doc["name"])

    return {
        "all": all_names,
        "applied": sorted(applied_names),
        "pending": [n for n in all_names if n not in applied_names],
    }
