import { useEffect, useRef, useState } from 'react';
import {
  isLiveActivitySupported,
  register,
  reconcile,
  unregister,
  getStatus,
} from './liveActivities';

// JWT payload segments are base64url (RFC 7515): map to base64 and pad before atob, then
// decode the bytes as UTF-8 so a non-ASCII sub survives (binary string where TextDecoder is
// missing: still exact for ASCII).
export function subOf(token) {
  try {
    const seg = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(seg.padEnd(seg.length + ((4 - (seg.length % 4)) % 4), '='));
    const json =
      typeof TextDecoder === 'function'
        ? new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)))
        : bin;
    return JSON.parse(json).sub || null;
  } catch (e) {
    return null;
  }
}

function apiBaseUrl() {
  const configured = process.env.REACT_APP_BACKEND_URL;
  if (configured) {
    try {
      return new URL(configured).origin;
    } catch (e) {
      /* fall through */
    }
  }
  return window.location.origin;
}

/**
 * Registers this device for iOS Live Activities once per login, reconciles
 * when the app becomes visible, and unregisters on logout. No-op everywhere
 * the native plugin is unavailable.
 */
export function useLiveActivities({ token, orgFlagEnabled }) {
  const [status, setStatus] = useState(null);
  // { key, token, needsFcm } of the session currently registered natively. needsFcm: the last
  // register sent no FCM token (fresh install before push setup), so register again on resume.
  const sessionRef = useRef(null);

  useEffect(() => {
    const session = sessionRef.current;
    const key = token ? subOf(token) || token : null;

    if (session && (!token || session.key !== key)) {
      unregister({ jwt: session.token });
      sessionRef.current = null;
      if (!token) setStatus(null);
    }
    if (!token || !orgFlagEnabled || !isLiveActivitySupported()) return undefined;

    if (sessionRef.current) {
      sessionRef.current.token = token; // keep the latest JWT for unregister
    } else {
      const current = { key, token, needsFcm: false };
      sessionRef.current = current;
      (async () => {
        const result = await register({ apiBaseUrl: apiBaseUrl(), jwt: token, fcmToken: undefined });
        if (sessionRef.current !== current) return;
        if (result === null) {
          sessionRef.current = null; // transient failure: retry on next dep change
          return;
        }
        if (result.supported === false) return; // unsupported iOS: not registered, no retry
        current.needsFcm = result.hasFcmToken === false;
        await reconcile();
        const s = await getStatus();
        if (sessionRef.current === current) setStatus(s);
      })();
    }

    const onVisible = async () => {
      const session = sessionRef.current;
      if (document.visibilityState !== 'visible' || !session) return;
      if (session.needsFcm) {
        // The server upsert is idempotent (no new secret); stop once an FCM token went out.
        session.needsFcm = false;
        const result = await register({ apiBaseUrl: apiBaseUrl(), jwt: session.token, fcmToken: undefined });
        if (sessionRef.current !== session) return;
        session.needsFcm = result === null || result.hasFcmToken === false;
      }
      reconcile();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [token, orgFlagEnabled]);

  return { status };
}
