import { useCallback, useEffect, useRef } from 'react';

/**
 * Holds the push setup behind the Live Activity consent sheet.
 *
 * Returns `deferIfHeld()`: the push setup calls it before asking iOS for permission. While
 * `held`, it records one pending run and returns true (the caller stops). When `held` turns
 * false and a run is pending, this hook is the single place that runs it again: it clears
 * the pending flag first, then calls `run()` once. `active` false (logged out) drops any
 * pending run.
 */
export function usePushHold({ held, active, run }) {
  const heldRef = useRef(held);
  const pendingRef = useRef(false);
  const runRef = useRef(run);

  useEffect(() => {
    runRef.current = run;
  }, [run]);

  useEffect(() => {
    heldRef.current = held;
    if (!active) {
      pendingRef.current = false;
      return;
    }
    if (!held && pendingRef.current) {
      pendingRef.current = false;
      runRef.current();
    }
  }, [held, active]);

  return useCallback(() => {
    if (!heldRef.current) return false;
    pendingRef.current = true;
    return true;
  }, []);
}
