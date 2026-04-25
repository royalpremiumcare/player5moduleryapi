"""
Reconciliation Summary & CSV/XLSX Export.

Aggregates financial flows across Stripe / platform / Wise / refunds
to produce a summary report + export for accounting.

See plan Bölüm 13 + 2.8.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Tolerance for "unexplained_diff" alert
TOLERANCE_MINOR = {"GBP": 1000, "TRY": 50000}  # £10, ₺500


async def compute_multi_currency_summary(
    db,
    *,
    start_iso: str,
    end_iso: str,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return per-currency reconciliation summaries under a single envelope.
    Keys: {"TRY": {...}, "GBP": {...}}. A currency is omitted if it has
    zero activity in the range.
    """
    result: Dict[str, Any] = {
        "start_iso": start_iso,
        "end_iso": end_iso,
        "organization_id": organization_id,
        "summaries": {},
    }
    for cc in ("TRY", "GBP"):
        s = await compute_reconciliation_summary(
            db, start_iso=start_iso, end_iso=end_iso,
            organization_id=organization_id, base_currency=cc,
        )
        # Omit currencies with no activity at all
        touched = any([
            s["stripe_total_minor"], s["platform_fee_total_minor"],
            s["refund_total_minor"], s["pending_total_minor"],
            s["reserved_total_minor"], s["paid_out_total_minor"],
            s["wise_funded_total_minor"],
        ])
        if touched:
            result["summaries"][cc] = s
    return result


