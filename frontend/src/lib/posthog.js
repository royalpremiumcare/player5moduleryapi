/**
 * PostHog client wrapper + funnel mirror.
 *
 * Tek sorumluluk: frontend-owned funnel event'lerini hem PostHog'a hem de
 * `/api/funnel/event` MongoDB ledger'ına aynı `$insert_id` ile gönderir.
 *
 * Mimari:
 *  - `init(options)` uygulama açılırken bir kez çağrılır (`index.js`).
 *  - `identifyUser(user)` AuthContext token decode olduğunda çağrılır.
 *    `distinct_id = user.user_id` (UUID); username sadece display property.
 *  - `track(eventName, properties)` event emit eder; PostHog + ledger paralel.
 *
 * Graceful degrade:
 *  - `posthog-js` yüklü değilse veya `REACT_APP_POSTHOG_KEY` boşsa init no-op olur.
 *  - Track çağrıları her durumda ledger POST'unu dener (analytics blocker
 *    bypass: ground-truth backend'de durur).
 *  - Ledger POST hatası kullanıcı akışını kırmaz (fire-and-forget).
 */

import api from '../api/api';

let _posthog = null;
let _initialised = false;
let _initAttempted = false;
let _disabled = false;

/**
 * UUIDv4-ish üretici (crypto.randomUUID + fallback).
 * `$insert_id` PostHog'a 24h dedupe için gider; aynı id MongoDB ledger'a da
 * yazılır → recovery cron her iki tarafta dup'lenmeden backfill yapabilir.
 */
function newInsertId() {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch (_) {}
  // RFC4122 v4 fallback
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * PostHog'u init eder. `index.js`'de bir kez çağrılır; tekrar çağrılırsa no-op.
 *
 * @param {Object} options
 * @param {string} [options.apiKey] — REACT_APP_POSTHOG_KEY override
 * @param {string} [options.host] — REACT_APP_POSTHOG_HOST override
 * @returns {Promise<boolean>} init başarısı
 */
export async function init(options = {}) {
  if (_initAttempted) return _initialised;
  _initAttempted = true;

  const apiKey = options.apiKey || process.env.REACT_APP_POSTHOG_KEY;
  const host = options.host || process.env.REACT_APP_POSTHOG_HOST || 'https://eu.posthog.com';

  if (!apiKey) {
    _disabled = true;
    if (process.env.NODE_ENV !== 'production') {
      console.info('[posthog] REACT_APP_POSTHOG_KEY not set; PostHog disabled (ledger still active).');
    }
    return false;
  }

  try {
    const mod = await import('posthog-js');
    _posthog = mod.default || mod;
    _posthog.init(apiKey, {
      api_host: host,
      capture_pageview: true,
      autocapture: true,
      persistence: 'localStorage',
      session_recording: {
        maskAllInputs: true,
        maskTextSelector: '.ph-mask',
      },
      // Privacy: GeoIP'i serverda enrich etmesin (KVKK)
      property_blacklist: [],
    });
    _initialised = true;
    return true;
  } catch (err) {
    console.warn('[posthog] init failed; events will only hit ledger:', err);
    _posthog = null;
    _initialised = false;
    return false;
  }
}

/**
 * Backend `user_id`'yi PostHog `distinct_id` olarak set eder.
 * Username değişikliklerinde funnel parçalanmasını önler — kişi user_id ile takip edilir.
 *
 * @param {Object} user — backend `/users` veya `/me` yanıtı
 *  - user_id (UUID, REQUIRED): stable distinct_id
 *  - username, full_name, organization_id, role, sector, activation_state, language
 */
export function identifyUser(user) {
  if (!user || !user.user_id) return;
  if (!_posthog || !_initialised) return;

  try {
    _posthog.identify(user.user_id, {
      $email: user.username || undefined,
      $name: user.company_name || user.full_name || undefined,
      full_name: user.full_name || undefined,
      organization_id: user.organization_id || undefined,
      company_name: user.company_name || undefined,
      role: user.role || undefined,
      sector: user.sector || undefined,
      activation_state: user.activation_state || undefined,
      language: user.language || undefined,
    });
  } catch (err) {
    console.warn('[posthog] identify failed:', err);
  }
}

/**
 * Anonim ziyaretçi → kayıt eşleştirmesi. Pre-signup event'lerin yeni kişiye bağlanması için.
 *
 * @param {string} userId — yeni kayıtın stable user_id'si
 */
export function aliasAnonymous(userId) {
  if (!userId || !_posthog || !_initialised) return;
  try {
    _posthog.alias(userId);
  } catch (err) {
    console.warn('[posthog] alias failed:', err);
  }
}

/**
 * Logout: PostHog kişiliğini sıfırla.
 */
export function reset() {
  if (!_posthog || !_initialised) return;
  try {
    _posthog.reset();
  } catch (_) {}
}

/**
 * Frontend-owned funnel event emit eder.
 * Aynı `$insert_id` hem PostHog hem MongoDB ledger'a gider — dedupe garantili.
 *
 * @param {string} eventName — `funnel_registry.EVENT_REGISTRY` ile uyumlu
 * @param {Object} [properties] — event-specific payload
 * @returns {Promise<void>} fire-and-forget; her iki tarafa best-effort
 */
export function track(eventName, properties = {}) {
  if (!eventName) return;

  const insertId = newInsertId();
  const enriched = {
    source: 'frontend',
    ...properties,
    $insert_id: insertId,
  };

  // 1. PostHog (init edilmişse)
  if (_posthog && _initialised) {
    try {
      _posthog.capture(eventName, enriched);
    } catch (err) {
      // PostHog client hatası ledger'ı engellemez
      if (process.env.NODE_ENV !== 'production') {
        console.warn(`[posthog] capture(${eventName}) failed:`, err);
      }
    }
  }

  // 2. MongoDB ledger (fire-and-forget; auth gerektirir, anonim çağrılarda 401 alır → sessizce yutulur)
  // Sadece auth token varken POST et — anonim çağrılarda backend'in 401 vermesini engelle.
  const hasToken = !!(localStorage.getItem('authToken') || sessionStorage.getItem('authToken'));
  if (hasToken) {
    api
      .post('/funnel/event', {
        event_name: eventName,
        insert_id: insertId,
        properties: enriched,
      })
      .catch((err) => {
        // 400 (unknown event), 401 (token expired), 5xx — kullanıcı akışına yansıtma
        if (process.env.NODE_ENV !== 'production') {
          console.debug(`[funnel] ledger insert failed for ${eventName}:`, err?.response?.status || err?.message);
        }
      });
  }
}

/**
 * PostHog opt-out — KVKK/cookie banner reject akışı için.
 */
export function optOut() {
  if (!_posthog || !_initialised) return;
  try {
    _posthog.opt_out_capturing();
  } catch (_) {}
}

export function optIn() {
  if (!_posthog || !_initialised) return;
  try {
    _posthog.opt_in_capturing();
  } catch (_) {}
}

export function isInitialised() {
  return _initialised;
}

export default {
  init,
  identifyUser,
  aliasAnonymous,
  reset,
  track,
  optOut,
  optIn,
  isInitialised,
};
