"""SaaS faturalama yaşam döngüsü e-postaları.

Üç tetik:
  - trial_ended   — 7 günlük deneme bitti, henüz ücretli plan yok
  - grace         — ücretli yenileme başarısız, 3 günlük tolerans başladı
  - suspended     — grace bitti, hesap duraklatıldı

Geçmişe gitmeme kuralı
----------------------
``BILLING_LIFECYCLE_EMAIL_EPOCH`` (env, ISO-8601) tarihinden ÖNCE bitmiş
trial / grace / suspend olaylarına mail gitmez. Bu özellik canlıya alındığı
andan itibaren oluşan bitişler gönderilir; eski denemesi bitmiş işletmeler
toplanmaz.

Idempotency: organization_plans üzerinde
``trial_ended_email_sent`` / ``grace_email_sent`` / ``suspended_email_sent``.

COPY: metinleri Fatih verecek — aşağıdaki TR/EN dict'lerden değiştirilir.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

# Bu özellik 25 Ağustos 2026 (~22:00 UTC) civarında açıldı.
# Env ile override: BILLING_LIFECYCLE_EMAIL_EPOCH=2026-08-24T22:00:00+00:00
_DEFAULT_EPOCH = "2026-08-24T22:00:00+00:00"
GRACE_DAYS = 3

# Trial biten / suspended CTA — native'de uygulamayı, web'de abonelik sayfasını açar
CTA_SUBSCRIBE_TR = os.getenv(
    "BILLING_EMAIL_CTA_TR",
    "https://plannapp.co/api/app/open?web=https%3A%2F%2Fplannapp.co%2F%23%2Fsubscribe",
)
CTA_SUBSCRIBE_EN = os.getenv(
    "BILLING_EMAIL_CTA_EN",
    "https://plannapp.co.uk/api/app/open?web=https%3A%2F%2Fplannapp.co.uk%2F%23%2Fsubscribe",
)


def billing_email_epoch() -> datetime:
    raw = (os.getenv("BILLING_LIFECYCLE_EMAIL_EPOCH") or _DEFAULT_EPOCH).strip()
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_plan_dt(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def paid_deadline(plan_doc: dict) -> Optional[datetime]:
    for key in ("next_billing_date", "next_payment_date", "quota_reset_date"):
        deadline = parse_plan_dt((plan_doc or {}).get(key))
        if deadline:
            return deadline
    return None


def _is_canceled(plan_doc: dict) -> bool:
    return str((plan_doc or {}).get("status") or "").lower() in ("canceled", "cancelled")


def saas_invoice_subscription_id(inv) -> Optional[str]:
    """Stripe 2025-11+ faturalarında `invoice.subscription` yok.

    Id şurada: parent.subscription_details.subscription
    (yedek: lines[].parent.subscription_item_details.subscription)
    """
    if inv is None:
        return None

    def _g(obj, key):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        try:
            return obj[key]
        except Exception:
            return getattr(obj, key, None)

    sub = _g(inv, "subscription")
    if isinstance(sub, dict):
        sub = sub.get("id")
    if sub:
        return str(sub)
    parent = _g(inv, "parent") or {}
    sd = _g(parent, "subscription_details") if parent else None
    sub = _g(sd, "subscription") if sd else None
    if sub:
        return str(sub)
    lines = _g(inv, "lines") or {}
    data = _g(lines, "data") if not isinstance(lines, list) else lines
    if isinstance(data, list):
        for ln in data:
            lp = _g(ln, "parent") or {}
            sid = _g(lp, "subscription_item_details") if lp else None
            sub = _g(sid, "subscription") if sid else None
            if sub:
                return str(sub)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# COPY — buradan değiştirilir (TR / EN)
# ═══════════════════════════════════════════════════════════════════════════

TRIAL_ENDED_COPY = {
    "tr": {
        "subject": "PLANN deneme süreniz sona erdi",
        "badge": "Deneme",
        "statement": "7 günlük ücretsiz denemeniz tamamlandı.",
        "paragraphs": [
            "Merhaba {name},",
            "PLANN deneme süreniz sona erdi. Randevu, müşteri ve takvim verileriniz güvende; aboneliğinizi başlattığınız anda kaldığınız yerden devam edersiniz.",
            "İşletmenizi kesintisiz yönetmeye devam etmek için bir paket seçmeniz yeterli.",
        ],
        "button": "Aboneliği başlat",
    },
    "en": {
        "subject": "Your PLANN free trial has ended",
        "badge": "Trial",
        "statement": "Your 7-day free trial is complete.",
        "paragraphs": [
            "Hello {name},",
            "Your PLANN trial has ended. Your appointments, customers and calendar are safe — the moment you start a subscription you continue exactly where you left off.",
            "Choose a plan to keep running your business without interruption.",
        ],
        "button": "Start subscription",
    },
}

# Mevcut canlı metin (invoice.payment_failed). Marka şablonuna taşındı.
GRACE_COPY = {
    "tr": {
        "subject": "PLANN Abonelik Yenilemeniz Hakkında Önemli Bilgilendirme",
        "badge": "Ödeme",
        "statement": "Yenileme ödemeniz tamamlanamadı.",
        "paragraphs": [
            "Merhaba {name},",
            "PLANN abonelik yenileme işleminiz bankanız/kartınız tarafından reddedildiği için tamamlanamadı.",
            "İşlemlerinizin aksamaması için <strong>3 günlük tolerans süreniz</strong> başlatılmıştır. Bu süreçte randevu almaya devam edebilirsiniz; ancak 3 gün sonunda ödeme tamamlanmazsa sisteminiz geçici olarak kilitlenecektir.",
            "Bakiyenizi kontrol ettikten sonra aşağıdaki güvenli bağlantı üzerinden ödemenizi manuel olarak anında tamamlayabilirsiniz.",
        ],
        "button": "Ödememi güvenle tamamla",
        "note": "Teşekkürler,<br/>PLANN Ekibi",
    },
    "en": {
        "subject": "Important update about your PLANN subscription renewal",
        "badge": "Payment",
        "statement": "Your renewal payment could not be completed.",
        "paragraphs": [
            "Hello {name},",
            "Your PLANN subscription renewal could not be completed because it was declined by your bank or card.",
            "To keep things running we have started a <strong>3-day grace period</strong>. You can keep taking appointments during this time; if payment is not completed within 3 days your account will be temporarily locked.",
            "After checking your balance you can complete the payment instantly via the secure link below.",
        ],
        "button": "Complete my payment securely",
        "note": "Thank you,<br/>The PLANN Team",
    },
}

SUSPENDED_COPY = {
    "tr": {
        "subject": "PLANN hesabınız geçici olarak duraklatıldı",
        "badge": "Hesap",
        "statement": "Ödeme tolerans süreniz doldu.",
        "paragraphs": [
            "Merhaba {name},",
            "3 günlük ödeme tolerans süreniz sona erdiği için PLANN hesabınız geçici olarak duraklatıldı.",
            "Ödemenizi tamamladığınız anda sisteminiz yeniden açılır; randevu ve müşteri verileriniz olduğu gibi korunur.",
        ],
        "button": "Ödemeyi tamamla",
    },
    "en": {
        "subject": "Your PLANN account has been paused",
        "badge": "Account",
        "statement": "Your payment grace period has ended.",
        "paragraphs": [
            "Hello {name},",
            "Your PLANN account has been temporarily paused because the 3-day payment grace period has ended.",
            "As soon as you complete payment, your account reopens. Your appointments and customer data stay exactly as they are.",
        ],
        "button": "Complete payment",
    },
}


def _copy_for(table: dict, lang: str) -> dict:
    return table.get("en" if lang == "en" else "tr")


def _fill_name(paragraphs: list, full_name: str, lang: str) -> list:
    fallback = "there" if lang == "en" else ""
    name = (full_name or "").strip() or fallback
    return [p.replace("{name}", name).replace("Merhaba ,", "Merhaba,").replace("Hello ,", "Hello,") for p in paragraphs]


def build_trial_ended_email(brand_email: Callable, lang: str, full_name: str, cta_url: str) -> tuple[str, str]:
    c = _copy_for(TRIAL_ENDED_COPY, lang)
    html = brand_email(
        lang=lang,
        badge=c["badge"],
        statement=c["statement"],
        paragraphs=_fill_name(c["paragraphs"], full_name, lang),
        button={"label": c["button"], "url": cta_url},
    )
    return c["subject"], html


def build_grace_period_email(
    brand_email: Callable,
    lang: str,
    full_name: str,
    pay_url: str,
) -> tuple[str, str]:
    c = _copy_for(GRACE_COPY, lang)
    html = brand_email(
        lang=lang,
        badge=c["badge"],
        statement=c["statement"],
        paragraphs=_fill_name(c["paragraphs"], full_name, lang),
        note=c.get("note") or "",
        button={"label": c["button"], "url": pay_url} if pay_url else None,
    )
    return c["subject"], html


def build_suspended_email(brand_email: Callable, lang: str, full_name: str, pay_url: str) -> tuple[str, str]:
    c = _copy_for(SUSPENDED_COPY, lang)
    html = brand_email(
        lang=lang,
        badge=c["badge"],
        statement=c["statement"],
        paragraphs=_fill_name(c["paragraphs"], full_name, lang),
        button={"label": c["button"], "url": pay_url} if pay_url else None,
    )
    return c["subject"], html


# ═══════════════════════════════════════════════════════════════════════════
# Eligibility — saf fonksiyonlar (geçmişe gitmeme + idempotency)
# ═══════════════════════════════════════════════════════════════════════════

def is_trial_ended_eligible(plan_doc: dict, now: datetime, epoch: datetime) -> bool:
    """Sadece epoch'tan sonra biten, hâlâ trial olan, henüz mail gitmemiş org."""
    doc = plan_doc or {}
    if doc.get("plan_id", "tier_trial") != "tier_trial":
        return False
    if _is_canceled(doc):
        return False
    if doc.get("trial_ended_email_sent") is True:
        return False
    # Ücretli abonelikten düşmüş hesaplara "deneme bitti" maili gitmesin
    if doc.get("suspended_email_sent") is True:
        return False
    if doc.get("stripe_subscription_id") or doc.get("subscription_id"):
        return False
    trial_end = parse_plan_dt(doc.get("trial_end_date"))
    if not trial_end:
        return False
    return epoch <= trial_end <= now


