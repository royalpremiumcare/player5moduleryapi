import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { tourStateFor, useTourStateReporter } from './dashboardTourState';

global.IS_REACT_ACT_ENVIRONMENT = true;

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

describe('useTourStateReporter', () => {
  let container;
  let root;
  let report;
  let onChange;

  function Probe({ cb }) {
    report = useTourStateReporter(cb);
    return null;
  }

  beforeEach(() => {
    onChange = jest.fn();
    container = document.createElement('div');
    root = createRoot(container);
    act(() => root.render(<Probe cb={onChange} />));
  });
  afterEach(() => {
    act(() => root.unmount());
  });

  test('reports each change once', () => {
    report('scheduled');
    report('scheduled');
    report('running');
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['scheduled', 'running']);
  });

  test('unmount reports unknown so the App never waits on a tour that is gone', () => {
    report('running');
    act(() => root.unmount());
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['running', 'unknown']);
    root = createRoot(container);
  });

  test('a late report after unmount (stale tour timer) is dropped', () => {
    report('scheduled');
    act(() => root.unmount());
    report('running');
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['scheduled', 'unknown']);
    root = createRoot(container);
  });

  test('uses the latest callback', () => {
    const next = jest.fn();
    act(() => root.render(<Probe cb={next} />));
    report('finished');
    expect(onChange).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledWith('finished');
  });
});
