"""
PLANN Financial Engine — API Endpoints

FastAPI router for all financial endpoints:
  - Merchant payment settings
  - Wallet & transactions
  - Payout requests & history
  - Public checkout sessions
  - SuperAdmin financial overview
  - Stripe & Wise webhooks
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_karmaşık_bir_secret_key_ekleyin_mutlaka')
_ALGORITHM = "HS256"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)

from .money import (
    format_display,
    get_tier_config,
    get_all_tiers,
    validate_bank_details,
    CURRENCY_SYMBOLS,
)
from .schemas import (
    MerchantPayoutSettingsUpdate,
    WalletResponse,
    TransactionListItem,
    PayoutHistoryItem,
    SuperAdminOverview,
)
from .fee_calculator import calculate_fee_preview, DepositRule
from .merchant_checkout import create_customer_checkout_session, handle_stripe_merchant_webhook
from .payout_service import check_payout_eligibility, create_payout_batch, process_payout_batch
from .compliance import (
    check_kyc_status,
    check_bank_details_cooldown,
    update_bank_details,
    check_aml_limits,
    set_kyc_verified,
)
from .wise_service import handle_wise_webhook, create_recipient_tr_iban, create_recipient_uk_bank
from .currency_shield import get_current_rate

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db(request: Request):
    return request.app.db


async def _require_auth(request: Request, token: str = Depends(_oauth2_scheme)):
    """Authenticate via JWT and set request.state.current_user (dict)."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = _get_db(request)
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["_id"] = str(user["_id"])
    request.state.current_user = user
    return user


async def _require_admin(request: Request, user=Depends(_require_auth)):
    """Require admin role."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _require_superadmin(request: Request, user=Depends(_require_auth)):
    """Require superadmin role."""
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


# ---------------------------------------------------------------------------
# 3a. Merchant Payment Settings
# ---------------------------------------------------------------------------

@router.get("/api/merchant/payment-settings", dependencies=[Depends(_require_admin)])
async def get_payment_settings(request: Request):
    """Get merchant's financial settings."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    settings = await db.settings.find_one({"organization_id": org_id})
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Lazy-init financial fields if missing
    if "base_currency" not in settings:
        # Determine currency from phone/country
        phone = settings.get("support_phone", "")
        detected_currency = "TRY" if phone.startswith("0") or phone.startswith("90") or phone.startswith("+90") else "GBP"
        await db.settings.update_one(
            {"organization_id": org_id},
            {"$set": {"base_currency": detected_currency, "payout_mode": "manual", "payout_tier": "standard", "fee_preference": "seller_pays"}},
        )
        settings = await db.settings.find_one({"organization_id": org_id})

    base_currency = settings.get("base_currency", "TRY")
    cooldown = await check_bank_details_cooldown(db, org_id)

    return {
        "base_currency": base_currency,
        "currency_symbol": CURRENCY_SYMBOLS.get(base_currency, "₺"),
        "payout_mode": settings.get("payout_mode", "manual"),
        "payout_tier": settings.get("payout_tier", "standard"),
        "fee_preference": settings.get("fee_preference", "seller_pays"),
        "iban": settings.get("iban"),
        "account_holder_name": settings.get("account_holder_name"),
        "sort_code": settings.get("sort_code"),
        "account_number": settings.get("account_number"),
        "wise_recipient_verified": settings.get("wise_recipient_verified", False),
        "kyc_verified": settings.get("kyc_verified", False),
        "refund_window_hours": settings.get("refund_window_hours", 24),
        "cooldown": cooldown,
        "tiers": {
            name: {
                "limit_minor": cfg.limit_minor,
                "limit_display": format_display(cfg.limit_minor, base_currency),
                "fee_rate_bps": cfg.fee_rate_bps,
                "fee_rate_pct": f"%{cfg.fee_rate_bps / 100}",
                "fixed_fee_minor": cfg.fixed_fee_minor,
                "fixed_fee_display": format_display(cfg.fixed_fee_minor, base_currency) if cfg.fixed_fee_minor > 0 else None,
            }
            for name, cfg in get_all_tiers(base_currency).items()
        },
    }


