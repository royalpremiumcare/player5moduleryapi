import { Capacitor } from '@capacitor/core';
import { App as CapApp } from '@capacitor/app';

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
 * Harici URL'i sistem tarayıcısında açar (çoklu fallback ile).
 *
 * Native: CapApp.openUrl → window.open(_system) → anchor click → location.href
 * Web: window.open(_blank) → anchor click → location.href
 *
 * @param {string} url - Açılacak harici URL
 * @returns {Promise<boolean>} Başarılı olursa true
 */
export async function openExternalUrl(url) {
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

  try {
    await CapApp.openUrl({ url });
    return true;
  } catch (err) {
    console.warn('CapApp.openUrl failed, fallback to window.open(_system)', err);
  }

  try {
    const win = window.open(url, '_system');
    if (win !== null) return true;
  } catch (err2) {
    console.warn('window.open(_system) failed', err2);
  }

  try {
    openViaAnchor(url);
    return true;
  } catch (err3) {
    console.warn('anchor click failed on native', err3);
  }

  try {
    window.location.href = url;
    return true;
  } catch (err4) {
    console.error('openExternalUrl(native) all fallbacks failed', err4);
    return false;
  }
}

export default openExternalUrl;
