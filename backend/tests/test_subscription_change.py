"""Plan change on an active Stripe subscription modifies it instead of creating a second one.

Design: docs/superpowers/specs/2026-11-18-subscription-upgrade-design.md. Stripe is faked.
"""

import pytest
import stripe as real_stripe

import subscription_change as sc
from tests.live_activity_fakes import FakeDB
from tests.subscription_fakes import AttrOnly, FakeStripe, Obj, price, so, subscription

PLAN_IDS = ["tier_trial", "tier_1_standard", "tier_2_profesyonel"]
PLANS = {
    "tier_1_standard": {"id": "tier_1_standard", "quota_monthly_appointments": 300},
    "tier_2_profesyonel": {"id": "tier_2_profesyonel", "quota_monthly_appointments": 800},
}


def make_key(plan_id, cycle, currency):
    name = {"tier_1_standard": "standart", "tier_2_profesyonel": "professional"}.get(plan_id, plan_id)
    return f"{name}_{cycle}_{currency.lower()}"


async def get_plan(plan_id):
    return PLANS.get(plan_id)


# --- same plan -------------------------------------------------------------------------

def test_same_plan_and_cycle_is_same():
    assert sc.is_same_plan({"plan_id": "tier_1_standard", "billing_cycle": "monthly"},
                           "tier_1_standard", "monthly")


def test_same_plan_other_cycle_is_a_change():
    assert not sc.is_same_plan({"plan_id": "tier_1_standard", "billing_cycle": "monthly"},
                               "tier_1_standard", "yearly")


def test_missing_stored_cycle_counts_as_monthly():
    assert sc.is_same_plan({"plan_id": "tier_1_standard"}, "tier_1_standard", "monthly")


# --- active subscription lookup ----------------------------------------------------------

@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_active_statuses_return_the_subscription(status):
    fs = FakeStripe()
    fs.subscriptions["sub_old"] = subscription(status=status)
    assert sc.get_active_subscription(fs, "sub_old")["id"] == "sub_old"


@pytest.mark.parametrize("status", ["canceled", "incomplete", "incomplete_expired", "unpaid", "paused"])
def test_inactive_statuses_return_none(status):
    fs = FakeStripe()
    fs.subscriptions["sub_old"] = subscription(status=status)
    assert sc.get_active_subscription(fs, "sub_old") is None


def test_missing_subscription_returns_none():
    assert sc.get_active_subscription(FakeStripe(), "sub_gone") is None


def test_no_tracked_id_makes_no_stripe_call():
    fs = FakeStripe()
    assert sc.get_active_subscription(fs, None) is None
    assert fs.calls == []


def test_other_stripe_errors_propagate():
    fs = FakeStripe()

    def boom(*a, **k):
        raise real_stripe.error.APIConnectionError("network down")

    fs.Subscription.retrieve = boom
    with pytest.raises(real_stripe.error.StripeError):
        sc.get_active_subscription(fs, "sub_old")


# --- modify ----------------------------------------------------------------------------

def _change(fs, sub, new_price, plan_id="tier_2_profesyonel", cycle="monthly"):
    return sc.change_subscription_plan(fs, sub, new_price, plan_id=plan_id,
                                       organization_id="org1", billing_cycle=cycle)


def test_change_modifies_the_existing_subscription_with_exact_params():
    fs = FakeStripe()
    sub = subscription(item_id="si_1")
    fs.modify_result = subscription(price_obj=price("price_pro_m", "professional_monthly_try"))
    _change(fs, sub, price("price_pro_m", "professional_monthly_try"))
    name, args, kw = fs.call("Subscription.modify")
    assert args == ("sub_old",)
    assert kw == {
        "items": [{"id": "si_1", "price": "price_pro_m"}],
        "proration_behavior": "always_invoice",
        "payment_behavior": "pending_if_incomplete",
        "metadata": {"plan_id": "tier_2_profesyonel", "organization_id": "org1",
                     "billing_cycle": "monthly"},
        "expand": ["latest_invoice"],
    }
    assert "discounts" not in kw and "coupon" not in kw


def test_applied_change_reports_applied():
    fs = FakeStripe()
    fs.modify_result = subscription(price_obj=price("price_pro_m", "professional_monthly_try"))
    out = _change(fs, subscription(), price("price_pro_m", "professional_monthly_try"))
    assert out["status"] == "applied"


