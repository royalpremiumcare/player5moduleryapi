"""
Meta Conversions API (CAPI) — Public endpoint.

Frontend, Pixel'i tetikledikten hemen sonra aynı `event_id` ile bu endpoint'e
POST atar. Endpoint, gerçek HTTP gönderimini FastAPI `BackgroundTasks` ile
arka plana atar; istemci akışını bloklamaz.

Auth: gerekli değil (anonim ziyaretçileri de takip ediyoruz).
Rate limit: server.py içindeki global SlowAPI middleware'i tarafından korunur.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, Field

from meta_capi_service import (
    VALID_ACTION_SOURCES,
    get_meta_capi_service,
    split_full_name,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meta", tags=["Meta CAPI"])


async def _try_enrich_from_jwt(request: Request, raw_user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    JWT token varsa kullanıcı email/phone/name bilgilerini user_data'ya ekler.
    Zaten frontend'den gelen değerleri override etmez (sadece eksikleri doldurur).
    Hata olursa sessizce geçer — analytics asla ürün akışını kırmamalı.
    """
    try:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return raw_user_data
        token = auth_header[7:]
        if not token:
            return raw_user_data

        from jose import jwt as jose_jwt, JWTError
        import os
        secret = os.getenv("JWT_SECRET_KEY", "")
        algorithm = "HS256"
        if not secret:
            return raw_user_data

        payload = jose_jwt.decode(token, secret, algorithms=[algorithm])
        username = payload.get("sub")  # email
        org_id = payload.get("org_id")
        full_name = payload.get("full_name")
        user_id = payload.get("user_id")

        # Email
        if username and not raw_user_data.get("em"):
            raw_user_data["em"] = username

        # Full name → fn + ln
        if full_name:
            name_parts = split_full_name(full_name)
            if name_parts.get("fn") and not raw_user_data.get("fn"):
                raw_user_data["fn"] = name_parts["fn"]
            if name_parts.get("ln") and not raw_user_data.get("ln"):
                raw_user_data["ln"] = name_parts["ln"]

        # Phone — settings tablosundan çek (JWT'de yok)
        if org_id and not raw_user_data.get("ph"):
            try:
                db = getattr(request.app, "db", None)
                if db:
                    org_settings = await db.settings.find_one(
                        {"organization_id": org_id},
                        {"support_phone": 1, "_id": 0},
                    )
                    if org_settings and org_settings.get("support_phone"):
                        raw_user_data["ph"] = org_settings["support_phone"]
            except Exception:
                pass

        # external_id
        if user_id and not raw_user_data.get("external_id"):
            raw_user_data["external_id"] = str(user_id)

    except Exception as exc:
        logger.debug(f"[meta_capi] JWT enrichment atlandı: {exc}")

    return raw_user_data


# ---------------------------------------------------------------------------
# Pydantic şemaları
# ---------------------------------------------------------------------------
class MetaUserData(BaseModel):
    """
    Hashlenmemiş raw değerler. Backend, gönderim öncesi normalize+SHA256 yapar.
    Tüm alanlar opsiyonel — boş geçilenler payload'a eklenmez.
    """
    contact_email: Optional[str] = None        # → em
    contact_phone: Optional[str] = None        # → ph (90xxxxxxxxxx formatına normalize edilir)
    contact_name: Optional[str] = None         # → fn + ln (otomatik split)
    first_name: Optional[str] = None           # → fn (öncelikli)
    last_name: Optional[str] = None            # → ln (öncelikli)
    external_id: Optional[str] = None          # ör. user_id
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class MetaCustomData(BaseModel):
    """
    Meta'nın `custom_data` alanına 1:1 düşer (camelCase yerine snake değil — Meta).
    """
    content_name: Optional[str] = None         # işletme adı veya ürün adı
    content_category: Optional[str] = None
    content_ids: Optional[list[str]] = None
    content_type: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = "TRY"
    num_items: Optional[int] = None
    order_id: Optional[str] = None
    predicted_ltv: Optional[float] = None
    status: Optional[str] = None


