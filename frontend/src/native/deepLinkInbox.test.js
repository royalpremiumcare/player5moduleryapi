import { takePending } from '../lib/pendingDeepLink';

jest.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => true } }), { virtual: true });

let mockUrlListener;
let mockLaunchUrl;
const mockGetLaunchUrl = jest.fn();
const mockAddListener = jest.fn();
jest.mock('@capacitor/app', () => ({
  App: {
    addListener: (...a) => mockAddListener(...a),
    getLaunchUrl: (...a) => mockGetLaunchUrl(...a),
  },
}), { virtual: true });

const flush = () => new Promise((r) => setTimeout(r, 0));

describe('deepLinkInbox', () => {
  let start;
  let events;
  const onEvent = (e) => events.push(e.detail);

  beforeEach(() => {
    jest.resetModules();
    window.sessionStorage.clear();
    mockAddListener.mockImplementation((name, cb) => {
      mockUrlListener = cb;
      return Promise.resolve({ remove: jest.fn() });
    });
    mockGetLaunchUrl.mockImplementation(() =>
      Promise.resolve(mockLaunchUrl ? { url: mockLaunchUrl } : undefined)
    );
    mockLaunchUrl = undefined;
    events = [];
    window.addEventListener('plann:deeplink', onEvent);
    start = require('./deepLinkInbox').startDeepLinkInbox;
  });
  afterEach(() => window.removeEventListener('plann:deeplink', onEvent));

  it('registers one listener and calls mockGetLaunchUrl once per runtime', async () => {
    start();
    start();
    await flush();
    expect(mockAddListener).toHaveBeenCalledTimes(1);
    expect(mockGetLaunchUrl).toHaveBeenCalledTimes(1);
  });

  it('stamps pending at tap time and dispatches an event', async () => {
    start();
    await flush();
    mockUrlListener({ url: 'plannapp://appointment/42' });
    expect(events).toEqual([{ kind: 'appointment', id: '42' }]);
    expect(takePending(Date.now())).toEqual({ kind: 'appointment', id: '42' });
  });

  it('does not claim checkout or unknown links', async () => {
    start();
    await flush();
    mockUrlListener({ url: 'plannapp://checkout/success' });
    mockUrlListener({ url: 'https://example.com' });
    expect(events).toEqual([]);
    expect(takePending(Date.now())).toBeNull();
  });

  it('handles the launch url', async () => {
    mockLaunchUrl = 'plannapp://new-appointment?source=widget_small';
    start();
    await flush();
    expect(takePending(Date.now())).toEqual({ kind: 'new-appointment', source: 'widget_small' });
  });

  it('same url via launch and retained appUrlOpen is dispatched once', async () => {
    mockLaunchUrl = 'plannapp://appointment/9';
    start();
    await flush();
    mockUrlListener({ url: 'plannapp://appointment/9' });
    expect(events).toHaveLength(1);
  });

  it('keeps the last unclaimed url and hands it out once', async () => {
    start();
    await flush();
    mockUrlListener({ url: 'plannapp://checkout/success?session_id=abc' });
    expect(events).toEqual([]);
    const { takeUnclaimedUrl } = require('./deepLinkInbox');
    expect(takeUnclaimedUrl()).toBe('plannapp://checkout/success?session_id=abc');
    expect(takeUnclaimedUrl()).toBeNull();
  });

  it('skips a launch url already handled in this session (new runtime after logout)', async () => {
    mockLaunchUrl = 'plannapp://appointment/5';
    start();
    await flush();
    expect(takePending(Date.now())).toEqual({ kind: 'appointment', id: '5' });

    jest.resetModules();
    require('./deepLinkInbox').startDeepLinkInbox();
    await flush();
    expect(mockGetLaunchUrl).toHaveBeenCalledTimes(2);
    expect(takePending(Date.now())).toBeNull();
  });

  it('a different launch url in a later runtime is handled', async () => {
    mockLaunchUrl = 'plannapp://appointment/5';
    start();
    await flush();
    takePending(Date.now());
    jest.resetModules();
    mockLaunchUrl = 'plannapp://appointment/6';
    require('./deepLinkInbox').startDeepLinkInbox();
    await flush();
    expect(takePending(Date.now())).toEqual({ kind: 'appointment', id: '6' });
  });
});
