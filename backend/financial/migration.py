"""
PLANN Financial Engine — Migration Script

Migrates existing data to support the dual-market financial architecture.
- Adds base_currency: "TRY" to all existing merchants
- Creates merchant_wallets for existing organizations
- Adds payment fields to existing services
- Creates MongoDB indexes for all financial collections
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from .schemas import FINANCIAL_INDEXES, MerchantWallet, MerchantPayoutSettings

logger = logging.getLogger(__name__)


async def run_migration(db) -> Dict[str, Any]:
    """
    Run all financial migrations. Safe to run multiple times (idempotent).
    Returns a summary of changes made.
    """
    results = {
        "settings_updated": 0,
        "wallets_created": 0,
        "services_updated": 0,
        "indexes_created": 0,
        "errors": [],
    }

    # Step 1: Add financial fields to existing settings
    try:
        r = await _migrate_settings(db)
        results["settings_updated"] = r
    except Exception as e:
        logger.exception("Settings migration failed")
        results["errors"].append(f"settings: {e}")

    # Step 2: Create wallets for existing organizations
    try:
        r = await _migrate_wallets(db)
        results["wallets_created"] = r
    except Exception as e:
        logger.exception("Wallet migration failed")
        results["errors"].append(f"wallets: {e}")

    # Step 3: Add payment fields to existing services
    try:
        r = await _migrate_services(db)
        results["services_updated"] = r
    except Exception as e:
        logger.exception("Service migration failed")
        results["errors"].append(f"services: {e}")

    # Step 4: Create indexes
    try:
        r = await _create_indexes(db)
        results["indexes_created"] = r
    except Exception as e:
        logger.exception("Index creation failed")
        results["errors"].append(f"indexes: {e}")

    logger.info("Migration complete: %s", results)
    return results


async def _migrate_settings(db) -> int:
    """Add base_currency and financial fields to existing settings."""
    defaults = MerchantPayoutSettings().model_dump()
    # Only set fields that don't exist yet
    count = 0
    cursor = db.settings.find({"base_currency": {"$exists": False}})
    async for doc in cursor:
        update_fields = {}
        for key, value in defaults.items():
            if key not in doc:
                update_fields[key] = value

        if update_fields:
            # Default all existing merchants to TRY
            update_fields["base_currency"] = "TRY"
            await db.settings.update_one(
                {"_id": doc["_id"]},
                {"$set": update_fields},
            )
            count += 1

    logger.info("Settings migrated: %d documents", count)
    return count


async def _migrate_wallets(db) -> int:
    """Create merchant_wallets for organizations that don't have one."""
    count = 0
    cursor = db.settings.find({})
    async for settings in cursor:
        org_id = settings.get("organization_id")
        if not org_id:
            continue

        existing = await db.merchant_wallets.find_one({"organization_id": org_id})
        if existing:
            continue

        base_currency = settings.get("base_currency", "TRY")
        wallet = MerchantWallet(
            organization_id=org_id,
            base_currency=base_currency,
        ).model_dump()

        await db.merchant_wallets.insert_one(wallet)
        count += 1

    logger.info("Wallets created: %d", count)
    return count


async def _migrate_services(db) -> int:
    """Add payment_rule field to existing services."""
    result = await db.services.update_many(
        {"payment_rule": {"$exists": False}},
        {"$set": {
            "payment_rule": "on_site",
            "deposit_type": None,
            "deposit_value": None,
            "price_minor": 0,  # Will need manual update by merchants
        }},
    )
    count = result.modified_count
    logger.info("Services migrated: %d documents", count)
    return count


async def _create_indexes(db) -> int:
    """Create all financial collection indexes."""
    count = 0
    for collection_name, indexes in FINANCIAL_INDEXES.items():
        collection = db[collection_name]
        for index_def in indexes:
            try:
                kwargs = {}
                if index_def.get("unique"):
                    kwargs["unique"] = True
                if index_def.get("sparse"):
                    kwargs["sparse"] = True

                await collection.create_index(index_def["keys"], **kwargs)
                count += 1
            except Exception as e:
                logger.warning(
                    "Index creation failed for %s: %s (may already exist)",
                    collection_name, e,
                )

    logger.info("Indexes created: %d", count)
    return count
