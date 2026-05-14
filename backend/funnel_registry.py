"""
Funnel Event Registry — Strict Ownership

Aktivasyon ve kritik dropoff event'lerinin TEK kaynak listesi.
Her event'in tek bir sahibi vardır:
  - "frontend": Tarayıcıdan PostHog `capture()` + `POST /api/funnel/event` ile gönderilir.
  - "webhook":  Backend webhook handler'ından PostHog Python SDK + MongoDB ledger'a yazılır.

Çift sayım imkânsızdır: aynı event hem frontend hem webhook'tan emit edilmez.
Test (`test_funnel_ownership.py`) registry ile kod arasındaki tutarlılığı doğrular.
"""

from typing import Dict, Literal

# ---------------------------------------------------------------------------
# EVENT REGISTRY — sadece bu listede tanımlı event'ler kabul edilir
# ---------------------------------------------------------------------------
EVENT_REGISTRY: Dict[str, Literal["frontend", "webhook"]] = {
    # Signup funnel
    "signup_form_started": "frontend",
    "signup_completed": "frontend",
    # Aha activation funnel
    "aha_spotlight_shown": "frontend",
    "aha_button_clicked": "frontend",
    "aha_appointment_created": "frontend",
    "aha_wa_failed": "frontend",
    "aha_retry_clicked": "frontend",
    "aha_skipped": "frontend",
    "aha_target_missing": "frontend",
    "aha_celebration_dismissed": "frontend",
    "aha_modal_dismissed_without_choice": "frontend",
    # Tour
    "tour_step_viewed": "frontend",
    "tour_completed": "frontend",
    "tour_skipped": "frontend",
    # First real appointment (post-Aha)
    "first_real_appointment_created": "frontend",
    # Subscription
    "subscription_checkout_started": "frontend",
    "subscription_completed": "webhook",
}

VALID_EVENT_NAMES = frozenset(EVENT_REGISTRY.keys())
FRONTEND_OWNED_EVENTS = frozenset(
    name for name, owner in EVENT_REGISTRY.items() if owner == "frontend"
)
WEBHOOK_OWNED_EVENTS = frozenset(
    name for name, owner in EVENT_REGISTRY.items() if owner == "webhook"
)


def get_owner(event_name: str) -> str:
    """Event'in beklenen sahibini döndürür. Bilinmiyorsa KeyError."""
    return EVENT_REGISTRY[event_name]


def is_valid_event(event_name: str) -> bool:
    """Event registry'de tanımlı mı?"""
    return event_name in VALID_EVENT_NAMES


def is_frontend_owned(event_name: str) -> bool:
    return event_name in FRONTEND_OWNED_EVENTS


def is_webhook_owned(event_name: str) -> bool:
    return event_name in WEBHOOK_OWNED_EVENTS
