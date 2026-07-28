"""
20260724_payment_type_fields — Business/Subscription ayrımı + Wise conversion idempotency.

- merchant_transactions backfill: payment_type="business", business_id=organization_id,
  converted=false (eksik olan kayıtlara). Mevcut kayıtlar geri-uyumlu etiketlenir.
- Yeni index'ler: payment_type, business_id, stripe_payout_id (sparse),
  stripe_balance_transaction_id (sparse), converted + bileşik.
- stripe_payout_reconciliations: stripe_payout_id unique (payout başına idempotent özet).
- conversions: idempotency_key unique, merchant_transaction_id unique,
  stripe_balance_transaction_id unique+sparse → çift conversion imkansız.
"""

REVERSIBLE = True
DESCRIPTION = "Payment type separation (business/subscription) + conversion idempotency indexes"


async def up(db):
    # 1) merchant_transactions backfill (geri-uyumlu etiketleme)
    await db.merchant_transactions.update_many(
        {"payment_type": {"$exists": False}},
        {"$set": {"payment_type": "business"}},
    )
    await db.merchant_transactions.update_many(
        {"converted": {"$exists": False}},
        {"$set": {"converted": False}},
    )
    # business_id = organization_id (yalnızca eksik olanlara, org_id mevcutsa)
    async for tx in db.merchant_transactions.find(
        {"business_id": {"$exists": False}, "organization_id": {"$exists": True}},
        {"_id": 1, "organization_id": 1},
    ):
        await db.merchant_transactions.update_one(
            {"_id": tx["_id"]},
            {"$set": {"business_id": tx.get("organization_id")}},
        )

    # 2) merchant_transactions yeni index'ler
    await db.merchant_transactions.create_index([("payment_type", 1)])
    await db.merchant_transactions.create_index([("business_id", 1)])
    await db.merchant_transactions.create_index([("stripe_payout_id", 1)], sparse=True)
    await db.merchant_transactions.create_index(
        [("stripe_balance_transaction_id", 1)], sparse=True
    )
    await db.merchant_transactions.create_index([("converted", 1)])
    await db.merchant_transactions.create_index(
        [("payment_type", 1), ("converted", 1), ("state", 1)]
    )

    # 3) stripe_payout_reconciliations — payout başına tek özet (idempotent)
    await db.stripe_payout_reconciliations.create_index(
        [("stripe_payout_id", 1)], unique=True
    )
    await db.stripe_payout_reconciliations.create_index([("created_at", -1)])

    # 4) conversions — üç katmanlı idempotency'nin unique constraint katmanı
    await db.conversions.create_index([("idempotency_key", 1)], unique=True)
    await db.conversions.create_index([("merchant_transaction_id", 1)], unique=True)
    await db.conversions.create_index(
        [("stripe_balance_transaction_id", 1)], unique=True, sparse=True
    )
    await db.conversions.create_index([("stripe_payout_id", 1)], sparse=True)
    await db.conversions.create_index([("status", 1)])


async def down(db):
    for coll_name, index_names in [
        ("merchant_transactions", [
            "payment_type_1", "business_id_1", "stripe_payout_id_1",
            "stripe_balance_transaction_id_1", "converted_1",
            "payment_type_1_converted_1_state_1",
        ]),
        ("stripe_payout_reconciliations", [
            "stripe_payout_id_1", "created_at_-1",
        ]),
        ("conversions", [
            "idempotency_key_1", "merchant_transaction_id_1",
            "stripe_balance_transaction_id_1", "stripe_payout_id_1", "status_1",
        ]),
    ]:
        coll = db[coll_name]
        for name in index_names:
            try:
                await coll.drop_index(name)
            except Exception:
                pass
    # Backfill alanları geri alınmaz (veri kaybı riski yok, geri-uyumlu).
