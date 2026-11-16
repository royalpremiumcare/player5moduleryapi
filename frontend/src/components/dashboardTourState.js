import { useCallback, useEffect, useRef } from 'react';

// Pure classification of what Dashboard's tour-scheduling effect is about to do.
// Dashboard reports this to App so the Live Activity consent sheet opens only
// after the tour, never on top of it.

const TERMINAL_AHA_STATES = ['aha_completed', 'aha_skipped', 'skip_aha_no_phone', 'not_applicable'];

export function tourStateFor({
  userRole,
  userLoaded,
  activationState,
  ahaOverlayActive,
  storageKeySet,
  forceStartTour,
}) {
  if (userRole !== 'admin') return 'not-eligible';
  if (!userLoaded) return 'unknown';
  if (ahaOverlayActive) return 'unknown';
  if (TERMINAL_AHA_STATES.includes(activationState)) {
    return forceStartTour || !storageKeySet ? 'scheduled' : 'not-eligible';
  }
  // Any other or missing activation state: the effect never runs the tour.
  return 'not-eligible';
}

/**
 * Returns a stable `report(state)` that forwards tour-state changes to `onTourStateChange`
 * (each value once). On unmount it reports 'unknown' and drops later reports: Dashboard's
 * tour timers are not cleared on unmount, so a late 'running' must not reach the App and
 * hold the push prompt behind a tour that is gone.
 */
export function useTourStateReporter(onTourStateChange) {
  const lastRef = useRef(null);
  const callbackRef = useRef(onTourStateChange);
  const mountedRef = useRef(false);

  useEffect(() => {
    callbackRef.current = onTourStateChange;
  }, [onTourStateChange]);

  const report = useCallback((state) => {
    if (!mountedRef.current || lastRef.current === state) return;
    lastRef.current = state;
    if (callbackRef.current) callbackRef.current(state);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      report('unknown');
      mountedRef.current = false;
    };
  }, [report]);

  return report;
}
