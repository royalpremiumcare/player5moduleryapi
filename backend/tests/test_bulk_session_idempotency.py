"""Unit tests for bulk session idempotency canonical hash (no server import)."""
import pytest

from bulk_session_idempotency import BulkSessionCreate, SessionSlot, canonical_bulk_session_hash


def _make(**kwargs) -> BulkSessionCreate:
    base = dict(
        customer_name="Ali",
        phone="905551234567",
        service_id="svc1",
        sessions=[
            SessionSlot(date="2025-06-01", time="10:00"),
            SessionSlot(date="2025-06-08", time="10:00"),
        ],
    )
    base.update(kwargs)
    return BulkSessionCreate(**base)


def test_hash_stable_across_session_order():
    a = _make(
        sessions=[
            SessionSlot(date="2025-06-08", time="10:00"),
            SessionSlot(date="2025-06-01", time="10:00"),
        ]
    )
    b = _make(
        sessions=[
            SessionSlot(date="2025-06-01", time="10:00"),
            SessionSlot(date="2025-06-08", time="10:00"),
        ]
    )
    assert canonical_bulk_session_hash(a) == canonical_bulk_session_hash(b)


def test_whitespace_trim_affects_canonical():
    a = _make(customer_name="  Ali  ", phone=" 90555 ")
    b = _make(customer_name="Ali", phone="90555")
    assert canonical_bulk_session_hash(a) == canonical_bulk_session_hash(b)


def test_different_payload_different_hash():
    a = _make()
    b = _make(customer_name="Veli")
    assert canonical_bulk_session_hash(a) != canonical_bulk_session_hash(b)


def test_optional_none_equivalence():
    a = _make(staff_member_id=None, session_group_id=None)
    b = _make()
    b2 = b.model_copy(update={"staff_member_id": None, "session_group_id": None})
    assert canonical_bulk_session_hash(a) == canonical_bulk_session_hash(b2)


def test_session_slot_strings_stripped():
    a = _make(
        sessions=[
            SessionSlot(date=" 2025-06-01 ", time=" 10:00 "),
            SessionSlot(date="2025-06-08", time="10:00"),
        ]
    )
    b = _make()
    assert canonical_bulk_session_hash(a) == canonical_bulk_session_hash(b)


def test_per_slot_staff_changes_hash():
    a = _make(
        sessions=[
            SessionSlot(date="2025-06-01", time="10:00", staff_member_id="alice"),
            SessionSlot(date="2025-06-08", time="10:00"),
        ]
    )
    b = _make(
        sessions=[
            SessionSlot(date="2025-06-01", time="10:00", staff_member_id="bob"),
            SessionSlot(date="2025-06-08", time="10:00"),
        ]
    )
    assert canonical_bulk_session_hash(a) != canonical_bulk_session_hash(b)
