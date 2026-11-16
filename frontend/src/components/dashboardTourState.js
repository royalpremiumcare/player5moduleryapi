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
