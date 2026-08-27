/**
 * Faz 12 — mobil içi abonelik checkout.
 *
 * Native picker `SHOW_IN_APP_SUBSCRIBE` ile açılır. Native 6.4 store
 * build'ine gömüldüğü için Apple review süresince flag KAPALI
 * (`constants/uiFlags.js`); native'de "siteye git" kartı görünür.
 *
 * Checkout URL'si sistem tarayıcısına değil @capacitor/browser (SFSafariViewController /
 * Chrome Custom Tabs) ile açılır.
 *
 * SFSafariViewController `plannapp://` custom scheme'i yutabilir. Güvenlik ağı:
 * 1) appUrlOpen deep link
 * 2) browserFinished
 * 3) Browser açıkken + kapandıktan sonra confirm + GET /plan/current poll
 */
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import api from '../api/api';
import { SHOW_IN_APP_SUBSCRIBE } from '../constants/uiFlags';

const POLL_WHILE_OPEN_MS = 2500;
const POLL_AFTER_CLOSE_MS = 1500;
const EXTRA_PROBES_AFTER_CLOSE = 10;

const listeners = new Set();

let watchGeneration = 0;
let watch = createIdleWatch();
let browserHooked = false;
let browserOpen = false;
let settleLoopRunning = false;

function createIdleWatch() {
  return {
    gen: watchGeneration,
    sessionId: null,
    baseline: null,
    openedAt: 0,
    settled: true,
    aborted: true,
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function subscribeCheckoutEvents(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(event) {
  listeners.forEach((fn) => {
    try {
      fn(event);
    } catch (err) {
      console.warn('inAppSubscribe listener error', err);
    }
  });
}

export async function resolveInAppSubscribeEnabled() {
  return !!SHOW_IN_APP_SUBSCRIBE;
}

export function snapshotPlan(plan) {
  if (!plan) return null;
  return {
    plan_id: plan.plan_id || null,
    is_trial: !!plan.is_trial,
    billing_cycle: plan.billing_cycle || (plan.is_yearly ? 'yearly' : 'monthly'),
  };
}

export function planLooksUpgraded(before, after) {
  if (!after || !before) return false;
  if (before.is_trial && !after.is_trial) return true;
  if (before.plan_id && after.plan_id && before.plan_id !== after.plan_id) return true;
  const beforeCycle = before.billing_cycle || 'monthly';
  const afterCycle = after.billing_cycle || 'monthly';
  if (beforeCycle !== afterCycle) return true;
  return false;
}

export function parseCheckoutDeepLink(url) {
  if (!url || typeof url !== 'string') return { kind: null, sessionId: null };
  const lower = url.toLowerCase();
  let sessionId = null;
  try {
    const normalized = url.replace(/^[a-z][a-z0-9+.-]*:\/\//i, 'https://plannapp.local/');
    const parsed = new URL(normalized);
    sessionId = parsed.searchParams.get('session_id');
  } catch (_) {
    const match = url.match(/[?&]session_id=([^&]+)/i);
    if (match) sessionId = decodeURIComponent(match[1]);
  }

  if (lower.includes('payment-success')) return { kind: 'success', sessionId };
  const isCustomScheme = /^plannapp:\/\//i.test(url);
  if (isCustomScheme && (lower.includes('subscribe') || /plannapp:\/\/dashboard/i.test(url))) {
    return { kind: 'cancel', sessionId: null };
  }
  return { kind: null, sessionId };
}

async function fetchCurrentPlan() {
  const response = await api.get('/plan/current');
  return response.data;
}

async function confirmSession(sessionId) {
  const response = await api.post('/payments/confirm-checkout-session', {
    session_id: sessionId,
  });
  return response.data;
}

async function probeOnce() {
  const sessionId = watch.sessionId;
  if (sessionId) {
    try {
      await confirmSession(sessionId);
      return 'paid';
    } catch (err) {
      const status = err?.response?.status;
      if (status && status !== 400) {
        console.warn('inAppSubscribe: confirm failed', status, err?.response?.data || err.message);
      }
    }
  }

  try {
    const current = await fetchCurrentPlan();
    if (planLooksUpgraded(watch.baseline, current)) return 'paid';
  } catch (err) {
    console.warn('inAppSubscribe: plan/current poll failed', err?.message);
  }
  return 'pending';
}

async function markPaid() {
  if (watch.settled) return;
  watch.settled = true;
  browserOpen = false;
  await closeCheckoutBrowser();
  emit({ type: 'upgraded', sessionId: watch.sessionId });
}

async function markUnresolved() {
  if (watch.settled) return;
  watch.settled = true;
  const elapsed = Date.now() - (watch.openedAt || 0);
  emit({ type: 'unresolved', elapsedMs: elapsed, sessionId: watch.sessionId });
}

async function runSettleLoop() {
  if (settleLoopRunning) return;
  settleLoopRunning = true;
  let extraAfterClose = 0;

  try {
    while (!watch.settled && !watch.aborted) {
      const gen = watch.gen;
      const outcome = await probeOnce();
      if (watch.gen !== gen) {
        extraAfterClose = 0;
        continue;
      }
      if (watch.aborted || watch.settled) break;
      if (outcome === 'paid') {
        await markPaid();
        break;
      }

      if (!browserOpen) {
        extraAfterClose += 1;
        if (extraAfterClose >= EXTRA_PROBES_AFTER_CLOSE) {
          await markUnresolved();
          break;
        }
        await sleep(POLL_AFTER_CLOSE_MS);
      } else {
        extraAfterClose = 0;
        await sleep(POLL_WHILE_OPEN_MS);
      }
    }
  } finally {
    settleLoopRunning = false;
    if (!watch.settled && !watch.aborted) {
      runSettleLoop();
    }
  }
}

function ensureBrowserHook() {
  if (browserHooked || !Capacitor.isNativePlatform()) return;
  browserHooked = true;
  Browser.addListener('browserFinished', () => {
    browserOpen = false;
    emit({ type: 'browser-finished' });
    if (!watch.settled && !watch.aborted) {
      runSettleLoop();
    }
  });
}

export async function closeCheckoutBrowser() {
  if (!Capacitor.isNativePlatform()) return;
  try {
    await Browser.close();
  } catch (_) {
    /* zaten kapalı */
  }
  browserOpen = false;
}

export async function openCheckoutInAppBrowser(url) {
  ensureBrowserHook();
  browserOpen = true;
  await Browser.open({
    url,
    presentationStyle: 'fullscreen',
    toolbarColor: '#18181b',
  });
}

export function startCheckoutWatch({ sessionId, baseline }) {
  watchGeneration += 1;
  watch = {
    gen: watchGeneration,
    sessionId: sessionId || null,
    baseline: snapshotPlan(baseline),
    openedAt: Date.now(),
    settled: false,
    aborted: false,
  };
  browserOpen = true;
  ensureBrowserHook();
  emit({ type: 'opened', sessionId: watch.sessionId });
  runSettleLoop();
}

export function abortCheckoutWatch() {
  watch.aborted = true;
  watch.settled = true;
  browserOpen = false;
}

export async function handleCheckoutDeepLink(url) {
  const parsed = parseCheckoutDeepLink(url);
  if (parsed.kind === 'success') {
    if (parsed.sessionId) watch.sessionId = parsed.sessionId;
    await closeCheckoutBrowser();
    emit({ type: 'deep-link-success', sessionId: parsed.sessionId });
    runSettleLoop();
    return parsed;
  }
  if (parsed.kind === 'cancel') {
    await closeCheckoutBrowser();
    watch.aborted = true;
    watch.settled = true;
    emit({ type: 'dismissed', reason: 'cancel-link' });
    return parsed;
  }
  return parsed;
}

export async function openPortalInAppBrowser(url) {
  ensureBrowserHook();
  await Browser.open({
    url,
    presentationStyle: 'fullscreen',
    toolbarColor: '#18181b',
  });
}
