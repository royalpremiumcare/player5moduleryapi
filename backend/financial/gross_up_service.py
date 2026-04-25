"""
Gross-Up Service — dynamic commission with buyer_pays / seller_pays modes.

Embeds Stripe processor fee + Wise payout fee + Platform fee into customer price.
Fixed fees are added OUTSIDE the denominator (percentage-only in denominator).

Terminology (see terminology.py):
  - net_target: merchant wants this amount net (online portion)
  - customer_price: what the customer sees/pays on Stripe
  - merchant_net: what lands in the wallet after all deductions
  - platform_fee: PLANN's commission (tier)
  - processor_fee: Stripe's cut (ENV: STRIPE_FEE_{CC}_BPS / FIXED)
  - payout_fee: Wise cut (env or tier)

See plan Bölüm 2.1.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Optional

from .money import apply_bps, get_tier_config
from .fee_calculator import DepositRule, _resolve_online_amount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Processor fee (Stripe) — env-configurable
# ---------------------------------------------------------------------------

def _stripe_fee_params(base_currency: str) -> tuple[int, int]:
    """Return (bps, fixed_minor) for Stripe processor fee based on currency."""
    cc = base_currency.upper()
    if cc == "GBP":
        bps = int(os.getenv("STRIPE_FEE_UK_BPS", "150"))
        fixed = int(os.getenv("STRIPE_FEE_UK_FIXED", "25"))
    elif cc == "TRY":
        bps = int(os.getenv("STRIPE_FEE_TR_BPS", "250"))
        fixed = int(os.getenv("STRIPE_FEE_TR_FIXED", "150"))
    else:
        bps, fixed = 200, 0
    return bps, fixed


def _wise_fee_params(base_currency: str, tier: str) -> tuple[int, int]:
    """
    Return (bps, fixed_minor) for Wise payout fee.
    Sourced from env (aggregate) and/or tier.wise_cost_estimate_minor.
    """
    bps = int(os.getenv("WISE_PAYOUT_BPS", "0"))
    # tier config gives GBP pence estimate; convert to base_currency minor
    try:
        cfg = get_tier_config(base_currency, tier)
        fixed_gbp_pence = cfg.wise_cost_estimate_minor
    except Exception:
        fixed_gbp_pence = 0

    # Safe fallback: treat as base_currency minor (≈ for TRY ~1₺ per £0.01 is wrong,
    # so we prefer an env override when available)
    env_fixed = os.getenv("WISE_PAYOUT_FIXED_MINOR")
    if env_fixed is not None:
        try:
            return bps, int(env_fixed)
        except ValueError:
            pass
    return bps, fixed_gbp_pence


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GrossUpResult:
    # Core amounts (minor units in base_currency)
    customer_price_minor: int       # what customer pays on Stripe
    merchant_net_minor: int         # what ends up in wallet
    net_target_minor: int           # online portion before any fees (deposit or full)
    full_service_price_minor: int   # service price (for display)
    on_site_amount_minor: int       # cash/card at location

    # Fee breakdown
    platform_fee_minor: int
    stripe_fee_minor: int
    wise_fee_minor: int

    # Config used
    base_currency: str
    fee_preference: str
    fee_rate_bps: int               # platform (tier) bps
    deposit_applied: bool
    deposit_minor: int
    gross_up_applied: bool

    def to_dict(self) -> dict:
        return {
            "customer_price_minor": self.customer_price_minor,
            "merchant_net_minor": self.merchant_net_minor,
            "net_target_minor": self.net_target_minor,
            "full_service_price_minor": self.full_service_price_minor,
            "on_site_amount_minor": self.on_site_amount_minor,
            "platform_fee_minor": self.platform_fee_minor,
            "stripe_fee_minor": self.stripe_fee_minor,
            "wise_fee_minor": self.wise_fee_minor,
            "base_currency": self.base_currency,
            "fee_preference": self.fee_preference,
            "fee_rate_bps": self.fee_rate_bps,
            "deposit_applied": self.deposit_applied,
            "deposit_minor": self.deposit_minor,
            "gross_up_applied": self.gross_up_applied,
        }


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

class GrossUpError(ValueError):
    pass


def compute_customer_price(
    *,
    base_currency: str,
    service_price_minor: int,
    fee_preference: str,
    tier: str,
    deposit_rule: Optional[DepositRule] = None,
) -> GrossUpResult:
    """
    Main entry point — computes customer_price and merchant_net given
    service price, commission preference, and tier config.

    Fixed fees are added OUTSIDE the denominator to avoid price explosion.
    """
    if service_price_minor <= 0:
        raise GrossUpError(f"service_price must be positive, got {service_price_minor}")
    if fee_preference not in ("seller_pays", "buyer_pays"):
        raise GrossUpError(f"invalid fee_preference: {fee_preference}")

    tier_cfg = get_tier_config(base_currency, tier)
    tier_bps = tier_cfg.fee_rate_bps
    tier_fixed = tier_cfg.fixed_fee_minor

    stripe_bps, stripe_fixed = _stripe_fee_params(base_currency)
    wise_bps, wise_fixed = _wise_fee_params(base_currency, tier)

    # Resolve online (net_target) amount
    online_amount = _resolve_online_amount(service_price_minor, deposit_rule)
    deposit_applied = deposit_rule is not None and deposit_rule.payment_rule == "deposit"
    deposit_minor = online_amount if deposit_applied else 0
    on_site_amount = max(0, service_price_minor - online_amount)

    if online_amount == 0:
        # Fully on-site — no Stripe charge at all
        return GrossUpResult(
            customer_price_minor=0,
            merchant_net_minor=0,
            net_target_minor=0,
            full_service_price_minor=service_price_minor,
            on_site_amount_minor=on_site_amount,
            platform_fee_minor=0,
            stripe_fee_minor=0,
            wise_fee_minor=0,
            base_currency=base_currency,
            fee_preference=fee_preference,
            fee_rate_bps=tier_bps,
            deposit_applied=False,
            deposit_minor=0,
            gross_up_applied=False,
        )

    net_target = online_amount

    if fee_preference == "seller_pays":
        # Customer pays net_target; fees come out of merchant's share
        customer_price = net_target
        platform_fee = apply_bps(net_target, tier_bps) + tier_fixed
        stripe_fee = apply_bps(net_target, stripe_bps) + stripe_fixed
        wise_fee = apply_bps(net_target, wise_bps) + wise_fixed
        merchant_net = net_target - platform_fee - stripe_fee - wise_fee
        gross_up = False
    else:
        # buyer_pays: gross-up so merchant receives net_target
        # Percentage-only in denominator; fixed fees added outside.
        percentage_sum_bps = tier_bps + stripe_bps + wise_bps
        if percentage_sum_bps >= 9500:  # 95%+ would explode
            raise GrossUpError(
                f"percentage fees too high ({percentage_sum_bps} bps), cannot gross-up"
            )

        denominator_bps = 10_000 - percentage_sum_bps
        # Ceiling division: (a * 10000 + (denom - 1)) // denom
        variable_gross = math.ceil((net_target * 10_000) / denominator_bps)
        fixed_total = tier_fixed + stripe_fixed + wise_fixed
        customer_price = variable_gross + fixed_total

        # Sanity: fee amounts on the actual customer_price (so they sum correctly)
        platform_fee = apply_bps(variable_gross, tier_bps) + tier_fixed
        stripe_fee = apply_bps(variable_gross, stripe_bps) + stripe_fixed
        wise_fee = apply_bps(variable_gross, wise_bps) + wise_fixed
        merchant_net = net_target
        gross_up = True

        # Price-explosion guard
        if customer_price >= net_target * 2:
            raise GrossUpError(
                f"gross-up explosion: customer_price={customer_price} "
                f"vs net_target={net_target}"
            )

    return GrossUpResult(
        customer_price_minor=int(customer_price),
        merchant_net_minor=int(merchant_net),
        net_target_minor=int(net_target),
        full_service_price_minor=int(service_price_minor),
        on_site_amount_minor=int(on_site_amount),
        platform_fee_minor=int(platform_fee),
        stripe_fee_minor=int(stripe_fee),
        wise_fee_minor=int(wise_fee),
        base_currency=base_currency,
        fee_preference=fee_preference,
        fee_rate_bps=tier_bps,
        deposit_applied=deposit_applied,
        deposit_minor=deposit_minor,
        gross_up_applied=gross_up,
    )


def preview_both_modes(
    *,
    base_currency: str,
    service_price_minor: int,
    tier: str,
    deposit_rule: Optional[DepositRule] = None,
) -> dict:
    """Return both seller_pays and buyer_pays results side by side — for UI comparison."""
    seller = compute_customer_price(
        base_currency=base_currency,
        service_price_minor=service_price_minor,
        fee_preference="seller_pays",
        tier=tier,
        deposit_rule=deposit_rule,
    )
    buyer = compute_customer_price(
        base_currency=base_currency,
        service_price_minor=service_price_minor,
        fee_preference="buyer_pays",
        tier=tier,
        deposit_rule=deposit_rule,
    )
    return {
        "seller_pays": seller.to_dict(),
        "buyer_pays": buyer.to_dict(),
        "base_currency": base_currency,
        "tier": tier,
        "service_price_minor": service_price_minor,
    }
