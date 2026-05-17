/**
 * Meta Pixel + Conversions API hibrit takip helper'ı.
 *
 * Mimari:
 *  - `init()` uygulama açılırken bir kez çağrılır (`index.js`).
 *  - `track(eventName, customData, userData)` event emit eder:
 *      1) Aynı `eventID` ile Meta Pixel (tarayıcı) → `react-facebook-pixel`
 *      2) Aynı `event_id` ile backend `/api/meta/event` endpoint'i (CAPI mirror)
 *    Meta her iki sinyali `event_id` üzerinden tekilleştirir → tarayıcı engelleri
 *    (adblock, iOS ITP, third-party cookie restrictions) aşılır.
 *  - PII (email/phone/ad-soyad) backend'e raw gönderilir; backend SHA256 hashler
 *    ve Meta'ya yollar. Frontend hashlemez (hash'i tek noktada tutmak güvenlik
 *    açısından daha temiz).
 *
 * Graceful degrade:
 *  - `REACT_APP_META_PIXEL_ID` boşsa init no-op olur; `track` çağrıları yine
 *    backend ledger'ına best-effort POST atar (CAPI tek başına çalışabilir).
 *  - Hatalar kullanıcı akışını kırmaz (try/catch + console.warn).
 */

import api from '../api/api';

let _ReactPixel = null;
let _initialised = false;
let _initAttempted = false;
let _pixelId = null;

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

