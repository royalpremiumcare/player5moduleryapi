from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from live_activity.phase import (
    TR_TZ,
    Phase,
    appointment_window,
    compute_phase,
    resolve_duration,
)

NOW_BASE = datetime(2026, 11, 16, 14, 0, tzinfo=TR_TZ)
apt = {"status": "Bekliyor", "appointment_date": "2026-11-16", "appointment_time": "14:30", "service_duration": 45}


def test_upcoming_before_start():
    assert compute_phase(apt, NOW_BASE, 45) is Phase.UPCOMING


def test_processing_at_start():
    assert compute_phase(apt, NOW_BASE.replace(minute=30), 45) is Phase.PROCESSING


def test_processing_one_sec_before_end():
    assert compute_phase(apt, datetime(2026, 11, 16, 15, 14, 59, tzinfo=TR_TZ), 45) is Phase.PROCESSING


def test_completed_at_end_while_still_bekliyor():
    assert compute_phase(apt, datetime(2026, 11, 16, 15, 15, tzinfo=TR_TZ), 45) is Phase.COMPLETED


def test_tamamlandi_is_completed_even_before_end():
    assert compute_phase({**apt, "status": "Tamamlandı"}, NOW_BASE, 45) is Phase.COMPLETED


@pytest.mark.parametrize("s", ["İptal", "İptal Edildi", "Cancelled"])
def test_cancelled_statuses(s):
    assert compute_phase({**apt, "status": s}, NOW_BASE, 45) is Phase.CANCELLED


def test_payment_pending_ineligible():
    assert compute_phase({**apt, "status": "Ödeme Bekleniyor"}, NOW_BASE, 45) is Phase.INELIGIBLE


def test_missing_doc_removed():
    assert compute_phase(None, NOW_BASE, 45) is Phase.REMOVED


def test_duration_rule_order():
    assert resolve_duration({"service_duration": 50, "service_id": "s"}, {"s": 20}) == 50
    assert resolve_duration({"service_id": "s"}, {"s": 20}) == 20
    assert resolve_duration({}, {}) == 30


def test_window_crosses_midnight():
    s, e = appointment_window({**apt, "appointment_time": "23:40"}, 45)
    assert e == datetime(2026, 11, 17, 0, 25, tzinfo=TR_TZ)


def test_tz_parameter_respected():
    s, _ = appointment_window(apt, 45, tz=ZoneInfo("Europe/London"))
    assert s.utcoffset() == timedelta(0)
