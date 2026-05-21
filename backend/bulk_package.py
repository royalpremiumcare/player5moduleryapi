"""
Bulk package creation — Pydantic model for POST /appointments/bulk-package.

Plan 12.1 (atomic transaction wrapper) için tek-bir-call'da 1..N seans paketi.
/bulk-session ile aynı core handler'ı kullanır (kod duplikasyonu yok). Bu modül
yalnızca request payload şemasını içerir.

Idempotency stratejisi (Plan 12.3):
- session_group_id frontend-generated (zorunlu, UUID).
- Backend aynı org_id + session_group_id ile var olan paketi no-op success
  olarak döndürür (retry / double-submit güvenliği).
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from bulk_session_idempotency import SessionSlot


class BulkPackageCreate(BaseModel):
    customer_name: str
    phone: str
    service_id: str
    staff_member_id: Optional[str] = None
    notes: str = ""
    # Frontend-generated UUID; idempotency anahtarı (Plan 12.3).
    # Backward compatibility: production frontend'in eski sürümleri henüz
    # bu endpoint'i çağırmadığı için None gelmesi pratikte beklenmez,
    # yine de Optional bırakıyoruz → handler'da boş olursa yeni UUID üretilir.
    session_group_id: Optional[str] = None
    # Toplam seans sayısı (genelde len(sessions) ile aynı, frontend'in
    # service.session_count'tan gelen değeri). Belirtilmezse handler
    # otomatik len(sessions) kullanır.
    session_total: Optional[int] = None
    sessions: List[SessionSlot]
    # SESSION_PACKAGE WhatsApp template'i gönderilmesini geçici olarak
    # devre dışı bırakmak için (örn. test akışları). Production default: False.
    skip_confirmation_whatsapp: bool = False
