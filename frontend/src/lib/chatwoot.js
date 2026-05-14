/**
 * Plann — Chatwoot Live-Chat Widget Loader
 *
 * Loads Chatwoot's SDK once on app boot. The launcher bubble is hidden by
 * default; the widget is opened programmatically via `openLiveChat()` from
 * `src/constants/contact.js`.
 *
 * Configuration:
 *   - REACT_APP_CHATWOOT_BASE_URL    (default: https://destek.plannapp.co)
 *   - REACT_APP_CHATWOOT_WEBSITE_TOKEN  (required — set after creating the
 *     Website Inbox in Chatwoot UI). If unset, the SDK does NOT load and
 *     `openLiveChat()` gracefully falls back to WhatsApp.
 */

const BASE_URL = process.env.REACT_APP_CHATWOOT_BASE_URL || "https://destek.plannapp.co";
const WEBSITE_TOKEN = process.env.REACT_APP_CHATWOOT_WEBSITE_TOKEN || "";

let loadPromise = null;
let pendingUser = null; // setChatwootUser sometimes called before SDK ready — buffer it

/**
 * Identify the current logged-in user inside Chatwoot. The widget will tag
 * subsequent conversations with this profile, so agents see the company
 * name + admin name instead of the auto-generated "small-dew" handle.
 *
 * `userInfo.identifier` must be a stable string (e.g. user_id). Call this
 * after login + settings load. Safe to call before the SDK has finished
 * loading — the call is buffered and replayed when ready.
 */
export function setChatwootUser(userInfo) {
  if (typeof window === "undefined" || !userInfo?.identifier) return;
  const payload = {
    name: userInfo.name || userInfo.company_name || userInfo.email || userInfo.identifier,
    email: userInfo.email || undefined,
    phone_number: userInfo.phone_number || undefined,
    avatar_url: userInfo.avatar_url || undefined,
    description: userInfo.description || undefined,
    company_name: userInfo.company_name || undefined,
    identifier_hash: userInfo.identifier_hash || undefined, // optional HMAC for verified identification
  };
  // Drop undefined keys so Chatwoot doesn't blank existing values.
  Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);

  const apply = () => {
    try {
      window.$chatwoot.setUser(String(userInfo.identifier), payload);
      // Extra custom attributes (org_id, role, sector) — searchable in Chatwoot.
      if (userInfo.custom_attributes && typeof window.$chatwoot.setCustomAttributes === "function") {
        window.$chatwoot.setCustomAttributes(userInfo.custom_attributes);
      }
    } catch (e) {
      console.warn("[Chatwoot] setUser failed:", e);
    }
  };

  if (window.$chatwoot && typeof window.$chatwoot.setUser === "function") {
    apply();
    return;
  }
  // Buffer until SDK fires `chatwoot:ready` event.
  pendingUser = { apply };
}

/**
 * Idempotent loader. Safe to call multiple times — only the first call
 * actually injects the script.
 */
export function loadChatwoot() {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (!WEBSITE_TOKEN) {
    // No token configured yet — skip silently (openLiveChat will fall back).
    return Promise.resolve(false);
  }
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve) => {
    // Configure the SDK before the script loads (Chatwoot reads these
    // settings from `window.chatwootSettings`).
    window.chatwootSettings = {
      hideMessageBubble: true,           // we control open/close manually
      position: "right",
      locale: "tr",
      type: "standard",
      darkMode: "auto",
    };

    const existing = document.querySelector('script[data-chatwoot-sdk]');
    if (existing) {
      // Script already in DOM (e.g. HMR re-render) — wait for it.
      existing.addEventListener("load", () => initRun(resolve));
      return;
    }

    const script = document.createElement("script");
    script.src = `${BASE_URL}/packs/js/sdk.js`;
    script.defer = true;
    script.async = true;
    script.dataset.chatwootSdk = "true";
    script.onload = () => initRun(resolve);
    script.onerror = () => {
      console.warn("[Chatwoot] SDK failed to load");
      resolve(false);
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}

function initRun(resolve) {
  if (!window.chatwootSDK || typeof window.chatwootSDK.run !== "function") {
    console.warn("[Chatwoot] SDK loaded but `chatwootSDK.run` is missing");
    resolve(false);
    return;
  }
  // SDK fires window event `chatwoot:ready` once `$chatwoot` API is mounted.
  // We flush any buffered setUser call there so login identity is applied
  // even if it was requested before the script finished loading.
  const onReady = () => {
    if (pendingUser) {
      try { pendingUser.apply(); } catch (_) {}
      pendingUser = null;
    }
  };
  window.addEventListener("chatwoot:ready", onReady, { once: false });

  // -----------------------------------------------------------------
  // iOS Safari klavye kapatma workaround'u
  //
  // Chatwoot widget cross-origin iframe içinde çalıştığı için parent'tan
  // input'a doğrudan blur() çağıramayız (same-origin policy). Bunun yerine
  // SDK'nın yayınladığı `chatwoot:on-message` event'ini dinleyip iframe
  // ELEMENT'ine `blur()` çağırıyoruz — bu, parent context'te olduğu için
  // izinli. iOS Safari iframe focus'unu kaybedince soft keyboard'u kapatır.
  // Aynı anda `document.activeElement.blur()` ile parent context'teki
  // backup focus'u da serbest bırakıyoruz.
  // -----------------------------------------------------------------
  const dismissKeyboard = () => {
    try {
      const iframe = document.querySelector(".woot-widget-holder iframe");
      if (iframe && typeof iframe.blur === "function") iframe.blur();
      if (
        document.activeElement &&
        typeof document.activeElement.blur === "function" &&
        document.activeElement !== document.body
      ) {
        document.activeElement.blur();
      }
    } catch (_) { /* sessizce yut */ }
  };
  window.addEventListener("chatwoot:on-message", dismissKeyboard);

  try {
    window.chatwootSDK.run({
      websiteToken: WEBSITE_TOKEN,
      baseUrl: BASE_URL,
    });
    resolve(true);
  } catch (e) {
    console.warn("[Chatwoot] init failed:", e);
    resolve(false);
  }
}
