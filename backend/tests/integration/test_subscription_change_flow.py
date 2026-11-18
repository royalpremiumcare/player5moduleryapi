"""POST /api/payments/create-checkout-session and the Stripe webhook, for an org that already
has an active subscription (design 2026-11-18-subscription-upgrade). Stripe is fully faked."""
from __future__ import annotations

import re

import pytest
import pytest_asyncio
import stripe as real_stripe

from tests.live_activity_fakes import FakeDB
from tests.subscription_fakes import FakeStripe, Obj, price, subscription

ORG = "org_test_integration"
NATIVE_SUCCESS = re.compile(r"^https://[^/]+/api/checkout-return\?status=success$")
WEB_SUCCESS = re.compile(r"^https://[^/]+/\?upgraded=1#/subscribe$")

STD_M = price("price_std_m", "standart_monthly_try", metadata={"appointment_limit": "300"})
PRO_M = price("price_pro_m", "professional_monthly_try", metadata={"appointment_limit": "800"})
PRO_Y = price("price_pro_y", "professional_yearly_try", metadata={"appointment_limit": "800"})


@pytest.fixture
def test_user(org_id):
    """The checkout endpoint needs an e-mail username (the shared fixture's is not one)."""
    from server import UserInDB

    return UserInDB(username="owner@salon.test", organization_id=org_id, role="admin",
                    full_name="Salon Owner", permitted_service_ids=[], can_view_all_appointments=True)


@pytest_asyncio.fixture
async def env(integration_client, monkeypatch):
    import server

    client, _redis, _ = integration_client
    db, fs = FakeDB(), FakeStripe()

    async def get_db(request):
        return db

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(server, "get_db_from_request", get_db)
    monkeypatch.setattr(server, "stripe", fs)
    monkeypatch.setattr(server, "STRIPE_SECRET_KEY", "sk_test_fake_never_live")
    monkeypatch.setattr(server, "STRIPE_WEBHOOK_SECRET", "whsec_fake")
    monkeypatch.setattr(server, "track_webhook_event", noop)
    monkeypatch.setattr(server, "_send_subscription_email_once", noop)
    for p in (STD_M, PRO_M, PRO_Y):
        fs.prices_by_lookup[p["lookup_key"]] = p
    return client, db, fs


async def _org(db, **extra):
    doc = {"organization_id": ORG, "plan_id": "tier_1_standard", "billing_cycle": "monthly",
           "stripe_subscription_id": "sub_old", "stripe_customer_id": "cus_1",
           "quota_usage": 42, "quota_limit": 300,
           "quota_reset_date": "2026-12-01T00:00:00+00:00"}
    doc.update(extra)
    await db.organization_plans.insert_one(doc)


async def _plan(db):
    return await db.organization_plans.find_one({"organization_id": ORG})


async def _post(client, plan_id, cycle="monthly", platform="ios"):
    return await client.post("/api/payments/create-checkout-session",
                             json={"plan_id": plan_id, "billing_cycle": cycle,
                                   "platform": platform, "currency": "try"},
                             headers={"origin": "https://plannapp.co.uk"})


# --- immediate change ------------------------------------------------------------------------

