import { subOf } from './useLiveActivities';

// Per-sub "last widget key issue" stamp. Without a sub there is no stable key name, so nothing
// is stamped and the key is always (re)issued. Storage failures are swallowed.
const keyFor = (token) => {
  const sub = subOf(token);
  return sub ? `widget_key_issued:${sub}` : null;
};

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
  } catch (e) {
    /* ignore */
  }
}
