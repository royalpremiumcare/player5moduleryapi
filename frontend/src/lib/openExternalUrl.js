import { Capacitor } from '@capacitor/core';

/**
 * WKWebView / PWA'da user-gesture bağlamı kaybolduğunda (async API sonrası)
 * window.open bloklanabilir. Gerçek <a> click bu kısıtlamayı aşar.
 */
function openViaAnchor(url) {
  const a = document.createElement('a');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.style.position = 'fixed';
  a.style.left = '-9999px';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    try { document.body.removeChild(a); } catch (_) {}
  }, 100);
}

/**
 * Harici URL'i sistem tarayıcısında açar.
 *
 * Capacitor 7'de App.openUrl yok. Native'de window.open(_blank) veya
 * location.assign, WKWebView delegate üzerinden UIApplication.shared.open /
 * Android Intent ile dış tarayıcıyı açar.
 *
 * @param {string} url - Açılacak harici URL
 * @returns {boolean} Başarılı olursa true
 */
export function openExternalUrl(url) {
  if (!url) return false;

  if (!Capacitor.isNativePlatform()) {
    try {
      const win = window.open(url, '_blank');
      if (win) return true;
    } catch (err) {
      console.warn('window.open(_blank) failed', err);
    }
    try {
      openViaAnchor(url);
      return true;
    } catch (err) {
      console.warn('anchor click failed, fallback to location.href', err);
    }
    try {
      window.location.href = url;
      return true;
    } catch (err2) {
      console.error('openExternalUrl(web) all fallbacks failed', err2);
      return false;
    }
  }

  // iOS: createWebViewWith → UIApplication.shared.open
  // Android: Bridge.shouldOverrideUrlLoading → ACTION_VIEW intent
  try {
    window.open(url, '_blank');
    return true;
  } catch (err) {
    console.warn('window.open(_blank) failed on native', err);
  }

  try {
    openViaAnchor(url);
    return true;
  } catch (err2) {
    console.warn('anchor click failed on native', err2);
  }

  try {
    window.location.assign(url);
    return true;
  } catch (err3) {
    console.error('openExternalUrl(native) all fallbacks failed', err3);
    return false;
  }
}

export default openExternalUrl;
