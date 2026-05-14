"""
Aha activation helpers — slot picker + WA retry wrapper unit tests.

Endpoint'in tamamı server.py içinde DB'ye bağlı; integration test'i V2'ye.
Burada plan'ın sözleştirdiği iki saf yardımcı (`pick_aha_slot`, 
`send_aha_whatsapp_with_retry`) test edilir.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

import pytest

from aha_helpers import (
    AHA_OFFSET_MINUTES,
    pick_aha_slot,
    send_aha_whatsapp_with_retry,
)


# ===========================================================================
# pick_aha_slot
# ===========================================================================


def _now(year=2026, month=5, day=4, hour=10, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_pick_slot_within_business_hours():
    """Mesai saatinde +15dk: aynı gün, candidate hour."""
    settings = {"work_start_hour": 9, "work_end_hour": 18}
    date_s, time_s = pick_aha_slot(settings, now_provider=lambda: _now(hour=10, minute=0))
    assert date_s == "2026-05-04"
    assert time_s == "10:15"


def test_pick_slot_before_business_pushed_forward_to_work_start():
    """Mesai başlamadan önce: o günün work_start:00'ına atılır."""
    settings = {"work_start_hour": 9, "work_end_hour": 18}
    date_s, time_s = pick_aha_slot(settings, now_provider=lambda: _now(hour=7, minute=30))
    # 07:30 + 15dk = 07:45 → < 09:00 → 09:00
    assert date_s == "2026-05-04"
    assert time_s == "09:00"


def test_pick_slot_after_business_rolls_to_next_day():
    """Mesai bitiminden sonra: ertesi günün work_start:00'ına."""
    settings = {"work_start_hour": 9, "work_end_hour": 18}
    date_s, time_s = pick_aha_slot(settings, now_provider=lambda: _now(hour=18, minute=10))
    # 18:10 + 15dk = 18:25 → ≥ 18 → next day 09:00
    assert date_s == "2026-05-05"
    assert time_s == "09:00"


def test_pick_slot_at_business_end_boundary_rolls_next_day():
    """Mesai bitiş saatinde (>=) bile ertesi güne kaydır."""
    settings = {"work_start_hour": 9, "work_end_hour": 18}
    date_s, time_s = pick_aha_slot(settings, now_provider=lambda: _now(hour=17, minute=50))
    # 17:50 + 15dk = 18:05 → ≥ 18 → next day
    assert date_s == "2026-05-05"
    assert time_s == "09:00"


def test_pick_slot_default_hours_when_settings_missing():
    """settings dict boşsa default 9-18 kullanılır."""
    date_s, time_s = pick_aha_slot({}, now_provider=lambda: _now(hour=10, minute=0))
    assert date_s == "2026-05-04"
    assert time_s == "10:15"


def test_pick_slot_handles_none_settings():
    """settings_doc None olabilir."""
    date_s, time_s = pick_aha_slot(None, now_provider=lambda: _now(hour=10, minute=0))
    assert date_s == "2026-05-04"
    assert time_s == "10:15"


def test_pick_slot_normalizes_inverted_hours():
    """work_end <= work_start → otomatik 8 saat normalize."""
    settings = {"work_start_hour": 9, "work_end_hour": 9}  # geçersiz
    date_s, time_s = pick_aha_slot(settings, now_provider=lambda: _now(hour=10, minute=0))
    # 9 + 8 = 17 → 10:15 < 17, aynı gün
    assert date_s == "2026-05-04"
    assert time_s == "10:15"


def test_pick_slot_offset_constant_is_fifteen_minutes():
    """Plan kontratı: AHA_OFFSET_MINUTES = 15."""
    assert AHA_OFFSET_MINUTES == 15


# ===========================================================================
# send_aha_whatsapp_with_retry
# ===========================================================================


def _make_send_callable(results: List):
    """Fake `send_whatsapp_template`: results listesinden sırayla pop eder.
    Element callable ise çağrılır (timeout simüle etmek için).
    """
    iterator = iter(results)

    def _send(*args, **kwargs):
        nxt = next(iterator)
        if callable(nxt):
            return nxt()
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    return _send


