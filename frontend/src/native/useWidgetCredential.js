import { useEffect } from 'react';
import api from '../api/api';
import { apiBaseUrl, subOf } from './useLiveActivities';
import { isWidgetSupported, setWidgetCredential } from './widgets';

const REISSUE_MS = 24 * 60 * 60 * 1000;
const issuedKey = (sub) => `widget_key_issued:${sub}`;

function lastIssued(sub) {
  try {
    return Number(localStorage.getItem(issuedKey(sub))) || 0;
  } catch (e) {
    return 0;
  }
}

function markIssued(sub) {
  try {
    localStorage.setItem(issuedKey(sub), String(Date.now()));
  } catch (e) {
    /* storage unavailable: re-issue next time */
  }
}

/**
 * Issues a read-only widget key after login and hands it to native code (shared Keychain), and
 * re-issues on resume when the last issue is over 24 h old. No-op without a token or off iOS.
 */
export function useWidgetCredential({ token }) {
  useEffect(() => {
    if (!token || !isWidgetSupported()) return undefined;
    const sub = subOf(token) || token;
    let cancelled = false;
    let inFlight = false;

    const issue = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const { data } = await api.post('/widget/key');
        if (cancelled || !data?.key) return;
        const result = await setWidgetCredential({ key: data.key, baseUrl: apiBaseUrl() });
        if (result !== null) markIssued(sub); // null: native could not store it, retry on resume
      } catch (e) {
        /* offline or server error: retried on the next resume */
      } finally {
        inFlight = false;
      }
    };

    // A new token (login) always issues: logout revoked the previous key.
    issue();

    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastIssued(sub) >= REISSUE_MS) issue();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [token]);
}