def test_pending_change_reports_hosted_invoice_url():
    fs = FakeStripe()
    fs.modify_result = subscription(
        pending_update=Obj(expires_at=1, subscription_items=[Obj(id="si_1", price="price_pro_m")]),
        latest_invoice=Obj(id="in_1", hosted_invoice_url="https://invoice.stripe.test/in_1"))
    out = _change(fs, subscription(), price("price_pro_m", "professional_monthly_try"))
    assert out == {"status": "pending", "hosted_invoice_url": "https://invoice.stripe.test/in_1",
                   "subscription": fs.modify_result}


def test_pending_change_without_invoice_url_is_an_error():
    fs = FakeStripe()
    fs.modify_result = subscription(pending_update=Obj(expires_at=1), latest_invoice="in_1")
    with pytest.raises(sc.PlanChangeError):
        _change(fs, subscription(), price("price_pro_m", "professional_monthly_try"))


def test_currency_mismatch_is_rejected_before_any_stripe_call():
    fs = FakeStripe()
    with pytest.raises(sc.PlanChangeError) as exc:
        _change(fs, subscription(currency="try"), price("price_pro_gbp", "professional_monthly_gbp",
                                                        currency="gbp"))
    assert "TRY" in exc.value.message and "GBP" in exc.value.message
    assert fs.calls == []


def test_past_due_subscription_cannot_change_plan():
    fs = FakeStripe()
    with pytest.raises(sc.PlanChangeError) as exc:
        _change(fs, subscription(status="past_due"), price("price_pro_m", "professional_monthly_try"))
    assert exc.value.message == ("Bekleyen bir ödemeniz var. Paket değiştirmeden önce lütfen "
                                 "bekleyen ödemenizi tamamlayın.")
    assert fs.calls == []


def test_multi_item_subscription_is_rejected():
    fs = FakeStripe()
    sub = subscription(items=[Obj(id="si_1", price=price("a")), Obj(id="si_2", price=price("b"))])
    with pytest.raises(sc.PlanChangeError):
        _change(fs, sub, price("price_pro_m"))
    assert fs.calls == []


# --- error messages --------------------------------------------------------------------

def test_stripe_currency_error_gets_a_readable_turkish_message():
    err = real_stripe.error.InvalidRequestError(
        "You cannot combine currencies on a single customer. This customer has an active "
        "subscription with currency try.", "currency")
    msg = sc.stripe_error_message(err)
    assert "para birimi" in msg.lower()


def test_card_error_message_is_shown():
    err = real_stripe.error.CardError("Your card was declined.", "card", "card_declined")
    msg = sc.stripe_error_message(err)
    assert "Your card was declined." in msg


# --- quota ----------------------------------------------------------------------------

def test_quota_from_price_metadata():
    assert sc.resolve_quota_limit(FakeStripe(), price("p", metadata={"appointment_limit": "999"}),
                                  PLANS["tier_2_profesyonel"]) == 999


def test_quota_from_retrieved_product_metadata():
    fs = FakeStripe()
    fs.products["prod_pro"] = Obj(id="prod_pro", metadata=Obj(appointment_limit="777"))
    assert sc.resolve_quota_limit(fs, price("p", product="prod_pro"), PLANS["tier_2_profesyonel"]) == 777


def test_quota_from_expanded_non_dict_product():
    product = AttrOnly(id="prod_pro", metadata=Obj(appointment_limit="555"))
    assert sc.resolve_quota_limit(FakeStripe(), price("p", product=product),
                                  PLANS["tier_2_profesyonel"]) == 555


def test_quota_from_fallback_metadata_then_plan():
    fs = FakeStripe()
    assert sc.resolve_quota_limit(fs, price("p"), PLANS["tier_2_profesyonel"],
                                  fallback_metadata={"appointment_limit": "123"}) == 123
    assert sc.resolve_quota_limit(fs, price("p"), PLANS["tier_2_profesyonel"]) == 800
    assert sc.resolve_quota_limit(fs, None, {}) == 100


def test_quota_falls_back_to_plan_when_stripe_fails():
    fs = FakeStripe()

    def boom(*a, **k):
        raise real_stripe.error.APIConnectionError("down")

    fs.Product.retrieve = boom
    assert sc.resolve_quota_limit(fs, price("p", product="prod_x"), PLANS["tier_1_standard"]) == 300


