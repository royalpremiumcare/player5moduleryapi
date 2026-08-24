"""
PLANN Financial Engine — Merchant Checkout (Stripe Customer Payments)

Creates Stripe Checkout Sessions for customer-facing service payments.
Currency is determined by merchant's base_currency.
Handles webhook events for payment lifecycle.
"""

import os
import hashlib
import logging
import stripe
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import asyncio
from .fee_calculator import calculate_fee, DepositRule, FeeResult
from .state_machine import StateMachine, create_transaction
from .schemas import WebhookEvent
from .feature_flags import is_env_flag_enabled
from .gross_up_service import compute_customer_price, GrossUpError
from .payment_types import (
    PaymentType,
    PaymentChannel,
    META_PAYMENT_TYPE,
    META_PAYMENT_CHANNEL,
    META_BUSINESS_ID,
    META_IS_MERCHANT_PAYMENT,
)

logger = logging.getLogger(__name__)


def _sobj(obj: Any, key: str, default: Any = None) -> Any:
    """
    Stripe nesnesinden (StripeObject) veya dict'ten güvenli alan okuma.

    stripe-python v15'te API'den dönen nesneler artık dict değildir ve `.get()`
    metodu yoktur (`.get` erişimi AttributeError fırlatır). Bu helper hem
    StripeObject hem dict için çalışır; alan yoksa default döner.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        val = obj[key]
        return val if val is not None else default
    except Exception:
        return getattr(obj, key, default)


def _build_pricing_snapshot(
    base_currency: str,
    tier: str,
    fee_preference: str,
    gross_up_applied: bool,
) -> Dict[str, Any]:
    """
    İşlem anındaki komisyon ayarlarının SNAPSHOT'unu üretir.

    Ayarlar (tier / oran / sabit ücret / mod) SONRADAN değişse bile bu snapshot
    işlemin üzerinde sabit kalır → muhasebe/denetim için single source of truth.
    """
    from .money import get_tier_config
    from datetime import datetime, timezone
    tier_bps = 0
    tier_fixed = 0
    try:
        cfg = get_tier_config(base_currency, tier)
        tier_bps = cfg.fee_rate_bps
        tier_fixed = cfg.fixed_fee_minor
    except Exception:
        pass
    return {
        "tier": tier,
        "commission_rate_bps": tier_bps,
        "commission_fixed_fee_minor": tier_fixed,
        "fee_preference": fee_preference,
        "base_currency": base_currency,
        "gross_up_applied": bool(gross_up_applied),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


PAYMENT_SUCCESS_URL = os.getenv("PAYMENT_SUCCESS_URL", "https://plannapp.co/#/payment-success")
PAYMENT_CANCEL_URL = os.getenv("PAYMENT_CANCEL_URL", "https://plannapp.co/#/payment-cancelled")
STRIPE_MERCHANT_WEBHOOK_SECRET = os.getenv("STRIPE_MERCHANT_WEBHOOK_SECRET", "")


async def create_customer_checkout_session(
    db,
    organization_id: str,
    service_id: str,
    appointment_id: str,
    customer_phone: str,
    session_count: int = 1,
    customer_name: str = "",
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for a customer payment.

    1. Load merchant settings + service
    2. Calculate fees based on base_currency + tier
    3. Create Stripe session with correct currency
    4. Create pending transaction in DB
    5. Return checkout URL + session info
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise ValueError(f"Settings not found for org: {organization_id}")

    service = await db.services.find_one({
        "id": service_id,
        "organization_id": organization_id,
    })
    if not service:
        raise ValueError(f"Service not found: {service_id}")

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    fee_preference = settings.get("fee_preference", "seller_pays")
    merchant_slug = settings.get("slug", "")
    service_price_minor = service.get("price_minor", 0)
    # Fallback: convert float price to minor units if price_minor not set
    if not service_price_minor and service.get("price"):
        service_price_minor = int(round(service["price"] * 100))
    service_name = service.get("name", "Hizmet")
    company_name = settings.get("company_name", "İşletme")

    if service_price_minor <= 0:
        raise ValueError(f"Service price must be positive: {service_price_minor}")

    from .money import MIN_ONLINE_PAYMENT_MINOR, MIN_DEPOSIT_MINOR
    payment_rule = service.get("payment_rule", "on_site")
    min_online = MIN_ONLINE_PAYMENT_MINOR.get(base_currency, 30_000)
    min_deposit = MIN_DEPOSIT_MINOR.get(base_currency, 20_000)
    if payment_rule in ("online", "full_online") and service_price_minor < min_online:
        raise ValueError(f"Service price below minimum for online payment ({min_online})")
    if payment_rule == "deposit":
        dep_amount = service.get("deposit_amount")
        if dep_amount is not None and int(round(dep_amount * 100)) < min_deposit:
            raise ValueError(f"Deposit amount below minimum ({min_deposit})")

    deposit_rule = _build_deposit_rule(service)

    # Feature flag: FEATURE_GROSS_UP activates processor + payout fees in gross-up.
    # OFF → legacy behaviour (platform fee only).
    gross_up_enabled = is_env_flag_enabled("FEATURE_GROSS_UP")
    gross_up_result = None
    if gross_up_enabled:
        try:
            gross_up_result = compute_customer_price(
                base_currency=base_currency,
                service_price_minor=service_price_minor,
                fee_preference=fee_preference,
                tier=tier,
                deposit_rule=deposit_rule,
            )
        except GrossUpError as ge:
            logger.error("gross-up failed, falling back to legacy fee_calculator: %s", ge)
            gross_up_result = None

    fee_result = calculate_fee(
        base_currency=base_currency,
        service_price_minor=service_price_minor,
        fee_preference=fee_preference,
        tier=tier,
        deposit_rule=deposit_rule,
        session_count=session_count,
    )

    # Choose authoritative amounts: gross_up overrides fee_result customer price
    # and merchant net when the flag is active and computation succeeded.
    if gross_up_result is not None:
        customer_price_minor = gross_up_result.customer_price_minor
        merchant_net_minor = gross_up_result.merchant_net_minor
        platform_fee_minor = gross_up_result.platform_fee_minor
        processor_fee_minor = gross_up_result.stripe_fee_minor
        payout_fee_minor = gross_up_result.wise_fee_minor
    else:
        customer_price_minor = fee_result.gross_minor
        merchant_net_minor = fee_result.net_minor
        platform_fee_minor = fee_result.fee_minor
        processor_fee_minor = 0
        payout_fee_minor = 0

    if customer_price_minor == 0:
        return {
            "payment_required": False,
            "payment_rule": deposit_rule.payment_rule if deposit_rule else "on_site",
            "message": "Bu hizmet için online ödeme gerekmez.",
        }

    custom_text_note = (
        "Platform hizmet bedeli iade kapsamı dışındadır. "
        "PLANNAPP LTD adına tahsil edilmektedir."
    ) if base_currency == "TRY" else (
        "Platform service fee is non-refundable. "
        "Collected on behalf of PLANNAPP LTD."
    )

    product_data = {
        "name": f"{service_name} - {company_name}",
        "description": _build_description(fee_result, service_name, session_count),
    }

    logo = settings.get("logo_url") or ""
    if logo:
        if logo.startswith("http"):
            product_data["images"] = [logo]
        else:
            product_data["images"] = [f"https://plannapp.co{logo}"]
    else:
        product_data["images"] = ["https://plannapp.co/api/static/logo.png"]

    stripe_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": fee_result.stripe_currency,
                "unit_amount": customer_price_minor,
                "product_data": product_data,
            },
            "quantity": 1,
        }],
        custom_text={
            "submit": {"message": custom_text_note},
        },
        metadata={
            "organization_id": organization_id,
            "appointment_id": appointment_id,
            "service_id": service_id,
            "customer_phone": customer_phone,
            "base_currency": base_currency,
            "fee_preference": fee_preference,
            # Legacy aliases (dual-write during terminology migration)
            "fee_minor": str(platform_fee_minor),
            "net_minor": str(merchant_net_minor),
            # Canonical names (PLANN v2 terminology)
            "customer_price_minor": str(customer_price_minor),
            "merchant_net_minor": str(merchant_net_minor),
            "platform_fee_minor": str(platform_fee_minor),
            "stripe_fee_minor": str(processor_fee_minor),
            "wise_fee_minor": str(payout_fee_minor),
            "gross_up_applied": "true" if gross_up_result is not None else "false",
            "session_count": str(session_count),
            "payment_rule": deposit_rule.payment_rule if deposit_rule else "full_online",
            # Business/Subscription ayrımı (resmî) + geri-uyumlu is_merchant_payment
            META_PAYMENT_TYPE: PaymentType.BUSINESS.value,
            META_BUSINESS_ID: organization_id,
            META_PAYMENT_CHANNEL: PaymentChannel.APPOINTMENT.value,
            META_IS_MERCHANT_PAYMENT: "true",
        },
        success_url=f"https://plannapp.co/{merchant_slug}?payment=success&session_id={{CHECKOUT_SESSION_ID}}" if merchant_slug else PAYMENT_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=f"https://plannapp.co/{merchant_slug}?payment=cancelled" if merchant_slug else PAYMENT_CANCEL_URL,
        # Müşterinin checkout sırasında promosyon kodu (Stripe Coupon
        # Promotion Code) girebilmesine izin ver. Bu session'da `discounts`
        # parametresi kullanılmadığı için Stripe ile çakışma yok.
        allow_promotion_codes=True,
    )

    # Resolve session_group_id from the appointment for session packages
    session_group_id = None
    if appointment_id:
        apt = await db.appointments.find_one({"id": appointment_id}, {"session_group_id": 1})
        if apt:
            session_group_id = apt.get("session_group_id")

    _pricing_snap = _build_pricing_snapshot(base_currency, tier, fee_preference, gross_up_result is not None)
    tx_doc = await create_transaction(
        db=db,
        organization_id=organization_id,
        base_currency=base_currency,
        tx_type="payment",
        amount_display_minor=merchant_net_minor,
        fee_amount_minor=platform_fee_minor,
        fee_rate_bps=fee_result.fee_rate_bps,
        fee_preference=fee_preference,
        appointment_id=appointment_id,
        customer_phone=customer_phone,
        stripe_checkout_session_id=stripe_session.id,
        customer_name=customer_name,
        session_group_id=session_group_id,
        # Business/Subscription ayrımı
        payment_type=PaymentType.BUSINESS.value,
        business_id=organization_id,
        payment_channel=PaymentChannel.APPOINTMENT.value,
        # PLANN v2 canonical fields
        customer_price_minor=customer_price_minor,
        merchant_net_minor=merchant_net_minor,
        platform_fee_minor=platform_fee_minor,
        stripe_fee_minor=processor_fee_minor,
        wise_fee_minor=payout_fee_minor,
        gross_up_applied=bool(gross_up_result is not None),
        service_price_minor=service_price_minor,
        # Komisyon snapshot (işlem anı — sonradan değişse de sabit)
        commission_tier=tier,
        commission_fixed_fee_minor=_pricing_snap["commission_fixed_fee_minor"],
        pricing_snapshot=_pricing_snap,
    )

    logger.info(
        "Checkout session created: org=%s session=%s customer_price=%d merchant_net=%d %s grossup=%s",
        organization_id, stripe_session.id, customer_price_minor,
        merchant_net_minor, base_currency,
        gross_up_result is not None,
    )

    return {
        "payment_required": True,
        "checkout_url": stripe_session.url,
        "session_id": stripe_session.id,
        "transaction_id": tx_doc["id"],
        # Legacy aliases (dual-write)
        "gross_minor": customer_price_minor,
        "net_minor": merchant_net_minor,
        "fee_minor": platform_fee_minor,
        # Canonical PLANN v2 fields
        "customer_price_minor": customer_price_minor,
        "merchant_net_minor": merchant_net_minor,
        "platform_fee_minor": platform_fee_minor,
        "stripe_fee_minor": processor_fee_minor,
        "wise_fee_minor": payout_fee_minor,
        "gross_up_applied": gross_up_result is not None,
        "base_currency": base_currency,
    }


def _resolve_service_price_minor(service: Dict[str, Any]) -> int:
    p = service.get("price_minor", 0)
    if not p and service.get("price"):
        p = int(round(service["price"] * 100))
    return p


def _compute_service_amounts(
    base_currency: str,
    tier: str,
    fee_preference: str,
    service: Dict[str, Any],
    session_count: int,
) -> Dict[str, Any]:
    """Tek bir hizmet için müşteri/merchant/komisyon tutarlarını hesaplar (Akıllı D toplamı için)."""
    service_price_minor = _resolve_service_price_minor(service)
    deposit_rule = _build_deposit_rule(service)

    gross_up_enabled = is_env_flag_enabled("FEATURE_GROSS_UP")
    gross_up_result = None
    if gross_up_enabled:
        try:
            gross_up_result = compute_customer_price(
                base_currency=base_currency,
                service_price_minor=service_price_minor,
                fee_preference=fee_preference,
                tier=tier,
                deposit_rule=deposit_rule,
            )
        except GrossUpError as ge:
            logger.error("multi gross-up failed, legacy fallback: %s", ge)
            gross_up_result = None

    fee_result = calculate_fee(
        base_currency=base_currency,
        service_price_minor=service_price_minor,
        fee_preference=fee_preference,
        tier=tier,
        deposit_rule=deposit_rule,
        session_count=session_count,
    )

    if gross_up_result is not None:
        return {
            "customer": gross_up_result.customer_price_minor,
            "net": gross_up_result.merchant_net_minor,
            "platform": gross_up_result.platform_fee_minor,
            "processor": gross_up_result.stripe_fee_minor,
            "payout": gross_up_result.wise_fee_minor,
            "service_price_minor": service_price_minor,
            "stripe_currency": fee_result.stripe_currency,
            "fee_rate_bps": fee_result.fee_rate_bps,
            "gross_up": True,
        }
    return {
        "customer": fee_result.gross_minor,
        "net": fee_result.net_minor,
        "platform": fee_result.fee_minor,
        "processor": 0,
        "payout": 0,
        "service_price_minor": service_price_minor,
        "stripe_currency": fee_result.stripe_currency,
        "fee_rate_bps": fee_result.fee_rate_bps,
        "gross_up": False,
    }


async def create_multi_service_checkout_session(
    db,
    organization_id: str,
    service_ids: list,
    appointment_id: str,
    customer_phone: str,
    customer_name: str = "",
) -> Dict[str, Any]:
    """Akıllı D: Çoklu hizmet için TEK line item'lı toplu kapora/ödeme Checkout Session.

    Her hizmetin müşteri tutarı ayrı ayrı hesaplanır, toplanır ve Stripe'a tek
    kalem ("Randevu Ödemesi (N Hizmet)") olarak gönderilir. service_ids ve
    service_names metadata'da saklanır (webhook + dashboard okunabilirliği).
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise ValueError(f"Settings not found for org: {organization_id}")

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    fee_preference = settings.get("fee_preference", "seller_pays")
    merchant_slug = settings.get("slug", "")
    company_name = settings.get("company_name", "İşletme")

    docs = await db.services.find(
        {"id": {"$in": service_ids}, "organization_id": organization_id}
    ).to_list(len(service_ids))
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in service_ids if sid in by_id]
    if len(ordered) != len(service_ids):
        raise ValueError("One or more services not found")

    total_customer = 0
    total_net = 0
    total_platform = 0
    total_processor = 0
    total_payout = 0
    total_service_price = 0
    stripe_currency = None
    fee_rate_bps = 0
    any_gross_up = False
    service_names = []
    for svc in ordered:
        amt = _compute_service_amounts(base_currency, tier, fee_preference, svc, 1)
        total_customer += amt["customer"]
        total_net += amt["net"]
        total_platform += amt["platform"]
        total_processor += amt["processor"]
        total_payout += amt["payout"]
        total_service_price += amt["service_price_minor"]
        stripe_currency = amt["stripe_currency"]
        fee_rate_bps = amt["fee_rate_bps"]
        any_gross_up = any_gross_up or amt["gross_up"]
        service_names.append(svc.get("name", "Hizmet"))

    if total_customer <= 0:
        return {
            "payment_required": False,
            "payment_rule": "on_site",
            "message": "Bu hizmetler için online ödeme gerekmez.",
        }

    custom_text_note = (
        "Platform hizmet bedeli iade kapsamı dışındadır. "
        "PLANNAPP LTD adına tahsil edilmektedir."
    ) if base_currency == "TRY" else (
        "Platform service fee is non-refundable. "
        "Collected on behalf of PLANNAPP LTD."
    )

    n = len(ordered)
    product_name = (
        f"Randevu Ödemesi ({n} Hizmet) - {company_name}"
        if base_currency == "TRY"
        else f"Appointment Payment ({n} services) - {company_name}"
    )
    product_data = {
        "name": product_name,
        "description": " + ".join(service_names)[:480],
    }
    logo = settings.get("logo_url") or ""
    if logo:
        product_data["images"] = [logo if logo.startswith("http") else f"https://plannapp.co{logo}"]
    else:
        product_data["images"] = ["https://plannapp.co/api/static/logo.png"]

    stripe_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": stripe_currency,
                "unit_amount": total_customer,
                "product_data": product_data,
            },
            "quantity": 1,
        }],
        custom_text={"submit": {"message": custom_text_note}},
        metadata={
            "organization_id": organization_id,
            "appointment_id": appointment_id,
            "service_id": service_ids[0],
            "service_ids": ",".join(service_ids),
            "service_names": ",".join(service_names)[:480],
            "customer_phone": customer_phone,
            "base_currency": base_currency,
            "fee_preference": fee_preference,
            "fee_minor": str(total_platform),
            "net_minor": str(total_net),
            "customer_price_minor": str(total_customer),
            "merchant_net_minor": str(total_net),
            "platform_fee_minor": str(total_platform),
            "stripe_fee_minor": str(total_processor),
            "wise_fee_minor": str(total_payout),
            "gross_up_applied": "true" if any_gross_up else "false",
            "session_count": "1",
            "payment_rule": "deposit",
            META_PAYMENT_TYPE: PaymentType.BUSINESS.value,
            META_BUSINESS_ID: organization_id,
            META_PAYMENT_CHANNEL: PaymentChannel.MULTI_SERVICE.value,
            META_IS_MERCHANT_PAYMENT: "true",
            "is_multi_service": "true",
        },
        success_url=f"https://plannapp.co/{merchant_slug}?payment=success&session_id={{CHECKOUT_SESSION_ID}}" if merchant_slug else PAYMENT_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=f"https://plannapp.co/{merchant_slug}?payment=cancelled" if merchant_slug else PAYMENT_CANCEL_URL,
        allow_promotion_codes=True,
    )

    session_group_id = None
    if appointment_id:
        apt = await db.appointments.find_one({"id": appointment_id}, {"session_group_id": 1})
        if apt:
            session_group_id = apt.get("session_group_id")

    _pricing_snap = _build_pricing_snapshot(base_currency, tier, fee_preference, any_gross_up)
    tx_doc = await create_transaction(
        db=db,
        organization_id=organization_id,
        base_currency=base_currency,
        tx_type="payment",
        amount_display_minor=total_net,
        fee_amount_minor=total_platform,
        fee_rate_bps=fee_rate_bps,
        fee_preference=fee_preference,
        appointment_id=appointment_id,
        customer_phone=customer_phone,
        stripe_checkout_session_id=stripe_session.id,
        customer_name=customer_name,
        session_group_id=session_group_id,
        payment_type=PaymentType.BUSINESS.value,
        business_id=organization_id,
        payment_channel=PaymentChannel.MULTI_SERVICE.value,
        customer_price_minor=total_customer,
        merchant_net_minor=total_net,
        platform_fee_minor=total_platform,
        stripe_fee_minor=total_processor,
        wise_fee_minor=total_payout,
        gross_up_applied=any_gross_up,
        service_price_minor=total_service_price,
        commission_tier=tier,
        commission_fixed_fee_minor=_pricing_snap["commission_fixed_fee_minor"],
        pricing_snapshot=_pricing_snap,
    )

    logger.info(
        "Multi-service checkout created: org=%s session=%s services=%d customer_price=%d",
        organization_id, stripe_session.id, n, total_customer,
    )

    return {
        "payment_required": True,
        "checkout_url": stripe_session.url,
        "session_id": stripe_session.id,
        "transaction_id": tx_doc["id"],
        "gross_minor": total_customer,
        "net_minor": total_net,
        "fee_minor": total_platform,
        "customer_price_minor": total_customer,
        "merchant_net_minor": total_net,
        "platform_fee_minor": total_platform,
        "stripe_fee_minor": total_processor,
        "wise_fee_minor": total_payout,
        "gross_up_applied": any_gross_up,
        "base_currency": base_currency,
    }


