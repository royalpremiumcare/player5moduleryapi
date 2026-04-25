"""
Operation-level audit (plan): request_id, actor, org, action, target_kind, target_ids, result.
AUDIT_LOGS_ENABLED kapalıysa yazılmaz — create_audit_log ile aynı bayrak.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

AUDIT_LOGS_ENABLED = os.environ.get("AUDIT_LOGS_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)


async def log_operation_audit(
    db,
    *,
    request_id: str,
    organization_id: str,
    actor_user_id: str,
    action: str,
    target_kind: str,
    target_ids: List[str],
    result: str,
    error_code: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not AUDIT_LOGS_ENABLED:
        return
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "request_id": request_id,
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "target_kind": target_kind,
            "target_ids": target_ids[:100],
            "result": result,
            "error_code": error_code,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.operation_audit_logs.insert_one(doc)
    except Exception as e:
        logger.warning(f"operation_audit insert failed: {e}", exc_info=True)