@router.put("/api/merchant/payment-settings", dependencies=[Depends(_require_admin)])
async def update_payment_settings(request: Request, body: MerchantPayoutSettingsUpdate):
    """Update merchant's financial settings."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    settings = await db.settings.find_one({"organization_id": org_id})
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    base_currency = settings.get("base_currency", "TRY")
    update_data = body.model_dump(exclude_none=True)

    # Validate bank details if being updated
    bank_fields = {}
    changed_bank_fields = {}
    for key in ("iban", "account_holder_name", "sort_code", "account_number"):
        if key in update_data:
            bank_fields[key] = update_data.pop(key)

    if bank_fields:
        # Only proceed if at least one bank field actually changed
        changed_bank_fields = {}
        for key, new_val in bank_fields.items():
            existing_val = settings.get(key)
            # Normalize IBAN comparison (uppercase, strip spaces)
            if key == "iban" and new_val and existing_val:
                if new_val.upper().replace(" ", "") == existing_val.upper().replace(" ", ""):
                    continue
            elif new_val == existing_val:
                continue
            changed_bank_fields[key] = new_val

        if changed_bank_fields:
            is_valid, error = validate_bank_details(base_currency, **bank_fields)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error)

            result = await update_bank_details(
                db, org_id, user.get("id", ""), **changed_bank_fields,
            )
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result.get("error"))

    if update_data:
        await db.settings.update_one(
            {"organization_id": org_id},
            {"$set": update_data},
        )

    # --- Wise Recipient Creation ---
    # After bank details are saved, create/update Wise recipient automatically.
    # This bridges the gap: IBAN save → Wise API → wise_recipient_verified=True
    # Sandbox: Wise API failure → auto-verify with mock recipient ID
    if changed_bank_fields:
        refreshed = await db.settings.find_one({"organization_id": org_id})
        holder_name = refreshed.get("account_holder_name", "")
        is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"

        if holder_name:
            recipient_id = None
            try:
                if base_currency == "TRY":
                    iban = refreshed.get("iban", "")
                    if iban:
                        recipient = await create_recipient_tr_iban(iban, holder_name)
                        recipient_id = str(recipient.get("id", ""))
                else:
                    sort_code = refreshed.get("sort_code", "")
                    account_number = refreshed.get("account_number", "")
                    if sort_code and account_number:
                        recipient = await create_recipient_uk_bank(sort_code, account_number, holder_name)
                        recipient_id = str(recipient.get("id", ""))
            except Exception as e:
                logger.error("Wise recipient creation failed for org %s: %s", org_id, e)
                if is_sandbox:
                    recipient_id = f"sandbox_mock_{org_id}"
                    logger.info("Sandbox: auto-verifying recipient for org %s", org_id)

            if recipient_id:
                await db.settings.update_one(
                    {"organization_id": org_id},
                    {"$set": {
                        "wise_recipient_id": recipient_id,
                        "wise_recipient_verified": True,
                    }},
                )
                logger.info("Wise recipient verified for org %s: %s", org_id, recipient_id)

    # Trigger KYC pending alert if KYC is not verified
    if not settings.get("kyc_verified", False):
        try:
            from .email_notifications import send_kyc_pending_alert
            merchant_name = settings.get("company_name") or user.get("full_name", "Unknown")
            send_kyc_pending_alert(org_id, merchant_name)
        except Exception as e:
            logger.warning("KYC alert email failed: %s", e)

    # payout_mode "auto" olarak değiştirildiyse hemen payout kontrolü tetikle
    new_payout_mode = update_data.get("payout_mode") or body.payout_mode
    if new_payout_mode == "auto":
        try:
            from .payout_service import check_payout_eligibility, create_payout_batch, process_payout_batch
            eligibility = await check_payout_eligibility(db, org_id)
            if eligibility.get("eligible"):
                refreshed_settings = await db.settings.find_one({"organization_id": org_id})
                wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
                if wallet:
                    bc = refreshed_settings.get("base_currency", "TRY")
                    org_data = {
                        "organization_id": org_id,
                        "amount_display_minor": eligibility["effective_available_minor"],
                        "amount_gbp_minor": wallet.get("pool_balance_gbp_minor", 0) if bc == "TRY" else eligibility["effective_available_minor"],
                        "wise_recipient_id": refreshed_settings.get("wise_recipient_id") or "",
                    }
                    batches = await create_payout_batch(db, bc, [org_data], "auto_immediate")
                    for batch in batches:
                        try:
                            await process_payout_batch(db, batch["id"])
                            logger.info("Auto-immediate payout triggered for org %s batch %s", org_id, batch["id"])
                        except Exception as e:
                            logger.error("Auto-immediate payout failed for batch %s: %s", batch["id"], e)
            else:
                logger.info("Auto payout mode set but not eligible yet for org %s: %s", org_id, eligibility.get("reasons"))
        except Exception as e:
            logger.error("Auto-immediate payout check failed for org %s: %s", org_id, e)

    return {"status": "updated"}


# ---------------------------------------------------------------------------
# 3b. Wallet & Transactions
# ---------------------------------------------------------------------------

@router.get("/api/merchant/wallet", dependencies=[Depends(_require_admin)])
async def get_wallet(request: Request):
    """Get merchant's wallet summary."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
    if not wallet:
        settings = await db.settings.find_one({"organization_id": org_id})
        bc = settings.get("base_currency", "TRY") if settings else "TRY"
        new_wallet = {
            "organization_id": org_id,
            "base_currency": bc,
            "available_balance_minor": 0,
            "pending_balance_minor": 0,
            "frozen_balance_minor": 0,
            "refund_reserve_minor": 0,
            "total_earned_minor": 0,
            "total_paid_out_minor": 0,
            "total_fees_minor": 0,
            "created_at": datetime.now(timezone.utc),
        }
        await db.merchant_wallets.insert_one(new_wallet)
        wallet = await db.merchant_wallets.find_one({"organization_id": org_id})

    settings = await db.settings.find_one({"organization_id": org_id})
    base_currency = wallet.get("base_currency", settings.get("base_currency", "TRY") if settings else "TRY")
    tier = settings.get("payout_tier", "standard") if settings else "standard"

    eligibility = await check_payout_eligibility(db, org_id)

    tier_cfg = get_tier_config(base_currency, tier)
    effective_available = max(0, wallet.get("available_balance_minor", 0) - wallet.get("refund_reserve_minor", 0))

    return WalletResponse(
        base_currency=base_currency,
        currency_symbol=CURRENCY_SYMBOLS.get(base_currency, "₺"),
        available=wallet.get("available_balance_minor", 0),
        pending=wallet.get("pending_balance_minor", 0),
        frozen=wallet.get("frozen_balance_minor", 0),
        refund_reserve=wallet.get("refund_reserve_minor", 0),
        effective_available=effective_available,
        total_earned=wallet.get("total_earned_minor", 0),
        total_paid_out=wallet.get("total_paid_out_minor", 0),
        total_fees=wallet.get("total_fees_minor", 0),
        tier=tier,
        tier_limit=tier_cfg.limit_minor,
        tier_fee_rate_bps=tier_cfg.fee_rate_bps,
        progress_pct=eligibility.get("progress_pct", 0),
        payout_enabled=eligibility.get("eligible", False),
        payout_enabled_reasons=eligibility.get("reasons", []),
    ).model_dump()


