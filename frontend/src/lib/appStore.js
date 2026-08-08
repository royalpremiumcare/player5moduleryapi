import { Capacitor } from "@capacitor/core";
import { openExternalUrl } from "@/lib/openExternalUrl";

// Mağaza yönlendirme hedefleri (push action: OPEN_STORE + force-update).
export const STORE_LINKS = {
  ios: {
    native: 'itms-apps://apps.apple.com/app/id6759719891',
    web: 'https://apps.apple.com/app/id6759719891',
  },
  android: {
    native: 'market://details?id=co.plannapp.app',
    web: 'https://play.google.com/store/apps/details?id=co.plannapp.app',
  },
};

/**
 * Kullanıcıyı işletim sistemine göre native mağaza uygulamasına yönlendirir;
 * native şema açılamazsa web mağaza linkine fallback yapar.
 *
 * Backend payload'u platforma özel anahtarlarla (store_url_ios /
 * store_url_android) veya genel store_url_native ile hedefleri override edebilir.
 */
export function openAppStore(data = {}) {
  const platform = Capacitor.getPlatform(); // 'ios' | 'android' | 'web'
  const conf = STORE_LINKS[platform] || STORE_LINKS.android;
  const nativeUrl = data[`store_url_${platform}`] || data.store_url_native || conf.native;
  const webUrl = data.store_url_web || conf.web;

  if (platform === 'web') {
    return openExternalUrl(webUrl);
  }

  try {
    const ok = openExternalUrl(nativeUrl);
    if (ok) return true;
  } catch (e) {
    console.warn('openAppStore native scheme failed, falling back to web', e);
  }
  return openExternalUrl(webUrl);
}
