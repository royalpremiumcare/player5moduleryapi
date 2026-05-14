"""
Funnel event registry ownership tests.

Registry tek kaynak: her event TEK bir owner'a (frontend VEYA webhook) sahip.
Frontend event'leri backend'den emit edilemez; webhook event'leri frontend'den emit edilemez.
Çift sayım bu kurallarla imkânsızdır.
"""

import pytest

from funnel_registry import (
    EVENT_REGISTRY,
    FRONTEND_OWNED_EVENTS,
    WEBHOOK_OWNED_EVENTS,
    VALID_EVENT_NAMES,
    get_owner,
    is_frontend_owned,
    is_webhook_owned,
    is_valid_event,
)


def test_registry_is_non_empty():
    assert len(EVENT_REGISTRY) > 0
    assert len(VALID_EVENT_NAMES) == len(EVENT_REGISTRY)


def test_every_event_has_valid_owner():
    for event_name, owner in EVENT_REGISTRY.items():
        assert owner in ("frontend", "webhook"), (
            f"Event '{event_name}' has invalid owner '{owner}'"
        )


def test_frontend_and_webhook_sets_are_disjoint():
    """Aynı event hem frontend hem webhook tarafından sahiplenilemez."""
    intersection = FRONTEND_OWNED_EVENTS & WEBHOOK_OWNED_EVENTS
    assert intersection == frozenset(), (
        f"These events have ambiguous ownership (both frontend+webhook): {intersection}"
    )


def test_frontend_and_webhook_cover_full_registry():
    assert FRONTEND_OWNED_EVENTS | WEBHOOK_OWNED_EVENTS == VALID_EVENT_NAMES


def test_subscription_completed_is_webhook_owned():
    """Stripe webhook'u backend'de tek sahip; frontend emit edemez."""
    assert "subscription_completed" in EVENT_REGISTRY
    assert is_webhook_owned("subscription_completed")
    assert not is_frontend_owned("subscription_completed")


def test_aha_events_are_frontend_owned():
    """Aha akışının tüm event'leri tarayıcıdan çıkar (backend tek-sahip değil)."""
    aha_events = [e for e in VALID_EVENT_NAMES if e.startswith("aha_")]
    assert len(aha_events) > 0
    for e in aha_events:
        assert is_frontend_owned(e), f"Aha event '{e}' should be frontend-owned"


def test_get_owner_returns_correct_value():
    assert get_owner("signup_completed") == "frontend"
    assert get_owner("subscription_completed") == "webhook"


def test_get_owner_unknown_raises():
    with pytest.raises(KeyError):
        get_owner("bogus_event_that_does_not_exist")


def test_is_valid_event_rejects_unknown():
    assert is_valid_event("aha_appointment_created")
    assert not is_valid_event("")
    assert not is_valid_event("made_up_event")


def test_is_frontend_webhook_mutually_exclusive_for_every_event():
    """Semantic: hiçbir event hem is_frontend_owned hem is_webhook_owned true olamaz."""
    for event_name in VALID_EVENT_NAMES:
        front = is_frontend_owned(event_name)
        web = is_webhook_owned(event_name)
        assert front ^ web, (
            f"Event '{event_name}' must be exactly one of frontend/webhook "
            f"(got frontend={front}, webhook={web})"
        )