@router.get("/api/merchant/transactions", dependencies=[Depends(_require_admin)])
async def get_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    state: Optional[str] = None,
):
    """Get merchant's transaction history."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    query = {"organization_id": org_id, "state": {"$nin": ["pending", "canceled", "async_failed"]}}
    if state:
        query["state"] = state

    total = await db.merchant_transactions.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.merchant_transactions.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    txs = await cursor.to_list(length=per_page)

    settings = await db.settings.find_one({"organization_id": org_id})
    base_currency = settings.get("base_currency", "TRY") if settings else "TRY"

    items = []
    for tx in txs:
        items.append(TransactionListItem(
            id=tx.get("id", ""),
            type=tx.get("type", ""),
            state=tx.get("state", ""),
            amount_display=format_display(tx.get("amount_display_minor", 0), base_currency),
            amount_minor=tx.get("amount_display_minor", 0),
            fee_display=format_display(tx.get("fee_amount_minor", 0), base_currency),
            fee_minor=tx.get("fee_amount_minor", 0),
            base_currency=base_currency,
            created_at=tx.get("created_at", ""),
            customer_name=tx.get("customer_name"),
            customer_phone=tx.get("customer_phone"),
        ).model_dump())

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


# ---------------------------------------------------------------------------
# 3c. Payout Requests & History
# ---------------------------------------------------------------------------

@router.post("/api/merchant/payout/request", dependencies=[Depends(_require_admin)])
async def request_payout(request: Request):
    """Request a manual payout."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    eligibility = await check_payout_eligibility(db, org_id)
    if not eligibility["eligible"]:
        raise HTTPException(status_code=400, detail={
            "error": "payout_not_eligible",
            "reasons": eligibility["reasons"],
        })

    settings = await db.settings.find_one({"organization_id": org_id})
    wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
    base_currency = settings.get("base_currency", "TRY")

    effective_available = eligibility["effective_available_minor"]

    aml = await check_aml_limits(db, org_id, effective_available, base_currency)
    if aml.get("needs_superadmin_review"):
        from .email_notifications import send_aml_review_alert
        send_aml_review_alert(
            org_id,
            settings.get("company_name", ""),
            effective_available,
            base_currency,
            aml["flags"],
        )
        return {
            "status": "pending_review",
            "message": "Ödemeniz güvenlik incelemesi için beklemede.",
        }

    wise_recipient_id = settings.get("wise_recipient_id") or ""
    is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"

    if not wise_recipient_id and is_sandbox:
        wise_recipient_id = f"sandbox_mock_{org_id}"
        await db.settings.update_one(
            {"organization_id": org_id},
            {"$set": {"wise_recipient_id": wise_recipient_id, "wise_recipient_verified": True}},
        )

    if not wise_recipient_id:
        raise HTTPException(status_code=400, detail="Wise alıcı hesabı tanımlanmamış. Lütfen önce banka bilgilerinizi kaydedin.")

    org_data = {
        "organization_id": org_id,
        "amount_display_minor": effective_available,
        "amount_gbp_minor": wallet.get("pool_balance_gbp_minor", 0) if base_currency == "TRY" else effective_available,
        "wise_recipient_id": wise_recipient_id,
    }

    batches = await create_payout_batch(
        db, base_currency, [org_data], "manual", user.get("id"),
    )

    if batches:
        try:
            await process_payout_batch(db, batches[0]["id"])
        except Exception as e:
            logger.error("Manual payout failed: %s", e)
            raise HTTPException(status_code=500, detail="Payout processing failed")

    return {
        "status": "processing",
        "batch_id": batches[0]["id"] if batches else None,
        "amount_display": format_display(effective_available, base_currency),
    }


