// Giriş kapısının DIŞINDA, uygulama açılırken bir kez başlar. Widget / Live Activity
// bağlantılarını dokunma anında damgalayıp bekletir; App hazır olunca alıp uygular.
// Checkout bağlantıları parseAppDeepLink tarafından reddedilir (App'in dinleyicisi işler).
import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { parseAppDeepLink } from '../lib/deepLinks';
import { savePending } from '../lib/pendingDeepLink';

export const DEEP_LINK_EVENT = 'plann:deeplink';
const DUPLICATE_WINDOW_MS = 3000;

let started = false;
let lastUrl = null;
let lastAt = 0;

function handleUrl(url) {
  const intent = parseAppDeepLink(url);
  if (!intent) return;
  const now = Date.now();
  // getLaunchUrl + tutulan appUrlOpen aynı bağlantıyı iki kez getirebilir
  if (url === lastUrl && now - lastAt < DUPLICATE_WINDOW_MS) return;
  lastUrl = url;
  lastAt = now;
  savePending(intent);
  window.dispatchEvent(new CustomEvent(DEEP_LINK_EVENT, { detail: intent }));
}

export function startDeepLinkInbox() {
  if (started || !Capacitor.isNativePlatform()) return;
  started = true;
  CapacitorApp.addListener('appUrlOpen', (event) => handleUrl(event?.url));
  // getLaunchUrl son açılan URL'i döndürür; JS çalışma zamanı başına yalnızca bir kez sorulur
  CapacitorApp.getLaunchUrl()
    .then((launch) => handleUrl(launch?.url))
    .catch(() => {});
}