def test_plan_change_fields_keep_usage():
    fields = sc.plan_change_fields("tier_2_profesyonel", "yearly", 800, "2026-11-18T00:00:00+00:00")
    assert fields["plan_id"] == "tier_2_profesyonel"
    assert fields["billing_cycle"] == "yearly"
    assert fields["quota_limit"] == 800
    assert "quota_usage" not in fields


# --- success landing -------------------------------------------------------------------

def test_success_url_native():
    assert sc.upgrade_success_url("plann.app", True) == "https://plann.app/api/checkout-return?status=success"


def test_success_url_web_reloads_into_the_subscribe_page():
    url = sc.upgrade_success_url("plann.app", False)
    assert url == "https://plann.app/?upgraded=1#/subscribe"
    assert "session_id" not in url and "payment-success" not in url


# --- customer.subscription.updated ---------------------------------------------------------

async def _org(db, **extra):
    doc = {"organization_id": "org1", "plan_id": "tier_1_standard", "billing_cycle": "monthly",
           "stripe_subscription_id": "sub_old", "stripe_customer_id": "cus_1",
           "quota_usage": 42, "quota_limit": 300}
    doc.update(extra)
    await db.organization_plans.insert_one(doc)


PRICE_CHANGED = {"items": {"data": [{"id": "si_1", "price": {"id": "price_std_m"}}]}}


async def _apply(db, fs, sub, previous_attributes=PRICE_CHANGED):
    return await sc.apply_subscription_updated(db, fs, sub, get_plan_info=get_plan,
                                               plan_ids=PLAN_IDS, make_lookup_key=make_key,
                                               previous_attributes=previous_attributes)


async def test_portal_change_without_metadata_maps_the_lookup_key():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_pro_m", "professional_monthly_try"))
    assert sc.smeta(sub) == {}
    assert await _apply(db, fs, sub) is True
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert (doc["plan_id"], doc["billing_cycle"]) == ("tier_2_profesyonel", "monthly")


async def test_lookup_key_wins_over_stale_metadata():
    """A PLANN change leaves metadata behind; a later portal change only moves the price."""
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_pro_y", "professional_yearly_gbp"),
                       metadata={"plan_id": "tier_1_standard", "billing_cycle": "monthly"})
    assert await _apply(db, fs, sub) is True
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert (doc["plan_id"], doc["billing_cycle"]) == ("tier_2_profesyonel", "yearly")


@pytest.mark.parametrize("lookup_key", [None, "mystery_monthly_try", "professional_weekly_try"])
async def test_unknown_or_missing_lookup_key_without_metadata_changes_nothing(lookup_key, caplog):
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_x", lookup_key))
    with caplog.at_level("WARNING", logger="subscription_change"):
        assert await _apply(db, fs, sub) is False
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert doc["plan_id"] == "tier_1_standard"
    assert any(r.levelname == "WARNING" for r in caplog.records)


@pytest.mark.parametrize("status", ["incomplete", "past_due", "unpaid", "canceled"])
async def test_updated_event_in_non_live_status_changes_nothing(status):
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(status=status, price_obj=price("price_pro_m", "professional_monthly_try"))
    assert await _apply(db, fs, sub) is False
    assert (await db.organization_plans.find_one({"organization_id": "org1"}))["plan_id"] == "tier_1_standard"


async def test_updated_event_in_trialing_status_applies():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(status="trialing", price_obj=price("price_pro_m", "professional_monthly_try"))
    assert await _apply(db, fs, sub) is True


@pytest.mark.parametrize("previous", [{"cancel_at_period_end": False}, {},
                                      {"items": {"data": [{"price": {"id": "price_pro_m"}}]}}])
async def test_updated_event_without_a_price_change_changes_nothing(previous):
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_pro_m", "professional_monthly_try"))
    assert await _apply(db, fs, sub, previous_attributes=previous) is False
    assert (await db.organization_plans.find_one({"organization_id": "org1"}))["plan_id"] == "tier_1_standard"