class MetaEventRequest(BaseModel):
    """
    Frontend → backend payload'u.
    `event_id` UUID — frontend Pixel.track çağrısında verdiği ile aynı olmalı.
    """
    event_name: str = Field(..., min_length=1, max_length=64)
    event_id: Optional[str] = None
    event_time: Optional[int] = None
    event_source_url: Optional[str] = None
    action_source: str = "website"
    user_data: Optional[MetaUserData] = None
    custom_data: Optional[MetaCustomData] = None
    fbp: Optional[str] = None
    fbc: Optional[str] = None
    test_event_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _client_ip(request: Request) -> Optional[str]:
    """Cloudflare/Nginx zincirinde gerçek IP'yi yakalar."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _build_raw_user_data(ud: Optional[MetaUserData]) -> Dict[str, Any]:
    """MetaUserData → service'in beklediği hash öncesi raw dict."""
    if ud is None:
        return {}

    fn = (ud.first_name or "").strip()
    ln = (ud.last_name or "").strip()
    if (not fn or not ln) and ud.contact_name:
        split = split_full_name(ud.contact_name)
        if not fn:
            fn = split["fn"]
        if not ln:
            ln = split["ln"]

    raw: Dict[str, Any] = {}
    if ud.contact_email:
        raw["em"] = ud.contact_email
    if ud.contact_phone:
        raw["ph"] = ud.contact_phone
    if fn:
        raw["fn"] = fn
    if ln:
        raw["ln"] = ln
    if ud.country:
        raw["country"] = ud.country
    if ud.city:
        raw["ct"] = ud.city
    if ud.state:
        raw["st"] = ud.state
    if ud.zip_code:
        raw["zp"] = ud.zip_code
    return raw


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/event")
async def meta_capi_event(
    payload: MetaEventRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Frontend'den gelen event'i Meta CAPI'a asenkron yollar.
    Yanıt anında döner; gerçek HTTP gönderimi BackgroundTasks içinde yapılır.

    Frontend, aynı `event_id` ile Pixel.track() de çağırmalı → Meta dedupe.
    """
    if payload.action_source not in VALID_ACTION_SOURCES:
        payload.action_source = "website"

    event_id = payload.event_id or str(uuid.uuid4())
    event_time = payload.event_time or int(time.time())

    raw_user_data = _build_raw_user_data(payload.user_data)
    # JWT'den gelen kullanıcı bilgileriyle zenginleştir (eksik alanları doldur)
    raw_user_data = await _try_enrich_from_jwt(request, raw_user_data)
    external_id = raw_user_data.pop("external_id", None) or (payload.user_data.external_id if payload.user_data else None)
    custom_data = payload.custom_data.model_dump(exclude_none=True) if payload.custom_data else None

    svc = get_meta_capi_service()
    background_tasks.add_task(
        svc.send_event,
        event_name=payload.event_name,
        event_id=event_id,
        event_time=event_time,
        event_source_url=payload.event_source_url,
        action_source=payload.action_source,
        user_data=raw_user_data,
        custom_data=custom_data,
        client_ip=_client_ip(request),
        client_user_agent=request.headers.get("user-agent"),
        fbp=payload.fbp,
        fbc=payload.fbc,
        external_id=external_id,
        test_event_code=payload.test_event_code,
    )

    return {
        "ok": True,
        "event_id": event_id,
        "event_name": payload.event_name,
        "queued": True,
        "capi_enabled": svc.enabled,
    }


@router.get("/health")
async def meta_capi_health() -> Dict[str, Any]:
    """Servisin enabled (token+pixel set) olup olmadığını anlamak için."""
    svc = get_meta_capi_service()
    return {
        "enabled": svc.enabled,
        "api_version": svc.api_version,
        "pixel_id_present": bool(svc.pixel_id),
    }
