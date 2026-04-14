"""
PLANN Financial Engine — Payout Service

Dual-market batch payout engine:
  - GBP market: Wise BACS local transfer (£0.20-0.40 cost)
  - TRY market: Wise GBP→TRY cross-border transfer (~£5-6 cost)

Handles pre-flight checks, batch creation, chunking (max 1000/batch),
and status tracking.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .money import get_tier_config, format_display
from .schemas import PayoutBatch, PayoutBatchItem
from .state_machine import StateMachine
from . import wise_service

logger = logging.getLogger(__name__)

WISE_MAX_TRANSFERS_PER_BATCH = 1000


# ---------------------------------------------------------------------------
# Pre-flight Checks (Computed Gate)
# ---------------------------------------------------------------------------

async def check_payout_eligibility(
    db,
    organization_id: str,
) -> Dict[str, Any]:
    """
    Computed payout_enabled gate.
    Returns {eligible: bool, reasons: [...], wallet: {...}, tier_config: {...}}
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        return {"eligible": False, "reasons": ["settings_not_found"]}

    wallet = await db.merchant_wallets.find_one({"organization_id": organization_id})
    if not wallet:
        return {"eligible": False, "reasons": ["wallet_not_found"]}

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    tier_cfg = get_tier_config(base_currency, tier)

    reasons = []

    if not settings.get("kyc_verified", False):
        reasons.append("kyc_not_verified")

    if not settings.get("wise_recipient_verified", False):
        reasons.append("recipient_not_verified")

    if wallet.get("frozen_balance_minor", 0) > 0:
        reasons.append("has_frozen_balance")

    iban_changed_at = settings.get("iban_changed_at")
    if iban_changed_at:
        from datetime import timedelta
        import os
        cooldown_hours = int(os.getenv("IBAN_CHANGE_COOLDOWN_HOURS", "48"))
        changed = datetime.fromisoformat(iban_changed_at)
        if datetime.now(timezone.utc) - changed < timedelta(hours=cooldown_hours):
            reasons.append("iban_cooldown_active")

    available = wallet.get("available_balance_minor", 0)
    refund_reserve = wallet.get("refund_reserve_minor", 0)
    effective_available = max(0, available - refund_reserve)

    if effective_available < tier_cfg.limit_minor:
        reasons.append("below_tier_limit")

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "effective_available_minor": effective_available,
        "tier_limit_minor": tier_cfg.limit_minor,
        "tier": tier,
        "base_currency": base_currency,
        "progress_pct": round(min(effective_available / tier_cfg.limit_minor * 100, 100), 1) if tier_cfg.limit_minor > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Batch Creation
# ---------------------------------------------------------------------------