async def create_payment_link_session(
    db,
    organization_id: str,
    customer_name: str,
    customer_phone: str,
    description: str,
    base_amount_minor: int,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standalone "Pay-by-Link" (Ödeme İste) Stripe Checkout Session.

    Müşteriden bağımsız, tek seferlik tahsilat. Randevu/hizmet bağlantısı YOK.
    Girilen tutar `net_target` (online tutar) olarak kabul edilir — full online,
    kapora yok. Komisyon tercihi tenant `settings.fee_preference`'tan gelir ve
    tam gross-up (`compute_customer_price`) uygulanır.

    Webhook eşleşmesi mevcut `_handle_checkout_completed` tarafından
    `stripe_checkout_session_id` ile yapılır; `appointment_id` olmadığı için
    randevu güncelleme/bildirim bloğu otomatik atlanır.
    """
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise ValueError(f"Settings not found for organization: {organization_id}")

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    fee_preference = settings.get("fee_preference", "seller_pays")
    merchant_slug = settings.get("slug", "")
    company_name = settings.get("company_name", "İşletme")
    normalized_email = (customer_email or "").strip().lower() or None

    if base_amount_minor <= 0:
        raise ValueError(f"Amount must be positive: {base_amount_minor}")

    from .money import MIN_ONLINE_PAYMENT_MINOR, format_display
    min_online = MIN_ONLINE_PAYMENT_MINOR.get(base_currency, 30_000)
    if base_amount_minor < min_online:
        raise ValueError(f"Minimum tutar {format_display(min_online, base_currency)} olmalıdır")

    # Pay-by-Link her zaman full online (kapora yok). deposit_rule olmadan
    # gross-up/fee_calculator online tutarı 0 sayıp customer_price=0 üretir,
    # bu yüzden açıkça full_online kuralı geçilir.
    deposit_rule = DepositRule(payment_rule="full_online")

    # Tam gross-up (full online, kapora yok). Flag kapalıysa legacy fee_calculator.
    gross_up_enabled = is_env_flag_enabled("FEATURE_GROSS_UP")
    gross_up_result = None
    if gross_up_enabled:
        try:
            gross_up_result = compute_customer_price(
                base_currency=base_currency,
                service_price_minor=base_amount_minor,
                fee_preference=fee_preference,
                tier=tier,
                deposit_rule=deposit_rule,
            )
        except GrossUpError as ge:
            logger.error("payment-link gross-up failed, falling back to legacy: %s", ge)
            gross_up_result = None

    fee_result = calculate_fee(
        base_currency=base_currency,
        service_price_minor=base_amount_minor,
        fee_preference=fee_preference,
        tier=tier,
        deposit_rule=deposit_rule,
    )

    if gross_up_result is not None:
        customer_price_minor = gross_up_result.customer_price_minor
        merchant_net_minor = gross_up_result.merchant_net_minor
        platform_fee_minor = gross_up_result.platform_fee_minor
        processor_fee_minor = gross_up_result.stripe_fee_minor
        payout_fee_minor = gross_up_result.wise_fee_minor
    else:
        customer_price_minor = fee_result.gross_minor
        merchant_net_minor = fee_result.net_minor
        platform_fee_minor = fee_result.fee_minor
        processor_fee_minor = 0
        payout_fee_minor = 0

    if customer_price_minor <= 0:
        raise ValueError("Computed customer price is zero; cannot create payment link")

    # 1) Önce pending transaction oluştur — tx_id, Stripe client_reference_id için gerekli.
    _pricing_snap = _build_pricing_snapshot(base_currency, tier, fee_preference, gross_up_result is not None)
    tx_doc = await create_transaction(
        db=db,
        organization_id=organization_id,
        base_currency=base_currency,
        tx_type="payment",
        amount_display_minor=merchant_net_minor,
        fee_amount_minor=platform_fee_minor,
        fee_rate_bps=fee_result.fee_rate_bps,
        fee_preference=fee_preference,
        appointment_id=None,
        customer_phone=customer_phone,
        customer_name=customer_name,
        description=description,
        payment_type=PaymentType.BUSINESS.value,
        business_id=organization_id,
        payment_channel=PaymentChannel.PAYMENT_LINK.value,
        customer_price_minor=customer_price_minor,
        merchant_net_minor=merchant_net_minor,
        platform_fee_minor=platform_fee_minor,
        stripe_fee_minor=processor_fee_minor,
        wise_fee_minor=payout_fee_minor,
        gross_up_applied=bool(gross_up_result is not None),
        service_price_minor=base_amount_minor,
        commission_tier=tier,
        commission_fixed_fee_minor=_pricing_snap["commission_fixed_fee_minor"],
        pricing_snapshot=_pricing_snap,
    )
    tx_id = tx_doc["id"]

    custom_text_note = (
        "Platform hizmet bedeli iade kapsamı dışındadır. "
        "PLANNAPP LTD adına tahsil edilmektedir."
    ) if base_currency == "TRY" else (
        "Platform service fee is non-refundable. "
        "Collected on behalf of PLANNAPP LTD."
    )

    product_data = {
        "name": (description.strip()[:250] if description and description.strip() else f"Ödeme - {company_name}"),
        "description": f"{company_name} tarafından oluşturulan ödeme talebi",
    }
    logo = settings.get("logo_url") or ""
    if logo:
        product_data["images"] = [logo if logo.startswith("http") else f"https://plannapp.co{logo}"]
    else:
        product_data["images"] = ["https://plannapp.co/api/static/logo.png"]

    # Stripe Radar risk azaltma: işlemi 'guest' bırakmak yerine gerçek Customer'a
    # bağla (mükerrer önlenir). Hata durumunda None döner, tahsilat bloklanmaz.
    stripe_customer_id = await _get_or_create_stripe_customer(
        db,
        organization_id=organization_id,
        name=customer_name,
        phone=customer_phone,
        email=normalized_email,
    )

    session_kwargs: Dict[str, Any] = {
        "payment_method_types": ["card"],
        "mode": "payment",
        "client_reference_id": tx_id,
        "line_items": [{
            "price_data": {
                "currency": fee_result.stripe_currency,
                "unit_amount": customer_price_minor,
                "product_data": product_data,
            },
            "quantity": 1,
        }],
        "custom_text": {"submit": {"message": custom_text_note}},
        # 3DS zorunlu (yüksek tutarlı işlemlerde Radar risk skorunu düşürür).
        "payment_method_options": {"card": {"request_three_d_secure": "any"}},
        "metadata": {
            "organization_id": organization_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "customer_email": normalized_email or "",
            "description": description,
            "base_currency": base_currency,
            "fee_preference": fee_preference,
            # Legacy aliases (dual-write)
            "fee_minor": str(platform_fee_minor),
            "net_minor": str(merchant_net_minor),
            # Canonical PLANN v2 fields
            "customer_price_minor": str(customer_price_minor),
            "merchant_net_minor": str(merchant_net_minor),
            "platform_fee_minor": str(platform_fee_minor),
            "stripe_fee_minor": str(processor_fee_minor),
            "wise_fee_minor": str(payout_fee_minor),
            "gross_up_applied": "true" if gross_up_result is not None else "false",
            "payment_rule": "full_online",
            META_PAYMENT_TYPE: PaymentType.BUSINESS.value,
            META_BUSINESS_ID: organization_id,
            META_PAYMENT_CHANNEL: PaymentChannel.PAYMENT_LINK.value,
            META_IS_MERCHANT_PAYMENT: "true",
            "transaction_id": tx_id,
        },
        "success_url": (
            f"https://plannapp.co/{merchant_slug}?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
            if merchant_slug else PAYMENT_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}"
        ),
        "cancel_url": (
            f"https://plannapp.co/{merchant_slug}?payment=cancelled"
            if merchant_slug else PAYMENT_CANCEL_URL
        ),
        "allow_promotion_codes": True,
    }

    # Customer bağla. customer verildiğinde Stripe customer_email/customer_creation
    # kabul etmez; Customer oluşturulamadıysa fallback olarak email + creation kullan.
    if stripe_customer_id:
        session_kwargs["customer"] = stripe_customer_id
    else:
        session_kwargs["customer_creation"] = "always"
        if normalized_email:
            session_kwargs["customer_email"] = normalized_email

    stripe_session = stripe.checkout.Session.create(**session_kwargs)

    # 2) Session id'yi tx'e bağla — webhook eşleşmesi bunun üzerinden yapılır.
    await db.merchant_transactions.update_one(
        {"id": tx_id},
        {"$set": {"stripe_checkout_session_id": stripe_session.id}},
    )
    tx_doc["stripe_checkout_session_id"] = stripe_session.id
    # Mongo insert_one tx_doc'a ObjectId `_id` ekler — JSON serialize edilemez, çıkar.
    tx_doc.pop("_id", None)

    logger.info(
        "Payment link created: org=%s tx=%s session=%s customer_price=%d merchant_net=%d %s grossup=%s",
        organization_id, tx_id, stripe_session.id, customer_price_minor,
        merchant_net_minor, base_currency, gross_up_result is not None,
    )

    return {
        "checkout_url": stripe_session.url,
        "session_id": stripe_session.id,
        "transaction_id": tx_id,
        "customer_price_minor": customer_price_minor,
        "merchant_net_minor": merchant_net_minor,
        "platform_fee_minor": platform_fee_minor,
        "base_currency": base_currency,
        "transaction": tx_doc,
    }


# ---------------------------------------------------------------------------
# Webhook Processing
# ---------------------------------------------------------------------------

async def handle_stripe_merchant_webhook(
    db,
    payload: bytes,
    sig_header: str,
) -> Dict[str, Any]:
    """
    Process a Stripe webhook event for merchant payments.

    1. Verify signature
    2. Check idempotency (event_id in webhook_events)
    3. Route to handler by event type
    4. Update state machine
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_MERCHANT_WEBHOOK_SECRET,
        )
    except (stripe.error.SignatureVerificationError, ValueError) as e:
        logger.warning("Stripe webhook signature failed: %s", e)
        return {"status": "signature_failed"}

    event_id = event["id"]
    event_type = event["type"]
    # Parse data object from raw payload (Stripe objects aren't plain dicts)
    import json as _json
    raw_event = _json.loads(payload)
    data_object = raw_event.get("data", {}).get("object", {})

    body_sha256 = hashlib.sha256(payload).hexdigest()
    raw_headers_dict = {"stripe-signature": sig_header}

    existing = await db.webhook_events.find_one({"event_id": event_id})
    if existing and existing.get("processing_status") == "processed":
        logger.info("Duplicate webhook skipped: %s", event_id)
        return {"status": "skipped", "event_id": event_id}

    webhook_doc = WebhookEvent(
        source="stripe_merchant",
        event_id=event_id,
        event_type=event_type,
        payload=data_object,
        raw_body=payload.decode("utf-8", errors="replace"),
        raw_headers=raw_headers_dict,
        body_sha256=body_sha256,
        signature_verified=True,
        processing_status="processing",
    ).model_dump()

    if existing:
        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "processing_status": "processing",
                "attempt_count": existing.get("attempt_count", 0) + 1,
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    else:
        await db.webhook_events.insert_one(webhook_doc)

    try:
        result = await _route_event(db, event_type, data_object, event_id)

        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "processing_status": "processed",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "organization_id": result.get("organization_id"),
                "transaction_id": result.get("transaction_id"),
            }},
        )

        return {"status": "processed", "event_id": event_id, **result}

    except Exception as e:
        logger.exception("Webhook processing failed: event=%s type=%s", event_id, event_type)
        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "processing_status": "failed",
                "processing_error": str(e),
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return {"status": "failed", "event_id": event_id, "error": str(e)}


