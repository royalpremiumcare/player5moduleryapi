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
 * Dahili / test hesapları — PostHog'a HİÇBİR veri gönderilmez (session replay +
 * event + pageview). Maskeleme değil, kaynağında opt-out: bu hesaplar login
 * olduğunda `opt_out_capturing()` ile tüm gönderim durur (bant genişliği +
 * depolama da harcanmaz). Normal kullanıcı login olunca opt-in ile geri açılır.
 * Not: PostHog sunucu tarafı "internal users" filtresi veriyi yine DEPOLAR;
 * gerçek engelleme yalnızca burada (client) mümkün.
 */
const INTERNAL_EMAILS = new Set([
  'royalpremiumcare@gmail.com',
  'fatihsenyuz12@gmail.com',
]);

function _isInternalEmail(email) {
  return !!email && INTERNAL_EMAILS.has(String(email).trim().toLowerCase());
}

/**
 * Geçici test bypass'ı. `localStorage.ph_debug === '1'` ise internal hesaplar
 * (royalpremiumcare, fatihsenyuz12) da NORMAL kullanıcı gibi capture eder —
 * böylece kendi hesabınla PostHog'da `screen` vb. property'leri doğrulayabilirsin.
 * Test bitince: `localStorage.removeItem('ph_debug')` → tekrar opt-out'a döner.
 * Konsoldan aç: localStorage.setItem('ph_debug','1'); location.reload();
 */