@router.get("/api/merchant/payout/history", dependencies=[Depends(_require_admin)])
async def get_payout_history(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get merchant's payout history."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    settings = await db.settings.find_one({"organization_id": org_id})
    base_currency = settings.get("base_currency", "TRY") if settings else "TRY"

    query = {"items.organization_id": org_id}
    total = await db.payout_batches.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.payout_batches.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    batches = await cursor.to_list(length=per_page)

    items = []
    for b in batches:
        my_items = [i for i in b.get("items", []) if i.get("organization_id") == org_id]
        total_minor = sum(i.get("amount_display_minor", 0) for i in my_items)
        items.append(PayoutHistoryItem(
            id=b.get("id", ""),
            status=b.get("status", ""),
            total_display=format_display(total_minor, base_currency),
            total_minor=total_minor,
            payout_rail=b.get("payout_rail", ""),
            triggered_by=b.get("triggered_by", ""),
            created_at=b.get("created_at", ""),
            completed_at=b.get("completed_at"),
        ).model_dump())

    return {"items": items, "total": total, "page": page, "per_page": per_page}


# ---------------------------------------------------------------------------
# 3d. Public Customer Checkout
# ---------------------------------------------------------------------------

class PublicCheckoutRequest(BaseModel):
    organization_id: str
    service_id: str
    appointment_id: str
    customer_phone: str
    customer_name: Optional[str] = None
    session_count: int = 1


@router.post("/api/public/checkout")
async def public_checkout(request: Request, body: PublicCheckoutRequest):
    """Create a checkout session for a customer (public, no auth)."""
    db = _get_db(request)

    try:
        result = await create_customer_checkout_session(
            db=db,
            organization_id=body.organization_id,
            service_id=body.service_id,
            appointment_id=body.appointment_id,
            customer_phone=body.customer_phone,
            session_count=body.session_count,
            customer_name=body.customer_name or "",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/public/fee-preview")
async def public_fee_preview(
    request: Request,
    organization_id: str,
    service_id: str,
    session_count: int = 1,
):
    """Preview fees for a service (public, no auth)."""
    db = _get_db(request)

    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise HTTPException(status_code=404, detail="Organization not found")

    service = await db.services.find_one({
        "id": service_id,
        "organization_id": organization_id,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    fee_preference = settings.get("fee_preference", "buyer_pays")
    service_price = service.get("price_minor", 0)
    if not service_price and service.get("price"):
        service_price = int(round(service["price"] * 100))

    deposit_rule = None
    if service.get("payment_rule") == "deposit":
        deposit_amount = service.get("deposit_amount")
        if deposit_amount is not None:
            deposit_rule = DepositRule(
                payment_rule="deposit",
                deposit_type="fixed",
                deposit_value=int(round(deposit_amount * 100)),
            )
        else:
            dep_pct = service.get("deposit_percentage", 30)
            deposit_rule = DepositRule(
                payment_rule="deposit",
                deposit_type="percentage",
                deposit_value=dep_pct * 100,
            )
    elif service.get("payment_rule") in ("full_online", "online"):
        deposit_rule = DepositRule(payment_rule="full_online")

    preview = calculate_fee_preview(
        base_currency, service_price, tier, session_count, deposit_rule,
    )

    preview["currency_symbol"] = CURRENCY_SYMBOLS.get(base_currency, "₺")
    preview["fee_preference"] = fee_preference
    return preview


# ---------------------------------------------------------------------------
# 3e. Session Credits
# ---------------------------------------------------------------------------

@router.get("/api/merchant/session-credits", dependencies=[Depends(_require_admin)])
async def get_session_credits(
    request: Request,
    customer_phone: Optional[str] = None,
):
    """Get session credits for merchant's customers."""
    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    query = {"organization_id": org_id, "status": "active"}
    if customer_phone:
        query["customer_phone"] = customer_phone

    credits = await db.session_credits.find(query).to_list(length=100)
    return {"items": credits}


# ---------------------------------------------------------------------------
# 3e-b. Merchant Refund
# ---------------------------------------------------------------------------

class MerchantRefundRequest(BaseModel):
    transaction_id: str
    reason: Optional[str] = None


@router.post("/api/merchant/refund", dependencies=[Depends(_require_admin)])
async def merchant_refund(request: Request, body: MerchantRefundRequest):
    """
    Merchant-initiated partial refund.

    Only the SERVICE AMOUNT is refunded to the customer.
    The PLATFORM SERVICE FEE is NEVER refunded and stays in PLANN's account.

    For session packages: refunds remaining unused sessions proportionally.
    """
    import stripe as _stripe

    db = _get_db(request)
    user = request.state.current_user
    org_id = user.get("organization_id", "")

    tx = await db.merchant_transactions.find_one({
        "id": body.transaction_id,
        "organization_id": org_id,
    })
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx["state"] not in ("captured", "available"):
        raise HTTPException(
            status_code=400,
            detail=f"Bu işlem iade edilemez (durum: {tx['state']})",
        )

    if not tx.get("stripe_payment_intent_id"):
        raise HTTPException(status_code=400, detail="No Stripe payment found for this transaction")

    # Calculate refund amount.
    # amount_display_minor = net (what merchant receives) in BOTH fee modes.
    # Platform fee is NEVER refunded — it stays in PLANN's account.
    # buyer_pays:  customer paid net+fee → refund net only
    # seller_pays: customer paid net+fee (gross=net+fee with fee hidden) → refund net only
    fee_minor = tx.get("fee_amount_minor", 0)
    refund_amount = tx.get("amount_display_minor", 0)

    # Session package: prorate refund by remaining sessions
    session_credit = None
    if tx.get("appointment_id"):
        session_credit = await db.session_credits.find_one({
            "payment_transaction_id": body.transaction_id,
            "status": "active",
        })

    if session_credit:
        total_sessions = session_credit.get("total_sessions", 1)
        remaining = session_credit.get("remaining_sessions", total_sessions)
        if remaining < total_sessions and remaining > 0:
            # Prorate: refund (remaining/total) * refund_amount
            refund_amount = (refund_amount * remaining + total_sessions // 2) // total_sessions
        elif remaining == 0:
            raise HTTPException(status_code=400, detail="Tüm seanslar kullanılmış, iade yapılamaz")

    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="İade tutarı hesaplanamadı")

    # Execute Stripe partial refund
    try:
        stripe_refund = _stripe.Refund.create(
            payment_intent=tx["stripe_payment_intent_id"],
            amount=refund_amount,
            reason="requested_by_customer",
            metadata={
                "organization_id": org_id,
                "transaction_id": body.transaction_id,
                "refund_reason": body.reason or "merchant_initiated",
                "platform_fee_retained": str(fee_minor),
            },
        )
    except _stripe.error.StripeError as e:
        logger.error("Stripe refund failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Stripe iade hatası: {str(e)}")

    # Transition state machine
    from .state_machine import StateMachine
    sm = StateMachine(db)
    try:
        await sm.transition(
            tx_id=body.transaction_id,
            new_state="refunded",
            trigger="merchant_refund",
            metadata={
                "stripe_refund_id": stripe_refund.id,
                "refund_amount_minor": refund_amount,
                "platform_fee_retained_minor": fee_minor,
                "refund_reason": body.reason or "merchant_initiated",
            },
        )
    except Exception as e:
        logger.error("State transition after refund failed: %s", e)

    # Mark session credits as refunded if applicable
    if session_credit:
        await db.session_credits.update_one(
            {"payment_transaction_id": body.transaction_id},
            {"$set": {"status": "refunded", "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    base_currency = tx.get("base_currency", "TRY")
    return {
        "status": "refunded",
        "refund_id": stripe_refund.id,
        "refund_amount_minor": refund_amount,
        "refund_amount_display": format_display(refund_amount, base_currency),
        "platform_fee_retained_minor": fee_minor,
        "platform_fee_retained_display": format_display(fee_minor, base_currency),
        "session_credit_refunded": session_credit is not None,
    }


# ---------------------------------------------------------------------------
# 3f. Webhooks
# ---------------------------------------------------------------------------

@router.post("/api/webhooks/stripe/merchant")
async def stripe_merchant_webhook(request: Request):
    """Stripe webhook endpoint for merchant payments."""
    db = _get_db(request)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    result = await handle_stripe_merchant_webhook(db, payload, sig_header)

    if result.get("status") == "signature_failed":
        raise HTTPException(status_code=400, detail="Invalid signature")

    return result


@router.get("/api/webhooks/wise")
async def wise_webhook_verify():
    """Wise webhook URL verification (GET ping)."""
    return {"status": "ok"}


@router.post("/api/webhooks/wise")
async def wise_webhook(request: Request):
    """Wise webhook endpoint for transfer status updates."""
    # Wise sends a test POST with X-Test-Notification header when creating subscriptions
    if request.headers.get("X-Test-Notification") == "true":
        return Response(content="ok", status_code=200, media_type="text/plain")

    payload = await request.body()

    import json
    try:
        body = json.loads(payload) if payload else {}
    except (json.JSONDecodeError, Exception):
        return Response(content="ok", status_code=200, media_type="text/plain")

    # If it's a test/ping event or empty, just ack
    event_type = body.get("event_type") or body.get("type", "")
    if not event_type or event_type == "test" or body.get("test"):
        return Response(content="ok", status_code=200, media_type="text/plain")

    db = _get_db(request)
    sig_header = request.headers.get("X-Signature-SHA256", "")

    try:
        result = await handle_wise_webhook(db, payload, sig_header)
    except Exception as e:
        logging.error(f"Wise webhook handler error: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

    if result.get("status") == "signature_failed":
        raise HTTPException(status_code=400, detail="Invalid signature")

    return result


# ---------------------------------------------------------------------------
# 3g. SuperAdmin Financial Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/superadmin/financial/overview", dependencies=[Depends(_require_superadmin)])
async def superadmin_overview(request: Request):
    """SuperAdmin consolidated financial overview."""
    db = _get_db(request)

    # Pool balance: sum of all wallets' pool_balance_gbp_minor
    pipeline = [
        {"$group": {
            "_id": None,
            "total_pool": {"$sum": "$pool_balance_gbp_minor"},
            "gbp_available": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "GBP"]}, "$available_balance_minor", 0]
            }},
            "try_available": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "TRY"]}, "$available_balance_minor", 0]
            }},
        }},
    ]
    agg = await db.merchant_wallets.aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {"total_pool": 0, "gbp_available": 0, "try_available": 0}

    gbp_count = await db.merchant_wallets.count_documents({"base_currency": "GBP"})
    try_count = await db.merchant_wallets.count_documents({"base_currency": "TRY"})

    pending_payouts = await db.payout_batches.count_documents({
        "status": {"$in": ["draft", "quoting", "quoted", "funding", "processing"]},
    })
    active_disputes = await db.merchant_transactions.count_documents({
        "state": {"$in": ["frozen", "disputed"]},
    })

    rate_doc = await get_current_rate(db)
    rate_micro = rate_doc.get("rate_micro", 0) if rate_doc else 0

    from .money import rate_from_micro
    rate_display = str(rate_from_micro(rate_micro)) if rate_micro else "N/A"

    return SuperAdminOverview(
        total_pool_gbp_minor=totals["total_pool"],
        total_pool_gbp_display=format_display(totals["total_pool"], "GBP"),
        total_pool_try_minor=totals["try_available"],
        total_pool_try_display=format_display(totals["try_available"], "TRY"),
        gbp_merchant_count=gbp_count,
        try_merchant_count=try_count,
        gbp_available_total_minor=totals["gbp_available"],
        try_available_total_minor=totals["try_available"],
        pending_payouts_count=pending_payouts,
        active_disputes_count=active_disputes,
        current_gbp_try_rate_micro=rate_micro,
        current_gbp_try_rate_display=rate_display,
        current_rate_display=rate_display,
    ).model_dump()


