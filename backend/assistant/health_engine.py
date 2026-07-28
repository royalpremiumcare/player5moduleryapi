"""
PLANN Asistan — Business Health Engine (Katman 2)

Analytics'ten gelen ham metrikleri işler, günü SKORLAR ve bir "karar paketi"
üretir. Karar paketi Notification Engine'e teslim edilir.

Karar paketi (JSON) şeması:
{
  "scenario": "night_revenue",        # 12 senaryodan biri (metin seçimi buna göre)
  "day_context": "revenue_day",       # insan-okur bağlam etiketi (log/superadmin)
  "health_score": 88,                 # 0-100 günün sağlık skoru
  "confidence_score": 95,             # 0-100 kararın güven skoru
  "primary_metric": "revenue_up_24",  # kararı tetikleyen ana metrik (log)
  "insight_reason": "protez_tirnak",  # "neden" içgörüsü (log)
  "mode": "intelligence" | "motivation",
  "gap_details": {...} | None,        # sabah senaryolarında boşluk bilgisi
  "insight": {"service_name": "...", "rate_pct": 28}  # haftalıkta {hizmet_adi}/{oran}
}
"""

import logging

from .scenarios import (
    Scenario,
    FULLNESS_BUSY_PCT,
    GAP_MIN_MINUTES,
    GROWTH_NEW_CUSTOMERS,
    BOOMERANG_MIN,
    LOYALTY_RETURNING_FRACTION,
    LOYALTY_MIN_CUSTOMERS,
    REVENUE_UP_PCT,
    WEEKLY_RECORD_PCT,
    WEEKLY_ALARM_PCT,
)

logger = logging.getLogger(__name__)


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(round(v))))


def _pct_change(current: float, baseline: float):
    if baseline and baseline > 0:
        return (current - baseline) / baseline * 100.0
    return None


# ---------------------------------------------------------------------------
# Sabah brifingi (08:30)
# ---------------------------------------------------------------------------
def build_morning_decision(metrics: dict) -> dict:
    total = metrics.get("total_appointments", 0)
    fullness = metrics.get("fullness_pct", 0.0)
    has_gap = metrics.get("has_gap", False)
    gap_type = metrics.get("gap_type")

    gap_details = {
        "has_gap": has_gap,
        "gap_start": metrics.get("gap_start"),
        "gap_end": metrics.get("gap_end"),
        "gap_minutes": metrics.get("gap_minutes", 0),
        "gap_type": gap_type,
        "lead_time_minutes": metrics.get("lead_time_minutes"),
    }

    # Tamamen boş gün → pazarlama CTA'sı için late_gap (bütün gün boşluk).
    if total == 0:
        gap_details.update({
            "has_gap": True,
            "gap_start": metrics.get("open_time"),
            "gap_end": metrics.get("close_time"),
            "gap_type": "late",
        })
        scenario = Scenario.MORNING_LATE_GAP.value
        day_context = "empty_day"
    elif fullness >= FULLNESS_BUSY_PCT:
        scenario = Scenario.MORNING_BUSY.value
        day_context = "busy_day"
    elif has_gap and metrics.get("gap_minutes", 0) >= GAP_MIN_MINUTES:
        if gap_type == "early":
            scenario = Scenario.MORNING_EARLY_GAP.value
            day_context = "early_gap_day"
        else:
            scenario = Scenario.MORNING_LATE_GAP.value
            day_context = "late_gap_day"
    else:
        scenario = Scenario.MORNING_NORMAL.value
        day_context = "normal_day"

    return {
        "scenario": scenario,
        "day_context": day_context,
        "health_score": _clamp(fullness),
        "confidence_score": 90 if total > 0 else 70,
        "primary_metric": f"fullness_{int(fullness)}pct",
        "insight_reason": gap_type or "capacity",
        "mode": None,
        "gap_details": gap_details,
        "insight": {},
    }


