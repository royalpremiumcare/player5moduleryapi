"""
Tests for financial.gross_up_service — dynamic commission calculation.

Covers:
  - seller_pays mode (fees deducted from merchant)
  - buyer_pays mode (gross-up with fixed fees OUTSIDE denominator)
  - TRY and GBP currencies
  - Deposit vs full_online vs on_site
  - Explosion guard (percentage > 95%)
  - Roundtrip: merchant_net + fees == customer_price (seller), merchant_net == net_target (buyer)
"""

import os
import pytest

from financial.fee_calculator import DepositRule
from financial.gross_up_service import (
    compute_customer_price,
    preview_both_modes,
    GrossUpError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _env_fixed_processor_fees(monkeypatch):
    """Deterministic Stripe fee values for reproducible assertions."""
    monkeypatch.setenv("STRIPE_FEE_UK_BPS", "150")   # 1.5%
    monkeypatch.setenv("STRIPE_FEE_UK_FIXED", "25")  # £0.25
    monkeypatch.setenv("STRIPE_FEE_TR_BPS", "250")   # 2.5%
    monkeypatch.setenv("STRIPE_FEE_TR_FIXED", "150") # ₺1.50
    monkeypatch.setenv("WISE_PAYOUT_BPS", "0")
    monkeypatch.setenv("WISE_PAYOUT_FIXED_MINOR", "200")  # 2 minor units (2₺ / £2)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_gbp_seller_pays_full_online():
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=5000,   # £50.00
        fee_preference="seller_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    assert r.customer_price_minor == 5000
    assert r.net_target_minor == 5000
    assert r.merchant_net_minor < 5000
    # GBP standard: tier 300 bps + 0 fixed, stripe 150 bps + 25 fixed, wise 0 bps + 200 fixed
    # platform = 5000*0.03 = 150, stripe = 5000*0.015 + 25 = 75+25 = 100, wise = 0 + 200 = 200
    assert r.platform_fee_minor == 150
    assert r.stripe_fee_minor == 100
    assert r.wise_fee_minor == 200
    assert r.merchant_net_minor == 5000 - 150 - 100 - 200
    assert r.gross_up_applied is False


def test_gbp_buyer_pays_grossup_reaches_net_target():
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=5000,
        fee_preference="buyer_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    # Merchant must still end up with net_target (5000)
    assert r.merchant_net_minor == 5000
    assert r.net_target_minor == 5000
    # Customer pays more than net_target
    assert r.customer_price_minor > 5000
    assert r.gross_up_applied is True
    # Should not explode (> 2x)
    assert r.customer_price_minor < 10000


def test_gbp_buyer_pays_fixed_fees_outside_denominator():
    """
    Critical invariant: fixed fees are NOT marked up.
    If net_target = 100, and only fixed fees existed, customer_price should be
    100 + sum(fixed). The denominator uses only percentage bps.
    """
    os_fixed = os.environ
    # Temporarily zero-out percentages
    os_fixed["STRIPE_FEE_UK_BPS"] = "0"
    os_fixed["WISE_PAYOUT_BPS"] = "0"
    # tier_bps for GBP standard is 300; override by using 'fast' (500)? No, use pure test
    # We'll assert via buyer_pays with only our non-zero percentages being tier.
    # Easier: just confirm fixed fees ARE included in customer_price, not scaled by percentage.
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=10000,
        fee_preference="buyer_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    # tier_bps=300 for standard GBP, stripe_bps=0 (overridden), wise_bps=0
    # percentage_sum = 300
    # variable_gross = ceil(10000 * 10000 / 9700) = ceil(103092.78) = 10310
    # fixed = tier(0 for GBP) + stripe(25) + wise(200) = 225
    # customer_price = 10310 + 225 = 10535
    assert r.customer_price_minor == 10310 + 0 + 25 + 200
    assert r.merchant_net_minor == 10000


def test_try_seller_pays_deposit_percentage():
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=20000,   # ₺200.00
        fee_preference="seller_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="deposit", deposit_type="percentage", deposit_value=2500),  # 25%
    )
    # deposit = 25% of 20000 = 5000 (₺50)
    assert r.net_target_minor == 5000
    assert r.deposit_applied is True
    assert r.deposit_minor == 5000
    assert r.on_site_amount_minor == 15000  # remainder
    assert r.customer_price_minor == 5000
    # TRY standard: tier 800 bps + 1500 fixed, stripe 250 bps + 150 fixed, wise 0 + 200 fixed
    assert r.platform_fee_minor == 400 + 1500   # 5000*0.08 + 1500
    assert r.stripe_fee_minor == 125 + 150      # 5000*0.025 + 150
    assert r.wise_fee_minor == 0 + 200
    expected_net = 5000 - (400+1500) - (125+150) - 200
    assert r.merchant_net_minor == expected_net


def test_try_buyer_pays_merchant_net_equals_net_target():
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=10000,  # ₺100
        fee_preference="buyer_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    assert r.merchant_net_minor == 10000
    assert r.customer_price_minor > 10000
    # Percentage sum: tier 800 + stripe 250 + wise 0 = 1050 bps = 10.5%
    # variable_gross = ceil(10000 * 10000 / (10000 - 1050)) = ceil(10000*10000/8950) = ceil(11173.18) = 11174
    # fixed_total = 1500 + 150 + 200 = 1850
    # customer_price = 11174 + 1850 = 13024
    assert r.customer_price_minor == 11174 + 1850
    assert r.gross_up_applied is True


def test_on_site_zero_online():
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=5000,
        fee_preference="seller_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="on_site"),
    )
    assert r.customer_price_minor == 0
    assert r.merchant_net_minor == 0
    assert r.on_site_amount_minor == 5000
    assert r.gross_up_applied is False


def test_invalid_fee_preference_raises():
    with pytest.raises(GrossUpError):
        compute_customer_price(
            base_currency="GBP",
            service_price_minor=5000,
            fee_preference="garbage",
            tier="standard",
        )


def test_zero_service_price_raises():
    with pytest.raises(GrossUpError):
        compute_customer_price(
            base_currency="GBP",
            service_price_minor=0,
            fee_preference="seller_pays",
            tier="standard",
        )


def test_explosion_guard(monkeypatch):
    monkeypatch.setenv("STRIPE_FEE_UK_BPS", "9500")
    with pytest.raises(GrossUpError):
        compute_customer_price(
            base_currency="GBP",
            service_price_minor=5000,
            fee_preference="buyer_pays",
            tier="standard",
            deposit_rule=DepositRule(payment_rule="full_online"),
        )


# ---------------------------------------------------------------------------
# Preview both modes
# ---------------------------------------------------------------------------

def test_preview_both_modes_returns_both():
    out = preview_both_modes(
        base_currency="GBP",
        service_price_minor=5000,
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    assert "seller_pays" in out
    assert "buyer_pays" in out
    assert out["seller_pays"]["customer_price_minor"] == 5000
    assert out["buyer_pays"]["merchant_net_minor"] == 5000
    assert out["buyer_pays"]["customer_price_minor"] > 5000
