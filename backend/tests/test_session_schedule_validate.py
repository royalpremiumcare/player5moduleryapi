"""Client-side schedule validation mirror (documents expected slot shape)."""
from bulk_session_idempotency import BulkSessionCreate, SessionSlot


def test_bulk_model_accepts_slots():
    b = BulkSessionCreate(
        customer_name="A",
        phone="1",
        service_id="s",
        sessions=[SessionSlot(date="2025-06-01", time="10:00")],
    )
    assert len(b.sessions) == 1
