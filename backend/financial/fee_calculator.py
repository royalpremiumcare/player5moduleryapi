"""
PLANN Financial Engine — Fee Calculator

Two modes:
  - seller_pays: Commission deducted from merchant's earnings
  - buyer_pays: Commission added on top, merchant gets full amount
"""

from dataclasses import dataclass
from typing import Optional
import logging

from .money import get_tier_config, apply_bps

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeeResult:
    gross_minor: int
    net_minor: int
    fee_minor: int
    fee_rate_bps: int
    stripe_currency: str
    base_currency: str
    deposit_applied: bool
    deposit_minor: int
    full_service_price_minor: int


@dataclass(frozen=True)
class DepositRule:
    payment_rule: str
    deposit_type: Optional[str] = None
    deposit_value: Optional[int] = None


def calculate_fee(
    base_currency: str,
    service_price_minor: int,
    fee_preference: str,
    tier: str,
    deposit_rule: Optional[DepositRule] = None,
    session_count: int = 1,
) -> FeeResult:
    if service_price_minor <= 0:
        raise ValueError(f"Service price must be positive, got {service_price_minor}")
    if fee_preference not in ("seller_pays", "buyer_pays"):
        raise ValueError(f"Invalid fee_preference: {fee_preference}")

    tier_cfg = get_tier_config(base_currency, tier)
    fee_rate_bps = tier_cfg.fee_rate_bps
    stripe_currency = base_currency.lower()

    total_price = service_price_minor

    online_amount = _resolve_online_amount(total_price, deposit_rule)
    deposit_applied = deposit_rule is not None and deposit_rule.payment_rule == "deposit"
    deposit_minor = online_amount if deposit_applied else 0

    if online_amount == 0:
        return FeeResult(
            gross_minor=0, net_minor=0, fee_minor=0,
            fee_rate_bps=fee_rate_bps, stripe_currency=stripe_currency,
            base_currency=base_currency, deposit_applied=False,
            deposit_minor=0, full_service_price_minor=total_price,
        )

    percentage_fee = apply_bps(online_amount, fee_rate_bps)
    fixed_fee = tier_cfg.fixed_fee_minor  # 0 for GBP, 1000 kuruş (₺10) for TRY
    fee_minor = percentage_fee + fixed_fee

    if fee_preference == "seller_pays":
        gross_minor = online_amount
        net_minor = online_amount - fee_minor
    else:
        gross_minor = online_amount + fee_minor
        net_minor = online_amount

    return FeeResult(
        gross_minor=gross_minor,
        net_minor=net_minor,
        fee_minor=fee_minor,
        fee_rate_bps=fee_rate_bps,
        stripe_currency=stripe_currency,
        base_currency=base_currency,
        deposit_applied=deposit_applied,
        deposit_minor=deposit_minor if deposit_applied else 0,
        full_service_price_minor=total_price,
    )


def _resolve_online_amount(
    total_price_minor: int,
    deposit_rule: Optional[DepositRule],
) -> int:
    if deposit_rule is None or deposit_rule.payment_rule == "on_site":
        return 0

    if deposit_rule.payment_rule == "full_online":
        return total_price_minor

    if deposit_rule.payment_rule == "deposit":
        if deposit_rule.deposit_type == "fixed":
            val = deposit_rule.deposit_value or 0
            return min(val, total_price_minor)
        elif deposit_rule.deposit_type == "percentage":
            bps = deposit_rule.deposit_value or 0
            return apply_bps(total_price_minor, bps)

    return 0


def calculate_fee_preview(
    base_currency: str,
    service_price_minor: int,
    tier: str,
    session_count: int = 1,
    deposit_rule: Optional[DepositRule] = None,
) -> dict:
    """Return both seller_pays and buyer_pays results for UI preview."""
    seller = calculate_fee(base_currency, service_price_minor, "seller_pays", tier, deposit_rule, session_count)
    buyer = calculate_fee(base_currency, service_price_minor, "buyer_pays", tier, deposit_rule, session_count)
    return {
        "seller_pays": {
            "customer_pays": seller.gross_minor,
            "merchant_receives": seller.net_minor,
            "platform_fee": seller.fee_minor,
        },
        "buyer_pays": {
            "customer_pays": buyer.gross_minor,
            "merchant_receives": buyer.net_minor,
            "platform_fee": buyer.fee_minor,
        },
        "fee_rate_bps": seller.fee_rate_bps,
        "base_currency": base_currency,
        "full_service_price_minor": buyer.full_service_price_minor,
        "deposit_applied": buyer.deposit_applied,
        "deposit_minor": buyer.deposit_minor,
    }
