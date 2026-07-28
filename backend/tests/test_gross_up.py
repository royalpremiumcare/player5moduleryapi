"""
Tests for financial.gross_up_service — ALL-IN komisyon modeli.

MİMARİ KURAL: İşletmeden düşülen TEK kesinti PLANN tier komisyonudur.
Stripe/Wise maliyeti merchant_net'ten ASLA düşülmez (yalnızca bilgilendirme).

Covers:
  - seller_pays: merchant_net == net_target - platform_fee (stripe/wise ETKİSİZ)
  - buyer_pays : merchant_net == net_target, customer_price == net_target + platform_fee
  - TRY ve GBP
  - Deposit / full_online / on_site
  - Komisyon net_target'ı aşarsa GrossUpError
  - stripe_fee/wise_fee yalnızca bilgilendirme (merchant'a yansımaz)
"""

import pytest

from financial.fee_calculator import DepositRule
from financial.gross_up_service import (
    compute_customer_price,
    preview_both_modes,
    GrossUpError,
)


@pytest.fixture(autouse=True)
def _env_fixed_processor_fees(monkeypatch):
    """Deterministic Stripe/Wise fee values for reproducible assertions."""
    monkeypatch.setenv("STRIPE_FEE_UK_BPS", "150")   # 1.5%
    monkeypatch.setenv("STRIPE_FEE_UK_FIXED", "25")  # £0.25
    monkeypatch.setenv("STRIPE_FEE_TR_BPS", "250")   # 2.5%
    monkeypatch.setenv("STRIPE_FEE_TR_FIXED", "150")  # ₺1.50
    monkeypatch.setenv("WISE_PAYOUT_BPS", "0")
    monkeypatch.setenv("WISE_PAYOUT_FIXED_MINOR", "200")


# ---------------------------------------------------------------------------
# seller_pays — merchant_net = net_target - platform_fee (SADECE komisyon)
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
    # GBP standard: tier 300 bps + 0 fixed → platform_fee = 150
    assert r.platform_fee_minor == 150
    # ALL-IN: merchant_net = net_target - platform_fee (stripe/wise düşülmez)
    assert r.merchant_net_minor == 5000 - 150
    assert r.gross_up_applied is False
    # stripe/wise yalnızca bilgilendirme
    assert r.stripe_fee_minor == 100   # 5000*0.015 + 25
    assert r.wise_fee_minor == 200     # 0 + 200


def test_stripe_wise_fee_does_not_affect_merchant_net(monkeypatch):
    """Stripe bps aşırı yüksek olsa bile merchant_net yalnızca komisyona bağlı."""
    monkeypatch.setenv("STRIPE_FEE_UK_BPS", "9500")  # %95 (absürt)
    monkeypatch.setenv("WISE_PAYOUT_FIXED_MINOR", "999999")
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=5000,
        fee_preference="seller_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    # platform_fee tier'a bağlı (300 bps) — stripe/wise'tan bağımsız
    assert r.platform_fee_minor == 150
    assert r.merchant_net_minor == 5000 - 150   # değişmedi!


# ---------------------------------------------------------------------------
# buyer_pays — merchant_net = net_target, customer_price = net_target + komisyon
# ---------------------------------------------------------------------------

def test_gbp_buyer_pays_only_commission_added():
    r = compute_customer_price(
        base_currency="GBP",
        service_price_minor=10000,
        fee_preference="buyer_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    # tier standard GBP = 300 bps + 0 fixed → platform_fee = 300
    assert r.platform_fee_minor == 300
    assert r.customer_price_minor == 10000 + 300   # yalnızca komisyon eklenir
    assert r.merchant_net_minor == 10000
    assert r.gross_up_applied is True


def test_try_buyer_pays_merchant_net_equals_net_target():
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=10000,  # ₺100
        fee_preference="buyer_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    # TRY standard: 800 bps + 1500 fixed → platform_fee = 800 + 1500 = 2300
    assert r.platform_fee_minor == 2300
    assert r.customer_price_minor == 10000 + 2300
    assert r.merchant_net_minor == 10000
    assert r.gross_up_applied is True


def test_try_seller_pays_deposit_percentage():
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=20000,   # ₺200.00
        fee_preference="seller_pays",
        tier="standard",
        deposit_rule=DepositRule(payment_rule="deposit", deposit_type="percentage", deposit_value=2500),
    )
    assert r.net_target_minor == 5000       # 25% of 20000
    assert r.deposit_applied is True
    assert r.on_site_amount_minor == 15000
    assert r.customer_price_minor == 5000
    # platform_fee = 5000*0.08 + 1500 = 1900
    assert r.platform_fee_minor == 400 + 1500
    assert r.merchant_net_minor == 5000 - 1900


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

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


def test_commission_exceeding_net_raises():
    """Küçük tutar + sabit ücret komisyonu net'i aşarsa GrossUpError."""
    with pytest.raises(GrossUpError):
        compute_customer_price(
            base_currency="TRY",
            service_price_minor=1000,   # ₺10 → komisyon 80+1500=1580 > 1000
            fee_preference="seller_pays",
            tier="standard",
            deposit_rule=DepositRule(payment_rule="full_online"),
        )


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


# ---------------------------------------------------------------------------
# Preview both modes — merchant'a yalnızca komisyon görünür (1:1 garantisi)
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
