"""Billing lifecycle e-posta eligibility — geçmişe gitmeme + idempotency."""

from datetime import datetime, timedelta, timezone

from billing_lifecycle_emails import (
    is_trial_ended_eligible,
    is_grace_eligible,
    is_suspended_eligible,
    is_historical_trial,
    is_historical_grace,
    paid_deadline,
    parse_plan_dt,
    _fill_name,
    saas_invoice_subscription_id,
    TRIAL_ENDED_COPY,
    GRACE_COPY,
    SUSPENDED_COPY,
)

EPOCH = datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def test_parse_plan_dt_iso_and_naive():
    d = parse_plan_dt("2026-08-25T12:00:00")
    assert d.tzinfo is not None
    assert parse_plan_dt(None) is None


def test_paid_deadline_prefers_next_billing_date():
    doc = {
        "next_billing_date": "2026-08-20T00:00:00+00:00",
        "quota_reset_date": "2026-09-01T00:00:00+00:00",
    }
    assert paid_deadline(doc) == datetime(2026, 8, 20, tzinfo=timezone.utc)


def test_historical_trial_not_eligible():
    plan = {
        "plan_id": "tier_trial",
        "trial_end_date": (EPOCH - timedelta(days=2)).isoformat(),
    }
    assert is_historical_trial(plan, EPOCH) is True
    assert is_trial_ended_eligible(plan, NOW, EPOCH) is False


def test_trial_ended_after_epoch_is_eligible():
    plan = {
        "plan_id": "tier_trial",
        "trial_end_date": (EPOCH + timedelta(hours=1)).isoformat(),
    }
    now = EPOCH + timedelta(hours=2)
    assert is_trial_ended_eligible(plan, now, EPOCH) is True


def test_trial_not_yet_ended_not_eligible():
    plan = {
        "plan_id": "tier_trial",
        "trial_end_date": (NOW + timedelta(days=3)).isoformat(),
    }
    assert is_trial_ended_eligible(plan, NOW, EPOCH) is False


def test_trial_already_sent_not_eligible():
    plan = {
        "plan_id": "tier_trial",
        "trial_end_date": (EPOCH + timedelta(hours=1)).isoformat(),
        "trial_ended_email_sent": True,
    }
    now = EPOCH + timedelta(hours=2)
    assert is_trial_ended_eligible(plan, now, EPOCH) is False


def test_trial_canceled_or_had_stripe_not_eligible():
    base = {
        "plan_id": "tier_trial",
        "trial_end_date": (EPOCH + timedelta(hours=1)).isoformat(),
    }
    now = EPOCH + timedelta(hours=2)
    assert is_trial_ended_eligible({**base, "status": "canceled"}, now, EPOCH) is False
    assert is_trial_ended_eligible({**base, "stripe_subscription_id": "sub_x"}, now, EPOCH) is False
    assert is_trial_ended_eligible({**base, "suspended_email_sent": True}, now, EPOCH) is False


def test_paid_plan_not_trial_ended():
    plan = {
        "plan_id": "tier_1_standard",
        "trial_end_date": (EPOCH + timedelta(hours=1)).isoformat(),
    }
    now = EPOCH + timedelta(hours=2)
    assert is_trial_ended_eligible(plan, now, EPOCH) is False


def test_grace_eligible_only_inside_window_after_epoch():
    deadline = EPOCH + timedelta(hours=2)
    plan = {
        "plan_id": "tier_1_standard",
        "next_billing_date": deadline.isoformat(),
    }
    in_window = deadline + timedelta(days=1)
    after_window = deadline + timedelta(days=4)
    assert is_grace_eligible(plan, in_window, EPOCH) is True
    assert is_grace_eligible(plan, after_window, EPOCH) is False
    assert is_grace_eligible(plan, deadline - timedelta(minutes=1), EPOCH) is False


def test_grace_deadline_before_epoch_not_eligible():
    plan = {
        "plan_id": "tier_1_standard",
        "next_billing_date": (EPOCH - timedelta(days=1)).isoformat(),
    }
    assert is_grace_eligible(plan, NOW, EPOCH) is False
    assert is_historical_grace(plan, NOW, EPOCH) is True


def test_suspended_requires_real_grace_email_and_epoch():
    deadline = EPOCH + timedelta(hours=1)
    plan = {
        "plan_id": "tier_1_standard",
        "next_billing_date": deadline.isoformat(),
        "grace_email_sent": True,
    }
    after_grace = deadline + timedelta(days=3, hours=1)
    assert is_suspended_eligible(plan, after_grace, EPOCH) is True
    assert is_suspended_eligible({**plan, "grace_email_sent": False}, after_grace, EPOCH) is False
    assert is_suspended_eligible(
        {**plan, "grace_email_skipped": "historical"}, after_grace, EPOCH
    ) is False
    # Grace bitişi epoch'tan önceyse geçmiş — mail yok
    old = {
        "plan_id": "tier_1_standard",
        "next_billing_date": (EPOCH - timedelta(days=10)).isoformat(),
        "grace_email_sent": True,
    }
    assert is_suspended_eligible(old, NOW, EPOCH) is False


def test_copy_tables_have_tr_and_en():
    for table in (TRIAL_ENDED_COPY, GRACE_COPY, SUSPENDED_COPY):
        assert "tr" in table and "en" in table
        assert table["tr"]["subject"] and table["en"]["subject"]
        assert "{name}" in table["tr"]["paragraphs"][0]


def test_fill_name_empty_turkish_hello():
    out = _fill_name(["Merhaba {name},", "body"], "", "tr")
    assert out[0] == "Merhaba,"


def test_saas_invoice_subscription_id_stripe_2025_parent():
    """Gamze'nin gerçek payload şekli: top-level subscription=None."""
    inv = {
        "subscription": None,
        "customer_email": "gamzegok93@gmail.com",
        "hosted_invoice_url": "https://invoice.stripe.com/i/acct_x/live_y",
        "parent": {
            "quote_details": None,
            "subscription_details": {"subscription": "sub_1TXRknQkUrne1qlk2eSAG60X"},
            "type": "subscription_details",
        },
        "lines": {"data": []},
    }
    assert saas_invoice_subscription_id(inv) == "sub_1TXRknQkUrne1qlk2eSAG60X"


def test_saas_invoice_subscription_id_from_line_item():
    inv = {
        "subscription": None,
        "parent": {},
        "lines": {"data": [{
            "parent": {
                "subscription_item_details": {"subscription": "sub_line_1"},
            }
        }]},
    }
    assert saas_invoice_subscription_id(inv) == "sub_line_1"
