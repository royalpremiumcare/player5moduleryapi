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

const freshState = (sub) => ({ sub, supported: undefined, closed: false, timedOut: false });

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
  // State is tagged with the sub it belongs to: after an account switch the previous
  // user's `supported`/`closed`/`timedOut` are ignored from the very first render.
  const [state, setState] = useState(() => freshState(sub));
  const current = state.sub === sub ? state : freshState(sub);
  const { supported, closed, timedOut } = current;

  const patch = useCallback(
    (changes) => setState((s) => ({ ...(s.sub === sub ? s : freshState(sub)), ...changes })),
    [sub]
  );

  // A different user (or a logout) starts from scratch.
  useEffect(() => {
    setState((s) => (s.sub === sub ? s : freshState(sub)));
    if (!sub) return undefined;
    let cancelled = false;
    (async () => {
      const s = await getStatus();
      if (!cancelled) patch({ supported: s?.supported === true });
    })();
    return () => {
      cancelled = true;
    };
  }, [sub, patch]);

  const decision = sub
    ? decideConsent({ seen: closed || wasConsentSeen(sub), supported, orgFlag, wizardOpen, ahaActive, tourState })
    : 'skip';

  // Leaving 'undecided' clears the timer. Once it has fired, `timedOut` stays true for this
  // user's session: the push prompt has been allowed to run, so a later 'wait' or 'show'
  // never holds it again (the sheet may still auto-open afterwards).
  useEffect(() => {
    if (decision !== 'undecided') return undefined;
    const id = setTimeout(() => patch({ timedOut: true }), UNDECIDED_RELEASE_MS);
    return () => clearTimeout(id);
  }, [decision, patch]);

  const close = useCallback(() => {
    if (sub) markConsentSeen(sub);
    patch({ closed: true });
  }, [sub, patch]);

  return {
    autoOpen: decision === 'show',
    pushHeld: !closed && !timedOut && decision !== 'skip',
    close,
  };
}
