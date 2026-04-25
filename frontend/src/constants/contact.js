/**
 * Plann — Contact Constants
 *
 * Single source of truth for customer-facing phone / WhatsApp / email endpoints.
 * Import from this module instead of hard-coding numbers in UI components:
 *
 *   import { CONTACT_PHONE_DISPLAY, WHATSAPP_URL, TEL_URL } from "@/constants/contact";
 */

/** E.164-compatible phone number (no +, no spaces) — used for wa.me + tel: links. */
export const CONTACT_PHONE_E164 = "905435113250";

/** Human-readable phone number for display in UI. */
export const CONTACT_PHONE_DISPLAY = "+90 543 511 3250";

/** Support e-mail (kept here so future changes are a single edit). */
export const CONTACT_EMAIL = "support@plannapp.co";

/** WhatsApp deep-link. Append `?text=...` at call-site if prefilled text is needed. */
export const WHATSAPP_URL = `https://wa.me/${CONTACT_PHONE_E164}`;

/** `tel:` deep-link (with leading +) — opens native dialer. */
export const TEL_URL = `tel:+${CONTACT_PHONE_E164}`;

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