def is_grace_eligible(plan_doc: dict, now: datetime, epoch: datetime, grace_days: int = GRACE_DAYS) -> bool:
    """Ücretli plan, deadline epoch'tan sonra geçti, hâlâ 3 günlük pencerede."""
    doc = plan_doc or {}
    if doc.get("plan_id", "tier_trial") == "tier_trial":
        return False
    if _is_canceled(doc):
        return False
    if doc.get("grace_email_sent") is True:
        return False
    deadline = paid_deadline(doc)
    if not deadline:
        return False
    if deadline < epoch:
        return False
    grace_end = deadline + timedelta(days=grace_days)
    return deadline < now <= grace_end


def is_suspended_eligible(plan_doc: dict, now: datetime, epoch: datetime, grace_days: int = GRACE_DAYS) -> bool:
    """Grace maili gerçekten gittikten sonra, grace bitişi epoch'tan sonra olan ücretli plan."""
    doc = plan_doc or {}
    if doc.get("plan_id", "tier_trial") == "tier_trial":
        return False
    if _is_canceled(doc):
        return False
    if doc.get("suspended_email_sent") is True:
        return False
    # Ödeme fail'i olmadan (sadece tarih geçti diye) askı maili gitmesin
    if doc.get("grace_email_sent") is not True:
        return False
    if doc.get("grace_email_skipped") == "historical":
        return False
    deadline = paid_deadline(doc)
    if not deadline:
        return False
    grace_end = deadline + timedelta(days=grace_days)
    if grace_end < epoch:
        return False
    return now > grace_end


def is_historical_trial(plan_doc: dict, epoch: datetime) -> bool:
    doc = plan_doc or {}
    if doc.get("plan_id", "tier_trial") != "tier_trial":
        return False
    if doc.get("trial_ended_email_sent") is True:
        return False
    trial_end = parse_plan_dt(doc.get("trial_end_date"))
    return bool(trial_end and trial_end < epoch)


def is_historical_grace(plan_doc: dict, now: datetime, epoch: datetime) -> bool:
    """Epoch'tan önce yenileme tarihi geçmiş ücretli plan — flag bas, mail atma."""
    doc = plan_doc or {}
    if doc.get("plan_id", "tier_trial") == "tier_trial":
        return False
    if doc.get("grace_email_sent") is True:
        return False
    deadline = paid_deadline(doc)
    return bool(deadline and deadline < epoch and deadline < now)


def cta_for_lang(lang: str, override_url: Optional[str] = None) -> str:
    if override_url:
        return override_url
    return CTA_SUBSCRIBE_EN if lang == "en" else CTA_SUBSCRIBE_TR
