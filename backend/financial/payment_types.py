"""
PLANN Financial Engine — Payment Type Taxonomy

Business (işletme müşteri ödemeleri) ile Subscription (PLANN abonelik geliri)
akışlarını net biçimde ayırmak için tek kaynak. Magic string yasağı: tüm
payment_type değerleri ve Stripe metadata anahtarları buradan alınır.

- BUSINESS: İşletme müşterilerinden alınan ödemeler (PaymentIntent/Checkout,
  ileride Wise ile GBP→TRY convert edilecek olan tutarlar).
- SUBSCRIPTION: PLANN'ın kendi SaaS abonelik geliri (GBP kalır, ASLA convert edilmez).

Yeni bir ödeme tipi eklemek için: PaymentType'a değer ekle + PAYMENT_TYPE_REGISTRY'ye
metadata gir. Convert edilebilirlik `convertible` bayrağıyla belirlenir.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


class PaymentType(str, Enum):
    """Ödeme akışı tipi. str tabanlı — MongoDB/Stripe metadata ile uyumlu."""

    BUSINESS = "business"
    SUBSCRIPTION = "subscription"

    @classmethod
    def from_value(cls, value: str, default: "PaymentType" = None) -> "PaymentType":
        """Serbest string'i güvenli şekilde PaymentType'a çevir (bilinmeyen → default)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except (ValueError, AttributeError):
            return default if default is not None else cls.BUSINESS


class PaymentChannel(str, Enum):
    """BUSINESS ödemesinin alt kanalı (raporlama/okunabilirlik için)."""

    APPOINTMENT = "appointment"
    MULTI_SERVICE = "multi_service"
    PAYMENT_LINK = "payment_link"


# ---------------------------------------------------------------------------
# Stripe metadata anahtarları — tek kaynak (magic string yasağı)
# ---------------------------------------------------------------------------

META_PAYMENT_TYPE = "payment_type"
META_PAYMENT_CHANNEL = "payment_channel"
META_BUSINESS_ID = "business_id"
META_ORGANIZATION_ID = "organization_id"
# Geri uyumluluk: eski webhook ayrıştırması bu bayrağa bakıyor.
META_IS_MERCHANT_PAYMENT = "is_merchant_payment"


# ---------------------------------------------------------------------------
# Payment Type Registry — extension point
# ---------------------------------------------------------------------------

class PaymentTypeConfig:
    """Bir payment_type için davranış metadata'sı (extension point)."""

    def __init__(
        self,
        *,
        creates_merchant_transaction: bool,
        convertible: bool,
        description: str,
    ):
        # BUSINESS → merchant_transactions kaydı oluşturur; SUBSCRIPTION → oluşturmaz.
        self.creates_merchant_transaction = creates_merchant_transaction
        # Yalnızca convertible=True olanlar Wise GBP→TRY conversion kapsamına girer.
        self.convertible = convertible
        self.description = description


PAYMENT_TYPE_REGISTRY: Dict[PaymentType, PaymentTypeConfig] = {
    PaymentType.BUSINESS: PaymentTypeConfig(
        creates_merchant_transaction=True,
        convertible=True,
        description="İşletme müşteri ödemesi — Wise ile GBP→TRY convert edilir.",
    ),
    PaymentType.SUBSCRIPTION: PaymentTypeConfig(
        creates_merchant_transaction=False,
        convertible=False,
        description="PLANN SaaS abonelik geliri — GBP kalır, asla convert edilmez.",
    ),
}


def is_convertible(payment_type) -> bool:
    """payment_type Wise conversion kapsamına giriyor mu? Bilinmeyen → False (güvenli)."""
    pt = PaymentType.from_value(payment_type, default=None) if not isinstance(payment_type, PaymentType) else payment_type
    if pt is None:
        return False
    cfg = PAYMENT_TYPE_REGISTRY.get(pt)
    return bool(cfg and cfg.convertible)
