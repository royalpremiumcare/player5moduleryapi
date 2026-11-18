"""Plan change for an org that already has an active Stripe subscription.

The change modifies that subscription (one item, new price) instead of opening a new
Checkout, which used to create a second customer and a second subscription.
Design: docs/superpowers/specs/2026-11-18-subscription-upgrade-design.md.

Stripe is always passed in (``stripe_mod``) so tests use a fake; nothing here imports server.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})
DEFAULT_QUOTA_LIMIT = 100

SAME_PLAN_MESSAGE = "Bu paketi zaten bu ödeme dönemiyle kullanıyorsunuz."
GENERIC_STRIPE_MESSAGE = "Paket değişikliği şu anda yapılamadı. Lütfen biraz sonra tekrar deneyin."
MULTI_ITEM_MESSAGE = ("Aboneliğiniz birden fazla kalem içerdiği için paket otomatik değiştirilemiyor. "
                      "Lütfen destek ile iletişime geçin.")
NO_INVOICE_URL_MESSAGE = ("Ödeme onayı gerekiyor ama ödeme sayfası alınamadı. "
                          "Lütfen biraz sonra tekrar deneyin.")
PAST_DUE_MESSAGE = ("Bekleyen bir ödemeniz var. Paket değiştirmeden önce lütfen "
                    "bekleyen ödemenizi tamamlayın.")


def no_price_message(currency: str) -> str:
    return (f"Seçilen paket aboneliğinizin para birimi ({(currency or '').upper()}) ile "
            "sunulmuyor. Lütfen destek ile iletişime geçin.")


class PlanChangeError(Exception):
    """A plan change that cannot go ahead; ``message`` is shown to the salon owner (HTTP 400)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def sget(obj, key, default=None):
    """Read a field from a dict or a StripeObject (stripe-python 15 objects are not dicts)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(key, default)
    else:
        try:
            val = obj[key]
        except (KeyError, TypeError, AttributeError):
            val = getattr(obj, key, default)
    return default if val is None else val


def to_plain_dict(obj) -> dict:
    """A Stripe object (or nested Stripe object) as a plain dict; anything else -> {}.

    stripe-python 15 StripeObjects are not mappings: ``dict(obj)`` raises, there is no
    ``.get``/``.keys``, and ``isinstance(obj, dict)`` is False. ``to_dict()`` is the supported,
    recursive conversion. Plain dicts (older SDKs, tests) are copied.
    """
    if obj is None:
        return {}
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            plain = to_dict()
        except Exception:
            plain = None
        if isinstance(plain, dict):
            return plain
    if isinstance(obj, dict):
        return dict(obj)
    return {}


def smeta(obj) -> dict:
    return to_plain_dict(sget(obj, "metadata"))


def _items(subscription) -> list:
    data = sget(sget(subscription, "items"), "data")
    return list(data) if data else []


def is_same_plan(plan_doc: Optional[dict], plan_id: str, billing_cycle: str) -> bool:
    plan_doc = plan_doc or {}
    return (plan_doc.get("plan_id") == plan_id
            and (plan_doc.get("billing_cycle") or "monthly") == (billing_cycle or "monthly"))


def get_active_subscription(stripe_mod, subscription_id: Optional[str]):
    """The tracked subscription if Stripe says it is active/trialing/past_due, else None.

    A subscription Stripe no longer knows is treated as not active; other Stripe errors propagate.
    """
    if not subscription_id:
        return None
    try:
        sub = stripe_mod.Subscription.retrieve(subscription_id)
    except stripe_mod.error.InvalidRequestError as exc:
        if getattr(exc, "code", None) == "resource_missing":
            logger.warning("Tracked subscription %s not found in Stripe", subscription_id)
            return None
        raise
    return sub if sget(sub, "status") in ACTIVE_STATUSES else None


def change_subscription_plan(stripe_mod, subscription, price, *, plan_id: str,
                             organization_id: str, billing_cycle: str) -> dict:
    """Swap the subscription's single item to ``price``; the difference is invoiced now.

    Returns ``{"status": "applied", "subscription": sub}`` when Stripe applied the change, or
    ``{"status": "pending", "hosted_invoice_url": url, "subscription": sub}`` when the charge needs
    the customer (3DS or a declined card). With ``pending_if_incomplete`` the plan only changes
    once that invoice is paid.

    A ``past_due`` subscription is refused: its change could be paid but never applied, because
    the webhook only applies changes on active/trialing subscriptions.
    """
    if sget(subscription, "status") == "past_due":
        raise PlanChangeError(PAST_DUE_MESSAGE)
    items = _items(subscription)
    if len(items) != 1:
        raise PlanChangeError(MULTI_ITEM_MESSAGE)

    sub_currency = (sget(subscription, "currency") or "").lower()
    price_currency = (sget(price, "currency") or "").lower()
    if sub_currency and price_currency and sub_currency != price_currency:
        raise PlanChangeError(
            f"Mevcut aboneliğiniz {sub_currency.upper()} para birimiyle, seçilen paket "
            f"{price_currency.upper()} ile faturalanıyor. Para birimi değiştirilerek paket "
            "değiştirilemez; lütfen aynı para birimini seçin veya destek ile iletişime geçin.")

    sub_id = sget(subscription, "id")
    modified = stripe_mod.Subscription.modify(
        sub_id,
        items=[{"id": sget(items[0], "id"), "price": sget(price, "id")}],
        proration_behavior="always_invoice",
        payment_behavior="pending_if_incomplete",
        metadata={"plan_id": plan_id, "organization_id": organization_id,
                  "billing_cycle": billing_cycle},
        expand=["latest_invoice"],
    )

    if not sget(modified, "pending_update"):
        return {"status": "applied", "subscription": modified}

    invoice = sget(modified, "latest_invoice")
    hosted_url = sget(invoice, "hosted_invoice_url") if not isinstance(invoice, str) else None
    if not hosted_url:
        logger.error("Plan change pending without hosted invoice url: sub=%s invoice=%s",
                     sub_id, invoice)
        raise PlanChangeError(NO_INVOICE_URL_MESSAGE)
    return {"status": "pending", "hosted_invoice_url": hosted_url, "subscription": modified}


def stripe_error_message(err) -> str:
    """Readable message for a Stripe error (shown to the owner, so no raw codes)."""
    text = (getattr(err, "user_message", None) or str(getattr(err, "_message", "") or err) or "").strip()
    if "currenc" in text.lower():
        return ("Mevcut aboneliğiniz farklı bir para birimiyle faturalanıyor. Para birimi "
                "değiştirilerek paket değiştirilemez; lütfen destek ile iletişime geçin.")
    if getattr(err, "code", None) == "card_declined" or type(err).__name__ == "CardError":
        return f"Ödeme alınamadı: {text}" if text else "Ödeme alınamadı."
    return GENERIC_STRIPE_MESSAGE


UNLIMITED_QUOTA = -1
MAX_QUOTA_LIMIT = 10_000_000


def _int_or_none(value):
    """appointment_limit metadata -> int; None (try the next source) when not numeric or 0.

    Negative or absurdly large values mean unlimited (-1, as in PLANS): the live corporate
    product carries a 39-digit limit, which Mongo cannot store (8-byte ints only).
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n < 0 or n > MAX_QUOTA_LIMIT:
        return UNLIMITED_QUOTA
    return n or None


