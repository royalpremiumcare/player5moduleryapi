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
import re
import logging
import requests
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
from .feature_flags import is_env_flag_enabled
from .gross_up_service import compute_customer_price as _gross_up_compute, GrossUpError
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
from .currency_shield import get_current_rate, ensure_fresh_exchange_rate

logger = logging.getLogger(__name__)

def _requests_http_status(exc: BaseException) -> Optional[int]:
    """requests HTTPError bazen response taşımaz; metinden 403 vb. çıkar."""
    r = getattr(exc, "response", None)
    if r is not None:
        code = getattr(r, "status_code", None)
        if code is not None:
            try:
                return int(code)
            except (TypeError, ValueError):
                pass
    m = re.match(r"^(\d{3})\s", str(exc))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


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

    # NOTE: Immediate "auto-payout on settings save" removed — all payouts now
    # run exclusively on the Wednesday weekly batch cron. Changing payout_mode
    # no longer triggers an instant payout.

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

    cursor = db.merchant_transactions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page)
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
        except requests.exceptions.HTTPError as e:
            wise_body = ""
            if e.response is not None:
                wise_body = (e.response.text or "")[:1500]
            http_st = _requests_http_status(e)
            logger.error(
                "Manual payout Wise HTTPError: %s body=%s",
                e,
                wise_body,
                exc_info=True,
            )
            # 502 kullanma: CDN (Cloudflare) bazen JSON yerine genel "Bad gateway" HTML sayfası gösterir.
            hint = None
            if http_st == 403 or ("forbidden" in (wise_body or "").lower()):
                hint = (
                    "TRY çekimi teknik olarak GBP kaynağından ödenir (quote GBP→TRY). "
                    "Wise Business çoklu para bakiyesinde bu işlem için yeterli GBP olmalı; "
                    "GBP yoksa veya yetmezse fund adımı genelde 403/forbidden döner. "
                    "Ayrıca API token’ın bakiyeden ödeme izni ve WISE_PROFILE_ID eşleşmesi gerekir. "
                    "Test için WISE_ENVIRONMENT=sandbox kullanılabilir."
                )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "wise_api_error",
                    "message": (
                        "Wise ödemeyi başlatamadı. En sık neden: Wise hesabında yeterli GBP bakiyesi olmaması "
                        "(TRY çekimi GBP’den düşülür). Diğer nedenler: API token izinleri veya profil uyumsuzluğu."
                    ),
                    "http_status": http_st,
                    "wise_response": wise_body or None,
                    "hint": hint,
                },
            )
        except Exception as e:
            logger.error("Manual payout failed: %s", e, exc_info=True)
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

    # Destekle: (1) legacy batch'ler (items[].organization_id) + (2) v2 batch'ler (tek-org, items yok)
    query = {
        "$or": [
            {"items.organization_id": org_id},
            {"organization_id": org_id},
        ]
    }
    total = await db.payout_batches.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.payout_batches.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(per_page)
    batches = await cursor.to_list(length=per_page)

    items = []
    for b in batches:
        if b.get("items"):
            my_items = [i for i in b.get("items", []) if i.get("organization_id") == org_id]
            total_minor = sum(i.get("amount_display_minor", 0) for i in my_items)
        else:
            # v2 single-org batch
            total_minor = int(b.get("total_amount_minor") or 0)

        items.append(PayoutHistoryItem(
            id=b.get("id", ""),
            status=b.get("status", ""),
            total_display=format_display(total_minor, base_currency),
            total_minor=total_minor,
            payout_rail=b.get("payout_rail", "wise"),
            triggered_by=b.get("triggered_by", "auto"),
            created_at=b.get("created_at", ""),
            completed_at=b.get("completed_at") or b.get("funded_at"),
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

    # PLANN v2 — Gross-up override: replace seller_pays / buyer_pays with full
    # processor + payout + platform fee gross-up so public UI matches checkout.
    if is_env_flag_enabled("FEATURE_GROSS_UP"):
        try:
            gu_seller = _gross_up_compute(
                base_currency=base_currency,
                service_price_minor=service_price,
                fee_preference="seller_pays",
                tier=tier,
                deposit_rule=deposit_rule,
            )
            gu_buyer = _gross_up_compute(
                base_currency=base_currency,
                service_price_minor=service_price,
                fee_preference="buyer_pays",
                tier=tier,
                deposit_rule=deposit_rule,
            )
            # Total embedded fee = customer_pays - merchant_net (single line for UI)
            preview["seller_pays"] = {
                "customer_pays": gu_seller.customer_price_minor,
                "merchant_receives": gu_seller.merchant_net_minor,
                "platform_fee": gu_seller.customer_price_minor - gu_seller.merchant_net_minor,
            }
            preview["buyer_pays"] = {
                "customer_pays": gu_buyer.customer_price_minor,
                "merchant_receives": gu_buyer.merchant_net_minor,
                "platform_fee": gu_buyer.customer_price_minor - gu_buyer.merchant_net_minor,
            }
            preview["deposit_applied"] = gu_buyer.deposit_applied
            preview["deposit_minor"] = gu_buyer.deposit_minor
            preview["gross_up_applied"] = True
        except GrossUpError as e:
            logger.warning("fee-preview gross-up failed, falling back to legacy: %s", e)
            preview["gross_up_applied"] = False
        except Exception as e:
            logger.error("fee-preview gross-up unexpected error: %s", e, exc_info=True)
            preview["gross_up_applied"] = False
    else:
        preview["gross_up_applied"] = False

    preview["fee_preference"] = fee_preference
    preview["currency_symbol"] = CURRENCY_SYMBOLS.get(base_currency, "₺")
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

    credits = await db.session_credits.find(query, {"_id": 0}).to_list(length=100)
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

    # Pool balance + pending/earned/refunded breakdowns per currency
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
            "gbp_pending": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "GBP"]}, {"$ifNull": ["$pending_balance_minor", 0]}, 0]
            }},
            "try_pending": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "TRY"]}, {"$ifNull": ["$pending_balance_minor", 0]}, 0]
            }},
            "gbp_earned": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "GBP"]}, {"$ifNull": ["$total_earned_minor", 0]}, 0]
            }},
            "try_earned": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "TRY"]}, {"$ifNull": ["$total_earned_minor", 0]}, 0]
            }},
            "gbp_refunded": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "GBP"]}, {"$ifNull": ["$total_refunded_minor", 0]}, 0]
            }},
            "try_refunded": {"$sum": {
                "$cond": [{"$eq": ["$base_currency", "TRY"]}, {"$ifNull": ["$total_refunded_minor", 0]}, 0]
            }},
        }},
    ]
    agg = await db.merchant_wallets.aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {
        "total_pool": 0, "gbp_available": 0, "try_available": 0,
        "gbp_pending": 0, "try_pending": 0,
        "gbp_earned": 0, "try_earned": 0,
        "gbp_refunded": 0, "try_refunded": 0,
    }

    gbp_count = await db.merchant_wallets.count_documents({"base_currency": "GBP"})
    try_count = await db.merchant_wallets.count_documents({"base_currency": "TRY"})

    pending_payouts = await db.payout_batches.count_documents({
        "status": {"$in": ["draft", "quoting", "quoted", "funding", "processing"]},
    })
    active_disputes = await db.merchant_transactions.count_documents({
        "state": {"$in": ["frozen", "disputed"]},
    })

    rate_doc = await ensure_fresh_exchange_rate(db, max_age_seconds=300)
    rate_micro = rate_doc.get("rate_micro", 0) if rate_doc else 0

    from .money import rate_from_micro
    rate_display = str(rate_from_micro(rate_micro)) if rate_micro else "N/A"

    payload = SuperAdminOverview(
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

    # Extended pending/earned/refunded breakdown (not in schema — passthrough)
    payload.update({
        "gbp_pending_total_minor":   totals["gbp_pending"],
        "gbp_pending_total_display": format_display(totals["gbp_pending"], "GBP"),
        "try_pending_total_minor":   totals["try_pending"],
        "try_pending_total_display": format_display(totals["try_pending"], "TRY"),
        "gbp_earned_total_minor":    totals["gbp_earned"],
        "gbp_earned_total_display":  format_display(totals["gbp_earned"], "GBP"),
        "try_earned_total_minor":    totals["try_earned"],
        "try_earned_total_display":  format_display(totals["try_earned"], "TRY"),
        "gbp_refunded_total_minor":  totals["gbp_refunded"],
        "gbp_refunded_total_display": format_display(totals["gbp_refunded"], "GBP"),
        "try_refunded_total_minor":  totals["try_refunded"],
        "try_refunded_total_display": format_display(totals["try_refunded"], "TRY"),
    })
    return payload


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


@router.post(
    "/api/superadmin/financial/refunds/reconciliation/{reconciliation_id}/resolve",
    dependencies=[Depends(_require_superadmin)],
)
async def superadmin_resolve_refund_reconciliation(request: Request, reconciliation_id: str):
    """Stripe iade sonrası iç kayıt kuyruğundaki tek kaydı kilitleyip yeniden dener (mutabakat)."""
    db = _get_db(request)
    user = request.state.current_user
    username = user.get("username", "superadmin")
    from financial.refund_reconciliation_service import resolve_refund_reconciliation_by_id

    result = await resolve_refund_reconciliation_by_id(
        db,
        reconciliation_id,
        locked_by=f"superadmin:{username}",
        request=request,
    )
    if result.get("ok"):
        return result
    hs = result.get("http_status")
    if hs == 404:
        raise HTTPException(status_code=404, detail=result)
    if hs == 409:
        raise HTTPException(status_code=409, detail=result.get("error", "lock_not_acquired"))
    if hs == 400:
        raise HTTPException(status_code=400, detail=result)
    return result


# ---------------------------------------------------------------------------
# 3h. PLANN v2 — Refund Requests
# ---------------------------------------------------------------------------

from . import refund_requests as refund_req_mod
from . import wednesday_batch as wb_mod
from . import dead_letter_queue as dlq_mod
from . import feature_flags as ff_mod
from .audit_service import write_audit

# Multi-layer rate limit (opt-in via FEATURE_MULTI_LAYER_RATE_LIMIT)
try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from multi_layer_rate_limit import enforce_multi_layer, get_profile as get_rl_profile
    _RL_AVAILABLE = True
except Exception as _rl_err:
    logger.warning("multi_layer_rate_limit not importable: %s", _rl_err)
    _RL_AVAILABLE = False

    async def enforce_multi_layer(*args, **kwargs):  # type: ignore[misc]
        return

    def get_rl_profile(name):  # type: ignore[misc]
        return {}


def _redis_for_request(request: Request):
    return getattr(request.app.state, "redis_client", None)


class RefundRequestCreate(BaseModel):
    merchant_transaction_id: str
    refund_amount_minor: int
    reason: str
    appointment_ids: Optional[List[str]] = None
    priority: str = "normal"
    customer_waiting: bool = False
    note: str = ""
    idempotency_key: Optional[str] = None


@router.post("/api/merchant/refund-requests", dependencies=[Depends(_require_admin)])
async def create_merchant_refund_request(request: Request, body: RefundRequestCreate, user=Depends(_require_auth)):
    """Merchant creates a refund request (requires SuperAdmin approval)."""
    db = _get_db(request)
    org_id = user.get("org_id") or user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id missing")

    # Kill-switch: SuperAdmin panelinden devre dışı bırakılabilir (arıza durumunda)
    if not await ff_mod.is_feature_enabled(db, "refund_requests_ui", organization_id=org_id, default=True):
        raise HTTPException(
            status_code=503,
            detail="İade talepleri şu anda kapalı. Lütfen daha sonra tekrar deneyin.",
        )

    # Multi-layer rate limit: 5/hour per account
    await enforce_multi_layer(
        request, _redis_for_request(request),
        limits=get_rl_profile("refund_request"),
        context={"account": user.get("sub") or org_id},
    )

    try:
        doc = await refund_req_mod.create_refund_request(
            db,
            organization_id=org_id,
            requested_by_user_id=user.get("sub", ""),
            merchant_transaction_id=body.merchant_transaction_id,
            refund_amount_minor=body.refund_amount_minor,
            reason=body.reason,
            appointment_ids=body.appointment_ids,
            priority=body.priority,
            customer_waiting=body.customer_waiting,
            note=body.note,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await write_audit(
            db, organization_id=org_id, actor=user.get("sub", ""),
            actor_role=user.get("role", "admin"),
            action="refund_request_created",
            details={"request_id": doc["id"], "amount_minor": body.refund_amount_minor},
            target_entity_type="refund_request", target_entity_id=doc["id"],
        )
    except Exception:
        pass
    return doc


@router.get("/api/merchant/refund-requests", dependencies=[Depends(_require_admin)])
async def list_merchant_refund_requests(
    request: Request, user=Depends(_require_auth),
    status: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
):
    db = _get_db(request)
    org_id = user.get("org_id") or user.get("organization_id")
    items = await refund_req_mod.list_org_refund_requests(db, org_id, status=status, limit=limit)
    return {"items": items}


@router.get("/api/merchant/customers/search", dependencies=[Depends(_require_admin)])
async def merchant_search_payments(
    request: Request, user=Depends(_require_auth),
    q: str = Query("", max_length=100),
    by: str = Query("name"),
    limit: int = Query(30, ge=1, le=100),
):
    db = _get_db(request)
    org_id = user.get("org_id") or user.get("organization_id")
    if by not in ("name", "phone", "amount", "date"):
        raise HTTPException(status_code=400, detail="invalid by param")

    # Multi-layer rate limit: IP 30/min, account 200/hour
    await enforce_multi_layer(
        request, _redis_for_request(request),
        limits=get_rl_profile("customer_search"),
        context={"account": user.get("sub") or org_id},
    )

    items = await refund_req_mod.search_customer_payments(
        db, organization_id=org_id, query=q, by=by, limit=limit,
    )
    return {"items": items}


# SuperAdmin refund_requests
@router.get("/api/superadmin/refund-requests", dependencies=[Depends(_require_superadmin)])
async def sa_list_refund_requests(request: Request, limit: int = Query(100, ge=1, le=500)):
    """Pending refund requests (awaiting SuperAdmin decision)."""
    db = _get_db(request)
    items = await refund_req_mod.list_pending_for_admin(db, limit=limit)
    return {"items": items}


@router.get(
    "/api/superadmin/refund-requests/history",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_list_refund_history(
    request: Request,
    status: Optional[str] = Query(None, regex="^(executed|rejected|failed)$"),
    limit: int = Query(100, ge=1, le=500),
):
    """Completed refund requests (executed / rejected / failed) for history panel."""
    db = _get_db(request)
    items = await refund_req_mod.list_completed_for_admin(db, status=status, limit=limit)
    return {"items": items}


class RefundRequestDecision(BaseModel):
    reason: Optional[str] = None


@router.post(
    "/api/superadmin/refund-requests/{request_id}/approve",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_approve_refund_request(
    request: Request, request_id: str, user=Depends(_require_auth),
):
    db = _get_db(request)
    # Inject stripe refund caller
    import stripe

    def _stripe_refund(pi_id, amount):
        if not pi_id:
            raise RuntimeError("no stripe_payment_intent_id on request")
        return stripe.Refund.create(payment_intent=pi_id, amount=int(amount))

    result = await refund_req_mod.approve_refund_request(
        db, request_id=request_id, reviewer_id=user.get("sub", "superadmin"),
        stripe_refund_call=_stripe_refund,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    try:
        req_doc = await db.refund_requests.find_one({"id": request_id})
        await write_audit(
            db, organization_id=(req_doc or {}).get("organization_id", ""),
            actor=user.get("sub", ""), actor_role="superadmin",
            action="refund_request_approved",
            details={"request_id": request_id, "stripe_refund_id": result.get("stripe_refund_id")},
            target_entity_type="refund_request", target_entity_id=request_id,
        )
    except Exception:
        pass
    return result


@router.post(
    "/api/superadmin/refund-requests/{request_id}/reject",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reject_refund_request(
    request: Request, request_id: str, body: RefundRequestDecision, user=Depends(_require_auth),
):
    db = _get_db(request)
    result = await refund_req_mod.reject_refund_request(
        db, request_id=request_id, reviewer_id=user.get("sub", "superadmin"),
        reason=body.reason or "",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    try:
        req_doc = await db.refund_requests.find_one({"id": request_id})
        await write_audit(
            db, organization_id=(req_doc or {}).get("organization_id", ""),
            actor=user.get("sub", ""), actor_role="superadmin",
            action="refund_request_rejected",
            details={"request_id": request_id, "reason": body.reason},
            target_entity_type="refund_request", target_entity_id=request_id,
        )
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# 3i. PLANN v2 — Wallet Status (merchant-facing)
# ---------------------------------------------------------------------------

@router.get("/api/merchant/wallet/status", dependencies=[Depends(_require_admin)])
async def get_wallet_status_v2(request: Request, user=Depends(_require_auth)):
    db = _get_db(request)
    org_id = user.get("org_id") or user.get("organization_id")
    return await wb_mod.compute_wallet_status(db, org_id)


@router.get("/api/merchant/features", dependencies=[Depends(_require_admin)])
async def get_merchant_features(request: Request, user=Depends(_require_auth)):
    """Merchant-facing feature flag durumu (UI gating icin)."""
    db = _get_db(request)
    org_id = user.get("org_id") or user.get("organization_id")
    return {
        "refund_requests_ui": await ff_mod.is_feature_enabled(
            db, "refund_requests_ui", organization_id=org_id, default=True,
        ),
    }


# ---------------------------------------------------------------------------
# 3j. PLANN v2 — Wednesday Batch (SuperAdmin)
# ---------------------------------------------------------------------------

@router.get(
    "/api/superadmin/financial/batches/awaiting",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_list_batches_awaiting(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    include_failed: bool = Query(False),
    include_completed: bool = Query(False),
):
    db = _get_db(request)
    items = await wb_mod.list_batches_awaiting_admin(
        db, limit=limit, include_failed=include_failed,
        include_completed=include_completed,
    )
    return {"items": items}


@router.post(
    "/api/superadmin/financial/batches/{batch_id}/prepare-wise",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_prepare_batch_wise(request: Request, batch_id: str, user=Depends(_require_auth)):
    db = _get_db(request)

    async def _wise_prepare(batch):
        # Delegate to wise_service — create quote + transfer (not fund)
        try:
            from .wise_service import prepare_batch_group
            return await prepare_batch_group(db, batch)
        except Exception as e:
            # Fallback: raise so caller handles DLQ
            raise RuntimeError(f"wise_prepare: {e}")

    result = await wb_mod.prepare_batch_for_wise(
        db, batch_id=batch_id, admin_id=user.get("sub", "superadmin"),
        wise_prepare_fn=_wise_prepare,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    try:
        batch = await db.payout_batches.find_one({"id": batch_id})
        await write_audit(
            db, organization_id=(batch or {}).get("organization_id", ""),
            actor=user.get("sub", ""), actor_role="superadmin",
            action="batch_wise_prepared",
            details={"batch_id": batch_id, "wise_quote_id": result.get("wise_quote_id")},
            target_entity_type="payout_batch", target_entity_id=batch_id,
        )
    except Exception:
        pass
    return result


class BulkPrepareBody(BaseModel):
    batch_ids: Optional[List[str]] = None  # null = all awaiting batches


@router.post(
    "/api/superadmin/financial/batches/bulk-prepare-wise",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_bulk_prepare_batches_wise(
    request: Request, body: BulkPrepareBody = BulkPrepareBody(), user=Depends(_require_auth),
):
    """Prepare all (or selected) awaiting_admin_fund batches as a SINGLE Wise
    batch group, so the Wise panel shows one consolidated "N GBP Transfer batch"
    entry the admin can fund in one click.
    """
    db = _get_db(request)

    async def _unified_wise_prepare(batches):
        try:
            from .wise_service import prepare_unified_batch_group
            return await prepare_unified_batch_group(db, batches)
        except Exception as e:
            raise RuntimeError(f"unified_wise_prepare: {e}")

    result = await wb_mod.bulk_prepare_batches_for_wise(
        db, batch_ids=body.batch_ids,
        admin_id=user.get("sub", "superadmin"),
        unified_prepare_fn=_unified_wise_prepare,
    )
    try:
        await write_audit(
            db, organization_id="",
            actor=user.get("sub", ""), actor_role="superadmin",
            action="batch_bulk_prepare",
            details={
                "processed": result.get("processed"),
                "success": result.get("success"),
                "failed": result.get("failed"),
            },
            target_entity_type="payout_batch",
            target_entity_id=",".join(body.batch_ids or [])[:200] or "all_awaiting",
        )
    except Exception:
        pass
    return result


class BatchFundConfirm(BaseModel):
    note: str = ""


@router.post(
    "/api/superadmin/financial/batches/{batch_id}/confirm-fund",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_confirm_batch_fund(
    request: Request, batch_id: str, body: BatchFundConfirm, user=Depends(_require_auth),
):
    db = _get_db(request)
    result = await wb_mod.confirm_manual_fund(
        db, batch_id=batch_id, admin_id=user.get("sub", "superadmin"), note=body.note,
    )
    try:
        batch = await db.payout_batches.find_one({"id": batch_id})
        await write_audit(
            db, organization_id=(batch or {}).get("organization_id", ""),
            actor=user.get("sub", ""), actor_role="superadmin",
            action="batch_funded",
            details={"batch_id": batch_id, "note": body.note, "result": result},
            target_entity_type="payout_batch", target_entity_id=batch_id,
        )
    except Exception:
        pass
    return result


class BulkFundConfirm(BaseModel):
    batch_ids: Optional[List[str]] = None  # null = all wise_fund_pending
    note: str = ""


@router.post(
    "/api/superadmin/financial/batches/bulk-confirm-fund",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_bulk_confirm_batches_fund(
    request: Request, body: BulkFundConfirm = BulkFundConfirm(), user=Depends(_require_auth),
):
    """Confirm manual fund for every wise_fund_pending batch (or selected) in one call."""
    db = _get_db(request)
    result = await wb_mod.bulk_confirm_manual_fund(
        db,
        batch_ids=body.batch_ids,
        admin_id=user.get("sub", "superadmin"),
        note=body.note,
    )
    try:
        await write_audit(
            db, organization_id="",
            actor=user.get("sub", ""), actor_role="superadmin",
            action="batch_bulk_funded",
            details={
                "processed": result.get("processed"),
                "success": result.get("success"),
                "failed": result.get("failed"),
                "note": body.note[:500],
            },
            target_entity_type="payout_batch",
            target_entity_id=",".join(body.batch_ids or [])[:200] or "all_wise_fund_pending",
        )
    except Exception:
        pass
    return result


class BatchFailMark(BaseModel):
    reason: str


@router.post(
    "/api/superadmin/financial/batches/{batch_id}/mark-failed",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_mark_batch_failed(
    request: Request, batch_id: str, body: BatchFailMark, user=Depends(_require_auth),
):
    if not body.reason or len(body.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="reason required (>=3 chars)")
    db = _get_db(request)
    result = await wb_mod.mark_batch_failed(
        db, batch_id=batch_id, admin_id=user.get("sub", "superadmin"), reason=body.reason,
    )
    try:
        batch = await db.payout_batches.find_one({"id": batch_id})
        await write_audit(
            db, organization_id=(batch or {}).get("organization_id", ""),
            actor=user.get("sub", ""), actor_role="superadmin",
            action="batch_failed",
            details={"batch_id": batch_id, "reason": body.reason},
            target_entity_type="payout_batch", target_entity_id=batch_id,
        )
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# 3k. PLANN v2 — Dead Letter Queue (SuperAdmin)
# ---------------------------------------------------------------------------

@router.get("/api/superadmin/financial/dlq", dependencies=[Depends(_require_superadmin)])
async def sa_list_dlq(
    request: Request,
    status: Optional[str] = None,
    failure_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    db = _get_db(request)
    query = {}
    if status:
        query["status"] = status
    if failure_type:
        query["failure_type"] = failure_type
    cursor = db.dead_letter_queue.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    return {"items": items}


@router.post(
    "/api/superadmin/financial/dlq/{dlq_id}/retry",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_dlq_retry(request: Request, dlq_id: str, user=Depends(_require_auth)):
    db = _get_db(request)
    result = await dlq_mod.manual_retry(db, dlq_id, user.get("sub", "superadmin"))
    try:
        await write_audit(
            db, organization_id="", actor=user.get("sub", ""), actor_role="superadmin",
            action="dlq_manual_retry", details={"dlq_id": dlq_id},
            target_entity_type="dlq", target_entity_id=dlq_id,
        )
    except Exception:
        pass
    return result


class DLQResolve(BaseModel):
    note: str


@router.post(
    "/api/superadmin/financial/dlq/{dlq_id}/resolve",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_dlq_resolve(request: Request, dlq_id: str, body: DLQResolve, user=Depends(_require_auth)):
    db = _get_db(request)
    result = await dlq_mod.manual_resolve(db, dlq_id, user.get("sub", "superadmin"), body.note)
    try:
        await write_audit(
            db, organization_id="", actor=user.get("sub", ""), actor_role="superadmin",
            action="dlq_manual_resolve", details={"dlq_id": dlq_id, "note": body.note},
            target_entity_type="dlq", target_entity_id=dlq_id,
        )
    except Exception:
        pass
    return result


@router.post(
    "/api/superadmin/financial/dlq/{dlq_id}/abandon",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_dlq_abandon(request: Request, dlq_id: str, body: DLQResolve, user=Depends(_require_auth)):
    db = _get_db(request)
    result = await dlq_mod.manual_abandon(db, dlq_id, user.get("sub", "superadmin"), body.note)
    try:
        await write_audit(
            db, organization_id="", actor=user.get("sub", ""), actor_role="superadmin",
            action="dlq_manual_abandon", details={"dlq_id": dlq_id, "reason": body.note},
            target_entity_type="dlq", target_entity_id=dlq_id,
        )
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# 3l. PLANN v2 — Feature Flags (SuperAdmin)
# ---------------------------------------------------------------------------

@router.get(
    "/api/superadmin/financial/feature-flags",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_list_feature_flags(request: Request):
    db = _get_db(request)
    return await ff_mod.list_all_flags(db)


class FlagGlobalSet(BaseModel):
    value: bool


@router.post(
    "/api/superadmin/financial/feature-flags/{name}/global",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_set_flag_global(
    request: Request, name: str, body: FlagGlobalSet, user=Depends(_require_auth),
):
    db = _get_db(request)
    try:
        await ff_mod.set_flag_global(db, name, body.value, user.get("sub", "superadmin"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await write_audit(
            db, organization_id="", actor=user.get("sub", ""), actor_role="superadmin",
            action="feature_flag_changed",
            details={"flag": name, "scope": "global", "value": body.value},
        )
    except Exception:
        pass
    return {"ok": True}


class FlagOrgSet(BaseModel):
    organization_id: str
    value: Optional[bool] = None  # None → remove override


@router.post(
    "/api/superadmin/financial/feature-flags/{name}/org",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_set_flag_org(
    request: Request, name: str, body: FlagOrgSet, user=Depends(_require_auth),
):
    db = _get_db(request)
    try:
        await ff_mod.set_flag_org_override(
            db, name, body.organization_id, body.value, user.get("sub", "superadmin"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await write_audit(
            db, organization_id=body.organization_id,
            actor=user.get("sub", ""), actor_role="superadmin",
            action="feature_flag_changed",
            details={"flag": name, "scope": "org", "value": body.value,
                     "organization_id": body.organization_id},
        )
    except Exception:
        pass
    return {"ok": True}


class FlagKillSwitch(BaseModel):
    disabled: bool


@router.post(
    "/api/superadmin/financial/feature-flags/{name}/kill-switch",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_flag_kill_switch(
    request: Request, name: str, body: FlagKillSwitch, user=Depends(_require_auth),
):
    db = _get_db(request)
    try:
        await ff_mod.set_emergency_disable(db, name, body.disabled, user.get("sub", "superadmin"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "emergency_disable": body.disabled}


# ---------------------------------------------------------------------------
# 3m. PLANN v2 — Reconciliation Summary + Export
# ---------------------------------------------------------------------------

from . import reconciliation as recon_mod


@router.get(
    "/api/superadmin/financial/reconciliation/multi_summary",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reconciliation_multi_summary(
    request: Request,
    start_iso: str = Query(...),
    end_iso: str = Query(...),
    organization_id: Optional[str] = None,
):
    """Return reconciliation summary per currency (TRY, GBP)."""
    db = _get_db(request)
    return await recon_mod.compute_multi_currency_summary(
        db, start_iso=start_iso, end_iso=end_iso, organization_id=organization_id,
    )


@router.get(
    "/api/superadmin/financial/reconciliation/discrepancies",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reconciliation_discrepancies(
    request: Request,
    start_iso: str = Query(...),
    end_iso: str = Query(...),
    organization_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    tolerance_minor: int = Query(100, ge=0, le=100000),
):
    """List per-tx discrepancies that contribute to the unexplained_diff."""
    db = _get_db(request)
    items = await recon_mod.list_discrepancies(
        db,
        start_iso=start_iso, end_iso=end_iso,
        organization_id=organization_id,
        limit=limit, tolerance_minor=tolerance_minor,
    )
    return {"items": items, "count": len(items)}


@router.get(
    "/api/superadmin/financial/reconciliation/summary",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reconciliation_summary(
    request: Request,
    start_iso: str = Query(...),
    end_iso: str = Query(...),
    organization_id: Optional[str] = None,
    base_currency: Optional[str] = None,
):
    db = _get_db(request)
    return await recon_mod.compute_reconciliation_summary(
        db, start_iso=start_iso, end_iso=end_iso,
        organization_id=organization_id, base_currency=base_currency,
    )


@router.get(
    "/api/superadmin/financial/reconciliation/export.csv",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reconciliation_export_csv(
    request: Request,
    start_iso: str = Query(...),
    end_iso: str = Query(...),
    organization_ids: Optional[str] = Query(None, description="comma separated"),
):
    db = _get_db(request)
    org_list = [s.strip() for s in (organization_ids or "").split(",") if s.strip()] or None
    content = await recon_mod.export_csv(
        db, start_iso=start_iso, end_iso=end_iso, organization_ids=org_list,
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="reconciliation_{start_iso[:10]}_{end_iso[:10]}.csv"',
        },
    )


@router.get(
    "/api/superadmin/financial/reconciliation/export.xlsx",
    dependencies=[Depends(_require_superadmin)],
)
async def sa_reconciliation_export_xlsx(
    request: Request,
    start_iso: str = Query(...),
    end_iso: str = Query(...),
    organization_ids: Optional[str] = Query(None),
):
    db = _get_db(request)
    org_list = [s.strip() for s in (organization_ids or "").split(",") if s.strip()] or None
    content = await recon_mod.export_xlsx(
        db, start_iso=start_iso, end_iso=end_iso, organization_ids=org_list,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="reconciliation_{start_iso[:10]}_{end_iso[:10]}.xlsx"',
        },
    )


# ---------------------------------------------------------------------------
# 3n. PLANN v2 — Fee preview with full gross-up (Stripe + Wise + Platform)
# ---------------------------------------------------------------------------

from .gross_up_service import preview_both_modes as _v2_preview_both


@router.get("/api/public/fee-preview-v2")
async def public_fee_preview_v2(
    request: Request,
    organization_id: str,
    service_id: Optional[str] = None,
    service_price_minor: Optional[int] = None,
):
    """
    Preview both fee_preference modes with full gross-up (PLANN v2).
    Either service_id OR service_price_minor must be provided.
    """
    db = _get_db(request)
    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise HTTPException(status_code=404, detail="Organization not found")

    base_currency = settings.get("base_currency", "TRY")
    tier = settings.get("payout_tier", "standard")
    price_minor = service_price_minor

    deposit_rule = None
    if service_id:
        service = await db.services.find_one({
            "id": service_id, "organization_id": organization_id,
        })
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        price_minor = price_minor or service.get("price_minor", 0)
        if not price_minor and service.get("price"):
            price_minor = int(round(service["price"] * 100))
        if service.get("payment_rule") == "deposit":
            dep_amount = service.get("deposit_amount")
            if dep_amount is not None:
                deposit_rule = DepositRule(
                    payment_rule="deposit", deposit_type="fixed",
                    deposit_value=int(round(dep_amount * 100)),
                )
            else:
                dep_pct = service.get("deposit_percentage", 30)
                deposit_rule = DepositRule(
                    payment_rule="deposit", deposit_type="percentage",
                    deposit_value=dep_pct * 100,
                )
        elif service.get("payment_rule") in ("full_online", "online"):
            deposit_rule = DepositRule(payment_rule="full_online")

    if not price_minor or price_minor <= 0:
        raise HTTPException(status_code=400, detail="invalid price")

    try:
        preview = _v2_preview_both(
            base_currency=base_currency,
            service_price_minor=price_minor,
            tier=tier,
            deposit_rule=deposit_rule,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    preview["currency_symbol"] = CURRENCY_SYMBOLS.get(base_currency, "₺")
    preview["tier"] = tier
    preview["fee_preference"] = settings.get("fee_preference", "seller_pays")
    return preview