async def list_discrepancies(
    db,
    *,
    start_iso: str,
    end_iso: str,
    organization_id: Optional[str] = None,
    limit: int = 200,
    tolerance_minor: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return per-transaction discrepancies that explain the unexplained_diff.
    For each payment tx, we check:
        expected_merchant = customer_price - platform_fee - stripe_fee - wise_fee
        recorded_merchant = amount_display_minor
    If the delta exceeds `tolerance_minor` (default 1.00 unit), it's listed.
    """
    q: Dict[str, Any] = {
        "type": "payment",
        "created_at": {"$gte": start_iso, "$lte": end_iso},
    }
    if organization_id:
        q["organization_id"] = organization_id

    # Resolve org names once
    org_name: Dict[str, str] = {}
    async for s in db.settings.find(
        {},
        {"_id": 0, "organization_id": 1, "company_name": 1, "business_name": 1},
    ):
        org_name[s["organization_id"]] = (
            s.get("company_name") or s.get("business_name") or s["organization_id"]
        )

    items: List[Dict[str, Any]] = []
    async for tx in db.merchant_transactions.find(q, {"_id": 0}).limit(2000):
        customer = int(tx.get("customer_price_minor") or tx.get("amount_display_minor") or 0)
        platform = int(tx.get("platform_fee_minor") or tx.get("fee_amount_minor") or 0)
        stripe_f = int(tx.get("stripe_fee_minor") or 0)
        wise_f = int(tx.get("wise_fee_minor") or 0)
        recorded = int(tx.get("amount_display_minor") or 0)
        expected = customer - platform - stripe_f - wise_f
        delta = recorded - expected
        if abs(delta) <= tolerance_minor:
            continue
        items.append({
            "tx_id": tx.get("id"),
            "organization_id": tx.get("organization_id"),
            "organization_name": org_name.get(tx.get("organization_id", ""), tx.get("organization_id", "")),
            "base_currency": tx.get("base_currency", "TRY"),
            "state": tx.get("state"),
            "customer_price_minor": customer,
            "platform_fee_minor": platform,
            "stripe_fee_minor": stripe_f,
            "wise_fee_minor": wise_f,
            "expected_merchant_minor": expected,
            "recorded_merchant_minor": recorded,
            "delta_minor": delta,
            "created_at": tx.get("created_at"),
            "stripe_payment_intent_id": tx.get("stripe_payment_intent_id"),
        })
        if len(items) >= limit:
            break

    # Most impactful first
    items.sort(key=lambda x: abs(x["delta_minor"]), reverse=True)
    return items


async def compute_reconciliation_summary(
    db,
    *,
    start_iso: str,
    end_iso: str,
    organization_id: Optional[str] = None,
    base_currency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate financial metrics for a date range (ISO timestamps).

    Returns stripe totals, platform fee, wise funded, refund/dispute deductions,
    pending/reserved, and an unexplained_diff.
    """
    tx_query: Dict[str, Any] = {
        "created_at": {"$gte": start_iso, "$lte": end_iso},
        # Exclude orphan payments — rows with no Stripe PI never reached the
        # processor, so they shouldn't contribute to tahsilat/pending totals.
        # Refund tx's (type=refund) don't have a PI either, so only exclude
        # orphan *payments*.
        "$or": [
            {"type": {"$ne": "payment"}},
            {
                "type": "payment",
                "stripe_payment_intent_id": {"$nin": [None, ""]},
            },
        ],
    }
    if organization_id:
        tx_query["organization_id"] = organization_id
    if base_currency:
        tx_query["base_currency"] = base_currency

    stripe_total = 0          # sum of customer_price (payments only)
    platform_fee_total = 0
    stripe_fee_total = 0
    wise_fee_total = 0
    refund_total = 0
    dispute_lost_total = 0
    pending_total = 0
    reserved_total = 0
    paid_out_total = 0

    async for tx in db.merchant_transactions.find(tx_query):
        ttype = tx.get("type")
        state = tx.get("state")
        amt_display = int(tx.get("amount_display_minor") or 0)
        customer_price = int(tx.get("customer_price_minor") or amt_display)
        platform_fee = int(tx.get("platform_fee_minor") or tx.get("fee_amount_minor") or 0)
        stripe_fee = int(tx.get("stripe_fee_minor") or 0)
        wise_fee = int(tx.get("wise_fee_minor") or 0)

        if ttype == "payment":
            stripe_total += customer_price
            platform_fee_total += platform_fee
            stripe_fee_total += stripe_fee
            wise_fee_total += wise_fee
            if state in ("pending", "captured", "settled"):
                pending_total += amt_display
            if state in ("reserved", "reserved_for_batch", "queued_for_wise", "wise_fund_pending"):
                reserved_total += amt_display
            if state == "paid_out":
                paid_out_total += amt_display
        elif ttype == "refund":
            refund_total += abs(amt_display)
        elif state == "resolved_lost":
            dispute_lost_total += amt_display

    # Wise funded = sum of completed payout_batches
    batch_query: Dict[str, Any] = {
        "status": "completed",
        "funded_at": {"$gte": start_iso, "$lte": end_iso},
    }
    if organization_id:
        batch_query["organization_id"] = organization_id
    wise_funded_total = 0
    async for b in db.payout_batches.find(batch_query):
        wise_funded_total += int(b.get("total_amount_minor") or 0)

    unexplained = (
        stripe_total
        - platform_fee_total
        - stripe_fee_total
        - wise_funded_total
        - refund_total
        - dispute_lost_total
        - pending_total
        - reserved_total
    )

    cc = base_currency or "GBP"
    tolerance = TOLERANCE_MINOR.get(cc, 1000)
    alert = abs(unexplained) > tolerance

    return {
        "start_iso": start_iso,
        "end_iso": end_iso,
        "organization_id": organization_id,
        "base_currency": cc,
        "stripe_total_minor": stripe_total,
        "platform_fee_total_minor": platform_fee_total,
        "stripe_fee_total_minor": stripe_fee_total,
        "wise_fee_total_minor": wise_fee_total,
        "wise_funded_total_minor": wise_funded_total,
        "refund_total_minor": refund_total,
        "dispute_lost_total_minor": dispute_lost_total,
        "pending_total_minor": pending_total,
        "reserved_total_minor": reserved_total,
        "paid_out_total_minor": paid_out_total,
        "unexplained_diff_minor": unexplained,
        "tolerance_minor": tolerance,
        "alert": alert,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Export (CSV / XLSX)
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "organization_id", "organization_name", "base_currency",
    "period_start", "period_end",
    "stripe_total", "platform_fee", "stripe_fee_estimate",
    "wise_fee", "wise_funded", "refund_deductions", "dispute_deductions",
    "pending", "reserved", "paid_out", "unexplained_diff",
]


async def export_csv(
    db,
    *,
    start_iso: str,
    end_iso: str,
    organization_ids: Optional[List[str]] = None,
) -> str:
    """Return CSV content as a string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    # Iterate orgs (single or all)
    if organization_ids:
        org_list = organization_ids
    else:
        org_list = [s["organization_id"] async for s in db.settings.find({}, {"organization_id": 1})]

    for org_id in org_list:
        settings = await db.settings.find_one({"organization_id": org_id}) or {}
        summary = await compute_reconciliation_summary(
            db, start_iso=start_iso, end_iso=end_iso, organization_id=org_id,
            base_currency=settings.get("base_currency"),
        )
        writer.writerow({
            "organization_id": org_id,
            "organization_name": settings.get("company_name", ""),
            "base_currency": summary["base_currency"],
            "period_start": start_iso,
            "period_end": end_iso,
            "stripe_total": summary["stripe_total_minor"] / 100,
            "platform_fee": summary["platform_fee_total_minor"] / 100,
            "stripe_fee_estimate": summary["stripe_fee_total_minor"] / 100,
            "wise_fee": summary["wise_fee_total_minor"] / 100,
            "wise_funded": summary["wise_funded_total_minor"] / 100,
            "refund_deductions": summary["refund_total_minor"] / 100,
            "dispute_deductions": summary["dispute_lost_total_minor"] / 100,
            "pending": summary["pending_total_minor"] / 100,
            "reserved": summary["reserved_total_minor"] / 100,
            "paid_out": summary["paid_out_total_minor"] / 100,
            "unexplained_diff": summary["unexplained_diff_minor"] / 100,
        })

    return buf.getvalue()


async def export_xlsx(
    db,
    *,
    start_iso: str,
    end_iso: str,
    organization_ids: Optional[List[str]] = None,
) -> bytes:
    """Return XLSX content as bytes. Requires openpyxl."""
    try:
        from openpyxl import Workbook
    except ImportError:
        # Fallback: return CSV bytes with xlsx extension label
        csv_str = await export_csv(db, start_iso=start_iso, end_iso=end_iso, organization_ids=organization_ids)
        return csv_str.encode("utf-8")

    wb = Workbook()
    ws = wb.active
    ws.title = "Reconciliation"
    ws.append(CSV_COLUMNS)

    if organization_ids:
        org_list = organization_ids
    else:
        org_list = [s["organization_id"] async for s in db.settings.find({}, {"organization_id": 1})]

    for org_id in org_list:
        settings = await db.settings.find_one({"organization_id": org_id}) or {}
        summary = await compute_reconciliation_summary(
            db, start_iso=start_iso, end_iso=end_iso, organization_id=org_id,
            base_currency=settings.get("base_currency"),
        )
        ws.append([
            org_id, settings.get("company_name", ""), summary["base_currency"],
            start_iso, end_iso,
            summary["stripe_total_minor"] / 100,
            summary["platform_fee_total_minor"] / 100,
            summary["stripe_fee_total_minor"] / 100,
            summary["wise_fee_total_minor"] / 100,
            summary["wise_funded_total_minor"] / 100,
            summary["refund_total_minor"] / 100,
            summary["dispute_lost_total_minor"] / 100,
            summary["pending_total_minor"] / 100,
            summary["reserved_total_minor"] / 100,
            summary["paid_out_total_minor"] / 100,
            summary["unexplained_diff_minor"] / 100,
        ])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
