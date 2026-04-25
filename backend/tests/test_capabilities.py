"""Capability mapping (plan: RBAC via session.plan, appointment.cancel, appointment.refund)."""
import pytest

from capabilities import (
    CAP_APPOINTMENT_CANCEL,
    CAP_APPOINTMENT_REFUND,
    CAP_SESSION_PLAN,
    user_has_capability,
)


def test_admin_has_all_core_caps():
    for cap in (CAP_SESSION_PLAN, CAP_APPOINTMENT_CANCEL, CAP_APPOINTMENT_REFUND):
        assert user_has_capability("admin", cap) is True


def test_staff_can_plan_and_cancel_not_refund():
    assert user_has_capability("staff", CAP_SESSION_PLAN) is True
    assert user_has_capability("staff", CAP_APPOINTMENT_CANCEL) is True
    assert user_has_capability("staff", CAP_APPOINTMENT_REFUND) is False


def test_marketing_has_no_caps():
    assert user_has_capability("marketing", CAP_SESSION_PLAN) is False


def test_superadmin_has_refund():
    assert user_has_capability("superadmin", CAP_APPOINTMENT_REFUND) is True
