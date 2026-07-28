"""
PLANN Financial Engine — Wise API Service

Handles recipient creation (TR IBAN + UK Sort Code), quote locking,
batch group transfers, status checks, and webhook verification.

Wise batch groups: create → add transfers → complete → fund
Max 1000 transfers per batch group — chunking handled by payout_service.
"""

import asyncio
import os
import base64
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List

import requests

from .money import rate_to_micro, RATE_MULTIPLIER
from .schemas import WiseQuote

logger = logging.getLogger(__name__)

WISE_API_BASE = "https://api.transferwise.com"
WISE_SANDBOX_API_BASE = "https://api.wise-sandbox.com"

WISE_MAX_TRANSFERS_PER_BATCH = 1000


def _api_base() -> str:
    env = os.getenv("WISE_ENVIRONMENT", "sandbox")
    return WISE_SANDBOX_API_BASE if env == "sandbox" else WISE_API_BASE


def _headers(idempotency_key: Optional[str] = None) -> dict:
    token = os.getenv("WISE_API_TOKEN", "")
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        h["X-Idempotency-Key"] = idempotency_key
    return h


def _profile_id() -> str:
    return os.getenv("WISE_PROFILE_ID", "")


# ---------------------------------------------------------------------------
# Recipient Management
# ---------------------------------------------------------------------------

