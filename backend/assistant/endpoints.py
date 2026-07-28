"""
PLANN Asistan — API router.

- Merchant (admin): kendi organizasyonunun bildirim geçmişi.
- Superadmin: metin havuzu durumu + seed, herhangi bir org için önizleme (dry-run)
  ve gerçek test gönderimi (3 periyot: morning/night/weekly).

Auth deseni financial_endpoints.py ile birebir aynı (JWT decode + rol kontrolü).
"""

import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from .analytics_engine import collect_daily_metrics, collect_week_metrics, service_revenue_between
from .health_engine import build_morning_decision, build_night_decision, build_weekly_decision
from .notification_engine import process_and_notify
from .seed_messages import seed_messages, messages_status, ensure_indexes
from .scenarios import resolve_profile

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Istanbul")
_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "default_karmaşık_bir_secret_key_ekleyin_mutlaka")
_ALGORITHM = "HS256"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)

router = APIRouter(prefix="/api/assistant", tags=["Assistant"], redirect_slashes=False)


def _get_db(request: Request):
    return request.app.db


async def _require_auth(request: Request, token: str = Depends(_oauth2_scheme)):
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
    user["_id"] = str(user["_id"])
    request.state.current_user = user
    return user


async def _require_admin(request: Request, user=Depends(_require_auth)):
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _require_superadmin(request: Request, user=Depends(_require_auth)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


# ---------------------------------------------------------------------------
# Merchant — bildirim geçmişi
# ---------------------------------------------------------------------------
@router.get("/notifications", dependencies=[Depends(_require_admin)])
async def my_notifications(request: Request, limit: int = Query(30, ge=1, le=100)):
    db = _get_db(request)
    org_id = request.state.current_user.get("organization_id", "")
    rows = await db.assistant_notifications.find(
        {"organization_id": org_id}, {"_id": 0},
    ).sort("sent_at", -1).to_list(limit)
    return {"notifications": rows, "count": len(rows)}


# ---------------------------------------------------------------------------
# Superadmin — havuz durumu + seed
# ---------------------------------------------------------------------------
@router.get("/superadmin/messages/status", dependencies=[Depends(_require_superadmin)])
async def sa_messages_status(request: Request):
    return await messages_status(_get_db(request))


@router.post("/superadmin/messages/seed", dependencies=[Depends(_require_superadmin)])
async def sa_messages_seed(request: Request):
    db = _get_db(request)
    await ensure_indexes(db)
    result = await seed_messages(db)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Superadmin — önizleme (dry-run) ve test gönderimi
# ---------------------------------------------------------------------------
async def _compute_packet(db, org_id: str, settings: dict, period: str, date_str: str):
    """Verilen periyot için metrik + karar paketi üretir (bugünün verisiyle)."""
    if period == "morning":
        metrics = await collect_daily_metrics(db, org_id, settings, date_str)
        return metrics, build_morning_decision(metrics)
    if period == "night":
        metrics = await collect_daily_metrics(db, org_id, settings, date_str)
        # Önizlemede baseline'ı basit tut: motivasyon modu (düne göre) yok, 0 baseline.
        packet = build_night_decision(metrics, baseline_revenue=0.0, mode="intelligence")
        return metrics, packet
    if period == "weekly":
        today = datetime.strptime(date_str, "%Y-%m-%d")
        week_start = today - timedelta(days=today.weekday())
        ws, we = week_start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        prev_ws = (week_start - timedelta(days=7)).strftime("%Y-%m-%d")
        prev_we = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        week_metrics = await collect_week_metrics(db, org_id, settings, ws, we)
        prev_service = await service_revenue_between(db, org_id, prev_ws, prev_we)
        prev_avg = round(sum(prev_service.values()), 2)
        return week_metrics, build_weekly_decision(week_metrics, prev_avg, prev_service)
    raise HTTPException(status_code=400, detail="period morning|night|weekly olmalı")


@router.get("/superadmin/preview", dependencies=[Depends(_require_superadmin)])
async def sa_preview(request: Request, org_id: str = Query(...),
                     period: str = Query("morning")):
    db = _get_db(request)
    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0})
    if not settings:
        raise HTTPException(status_code=404, detail="Organization settings not found")
    date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    metrics, packet = await _compute_packet(db, org_id, settings, period, date_str)
    result = await process_and_notify(
        db, org_id, settings, period, metrics, packet, date_str, dry_run=True,
    )
    return {
        "profile": resolve_profile(settings.get("sector")),
        "sector": settings.get("sector"),
        "metrics": metrics,
        "packet": packet,
        "preview": result,
    }


@router.post("/superadmin/test-send", dependencies=[Depends(_require_superadmin)])
async def sa_test_send(request: Request, org_id: str = Query(...),
                       period: str = Query("morning")):
    db = _get_db(request)
    settings = await db.settings.find_one({"organization_id": org_id}, {"_id": 0})
    if not settings:
        raise HTTPException(status_code=404, detail="Organization settings not found")
    date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    metrics, packet = await _compute_packet(db, org_id, settings, period, date_str)
    result = await process_and_notify(
        db, org_id, settings, period, metrics, packet, date_str, dry_run=False,
    )
    return {"ok": result.get("status") == "sent", "result": result}