def resolve_quota_limit(stripe_mod, price, plan_data: Optional[dict],
                        fallback_metadata: Optional[dict] = None) -> int:
    """Monthly appointment limit for a paid plan, same order the checkout webhook uses:
    price metadata, product metadata (expanded or retrieved), session metadata, plan default.
    """
    limit = None
    try:
        if price is not None:
            limit = _int_or_none(smeta(price).get("appointment_limit"))
            if not limit:
                product = sget(price, "product")
                if isinstance(product, str):
                    product = stripe_mod.Product.retrieve(product)
                if product is not None:
                    limit = _int_or_none(smeta(product).get("appointment_limit"))
    except Exception as exc:
        logger.warning("appointment_limit could not be read from Stripe: %s", exc)
        limit = None
    if not limit:
        limit = _int_or_none((fallback_metadata or {}).get("appointment_limit"))
    if not limit:
        limit = (plan_data or {}).get("quota_monthly_appointments", DEFAULT_QUOTA_LIMIT)
    return limit


def plan_change_fields(plan_id: str, billing_cycle: str, quota_limit: int, now_iso: str) -> dict:
    """organization_plans fields for a paid plan change. Usage and the quota period are kept."""
    return {
        "plan_id": plan_id,
        "billing_cycle": billing_cycle,
        "quota_limit": quota_limit,
        "is_first_month": False,
        "trial_start_date": None,
        "trial_end_date": None,
        "updated_at": now_iso,
    }


def upgrade_success_url(domain: str, is_native: bool) -> str:
    """Landing after an immediate plan change.

    Native: the in-app browser closes on checkout-return and the plan poll sees the new plan.
    Web: the query string forces a full page load (a hash-only change would keep the stale
    plan picker on screen), then the ``#/subscribe`` route shows the current plan.
    """
    if is_native:
        return f"https://{domain}/api/checkout-return?status=success"
    return f"https://{domain}/?upgraded=1#/subscribe"


LOOKUP_CURRENCIES = ("try", "gbp")
UPDATE_APPLY_STATUSES = frozenset({"active", "trialing"})


def plan_from_lookup_key(lookup_key: Optional[str], plan_ids, make_lookup_key):
    """Reverse of ``make_lookup_key`` (server.get_stripe_lookup_key, the one mapping):
    ``professional_monthly_try`` -> ("tier_2_profesyonel", "monthly"), else None."""
    if not lookup_key:
        return None
    for pid in plan_ids:
        for cycle in ("monthly", "yearly"):
            for currency in LOOKUP_CURRENCIES:
                if make_lookup_key(pid, cycle, currency) == lookup_key:
                    return pid, cycle
    return None


