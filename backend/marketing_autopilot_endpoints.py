"""
Pazarlama Otopilotu — API router (merchant admin).

- GET  /api/marketing/autopilot  : otopilot durumu + hizmet listesi (gün ayarlarıyla)
                                    + işletme adı/slug (canlı önizleme için) + istatistik.
- PUT  /api/marketing/autopilot  : otopilotu aç/kapat ve hizmet-bazlı gün sürelerini
                                    kaydet. Otopilot ilk kez açıldığında enabled_at set
                                    edilir (yalnızca o andan sonra tamamlananlar kuyruğa girer).

Auth deseni assistant/endpoints.py ile aynı (JWT decode + rol kontrolü).
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Dict, Optional

from marketing_autopilot import (
    DEFAULT_REACTIVATION_DAYS,
    clamp_days,
    get_org_stats,
    ensure_indexes,
)

logger = logging.getLogger(__name__)

_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "default_karmaşık_bir_secret_key_ekleyin_mutlaka")
_ALGORITHM = "HS256"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)

router = APIRouter(prefix="/api/marketing/autopilot", tags=["Marketing Autopilot"], redirect_slashes=False)


def _get_db(request: Request):
    return request.app.db


async def _require_admin(request: Request, token: str = Depends(_oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = _get_db(request)
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class AutopilotUpdate(BaseModel):
    enabled: bool
    days: Optional[Dict[str, int]] = None


@router.get("")
async def get_autopilot(request: Request, user=Depends(_require_admin)):
    db = _get_db(request)
    org_id = user.get("organization_id")

    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    days_map = settings.get("marketing_autopilot_days") or {}

    services = await db.services.find(
        {"organization_id": org_id, "is_active": {"$ne": False}}, {"_id": 0}
    ).sort("order", 1).to_list(1000)

    svc_out = [{
        "id": s.get("id"),
        "name": s.get("name"),
        "duration": s.get("duration", 30),
        "days": clamp_days(days_map.get(s.get("id")), DEFAULT_REACTIVATION_DAYS),
    } for s in services]

    stats = await get_org_stats(db, org_id)

    sector = settings.get("sector")
    try:
        from whatsapp_service import sector_template_key
        sector_key = sector_template_key(sector)
    except Exception:
        sector_key = "genel"

    return {
        "enabled": bool(settings.get("marketing_autopilot_enabled", False)),
        "enabled_at": settings.get("marketing_autopilot_enabled_at"),
        "default_days": DEFAULT_REACTIVATION_DAYS,
        "company_name": settings.get("company_name") or "İşletmeniz",
        "slug": settings.get("slug"),
        "sector": sector,
        "sector_key": sector_key,
        "services": svc_out,
        "stats": stats,
    }


@router.put("")
async def update_autopilot(request: Request, body: AutopilotUpdate, user=Depends(_require_admin)):
    db = _get_db(request)
    org_id = user.get("organization_id")

    current = await db.settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    was_enabled = bool(current.get("marketing_autopilot_enabled", False))

    update = {"marketing_autopilot_enabled": bool(body.enabled)}

    # Gün haritası: gelen değerler MIN/MAX aralığına sıkıştırılır.
    if body.days is not None:
        clean = {}
        for sid, d in body.days.items():
            if sid:
                clean[str(sid)] = clamp_days(d, DEFAULT_REACTIVATION_DAYS)
        update["marketing_autopilot_days"] = clean

    # İlk kez açılıyorsa enabled_at damgala (geçmiş randevu patlamasını önler).
    if body.enabled and not was_enabled:
        update["marketing_autopilot_enabled_at"] = datetime.now(timezone.utc).isoformat()

    await db.settings.update_one(
        {"organization_id": org_id}, {"$set": update}, upsert=True,
    )
    # Görev kuyruğu indekslerinin var olduğundan emin ol (ilk kullanımda).
    try:
        await ensure_indexes(db)
    except Exception:
        pass

    return {"status": "ok", "enabled": bool(body.enabled)}
