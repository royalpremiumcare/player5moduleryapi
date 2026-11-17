import { useEffect } from 'react';
import api from '../api/api';
import { apiBaseUrl } from './useLiveActivities';
import { lastWidgetIssue, markWidgetIssued } from './widgetStamp';
import { isWidgetSupported, setWidgetCredential } from './widgets';

const REISSUE_MS = 24 * 60 * 60 * 1000;

/**
 * Issues a read-only widget key after login and hands it to native code (shared Keychain), and
 * re-issues on resume when the last issue is over 24 h old. No-op without a token or off iOS.
 */
export function useWidgetCredential({ token }) {
  useEffect(() => {
    if (!token || !isWidgetSupported()) return undefined;
    let cancelled = false;
    let inFlight = false;

    const issue = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const { data } = await api.post('/widget/key');
        if (cancelled || !data?.key) return;
        const result = await setWidgetCredential({ key: data.key, baseUrl: apiBaseUrl() });
        if (result !== null) markWidgetIssued(token); // null: native could not store it, retry on resume
      } catch (e) {
        /* offline or server error: retried on the next resume */
      } finally {
        inFlight = false;
      }
    };

    // Cold starts restore the token too: only issue when the stamp is stale. Logout clears the
    // stamp (it revokes the key), so the next login always issues.
    if (Date.now() - lastWidgetIssue(token) >= REISSUE_MS) issue();

    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastWidgetIssue(token) >= REISSUE_MS) issue();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [token]);
}
