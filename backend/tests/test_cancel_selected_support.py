"""Unit tests for cancel-selected staff access helper."""
from cancel_selected_support import staff_cannot_access_appointments


def test_staff_own_appointments_allowed():
    appts = [
        {"id": "1", "staff_member_id": "alice"},
        {"id": "2", "staff_member_id": "alice"},
    ]
    assert staff_cannot_access_appointments(appts, "alice") is False


def test_staff_foreign_appointment_blocked():
    appts = [
        {"id": "1", "staff_member_id": "alice"},
        {"id": "2", "staff_member_id": "bob"},
    ]
    assert staff_cannot_access_appointments(appts, "alice") is True


def test_empty_list_allowed():
    assert staff_cannot_access_appointments([], "alice") is False


def test_missing_staff_field_treated_as_foreign():
    appts = [{"id": "1", "staff_member_id": "alice"}, {"id": "2"}]
    assert staff_cannot_access_appointments(appts, "alice") is True
