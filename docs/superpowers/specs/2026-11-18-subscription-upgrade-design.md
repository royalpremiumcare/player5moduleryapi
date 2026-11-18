# Subscription plan change updates the existing Stripe subscription (short design)

Date: 2026-11-18. Owner request: "kalıcı düzeltmeyi de yap", after a field incident.

## Incident
A business on an active monthly Standart subscription upgraded to Professional through `POST /api/payments/create-checkout-session`. The endpoint always builds a new Stripe Checkout Session with `customer_email`, so Stripe created:
- a **new Stripe customer**, and
- a **second active subscription**.

The old Standart subscription kept billing. PLANN only tracked the new one, because `organization_plans.stripe_subscription_id` was overwritten. The owner cancelled the old one by hand.

## Facts (recon)
- `organization_plans` holds `plan_id`, `billing_cycle`, `stripe_subscription_id` and `stripe_customer_id`. The plan is activated by the `checkout.session.completed` webhook, which uses `payment_logs` or session metadata (`plan_id`, `organization_id`).
- The `customer.subscription.updated` webhook only logs a scheduled cancel. `customer.subscription.deleted` drops the org to trial, but only if the subscription id is the tracked one.
- The Stripe Customer Portal has `subscription_update.enabled = false` (it allows cancel only), so a portal-based upgrade flow is not available without changing the Stripe config.
- Frontend `PlanPicker.js` POSTs `{plan_id, billing_cycle, platform, currency}` and expects `checkout_url` (and `session_id`).
  - Web redirects to `checkout_url`.
  - Native opens it in the in-app browser and polls `/plan/current` against the baseline plan.
  - Frozen mobile builds behave the same way.

## Decision (owner-approved approach; details are the author's calls)
1. **An org with an active tracked subscription changes plan by modifying that subscription. It never gets a new one.** "Active" means `organization_plans.stripe_subscription_id` is set and Stripe reports status `active`, `trialing` or `past_due`.
   - Call `stripe.Subscription.modify` and replace the single item's price with the new plan's price (same price lookup as today).
   - Use `proration_behavior="always_invoice"`, so the difference is charged now. A downgrade leaves a credit on the customer's balance that pays future invoices.
   - Use `payment_behavior="pending_if_incomplete"`, so the plan does not change until the charge succeeds.
   - Set subscription metadata `plan_id`, `organization_id` and `billing_cycle`.
   - No launch coupon applies to a plan change.
2. **Charge succeeded immediately.** Update `organization_plans` right away: `plan_id`, `billing_cycle`, and the quota fields the checkout webhook sets for a paid plan, using the same helper or logic. Keep the current quota usage.
   - Return `checkout_url` = a success landing URL, plus additive `upgraded: true`.
   - Native: `https://{domain}/api/checkout-return?status=success`. The in-app browser closes, and the plan poll sees the new plan.
   - Web: `https://{domain}/#/subscribe?upgraded=1`, or another existing page that shows the current plan. It must not be the payment-success page that needs a `session_id`.
3. **Charge needs customer action (3DS) or failed.** The update stays pending in Stripe.
   - Return `checkout_url` = the latest invoice's `hosted_invoice_url`, plus `pending: true`. The customer pays there.
   - When Stripe applies the update, the `customer.subscription.updated` webhook sets `plan_id` and `billing_cycle` from the subscription metadata or the item price, but only for the tracked subscription.
4. **The same plan and cycle as the current one** returns `400` with a clear Turkish message, with no Stripe call.
5. **New subscriptions (no active tracked subscription).** Checkout as today, but pass `customer=<stored stripe_customer_id>` instead of `customer_email` when one is stored. This stops a duplicate Stripe customer from being created on re-subscribe.
6. **Webhook guard.** If `checkout.session.completed` activates a subscription for an org whose tracked subscription is a different, still-active one, cancel the previous one immediately with proration. This is a safety net for old app builds or races. Log it.
7. **Errors.** A Stripe currency mismatch, for example a TRY subscription changed to a GBP price, or any Stripe error returns `400` with a readable message. Log the error and never 500 silently.

## Non-goals
- No change to the response keys old clients read (`checkout_url`, `session_id` may be null on an upgrade).
- No Customer Portal configuration change.
- No refunds automation.

## Tests
Unit and integration tests mock `stripe`. Required cases:
- an upgrade modifies the existing subscription with the exact params and updates the plan;
- a downgrade does the same;
- a pending payment returns the hosted invoice URL and leaves the plan unchanged;
- the same plan returns 400;
- a new subscription uses the stored customer id;
- the webhook updated-event sets the plan for the tracked subscription only;
- the webhook completed-event cancels a different still-active subscription;
- a Stripe error returns 400.
