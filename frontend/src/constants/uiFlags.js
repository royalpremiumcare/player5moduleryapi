/**
 * UI feature flags — kod silmeden görünürlük kontrolü.
 * true yapınca ilgili UI tekrar görünür.
 */

/** Randevu kartları sağ üst: Bekliyor (nefes) / Tamamlandı / İptal ikonları */
export const SHOW_APPOINTMENT_CARD_STATUS = false;

/**
 * Mobil içi paket seçimi + Stripe Checkout (Faz 12).
 *
 * KAPALI (30 Eyl 2026, OTA). 29 Eyl'de açılmıştı; Apple review ekibi abonelik sayfasına baktı.
 * Açmak için önce iOS'ta IAP (StoreKit) gerekir; Google Play de Play Billing ister.
 * Native 6.4 review'ı sırasında da kapalıydı: Apple dijital abonelik
 * satışında IAP zorunlu tutuyor; uygulama içinde Stripe Checkout'a giden bir akış
 * reddedilme sebebi. Önceki varsayım "bu JS yalnız internal OTA'da, store build'i
 * içermez" idi — 6.4 ile bu artık DOĞRU DEĞİL, kod store build'ine gömülüyor.
 *
 * Yalnız native'i etkiler: `Subscribe.js` / `SettingsSubscription.js` içindeki
 * kapılar `isNative` ile ayrışıyor, web her hâlükârda paket seçiciyi gösterir.
 * false = native'de "siteye git" kartı.
 */
export const SHOW_IN_APP_SUBSCRIBE = false;