def plan_from_subscription(subscription, plan_ids, make_lookup_key):
    """(plan_id, billing_cycle) the subscription bills for, from a known price lookup_key only.

    Subscription metadata is never used: PLANN's own change writes plan_id metadata that nothing
    clears, so after a Customer Portal move it can name a plan nobody pays for.
    """
    items = _items(subscription)
    price = sget(items[0], "price") if len(items) == 1 else None
    lookup_key = sget(price, "lookup_key")
    found = plan_from_lookup_key(lookup_key, plan_ids, make_lookup_key)
    if found:
        return found
    logger.warning("subscription %s: price %s has %s lookup_key %r; plan left unchanged",
                   sget(subscription, "id"), sget(price, "id"),
                   "an unknown" if lookup_key else "no", lookup_key)
    return None


def _price_changed(subscription, previous_attributes) -> bool:
    """True when the event's previous_attributes show the item price moved to another id.
    An unreadable previous price counts as no change."""
    prev_items = sget(previous_attributes, "items")
    if not prev_items:
        return False
    prev_data = sget(prev_items, "data") or []
    prev_price = sget(prev_data[0], "price") if prev_data else None
    prev_price_id = prev_price if isinstance(prev_price, str) else sget(prev_price, "id")
    items = _items(subscription)
    cur_price_id = sget(sget(items[0], "price"), "id") if items else None
    if not prev_price_id:
        return False
    return prev_price_id != cur_price_id


async def apply_subscription_updated(db, stripe_mod, subscription, *, get_plan_info, plan_ids,
                                     make_lookup_key, previous_attributes=None,
                                     now_iso: Optional[str] = None) -> bool:
    """customer.subscription.updated: follow a plan change Stripe applied (a pending 3DS charge
    that got paid, or a Customer Portal switch). Returns True if organization_plans was written.

    Only the org's tracked subscription counts, only when the item price changed in this event,
    the subscription is active/trialing and nothing is pending.
    """
    sub_id = sget(subscription, "id")
    if not sub_id:
        return False
    plan_doc = await db.organization_plans.find_one({"stripe_subscription_id": sub_id})
    if not plan_doc:
        return False
    if sget(subscription, "pending_update"):
        logger.info("Subscription %s has a pending update; plan unchanged until it is paid", sub_id)
        return False
    if sget(subscription, "status") not in UPDATE_APPLY_STATUSES:
        return False
    if not _price_changed(subscription, previous_attributes):
        return False
    target = plan_from_subscription(subscription, plan_ids, make_lookup_key)
    if not target:
        return False
    plan_id, billing_cycle = target
    if is_same_plan(plan_doc, plan_id, billing_cycle):
        return False
    plan_data = await get_plan_info(plan_id)
    if not plan_data:
        logger.error("subscription.updated: unknown plan %s for subscription %s", plan_id, sub_id)
        return False
    items = _items(subscription)
    quota_limit = resolve_quota_limit(stripe_mod, sget(items[0], "price") if items else None, plan_data)
    if now_iso is None:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
    await db.organization_plans.update_one(
        {"organization_id": plan_doc.get("organization_id"), "stripe_subscription_id": sub_id},
        {"$set": plan_change_fields(plan_id, billing_cycle, quota_limit, now_iso)},
    )
    logger.info("subscription.updated: org=%s plan -> %s (%s) sub=%s",
                plan_doc.get("organization_id"), plan_id, billing_cycle, sub_id)
    return True


def cancel_superseded_subscription(stripe_mod, organization_id: str,
                                   previous_subscription_id: Optional[str],
                                   new_subscription_id: Optional[str]) -> Optional[str]:
    """Safety net when a checkout activates a new subscription for an org that tracked a
    different, still-active one (old app builds, races): cancel the old one now, prorated.

    Call it AFTER organization_plans holds the new id, so the old subscription's
    customer.subscription.deleted no longer matches the org and cannot drop it to trial.
    Returns the cancelled id. Never raises; the new plan must stay active regardless.
    """
    try:
        if not previous_subscription_id or not new_subscription_id:
            return None
        if previous_subscription_id == new_subscription_id:
            return None
        if get_active_subscription(stripe_mod, previous_subscription_id) is None:
            return None
        stripe_mod.Subscription.cancel(previous_subscription_id, prorate=True, invoice_now=True)
        logger.warning("Superseded subscription cancelled: org=%s old=%s new=%s",
                       organization_id, previous_subscription_id, new_subscription_id)
        return previous_subscription_id
    except Exception as exc:
        logger.error("Superseded subscription cancel failed: org=%s old=%s new=%s err=%s",
                     organization_id, previous_subscription_id, new_subscription_id, exc,
                     exc_info=True)
        return None
