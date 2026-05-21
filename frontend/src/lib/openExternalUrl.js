import { Capacitor } from '@capacitor/core';
import { App as CapApp } from '@capacitor/app';

/**
 * Harici URL'i sistem tarayıcısında açar (üçlü fallback ile).
 *
 * Native platformlarda Capacitor `App.openUrl()` API'si kullanılır →
 * cihazın varsayılan tarayıcısı (Safari/Chrome) açılır, in-app browser
 * (SafariViewController / Custom Tabs) DEĞİL.
 *
 * Hata kurgusu (Plan 12.4):
 *   1. CapApp.openUrl başarısız → window.open(url, '_system')
 *      (Capacitor WebView'da _system sistem browser'a yönlendirir).
 *   2. _system de başarısız → window.open(url, '_blank') (son çare).
 *   3. Web ortamında doğrudan window.open(_blank).
 *
 * Uygulama HİÇBİR senaryoda crash etmez; başarısız fallback'ler konsola
 * loglanır ve sessizce alternatif yola geçilir.
 *
 * @param {string} url - Açılacak harici URL
 * @returns {Promise<void>}
 */
export async function openExternalUrl(url) {
  if (!url) return;

  if (!Capacitor.isNativePlatform()) {
    try {
      window.open(url, '_blank');
    } catch (err) {
      console.warn('window.open(_blank) failed, fallback to location.href', err);
      try {
        window.location.href = url;
      } catch (err2) {
        console.error('openExternalUrl(web) all fallbacks failed', err2);
      }
    }
    return;
  }

  try {
    await CapApp.openUrl({ url });
    return;
  } catch (err) {
    console.warn('CapApp.openUrl failed, fallback to window.open(_system)', err);
  }

  try {
    window.open(url, '_system');
    return;
  } catch (err2) {
    console.warn('window.open(_system) failed, fallback to _blank', err2);
  }

  try {
    window.open(url, '_blank');
  } catch (err3) {
    console.error('openExternalUrl(native) all fallbacks failed', err3);
  }
}

export default openExternalUrl;
