"""
GET /appointments — refund_eligible bayrağı (merchant Stripe + session_group).
Test edilebilir saf yardımcılar.
"""

from __future__ import annotations

from typing import Any, Dict, List, MutableSequence, Set

REFUNDABLE_MERCHANT_STATES = ("captured", "settled", "available")


def session_group_ids_from_merchant_transactions(
    transactions: List[Dict[str, Any]],
) -> Set[str]:
    """
    Mongo sorgusu ile dönen merchant_transactions kayıtlarından
    iade için uygun session_group_id kümesi (sunucu find filtresi ile uyumlu).
    """
    out: Set[str] = set()
    for t in transactions:
        gid = t.get("session_group_id")
        if gid:
            out.add(gid)
    return out


def attach_refund_eligible(
    appointments: MutableSequence[Dict[str, Any]],
    eligible_group_ids: Set[str],
) -> None:
    """Her randevuya refund_eligible yazar (yerinde mutasyon)."""
    for a in appointments:
        gid = a.get("session_group_id")
        a["refund_eligible"] = bool(gid and gid in eligible_group_ids)