/** UUIDv4 üretici (crypto.randomUUID + fallback). */
function newEventId() {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch (_) {}
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** `_fbp` cookie değerini okur (Pixel set eder). */
function readFbp() {
  try {
    const m = document.cookie.match(/(?:^|; )_fbp=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  } catch (_) {
    return null;
  }
}

/**
 * `_fbc` üretir / okur:
 *   - Cookie varsa onu kullan.
 *   - Yoksa URL'deki `fbclid`'den `fb.1.{ts}.{fbclid}` formatını üret.
 */
function readFbc() {
  try {
    const cookie = document.cookie.match(/(?:^|; )_fbc=([^;]+)/);
    if (cookie) return decodeURIComponent(cookie[1]);

    const params = new URLSearchParams(window.location.search);
    const fbclid = params.get('fbclid');
    if (fbclid) {
      return `fb.1.${Date.now()}.${fbclid}`;
    }
    return null;
  } catch (_) {
    return null;
  }
}

/**
 * Telefon normalize: sadece rakamları bırak (backend zaten normalize eder ama
 * gereksiz hash farklılıklarını önlemek için frontend'de de yapıyoruz).
 */
function normalizePhone(phone) {
  if (!phone) return undefined;
  const digits = String(phone).replace(/\D/g, '');
  return digits || undefined;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

/**
 * Meta Pixel'i init eder. Idempotent — birden fazla çağrı no-op.
 * @param {Object} [options]
 * @param {string} [options.pixelId] — REACT_APP_META_PIXEL_ID override
 * @param {boolean} [options.advancedMatching=true]
 * @param {boolean} [options.debug=false]
 * @returns {Promise<boolean>} init başarısı
 */
export async function init(options = {}) {
  if (_initAttempted) return _initialised;
  _initAttempted = true;

  const pixelId = options.pixelId || process.env.REACT_APP_META_PIXEL_ID;
  if (!pixelId) {
    if (process.env.NODE_ENV !== 'production') {
      console.info('[meta-pixel] REACT_APP_META_PIXEL_ID set değil — Pixel disabled (CAPI hâlâ aktif).');
    }
    return false;
  }

  try {
    const mod = await import('react-facebook-pixel');
    _ReactPixel = mod.default || mod;
    _ReactPixel.init(pixelId, undefined, {
      autoConfig: true,
      debug: !!options.debug,
    });
    _ReactPixel.pageView();
    _pixelId = pixelId;
    _initialised = true;
    return true;
  } catch (err) {
    console.warn('[meta-pixel] init failed:', err);
    _ReactPixel = null;
    _initialised = false;
    return false;
  }
}

/**
 * Pixel'in yüklendikten sonra advanced matching ile kullanıcı tanıması yapması için.
 * Login/onboarding sonrası bilinen email/phone'u Pixel cookie'sine yansıtır.
 *
 * @param {{ email?: string, phone?: string, firstName?: string, lastName?: string, externalId?: string }} info
 */
export function identify(info = {}) {
  if (!_ReactPixel || !_initialised) return;
  try {
    // react-facebook-pixel `setUserProperties`/`init` ile advanced matching destekler.
    // Burada Pixel tarafına setUserProperties ile yansıtırız (FB hash'i kendi yapar).
    const matching = {};
    if (info.email) matching.em = info.email.trim().toLowerCase();
    if (info.phone) matching.ph = normalizePhone(info.phone);
    if (info.firstName) matching.fn = info.firstName.trim().toLowerCase();
    if (info.lastName) matching.ln = info.lastName.trim().toLowerCase();
    if (info.externalId) matching.external_id = String(info.externalId);

    if (Object.keys(matching).length > 0 && _pixelId) {
      _ReactPixel.init(_pixelId, matching, { autoConfig: true, debug: false });
    }
  } catch (err) {
    console.warn('[meta-pixel] identify failed:', err);
  }
}

// ---------------------------------------------------------------------------
// Track (hibrit)
// ---------------------------------------------------------------------------

/**
 * Pixel ↔ CAPI hibrit event gönderir.
 *
 * @param {string} eventName — `Lead` | `Schedule` | `InitiateCheckout` | `AddPaymentInfo`
 *                            | `Purchase` | `CompleteRegistration` | `ViewContent` | custom...
 * @param {Object} [params]
 * @param {Object} [params.customData] — Meta `custom_data` (content_name, value, currency, ...)
 * @param {Object} [params.userData]   — Raw PII (contact_email, contact_phone, contact_name, ...)
 *                                       Backend hashler.
 * @param {string} [params.eventId]    — Override; verilmezse UUID üretilir.
 * @param {string} [params.eventSourceUrl] — Default: `window.location.href`
 * @param {string} [params.actionSource]   — Default: `website`
 * @param {string} [params.testEventCode]  — Meta Test Events Manager kodu (sadece test).
 * @returns {string} kullanılan eventId
 */
export function track(eventName, params = {}) {
  if (!eventName) return null;

  const eventId = params.eventId || newEventId();
  const eventSourceUrl = params.eventSourceUrl || (typeof window !== 'undefined' ? window.location.href : undefined);
  const actionSource = params.actionSource || 'website';
  const customData = params.customData || {};
  const userData = params.userData || {};

  // ---- 1) Pixel (tarayıcı) ----
  if (_ReactPixel && _initialised) {
    try {
      const isStandard = STANDARD_EVENTS.has(eventName);
      const fn = isStandard ? _ReactPixel.track : _ReactPixel.trackCustom;
      fn.call(_ReactPixel, eventName, customData, { eventID: eventId });
    } catch (err) {
      if (process.env.NODE_ENV !== 'production') {
        console.warn(`[meta-pixel] Pixel.track(${eventName}) failed:`, err);
      }
    }
  }

  // ---- 2) Backend CAPI mirror ----
  // Phone normalize edilir; backend de aynısını yapacak ama hash uyumu için kritik.
  const phNormalized = normalizePhone(userData.contact_phone || userData.phone);

  const body = {
    event_name: eventName,
    event_id: eventId,
    event_time: Math.floor(Date.now() / 1000),
    event_source_url: eventSourceUrl,
    action_source: actionSource,
    user_data: {
      contact_email: userData.contact_email || userData.email || undefined,
      contact_phone: phNormalized,
      contact_name: userData.contact_name || userData.fullName || undefined,
      first_name: userData.first_name || userData.firstName || undefined,
      last_name: userData.last_name || userData.lastName || undefined,
      external_id: userData.external_id || userData.externalId || undefined,
      country: userData.country || undefined,
      city: userData.city || undefined,
      state: userData.state || undefined,
      zip_code: userData.zip_code || userData.zip || undefined,
    },
    custom_data: {
      content_name: customData.content_name,
      content_category: customData.content_category,
      content_ids: customData.content_ids,
      content_type: customData.content_type,
      value: customData.value,
      currency: customData.currency || 'TRY',
      num_items: customData.num_items,
      order_id: customData.order_id,
      predicted_ltv: customData.predicted_ltv,
      status: customData.status,
    },
    fbp: readFbp() || undefined,
    fbc: readFbc() || undefined,
    test_event_code: params.testEventCode || undefined,
  };

  // Boş alanları temizle (backend zaten exclude_none kullanıyor ama temiz olsun).
  const stripEmpty = (obj) => {
    Object.keys(obj).forEach((k) => {
      if (obj[k] === undefined || obj[k] === null || obj[k] === '') delete obj[k];
    });
    return obj;
  };
  stripEmpty(body.user_data);
  stripEmpty(body.custom_data);
  if (Object.keys(body.user_data).length === 0) delete body.user_data;
  if (Object.keys(body.custom_data).length === 0) delete body.custom_data;
  stripEmpty(body);

  // Fire-and-forget. Auth header zaten interceptor'da otomatik eklenir;
  // anonim kullanıcıda Authorization olmadan POST atılır (endpoint public).
  api.post('/meta/event', body).catch((err) => {
    if (process.env.NODE_ENV !== 'production') {
      console.debug(`[meta-capi] '${eventName}' POST failed:`, err?.response?.status || err?.message);
    }
  });

  return eventId;
}

/**
 * Sayfa görüntüleme — SPA route değişimlerinde manuel çağrılabilir.
 */
export function pageView() {
  if (_ReactPixel && _initialised) {
    try {
      _ReactPixel.pageView();
    } catch (_) {}
  }
}

/** Pixel'den event silmek için (KVKK opt-out). */
export function revoke() {
  if (_ReactPixel && _initialised) {
    try {
      _ReactPixel.revokeConsent();
    } catch (_) {}
  }
}

export function grant() {
  if (_ReactPixel && _initialised) {
    try {
      _ReactPixel.grantConsent();
    } catch (_) {}
  }
}

export function isInitialised() {
  return _initialised;
}

// ---------------------------------------------------------------------------
// Standart event seti — `track()` içinde Pixel.track vs Pixel.trackCustom seçimi için.
// ---------------------------------------------------------------------------
const STANDARD_EVENTS = new Set([
  'PageView',
  'ViewContent',
  'Search',
  'AddToCart',
  'AddToWishlist',
  'InitiateCheckout',
  'AddPaymentInfo',
  'Purchase',
  'Lead',
  'CompleteRegistration',
  'Contact',
  'CustomizeProduct',
  'Donate',
  'FindLocation',
  'Schedule',
  'StartTrial',
  'SubmitApplication',
  'Subscribe',
]);

export default {
  init,
  identify,
  track,
  pageView,
  revoke,
  grant,
  isInitialised,
};
