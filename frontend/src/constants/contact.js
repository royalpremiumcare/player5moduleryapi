/**
 * Plann — Contact Constants
 *
 * Single source of truth for customer-facing WhatsApp / email endpoints + live-chat (Chatwoot).
 * Import from this module instead of hard-coding numbers in UI components:
 *
 *   import { WHATSAPP_URL, openWhatsApp, openLiveChat } from "@/constants/contact";
 */

/** E.164-compatible WhatsApp number (no +, no spaces) — used for wa.me links. */
export const WHATSAPP_PHONE_E164 = "15559878144";

/** Human-readable WhatsApp number for display in UI. */
export const WHATSAPP_PHONE_DISPLAY = "+1 555 987 8144";

/** Support e-mail (kept here so future changes are a single edit). */
export const CONTACT_EMAIL = "support@plannapp.co";

/** WhatsApp deep-link. Append `?text=...` at call-site if prefilled text is needed. */
export const WHATSAPP_URL = `https://wa.me/${WHATSAPP_PHONE_E164}`;

/**
 * Open the WhatsApp chat in a new tab with a pre-filled message.
 * Safe to call on SSR — becomes a no-op if `window` is absent.
 */
export function openWhatsApp(prefilledMessage = "") {
  if (typeof window === "undefined") return;
  const url = prefilledMessage
    ? `${WHATSAPP_URL}?text=${encodeURIComponent(prefilledMessage)}`
    : WHATSAPP_URL;
  window.open(url, "_blank", "noopener,noreferrer");
}

/**
 * Open the Chatwoot live-chat widget. Requires the SDK to be loaded
 * (see `src/lib/chatwoot.js`). Falls back to WhatsApp if the widget is unavailable.
 */
export function openLiveChat() {
  if (typeof window === "undefined") return;
  if (window.$chatwoot && typeof window.$chatwoot.toggle === "function") {
    window.$chatwoot.toggle("open");
    return;
  }
  // Fallback — widget hasn't loaded yet (no token configured or network issue)
  openWhatsApp();
}
