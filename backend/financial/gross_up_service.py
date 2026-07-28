"""
Gross-Up Service — ALL-IN komisyon (buyer_pays / seller_pays modları).

MİMARİ KURAL: İşletmeden düşülen TEK kesinti PLANN tier komisyonudur
(tier %bps + sabit ücret). Stripe processor ücreti + Wise payout maliyeti bu
komisyonun İÇİNDE eritilir — merchant_net'ten ASLA ikinci kez düşülmez.
Arayüzde vaat edilen komisyon oranı ile cüzdana yansıyan net birebir uyuşur.

Terminology (see terminology.py):
  - net_target: merchant wants this amount net (online portion)
  - customer_price: what the customer sees/pays on Stripe
  - merchant_net: what lands in the wallet (net_target - commission, veya buyer_pays'te net_target)
  - platform_fee: PLANN's commission (tier %bps + sabit) — TEK merchant kesintisi
  - stripe_fee/wise_fee: PLANN'ın iç maliyet TAHMİNİ (yalnızca marj raporu; kesinti değil)
"""

from __future__ import annotations

import logging
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
    platform_fee_minor: int          # PLANN komisyonu — TEK merchant kesintisi
    stripe_fee_minor: int            # PLANN iç maliyet tahmini (kesinti DEĞİL)
    wise_fee_minor: int              # PLANN iç maliyet tahmini (kesinti DEĞİL)

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
    ALL-IN komisyon modeli (mimari kural).

    İşletmeden düşülen TEK kesinti PLANN tier komisyonudur (tier %bps + sabit ücret).
    Stripe, Wise ve gelecekteki ödeme maliyetleri bu komisyonun İÇİNDE eritilir;
    `merchant_net`'ten ASLA ikinci kez düşülmez. Böylece arayüzde vaat edilen oran ile
    cüzdana yansıyan net tutar matematiksel olarak birebir uyuşur.

      seller_pays: müşteri `net_target` öder; komisyon işletmeden düşülür.
                   merchant_net = net_target - commission
      buyer_pays : müşteri `net_target + commission` öder; işletme tam `net_target` alır.
                   merchant_net = net_target

    `stripe_fee_minor` / `wise_fee_minor`: yalnızca PLANN iç marj raporu için TAHMİN.
    merchant_net'e veya customer_price'a ETKİ ETMEZ (çift sayım yasak).
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

    # TEK işletme kesintisi: PLANN tier komisyonu (all-in). Stripe/Wise DAHİL DEĞİL.
    platform_fee = apply_bps(net_target, tier_bps) + tier_fixed

    if fee_preference == "seller_pays":
        customer_price = net_target
        merchant_net = net_target - platform_fee
        gross_up = False
    else:  # buyer_pays — komisyon müşteriye eklenir, işletme net_target'ı tam alır
        customer_price = net_target + platform_fee
        merchant_net = net_target
        gross_up = True

    # Sanity: komisyon net_target'ı aşarsa (küçük tutar + sabit ücret) net negatif olur.
    if merchant_net < 0:
        raise GrossUpError(
            f"commission ({platform_fee}) exceeds net_target ({net_target}); "
            f"amount too small for tier fixed fee"
        )

    # PLANN iç maliyet TAHMİNLERİ (bilgilendirme/marj raporu; kesinti DEĞİL).
    stripe_fee = apply_bps(customer_price, stripe_bps) + stripe_fixed
    wise_fee = apply_bps(net_target, wise_bps) + wise_fixed

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
