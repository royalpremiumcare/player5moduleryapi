// Merchant payments (wallet, payment settings, online / deposit payment for services) are paused:
// PLANN may not hold money on behalf of businesses and the payout account is closed (2026-11-18).
// Flip to false only when a compliant payment solution is live; the backend has its own switch
// (MERCHANT_PAYMENTS_PAUSED) that refuses new online payments either way.
export const MERCHANT_PAYMENTS_PAUSED = true;

const ALL_PAYMENT_RULES = ['on_site', 'online', 'deposit'];

/** Payment rules a service form may offer. While paused only pay-at-salon. */
export function selectablePaymentRules(paused = MERCHANT_PAYMENTS_PAUSED) {
  return paused ? ['on_site'] : ALL_PAYMENT_RULES;
}

/** How a stored service rule behaves now: while paused online / deposit is pay-at-salon. */
export function effectivePaymentRule(rule, paused = MERCHANT_PAYMENTS_PAUSED) {
  const r = rule || 'on_site';
  return paused && r !== 'on_site' ? 'on_site' : r;
}
