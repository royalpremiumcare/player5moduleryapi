"""
20260421_bootstrap_indexes — Create indexes for new collections introduced in PLANN v2.

Collections:
  - feature_flags
  - dead_letter_queue
  - refund_requests
  - migration_log (already by runner)
"""

REVERSIBLE = True
DESCRIPTION = "Bootstrap indexes for feature_flags, dead_letter_queue, refund_requests"


async def up(db):
    # feature_flags
    await db.feature_flags.create_index("name", unique=True)

    # dead_letter_queue
    await db.dead_letter_queue.create_index([("status", 1), ("next_retry_at", 1)])
    await db.dead_letter_queue.create_index("failure_type")
    await db.dead_letter_queue.create_index("organization_id")
    await db.dead_letter_queue.create_index([("source_entity_type", 1), ("source_entity_id", 1)])
    await db.dead_letter_queue.create_index("idempotency_key", unique=True, sparse=True)
    await db.dead_letter_queue.create_index([("created_at", -1)])

    # refund_requests
    await db.refund_requests.create_index([("organization_id", 1), ("status", 1)])
    await db.refund_requests.create_index([("status", 1), ("sla_deadline", 1)])
    await db.refund_requests.create_index("merchant_transaction_id")
    await db.refund_requests.create_index("idempotency_key", unique=True, sparse=True)
    await db.refund_requests.create_index([("created_at", -1)])

    # webhook_events — extended fields for replay guard
    # (event_id unique already exists; add payload_hash index for forensic lookup)
    try:
        await db.webhook_events.create_index("payload_hash", sparse=True)
    except Exception:
        pass


async def down(db):
    # Drop indexes we created. Safe if they don't exist.
    for coll_name, index_names in [
        ("feature_flags", ["name_1"]),
        ("dead_letter_queue", [
            "status_1_next_retry_at_1", "failure_type_1", "organization_id_1",
            "source_entity_type_1_source_entity_id_1", "idempotency_key_1",
            "created_at_-1",
        ]),
        ("refund_requests", [
            "organization_id_1_status_1", "status_1_sla_deadline_1",
            "merchant_transaction_id_1", "idempotency_key_1", "created_at_-1",
        ]),
        ("webhook_events", ["payload_hash_1"]),
    ]:
        coll = db[coll_name]
        for name in index_names:
            try:
                await coll.drop_index(name)
            except Exception:
                pass