async def create_payout_batch(
    db,
    market: str,
    eligible_orgs: List[Dict[str, Any]],
    triggered_by: str = "auto",
    triggered_by_user: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Create payout batch(es) for a given market.
    Chunks into multiple batches if > 1000 transfers.

    Args:
        market: "GBP" or "TRY"
        eligible_orgs: List of {organization_id, amount_display_minor, amount_gbp_minor, wise_recipient_id}
        triggered_by: "auto" | "manual" | "cron" | "superadmin"

    Returns:
        List of created batch documents
    """
    if not eligible_orgs:
        return []

    rail = "bacs" if market == "GBP" else "local_tr"
    chunks = _chunk_list(eligible_orgs, WISE_MAX_TRANSFERS_PER_BATCH)
    batches = []

    for idx, chunk in enumerate(chunks):
        items = []
        total_gbp = 0

        for org in chunk:
            item = PayoutBatchItem(
                organization_id=org["organization_id"],
                base_currency=market,
                amount_display_minor=org["amount_display_minor"],
                amount_gbp_minor=org["amount_gbp_minor"],
                wise_recipient_id=org["wise_recipient_id"],
            ).model_dump()
            items.append(item)
            total_gbp += org["amount_gbp_minor"]

        batch = PayoutBatch(
            payout_market=market,
            payout_provider="wise",
            payout_rail=rail,
            chunk_index=idx,
            chunk_total=len(chunks),
            status="draft",
            items=items,
            total_gbp_minor=total_gbp,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
        ).model_dump()

        await db.payout_batches.insert_one(batch)
        batches.append(batch)

        logger.info(
            "Payout batch created: id=%s market=%s rail=%s items=%d chunk=%d/%d total_gbp=%d",
            batch["id"], market, rail, len(items), idx + 1, len(chunks), total_gbp,
        )

    return batches


async def process_payout_batch(db, batch_id: str) -> Dict[str, Any]:
    """
    Process a draft payout batch through the Wise pipeline:
    1. Create quotes for each item
    2. Create batch group
    3. Add transfers
    4. Complete and fund batch group
    5. Reserve wallet balances

    Sandbox with Wise credentials: Uses real Wise sandbox API (api.sandbox.transferwise.tech).
    Sandbox without credentials: Mock simulation, instant payout.
    """
    batch = await db.payout_batches.find_one({"id": batch_id})
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")

    if batch["status"] != "draft":
        raise ValueError(f"Batch {batch_id} is not in draft status: {batch['status']}")

    sm = StateMachine(db)
    is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"
    has_wise_creds = bool(os.getenv("WISE_API_TOKEN")) and bool(os.getenv("WISE_PROFILE_ID"))

    if is_sandbox and not has_wise_creds:
        return await _process_sandbox_mock_batch(db, sm, batch, batch_id)

    return await _process_wise_batch(db, sm, batch, batch_id, is_sandbox)


async def _process_sandbox_mock_batch(
    db, sm: StateMachine, batch: Dict[str, Any], batch_id: str,
) -> Dict[str, Any]:
    """Sandbox without Wise credentials: skip Wise API, simulate instant paid_out."""
    now = datetime.now(timezone.utc).isoformat()
    transitioned = 0

    for i, item in enumerate(batch["items"]):
        mock_transfer_id = f"sandbox_transfer_{uuid.uuid4().hex[:12]}"
        batch["items"][i]["wise_transfer_id"] = mock_transfer_id
        batch["items"][i]["item_status"] = "completed"

        available_txs = await db.merchant_transactions.find({
            "organization_id": item["organization_id"],
            "state": "available",
        }).to_list(length=500)

        for tx in available_txs:
            try:
                await sm.transition(
                    tx_id=tx["id"],
                    new_state="reserved",
                    trigger="sandbox_payout",
                    metadata={"payout_batch_id": batch_id, "wise_transfer_id": mock_transfer_id},
                )
                await sm.transition(
                    tx_id=tx["id"],
                    new_state="paid_out",
                    trigger="sandbox_payout_instant",
                    metadata={"payout_batch_id": batch_id},
                )
                transitioned += 1
            except Exception as e:
                logger.warning("Sandbox transition failed for tx %s: %s", tx["id"], e)

    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {
            "status": "completed",
            "items": batch["items"],
            "completed_at": now,
        }},
    )

    logger.info("Sandbox payout batch completed instantly: id=%s items=%d txs=%d", batch_id, len(batch["items"]), transitioned)
    return {"status": "completed", "batch_id": batch_id, "sandbox": True}


async def _process_wise_batch(
    db, sm: StateMachine, batch: Dict[str, Any], batch_id: str,
    is_sandbox: bool = False,
) -> Dict[str, Any]:
    """Full Wise API pipeline (quote → batch group → fund). Works with both sandbox and production API."""
    market = batch["payout_market"]
    source_currency = "GBP"
    target_currency = market

    await db.payout_batches.update_one(
        {"id": batch_id},
        {"$set": {"status": "quoting"}},
    )

    try:
        for i, item in enumerate(batch["items"]):
            quote_result = await wise_service.create_quote(
                db=db,
                organization_id=item["organization_id"],
                source_currency=source_currency,
                target_currency=target_currency,
                source_amount_minor=item["amount_gbp_minor"],
                payout_batch_id=batch_id,
                target_amount_minor=item["amount_display_minor"] if not item["amount_gbp_minor"] else 0,
            )
            batch["items"][i]["wise_quote_id"] = quote_result["quote_doc"]["wise_quote_id"]

        await db.payout_batches.update_one(
            {"id": batch_id},
            {"$set": {"status": "quoted", "items": batch["items"]}},
        )

        use_single = is_sandbox
        if not is_sandbox:
            try:
                group = await wise_service.create_batch_group(source_currency)
                await db.payout_batches.update_one(
                    {"id": batch_id},
                    {"$set": {
                        "wise_batch_group_id": group["id"],
                        "wise_batch_group_version": group["version"],
                    }},
                )

                for i, item in enumerate(batch["items"]):
                    transfer = await wise_service.add_transfer_to_batch(
                        batch_group_id=group["id"],
                        quote_id=item["wise_quote_id"],
                        recipient_id=item["wise_recipient_id"],
                        customer_transaction_id=item["customer_transaction_id"],
                    )
                    batch["items"][i]["wise_transfer_id"] = str(transfer.get("id", ""))
                    batch["items"][i]["item_status"] = "funded"

                await db.payout_batches.update_one(
                    {"id": batch_id},
                    {"$set": {"items": batch["items"]}},
                )

                current_group = await wise_service.get_batch_group(group["id"])
                latest_version = current_group.get("version", group["version"])

                completed = await wise_service.complete_batch_group(
                    group["id"], latest_version,
                )
                new_version = completed.get("version", group["version"])

                await wise_service.fund_batch_group(group["id"])

                await db.payout_batches.update_one(
                    {"id": batch_id},
                    {"$set": {
                        "status": "processing",
                        "wise_batch_group_version": new_version,
                    }},
                )
            except Exception as batch_err:
                logger.warning(
                    "Batch API failed for %s, falling back to single transfers: %s",
                    batch_id, batch_err,
                )
                use_single = True
                for i in range(len(batch["items"])):
                    batch["items"][i]["wise_transfer_id"] = ""
                    batch["items"][i]["item_status"] = "pending"

        if use_single:
            for i, item in enumerate(batch["items"]):
                transfer = await wise_service.create_single_transfer(
                    quote_id=item["wise_quote_id"],
                    recipient_id=item["wise_recipient_id"],
                    customer_transaction_id=item["customer_transaction_id"],
                )
                transfer_id = str(transfer.get("id", ""))
                batch["items"][i]["wise_transfer_id"] = transfer_id
                batch["items"][i]["item_status"] = "funded"

                await wise_service.fund_single_transfer(transfer_id)

            await db.payout_batches.update_one(
                {"id": batch_id},
                {"$set": {"status": "processing", "items": batch["items"]}},
            )

        for item in batch["items"]:
            available_txs = await db.merchant_transactions.find({
                "organization_id": item["organization_id"],
                "state": "available",
            }).to_list(length=500)

            for tx in available_txs:
                try:
                    await sm.transition(
                        tx_id=tx["id"],
                        new_state="reserved",
                        trigger="payout_batch_funded",
                        metadata={
                            "payout_batch_id": batch_id,
                            "wise_transfer_id": item.get("wise_transfer_id", ""),
                        },
                    )
                except Exception as e:
                    logger.warning("Reserve transition failed for tx %s: %s", tx["id"], e)

        if is_sandbox:
            now = datetime.now(timezone.utc).isoformat()
            for item in batch["items"]:
                reserved_txs = await db.merchant_transactions.find({
                    "organization_id": item["organization_id"],
                    "state": "reserved",
                    "payout_batch_id": batch_id,
                }).to_list(length=500)

                for tx in reserved_txs:
                    try:
                        await sm.transition(
                            tx_id=tx["id"],
                            new_state="paid_out",
                            trigger="sandbox_wise_instant",
                            metadata={"payout_batch_id": batch_id},
                        )
                    except Exception as e:
                        logger.warning("Sandbox paid_out transition failed for tx %s: %s", tx["id"], e)

            await db.payout_batches.update_one(
                {"id": batch_id},
                {"$set": {"status": "completed", "completed_at": now}},
            )
            logger.info("Sandbox Wise payout completed: id=%s", batch_id)
            return {"status": "completed", "batch_id": batch_id, "sandbox_wise": True}

        logger.info("Payout batch processing started: id=%s", batch_id)
        return {"status": "processing", "batch_id": batch_id}

    except Exception as e:
        logger.exception("Payout batch processing failed: id=%s", batch_id)
        await db.payout_batches.update_one(
            {"id": batch_id},
            {"$set": {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        raise


# ---------------------------------------------------------------------------
# Auto-Payout Batch Builder
# ---------------------------------------------------------------------------

async def build_auto_payout_batches(
    db,
    triggered_by: str = "cron",
) -> Dict[str, Any]:
    """
    Build and process auto-payout batches for both markets.
    Called by auto_payout_job cron.

    1. Find all orgs with payout_mode=auto and sufficient balance
    2. Split by market (GBP / TRY)
    3. Create and process separate batches
    """
    results = {"gbp_batches": [], "try_batches": [], "skipped": []}

    cursor = db.settings.find({"payout_mode": "auto"})
    gbp_eligible = []
    try_eligible = []

    async for settings in cursor:
        org_id = settings["organization_id"]
        eligibility = await check_payout_eligibility(db, org_id)

        if not eligibility["eligible"]:
            results["skipped"].append({
                "organization_id": org_id,
                "reasons": eligibility["reasons"],
            })
            continue

        wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
        if not wallet:
            continue

        base_currency = settings.get("base_currency", "TRY")
        effective_available = eligibility["effective_available_minor"]

        org_data = {
            "organization_id": org_id,
            "amount_display_minor": effective_available,
            "amount_gbp_minor": wallet.get("pool_balance_gbp_minor", 0) if base_currency == "TRY" else effective_available,
            "wise_recipient_id": settings.get("wise_recipient_id") or "",
        }

        if base_currency == "GBP":
            gbp_eligible.append(org_data)
        else:
            try_eligible.append(org_data)

    if gbp_eligible:
        batches = await create_payout_batch(db, "GBP", gbp_eligible, triggered_by)
        for batch in batches:
            try:
                await process_payout_batch(db, batch["id"])
                results["gbp_batches"].append(batch["id"])
            except Exception as e:
                logger.error("GBP batch %s failed: %s", batch["id"], e)

    if try_eligible:
        batches = await create_payout_batch(db, "TRY", try_eligible, triggered_by)
        for batch in batches:
            try:
                await process_payout_batch(db, batch["id"])
                results["try_batches"].append(batch["id"])
            except Exception as e:
                logger.error("TRY batch %s failed: %s", batch["id"], e)

    logger.info(
        "Auto payout complete: GBP=%d TRY=%d skipped=%d",
        len(results["gbp_batches"]), len(results["try_batches"]), len(results["skipped"]),
    )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_list(lst: list, max_size: int) -> List[list]:
    """Split a list into chunks of max_size."""
    return [lst[i:i + max_size] for i in range(0, len(lst), max_size)]