async def get_recipient_requirements(
    target_currency: str,
    country: str = "",
) -> List[Dict[str, Any]]:
    """Fetch dynamic recipient field requirements from Wise API."""
    params = {"source": "GBP", "target": target_currency, "sourceAmount": 100}
    if country:
        params["country"] = country

    try:
        resp = requests.get(
            f"{_api_base()}/v1/account-requirements",
            params=params,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Failed to fetch recipient requirements: %s", e)
        raise


async def create_recipient_tr_iban(
    iban: str,
    account_holder_name: str,
) -> Dict[str, Any]:
    """Create a TRY recipient with Turkish IBAN for cross-border transfer."""
    payload = {
        "profile": _profile_id(),
        "accountHolderName": account_holder_name,
        "currency": "TRY",
        "type": "turkish_earthport",
        "details": {
            "legalType": "PRIVATE",
            "IBAN": iban.upper().replace(" ", ""),
        },
    }

    try:
        resp = requests.post(
            f"{_api_base()}/v1/accounts",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Created TR recipient: id=%s name=%s", data.get("id"), account_holder_name)
        return data
    except Exception as e:
        logger.error("Failed to create TR recipient: %s", e)
        raise


async def create_recipient_uk_bank(
    sort_code: str,
    account_number: str,
    account_holder_name: str,
) -> Dict[str, Any]:
    """Create a GBP recipient with UK sort code + account number for BACS."""
    payload = {
        "profile": _profile_id(),
        "accountHolderName": account_holder_name,
        "currency": "GBP",
        "type": "sort_code",
        "details": {
            "sortCode": sort_code.replace("-", ""),
            "accountNumber": account_number.strip(),
        },
    }

    try:
        resp = requests.post(
            f"{_api_base()}/v1/accounts",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Created UK recipient: id=%s name=%s", data.get("id"), account_holder_name)
        return data
    except Exception as e:
        logger.error("Failed to create UK recipient: %s", e)
        raise


async def get_recipient_schema_hash(target_currency: str) -> str:
    """
    Get a hash of the current recipient requirements schema.
    Used to detect when Wise changes their requirements.
    """
    try:
        reqs = await get_recipient_requirements(target_currency)
        schema_str = str(sorted(str(reqs)))
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Quote Management
# ---------------------------------------------------------------------------

async def create_quote(
    db,
    organization_id: str,
    source_currency: str,
    target_currency: str,
    source_amount_minor: int,
    payout_batch_id: Optional[str] = None,
    target_amount_minor: int = 0,
) -> Dict[str, Any]:
    """
    Create and lock a Wise quote.
    Uses targetAmount when source amount is 0 (TRY market without GBP pool tracking).
    Returns the quote data + persists to wise_quotes collection.
    """
    payload = {
        "sourceCurrency": source_currency,
        "targetCurrency": target_currency,
        "profile": _profile_id(),
    }

    if source_amount_minor > 0:
        payload["sourceAmount"] = source_amount_minor / 100
    elif target_amount_minor > 0:
        payload["targetAmount"] = target_amount_minor / 100
    else:
        raise ValueError("Either source_amount_minor or target_amount_minor must be > 0")

    try:
        resp = requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/quotes",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code >= 400:
            body_preview = (resp.text or "")[:2000]
            logger.error(
                "Wise quote create %s: body=%s payload=%s",
                resp.status_code, body_preview, payload,
            )
            raise RuntimeError(f"wise_quote_{resp.status_code}: {body_preview}")
        data = resp.json()

        rate = Decimal(str(data.get("rate", 0)))
        rate_micro = rate_to_micro(rate)

        target_amount = data.get("targetAmount", 0)
        target_amount_minor = int(Decimal(str(target_amount)) * 100)

        fee_total = sum(
            Decimal(str(f.get("total", {}).get("value", 0)))
            for f in data.get("paymentOptions", [{}])[0:1]
        )
        wise_fee_minor = int(fee_total * 100)

        quote_doc = WiseQuote(
            organization_id=organization_id,
            payout_batch_id=payout_batch_id,
            wise_quote_id=data.get("id", ""),
            source_currency=source_currency,
            target_currency=target_currency,
            source_amount_minor=source_amount_minor,
            target_amount_minor=target_amount_minor,
            rate_micro=rate_micro,
            wise_fee_minor=wise_fee_minor,
            quote_expires_at=data.get("expirationTime", ""),
            status="active",
        ).model_dump()

        await db.wise_quotes.insert_one(quote_doc)

        logger.info(
            "Quote created: wise_id=%s %s→%s amount=%d rate=%s",
            data.get("id"), source_currency, target_currency, source_amount_minor, rate,
        )

        return {
            "quote_doc": quote_doc,
            "wise_quote_data": data,
        }

    except Exception as e:
        logger.error("Failed to create Wise quote: %s", e)
        raise


# ---------------------------------------------------------------------------
# Balance-to-Balance Conversion (GBP → TRY, PLANN treasury)
#
# İki adım:
#   1) Quote oluştur (payIn=BALANCE, payOut=BALANCE) → rate + quoteId.
#   2) balance-movements ile çalıştır (X-idempotence-uuid ile idempotent).
# Bu, transfer DEĞİLDİR — PLANN'ın kendi Wise hesabında GBP balance'ından
# TRY balance'ına para çevirir. İşletmeye ödeme Çarşamba batch'i ile ayrı yapılır.
# ---------------------------------------------------------------------------

async def create_balance_conversion_quote(
    source_currency: str,
    target_currency: str,
    source_amount_minor: int,
) -> Dict[str, Any]:
    """
    Balance-to-balance conversion için quote oluştur (payOut=BALANCE).

    Returns: {"id": quoteId, "rate": Decimal, "rate_micro": int,
              "target_minor": int, "fee_minor": int}
    """
    if source_amount_minor <= 0:
        raise ValueError("source_amount_minor must be > 0")

    payload = {
        "sourceCurrency": source_currency,
        "targetCurrency": target_currency,
        "sourceAmount": source_amount_minor / 100,
        "payOut": "BALANCE",
        "preferredPayIn": "BALANCE",
        "profile": _profile_id(),
    }

    def _do_post():
        return requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/quotes",
            json=payload,
            headers=_headers(),
            timeout=20,
        )

    resp = await asyncio.to_thread(_do_post)
    if resp.status_code >= 400:
        body_preview = (resp.text or "")[:2000]
        logger.error("Wise conversion quote %s: body=%s payload=%s",
                     resp.status_code, body_preview, payload)
        raise RuntimeError(f"wise_conversion_quote_{resp.status_code}: {body_preview}")

    data = resp.json()
    rate = Decimal(str(data.get("rate", 0)))
    rate_micro = rate_to_micro(rate)

    # BALANCE→BALANCE payment option'ından target + fee al (yoksa top-level'a düş).
    target_minor = 0
    fee_minor = 0
    for opt in data.get("paymentOptions", []) or []:
        if opt.get("payIn") == "BALANCE" and opt.get("payOut") == "BALANCE":
            ta = opt.get("targetAmount")
            if ta is not None:
                target_minor = int((Decimal(str(ta)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            fee_obj = opt.get("fee", {}) or {}
            fee_val = fee_obj.get("total", fee_obj.get("transferwise", 0)) or 0
            fee_minor = int((Decimal(str(fee_val)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            break
    if not target_minor:
        ta = data.get("targetAmount", 0) or 0
        target_minor = int((Decimal(str(ta)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    return {
        "id": data.get("id", ""),
        "rate": rate,
        "rate_micro": rate_micro,
        "target_minor": target_minor,
        "fee_minor": fee_minor,
    }


async def execute_balance_conversion(
    quote_id: str,
    idempotence_uuid: str,
) -> Dict[str, Any]:
    """
    Quote'u çalıştırıp GBP balance → TRY balance conversion'ı gerçekleştirir.

    `X-idempotence-uuid` deterministik verilir → retry'da Wise aynı hareketi döner,
    çift conversion oluşmaz. Returns: balance-movement response (id, state,
    sourceAmount, targetAmount, rate, feeAmounts).
    """
    if not quote_id:
        raise ValueError("quote_id required")

    headers = _headers()
    headers["X-idempotence-uuid"] = idempotence_uuid

    def _do_post():
        return requests.post(
            f"{_api_base()}/v2/profiles/{_profile_id()}/balance-movements",
            json={"quoteId": quote_id},
            headers=headers,
            timeout=30,
        )

    resp = await asyncio.to_thread(_do_post)
    if resp.status_code >= 400:
        body_preview = (resp.text or "")[:2000]
        logger.error("Wise balance-movement %s: body=%s quote=%s",
                     resp.status_code, body_preview, quote_id)
        raise RuntimeError(f"wise_balance_movement_{resp.status_code}: {body_preview}")

    data = resp.json()
    logger.info("Wise balance conversion executed: movement=%s state=%s quote=%s",
                data.get("id"), data.get("state"), quote_id)
    return data


# ---------------------------------------------------------------------------
# Batch Group Transfers
# ---------------------------------------------------------------------------

async def create_batch_group(source_currency: str = "GBP") -> Dict[str, Any]:
    """Create a new Wise batch group. Returns {id, version}."""
    payload = {
        "sourceCurrency": source_currency,
    }

    try:
        resp = requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/batch-groups",
            json=payload,
            headers=_headers(idempotency_key=str(uuid.uuid4())),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Batch group created: id=%s", data.get("id"))
        return {"id": data["id"], "version": data.get("version", 0)}
    except Exception as e:
        logger.error("Failed to create batch group: %s", e)
        raise


async def create_single_transfer(
    quote_id: str,
    recipient_id: str,
    customer_transaction_id: str,
    reference: str = "PLANN payout",
) -> Dict[str, Any]:
    """Create a single Wise transfer (used in sandbox where batch API is unavailable)."""
    payload = {
        "targetAccount": int(recipient_id) if recipient_id.isdigit() else recipient_id,
        "quoteUuid": quote_id,
        "customerTransactionId": customer_transaction_id,
        "details": {"reference": reference},
    }

    try:
        resp = requests.post(
            f"{_api_base()}/v1/transfers",
            json=payload,
            headers=_headers(idempotency_key=customer_transaction_id),
            timeout=15,
        )
        if resp.status_code >= 400:
            # Capture full Wise error body so DLQ / logs have actionable detail.
            body_preview = (resp.text or "")[:2000]
            logger.error(
                "Wise transfer create %s: status=%s body=%s payload=%s",
                resp.status_code, resp.reason, body_preview, payload,
            )
            raise RuntimeError(
                f"wise_transfer_create_{resp.status_code}: {body_preview or resp.reason}"
            )
        data = resp.json()
        logger.info("Single transfer created: id=%s status=%s", data.get("id"), data.get("status"))
        return data
    except RuntimeError:
        raise
    except Exception as e:
        logger.error("Failed to create single transfer: %s", e)
        raise


async def fund_single_transfer(transfer_id: str) -> Dict[str, Any]:
    """Fund a single Wise transfer. In sandbox, uses simulation endpoints to advance status."""
    is_sandbox = os.getenv("WISE_ENVIRONMENT", "sandbox") == "sandbox"

    if is_sandbox:
        import asyncio
        simulation_steps = ["processing", "funds_converted", "outgoing_payment_sent"]
        data = {}
        for step in simulation_steps:
            for attempt in range(3):
                await asyncio.sleep(2)
                resp = requests.get(
                    f"{_api_base()}/v1/simulation/transfers/{transfer_id}/{step}",
                    headers=_headers(),
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("Sandbox simulation %s: transfer %s → %s", step, transfer_id, data.get("status"))
                    break
                logger.warning("Sandbox simulation %s attempt %d failed: %s %s", step, attempt + 1, resp.status_code, resp.text[:200])
            else:
                logger.warning("Sandbox simulation %s failed after retries, continuing", step)
        return data

    try:
        resp = requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/transfers/{transfer_id}/payments",
            json={"type": "BALANCE"},
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.error(
                "Fund single transfer failed: id=%s status=%s body=%s",
                transfer_id,
                resp.status_code,
                (resp.text or "")[:2000],
            )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Single transfer funded: id=%s status=%s", transfer_id, data.get("status"))
        return data
    except Exception as e:
        logger.error("Failed to fund single transfer %s: %s", transfer_id, e)
        raise


async def add_transfer_to_batch(
    batch_group_id: str,
    quote_id: str,
    recipient_id: str,
    customer_transaction_id: str,
    reference: str = "PLANN payout",
) -> Dict[str, Any]:
    """Add a single transfer to an existing batch group."""
    payload = {
        "targetAccount": int(recipient_id) if recipient_id.isdigit() else recipient_id,
        "quoteUuid": quote_id,
        "customerTransactionId": customer_transaction_id,
        "details": {"reference": reference},
    }

    try:
        resp = requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/batch-groups/{batch_group_id}/transfers",
            json=payload,
            headers=_headers(idempotency_key=customer_transaction_id),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Transfer added to batch %s: transfer_id=%s", batch_group_id, data.get("id"))
        return data
    except Exception as e:
        logger.error("Failed to add transfer to batch: %s", e)
        raise


async def get_batch_group(batch_group_id: str) -> Dict[str, Any]:
    """Get current state of a batch group (to fetch latest version)."""
    try:
        resp = requests.get(
            f"{_api_base()}/v3/profiles/{_profile_id()}/batch-groups/{batch_group_id}",
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Failed to get batch group %s: %s", batch_group_id, e)
        raise


async def complete_batch_group(batch_group_id: str, version: int) -> Dict[str, Any]:
    """Complete (close) a batch group for funding."""
    payload = {"version": version}

    try:
        resp = requests.patch(
            f"{_api_base()}/v3/profiles/{_profile_id()}/batch-groups/{batch_group_id}",
            json={"status": "COMPLETED", **payload},
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Batch group completed: id=%s version=%s", batch_group_id, data.get("version"))
        return data
    except Exception as e:
        logger.error("Failed to complete batch group: %s", e)
        raise


async def fund_batch_group(batch_group_id: str) -> Dict[str, Any]:
    """Fund a completed batch group to initiate transfers."""
    try:
        resp = requests.post(
            f"{_api_base()}/v3/profiles/{_profile_id()}/batch-payments/{batch_group_id}/payments",
            json={"type": "BALANCE"},
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Batch group funded: id=%s", batch_group_id)
        return data
    except Exception as e:
        logger.error("Failed to fund batch group: %s", e)
        raise


# ---------------------------------------------------------------------------
# PLANN v2 — Wednesday Batch Preparation
# ---------------------------------------------------------------------------

async def prepare_batch_group(db, batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare a Wise transfer for a Wednesday batch payout.

    IMPORTANT: Does NOT fund — only creates a quote + draft transfer.
    SuperAdmin will fund manually via the Wise dashboard on Wednesday.

    Batch is per-organization (one merchant wallet). We create ONE Wise transfer
    for the aggregate total_amount_minor to the merchant's registered recipient.

    Args:
        db: MongoDB instance (for settings lookup)
        batch: payout_batches document (contains organization_id, base_currency,
               total_amount_minor, item_transaction_ids, id)

    Returns:
        {
            "wise_quote_id": str,
            "wise_transfer_id": str,
            "wise_batch_group_id": str or None,  # if batch API used
            "total_amount_minor": int,
            "target_currency": str,
            "recipient_id": str,
        }

    Raises:
        RuntimeError: on Wise API failure or missing config.
    """
    organization_id = batch.get("organization_id")
    base_currency = (batch.get("base_currency") or "TRY").upper()
    total_amount_minor = int(batch.get("total_amount_minor") or 0)
    batch_id = batch.get("id") or str(uuid.uuid4())

    if total_amount_minor <= 0:
        raise RuntimeError(f"batch has no amount: batch_id={batch_id}")

    settings = await db.settings.find_one({"organization_id": organization_id})
    if not settings:
        raise RuntimeError(f"settings not found for org={organization_id}")

    recipient_id = settings.get("wise_recipient_id")
    if not recipient_id:
        raise RuntimeError(
            f"wise_recipient_id missing for org={organization_id}; "
            "merchant must complete KYC + bank setup first."
        )

    # Source is always GBP (PLANN pool). Target depends on market.
    source_currency = "GBP"
    target_currency = base_currency  # TRY for TR merchants, GBP for UK

    # For GBP merchants, source == target (no conversion)
    # For TRY merchants, Wise cross-border GBP → TRY
    if base_currency == "GBP":
        # 1:1, source_amount == total_amount
        source_amount_minor = total_amount_minor
        target_amount_minor = 0  # use sourceAmount
    else:
        # TRY: we want merchant to receive exactly total_amount_minor in TRY
        source_amount_minor = 0
        target_amount_minor = total_amount_minor

    logger.info(
        "wise prepare_batch_group: batch=%s org=%s amount=%d %s → %s recipient=%s",
        batch_id, organization_id, total_amount_minor, source_currency,
        target_currency, recipient_id,
    )

    # Step 1: Create + persist quote
    try:
        quote_result = await create_quote(
            db,
            organization_id=organization_id,
            source_currency=source_currency,
            target_currency=target_currency,
            source_amount_minor=source_amount_minor,
            target_amount_minor=target_amount_minor,
            payout_batch_id=batch_id,
        )
    except requests.HTTPError as e:
        body = getattr(e.response, "text", "")[:500] if getattr(e, "response", None) else ""
        raise RuntimeError(f"wise quote failed: {e} body={body}")
    except Exception as e:
        raise RuntimeError(f"wise quote failed: {e}")

    wise_quote_id = quote_result["quote_doc"].get("wise_quote_id") or quote_result["wise_quote_data"].get("id")
    if not wise_quote_id:
        raise RuntimeError(f"wise quote returned no id: {quote_result}")

    # Step 2: Create transfer (NOT funded — awaits manual admin fund in Wise panel)
    # Wise requires customerTransactionId to be a valid UUID (no prefix allowed).
    # batch_id is already a UUID; use it directly.
    customer_tx_id = str(batch_id)
    reference = (settings.get("company_name") or "PLANN")[:18]  # Wise reference max ~20 chars

    wise_batch_group_id: Optional[str] = None
    transfer_data: Dict[str, Any] = {}

    # Use batch-group flow for production, single transfer for sandbox
    use_batch_group = os.getenv("WISE_USE_BATCH_GROUPS", "false").lower() == "true"

    try:
        if use_batch_group:
            bg = await create_batch_group(source_currency=source_currency)
            wise_batch_group_id = bg["id"]
            transfer_data = await add_transfer_to_batch(
                batch_group_id=wise_batch_group_id,
                quote_id=wise_quote_id,
                recipient_id=str(recipient_id),
                customer_transaction_id=customer_tx_id,
                reference=reference,
            )
            # Complete the batch group so admin can fund it from the Wise panel
            try:
                latest = await get_batch_group(wise_batch_group_id)
                await complete_batch_group(
                    wise_batch_group_id,
                    version=latest.get("version", bg.get("version", 0)),
                )
            except Exception as ce:
                logger.warning("batch group complete failed (non-fatal): %s", ce)
        else:
            transfer_data = await create_single_transfer(
                quote_id=wise_quote_id,
                recipient_id=str(recipient_id),
                customer_transaction_id=customer_tx_id,
                reference=reference,
            )
    except requests.HTTPError as e:
        body = getattr(e.response, "text", "")[:500] if getattr(e, "response", None) else ""
        raise RuntimeError(f"wise transfer create failed: {e} body={body}")
    except Exception as e:
        raise RuntimeError(f"wise transfer create failed: {e}")

    wise_transfer_id = str(transfer_data.get("id") or "")
    if not wise_transfer_id:
        raise RuntimeError(f"wise transfer create returned no id: {transfer_data}")

    logger.info(
        "wise prepare_batch_group success: batch=%s quote=%s transfer=%s batch_group=%s",
        batch_id, wise_quote_id, wise_transfer_id, wise_batch_group_id,
    )

    return {
        "wise_quote_id": wise_quote_id,
        "wise_transfer_id": wise_transfer_id,
        "wise_batch_group_id": wise_batch_group_id,
        "total_amount_minor": total_amount_minor,
        "target_currency": target_currency,
        "recipient_id": str(recipient_id),
        "transfer_status": transfer_data.get("status"),
    }


async def prepare_unified_batch_group(
    db, batches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Prepare MULTIPLE PLANN payout_batches as a SINGLE Wise batch group.

    Every PLANN batch becomes one transfer inside the same Wise batch group,
    so the Wise panel shows a single "N GBP Transfer batch" entry admin can fund
    in one shot (instead of per-merchant single transfers).

    Returns:
        {
            "wise_batch_group_id": str,
            "total_source_gbp_minor": int,       # approx — sum via quotes
            "per_batch": {
                plann_batch_id: {
                    "wise_quote_id": str,
                    "wise_transfer_id": str,
                    "target_currency": str,
                    "recipient_id": str,
                    "total_amount_minor": int,
                    "transfer_status": str,
                },
                ...
            },
        }

    Raises:
        RuntimeError: if ANY batch fails during prep. Caller is responsible for
        rolling back tx/batch states. wise_batch_group_id (if created) is included
        in the error for manual cleanup from Wise panel.
    """
    if not batches:
        raise RuntimeError("no batches to prepare")

    # Source currency is always GBP (PLANN pool) — single batch group covers all.
    source_currency = "GBP"

    # Step 1: create the shared Wise batch group
    bg = await create_batch_group(source_currency=source_currency)
    wise_batch_group_id = bg["id"]
    logger.info(
        "unified batch group created: wise_group=%s plann_batch_count=%d",
        wise_batch_group_id, len(batches),
    )

    per_batch: Dict[str, Dict[str, Any]] = {}

    # Step 2: for each PLANN batch, create quote + add transfer to the group
    for b in batches:
        organization_id = b.get("organization_id")
        base_currency = (b.get("base_currency") or "TRY").upper()
        total_amount_minor = int(b.get("total_amount_minor") or 0)
        batch_id = b.get("id")

        if total_amount_minor <= 0:
            raise RuntimeError(
                f"unified: batch {batch_id} has zero amount; aborting (wise_group={wise_batch_group_id})"
            )

        settings = await db.settings.find_one({"organization_id": organization_id})
        if not settings:
            raise RuntimeError(
                f"unified: settings not found for org={organization_id} (wise_group={wise_batch_group_id})"
            )

        recipient_id = settings.get("wise_recipient_id")
        if not recipient_id:
            raise RuntimeError(
                f"unified: wise_recipient_id missing for org={organization_id} "
                f"(wise_group={wise_batch_group_id})"
            )

        target_currency = base_currency
        if base_currency == "GBP":
            source_amount_minor = total_amount_minor
            target_amount_minor = 0
        else:
            source_amount_minor = 0
            target_amount_minor = total_amount_minor

        try:
            quote_result = await create_quote(
                db,
                organization_id=organization_id,
                source_currency=source_currency,
                target_currency=target_currency,
                source_amount_minor=source_amount_minor,
                target_amount_minor=target_amount_minor,
                payout_batch_id=batch_id,
            )
        except Exception as e:
            raise RuntimeError(
                f"unified: quote failed for batch {batch_id}: {e} (wise_group={wise_batch_group_id})"
            )

        wise_quote_id = (
            quote_result["quote_doc"].get("wise_quote_id")
            or quote_result["wise_quote_data"].get("id")
        )
        if not wise_quote_id:
            raise RuntimeError(
                f"unified: quote returned no id for batch {batch_id} (wise_group={wise_batch_group_id})"
            )

        customer_tx_id = str(batch_id)
        reference = (settings.get("company_name") or "PLANN")[:18]

        try:
            transfer_data = await add_transfer_to_batch(
                batch_group_id=wise_batch_group_id,
                quote_id=wise_quote_id,
                recipient_id=str(recipient_id),
                customer_transaction_id=customer_tx_id,
                reference=reference,
            )
        except Exception as e:
            raise RuntimeError(
                f"unified: add_transfer failed for batch {batch_id}: {e} "
                f"(wise_group={wise_batch_group_id})"
            )

        wise_transfer_id = str(transfer_data.get("id") or "")
        if not wise_transfer_id:
            raise RuntimeError(
                f"unified: transfer returned no id for batch {batch_id} "
                f"(wise_group={wise_batch_group_id})"
            )

        per_batch[batch_id] = {
            "wise_quote_id": wise_quote_id,
            "wise_transfer_id": wise_transfer_id,
            "target_currency": target_currency,
            "recipient_id": str(recipient_id),
            "total_amount_minor": total_amount_minor,
            "transfer_status": transfer_data.get("status"),
        }
        logger.info(
            "unified: batch %s added to group %s (transfer=%s)",
            batch_id, wise_batch_group_id, wise_transfer_id,
        )

    # Step 3: complete the batch group (Wise panel: ready-to-fund)
    try:
        latest = await get_batch_group(wise_batch_group_id)
        await complete_batch_group(
            wise_batch_group_id,
            version=latest.get("version", bg.get("version", 0)),
        )
        logger.info("unified batch group completed: %s", wise_batch_group_id)
    except Exception as ce:
        logger.warning(
            "unified: batch group complete failed (non-fatal): wise_group=%s err=%s",
            wise_batch_group_id, ce,
        )

    return {
        "wise_batch_group_id": wise_batch_group_id,
        "per_batch": per_batch,
    }


# ---------------------------------------------------------------------------
# Transfer Status
# ---------------------------------------------------------------------------

async def get_transfer_status(transfer_id: str) -> Dict[str, Any]:
    """Get current status of a Wise transfer."""
    try:
        resp = requests.get(
            f"{_api_base()}/v1/transfers/{transfer_id}",
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Failed to get transfer status: %s", e)
        raise


def map_wise_status_to_state(wise_status: str) -> Optional[str]:
    """Map Wise transfer status to our state machine state."""
    mapping = {
        "incoming_payment_waiting": "reserved",
        "incoming_payment_initiated": "reserved",
        "processing": "reserved",
        "funds_converted": "reserved",
        "outgoing_payment_sent": "paid_out",
        "cancelled": "failed",
        "funds_refunded": "failed",
        "bounced_back": "failed",
        "charged_back": "failed",
    }
    return mapping.get(wise_status)


# ---------------------------------------------------------------------------
# Webhook Verification
# ---------------------------------------------------------------------------

# Wise sandbox RSA public key (from https://docs.wise.com/guides/developer/webhooks/event-handling)
_WISE_SANDBOX_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwpb91cEYuyJNQepZAVfP
ZIlPZfNUefH+n6w9SW3fykqKu938cR7WadQv87oF2VuT+fDt7kqeRziTmPSUhqPU
ys/V2Q1rlfJuXbE+Gga37t7zwd0egQ+KyOEHQOpcTwKmtZ81ieGHynAQzsn1We3j
wt760MsCPJ7GMT141ByQM+yW1Bx+4SG3IGjXWyqOWrcXsxAvIXkpUD/jK/L958Cg
nZEgz0BSEh0QxYLITnW1lLokSx/dTianWPFEhMC9BgijempgNXHNfcVirg1lPSyg
z7KqoKUN0oHqWLr2U1A+7kqrl6O2nx3CKs1bj1hToT1+p4kcMoHXA7kA+VBLUpEs
VwIDAQAB
-----END PUBLIC KEY-----"""

# Wise production RSA public key
_WISE_PROD_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvO8vXV+JksBzZAY6GhSO
XdoTCfhXaaiZ+qAbtaDBiu2AGkGVpmEygFmWP4Li9m5+Ni85BhVvZOodM9epgW3F
bA5Q1SexvAF1PPjX4JpMstak/QhAgl1qMSqEevL8cmUeTgcMuVWCJmlge9h7B1CS
D4rtlimGZozG39rUBDg6Qt2K+P4wBfLblL0k4C4YUdLnpGYEDIth+i8XsRpFlogx
CAFyH9+knYsDbR43UJ9shtc42Ybd40Afihj8KnYKXzchyQ42aC8aZ/h5hyZ28yVy
Oj3Vos0VdBIs/gAyJ/4yyQFCXYte64I7ssrlbGRaco4nKF3HmaNhxwyKyJafz19e
HwIDAQAB
-----END PUBLIC KEY-----"""


def verify_wise_signature(payload: bytes, signature_header: str) -> bool:
    """
    Verify Wise webhook signature using X-Signature-SHA256 header.
    Wise V2 webhooks use RSA SHA256 signing — no shared secret needed.
    The signature header is a base64-encoded RSA signature.
    """
    if not signature_header:
        environment = os.getenv("WISE_ENVIRONMENT", "sandbox").lower()
        if environment == "production":
            logger.warning("Wise webhook: missing X-Signature-SHA256 header — rejecting in production")
            return False
        logger.warning("Wise webhook: missing X-Signature-SHA256 header — allowing in sandbox")
        return True

    environment = os.getenv("WISE_ENVIRONMENT", "sandbox").lower()
    public_key_pem = _WISE_SANDBOX_PUBLIC_KEY if environment == "sandbox" else _WISE_PROD_PUBLIC_KEY

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8"),
            backend=default_backend(),
        )
        signature_bytes = base64.b64decode(signature_header)
        public_key.verify(signature_bytes, payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception as e:
        logger.warning(f"Wise webhook RSA signature verification failed: {e}")
        return False


async def handle_wise_webhook(
    db,
    payload: bytes,
    signature_header: str,
    *,
    redis_client=None,
    background_tasks=None,
) -> Dict[str, Any]:
    """
    Process a Wise webhook event.
    1. Verify signature
    2. Check idempotency
    3. Route: balance credit → GBP→TRY auto-convert; transfer state → state machine
    """
    import json

    if not verify_wise_signature(payload, signature_header):
        logger.warning("Wise webhook signature verification failed")
        return {"status": "signature_failed"}

    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        return {"status": "invalid_json"}

    event_type = event_data.get("event_type", "")

    # Balance kredilendi → bekleyen BUSINESS ödemelerini GBP→TRY otomatik çevir.
    if event_type in ("balances#credit", "balances#update"):
        return await _handle_balance_credit_event(
            db, event_data, payload,
            redis_client=redis_client, background_tasks=background_tasks,
        )

    resource = event_data.get("data", {}).get("resource", {})
    transfer_id = str(resource.get("id", ""))
    wise_status = resource.get("current_state", "")

    event_id = f"wise_{event_type}_{transfer_id}_{wise_status}"
    body_sha256 = hashlib.sha256(payload).hexdigest()

    existing = await db.webhook_events.find_one({"event_id": event_id})
    if existing and existing.get("processing_status") == "processed":
        return {"status": "skipped", "event_id": event_id}

    webhook_doc = {
        "id": str(uuid.uuid4()),
        "source": "wise",
        "event_id": event_id,
        "event_type": event_type,
        "payload": event_data,
        "raw_body": payload.decode("utf-8", errors="replace"),
        "raw_headers": {"X-Signature-SHA256": signature_header},
        "body_sha256": body_sha256,
        "signature_verified": True,
        "processing_status": "processing",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    if not existing:
        await db.webhook_events.insert_one(webhook_doc)

    try:
        new_state = map_wise_status_to_state(wise_status)
        if not new_state or not transfer_id:
            await db.webhook_events.update_one(
                {"event_id": event_id},
                {"$set": {"processing_status": "processed"}},
            )
            return {"status": "processed", "handled": False}

        tx = await db.merchant_transactions.find_one({"wise_transfer_id": transfer_id})
        if not tx:
            logger.warning("No transaction found for Wise transfer: %s", transfer_id)
            await db.webhook_events.update_one(
                {"event_id": event_id},
                {"$set": {"processing_status": "processed"}},
            )
            return {"status": "processed", "handled": False}

        from .state_machine import StateMachine
        sm = StateMachine(db)
        await sm.transition(
            tx_id=tx["id"],
            new_state=new_state,
            trigger=f"wise.{wise_status}",
        )

        if new_state in ("paid_out", "failed"):
            try:
                await _send_payout_email(db, tx, new_state)
            except Exception as mail_err:
                logger.warning("Payout email failed (non-blocking): %s", mail_err)

        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "processing_status": "processed",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "organization_id": tx["organization_id"],
                "transaction_id": tx["id"],
            }},
        )

        return {
            "status": "processed",
            "handled": True,
            "transaction_id": tx["id"],
            "new_state": new_state,
        }

    except Exception as e:
        logger.exception("Wise webhook processing failed: %s", e)
        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "processing_status": "failed",
                "processing_error": str(e),
            }},
        )
        return {"status": "failed", "error": str(e)}


async def _handle_balance_credit_event(
    db,
    event_data: Dict[str, Any],
    payload: bytes,
    *,
    redis_client=None,
    background_tasks=None,
) -> Dict[str, Any]:
    """
    `balances#credit` / `balances#update` işleyici.

    GBP balance kredilendiğinde (Stripe payout Wise'a düştüğünde) bekleyen BUSINESS
    ödemelerini GBP→TRY otomatik çevirir. SUBSCRIPTION gelirlerine DOKUNULMAZ.
    Conversion, webhook yanıtını bloklamamak için background task'ta çalışır;
    per-transaction idempotency çift conversion'ı engeller.
    """
    data = event_data.get("data", {}) or {}
    currency = str(data.get("currency", "")).upper()
    amount = data.get("amount", 0) or 0
    txn_type = str(data.get("transaction_type", "credit")).lower()
    occurred_at = data.get("occurred_at", "")
    event_type = event_data.get("event_type", "")

    # Yalnızca GBP kredisi ilgilendirir (GBP→TRY convert). Debit/diğer para birimi → ack.
    is_credit = txn_type == "credit" or (event_type == "balances#credit")
    if currency != "GBP" or not is_credit or float(amount) <= 0:
        return {"status": "processed", "handled": False, "reason": "not_gbp_credit"}

    event_id = f"wise_balcredit_GBP_{amount}_{occurred_at}"
    body_sha256 = hashlib.sha256(payload).hexdigest()

    existing = await db.webhook_events.find_one({"event_id": event_id})
    if existing and existing.get("processing_status") == "processed":
        return {"status": "skipped", "event_id": event_id}

    if not existing:
        await db.webhook_events.insert_one({
            "id": str(uuid.uuid4()),
            "source": "wise",
            "event_id": event_id,
            "event_type": event_type,
            "payload": event_data,
            "raw_body": payload.decode("utf-8", errors="replace"),
            "body_sha256": body_sha256,
            "signature_verified": True,
            "processing_status": "processing",
            "received_at": datetime.now(timezone.utc).isoformat(),
        })

    from .wise_conversion_service import run_auto_conversion_on_credit

    if background_tasks is not None:
        # Hızlı 200 dön; conversion arka planda çalışsın.
        background_tasks.add_task(
            run_auto_conversion_on_credit, db, redis_client=redis_client,
        )
        triggered = "scheduled"
    else:
        # Cron/senkron çağrı: inline çalıştır.
        await run_auto_conversion_on_credit(db, redis_client=redis_client)
        triggered = "inline"

    await db.webhook_events.update_one(
        {"event_id": event_id},
        {"$set": {
            "processing_status": "processed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    logger.info("Wise GBP balance credit handled: amount=%s conversion=%s", amount, triggered)
    return {"status": "processed", "handled": True, "conversion_trigger": triggered}


async def _send_payout_email(db, tx: dict, new_state: str):
    """Send payout success/failure email to the merchant (non-blocking)."""
    import asyncio
    from .email_notifications import send_payout_success_email, send_payout_failed_email

    org_id = tx.get("organization_id", "")
    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0})
    user = await db.users.find_one({"organization_id": org_id, "role": "admin"}, {"_id": 0})

    if not user or not settings:
        logger.warning("Cannot send payout email: user/settings not found for org %s", org_id)
        return

    to_email = user.get("username", "")
    merchant_name = settings.get("company_name", "İşletme")
    amount_minor = tx.get("amount_display_minor", 0)
    base_currency = tx.get("base_currency", "TRY")

    if not to_email:
        return

    if new_state == "paid_out":
        payout_rail = "wise" if tx.get("wise_transfer_id") else "unknown"
        await asyncio.to_thread(
            send_payout_success_email, to_email, merchant_name, amount_minor, base_currency, payout_rail
        )
    elif new_state == "failed":
        error_msg = tx.get("failure_reason", "")
        await asyncio.to_thread(
            send_payout_failed_email, to_email, merchant_name, amount_minor, base_currency, error_msg
        )