@pytest.mark.asyncio
async def test_first_attempt_success_returns_message_id():
    send = _make_send_callable(["wamid.first_msg_001"])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+905551112233",
        customer_name="Owner",
        company_name="Salon",
        appointment_date="2026-05-04",
        appointment_time="10:15",
        service_name="Demo",
        support_phone="+905551112233",
        retry_delay_s=0.01,  # test hızlandırma
    )
    assert ok is True
    assert msg_id == "wamid.first_msg_001"
    assert err is None


@pytest.mark.asyncio
async def test_first_fail_then_retry_success():
    """1. fail → 1.5s bekle (test'te 0.01) → 2. success."""
    send = _make_send_callable([RuntimeError("network glitch"), "wamid.retry_ok"])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        retry_delay_s=0.01,
    )
    assert ok is True
    assert msg_id == "wamid.retry_ok"
    assert err is None


@pytest.mark.asyncio
async def test_both_attempts_fail_returns_combined_error():
    send = _make_send_callable([
        RuntimeError("first 5xx"),
        RuntimeError("second timeout"),
    ])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        retry_delay_s=0.01,
    )
    assert ok is False
    assert msg_id is None
    assert err and "first=" in err and "second=" in err
    assert "RuntimeError" in err


@pytest.mark.asyncio
async def test_empty_string_response_treated_as_failure():
    """Send fonksiyonu boş string dönerse fail kabul edilir."""
    send = _make_send_callable(["", ""])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        retry_delay_s=0.01,
    )
    assert ok is False
    assert msg_id is None
    assert "empty_response" in err


@pytest.mark.asyncio
async def test_disabled_response_treated_as_success_for_test_envs():
    """WHATSAPP_ENABLED=False iken send_whatsapp_template "disabled" döner.
    Aha akışının dev/test ortamında tıkanmaması için bu success sayılır.
    """
    send = _make_send_callable(["disabled"])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        retry_delay_s=0.01,
    )
    assert ok is True
    assert msg_id == "disabled"


@pytest.mark.asyncio
async def test_first_attempt_timeout_triggers_retry():
    """1. çağrı 2s'de yanıt vermezse asyncio.wait_for bizi bırakır.

    Test'i hızlandırmak için first_timeout_s=0.05 ile çalıştırırız ve
    fake send_callable 0.5s blocking sleep yapar.
    """
    import time

    def _slow_then_ok():
        time.sleep(0.5)  # blocking; run_in_executor thread'i tutar
        return "wamid.late"

    send = _make_send_callable([_slow_then_ok, "wamid.fast"])
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        first_timeout_s=0.05,
        retry_delay_s=0.01,
        second_timeout_s=2.0,
    )
    assert ok is True
    assert msg_id == "wamid.fast"
    assert err is None


@pytest.mark.asyncio
async def test_total_latency_within_worst_case_budget():
    """
    Plan kontratı: worst-case ~5.5s (2 + 1.5 + 2). Test'te küçük budget'lerle
    aynı oranı doğrularız: 0.05 + 0.05 + 0.05 = 0.15s, üstüne küçük overhead.
    """
    import time as _t

    def _slow_blocking():
        _t.sleep(1.0)  # block worker thread; wait_for keser
        return "ok"

    send = _make_send_callable([_slow_blocking, _slow_blocking])
    start = asyncio.get_event_loop().time()
    ok, msg_id, err = await send_aha_whatsapp_with_retry(
        send_callable=send,
        to_number="+90",
        customer_name="x",
        company_name="y",
        appointment_date="d",
        appointment_time="t",
        service_name="s",
        support_phone="+90",
        first_timeout_s=0.05,
        retry_delay_s=0.05,
        second_timeout_s=0.05,
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert ok is False
    assert "timeout" in err
    # 0.05 + 0.05 + 0.05 = 0.15s; 0.5s overhead toleransı
    assert elapsed < 0.65, f"send_aha_whatsapp_with_retry exceeded budget: {elapsed:.2f}s"