async def _route_event(
    db,
    event_type: str,
    data_object: Dict[str, Any],
    event_id: str,
) -> Dict[str, Any]:
    """Route webhook event to the appropriate handler."""
    sm = StateMachine(db)

    if event_type == "checkout.session.completed":
        return await _handle_checkout_completed(db, sm, data_object)

    elif event_type == "checkout.session.async_payment_succeeded":
        return await _handle_checkout_completed(db, sm, data_object)

    elif event_type == "checkout.session.async_payment_failed":
        return await _handle_async_payment_failed(db, sm, data_object)

    elif event_type == "payment_intent.succeeded":
        return await _handle_payment_intent_succeeded(db, sm, data_object)

    elif event_type == "charge.dispute.created":
        return await _handle_dispute_created(db, sm, data_object)

    elif event_type == "charge.dispute.funds_withdrawn":
        return await _handle_dispute_funds_withdrawn(db, sm, data_object)

    elif event_type == "charge.dispute.funds_reinstated":
        return await _handle_dispute_resolved(db, sm, data_object, won=True)

    elif event_type == "charge.dispute.closed":
        return await _handle_dispute_closed(db, sm, data_object)

    elif event_type == "checkout.session.expired":
        return await _handle_checkout_expired(db, sm, data_object)

    elif event_type == "charge.refunded":
        return await _handle_refund(db, sm, data_object)

    elif event_type == "payout.paid":
        # Payout içindeki balance txn'leri business/subscription olarak ayır + etiketle.
        from .payout_reconciliation import handle_payout_paid
        return await handle_payout_paid(db, data_object)

    elif event_type == "invoice.payment_failed":
        # SaaS abonelik dunning — merchant endpoint'ine de düşüyor (Stripe aynı hesabı paylaşıyor).
        from server import notify_saas_invoice_payment_failed
        sent = await notify_saas_invoice_payment_failed(db, data_object)
        return {"handled": True, "event_type": event_type, "grace_email_sent": sent}

    else:
        logger.info("Unhandled webhook event type: %s", event_type)
        return {"handled": False, "event_type": event_type}


