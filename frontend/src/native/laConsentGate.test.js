import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { decideConsent, wasConsentSeen, markConsentSeen, useLaConsentGate } from './laConsentGate';
import { getStatus } from './liveActivities';

jest.mock('./liveActivities', () => ({ getStatus: jest.fn() }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const jwt = (sub) => `h.${btoa(JSON.stringify({ sub }))}.s`;

const base = {
  seen: false,
  supported: true,
  orgFlag: true,
  wizardOpen: false,
  ahaActive: false,
  tourState: 'finished',
};

describe('decideConsent', () => {
  const cases = [
    ['seen skips', { seen: true }, 'skip'],
    ['unsupported skips', { supported: false }, 'skip'],
    ['flag off skips', { orgFlag: false }, 'skip'],
    ['seen beats wait', { seen: true, wizardOpen: true }, 'skip'],
    ['flag off beats undecided supported', { orgFlag: false, supported: undefined }, 'skip'],
    ['unsupported beats undecided flag', { supported: false, orgFlag: undefined }, 'skip'],
    ['supported unknown is undecided', { supported: undefined }, 'undecided'],
    ['flag unknown is undecided', { orgFlag: undefined }, 'undecided'],
    ['undecided beats wait', { supported: undefined, wizardOpen: true }, 'undecided'],
    ['wizard open waits', { wizardOpen: true }, 'wait'],
    ['aha active waits', { ahaActive: true }, 'wait'],
    ['tour scheduled waits', { tourState: 'scheduled' }, 'wait'],
    ['tour running waits', { tourState: 'running' }, 'wait'],
    ['tour unknown is undecided', { tourState: 'unknown' }, 'undecided'],
    ['wait beats unknown tour', { tourState: 'unknown', wizardOpen: true }, 'wait'],
    ['tour finished shows', { tourState: 'finished' }, 'show'],
    ['tour not-eligible shows', { tourState: 'not-eligible' }, 'show'],
  ];
  test.each(cases)('%s', (_n, over, expected) => {
    expect(decideConsent({ ...base, ...over })).toBe(expected);
  });
});

describe('seen helpers', () => {
  beforeEach(() => localStorage.clear());
  test('use the la_consent_seen:<sub> key', () => {
    expect(wasConsentSeen('u1')).toBe(false);
    markConsentSeen('u1');
    expect(localStorage.getItem('la_consent_seen:u1')).toBe('1');
    expect(wasConsentSeen('u1')).toBe(true);
    expect(wasConsentSeen('u2')).toBe(false);
  });
  test('survive unavailable storage', () => {
    const g = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const s = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(wasConsentSeen('u1')).toBe(false);
    expect(() => markConsentSeen('u1')).not.toThrow();
    g.mockRestore();
    s.mockRestore();
  });
});

describe('useLaConsentGate', () => {
  let container;
  let root;
  let out;

  function Probe(props) {
    out = useLaConsentGate(props);
    return null;
  }
  const render = async (props) => {
    await act(async () => {
      root.render(<Probe {...props} />);
    });
  };
  const defaults = { token: jwt('u1'), orgFlag: true, wizardOpen: false, ahaActive: false, tourState: 'not-eligible' };

  beforeEach(() => {
    jest.useFakeTimers();
    localStorage.clear();
    getStatus.mockReset();
    getStatus.mockResolvedValue({ supported: true, enabled: true });
    container = document.createElement('div');
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    jest.useRealTimers();
  });

  test('holds push while undecided then releases after 30000ms', async () => {
    getStatus.mockReturnValue(new Promise(() => {}));
    await render(defaults);
    expect(out.pushHeld).toBe(true);
    expect(out.autoOpen).toBe(false);
    await act(async () => {
      jest.advanceTimersByTime(29999);
    });
    expect(out.pushHeld).toBe(true);
    await act(async () => {
      jest.advanceTimersByTime(1);
    });
    expect(out.pushHeld).toBe(false);
  });

  test('not-eligible tour shows immediately when flag on and supported', async () => {
    await render(defaults);
    expect(out.autoOpen).toBe(true);
    expect(out.pushHeld).toBe(true);
  });

  test('waits during tour running then shows after finished', async () => {
    await render({ ...defaults, tourState: 'running' });
    expect(out.autoOpen).toBe(false);
    expect(out.pushHeld).toBe(true);
    await render({ ...defaults, tourState: 'finished' });
    expect(out.autoOpen).toBe(true);
  });

  test('close marks seen and releases hold', async () => {
    await render(defaults);
    await act(async () => out.close());
    expect(localStorage.getItem('la_consent_seen:u1')).toBe('1');
    expect(out.autoOpen).toBe(false);
    expect(out.pushHeld).toBe(false);
  });

  test('token change resets autoOpen and hold', async () => {
    await render(defaults);
    await act(async () => out.close());
    await render({ ...defaults, token: jwt('u2') });
    expect(out.autoOpen).toBe(true);
    expect(out.pushHeld).toBe(true);
  });

  test.each([
    ['previous user closed the sheet', true],
    ['previous user had it open', false],
  ])('first render after a token change starts fresh (%s)', async (_n, closeFirst) => {
    const history = [];
    function Recorder(props) {
      history.push(useLaConsentGate(props));
      return null;
    }
    await act(async () => {
      root.render(<Recorder {...defaults} />);
    });
    if (closeFirst) await act(async () => history[history.length - 1].close());
    getStatus.mockReturnValue(new Promise(() => {}));
    const before = history.length;
    await act(async () => {
      root.render(<Recorder {...defaults} token={jwt('u2')} />);
    });
    const first = history[before];
    expect(first.autoOpen).toBe(false);
    expect(first.pushHeld).toBe(true);
    // ...and every later render too, while getStatus for u2 is still pending.
    history.slice(before).forEach((r) => {
      expect(r.autoOpen).toBe(false);
      expect(r.pushHeld).toBe(true);
    });
  });

  test('logout and login as the same user starts a new session', async () => {
    getStatus.mockReturnValue(new Promise(() => {}));
    await render(defaults);
    await act(async () => {
      jest.advanceTimersByTime(30000);
    });
    expect(out.pushHeld).toBe(false);
    await render({ ...defaults, token: null });
    await render(defaults);
    expect(out.pushHeld).toBe(true);
  });

  test('after the 30 s release the hold stays off for the session', async () => {
    let resolveStatus;
    getStatus.mockReturnValue(new Promise((r) => { resolveStatus = r; }));
    await render(defaults);
    await act(async () => {
      jest.advanceTimersByTime(30000);
    });
    expect(out.pushHeld).toBe(false);
    // The decision later becomes 'show', then 'wait': the push prompt has already been allowed to run.
    await act(async () => resolveStatus({ supported: true }));
    expect(out.autoOpen).toBe(true);
    expect(out.pushHeld).toBe(false);
    await render({ ...defaults, tourState: 'running' });
    expect(out.autoOpen).toBe(false);
    expect(out.pushHeld).toBe(false);
  });

  test('the 30 s timer is cleared when the decision leaves undecided', async () => {
    let resolveStatus;
    getStatus.mockReturnValue(new Promise((r) => { resolveStatus = r; }));
    await render(defaults);
    await act(async () => {
      jest.advanceTimersByTime(10000);
    });
    await act(async () => resolveStatus({ supported: true }));
    expect(out.autoOpen).toBe(true);
    // 35 s after the first render, but only 10 s of it undecided: the hold must still be on.
    await act(async () => {
      jest.advanceTimersByTime(25000);
    });
    expect(out.pushHeld).toBe(true);
  });

  test('flag false never holds', async () => {
    await render({ ...defaults, orgFlag: false });
    expect(out.pushHeld).toBe(false);
    expect(out.autoOpen).toBe(false);
  });

  test('unsupported or null status never holds', async () => {
    getStatus.mockResolvedValue(null);
    await render(defaults);
    expect(out.pushHeld).toBe(false);
    expect(out.autoOpen).toBe(false);
  });
});
