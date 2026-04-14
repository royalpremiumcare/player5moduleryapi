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

logger = logging.getLogger(__name__)

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

    fee_result = calculate_fee(
        base_currency=base_currency,
        service_price_minor=service_price_minor,
        fee_preference=fee_preference,
        tier=tier,
        deposit_rule=deposit_rule,
        session_count=session_count,
    )

    if fee_result.gross_minor == 0:
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
                "unit_amount": fee_result.gross_minor,
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
            "fee_minor": str(fee_result.fee_minor),
            "net_minor": str(fee_result.net_minor),
            "session_count": str(session_count),
            "payment_rule": deposit_rule.payment_rule if deposit_rule else "full_online",
        },
        success_url=f"https://plannapp.co/{merchant_slug}?payment=success&session_id={{CHECKOUT_SESSION_ID}}" if merchant_slug else PAYMENT_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=f"https://plannapp.co/{merchant_slug}?payment=cancelled" if merchant_slug else PAYMENT_CANCEL_URL,
    )

    # Resolve session_group_id from the appointment for session packages
    session_group_id = None
    if appointment_id:
        apt = await db.appointments.find_one({"id": appointment_id}, {"session_group_id": 1})
        if apt:
            session_group_id = apt.get("session_group_id")

    tx_doc = await create_transaction(
        db=db,
        organization_id=organization_id,
        base_currency=base_currency,
        tx_type="payment",
        amount_display_minor=fee_result.net_minor,
        fee_amount_minor=fee_result.fee_minor,
        fee_rate_bps=fee_result.fee_rate_bps,
        fee_preference=fee_preference,
        appointment_id=appointment_id,
        customer_phone=customer_phone,
        stripe_checkout_session_id=stripe_session.id,
        customer_name=customer_name,
        session_group_id=session_group_id,
    )

    logger.info(
        "Checkout session created: org=%s session=%s gross=%d %s",
        organization_id, stripe_session.id, fee_result.gross_minor, base_currency,
    )

    return {
        "payment_required": True,
        "checkout_url": stripe_session.url,
        "session_id": stripe_session.id,
        "transaction_id": tx_doc["id"],
        "gross_minor": fee_result.gross_minor,
        "net_minor": fee_result.net_minor,
        "fee_minor": fee_result.fee_minor,
        "base_currency": base_currency,
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

    else:
        logger.info("Unhandled webhook event type: %s", event_type)
        return {"handled": False, "event_type": event_type}


# ---------------------------------------------------------------------------
# Post-payment notifications (WhatsApp + Push + WebSocket)
# ---------------------------------------------------------------------------

async def _send_post_payment_notifications(db, apt: Dict[str, Any], org_id: str):
    """Send notifications after payment is confirmed for a pending_payment appointment."""
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

        # WhatsApp
        try:
            from whatsapp_service import send_whatsapp_template
            await asyncio.to_thread(
                send_whatsapp_template,
                customer_phone, "CONFIRMATION", customer_name, company_name,
                apt_date, apt_time, service_name,
                support_phone or "+44 7474 626 900",
                business_lat=lat, business_lng=lng, business_address=address,
            )
            logger.info("Post-payment WhatsApp sent to %s", customer_phone)
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

    if payment_intent_id:
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id, expand=["latest_charge"])
            charge_id = pi.get("latest_charge", {}).get("id", "") if isinstance(pi.get("latest_charge"), dict) else str(pi.get("latest_charge", ""))
            balance_tx_id = pi.get("latest_charge", {}).get("balance_transaction", "") if isinstance(pi.get("latest_charge"), dict) else ""
            if balance_tx_id:
                bt = stripe.BalanceTransaction.retrieve(balance_tx_id)
                settled_gbp_minor = bt.get("net", 0)
        except Exception as e:
            logger.warning("Failed to retrieve PI details: %s", e)

    wallet_inc = await sm.transition(
        tx_id=tx["id"],
        new_state="captured",
        trigger="checkout.session.completed",
        metadata={
            "stripe_payment_intent_id": payment_intent_id,
            "stripe_charge_id": charge_id,
            "amount_settled_gbp_minor": settled_gbp_minor,
        },
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
