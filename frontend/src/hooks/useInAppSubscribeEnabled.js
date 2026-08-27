import { useEffect, useState } from 'react';
import { resolveInAppSubscribeEnabled } from '../lib/inAppSubscribe';

/** SHOW_IN_APP_SUBSCRIBE (bkz. constants/uiFlags.js — Apple review için kapalı). */
export default function useInAppSubscribeEnabled() {
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    resolveInAppSubscribeEnabled()
      .then((value) => {
        if (!cancelled) {
          setEnabled(!!value);
          setReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEnabled(false);
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { enabled, ready };
}
