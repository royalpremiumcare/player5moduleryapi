"""
bulk-session: idempotency replay/mismatch, concurrency (Redis lock).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest


@pytest.mark.asyncio
async def test_idempotency_replay_same_request_id(integration_client, bulk_session_body):
    client, redis, db = integration_client
    idem = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem}

    r1 = await client.post("/api/appointments/bulk-session", json=bulk_session_body, headers=headers)
    assert r1.status_code == 201, r1.text
    j1 = r1.json()
    rid1 = j1["request_id"]
    ids1 = j1["created_appointment_ids"]

    r2 = await client.post("/api/appointments/bulk-session", json=bulk_session_body, headers=headers)
    assert r2.status_code == 201, r2.text
    j2 = r2.json()
    assert j2["request_id"] == rid1
    assert j2["created_appointment_ids"] == ids1
    assert j2["session_group_id"] == j1["session_group_id"]
    # Tek insert — replay DB yazmaz
    assert len(db.appointments.docs) == 1


@pytest.mark.asyncio
async def test_idempotency_key_mismatch_different_payload(integration_client, bulk_session_body):
    client, redis, db = integration_client
    idem = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem}

    body_a = dict(bulk_session_body)
    body_b = dict(bulk_session_body)
    body_b["sessions"] = [{"date": "2026-09-02", "time": "11:00"}]

    r1 = await client.post("/api/appointments/bulk-session", json=body_a, headers=headers)
    assert r1.status_code == 201

    r2 = await client.post("/api/appointments/bulk-session", json=body_b, headers=headers)
    assert r2.status_code == 422
    d = r2.json()["detail"]
    assert isinstance(d, dict)
    assert d.get("error_code") == "idempotency_key_mismatch"


@pytest.mark.asyncio
async def test_concurrency_parallel_lock_same_slot_same_staff(integration_client, bulk_session_body):
    """İki farklı Idempotency-Key ve grup; aynı staff+slot → biri 201, diğeri 409 (kilit veya DB çakışması)."""
    client, redis, db = integration_client
    base = dict(bulk_session_body)
    base["staff_member_id"] = "staff_lock"
    base["sessions"] = [{"date": "2026-10-15", "time": "14:00"}]

    async def one_request():
        # Aynı session_group_id iki istekte olursa biri diğerini "yeniden planlama" ile iptal eder;
        # çakışma kontrolü iptal randevuları saymadığı için ikisi de 201 döner. Grupları ayır.
        b = dict(base)
        b["session_group_id"] = str(uuid.uuid4())
        return await client.post(
            "/api/appointments/bulk-session",
            json=b,
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

    results = await asyncio.gather(one_request(), one_request())
    codes = sorted([r.status_code for r in results])
    assert codes == [201, 409]
    ok = [r for r in results if r.status_code == 201][0].json()
    fail = [r for r in results if r.status_code == 409][0].json()
    assert "detail" in fail
    det = fail["detail"]
    if isinstance(det, dict):
        assert det.get("error_code") == "slot_conflict"


@pytest.mark.asyncio
async def test_idempotency_in_progress_parallel_same_key(integration_client, bulk_session_body, monkeypatch):
    """Aynı Idempotency-Key ile ikinci istek, ilki kota kontrolünde beklerken 409 idempotency_in_progress."""
    import server

    barrier = asyncio.Event()
    started = asyncio.Event()

    async def slow_quota(db, org_id):
        started.set()
        await barrier.wait()
        return True, ""

    monkeypatch.setattr(server, "check_quota_and_increment", slow_quota)

    client, redis, db = integration_client
    idem = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem}
    body = dict(bulk_session_body)
    body["session_group_id"] = str(uuid.uuid4())

    loop = asyncio.get_running_loop()
    # conftest asyncio.create_task'ı kapatıyor; loop.create_task patch'lenmez.
    t1 = loop.create_task(
        client.post("/api/appointments/bulk-session", json=body, headers=headers)
    )
    await asyncio.wait_for(started.wait(), timeout=3.0)
    r2 = await client.post("/api/appointments/bulk-session", json=body, headers=headers)
    assert r2.status_code == 409, r2.text
    d2 = r2.json()["detail"]
    assert isinstance(d2, dict)
    assert d2.get("error_code") == "idempotency_in_progress"
    barrier.set()
    r1 = await asyncio.wait_for(t1, timeout=10.0)
    assert r1.status_code == 201, r1.text
