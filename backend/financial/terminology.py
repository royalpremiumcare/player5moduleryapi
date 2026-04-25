"""
PLANN Financial Engine — Terminology Dictionary & Field Mapping

SINGLE SOURCE OF TRUTH for monetary/financial naming.
Enforce these names in all new code, gradually deprecate old names.

See plan Bölüm -1.
"""

# ---------------------------------------------------------------------------
# Canonical Term Definitions
# ---------------------------------------------------------------------------

TERMS = {
    "service_price": {
        "field": "service_price_minor",
        "description": "Hizmetin fiyat listesi tutarı (kapora + on_site toplamı).",
    },
    "net_target": {
        "field": "net_target_minor",
        "description": (
            "Online kanalda müşteriden tahsil edilmesi gereken ham tutar. "
            "Kapora senaryosunda deposit, tam online senaryosunda service_price."
        ),
    },
    "customer_price": {
        "field": "customer_price_minor",
        "description": "Müşterinin Stripe checkout'ta gördüğü ve ödediği nihai tutar.",
    },
    "merchant_net": {
        "field": "merchant_net_minor",
        "description": "İşletmenin cüzdanına yazılan, tüm kesintiler sonrası kalan.",
    },
    "platform_fee": {
        "field": "platform_fee_minor",
        "description": "PLANN'in aldığı tier bazlı komisyon (%bps + sabit).",
    },
    "processor_fee": {
        "field": "stripe_fee_minor",
        "description": "Stripe kesintisi (%bps + sabit, ülkeye göre).",
    },
    "payout_fee": {
        "field": "wise_fee_minor",
        "description": "Wise payout kesintisi (sabit + %bps).",
    },
    "on_site_amount": {
        "field": "on_site_amount_minor",
        "description": "İşletmede nakden/kart ile alınacak kalan tutar.",
    },
}


# ---------------------------------------------------------------------------
# Legacy → Canonical Alias Map (for dual-read during migration)
# ---------------------------------------------------------------------------

LEGACY_ALIASES = {
    # Old name → (canonical_field, note)
    "gross_minor": ("customer_price_minor", "buyer_pays gross"),
    "net_minor": ("merchant_net_minor", "post-fee merchant share"),
    "fee_minor": ("platform_fee_minor", "platform commission only"),
    "amount_display_minor": ("customer_price_minor", "display-facing amount"),
}


def canonical_field(legacy_name: str) -> str:
    """Return the canonical field name for a legacy alias, or the input if already canonical."""
    entry = LEGACY_ALIASES.get(legacy_name)
    if entry is None:
        return legacy_name
    return entry[0]


def get_monetary_value(doc: dict, canonical: str, default: int = 0) -> int:
    """
    Dual-read helper: try canonical field first, fall back to legacy aliases.

    Example:
        price = get_monetary_value(tx, "customer_price_minor")
    """
    if canonical in doc and doc[canonical] is not None:
        return int(doc[canonical])
    # Search aliases that map to this canonical
    for legacy, (mapped, _note) in LEGACY_ALIASES.items():
        if mapped == canonical and legacy in doc and doc[legacy] is not None:
            return int(doc[legacy])
    return default