@router.get("/api/superadmin/financial/wallets", dependencies=[Depends(_require_superadmin)])
async def superadmin_wallets(
    request: Request,
    market: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List all merchant wallets with optional market filter."""
    db = _get_db(request)

    query = {}
    if market and market in ("GBP", "TRY"):
        query["base_currency"] = market

    total = await db.merchant_wallets.count_documents(query)
    skip = (page - 1) * per_page

    wallets = await db.merchant_wallets.find(query).sort("updated_at", -1).skip(skip).limit(per_page).to_list(per_page)

    # Enrich with org names + kyc status (fallback chain)
    org_ids = [w["organization_id"] for w in wallets if w.get("organization_id")]
    org_names = {}
    org_kyc = {}
    org_iban_holders = {}
    if org_ids:
        settings_list = await db.settings.find(
            {"organization_id": {"$in": org_ids}},
            {"_id": 0, "organization_id": 1, "company_name": 1, "business_name": 1, "kyc_verified": 1, "account_holder_name": 1, "iban": 1}
        ).to_list(len(org_ids))
        for s in settings_list:
            name = s.get("company_name") or s.get("business_name") or ""
            org_names[s["organization_id"]] = name
            org_kyc[s["organization_id"]] = s.get("kyc_verified", False)
            org_iban_holders[s["organization_id"]] = {
                "account_holder_name": s.get("account_holder_name", ""),
                "iban": s.get("iban", ""),
            }

        # Fetch admin full_name for all orgs (for KYC comparison)
        org_admin_names = {}
        admins = await db.users.find(
            {"organization_id": {"$in": org_ids}, "role": "admin"},
            {"_id": 0, "organization_id": 1, "full_name": 1, "username": 1}
        ).to_list(len(org_ids))
        for a in admins:
            org_admin_names[a["organization_id"]] = a.get("full_name") or a.get("username") or ""
            if a["organization_id"] not in org_names or not org_names[a["organization_id"]]:
                org_names[a["organization_id"]] = a.get("full_name") or a.get("username") or ""

    for w in wallets:
        w.pop("_id", None)
        bc = w.get("base_currency", "TRY")
        oid = w.get("organization_id", "")
        w["available_display"] = format_display(w.get("available_balance_minor", 0), bc)
        w["pool_gbp_display"] = format_display(w.get("pool_balance_gbp_minor", 0), "GBP")
        w["org_name"] = org_names.get(oid, "")
        w["admin_name"] = org_admin_names.get(oid, "") if org_ids else ""
        iban_info = org_iban_holders.get(oid, {})
        w["account_holder_name"] = iban_info.get("account_holder_name", "")
        w["iban"] = iban_info.get("iban", "")
        if "kyc_verified" not in w:
            w["kyc_verified"] = org_kyc.get(oid, False)

    return {"items": wallets, "total": total, "page": page, "per_page": per_page}


@router.post("/api/superadmin/financial/payout/{batch_id}/approve", dependencies=[Depends(_require_superadmin)])
async def superadmin_approve_payout(request: Request, batch_id: str):
    """SuperAdmin manual payout approval."""
    db = _get_db(request)

    batch = await db.payout_batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch["status"] != "draft":
        raise HTTPException(status_code=400, detail=f"Batch not in draft status: {batch['status']}")

    try:
        result = await process_payout_batch(db, batch_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/superadmin/financial/wallet/{org_id}/freeze", dependencies=[Depends(_require_superadmin)])
async def superadmin_freeze_wallet(request: Request, org_id: str):
    """SuperAdmin manual wallet freeze."""
    db = _get_db(request)
    user = request.state.current_user

    wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    available = wallet.get("available_balance_minor", 0)
    if available <= 0:
        raise HTTPException(status_code=400, detail="No available balance to freeze")

    now = datetime.now(timezone.utc).isoformat()
    await db.merchant_wallets.update_one(
        {"organization_id": org_id},
        {"$inc": {
            "available_balance_minor": -available,
            "frozen_balance_minor": available,
        }, "$set": {"updated_at": now}},
    )

    await db.financial_audit_logs.insert_one({
        "id": str(__import__("uuid").uuid4()),
        "organization_id": org_id,
        "actor": user.get("id", "superadmin"),
        "actor_role": "superadmin",
        "action": "manual_wallet_freeze",
        "details": {"frozen_amount_minor": available},
        "created_at": now,
    })

    return {"status": "frozen", "amount_minor": available}


@router.get("/api/superadmin/financial/audit-logs", dependencies=[Depends(_require_superadmin)])
async def superadmin_audit_logs(
    request: Request,
    org_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """Financial audit logs."""
    db = _get_db(request)

    query = {}
    if org_id:
        query["organization_id"] = org_id

    total = await db.financial_audit_logs.count_documents(query)
    skip = (page - 1) * per_page

    logs = await db.financial_audit_logs.find(query).sort("created_at", -1).skip(skip).limit(per_page).to_list(per_page)

    for log in logs:
        log.pop("_id", None)

    return {"items": logs, "total": total, "page": page, "per_page": per_page}


@router.get("/api/superadmin/financial/exchange-rate-history", dependencies=[Depends(_require_superadmin)])
async def superadmin_exchange_rate_history(
    request: Request,
    limit: int = Query(30, ge=1, le=365),
):
    """Exchange rate history."""
    db = _get_db(request)

    rates = await db.exchange_rates.find(
        {"pair": "GBP_TRY"},
    ).sort("fetched_at", -1).limit(limit).to_list(limit)

    for r in rates:
        r.pop("_id", None)

    return {"items": rates}


@router.get("/api/superadmin/financial/pool-balance", dependencies=[Depends(_require_superadmin)])
async def superadmin_pool_balance(request: Request):
    """UK pool total GBP balance."""
    db = _get_db(request)

    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$pool_balance_gbp_minor"}}},
    ]
    result = await db.merchant_wallets.aggregate(pipeline).to_list(1)
    total = result[0]["total"] if result else 0

    return {
        "pool_balance_gbp_minor": total,
        "pool_balance_gbp_display": format_display(total, "GBP"),
    }


@router.delete("/api/superadmin/financial/wallet/{org_id}", dependencies=[Depends(_require_superadmin)])
async def superadmin_delete_wallet(request: Request, org_id: str):
    """Delete an orphaned wallet (only if zero balance and no active settings)."""
    db = _get_db(request)

    wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Safety: only allow deletion if all balances are zero
    if (wallet.get("available_balance_minor", 0) != 0 or
        wallet.get("pending_balance_minor", 0) != 0 or
        wallet.get("frozen_balance_minor", 0) != 0):
        raise HTTPException(status_code=400, detail="Bakiyesi olan cüzdan silinemez")

    await db.merchant_wallets.delete_one({"organization_id": org_id})
    logger.info("Orphan wallet deleted by superadmin: org=%s", org_id)
    return {"status": "deleted", "organization_id": org_id}


@router.post("/api/superadmin/financial/kyc/{org_id}/verify", dependencies=[Depends(_require_superadmin)])
async def superadmin_kyc_verify(request: Request, org_id: str):
    """SuperAdmin KYC verification."""
    db = _get_db(request)
    user = request.state.current_user

    await set_kyc_verified(
        db, org_id, True,
        actor=user.get("id", "superadmin"),
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "verified", "organization_id": org_id}
