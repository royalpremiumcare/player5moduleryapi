"""
PLANN Financial Engine — Stripe Payout Reconciliation

Stripe `payout.paid` sonrası, payout içindeki balance transaction'ları listeler ve
her birini `merchant_transactions` ile eşler:

  - Eşleşen (stripe_charge_id / stripe_balance_transaction_id) → BUSINESS ödemesi.
    Bu tx'lere `stripe_payout_id` yazılır (Wise conversion & mutabakat için).
  - Eşleşmeyen → SUBSCRIPTION geliri veya diğer (PLANN'ın kendi GBP geliri).

Böylece bir Stripe payout'u içinde işletme müşteri ödemeleri ile abonelik geliri
net biçimde ayrılır. Sonuç `stripe_payout_reconciliations` koleksiyonuna özet
olarak kaydedilir (`_id`/`stripe_payout_id` unique → idempotent re-run).

NOT: Bu modül gerçek Wise conversion YAPMAZ; yalnızca etiketleme + mutabakat.
Conversion, wise_conversion_service.py (extension point) tarafından yürütülür.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import stripe

from .payment_types import PaymentType

logger = logging.getLogger(__name__)

# Stripe API tek sayfada max 100 döner; büyük payout'lar için sayfalama yapılır.
_BT_PAGE_SIZE = 100


def _sobj(obj: Any, key: str, default: Any = None) -> Any:
    """
    StripeObject veya dict'ten güvenli alan okuma.

    stripe-python v15'te API nesneleri dict değildir ve `.get()` yoktur;
    `.get` erişimi AttributeError fırlatır. Bu helper her ikisiyle de çalışır.
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


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _iter_payout_balance_transactions(payout_id: str) -> List[Dict[str, Any]]:
    """Bir payout'a bağlı tüm balance transaction'ları (sayfalayarak) topla."""
    items: List[Dict[str, Any]] = []
    starting_after = None
    while True:
        kwargs: Dict[str, Any] = {"payout": payout_id, "limit": _BT_PAGE_SIZE}
        if starting_after:
            kwargs["starting_after"] = starting_after
        resp = stripe.BalanceTransaction.list(**kwargs)
        data = resp.get("data", []) if isinstance(resp, dict) else resp.data
        if not data:
            break
        items.extend(data)
        has_more = resp.get("has_more", False) if isinstance(resp, dict) else resp.has_more
        if not has_more:
            break
        last = data[-1]
        starting_after = last.get("id") if isinstance(last, dict) else last.id
    return items


async def reconcile_payout(db, payout_id: str, payout_amount_minor: int = 0,
                           currency: str = "GBP") -> Dict[str, Any]:
    """
    Stripe payout'u business/subscription olarak ayrıştır ve özet kaydet.

    Idempotent: `stripe_payout_reconciliations._id = payout_id` (unique). Aynı
    `payout.paid` tekrar gelirse mevcut özet döner, yeniden etiketleme yapılmaz.
    """
    if not payout_id:
        return {"handled": False, "reason": "missing_payout_id"}

    # Idempotency: bu payout daha önce mutabakat gördü mü?
    existing = await db.stripe_payout_reconciliations.find_one({"_id": payout_id})
    if existing:
        logger.info("Payout %s already reconciled; skipping.", payout_id)
        return {"handled": True, "idempotent": True, "summary": existing}

    try:
        balance_txns = await _iter_payout_balance_transactions(payout_id)
    except Exception as e:
        logger.error("Failed to list balance transactions for payout %s: %s",
                     payout_id, e, exc_info=True)
        return {"handled": False, "reason": "stripe_list_failed", "error": str(e)}

    business_ids: List[str] = []
    business_total = 0
    subscription_count = 0
    subscription_total = 0
    unmatched_count = 0
    unmatched_total = 0

    for bt in balance_txns:
        bt_id = _sobj(bt, "id", "")
        bt_type = _sobj(bt, "type", "")
        source = _sobj(bt, "source", "")
        source_id = _sobj(source, "id", "") if not isinstance(source, str) else source
        gross = int(_sobj(bt, "amount", 0) or 0)

        # Payout satırının kendisini (type=payout) atla; yalnızca charge'ları eşle.
        if bt_type == "payout":
            continue
        if gross <= 0:
            # refund/adjustment vb. — mutabakatta ayrıca sınıflandırılmaz.
            continue

        # merchant_transactions ile eşle: balance_transaction_id VEYA charge_id.
        tx = await db.merchant_transactions.find_one({
            "$or": [
                {"stripe_balance_transaction_id": bt_id},
                {"stripe_charge_id": source_id},
            ]
        })

        if tx:
            # BUSINESS: payout_id'yi yaz (conversion & mutabakat izi).
            await db.merchant_transactions.update_one(
                {"id": tx["id"]},
                {"$set": {
                    "stripe_payout_id": payout_id,
                    "payment_type": PaymentType.BUSINESS.value,
                    "updated_at": _utcnow(),
                }},
            )
            business_ids.append(tx["id"])
            business_total += gross
        else:
            # Eşleşmeyen = PLANN'ın kendi geliri (abonelik) veya diğer.
            subscription_count += 1
            subscription_total += gross

    summary = {
        "_id": payout_id,
        "id": payout_id,
        "stripe_payout_id": payout_id,
        "currency": currency,
        "payout_amount_minor": payout_amount_minor,
        "business_count": len(business_ids),
        "business_total_minor": business_total,
        "subscription_count": subscription_count,
        "subscription_total_minor": subscription_total,
        "unmatched_count": unmatched_count,
        "unmatched_total_minor": unmatched_total,
        "matched_transaction_ids": business_ids,
        "created_at": _utcnow(),
    }

    # Idempotent yazım: unique _id sayesinde çift kayıt imkansız.
    try:
        await db.stripe_payout_reconciliations.insert_one(summary)
    except Exception as e:
        # DuplicateKeyError → başka bir worker aynı anda işledi; mevcut kaydı dön.
        logger.warning("Payout reconciliation insert race for %s (non-fatal): %s",
                       payout_id, e)
        existing = await db.stripe_payout_reconciliations.find_one({"_id": payout_id})
        if existing:
            return {"handled": True, "idempotent": True, "summary": existing}

    logger.info(
        "Payout %s reconciled: business=%d (%d) subscription=%d (%d)",
        payout_id, len(business_ids), business_total,
        subscription_count, subscription_total,
    )
    return {"handled": True, "idempotent": False, "summary": summary}


async def handle_payout_paid(db, payout: Dict[str, Any]) -> Dict[str, Any]:
    """`payout.paid` event handler → reconcile_payout."""
    payout_id = payout.get("id", "")
    amount = int(payout.get("amount", 0) or 0)
    currency = (payout.get("currency", "gbp") or "gbp").upper()
    return await reconcile_payout(db, payout_id, payout_amount_minor=amount, currency=currency)
