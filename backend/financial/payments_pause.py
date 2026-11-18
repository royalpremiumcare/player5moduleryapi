"""Merchant payments pause switch (2026-11-18).

PLANN may not collect and hold money on behalf of businesses, and the payout account is closed.
Until a compliant solution is live, no new online payment (checkout, payment link) may start and
services can only be pay-at-salon. Paused unless MERCHANT_PAYMENTS_PAUSED is explicitly false.
"""

import os
from typing import Optional, Tuple

from fastapi import HTTPException

PAUSED_DETAIL = "Online ödeme geçici olarak kapalı. Ödemeyi salonda alabilirsiniz."
_FALSE = {"false", "0", "no", "off"}
_ONLINE_RULES = {"online", "deposit", "full_online"}


def payments_paused() -> bool:
    return (os.environ.get("MERCHANT_PAYMENTS_PAUSED") or "true").strip().lower() not in _FALSE


def coerce_payment_rule(
    rule: Optional[str], deposit: Optional[float], *, paused: bool
) -> Tuple[Optional[str], Optional[float]]:
    """While paused an online / deposit rule becomes pay-at-salon (old app builds still send them)."""
    if paused and rule in _ONLINE_RULES:
        return "on_site", None
    return rule, deposit


def effective_payment_rule(rule: Optional[str], *, paused: Optional[bool] = None) -> Optional[str]:
    """How a stored rule behaves now: while paused every online / deposit service is pay-at-salon."""
    if paused is None:
        paused = payments_paused()
    return "on_site" if paused and rule in _ONLINE_RULES else rule


def ensure_payments_open() -> None:
    if payments_paused():
        raise HTTPException(status_code=403, detail=PAUSED_DETAIL)
