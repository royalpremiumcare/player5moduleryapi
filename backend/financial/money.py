"""
PLANN Financial Engine — Money Utilities

All monetary values are stored as integers in minor units:
  - TRY → kuruş  (1₺ = 100 kuruş)
  - GBP → pence   (1£ = 100 pence)

Exchange rates are stored as rate_micro: int = rate × 1_000_000
  - e.g. GBP/TRY 42.35 → 42_350_000
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dataclasses import dataclass
from typing import Optional
import re
import string


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_CURRENCIES = {"GBP", "TRY"}
RATE_MULTIPLIER = 1_000_000  # 6-decimal precision for exchange rates
MINOR_UNIT_FACTOR = 100      # Both GBP and TRY have 2 decimal places

CURRENCY_SYMBOLS = {
    "GBP": "£",
    "TRY": "₺",
}

CURRENCY_LOCALES = {
    "GBP": {"decimal": ".", "thousands": ",", "symbol_position": "prefix"},
    "TRY": {"decimal": ",", "thousands": ".", "symbol_position": "suffix"},
}


# ---------------------------------------------------------------------------
# Tier Configuration — Single Source of Truth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierConfig:
    """Immutable tier configuration for a specific base_currency + tier combo."""
    tier: str
    base_currency: str
    limit_minor: int       # Payout threshold in minor units
    fee_rate_bps: int      # Platform commission in basis points
    fixed_fee_minor: int   # Fixed per-transaction fee in minor units (TRY only, 0 for GBP)
    gbp_target_minor: int  # Target GBP equivalent in pence (for Currency Shield)
    wise_cost_estimate_minor: int  # Estimated Wise transfer cost in pence


# GBP market tiers — fixed, no currency shield needed
_GBP_TIERS = {
    "fast": TierConfig(
        tier="fast", base_currency="GBP",
        limit_minor=2_500,       # £25
        fee_rate_bps=500,        # 5%
        fixed_fee_minor=0,       # No fixed fee for GBP
        gbp_target_minor=2_500,  # £25 (1:1)
        wise_cost_estimate_minor=20,  # ~£0.20 BACS
    ),
    "standard": TierConfig(
        tier="standard", base_currency="GBP",
        limit_minor=5_000,       # £50
        fee_rate_bps=300,        # 3%
        fixed_fee_minor=0,       # No fixed fee for GBP
        gbp_target_minor=5_000,  # £50
        wise_cost_estimate_minor=30,  # ~£0.30 BACS
    ),
    "vip": TierConfig(
        tier="vip", base_currency="GBP",
        limit_minor=10_000,      # £100
        fee_rate_bps=200,        # 2%
        fixed_fee_minor=0,       # No fixed fee for GBP
        gbp_target_minor=10_000, # £100
        wise_cost_estimate_minor=40,  # ~£0.40 BACS
    ),
}

# TRY market tiers — limits are dynamic (Currency Shield updates them)
# Commission formula: %X + fixed 15₺ per transaction
#
# fast tier eşiği sabitlenir: ₺6.000 (Currency Shield dinamik hesaplamasının üstüne
# yazılır — iş kararı: operator-facing eşik kur dalgalanmasından etkilenmesin).
# None yaparsanız kur bazlı dinamik hesaplama devreye girer.
TRY_FAST_LIMIT_OVERRIDE_MINOR: Optional[int] = 600_000

_TRY_TIERS = {
    "fast": TierConfig(
        tier="fast", base_currency="TRY",
        limit_minor=(
            TRY_FAST_LIMIT_OVERRIDE_MINOR
            if TRY_FAST_LIMIT_OVERRIDE_MINOR is not None
            else 600_000
        ),  # ₺300 (test) / ₺6,000 (prod)
        fee_rate_bps=1_000,        # 10%
        fixed_fee_minor=1_500,     # +₺15 per transaction
        gbp_target_minor=10_000,   # £100 target
        wise_cost_estimate_minor=250,  # ~£2.50 Wise Balance transfer
    ),
    "standard": TierConfig(
        tier="standard", base_currency="TRY",
        limit_minor=1_200_000,     # ₺12,000
        fee_rate_bps=800,          # 8%
        fixed_fee_minor=1_500,     # +₺15 per transaction
        gbp_target_minor=20_000,   # £200 target
        wise_cost_estimate_minor=250,
    ),
    "vip": TierConfig(
        tier="vip", base_currency="TRY",
        limit_minor=3_000_000,     # ₺30,000
        fee_rate_bps=700,          # 7%
        fixed_fee_minor=1_500,     # +₺15 per transaction
        gbp_target_minor=50_000,   # £500 target
        wise_cost_estimate_minor=250,
    ),
}

# Minimum online payment/deposit limits (minor units)
MIN_ONLINE_PAYMENT_MINOR = {"TRY": 30_000, "GBP": 500}   # ₺300 / £5
MIN_DEPOSIT_MINOR = {"TRY": 20_000, "GBP": 300}           # ₺200 / £3

_TIER_REGISTRY = {
    "GBP": _GBP_TIERS,
    "TRY": _TRY_TIERS,
}


def get_tier_config(base_currency: str, tier: str) -> TierConfig:
    """Return the tier configuration for a given currency and tier level."""
    _validate_currency(base_currency)
    tiers = _TIER_REGISTRY.get(base_currency)
    if not tiers or tier not in tiers:
        raise ValueError(f"Unknown tier '{tier}' for currency '{base_currency}'")
    return tiers[tier]


def get_all_tiers(base_currency: str) -> dict[str, TierConfig]:
    """Return all tier configs for a currency."""
    _validate_currency(base_currency)
    return dict(_TIER_REGISTRY[base_currency])


def update_try_tier_limit(tier: str, new_limit_minor: int) -> TierConfig:
    """
    Update a TRY tier's limit (called by Currency Shield).
    Returns the new TierConfig. GBP tiers cannot be updated.
    """
    if tier not in _TRY_TIERS:
        raise ValueError(f"Unknown TRY tier: {tier}")
    if new_limit_minor <= 0:
        raise ValueError(f"Tier limit must be positive, got {new_limit_minor}")
    old = _TRY_TIERS[tier]
    updated = TierConfig(
        tier=old.tier,
        base_currency=old.base_currency,
        limit_minor=new_limit_minor,
        fee_rate_bps=old.fee_rate_bps,
        fixed_fee_minor=old.fixed_fee_minor,
        gbp_target_minor=old.gbp_target_minor,
        wise_cost_estimate_minor=old.wise_cost_estimate_minor,
    )
    _TRY_TIERS[tier] = updated
    return updated


# ---------------------------------------------------------------------------
# Currency Conversion
# ---------------------------------------------------------------------------

def to_minor(amount: Decimal, currency: str) -> int:
    """
    Convert a human-readable amount to minor units.
    e.g. Decimal("50.00") with "GBP" → 5000 (pence)
    """
    _validate_currency(currency)
    if amount < 0:
        raise ValueError(f"Amount cannot be negative: {amount}")
    result = (amount * MINOR_UNIT_FACTOR).to_integral_value(rounding=ROUND_HALF_UP)
    return int(result)


def from_minor(minor: int, currency: str) -> Decimal:
    """
    Convert minor units back to human-readable Decimal.
    e.g. 5000 with "GBP" → Decimal("50.00")
    """
    _validate_currency(currency)
    return (Decimal(minor) / MINOR_UNIT_FACTOR).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def apply_rate(amount_minor: int, rate_micro: int, *, inverse: bool = False) -> int:
    """
    Convert between currencies using rate_micro.

    Default (inverse=False): GBP → TRY
        try_minor = (gbp_minor * rate_micro) // RATE_MULTIPLIER

    Inverse (inverse=True): TRY → GBP
        gbp_minor = (try_minor * RATE_MULTIPLIER) // rate_micro
    """
    if rate_micro <= 0:
        raise ValueError(f"Exchange rate must be positive, got {rate_micro}")
    if inverse:
        return (amount_minor * RATE_MULTIPLIER + rate_micro // 2) // rate_micro
    return (amount_minor * rate_micro + RATE_MULTIPLIER // 2) // RATE_MULTIPLIER


def rate_to_micro(rate: Decimal) -> int:
    """Convert a decimal exchange rate to rate_micro int. e.g. 42.35 → 42_350_000"""
    return int((rate * RATE_MULTIPLIER).to_integral_value(rounding=ROUND_HALF_UP))


def rate_from_micro(rate_micro: int) -> Decimal:
    """Convert rate_micro back to decimal. e.g. 42_350_000 → Decimal('42.350000')"""
    return (Decimal(rate_micro) / RATE_MULTIPLIER).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def bps_to_rate(bps: int) -> Decimal:
    """Convert basis points to decimal rate. e.g. 700 → Decimal('0.07')"""
    return (Decimal(bps) / Decimal(10_000)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def apply_bps(amount_minor: int, bps: int) -> int:
    """
    Apply basis points to an amount using Decimal + ROUND_HALF_UP.
    e.g. 100000 kuruş at 700bps → 7000 kuruş

    Finansal hesaplarda standart yuvarlama (ROUND_HALF_UP). Negatif olmayan
    girdiler için eski tamsayı formülüyle ((x*bps+5000)//10000) birebir aynıdır.
    """
    result = (Decimal(amount_minor) * Decimal(bps) / Decimal(10_000)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(result)


# ---------------------------------------------------------------------------
# Display Formatting
# ---------------------------------------------------------------------------

def format_display(minor: int, currency: str) -> str:
    """
    Format minor units for display.
    GBP: "£50.00"
    TRY: "1.000,00 ₺"
    """
    _validate_currency(currency)
    locale = CURRENCY_LOCALES[currency]
    symbol = CURRENCY_SYMBOLS[currency]

    whole = abs(minor) // MINOR_UNIT_FACTOR
    frac = abs(minor) % MINOR_UNIT_FACTOR
    sign = "-" if minor < 0 else ""

    # Format with thousands separator
    whole_str = f"{whole:,}".replace(",", locale["thousands"])
    frac_str = f"{frac:02d}"
    amount_str = f"{whole_str}{locale['decimal']}{frac_str}"

    if locale["symbol_position"] == "prefix":
        return f"{sign}{symbol}{amount_str}"
    return f"{sign}{amount_str} {symbol}"


def format_display_short(minor: int, currency: str) -> str:
    """Short format without minor units when .00. e.g. '£50' or '₺6.000'"""
    _validate_currency(currency)
    locale = CURRENCY_LOCALES[currency]
    symbol = CURRENCY_SYMBOLS[currency]

    whole = abs(minor) // MINOR_UNIT_FACTOR
    frac = abs(minor) % MINOR_UNIT_FACTOR
    sign = "-" if minor < 0 else ""

    whole_str = f"{whole:,}".replace(",", locale["thousands"])

    if frac == 0:
        amount_str = whole_str
    else:
        amount_str = f"{whole_str}{locale['decimal']}{frac:02d}"

    if locale["symbol_position"] == "prefix":
        return f"{sign}{symbol}{amount_str}"
    return f"{sign}{amount_str} {symbol}"


# ---------------------------------------------------------------------------
# IBAN & Bank Account Validation
# ---------------------------------------------------------------------------

# Turkish IBAN: TR + 2 check digits + 22 alphanumeric = 26 chars total
_TR_IBAN_REGEX = re.compile(r"^TR\d{24}$")

# UK Sort Code: 6 digits, optionally with hyphens (e.g. "12-34-56" or "123456")
_UK_SORT_CODE_REGEX = re.compile(r"^\d{2}-?\d{2}-?\d{2}$")

# UK Account Number: 8 digits
_UK_ACCOUNT_NUMBER_REGEX = re.compile(r"^\d{8}$")


def validate_turkish_iban(iban: str) -> bool:
    """
    Validate a Turkish IBAN.
    Format: TR + 24 digits = 26 characters total.
    Performs format check + ISO 7064 Mod 97 checksum.
    """
    if not iban:
        return False

    cleaned = iban.upper().replace(" ", "")

    if not _TR_IBAN_REGEX.match(cleaned):
        return False

    return _iban_checksum_valid(cleaned)


def validate_uk_sort_code(sort_code: str) -> bool:
    """Validate UK sort code format (6 digits, optionally hyphenated)."""
    if not sort_code:
        return False
    return bool(_UK_SORT_CODE_REGEX.match(sort_code.strip()))


def normalize_sort_code(sort_code: str) -> str:
    """Normalize sort code to 6 digits without hyphens."""
    return sort_code.replace("-", "").strip()


def validate_uk_account_number(account_number: str) -> bool:
    """Validate UK bank account number (8 digits)."""
    if not account_number:
        return False
    return bool(_UK_ACCOUNT_NUMBER_REGEX.match(account_number.strip()))


def validate_bank_details(base_currency: str, **kwargs) -> tuple[bool, Optional[str]]:
    """
    Validate bank details based on merchant's base_currency.

    For TRY: requires 'iban'
    For GBP: requires 'sort_code' and 'account_number'

    Returns (is_valid, error_message).
    """
    _validate_currency(base_currency)

    if base_currency == "TRY":
        iban = kwargs.get("iban", "")
        if not validate_turkish_iban(iban):
            return False, "Geçersiz TR IBAN formatı. TR + 24 rakam olmalıdır."
        return True, None

    if base_currency == "GBP":
        sort_code = kwargs.get("sort_code", "")
        account_number = kwargs.get("account_number", "")
        if not validate_uk_sort_code(sort_code):
            return False, "Invalid UK sort code. Must be 6 digits (e.g. 12-34-56)."
        if not validate_uk_account_number(account_number):
            return False, "Invalid UK account number. Must be 8 digits."
        return True, None

    return False, f"Unsupported currency: {base_currency}"


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _validate_currency(currency: str) -> None:
    """Raise ValueError if currency is not supported."""
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported currency '{currency}'. Must be one of: {SUPPORTED_CURRENCIES}"
        )


def _iban_checksum_valid(iban: str) -> bool:
    """
    ISO 7064 Mod 97-10 checksum validation for IBAN.
    Move the first 4 chars to the end, convert letters to numbers (A=10..Z=35),
    and check that the resulting number mod 97 == 1.
    """
    rearranged = iban[4:] + iban[:4]

    numeric_str = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric_str += ch
        elif ch.isalpha():
            numeric_str += str(ord(ch.upper()) - ord("A") + 10)
        else:
            return False

    try:
        return int(numeric_str) % 97 == 1
    except (ValueError, InvalidOperation):
        return False