# ---------------------------------------------------------------------------
# Post-payment notifications (WhatsApp + Push + WebSocket)
# ---------------------------------------------------------------------------

async def _send_post_payment_notifications(db, apt: Dict[str, Any], org_id: str):
    """Send notifications after payment is confirmed for a pending_payment appointment.

    PLANN v2 dispatch:
      payment_rule == "online"/"full_online" → CONFIRMATION_FULL_PAID  (with amount_paid)
      payment_rule == "deposit"              → CONFIRMATION_DEPOSIT    (with amount_paid + on_site_amount)
      else                                    → CONFIRMATION            (klasik)
    """
    try:
        settings = await db.settings.find_one({"organization_id": org_id})
        if not settings:
            return

        company_name = settings.get("company_name", "İşletme")
        support_phone = settings.get("support_phone", settings.get("phone", ""))
        location = settings.get("location") or {}
        coordinates = location.get("coordinates", {})
        lat = coordinates.get("lat")
        lng = coordinates.get("lng")
        address = location.get("address")
        customer_phone = apt.get("phone", "")
        customer_name = apt.get("customer_name", "")
        apt_date = apt.get("appointment_date", "")
        apt_time = apt.get("appointment_time", "")
        service_name = apt.get("service_name", "")
        staff_id = apt.get("staff_member_id")

        # ---- PLANN v2: payment_rule branching ----
        # 1) Service'ten payment_rule oku (apt'de payment_rule alanı yok)
        service_doc = await db.services.find_one(
            {"id": apt.get("service_id"), "organization_id": org_id}
        ) if apt.get("service_id") else None
        payment_rule = (service_doc or {}).get("payment_rule") or "on_site"

        # 2) Merchant transaction'tan ödenen tutar + para birimi
        tx = await db.merchant_transactions.find_one(
            {"appointment_id": apt.get("id"), "organization_id": org_id, "type": "payment"},
            sort=[("created_at", -1)],
        )
        currency = ((tx or {}).get("base_currency")
                    or settings.get("currency") or "TRY").upper()
        symbol = "₺" if currency == "TRY" else "£" if currency == "GBP" else f"{currency} "

        def _fmt_money(minor: int) -> str:
            try:
                whole = int(minor) / 100.0
                # 25 → "25", 25.5 → "25.50"
                if whole == int(whole):
                    return f"{symbol}{int(whole)}"
                return f"{symbol}{whole:.2f}"
            except Exception:
                return f"{symbol}-"

        customer_price_minor = int((tx or {}).get("customer_price_minor") or 0)
        amount_paid_display = _fmt_money(customer_price_minor) if customer_price_minor else None

        # 3) Branch
        wa_kwargs: Dict[str, Any] = {}
        if payment_rule in ("online", "full_online"):
            template_type = "CONFIRMATION_FULL_PAID"
            wa_kwargs["amount_paid_display"] = amount_paid_display or "-"
        elif payment_rule == "deposit":
            # On-site = full service price - deposit paid
            full_price_minor = int((tx or {}).get("service_price_minor") or 0)
            if not full_price_minor and service_doc:
                full_price_minor = int(round(float(service_doc.get("price") or 0) * 100))
            on_site_minor = max(0, full_price_minor - customer_price_minor)
            template_type = "CONFIRMATION_DEPOSIT"
            wa_kwargs["amount_paid_display"] = amount_paid_display or "-"
            wa_kwargs["on_site_amount_display"] = _fmt_money(on_site_minor)
        else:
            template_type = "CONFIRMATION"

        # WhatsApp
        try:
            from whatsapp_service import send_whatsapp_template
            await asyncio.to_thread(
                send_whatsapp_template,
                customer_phone, template_type, customer_name, company_name,
                apt_date, apt_time, service_name,
                support_phone or "Destek Hattı",
                business_lat=lat, business_lng=lng, business_address=address,
                **wa_kwargs,
            )
            logger.info(
                "Post-payment WhatsApp sent: template=%s payment_rule=%s amount=%s on_site=%s to=%s",
                template_type, payment_rule,
                wa_kwargs.get("amount_paid_display"),
                wa_kwargs.get("on_site_amount_display"),
                customer_phone,
            )
        except Exception as e:
            logger.warning("Post-payment WhatsApp failed: %s", e)

        # Push notifications
        try:
            from server import send_push_notification
            try:
                date_parts = apt_date.split("-")
                formatted_date = f"{date_parts[2]}.{date_parts[1]}.{date_parts[0]}"
            except Exception:
                formatted_date = apt_date
            body = f"{customer_name} - {service_name} ({formatted_date} {apt_time})"
            data = {"type": "new_appointment", "appointment_id": apt.get("id"), "source": "payment_confirmed"}

            admins = await db.users.find({"organization_id": org_id, "role": "admin"}).to_list(50)
            for admin in admins:
                await send_push_notification(db=db, organization_id=org_id, title="🔔 Yeni Online Randevu!", body=body, data=data, user_id=admin["username"])
            if staff_id:
                staff = await db.users.find_one({"username": staff_id, "organization_id": org_id})
                if staff and staff.get("role") != "admin":
                    await send_push_notification(db=db, organization_id=org_id, title="🔔 Yeni Randevu Atandı!", body=body, data=data, user_id=staff_id)
            logger.info("Post-payment push notifications sent for %s", apt.get("id"))
        except Exception as e:
            logger.warning("Post-payment push failed: %s", e)

        # WebSocket
        try:
            from server import emit_to_organization
            await emit_to_organization(org_id, "appointment_created", {"appointment": apt})
            logger.info("Post-payment WebSocket emitted for %s", apt.get("id"))
        except Exception as e:
            logger.warning("Post-payment WebSocket failed: %s", e)

        # Redis cache invalidation — admin dashboard & customers listesi tazelensin.
        # Public checkout tarafında Request objesi elde yok, doğrudan Redis'e vuruyoruz.
        try:
            from server import app as _srv_app
            _redis = getattr(_srv_app.state, "redis_client", None)
            if _redis and org_id:
                for _prefix in ("dashboard_stats", "customers_list"):
                    _key = f"plann:org_{org_id}:{_prefix}"
                    await _redis.delete(_key)
                    _wild = await _redis.keys(f"{_key}*")
                    if _wild:
                        await _redis.delete(*_wild)
        except Exception as _cache_err:
            logger.warning("Post-payment cache invalidation skipped: %s", _cache_err)

        # Denormalize sayaç güncellemesi — post-payment yeni randevu oluştu.
        try:
            from server import _apply_customer_delta as _delta_fn
            _is_completed = (apt.get("status") == "Tamamlandı")
            await _delta_fn(
                db,
                organization_id=org_id,
                phone=customer_phone or apt.get("phone") or "",
                name=customer_name or apt.get("customer_name"),
                delta_total=1,
                delta_completed=1 if _is_completed else 0,
                appointment_date=apt.get("appointment_date"),
                appointment_time=apt.get("appointment_time"),
            )
        except Exception as _delta_err:
            logger.warning("Post-payment customer delta skipped: %s", _delta_err)

    except Exception as e:
        logger.error("_send_post_payment_notifications error: %s", e)


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------