async def test_upgrade_modifies_the_existing_subscription_and_updates_the_plan(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(price_obj=STD_M)
    fs.modify_result = subscription(price_obj=PRO_M)

    r = await _post(client, "tier_2_profesyonel")

    assert r.status_code == 200, r.text
    body = r.json()
    assert NATIVE_SUCCESS.match(body["checkout_url"])
    assert body["upgraded"] is True
    assert body["session_id"] is None
    _, args, kw = fs.call("Subscription.modify")
    assert args == ("sub_old",)
    assert kw == {
        "items": [{"id": "si_1", "price": "price_pro_m"}],
        "proration_behavior": "always_invoice",
        "payment_behavior": "pending_if_incomplete",
        "metadata": {"plan_id": "tier_2_profesyonel", "organization_id": ORG, "billing_cycle": "monthly"},
        "expand": ["latest_invoice"],
    }
    assert "checkout.Session.create" not in fs.names()
    doc = await _plan(db)
    assert doc["plan_id"] == "tier_2_profesyonel"
    assert doc["billing_cycle"] == "monthly"
    assert doc["quota_limit"] == 800
    assert doc["quota_usage"] == 42
    assert doc["stripe_subscription_id"] == "sub_old"
    assert doc["stripe_customer_id"] == "cus_1"


async def test_downgrade_on_web_modifies_the_subscription_and_lands_on_subscribe(env):
    client, db, fs = env
    await _org(db, plan_id="tier_2_profesyonel", billing_cycle="yearly", quota_limit=800)
    fs.subscriptions["sub_old"] = subscription(price_obj=PRO_Y)
    fs.modify_result = subscription(price_obj=STD_M)

    r = await _post(client, "tier_1_standard", "monthly", platform="web")

    assert r.status_code == 200, r.text
    assert WEB_SUCCESS.match(r.json()["checkout_url"])
    assert r.json()["upgraded"] is True
    _, _, kw = fs.call("Subscription.modify")
    assert kw["items"] == [{"id": "si_1", "price": "price_std_m"}]
    assert kw["proration_behavior"] == "always_invoice"
    doc = await _plan(db)
    assert (doc["plan_id"], doc["billing_cycle"], doc["quota_limit"]) == ("tier_1_standard", "monthly", 300)
    assert doc["quota_usage"] == 42


async def test_plan_change_never_applies_a_launch_coupon(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(price_obj=STD_M)
    fs.modify_result = subscription(price_obj=PRO_M)
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 200, r.text
    _, _, kw = fs.call("Subscription.modify")
    assert not {"discounts", "coupon", "promotion_code"} & set(kw)


# --- pending charge ----------------------------------------------------------------------------

async def test_pending_charge_returns_the_hosted_invoice_and_keeps_the_plan(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(price_obj=STD_M)
    fs.modify_result = subscription(
        price_obj=STD_M, pending_update=Obj(expires_at=1),
        latest_invoice=Obj(id="in_1", hosted_invoice_url="https://invoice.stripe.test/in_1"))

    r = await _post(client, "tier_2_profesyonel")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checkout_url"] == "https://invoice.stripe.test/in_1"
    assert body["pending"] is True
    assert "upgraded" not in body
    doc = await _plan(db)
    assert (doc["plan_id"], doc["quota_limit"]) == ("tier_1_standard", 300)


# --- same plan ----------------------------------------------------------------------------

async def test_same_plan_and_cycle_returns_400_without_any_stripe_call(env):
    client, db, fs = env
    await _org(db)
    r = await _post(client, "tier_1_standard", "monthly")
    assert r.status_code == 400
    assert "zaten" in r.json()["detail"].lower()
    assert fs.calls == []


# --- new subscription ----------------------------------------------------------------------

async def test_new_subscription_uses_the_stored_customer(env):
    client, db, fs = env
    await _org(db, plan_id="tier_trial")
    fs.subscriptions["sub_old"] = subscription(status="canceled")

    r = await _post(client, "tier_2_profesyonel")

    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"] == "https://checkout.stripe.test/cs_test_1"
    assert r.json()["session_id"] == "cs_test_1"
    _, _, kw = fs.call("checkout.Session.create")
    assert kw["customer"] == "cus_1"
    assert "customer_email" not in kw
    assert "Subscription.modify" not in fs.names()


async def test_new_subscription_without_stored_customer_uses_email(env):
    client, db, fs = env
    await _org(db, plan_id="tier_trial", stripe_subscription_id=None, stripe_customer_id=None)
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 200, r.text
    _, _, kw = fs.call("checkout.Session.create")
    assert "customer" not in kw
    assert kw["customer_email"]
    assert "Subscription.retrieve" not in fs.names()


async def test_stored_customer_unknown_to_stripe_falls_back_to_email(env):
    client, db, fs = env
    await _org(db, plan_id="tier_trial", stripe_subscription_id=None)
    fs.session_error = real_stripe.error.InvalidRequestError(
        "No such customer: 'cus_1'", "customer", code="resource_missing")
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 200, r.text
    creates = [c for c in fs.calls if c[0] == "checkout.Session.create"]
    assert len(creates) == 2
    assert creates[0][2]["customer"] == "cus_1"
    assert "customer" not in creates[1][2] and creates[1][2]["customer_email"]


async def test_same_plan_without_a_subscription_can_still_be_bought(env):
    client, db, fs = env
    await _org(db, stripe_subscription_id=None)
    r = await _post(client, "tier_1_standard", "monthly")
    assert r.status_code == 200, r.text
    assert "checkout.Session.create" in fs.names()


# --- errors -------------------------------------------------------------------------------

async def test_stripe_error_on_plan_change_returns_400(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(price_obj=STD_M)
    fs.modify_error = real_stripe.error.CardError("Your card was declined.", "card", "card_declined")
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 400
    assert "Your card was declined." in r.json()["detail"]
    assert (await _plan(db))["plan_id"] == "tier_1_standard"


async def test_currency_mismatch_returns_400_without_modify(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(price_obj=STD_M, currency="gbp")
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 400
    assert "para birimi" in r.json()["detail"].lower()
    assert "Subscription.modify" not in fs.names()


async def test_stripe_error_on_subscription_lookup_returns_400(env):
    client, db, fs = env
    await _org(db)

    def boom(*a, **k):
        raise real_stripe.error.APIConnectionError("network down")

    fs.Subscription.retrieve = boom
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 400
    assert r.json()["detail"]


async def test_stripe_error_on_new_checkout_returns_400(env):
    client, db, fs = env
    await _org(db, plan_id="tier_trial", stripe_subscription_id=None, stripe_customer_id=None)
    fs.session_error = real_stripe.error.APIConnectionError("network down")
    r = await _post(client, "tier_2_profesyonel")
    assert r.status_code == 400


# --- webhook ------------------------------------------------------------------------------

FROM_STD = Obj(items=Obj(data=[Obj(id="si_1", price=Obj(id="price_std_m"))]))


async def _webhook(client, fs, event_type, obj, previous=None):
    data = Obj(object=obj)
    if previous is not None:
        data["previous_attributes"] = previous
    fs.event = Obj(id="evt_1", type=event_type, data=data)
    return await client.post("/api/webhook/stripe", content=b"{}",
                             headers={"stripe-signature": "t=1,v1=fake"})


async def test_subscription_updated_sets_the_plan_for_the_tracked_subscription(env):
    client, db, fs = env
    await _org(db)
    r = await _webhook(client, fs, "customer.subscription.updated",
                       subscription(price_obj=PRO_M, metadata={"plan_id": "tier_2_profesyonel",
                                                               "billing_cycle": "monthly"}),
                       previous=FROM_STD)
    assert r.status_code == 200
    doc = await _plan(db)
    assert (doc["plan_id"], doc["quota_limit"], doc["quota_usage"]) == ("tier_2_profesyonel", 800, 42)


async def test_portal_plan_switch_without_metadata_sets_the_plan_from_the_lookup_key(env):
    client, db, fs = env
    await _org(db)
    r = await _webhook(client, fs, "customer.subscription.updated",
                       subscription(price_obj=PRO_Y), previous=FROM_STD)
    assert r.status_code == 200
    doc = await _plan(db)
    assert (doc["plan_id"], doc["billing_cycle"], doc["quota_limit"]) == ("tier_2_profesyonel", "yearly", 800)
    assert doc["quota_usage"] == 42


async def test_portal_switch_to_an_unknown_price_changes_nothing(env):
    client, db, fs = env
    await _org(db)
    r = await _webhook(client, fs, "customer.subscription.updated",
                       subscription(price_obj=price("price_odd", "legacy_promo_try")), previous=FROM_STD)
    assert r.status_code == 200
    doc = await _plan(db)
    assert (doc["plan_id"], doc["quota_limit"]) == ("tier_1_standard", 300)


async def test_subscription_updated_ignores_an_untracked_subscription(env):
    client, db, fs = env
    await _org(db)
    r = await _webhook(client, fs, "customer.subscription.updated",
                       subscription(sub_id="sub_stray", price_obj=PRO_M), previous=FROM_STD)
    assert r.status_code == 200
    assert (await _plan(db))["plan_id"] == "tier_1_standard"


async def test_subscription_updated_to_incomplete_changes_nothing(env):
    client, db, fs = env
    await _org(db)
    r = await _webhook(client, fs, "customer.subscription.updated",
                       subscription(status="incomplete", price_obj=PRO_M), previous=FROM_STD)
    assert r.status_code == 200
    assert (await _plan(db))["plan_id"] == "tier_1_standard"


def _completed_session(sub_id="sub_new"):
    return Obj(id="cs_new", mode="subscription", subscription=sub_id, customer="cus_1",
               amount_total=80000, metadata=Obj(plan_id="tier_2_profesyonel", organization_id=ORG,
                                                billing_cycle="monthly"))


async def test_checkout_completed_cancels_a_different_still_active_subscription(env):
    client, db, fs = env
    await _org(db)
    await db.payment_logs.insert_one({"session_id": "cs_new", "organization_id": ORG,
                                      "plan_id": "tier_2_profesyonel", "status": "pending"})
    fs.subscriptions["sub_old"] = subscription(status="active")
    fs.session_retrieve_result = Obj(id="cs_new", line_items=Obj(data=[Obj(price=PRO_M)]))

    r = await _webhook(client, fs, "checkout.session.completed", _completed_session())

    assert r.status_code == 200
    _, args, kw = fs.call("Subscription.cancel")
    assert args == ("sub_old",)
    assert kw == {"prorate": True, "invoice_now": True}
    doc = await _plan(db)
    assert (doc["stripe_subscription_id"], doc["plan_id"]) == ("sub_new", "tier_2_profesyonel")


async def test_checkout_completed_for_the_tracked_subscription_cancels_nothing(env):
    client, db, fs = env
    await _org(db, stripe_subscription_id="sub_new")
    await db.payment_logs.insert_one({"session_id": "cs_new", "organization_id": ORG,
                                      "plan_id": "tier_2_profesyonel", "status": "pending"})
    fs.session_retrieve_result = Obj(id="cs_new", line_items=Obj(data=[Obj(price=PRO_M)]))
    r = await _webhook(client, fs, "checkout.session.completed", _completed_session())
    assert r.status_code == 200
    assert "Subscription.cancel" not in fs.names()
    assert (await _plan(db))["quota_limit"] == 800


async def test_confirm_checkout_also_cancels_a_superseded_subscription(env):
    client, db, fs = env
    await _org(db)
    fs.subscriptions["sub_old"] = subscription(status="active")
    session = _completed_session()
    session.update(payment_status="paid", status="complete", line_items=Obj(data=[Obj(price=PRO_M)]))
    fs.session_retrieve_result = session

    r = await client.post("/api/payments/confirm-checkout-session", json={"session_id": "cs_new"})

    assert r.status_code == 200, r.text
    _, args, _ = fs.call("Subscription.cancel")
    assert args == ("sub_old",)
    assert (await _plan(db))["stripe_subscription_id"] == "sub_new"
