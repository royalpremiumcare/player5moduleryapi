"""
Bulk session idempotency — canonical payload hash for POST /appointments/bulk-session.

Tek kaynak: server bu modülü kullanır; pytest burayı doğrudan import eder (server yüklenmez).
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional

from pydantic import BaseModel


class SessionSlot(BaseModel):
    date: str
    time: str
    staff_member_id: Optional[str] = None


class BulkSessionCreate(BaseModel):
    customer_name: str
    phone: str
    service_id: str
    staff_member_id: Optional[str] = None
    notes: str = ""
    session_group_id: Optional[str] = None
    starting_session_number: int = 1
    session_total: Optional[int] = None
    sessions: List[SessionSlot]


def canonical_bulk_session_hash(bulk: BulkSessionCreate) -> str:
    """Aynı anlamlı istek için stabil hash (sıra, boşluk, JSON anahtar sırası normalize)."""
    d = bulk.model_dump()
    d["customer_name"] = (d.get("customer_name") or "").strip()
    d["phone"] = (d.get("phone") or "").strip()
    d["notes"] = d.get("notes") or ""
    d["service_id"] = (d.get("service_id") or "").strip()
    d["staff_member_id"] = d.get("staff_member_id") or None
    d["session_group_id"] = d.get("session_group_id") or None
    d["starting_session_number"] = int(d.get("starting_session_number") or 1)
    d["session_total"] = d.get("session_total")
    raw_sess = d.get("sessions") or []
    norm = []
    for s in raw_sess:
        sid = (s.get("staff_member_id") or "").strip() or None
        norm.append(
            {
                "date": (s.get("date") or "").strip(),
                "time": (s.get("time") or "").strip(),
                "staff_member_id": sid,
            }
        )
    norm.sort(key=lambda x: (x["date"], x["time"], x.get("staff_member_id") or ""))
    d["sessions"] = norm
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
