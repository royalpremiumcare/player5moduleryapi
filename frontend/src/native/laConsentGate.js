import { useCallback, useEffect, useState } from 'react';
import { getStatus } from './liveActivities';
import { subOf } from './useLiveActivities';

const UNDECIDED_RELEASE_MS = 30000;

const seenKey = (sub) => `la_consent_seen:${sub}`;

export function wasConsentSeen(sub) {
  try {
    return localStorage.getItem(seenKey(sub)) === '1';
  } catch (e) {
    return false;
  }
}

export function markConsentSeen(sub) {
  try {
    localStorage.setItem(seenKey(sub), '1');
  } catch (e) {
    /* storage unavailable: the sheet may show again next launch */
  }
}

/** -> 'skip' | 'undecided' | 'wait' | 'show' */
export function decideConsent({ seen, supported, orgFlag, wizardOpen, ahaActive, tourState }) {
  if (seen || supported === false || orgFlag === false) return 'skip';
  if (supported === undefined || orgFlag === undefined) return 'undecided';
  if (wizardOpen || ahaActive || tourState === 'scheduled' || tourState === 'running') return 'wait';
  if (tourState === 'unknown') return 'undecided';
  return 'show';
}

/**
 * Decides when the Live Activity consent sheet auto-opens and whether the iOS push
 * permission prompt is held behind it.
 */
export function useLaConsentGate({ token, orgFlag, wizardOpen, ahaActive, tourState }) {
  const sub = token ? subOf(token) : null;
  const [supported, setSupported] = useState(undefined);
  const [closed, setClosed] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  // A different user starts from scratch.
  useEffect(() => {
    setSupported(undefined);
    setClosed(false);
    setTimedOut(false);
    if (!sub) return undefined;
    let cancelled = false;
    (async () => {
      const s = await getStatus();
      if (!cancelled) setSupported(s?.supported === true);
    })();
    return () => {
      cancelled = true;
    };
  }, [sub]);

  const decision = sub
    ? decideConsent({ seen: closed || wasConsentSeen(sub), supported, orgFlag, wizardOpen, ahaActive, tourState })
    : 'skip';

  useEffect(() => {
    if (decision !== 'undecided') return undefined;
    const id = setTimeout(() => setTimedOut(true), UNDECIDED_RELEASE_MS);
    return () => clearTimeout(id);
  }, [decision]);

  const close = useCallback(() => {
    if (sub) markConsentSeen(sub);
    setClosed(true);
  }, [sub]);

  return {
    autoOpen: decision === 'show',
    pushHeld: !closed && !timedOut && decision !== 'skip',
    close,
  };
}
