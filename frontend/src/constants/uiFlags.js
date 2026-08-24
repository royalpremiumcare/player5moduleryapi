/**
 * UI feature flags — kod silmeden görünürlük kontrolü.
 * true yapınca ilgili UI tekrar görünür.
 */

/** Randevu kartları sağ üst: Bekliyor (nefes) / Tamamlandı / İptal ikonları */
export const SHOW_APPOINTMENT_CARD_STATUS = false;

/**
 * Mobil içi paket seçimi + Stripe Checkout (Faz 12).
 * Bu JS yalnız internal OTA'da; production 6.3.4 bu kodu içermez (Apple).
 * false = native'de yine "siteye git" kartı.
 */
export const SHOW_IN_APP_SUBSCRIBE = true;