async def test_updated_event_sets_plan_for_tracked_subscription():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_pro_y", "professional_yearly_try",
                                       metadata={"appointment_limit": "800"}))
    assert await _apply(db, fs, sub) is True
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert doc["plan_id"] == "tier_2_profesyonel"
    assert doc["billing_cycle"] == "yearly"
    assert doc["quota_limit"] == 800
    assert doc["quota_usage"] == 42


@pytest.mark.parametrize("lookup_key", [None, "legacy_promo_try"])
async def test_unknown_key_with_stale_plann_metadata_changes_nothing(lookup_key, caplog):
    """PLANN's own modify leaves plan_id metadata behind; a later portal move to a price we
    cannot map must not apply that stale plan (nobody pays for it)."""
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_odd", lookup_key),
                       metadata={"plan_id": "tier_2_profesyonel", "billing_cycle": "monthly",
                                 "organization_id": "org1"})
    with caplog.at_level("WARNING", logger="subscription_change"):
        assert await _apply(db, fs, sub) is False
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert (doc["plan_id"], doc["quota_limit"]) == ("tier_1_standard", 300)
    assert any(r.levelname == "WARNING" for r in caplog.records)


@pytest.mark.parametrize("previous", [
    {"items": {"data": []}},
    {"items": {"data": [{"id": "si_1"}]}},
    {"items": {"data": [{"id": "si_1", "price": {}}]}},
])
async def test_unreadable_previous_price_counts_as_no_change(previous):
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_pro_m", "professional_monthly_try"))
    assert await _apply(db, fs, sub, previous_attributes=previous) is False
    assert (await db.organization_plans.find_one({"organization_id": "org1"}))["plan_id"] == "tier_1_standard"


async def test_updated_event_ignores_untracked_subscription():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(sub_id="sub_other", price_obj=price("price_pro_m", "professional_monthly_try"))
    assert await _apply(db, fs, sub) is False
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert doc["plan_id"] == "tier_1_standard"


async def test_updated_event_waits_while_update_is_pending():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_std_m", "standart_monthly_try"),
                       metadata={"plan_id": "tier_2_profesyonel", "billing_cycle": "monthly"},
                       pending_update=Obj(expires_at=1))
    assert await _apply(db, fs, sub) is False
    doc = await db.organization_plans.find_one({"organization_id": "org1"})
    assert doc["plan_id"] == "tier_1_standard"


async def test_updated_event_with_unchanged_plan_writes_nothing():
    db, fs = FakeDB(), FakeStripe()
    await _org(db)
    sub = subscription(price_obj=price("price_std_m", "standart_monthly_try"))
    assert await _apply(db, fs, sub) is False
    assert not [c for c in db.log if c[1] == "update_one"]


# --- superseded subscription guard ----------------------------------------------------------
# The caller writes the new id to organization_plans first, then passes the previous id here.

def test_guard_cancels_a_different_still_active_subscription():
    fs = FakeStripe()
    fs.subscriptions["sub_old"] = subscription(status="active")
    assert sc.cancel_superseded_subscription(fs, "org1", "sub_old", "sub_new") == "sub_old"
    name, args, kw = fs.call("Subscription.cancel")
    assert args == ("sub_old",)
    assert kw == {"prorate": True, "invoice_now": True}


def test_guard_leaves_same_subscription_alone():
    fs = FakeStripe()
    assert sc.cancel_superseded_subscription(fs, "org1", "sub_old", "sub_old") is None
    assert fs.calls == []


def test_guard_skips_already_cancelled_subscription():
    fs = FakeStripe()
    fs.subscriptions["sub_old"] = subscription(status="canceled")
    assert sc.cancel_superseded_subscription(fs, "org1", "sub_old", "sub_new") is None
    assert "Subscription.cancel" not in fs.names()


def test_guard_without_previous_subscription_does_nothing():
    fs = FakeStripe()
    assert sc.cancel_superseded_subscription(fs, "org1", None, "sub_new") is None
    assert fs.calls == []


def test_guard_never_raises():
    fs = FakeStripe()

    def boom(*a, **k):
        raise real_stripe.error.APIConnectionError("down")

    fs.Subscription.retrieve = boom
    assert sc.cancel_superseded_subscription(fs, "org1", "sub_old", "sub_new") is None


# --- real stripe-python 15 objects (not dicts) ------------------------------------------------

