import { tourStateFor } from './dashboardTourState';

const base = {
  userRole: 'admin',
  userLoaded: true,
  activationState: 'aha_completed',
  ahaOverlayActive: false,
  storageKeySet: false,
  forceStartTour: false,
};
const state = (over) => tourStateFor({ ...base, ...over });

describe('tourStateFor', () => {
  test('staff is not eligible', () => {
    expect(state({ userRole: 'staff' })).toBe('not-eligible');
  });
  test('staff is not eligible even before the user has loaded', () => {
    expect(state({ userRole: 'staff', userLoaded: false })).toBe('not-eligible');
  });
  test('admin with terminal aha state and key set is not eligible', () => {
    expect(state({ storageKeySet: true })).toBe('not-eligible');
  });
  test('admin with terminal aha state and no key is scheduled', () => {
    expect(state({})).toBe('scheduled');
  });
  test('forceStartTour schedules even when the key is set', () => {
    expect(state({ storageKeySet: true, forceStartTour: true })).toBe('scheduled');
  });
  test.each(['aha_completed', 'aha_skipped', 'skip_aha_no_phone', 'not_applicable'])(
    '%s counts as terminal',
    (activationState) => {
      expect(state({ activationState })).toBe('scheduled');
    },
  );
  test('admin whose user has not loaded is unknown', () => {
    expect(state({ userLoaded: false, activationState: undefined })).toBe('unknown');
  });
  test('aha overlay active is unknown', () => {
    expect(state({ ahaOverlayActive: true })).toBe('unknown');
  });
  test('admin loaded with missing activationState is not eligible', () => {
    expect(state({ activationState: undefined })).toBe('not-eligible');
  });
  test('admin loaded with pending_aha_appointment and no overlay is not eligible', () => {
    expect(state({ activationState: 'pending_aha_appointment' })).toBe('not-eligible');
  });
});