async def _handle_checkout_completed(
    db,
    sm: StateMachine,
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """checkout.session.completed / async_payment_succeeded → captured"""
    metadata = session.get("metadata", {})
    org_id = metadata.get("organization_id", "")
    checkout_session_id = session.get("id", "")

    tx = await db.merchant_transactions.find_one({
        "stripe_checkout_session_id": checkout_session_id,
    })
    if not tx:
        logger.warning("No transaction found for checkout session: %s", checkout_session_id)
        return {"handled": False}

    payment_intent_id = session.get("payment_intent", "")
    charge_id = ""
    settled_gbp_minor = 0
    balance_tx_id = ""
    actual_stripe_fee_minor = None
    gross_amount_minor = None
    available_on_iso = None

    if payment_intent_id:
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id, expand=["latest_charge"])
            # latest_charge: expand ile Charge nesnesi; expand yoksa str id.
            latest_charge = _sobj(pi, "latest_charge")
            if isinstance(latest_charge, str):
                charge_id = latest_charge
            elif latest_charge is not None:
                charge_id = _sobj(latest_charge, "id", "") or ""
                balance_tx_id = _sobj(latest_charge, "balance_transaction", "") or ""
                # balance_transaction bazen str id, bazen genişletilmiş nesne olabilir.
                if not isinstance(balance_tx_id, str):
                    balance_tx_id = _sobj(balance_tx_id, "id", "") or ""
            if balance_tx_id:
                bt = stripe.BalanceTransaction.retrieve(balance_tx_id)
                settled_gbp_minor = _sobj(bt, "net", 0) or 0
                # Gerçek Stripe maliyeti + brüt (yalnızca PLANN raporu; merchant_net'e etkisiz).
                actual_stripe_fee_minor = _sobj(bt, "fee", None)
                gross_amount_minor = _sobj(bt, "amount", None)
                # KRİTİK: Paranın Stripe bakiyesine ne zaman geçeceğinin KESİN tarihi.
                # Stripe bunu iş günü + resmi tatil hesabıyla verir → settlement
                # zamanlamasında statik T+2 yerine bunu kullanacağız (hafta sonu sapması yok).
                available_on_ts = _sobj(bt, "available_on", None)
                if available_on_ts:
                    available_on_iso = datetime.fromtimestamp(
                        int(available_on_ts), tz=timezone.utc
                    ).isoformat()
        except Exception as e:
            logger.warning("Failed to retrieve PI details: %s", e)

    # Payout reconciliation'ın charge/balance_transaction üzerinden eşleştirme
    # yapabilmesi için bu ID'leri tx'e yaz (business/subscription ayrımı).
    # NOT: balance_transaction her zaman SETTLE para biriminde (UK hesabı = GBP).
    # TRY merchant'ta müşteri TRY öder ama net/fee/gross GBP olur → GBP alanlarına yaz.
    # TRY estimate olan stripe_fee_minor'a DOKUNMA (para birimi karışmasın).
    transition_meta: Dict[str, Any] = {
        "stripe_payment_intent_id": payment_intent_id,
        "stripe_charge_id": charge_id,
        "amount_settled_gbp_minor": settled_gbp_minor,   # bt.net (GBP)
    }
    if balance_tx_id:
        transition_meta["stripe_balance_transaction_id"] = balance_tx_id
    if actual_stripe_fee_minor is not None:
        transition_meta["stripe_fee_gbp_minor"] = actual_stripe_fee_minor  # bt.fee (GBP)
    if gross_amount_minor is not None:
        transition_meta["gross_amount_gbp_minor"] = gross_amount_minor      # bt.amount (GBP)
    if available_on_iso:
        # Settlement cron bunu okuyup captured→settled'ı gerçek iş gününde yapar.
        transition_meta["stripe_available_on"] = available_on_iso

    wallet_inc = await sm.transition(
        tx_id=tx["id"],
        new_state="captured",
        trigger="checkout.session.completed",
        metadata=transition_meta,
    )

    if int(metadata.get("session_count", "1")) > 1:
        await _create_session_credits(db, tx, metadata)

    appointment_id = tx.get("appointment_id") or metadata.get("appointment_id")
    was_pending_payment = False
    if appointment_id:
        apt_update = {"payment_status": "paid"}
        apt = await db.appointments.find_one({"id": appointment_id})
        if apt and apt.get("status") == "Ödeme Bekleniyor":
            apt_update["status"] = "Bekliyor"
            was_pending_payment = True
        await db.appointments.update_one(
            {"id": appointment_id},
            {"$set": apt_update},
        )
        logger.info("Updated appointment %s payment_status=paid", appointment_id)

    if was_pending_payment and apt:
        await _send_post_payment_notifications(db, apt, org_id)

    return {
        "handled": True,
        "organization_id": org_id,
        "transaction_id": tx["id"],
        "new_state": "captured",
    }