def test_real_stripe_object_is_not_a_mapping():
    """Guards the premise: if this ever changes, the helpers below still work."""
    obj = so({"metadata": {"plan_id": "p"}})
    assert not isinstance(obj, dict)
    with pytest.raises(TypeError):
        dict(obj["metadata"])


def test_to_plain_dict_reads_real_stripe_objects_recursively():
    obj = so({"id": "cs_1", "metadata": {"plan_id": "tier_2_profesyonel", "billing_cycle": "yearly"},
              "line_items": {"object": "list", "data": [{"price": {"id": "price_1"}}]}})
    plain = sc.to_plain_dict(obj)
    assert type(plain) is dict
    assert plain["metadata"] == {"plan_id": "tier_2_profesyonel", "billing_cycle": "yearly"}
    assert plain["line_items"]["data"][0]["price"]["id"] == "price_1"


@pytest.mark.parametrize("value,expected", [(None, {}), ({"a": 1}, {"a": 1}), ("cus_1", {}), (42, {})])
def test_to_plain_dict_handles_plain_values(value, expected):
    assert sc.to_plain_dict(value) == expected


def test_smeta_reads_real_stripe_object_metadata():
    obj = so({"id": "sub_1", "metadata": {"plan_id": "tier_2_profesyonel", "organization_id": "org1"}})
    assert sc.smeta(obj) == {"plan_id": "tier_2_profesyonel", "organization_id": "org1"}
    assert sc.smeta(so({"id": "x"})) == {}


def test_sget_reads_nested_real_stripe_objects():
    obj = so({"items": {"object": "list", "data": [{"id": "si_1", "price": {"id": "price_1"}}]},
              "pending_update": None})
    data = sc.sget(sc.sget(obj, "items"), "data")
    assert sc.sget(sc.sget(data[0], "price"), "id") == "price_1"
    assert sc.sget(obj, "pending_update") is None
    assert sc.sget(obj, "missing", "dflt") == "dflt"


def test_quota_from_real_stripe_price_metadata():
    p = so({"id": "price_1", "metadata": {"appointment_limit": "777"}, "product": "prod_x"})
    assert sc.resolve_quota_limit(FakeStripe(), p, PLANS["tier_2_profesyonel"]) == 777


def test_quota_from_real_expanded_stripe_product():
    p = so({"id": "price_1", "metadata": {}, "product": {"id": "prod_1", "metadata": {"appointment_limit": "555"}}})
    assert sc.resolve_quota_limit(FakeStripe(), p, PLANS["tier_2_profesyonel"]) == 555


# --- unlimited quota sentinel (live corporate product: 39-digit appointment_limit) ---------------

HUGE = "999999999999999999999999999999999999999"
CORPORATE = {"id": "tier_6_kurumsal", "quota_monthly_appointments": -1}


def _real_price(price_limit=None, product_limit=None):
    return so({"id": "price_c", "object": "price",
               "metadata": {} if price_limit is None else {"appointment_limit": price_limit},
               "product": {"id": "prod_c", "object": "product",
                           "metadata": {} if product_limit is None else {"appointment_limit": product_limit}}})


def test_huge_corporate_product_limit_ends_as_unlimited_via_the_plan_default():
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(product_limit=HUGE), CORPORATE) == -1


def test_minus_one_means_unlimited():
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit="-1"), CORPORATE) == -1


STANDART = {"id": "tier_1_standard", "quota_monthly_appointments": 100}  # real PLANS value


@pytest.mark.parametrize("value", ["30000000", "10000001", "-5", HUGE])
def test_out_of_range_limits_fall_through_to_the_plan_default(value):
    """A typo must not grant unlimited appointments: out-of-range values are ignored."""
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit=value), STANDART) == 100


def test_out_of_range_price_limit_falls_through_to_the_product_limit():
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit="30000000", product_limit="450"),
                                  STANDART) == 450


def test_upper_bound_is_still_a_real_limit():
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit="10000000"),
                                  PLANS["tier_1_standard"]) == 10_000_000


def test_non_numeric_limit_falls_through_to_the_next_source():
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit="abc", product_limit="450"),
                                  PLANS["tier_1_standard"]) == 450
    assert sc.resolve_quota_limit(FakeStripe(), _real_price(price_limit="abc"),
                                  PLANS["tier_1_standard"]) == 300
