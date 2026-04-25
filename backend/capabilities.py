"""
Capability-based access (plan: session.plan, appointment.cancel, appointment.refund, audit.write).
Server her kritik handler'da tekrar kontrol eder; UI yalnızca yansıtma.
"""
from __future__ import annotations

# Sabit yetenek kimlikleri
CAP_SESSION_PLAN = "session.plan"
CAP_APPOINTMENT_CANCEL = "appointment.cancel"
CAP_APPOINTMENT_REFUND = "appointment.refund"
CAP_AUDIT_WRITE = "audit.write"


def user_has_capability(
    role: str,
    capability: str,
    *,
    can_view_all_appointments: bool = False,
) -> bool:
    """Rol + opsiyonel staff geniş görünüm — yetenek eşlemesi."""
    if role == "marketing":
        return False
    if role == "superadmin":
        return capability in (
            CAP_SESSION_PLAN,
            CAP_APPOINTMENT_CANCEL,
            CAP_APPOINTMENT_REFUND,
            CAP_AUDIT_WRITE,
        )
    if role == "admin":
        return capability in (
            CAP_SESSION_PLAN,
            CAP_APPOINTMENT_CANCEL,
            CAP_APPOINTMENT_REFUND,
            CAP_AUDIT_WRITE,
        )
    if role == "staff":
        if capability == CAP_APPOINTMENT_REFUND:
            return False
        if capability == CAP_AUDIT_WRITE:
            return bool(can_view_all_appointments)
        return capability in (CAP_SESSION_PLAN, CAP_APPOINTMENT_CANCEL)
    return False


def assert_capability_for_user(
    user,
    capability: str,
    *,
    request_id: str,
) -> None:
    """UserInDB — yoksa HTTPException permission_denied."""
    from fastapi import HTTPException

    ok = user_has_capability(
        getattr(user, "role", "") or "",
        capability,
        can_view_all_appointments=bool(
            getattr(user, "can_view_all_appointments", False)
        ),
    )
    if not ok:
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error_code": "permission_denied",
                "message": "Bu işlem için yetkiniz yok",
                "request_id": request_id,
            },
        )
