// Giriş kapısının DIŞINDA, uygulama açılırken bir kez başlar. Widget / Live Activity
// bağlantılarını dokunma anında damgalayıp bekletir; App hazır olunca alıp uygular.
// Checkout bağlantıları parseAppDeepLink tarafından reddedilir (App'in dinleyicisi işler).
import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { parseAppDeepLink } from '../lib/deepLinks';
import { savePending } from '../lib/pendingDeepLink';

export const DEEP_LINK_EVENT = 'plann:deeplink';
const DUPLICATE_WINDOW_MS = 3000;

const LAUNCH_KEY = 'plann_last_launch_url';

let started = false;
let unclaimedUrl = null;
let lastUrl = null;
let lastAt = 0;

function handleUrl(url) {
  const intent = parseAppDeepLink(url);
  if (!intent) {
    // Checkout gibi bizim olmayan bağlantı: App'in dinleyicisi sonradan alabilsin
    if (url) unclaimedUrl = url;
    return;
  }
  const now = Date.now();
  // getLaunchUrl + tutulan appUrlOpen aynı bağlantıyı iki kez getirebilir
  if (url === lastUrl && now - lastAt < DUPLICATE_WINDOW_MS) return;
  lastUrl = url;
  lastAt = now;
  savePending(intent);
  window.dispatchEvent(new CustomEvent(DEEP_LINK_EVENT, { detail: intent }));
}

export function takeUnclaimedUrl() {
  const url = unclaimedUrl;
  unclaimedUrl = null;
  return url;
}

// Çıkış sayfayı yeniler (yeni JS çalışma zamanı) ama native getLaunchUrl son URL'i
// döndürmeye devam eder; aynı oturumda zaten işlenmiş launch URL'i tekrar uygulanmaz.
function launchAlreadyHandled(url) {
  try {
    if (window.sessionStorage.getItem(LAUNCH_KEY) === url) return true;
    window.sessionStorage.setItem(LAUNCH_KEY, url);
  } catch {
    /* storage kapalı */
  }
  return false;
}

export function startDeepLinkInbox() {
  if (started || !Capacitor.isNativePlatform()) return;
  started = true;
  CapacitorApp.addListener('appUrlOpen', (event) => handleUrl(event?.url));
  // getLaunchUrl son açılan URL'i döndürür; JS çalışma zamanı başına yalnızca bir kez sorulur
  CapacitorApp.getLaunchUrl()
    .then((launch) => {
      const url = launch?.url;
      if (url && !launchAlreadyHandled(url)) handleUrl(url);
    })
    .catch(() => {});
}