function _debugForceCapture() {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem('ph_debug') === '1';
  } catch (_) {
    return false;
  }
}

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

  // Test bypass flag'ini URL'den localStorage'a kalıcılaştır (DOĞRU ORIGIN garantisi).
  // Uygulama açılırken kendi origin'inde çalıştığı için flag her zaman doğru yere yazılır
  // (konsolda yanlış sekmede set etme sorununu tamamen ortadan kaldırır):
  //   https://www.plannapp.co/?ph_debug=1  → internal hesap da capture eder (test)
  //   https://www.plannapp.co/?ph_debug=0  → flag temizlenir (tekrar opt-out)
  try {
    if (typeof window !== 'undefined' && window.location) {
      const _v = new URLSearchParams(window.location.search || '').get('ph_debug');
      if (_v === '1') localStorage.setItem('ph_debug', '1');
      else if (_v === '0') localStorage.removeItem('ph_debug');
    }
  } catch (_) {}

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
    // Capacitor (iOS/Android WebView) tespiti — origin `capacitor://localhost` olduğunda
    // sendBeacon büyük session replay paketlerini WKWebView tarafından bloklanabilir.
    // Bu durumda `fetch` transport zorunlu (aksi halde replay parçaları yolda kaybolur).
    const isCapacitor = typeof window !== 'undefined' && (
      window.Capacitor?.isNativePlatform?.() === true ||
      /^capacitor:|^ionic:/i.test(window.location?.protocol || '')
    );

    _posthog.init(apiKey, {
      api_host: host,
      capture_pageview: true,
      capture_pageleave: true,
      autocapture: true,
      persistence: 'localStorage',
      // Capacitor'da sendBeacon güvenilir değil → fetch zorla
      api_transport: isCapacitor ? 'fetch' : undefined,
      // Capacitor `capacitor://localhost` origin'inde cookie mantığını kapat,
      // localStorage kullan. Aksi halde iOS WKWebView cookie doğrulaması SecurityError verir.
      cross_subdomain_cookie: false,
      secure_cookie: false,
      disable_session_recording: false,
      session_recording: {
        // Input'ları maskeleme KAPALI — session replay'de klavye girişleri
        // (isim, telefon, hizmet vb.) görünür. Ancak ŞİFRE alanları güvenlik/
        // KVKK için maskeli kalır. Gizlenmesi gereken özel alanlara `.ph-mask`
        // class'ı eklenebilir.
        maskAllInputs: false,
        maskInputOptions: { password: true },
        maskTextSelector: '.ph-mask',
        // iOS WKWebView'da canvas kaydı ilk snapshot'ta SecurityError'a yol açıp
        // rrweb'in ölmesine sebep oluyor → Capacitor'da kapat.
        recordCanvas: !isCapacitor,
        recordCrossOriginIframes: false,
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

  // Dahili/test hesabı → hiçbir şey gönderme (session replay dahil). Kişi de
  // oluşturma. opt-out localStorage'da kalıcı; aynı tarayıcıda normal kullanıcı
  // login olursa aşağıdaki opt-in ile geri açılır.
  // İSTİSNA: `ph_debug=1` flag'i varsa test amaçlı bypass → normal akışa düş.
  if (_isInternalEmail(user.username) && !_debugForceCapture()) {
    try { _posthog.opt_out_capturing(); } catch (_) {}
    return;
  }
  // Normal kullanıcı → önceki bir opt-out varsa geri al (cihaz paylaşımı senaryosu).
  try {
    if (typeof _posthog.has_opted_out_capturing === 'function' && _posthog.has_opted_out_capturing()) {
      _posthog.opt_in_capturing();
    }
  } catch (_) {}

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
 * `currentView` slug'ından → PostHog için Türkçe label + URL-güvenli Türkçe slug.
 * `screen` (Türkçe label) breakdown'da okunur; `$pathname` (Türkçe ama ASCII slug)
 * Paths/Url-Screen kolonunda temiz görünür; `screen_key` (ham İngilizce) kararlı
 * filtreleme içindir (label değişse bile funnel/filtre bozulmaz).
 */
const SCREEN_MAP_TR = {
  dashboard: { label: 'Ana Sayfa', slug: 'ana-sayfa' },
  calendar: { label: 'Takvim', slug: 'takvim' },
  sessions: { label: 'Aktif Seanslar', slug: 'aktif-seanslar' },
  customers: { label: 'Müşteriler', slug: 'musteriler' },
  services: { label: 'Hizmetler', slug: 'hizmetler' },
  staff: { label: 'Personel', slug: 'personel' },
  'marketing-assistant': { label: 'Pazarlama Asistanı', slug: 'pazarlama-asistani' },
  cash: { label: 'Kasa', slug: 'kasa' },
  audit: { label: 'Denetim Kayıtları', slug: 'denetim-kayitlari' },
  import: { label: 'İçe Aktar', slug: 'ice-aktar' },
  settings: { label: 'Ayarlar', slug: 'ayarlar' },
  'settings-subscription': { label: 'Ayarlar · Abonelik', slug: 'ayarlar-abonelik' },
  'settings-profile': { label: 'Ayarlar · Profil', slug: 'ayarlar-profil' },
  'settings-location': { label: 'Ayarlar · Konum', slug: 'ayarlar-konum' },
  'settings-online-booking': { label: 'Ayarlar · Online Randevu', slug: 'ayarlar-online-randevu' },
  'settings-finance': { label: 'Ayarlar · Finans', slug: 'ayarlar-finans' },
  'merchant-wallet': { label: 'Cüzdan', slug: 'cuzdan' },
  'merchant-refund-requests': { label: 'İade Talepleri', slug: 'iade-talepleri' },
  'merchant-payment-settings': { label: 'Ödeme Ayarları', slug: 'odeme-ayarlari' },
  subscribe: { label: 'Abonelik', slug: 'abonelik' },
  'help-center': { label: 'Yardım Merkezi', slug: 'yardim-merkezi' },
  superadmin: { label: 'Süper Admin', slug: 'superadmin' },
  marketing: { label: 'Pazarlama Paneli', slug: 'pazarlama-paneli' },
};

/**
 * Panel iç-ekran görüntüleme takibi (hibrit navigasyon: `currentView` state
 * URL değiştirmediği için otomatik `$pageview` bu ekranları GÖREMEZ).
 *
 * Performans: SADECE PostHog client'ına yazar (batch'lenir, non-blocking,
 * fire-and-forget) — mevcut `track()`'in aksine `/api/funnel/event` ledger'ına
 * POST ATMAZ. Böylece her ekran geçişinde ekstra network isteği/backend yükü
 * oluşmaz. Opt-out (dahili hesap) durumunda PostHog `capture`'ı zaten no-op'tur.
 *
 * Türkçe: `screen` = Türkçe label (ör. 'Müşteriler'), `$pathname` = Türkçe ASCII
 * slug (ör. '/app/musteriler'), `screen_key` = ham slug (ör. 'customers').
 *
 * @param {string} screen — currentView değeri (ör. 'dashboard', 'calendar')
 */
export function trackScreen(screen) {
  if (!screen) return;
  if (!_posthog || !_initialised) return;
  try {
    const meta = SCREEN_MAP_TR[screen] || { label: screen, slug: screen };
    const path = `/app/${meta.slug}`;
    const origin = (typeof window !== 'undefined' && window.location?.origin) || '';
    // Super property: o ekrandayken atılan HER event (autocapture tıklamalar dahil)
    // `screen`/`screen_key` taşır. Aksi halde tıklama event'lerinde SCREEN kolonu
    // boş (`-`) kalır çünkü panel URL'i değişmez. reset()/logout'ta temizlenir.
    // NOT: $pathname/$current_url REGISTER EDİLMEZ — yoksa tıklama event'lerinin
    // gerçek URL'ini ezerdi.
    _posthog.register({ screen: meta.label, screen_key: screen });
    _posthog.capture('$pageview', {
      $current_url: origin ? `${origin}${path}` : path,
      $pathname: path,
      screen: meta.label,   // Türkçe label — breakdown'da okunur
      screen_key: screen,   // ham İngilizce slug — kararlı filtre/funnel
      source: 'panel_view',
    });
  } catch (_) {
    // Ekran takibi hiçbir durumda UI akışını kırmaz
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
  trackScreen,
  optOut,
  optIn,
  isInitialised,
};