async def _handle_async_payment_failed(
    db,
    sm: StateMachine,
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """checkout.session.async_payment_failed → async_failed"""
    checkout_session_id = session.get("id", "")
    tx = await db.merchant_transactions.find_one({
        "stripe_checkout_session_id": checkout_session_id,
    })
    if not tx:
        return {"handled": False}

    await sm.transition(
        tx_id=tx["id"],
        new_state="async_failed",
        trigger="checkout.session.async_payment_failed",
    )

    return {
        "handled": True,
        "organization_id": tx.get("organization_id"),
        "transaction_id": tx["id"],
        "new_state": "async_failed",
    }


async def _handle_checkout_expired(
    db,
    sm: StateMachine,
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """checkout.session.expired → cancel pending transaction and pending_payment appointment."""
    checkout_session_id = session.get("id", "")
    metadata = session.get("metadata", {})
    org_id = metadata.get("organization_id", "")

    tx = await db.merchant_transactions.find_one({
        "stripe_checkout_session_id": checkout_session_id,
    })

    if tx and tx.get("state") == "pending":
        await sm.transition(
            tx_id=tx["id"],
            new_state="canceled",
            trigger="checkout.session.expired",
        )
        logger.info("Expired checkout: cancelled transaction %s", tx["id"])

    appointment_id = (tx or {}).get("appointment_id") or metadata.get("appointment_id")
    if appointment_id:
        apt = await db.appointments.find_one({"id": appointment_id})
        if apt and apt.get("status") == "Ödeme Bekleniyor":
            await db.appointments.update_one(
                {"id": appointment_id},
                {"$set": {
                    "status": "İptal Edildi",
                    "payment_status": "expired",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.info("Expired checkout: cancelled appointment %s", appointment_id)

    return {
        "handled": True,
        "organization_id": org_id,
        "transaction_id": tx["id"] if tx else None,
        "new_state": "canceled",
    }


async def _handle_payment_intent_succeeded(
    db,
    sm: StateMachine,
    pi: Dict[str, Any],
) -> Dict[str, Any]:
    """payment_intent.succeeded — only acts if tx is still pending (backup for checkout)."""
    pi_id = pi.get("id", "")
    tx = await db.merchant_transactions.find_one({
        "stripe_payment_intent_id": pi_id,
    })
    if not tx:
        return {"handled": False, "reason": "no_tx_for_pi"}

    if tx["state"] != "pending":
        return {"handled": False, "reason": f"tx_already_{tx['state']}"}

    await sm.transition(
        tx_id=tx["id"],
        new_state="captured",
        trigger="payment_intent.succeeded",
    )

    return {
        "handled": True,
        "organization_id": tx["organization_id"],
        "transaction_id": tx["id"],
        "new_state": "captured",
    }


async def _handle_dispute_created(
    db,
    sm: StateMachine,
    dispute: Dict[str, Any],
) -> Dict[str, Any]:
    """charge.dispute.created → frozen"""
    charge_id = dispute.get("charge", "")
    tx = await db.merchant_transactions.find_one({"stripe_charge_id": charge_id})
    if not tx:
        return {"handled": False}

    if tx["state"] != "available":
        logger.warning("Dispute on tx %s in state %s (expected available)", tx["id"], tx["state"])
        return {"handled": False, "reason": f"tx_state_{tx['state']}"}

    await sm.transition(
        tx_id=tx["id"],
        new_state="frozen",
        trigger="charge.dispute.created",
        metadata={"stripe_dispute_id": dispute.get("id", "")},
    )

    return {
        "handled": True,
        "organization_id": tx["organization_id"],
        "transaction_id": tx["id"],
        "new_state": "frozen",
    }


async def _handle_dispute_funds_withdrawn(
    db,
    sm: StateMachine,
    dispute: Dict[str, Any],
) -> Dict[str, Any]:
    """charge.dispute.funds_withdrawn — logged as audit event, state already frozen."""
    charge_id = dispute.get("charge", "")
    tx = await db.merchant_transactions.find_one({"stripe_charge_id": charge_id})
    if not tx:
        return {"handled": False}

    await db.financial_audit_logs.insert_one({
        "organization_id": tx["organization_id"],
        "actor": "stripe",
        "actor_role": "system",
        "action": "dispute_funds_withdrawn",
        "details": {
            "dispute_id": dispute.get("id"),
            "charge_id": charge_id,
            "amount": dispute.get("amount"),
            "transaction_id": tx["id"],
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    if tx["state"] == "frozen":
        await sm.transition(
            tx_id=tx["id"],
            new_state="disputed",
            trigger="charge.dispute.funds_withdrawn",
        )

    return {
        "handled": True,
        "organization_id": tx["organization_id"],
        "transaction_id": tx["id"],
    }


async def _handle_dispute_resolved(
    db,
    sm: StateMachine,
    dispute: Dict[str, Any],
    won: bool = True,
) -> Dict[str, Any]:
    """charge.dispute.funds_reinstated → resolved_won"""
    charge_id = dispute.get("charge", "")
    tx = await db.merchant_transactions.find_one({"stripe_charge_id": charge_id})
    if not tx:
        return {"handled": False}

    new_state = "resolved_won" if won else "resolved_lost"

    if tx["state"] == "disputed":
        await sm.transition(
            tx_id=tx["id"],
            new_state=new_state,
            trigger="charge.dispute.funds_reinstated" if won else "charge.dispute.closed_lost",
        )

    return {
        "handled": True,
        "organization_id": tx["organization_id"],
        "transaction_id": tx["id"],
        "new_state": new_state,
    }


async def _handle_dispute_closed(
    db,
    sm: StateMachine,
    dispute: Dict[str, Any],
) -> Dict[str, Any]:
    """charge.dispute.closed — determine won/lost from dispute status."""
    status = dispute.get("status", "")
    won = status == "won"
    return await _handle_dispute_resolved(db, sm, dispute, won=won)


async def _handle_refund(
    db,
    sm: StateMachine,
    charge: Dict[str, Any],
) -> Dict[str, Any]:
    """charge.refunded → refunded"""
    charge_id = charge.get("id", "")
    tx = await db.merchant_transactions.find_one({"stripe_charge_id": charge_id})
    if not tx:
        return {"handled": False}

    if tx["state"] not in ("captured", "available"):
        return {"handled": False, "reason": f"cannot_refund_from_{tx['state']}"}

    refund_id = ""
    refunds = charge.get("refunds", {}).get("data", [])
    if refunds:
        refund_id = refunds[-1].get("id", "")

    await sm.transition(
        tx_id=tx["id"],
        new_state="refunded",
        trigger="charge.refunded",
        metadata={"stripe_refund_id": refund_id},
    )

    return {
        "handled": True,
        "organization_id": tx["organization_id"],
        "transaction_id": tx["id"],
        "new_state": "refunded",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_stripe_customer(
    db,
    organization_id: str,
    name: str,
    phone: str,
    email: Optional[str] = None,
) -> Optional[str]:
    """Pay-by-Link için Stripe Customer bul/oluştur (mükerrer önlenir).

    Radar risk skorunu düşürmek için işlemi 'guest' yerine gerçek bir Customer'a
    bağlar. Aynı organizasyon + telefon (veya email) için mevcut Customer yeniden
    kullanılır. Herhangi bir Stripe/DB hatasında None döner; çağıran taraf
    Customer olmadan (fallback) devam eder, tahsilat bloklanmaz.
    """
    normalized_phone = (phone or "").replace(" ", "").strip()
    normalized_email = (email or "").strip().lower() or None

    # 1) Mevcut Customer'ı yeniden kullan (mükerrer önleme)
    try:
        or_clauses: list = []
        if normalized_phone:
            or_clauses.append({"customer_phone": normalized_phone})
        if normalized_email:
            or_clauses.append({"customer_email": normalized_email})
        if or_clauses:
            existing = await db.stripe_customers.find_one({
                "organization_id": organization_id,
                "$or": or_clauses,
            })
            if existing and existing.get("stripe_customer_id"):
                return existing["stripe_customer_id"]
    except Exception as e:
        logger.warning("stripe_customers lookup failed (non-fatal): %s", e)

    # 2) Yeni Customer oluştur (boş alanları Stripe'a gönderme)
    create_kwargs: Dict[str, Any] = {
        "metadata": {"organization_id": organization_id, "source": "pay_by_link"},
    }
    if name and name.strip():
        create_kwargs["name"] = name.strip()
    if normalized_phone:
        create_kwargs["phone"] = normalized_phone
    if normalized_email:
        create_kwargs["email"] = normalized_email

    try:
        customer = stripe.Customer.create(**create_kwargs)
        cus_id = customer.get("id") if isinstance(customer, dict) else customer.id
    except Exception as e:
        logger.error("stripe.Customer.create failed (non-fatal): %s", e)
        return None

    if not cus_id:
        return None

    # 3) Yeniden kullanım için DB'ye kaydet
    try:
        await db.stripe_customers.insert_one({
            "stripe_customer_id": cus_id,
            "organization_id": organization_id,
            "customer_name": (name or "").strip(),
            "customer_phone": normalized_phone,
            "customer_email": normalized_email,
            "source": "pay_by_link",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning("stripe_customers insert failed (non-fatal): %s", e)

    return cus_id


def _build_deposit_rule(service: Dict[str, Any]) -> Optional[DepositRule]:
    payment_rule = service.get("payment_rule", "on_site")
    if payment_rule == "on_site":
        return DepositRule(payment_rule="on_site")
    if payment_rule in ("full_online", "online"):
        return DepositRule(payment_rule="full_online")
    if payment_rule == "deposit":
        deposit_amount = service.get("deposit_amount")
        if deposit_amount is not None:
            return DepositRule(
                payment_rule="deposit",
                deposit_type="fixed",
                deposit_value=int(round(deposit_amount * 100)),
            )
        dep_pct = service.get("deposit_percentage", 30)
        return DepositRule(
            payment_rule="deposit",
            deposit_type="percentage",
            deposit_value=dep_pct * 100,
        )
    return None


def _build_description(fee_result: FeeResult, service_name: str, session_count: int) -> str:
    parts = [service_name]
    if session_count > 1:
        parts.append(f"({session_count} seans paketi)")
    if fee_result.deposit_applied:
        parts.append("- Kapora")
    return " ".join(parts)


async def _create_session_credits(db, tx: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """Create session credits for multi-session package purchases."""
    from .schemas import SessionCredit

    session_count = int(metadata.get("session_count", "1"))
    credit = SessionCredit(
        organization_id=tx["organization_id"],
        customer_phone=tx.get("customer_phone", ""),
        service_id=metadata.get("service_id", ""),
        service_name=metadata.get("service_name", ""),
        total_sessions=session_count,
        remaining_sessions=session_count,
        payment_transaction_id=tx["id"],
        stripe_payment_intent_id=tx.get("stripe_payment_intent_id", ""),
    )

    await db.session_credits.insert_one(credit.model_dump())
    logger.info(
        "Session credits created: org=%s phone=%s sessions=%d",
        tx["organization_id"], tx.get("customer_phone"), session_count,
    )
