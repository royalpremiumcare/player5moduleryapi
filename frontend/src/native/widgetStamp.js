import { subOf } from './useLiveActivities';

// Per-sub "last widget key issue" stamp, plus a "do not ask before" backoff for devices that cannot
// hold a widget key. Without a sub there is no stable key name, so nothing is stamped and the key
// is always (re)issued. Storage failures are swallowed. Only times are stored, never a key.
const keyFor = (token, prefix = 'widget_key_issued') => {
  const sub = subOf(token);
  return sub ? `${prefix}:${sub}` : null;
};

export function widgetBackoffUntil(token) {
  try {
    const k = keyFor(token, 'widget_key_backoff');
    return k ? Number(localStorage.getItem(k)) || 0 : 0;
  } catch (e) {
    return 0;
  }
}

export function markWidgetBackoff(token, ms) {
  try {
    const k = keyFor(token, 'widget_key_backoff');
    if (k) localStorage.setItem(k, String(Date.now() + ms));
  } catch (e) {
    /* storage unavailable: ask again next time */
  }
}

export function lastWidgetIssue(token) {
  try {
    const k = keyFor(token);
    return k ? Number(localStorage.getItem(k)) || 0 : 0;
  } catch (e) {
    return 0;
  }
}

export function markWidgetIssued(token) {
  try {
    const k = keyFor(token);
    if (k) localStorage.setItem(k, String(Date.now()));
  } catch (e) {
    /* storage unavailable: re-issue next time */
  }
}

export function clearWidgetIssueStamp(token) {
  try {
    const k = keyFor(token);
    if (k) localStorage.removeItem(k);
    const b = keyFor(token, 'widget_key_backoff');
    if (b) localStorage.removeItem(b);
  } catch (e) {
    /* ignore */
  }
}
