"""
Financial Audit Logger — standardized entry-writing helpers.

Writes to `financial_audit_log` collection (indexes created via schemas).

Every critical financial action should log via `write_audit()`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Known actions (centralized for easy filtering in SuperAdmin UI)
ACTIONS = {
    "refund_request_created",
    "refund_request_approved",
    "refund_request_rejected",
    "refund_request_escalated",
    "batch_created",
    "batch_wise_prepared",
    "batch_funded",
    "batch_failed",
    "batch_rolled_back",
    "wallet_debit_applied",
    "wallet_credit_applied",
    "wallet_frozen",
    "wallet_payout_stopped",
    "wallet_payout_restored",
    "tier_changed",
    "commission_preference_changed",
    "feature_flag_changed",
    "dlq_manual_retry",
    "dlq_manual_resolve",
    "dlq_manual_abandon",
    "force_state_transition",
    "dispute_opened",
    "dispute_resolved",
}


async def write_audit(
    db,
    *,
    organization_id: str,
    actor: str,
    actor_role: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    target_entity_type: Optional[str] = None,
    target_entity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Insert a single audit log entry. Never raises; logs on failure.
    """
    if action not in ACTIONS:
        logger.warning("audit: unknown action %r (allowing)", action)

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id or "",
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "details": details or {},
        "target_entity_type": target_entity_type,
        "target_entity_id": target_entity_id,
        "before": before,
        "after": after,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": now,
    }
    try:
        await db.financial_audit_log.insert_one(doc)
    except Exception as e:
        logger.error("financial_audit_log insert failed: %s", e)
    return doc


async def list_audits(
    db,
    *,
    organization_id: Optional[str] = None,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100,
    since_iso: Optional[str] = None,
) -> list:
    query: Dict[str, Any] = {}
    if organization_id:
        query["organization_id"] = organization_id
    if action:
        query["action"] = action
    if actor:
        query["actor"] = actor
    if since_iso:
        query["created_at"] = {"$gte": since_iso}

    cursor = db.financial_audit_log.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)