# ---------------------------------------------------------------------------
# Gece kapanışı (22:00)
# ---------------------------------------------------------------------------
def build_night_decision(metrics: dict, baseline_revenue: float, mode: str) -> dict:
    revenue = metrics.get("revenue", 0.0)
    new_cust = metrics.get("new_customers", 0)
    boomerang = metrics.get("boomerang_customers", 0)
    returning_frac = metrics.get("returning_fraction", 0.0)
    unique = metrics.get("unique_customers", 0)

    change = _pct_change(revenue, baseline_revenue)
    confidence = 95 if mode == "intelligence" else 70

    # Öncelik: boomerang > growth > revenue > loyalty > honest
    if boomerang >= BOOMERANG_MIN:
        scenario = Scenario.NIGHT_BOOMERANG.value
        day_context = "boomerang_day"
        primary = f"boomerang_{boomerang}"
    elif new_cust >= GROWTH_NEW_CUSTOMERS:
        scenario = Scenario.NIGHT_GROWTH.value
        day_context = "growth_day"
        primary = f"new_customers_{new_cust}"
    elif (change is not None and change >= REVENUE_UP_PCT) or \
         (baseline_revenue <= 0 and revenue > 0 and unique >= 3):
        scenario = Scenario.NIGHT_REVENUE.value
        day_context = "revenue_day"
        primary = f"revenue_up_{int(change)}" if change is not None else "revenue_strong"
    elif returning_frac >= LOYALTY_RETURNING_FRACTION and unique >= LOYALTY_MIN_CUSTOMERS:
        scenario = Scenario.NIGHT_LOYALTY.value
        day_context = "loyalty_day"
        primary = f"returning_{int(returning_frac * 100)}pct"
    else:
        scenario = Scenario.NIGHT_HONEST.value
        day_context = "honest_day"
        primary = f"revenue_{int(revenue)}"

    if change is not None:
        health = _clamp(50 + change)
    else:
        health = 60 if revenue > 0 else 40

    return {
        "scenario": scenario,
        "day_context": day_context,
        "health_score": health,
        "confidence_score": confidence,
        "primary_metric": primary,
        "insight_reason": day_context,
        "mode": mode,
        "gap_details": None,
        "insight": {},
    }


# ---------------------------------------------------------------------------
# Haftalık CEO özeti (Pazar 22:00)
# ---------------------------------------------------------------------------
def build_weekly_decision(week_metrics: dict, prev_avg_revenue: float,
                          prev_service_revenue: dict) -> dict:
    revenue = week_metrics.get("revenue", 0.0)
    change = _pct_change(revenue, prev_avg_revenue)

    if change is not None and change >= WEEKLY_RECORD_PCT:
        scenario = Scenario.WEEKLY_RECORD.value
        day_context = "weekly_record"
    elif change is not None and change <= WEEKLY_ALARM_PCT:
        scenario = Scenario.WEEKLY_ALARM.value
        day_context = "weekly_alarm"
    else:
        scenario = Scenario.WEEKLY_NORMAL.value
        day_context = "weekly_normal"

    # "Neden" içgörüsü: bu hafta vs geçen hafta en çok değişen hizmet.
    insight = _weekly_service_insight(
        week_metrics.get("service_revenue") or {},
        prev_service_revenue or {},
        direction="up" if scenario == Scenario.WEEKLY_RECORD.value else
                  ("down" if scenario == Scenario.WEEKLY_ALARM.value else "up"),
    )

    health = _clamp(50 + change) if change is not None else 55
    confidence = 90 if (prev_avg_revenue or 0) > 0 else 65

    return {
        "scenario": scenario,
        "day_context": day_context,
        "health_score": health,
        "confidence_score": confidence,
        "primary_metric": f"weekly_change_{int(change)}" if change is not None else "weekly_flat",
        "insight_reason": insight.get("service_name") or "n/a",
        "mode": "intelligence",
        "gap_details": None,
        "insight": insight,
    }


def _weekly_service_insight(this_week: dict, last_week: dict, direction: str) -> dict:
    """
    En çok DEĞİŞEN hizmeti bulur → {service_name, rate_pct}.
    direction='up'  → en çok artan (rekor/normal için)
    direction='down'→ en çok azalan (alarm için)
    """
    best_name = None
    best_rate = 0
    names = set(this_week.keys()) | set(last_week.keys())
    for name in names:
        cur = this_week.get(name, 0.0)
        prev = last_week.get(name, 0.0)
        if prev <= 0:
            # Geçen hafta yoksa: yeni/patlayan hizmet → yalnızca 'up' yönünde anlamlı.
            if direction == "up" and cur > 0:
                rate = 100
            else:
                continue
        else:
            rate = (cur - prev) / prev * 100.0
        if direction == "up" and rate > best_rate:
            best_rate, best_name = rate, name
        elif direction == "down" and rate < best_rate:
            best_rate, best_name = rate, name

    if best_name is None:
        # Fallback: bu haftanın en yüksek cirolu hizmeti, oran 0.
        if this_week:
            best_name = max(this_week, key=this_week.get)
        elif last_week:
            best_name = max(last_week, key=last_week.get)
        best_rate = 0

    return {"service_name": best_name or "hizmetleriniz", "rate_pct": abs(int(round(best_rate)))}
