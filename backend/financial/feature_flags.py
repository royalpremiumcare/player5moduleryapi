"""
PLANN Financial Engine — Feature Flag System (Hybrid: env + DB)

Usage:
    # Global env flag (requires restart):
    if is_env_flag_enabled("FEATURE_GROSS_UP"):
        ...

    # DB flag with org override (hot-reloadable):
    if await is_feature_enabled(db, "refund_requests_ui", organization_id=org_id):
        ...

Rules:
  - Env flags: critical backend flows (gross-up, state machine, negative balance)
  - DB flags: UI-facing features with canary rollout (refund requests UI, etc.)
  - DB flags have per-org override, global default, and emergency disable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ENV FLAGS — global on/off, controlled via backend/.env
# ---------------------------------------------------------------------------

ENV_FLAGS = {
    "FEATURE_GROSS_UP": False,
    "FEATURE_NEW_STATE_MACHINE": False,
    "FEATURE_WEDNESDAY_BATCH": False,
    "FEATURE_NEGATIVE_BALANCE": False,
    "FEATURE_REFUND_REQUESTS_BACKEND": False,
    "FEATURE_WEBHOOK_REPLAY_GUARD": False,
    "FEATURE_DLQ": False,
    "FEATURE_EXPIRY_CRONS": False,
    "FEATURE_MULTI_LAYER_RATE_LIMIT": False,
}


def is_env_flag_enabled(flag_name: str, default: bool = False) -> bool:
    """Check a global env-based feature flag. Restart required to change."""
    if flag_name not in ENV_FLAGS:
        logger.warning("Unknown env flag: %s (treating as disabled)", flag_name)
        return default
    value = os.getenv(flag_name)
    if value is None:
        return ENV_FLAGS[flag_name] or default
    return value.lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# DB FLAGS — org-level canary rollout, hot-reloadable
# ---------------------------------------------------------------------------

DB_FLAG_REGISTRY = {
    "refund_requests_ui": {
        "description": "İade talebi akışı (işletme buton + backend endpoint). Kapatılırsa yeni iade talepleri kabul edilmez.",
        "global_default": True,
    },
}


async def is_feature_enabled(
    db,
    flag_name: str,
    organization_id: Optional[str] = None,
    default: Optional[bool] = None,
) -> bool:
    """
    Check a DB-based feature flag with org-level override.

    Priority (highest wins):
      1. Emergency disable (kill switch) → always False
      2. Per-org override (if organization_id given)
      3. Global default from DB
      4. Registry default
      5. `default` arg (safe fallback)
    """
    if flag_name not in DB_FLAG_REGISTRY:
        logger.warning("Unknown DB flag: %s", flag_name)
        return False if default is None else default

    registry_entry = DB_FLAG_REGISTRY[flag_name]

    try:
        doc = await db.feature_flags.find_one({"name": flag_name})
    except Exception as e:
        logger.error("feature_flags query failed for %s: %s", flag_name, e)
        return registry_entry["global_default"] if default is None else default

    if not doc:
        return registry_entry["global_default"] if default is None else default

    # Kill switch — immediate disable
    if doc.get("emergency_disable"):
        return False

    # Per-org override
    if organization_id:
        overrides = doc.get("org_overrides") or {}
        if organization_id in overrides:
            return bool(overrides[organization_id])

    return bool(doc.get("global_default", registry_entry["global_default"]))


async def set_flag_global(db, flag_name: str, value: bool, updated_by: str) -> None:
    """SuperAdmin: set the global default for a DB flag."""
    if flag_name not in DB_FLAG_REGISTRY:
        raise ValueError(f"Unknown DB flag: {flag_name}")
    now = datetime.now(timezone.utc).isoformat()
    await db.feature_flags.update_one(
        {"name": flag_name},
        {
            "$set": {
                "name": flag_name,
                "global_default": bool(value),
                "description": DB_FLAG_REGISTRY[flag_name]["description"],
                "updated_at": now,
                "updated_by": updated_by,
            },
            "$setOnInsert": {
                "org_overrides": {},
                "emergency_disable": False,
                "created_at": now,
            },
        },
        upsert=True,
    )
    logger.info("feature_flag global: %s = %s (by %s)", flag_name, value, updated_by)


async def set_flag_org_override(
    db, flag_name: str, organization_id: str, value: Optional[bool], updated_by: str
) -> None:
    """
    SuperAdmin: add/remove org-level override.
    value=None removes the override.
    """
    if flag_name not in DB_FLAG_REGISTRY:
        raise ValueError(f"Unknown DB flag: {flag_name}")
    now = datetime.now(timezone.utc).isoformat()
    key = f"org_overrides.{organization_id}"
    if value is None:
        await db.feature_flags.update_one(
            {"name": flag_name},
            {"$unset": {key: ""}, "$set": {"updated_at": now, "updated_by": updated_by}},
            upsert=True,
        )
    else:
        await db.feature_flags.update_one(
            {"name": flag_name},
            {
                "$set": {
                    key: bool(value),
                    "updated_at": now,
                    "updated_by": updated_by,
                    "description": DB_FLAG_REGISTRY[flag_name]["description"],
                },
                "$setOnInsert": {
                    "name": flag_name,
                    "global_default": DB_FLAG_REGISTRY[flag_name]["global_default"],
                    "emergency_disable": False,
                    "created_at": now,
                },
            },
            upsert=True,
        )
    logger.info(
        "feature_flag org_override: %s[%s] = %s (by %s)",
        flag_name, organization_id, value, updated_by,
    )


async def set_emergency_disable(db, flag_name: str, disabled: bool, updated_by: str) -> None:
    """Kill switch: force a flag to always return False."""
    if flag_name not in DB_FLAG_REGISTRY:
        raise ValueError(f"Unknown DB flag: {flag_name}")
    now = datetime.now(timezone.utc).isoformat()
    await db.feature_flags.update_one(
        {"name": flag_name},
        {
            "$set": {
                "emergency_disable": bool(disabled),
                "updated_at": now,
                "updated_by": updated_by,
            },
            "$setOnInsert": {
                "name": flag_name,
                "global_default": DB_FLAG_REGISTRY[flag_name]["global_default"],
                "description": DB_FLAG_REGISTRY[flag_name]["description"],
                "org_overrides": {},
                "created_at": now,
            },
        },
        upsert=True,
    )
    if disabled:
        logger.critical("feature_flag EMERGENCY_DISABLE: %s by %s", flag_name, updated_by)
    else:
        logger.info("feature_flag emergency_disable cleared: %s by %s", flag_name, updated_by)


async def list_all_flags(db) -> Dict[str, Any]:
    """Return a complete flag state map for SuperAdmin UI."""
    result: Dict[str, Any] = {
        "env_flags": {
            name: {
                "enabled": is_env_flag_enabled(name),
                "default": default,
                "requires_restart": True,
            }
            for name, default in ENV_FLAGS.items()
        },
        "db_flags": {},
    }

    db_docs = {}
    try:
        async for doc in db.feature_flags.find({}):
            db_docs[doc["name"]] = doc
    except Exception as e:
        logger.error("list_all_flags query failed: %s", e)

    for name, meta in DB_FLAG_REGISTRY.items():
        doc = db_docs.get(name, {})
        result["db_flags"][name] = {
            "description": meta["description"],
            "global_default": doc.get("global_default", meta["global_default"]),
            "emergency_disable": doc.get("emergency_disable", False),
            "org_overrides": doc.get("org_overrides") or {},
            "updated_at": doc.get("updated_at"),
            "updated_by": doc.get("updated_by"),
        }

    return result


# MongoDB index for feature_flags collection
FEATURE_FLAG_INDEXES = [
    {"keys": [("name", 1)], "unique": True},
]
