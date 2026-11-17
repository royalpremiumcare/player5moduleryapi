import { useEffect } from 'react';
import api from '../api/api';
import { apiBaseUrl } from './useLiveActivities';
import { lastWidgetIssue, markWidgetBackoff, markWidgetIssued, widgetBackoffUntil } from './widgetStamp';
import { isWidgetSupported, setWidgetCredential, widgetCredentialPresent } from './widgets';

const REISSUE_MS = 24 * 60 * 60 * 1000;
// A device that cannot hold a widget key (iOS < 16.2, a Keychain error, an old native build without
// the widget methods) is asked again only after this, so foregrounds do not keep minting keys.
const BACKOFF_MS = 6 * 60 * 60 * 1000;

/**
 * Revokes a widget key on the server. Fire-and-forget: never throws, never waits. With `key`
 * only that key goes; without it every widget key of the user goes (only for when the device's
 * key is unknown). `token` sets the Authorization header explicitly (logout clears it right after).
 */
export function revokeWidgetKey({ key, token } = {}) {
  try {
    const config = {};
    if (key) config.data = { key };
    if (token) config.headers = { Authorization: `Bearer ${token}` };
    Promise.resolve(api.delete('/widget/key', config)).catch(() => {});
  } catch (e) {
    /* never block the caller */
  }
}

/**
 * Issues a read-only widget key after login and hands it to native code (shared Keychain). On
 * mount and on every return to the foreground it re-issues when the last issue is over 24 h old
 * or when the widget has lost its credential. The key it replaces is revoked, so every device
 * keeps exactly one live key. No-op without a token or off iOS. The key itself never touches web
 * storage: native code keeps it and reports it back when it is replaced or cleared.
 */
export function useWidgetCredential({ token }) {
  useEffect(() => {
    if (!token || !isWidgetSupported()) return undefined;
    let cancelled = false;
    let inFlight = false;

    const issue = async () => {
      const { data } = await api.post('/widget/key');
      if (cancelled || !data?.key) return;
      const result = await setWidgetCredential({ key: data.key, baseUrl: apiBaseUrl() });
      if (!result || result.supported === false) {
        // Native could not store it: the key is useless, and asking again right away would fail too.
        markWidgetBackoff(token, BACKOFF_MS);
        revokeWidgetKey({ key: data.key });
        return;
      }
      markWidgetIssued(token);
      if (result.previousKey && result.previousKey !== data.key) revokeWidgetKey({ key: result.previousKey });
    };

    // Cold starts restore the token too: issue only when due. Logout clears the stamps (it revokes
    // the key), so the next login always issues.
    const check = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        if (Date.now() < widgetBackoffUntil(token)) return;
        const stale = Date.now() - lastWidgetIssue(token) >= REISSUE_MS;
        const presence = await widgetCredentialPresent(); // null on an old native build
        if (cancelled) return;
        if (presence?.supported === false) {
          markWidgetBackoff(token, BACKOFF_MS); // iOS < 16.2: no widgets to feed
          return;
        }
        if (stale || presence?.present === false) await issue();
      } catch (e) {
        /* offline or server error: retried on the next resume */
      } finally {
        inFlight = false;
      }
    };

    check();
    const onVisible = () => {
      if (document.visibilityState === 'visible') check();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [token]);
}
