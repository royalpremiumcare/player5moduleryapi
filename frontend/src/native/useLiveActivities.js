import { useEffect, useRef, useState } from 'react';
import {
  isLiveActivitySupported,
  register,
  reconcile,
  unregister,
  getStatus,
} from './liveActivities';

function subOf(token) {
  try {
    return JSON.parse(atob(token.split('.')[1])).sub || null;
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
  // { key, token } of the session currently registered natively.
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
      const current = { key, token };
      sessionRef.current = current;
      (async () => {
        const result = await register({ apiBaseUrl: apiBaseUrl(), jwt: token, fcmToken: undefined });
        if (sessionRef.current !== current) return;
        if (result === null) {
          sessionRef.current = null; // transient failure: retry on next dep change
          return;
        }
        if (result.supported === false) return; // unsupported iOS: not registered, no retry
        await reconcile();
        const s = await getStatus();
        if (sessionRef.current === current) setStatus(s);
      })();
    }

    const onVisible = () => {
      if (document.visibilityState === 'visible' && sessionRef.current) reconcile();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [token, orgFlagEnabled]);

  return { status };
}
