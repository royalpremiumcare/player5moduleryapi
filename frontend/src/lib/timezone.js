/**
 * PLANN v2 — Timezone Helper
 *
 * Backend always returns UTC ISO-8601. This converts to the user's
 * preferred timezone (org currency default or browser fallback).
 *
 * Priority:
 *   1. user.preferred_timezone (if set in profile)
 *   2. Org base_currency → TRY="Europe/Istanbul", GBP="Europe/London"
 *   3. Browser Intl.DateTimeFormat timezone
 */

const CURRENCY_DEFAULT_TZ = {
  TRY: "Europe/Istanbul",
  GBP: "Europe/London",
};

export function getUserTz(user = null, baseCurrency = null) {
  try {
    if (user?.preferred_timezone) return user.preferred_timezone;
    if (baseCurrency && CURRENCY_DEFAULT_TZ[baseCurrency]) {
      return CURRENCY_DEFAULT_TZ[baseCurrency];
    }
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Format a UTC ISO timestamp to a local display string.
 * Options: dateOnly, timeOnly, short, long
 */
export function formatLocal(utcIso, tz = null, opts = {}) {
  if (!utcIso) return "";
  const zone = tz || getUserTz();
  try {
    const d = new Date(utcIso);
    if (isNaN(d.getTime())) return utcIso;
    const style = opts.style || "short";
    const options = { timeZone: zone };
    if (opts.dateOnly) {
      Object.assign(options, { year: "numeric", month: "2-digit", day: "2-digit" });
    } else if (opts.timeOnly) {
      Object.assign(options, { hour: "2-digit", minute: "2-digit" });
    } else if (style === "long") {
      Object.assign(options, {
        year: "numeric", month: "long", day: "numeric",
        hour: "2-digit", minute: "2-digit", timeZoneName: "short",
      });
    } else {
      Object.assign(options, {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    }
    return d.toLocaleString(opts.locale || undefined, options);
  } catch {
    return utcIso;
  }
}

/**
 * Combined "UTC / local" display for audit logs.
 */
export function formatWithTz(utcIso, tz = null) {
  if (!utcIso) return "";
  const zone = tz || getUserTz();
  const short = tz === "Europe/Istanbul" ? "İstanbul" : tz === "Europe/London" ? "London" : zone;
  return `${utcIso.slice(0, 19).replace("T", " ")}Z / ${formatLocal(utcIso, zone)} (${short})`;
}

/**
 * Next Wednesday date (for batch payout display).
 */
export function nextWednesdayLocal(tz = null) {
  const zone = tz || getUserTz();
  const now = new Date();
  const daysAhead = (3 - now.getUTCDay() + 7) % 7 || 7; // 3 = Wed (UTC)
  const nextWed = new Date(now.getTime() + daysAhead * 86400 * 1000);
  return formatLocal(nextWed.toISOString(), zone, { dateOnly: true });
}
