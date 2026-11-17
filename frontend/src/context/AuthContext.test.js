import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthProvider, useAuth } from './AuthContext';
import api from '../api/api';
import * as la from '../native/liveActivities';
import * as widgets from '../native/widgets';

// axios ships ESM that CRA's jest does not transform; AuthContext only uses it in login().
jest.mock('axios', () => ({ __esModule: true, default: { post: jest.fn() } }));
jest.mock('../api/api', () => ({ __esModule: true, default: { delete: jest.fn(), post: jest.fn() } }));
jest.mock('../lib/posthog', () => ({
  __esModule: true,
  default: { identifyUser: jest.fn(), reset: jest.fn(), track: jest.fn(), aliasAnonymous: jest.fn() },
}));
jest.mock('../i18n', () => ({ __esModule: true, default: { t: (k) => k } }));
jest.mock('../native/liveActivities', () => ({ unregister: jest.fn() }));
jest.mock('../native/widgets', () => ({ clearWidgetCredential: jest.fn(), isWidgetSupported: jest.fn() }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const TOKEN = `h.${btoa(JSON.stringify({ sub: 'ali', role: 'admin' }))}.s`;

let container;
let root;
let auth;
let events;
let originalLocation;

function Probe() {
  auth = useAuth();
  return null;
}

beforeEach(async () => {
  jest.clearAllMocks();
  events = [];
  localStorage.clear();
  sessionStorage.clear();
  window.matchMedia = jest.fn(() => ({ matches: false }));
  originalLocation = window.location;
  delete window.location;
  window.location = {
    set href(v) { events.push(['navigate', v]); },
    get href() { return 'http://localhost/'; },
  };
  la.unregister.mockImplementation((opts) => {
    events.push(['la-unregister', opts, localStorage.getItem('authToken')]);
    return new Promise(() => {}); // native call never answers before the reload
  });
  // The push unsubscribe is a network round trip: it settles after the native bridge answers.
  api.delete.mockImplementation(async (url) => {
    if (url === '/push/unsubscribe') {
      await new Promise((r) => setTimeout(r, 0));
      events.push(['push-unsubscribe']);
    }
  });
  widgets.isWidgetSupported.mockReturnValue(true);
  widgets.clearWidgetCredential.mockResolvedValue({ key: 'wk-device' });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  window.location = originalLocation;
});

async function renderWithStoredToken(token) {
  if (token) localStorage.setItem('authToken', token);
  await act(async () => {
    root.render(<AuthProvider><Probe /></AuthProvider>);
  });
}

test('logout unregisters Live Activities with the current JWT before clearing it and navigating', async () => {
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });

  expect(la.unregister).toHaveBeenCalledTimes(1);
  expect(la.unregister).toHaveBeenCalledWith({ jwt: TOKEN });
  const names = events.map((e) => e[0]);
  expect(names).toEqual(['la-unregister', 'push-unsubscribe', 'navigate']);
  expect(events[0][2]).toBe(TOKEN); // token still stored when unregister was sent
  expect(localStorage.getItem('authToken')).toBeNull();
});

test('logout does not wait for the native unregister', async () => {
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); }); // unregister never resolves
  expect(events[events.length - 1]).toEqual(['navigate', '/login']);
});

test('logout without a stored token skips the Live Activity unregister', async () => {
  await renderWithStoredToken(null);
  await act(async () => { await auth.logout(); });
  expect(la.unregister).not.toHaveBeenCalled();
  expect(events.map((e) => e[0])).toEqual(['navigate']);
});

test('logout clears a pending widget deep link so the next user does not inherit it', async () => {
  const { savePending, takePending } = require('../lib/pendingDeepLink');
  await renderWithStoredToken(TOKEN);
  savePending({ kind: 'appointment', id: '9' });
  await act(async () => { await auth.logout(); });
  expect(takePending(Date.now())).toBeNull();
});

const widgetDeletes = () => api.delete.mock.calls.filter(([url]) => url === '/widget/key');

test('logout revokes only this device key (from native) before navigation', async () => {
  api.delete.mockImplementation(async (url, config) => {
    if (url === '/widget/key') {
      events.push(['widget-delete', localStorage.getItem('authToken'), config]);
      return;
    }
    await new Promise((r) => setTimeout(r, 0));
    events.push(['push-unsubscribe']);
  });
  widgets.clearWidgetCredential.mockImplementation(() => {
    events.push(['widget-clear']);
    return Promise.resolve({ key: 'wk-device' });
  });
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });

  expect(widgetDeletes()).toEqual([['/widget/key', {
    data: { key: 'wk-device' },
    headers: { Authorization: `Bearer ${TOKEN}` },
  }]]);
  const names = events.map((e) => e[0]);
  expect(names.indexOf('widget-clear')).toBeLessThan(names.indexOf('widget-delete'));
  expect(names.indexOf('widget-delete')).toBeLessThan(names.indexOf('navigate'));
  expect(events.find((e) => e[0] === 'widget-delete')[1]).toBe(TOKEN);
});

test('logout does not wait for the native clear', async () => {
  widgets.clearWidgetCredential.mockReturnValue(new Promise(() => {}));
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(events[events.length - 1]).toEqual(['navigate', '/login']);
  expect(widgetDeletes()).toEqual([]);
});

test('logout revokes all keys only when native cannot tell the key (old native build)', async () => {
  widgets.clearWidgetCredential.mockResolvedValue(null);
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(widgetDeletes()).toEqual([['/widget/key', { headers: { Authorization: `Bearer ${TOKEN}` } }]]);
});

test('logout sends no revoke when this device holds no widget key', async () => {
  widgets.clearWidgetCredential.mockResolvedValue({});
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(widgetDeletes()).toEqual([]);
});

test('logout on web or Android leaves the iPhone widget keys alone', async () => {
  widgets.isWidgetSupported.mockReturnValue(false);
  widgets.clearWidgetCredential.mockResolvedValue(null);
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(widgetDeletes()).toEqual([]);
});

test('logout never throws when the delete fails', async () => {
  api.delete.mockImplementation(async (url) => {
    if (url === '/widget/key') throw new Error('network');
  });
  widgets.clearWidgetCredential.mockImplementation(() => { throw new Error('native'); });
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(events[events.length - 1]).toEqual(['navigate', '/login']);
  expect(localStorage.getItem('authToken')).toBeNull();
});

test('logout clears the widget issue stamp and backoff so the next login issues a fresh key', async () => {
  localStorage.setItem('widget_key_issued:ali', String(Date.now()));
  localStorage.setItem('widget_key_backoff:ali', String(Date.now() + 1000));
  await renderWithStoredToken(TOKEN);
  await act(async () => { await auth.logout(); });
  expect(localStorage.getItem('widget_key_issued:ali')).toBeNull();
  expect(localStorage.getItem('widget_key_backoff:ali')).toBeNull();
});
