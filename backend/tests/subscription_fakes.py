"""Stripe stand-ins for the subscription plan-change tests. Never talks to Stripe.

``Obj`` behaves like a StripeObject for both access styles the code uses
(``obj["key"]`` and ``obj.key``). ``AttrOnly`` is a non-dict object, which is how
stripe-python 15 StripeObjects look to ``isinstance(x, dict)``.
"""

from types import SimpleNamespace

import stripe as _real_stripe


class Obj(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class AttrOnly:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, key):
        return self.__dict__[key]


def price(price_id, lookup_key=None, currency="try", metadata=None, product="prod_x"):
    return Obj(id=price_id, lookup_key=lookup_key, currency=currency, unit_amount=100000,
               metadata=Obj(metadata or {}), product=product)


def subscription(sub_id="sub_old", status="active", price_obj=None, item_id="si_1",
                 currency="try", customer="cus_1", metadata=None, pending_update=None,
                 latest_invoice=None, items=None):
    if items is None:
        items = [Obj(id=item_id, price=price_obj or price("price_std_m", "standart_monthly_try"))]
    return Obj(id=sub_id, status=status, currency=currency, customer=customer,
               items=Obj(data=items), metadata=Obj(metadata or {}),
               pending_update=pending_update, latest_invoice=latest_invoice)


class FakeStripe:
    """Records every call in ``calls`` as ``(name, args, kwargs)``."""

    error = _real_stripe.error

    def __init__(self):
        self.calls = []
        self.subscriptions = {}
        self.prices_by_lookup = {}
        self.products = {}
        self.modify_result = None
        self.modify_error = None
        self.session_error = None
        self.event = None
        self.session_retrieve_result = None
        self.Subscription = SimpleNamespace(retrieve=self._sub_retrieve, modify=self._sub_modify,
                                            cancel=self._sub_cancel)
        self.Product = SimpleNamespace(retrieve=self._product_retrieve)
        self.Price = SimpleNamespace(list=self._price_list, create=self._price_create)
        self.checkout = SimpleNamespace(Session=SimpleNamespace(create=self._session_create,
                                                                retrieve=self._session_retrieve))
        self.Webhook = SimpleNamespace(construct_event=self._construct_event)

    def names(self):
        return [c[0] for c in self.calls]

    def call(self, name):
        found = [c for c in self.calls if c[0] == name]
        assert found, f"{name} not called; calls={self.names()}"
        return found[-1]

    def _sub_retrieve(self, sub_id, **kw):
        self.calls.append(("Subscription.retrieve", (sub_id,), kw))
        if sub_id not in self.subscriptions:
            raise _real_stripe.error.InvalidRequestError(
                f"No such subscription: '{sub_id}'", "id", code="resource_missing")
        return self.subscriptions[sub_id]

    def _sub_modify(self, sub_id, **kw):
        self.calls.append(("Subscription.modify", (sub_id,), kw))
        if self.modify_error is not None:
            raise self.modify_error
        return self.modify_result

    def _sub_cancel(self, sub_id, **kw):
        self.calls.append(("Subscription.cancel", (sub_id,), kw))
        return Obj(id=sub_id, status="canceled")

    def _product_retrieve(self, product_id, **kw):
        self.calls.append(("Product.retrieve", (product_id,), kw))
        return self.products.get(product_id, Obj(id=product_id, metadata=Obj()))

    def _price_list(self, **kw):
        self.calls.append(("Price.list", (), kw))
        key = (kw.get("lookup_keys") or [None])[0]
        found = self.prices_by_lookup.get(key)
        return Obj(data=[found] if found else [])

    def _price_create(self, **kw):
        self.calls.append(("Price.create", (), kw))
        return price("price_dynamic", None, currency=kw.get("currency"))

    def _session_create(self, **kw):
        self.calls.append(("checkout.Session.create", (), kw))
        if self.session_error is not None:
            err, self.session_error = self.session_error, None
            raise err
        return Obj(id="cs_test_1", url="https://checkout.stripe.test/cs_test_1")

    def _session_retrieve(self, session_id, **kw):
        self.calls.append(("checkout.Session.retrieve", (session_id,), kw))
        return self.session_retrieve_result

    def _construct_event(self, payload, sig, secret):
        self.calls.append(("Webhook.construct_event", (), {}))
        return self.event
