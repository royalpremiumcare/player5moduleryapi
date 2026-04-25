"""
cancel-selected + refund: Stripe hata verince DB iptal güncellenmemeli.
"""
from __future__ import annotations

import pytest

import stripe

from .mocks import make_txn_refund_scenario


@pytest.mark.asyncio
async def test_cancel_selected_refund_stripe_fail_leaves_appointments_unchanged(
    integration_client, org_id, monkeypatch
):
    client, _redis, db = integration_client
    group_id = "grp_cancel_refund_int"
    txn, appts = make_txn_refund_scenario(org_id, group_id)
    db.appointments.docs = [dict(a) for a in appts]
    db.merchant_transactions.txn = dict(txn)

    def fake_refund_create(*args, **kwargs):
        raise stripe.error.StripeError("integration test: refund refused")

    monkeypatch.setattr(stripe.Refund, "create", fake_refund_create)

    resp = await client.post(
        "/api/appointments/cancel-selected",
        json={"appointment_ids": [a["id"] for a in appts], "refund": True},
    )
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    assert detail.get("refund_status") == "failed"
    assert all(d.get("status") == "Bekliyor" for d in db.appointments.docs)


@pytest.mark.asyncio
async def test_cancel_selected_stripe_ok_state_machine_fail_reconciliation_queue(
    integration_client, org_id, monkeypatch
):
    """Stripe iade başarılı; StateMachine patlayınca randevular iptal edilmez, kuyruk kaydı oluşur."""
    client, _redis, db = integration_client
    group_id = "grp_sm_fail_int"
    txn, appts = make_txn_refund_scenario(org_id, group_id)
    db.appointments.docs = [dict(a) for a in appts]
    db.merchant_transactions.txn = dict(txn)

    class FakeRefund:
        id = "re_test_sm_fail"

    def fake_refund_create(*args, **kwargs):
        return FakeRefund()

    monkeypatch.setattr(stripe.Refund, "create", fake_refund_create)

    async def fail_transition(self, *args, **kwargs):
        raise RuntimeError("integration: state machine failed")

    monkeypatch.setattr(
        "financial.state_machine.StateMachine.transition",
        fail_transition,
    )

    resp = await client.post(
        "/api/appointments/cancel-selected",
        json={"appointment_ids": [a["id"] for a in appts], "refund": True},
    )
    assert resp.status_code == 503, resp.text
    body = resp.json()
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    assert detail.get("error_code") == "stripe_refund_succeeded_db_failed"
    assert detail.get("refund_status") == "pending_reconciliation"
    assert detail.get("stripe_refund_id") == "re_test_sm_fail"
    assert all(d.get("status") == "Bekliyor" for d in db.appointments.docs)
    assert len(db.refund_reconciliation_pending.docs) == 1
    assert db.refund_reconciliation_pending.docs[0].get("failed_step") == "state_machine"
    assert db.refund_reconciliation_pending.docs[0].get("stripe_refund_id") == "re_test_sm_fail"
    assert db.refund_reconciliation_pending.docs[0].get("retry_count") == 0
    assert db.refund_reconciliation_pending.docs[0].get("next_retry_at") is None
    assert db.refund_reconciliation_pending.docs[0].get("locked_by") is None
