"""GET /appointments refund_eligible — saf yardımcı testleri."""

from appointment_refund_flags import (
    attach_refund_eligible,
    session_group_ids_from_merchant_transactions,
)


def test_session_group_ids_from_merchant_transactions():
    tx = [
        {"session_group_id": "a"},
        {"session_group_id": "b"},
        {"session_group_id": None},
    ]
    assert session_group_ids_from_merchant_transactions(tx) == {"a", "b"}


def test_attach_refund_eligible():
    appts = [
        {"id": "1", "session_group_id": "g1"},
        {"id": "2", "session_group_id": None},
        {"id": "3", "session_group_id": "g2"},
    ]
    attach_refund_eligible(appts, {"g1"})
    assert appts[0]["refund_eligible"] is True
    assert appts[1]["refund_eligible"] is False
    assert appts[2]["refund_eligible"] is False
