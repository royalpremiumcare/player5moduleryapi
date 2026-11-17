import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { useWidgetCredential } from './useWidgetCredential';
import api from '../api/api';
import * as widgets from './widgets';
import { clearWidgetIssueStamp } from './widgetStamp';
import { Capacitor } from '@capacitor/core';

jest.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: jest.fn(), getPlatform: jest.fn(), isPluginAvailable: jest.fn() },
  registerPlugin: jest.fn(() => ({})),
}));
jest.mock('../api/api', () => ({ __esModule: true, default: { post: jest.fn(), delete: jest.fn() } }));
jest.mock('./widgets', () => ({
  isWidgetSupported: jest.fn(),
  setWidgetCredential: jest.fn(),
  clearWidgetCredential: jest.fn(),
  reloadWidgets: jest.fn(),
  widgetCredentialPresent: jest.fn(),
}));

global.IS_REACT_ACT_ENVIRONMENT = true;

const jwt = (sub) => `h.${btoa(JSON.stringify({ sub }))}.s`;
const DAY = 24 * 60 * 60 * 1000;

let container;
let root;

function Probe(props) {
  useWidgetCredential(props);
  return null;
}

async function render(props) {
  await act(async () => {
    root.render(<Probe {...props} />);
  });
}

async function becomeVisible() {
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  widgets.isWidgetSupported.mockReturnValue(true);
  widgets.setWidgetCredential.mockResolvedValue({});
  widgets.widgetCredentialPresent.mockResolvedValue({ present: true });
  api.delete.mockResolvedValue({});
  api.post.mockResolvedValue({ data: { key: 'wk1', expires_at: '2027-01-01T00:00:00Z' } });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  jest.restoreAllMocks();
  await act(async () => root.unmount());
  container.remove();
});

test('issues key and stores credential on login', async () => {
  await render({ token: jwt('ali') });
  expect(api.post).toHaveBeenCalledWith('/widget/key');
  expect(widgets.setWidgetCredential).toHaveBeenCalledWith({
    key: 'wk1',
    baseUrl: window.location.origin,
  });
  expect(localStorage.getItem('widget_key_issued:ali')).not.toBeNull();
});

test('does not issue while token is null', async () => {
  await render({ token: null });
  expect(api.post).not.toHaveBeenCalled();
});

test('does not re-issue within 24h', async () => {
  await render({ token: jwt('ali') });
  await becomeVisible();
  expect(api.post).toHaveBeenCalledTimes(1);
});

test('re-issues on visible after 24h', async () => {
  const now = Date.now();
  const spy = jest.spyOn(Date, 'now').mockReturnValue(now);
  await render({ token: jwt('ali') });
  spy.mockReturnValue(now + DAY + 1000);
  await becomeVisible();
  expect(api.post).toHaveBeenCalledTimes(2);
  expect(widgets.setWidgetCredential).toHaveBeenCalledTimes(2);
});

test('does not post on mount when a recent issue stamp exists (cold start)', async () => {
  localStorage.setItem('widget_key_issued:ali', String(Date.now() - 1000));
  await render({ token: jwt('ali') });
  expect(api.post).not.toHaveBeenCalled();
});

test('posts on mount when the stamp is older than 24h', async () => {
  localStorage.setItem('widget_key_issued:ali', String(Date.now() - DAY - 1000));
  await render({ token: jwt('ali') });
  expect(api.post).toHaveBeenCalledTimes(1);
});

test('after the stamp is cleared (logout) the next mount posts', async () => {
  await render({ token: jwt('ali') });
  expect(api.post).toHaveBeenCalledTimes(1);
  await render({ token: null });
  clearWidgetIssueStamp(jwt('ali'));
  await render({ token: jwt('ali') });
  expect(api.post).toHaveBeenCalledTimes(2);
});

test('a token without sub never puts the JWT into a storage key', async () => {
  const noSub = `h.${btoa(JSON.stringify({}))}.s`;
  await render({ token: noSub });
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(Object.keys(localStorage).some((k) => k.includes(noSub))).toBe(false);
});

test('no-op on web/android', async () => {
  widgets.isWidgetSupported.mockReturnValue(false);
  await render({ token: jwt('ali') });
  await becomeVisible();
  expect(api.post).not.toHaveBeenCalled();
  expect(widgets.setWidgetCredential).not.toHaveBeenCalled();
});

test('a failed issue does not throw and does not stamp the issue time', async () => {
  api.post.mockRejectedValue(new Error('offline'));
  await render({ token: jwt('ali') });
  expect(widgets.setWidgetCredential).not.toHaveBeenCalled();
  expect(localStorage.getItem('widget_key_issued:ali')).toBeNull();
});

const HOUR = 60 * 60 * 1000;
const keyDeletes = () => api.delete.mock.calls.filter(([url]) => url === '/widget/key');

describe('per-device key lifecycle (final review Important 1)', () => {
  test('a re-issue revokes exactly the key it replaced', async () => {
    widgets.setWidgetCredential.mockResolvedValue({ previousKey: 'wk-old' });
    await render({ token: jwt('ali') });
    expect(keyDeletes()).toEqual([['/widget/key', { data: { key: 'wk-old' } }]]);
  });

  test('a first issue (nothing replaced) revokes nothing', async () => {
    await render({ token: jwt('ali') });
    expect(keyDeletes()).toEqual([]);
  });

  test('a failing revoke never throws and the issue still counts', async () => {
    widgets.setWidgetCredential.mockResolvedValue({ previousKey: 'wk-old' });
    api.delete.mockRejectedValue(new Error('offline'));
    await render({ token: jwt('ali') });
    expect(localStorage.getItem('widget_key_issued:ali')).not.toBeNull();
  });

  test('the raw key is never written to web storage', async () => {
    sessionStorage.clear();
    widgets.setWidgetCredential.mockResolvedValue({ previousKey: 'wk-old' });
    await render({ token: jwt('ali') });
    const stored = [localStorage, sessionStorage].flatMap((st) =>
      Object.keys(st).flatMap((k) => [k, st.getItem(k)]));
    expect(stored.some((v) => v.includes('wk1') || v.includes('wk-old'))).toBe(false);
  });
});

describe('missing native credential (final review Important 2)', () => {
  test('re-issues on mount despite a fresh stamp when the widget has no credential', async () => {
    localStorage.setItem('widget_key_issued:ali', String(Date.now() - 1000));
    widgets.widgetCredentialPresent.mockResolvedValue({ present: false });
    await render({ token: jwt('ali') });
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  test('re-issues on visible despite a fresh stamp when the credential went missing', async () => {
    await render({ token: jwt('ali') });
    widgets.widgetCredentialPresent.mockResolvedValue({ present: false });
    await becomeVisible();
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  test('a fresh stamp and a present credential do not post', async () => {
    localStorage.setItem('widget_key_issued:ali', String(Date.now() - 1000));
    await render({ token: jwt('ali') });
    await becomeVisible();
    expect(api.post).not.toHaveBeenCalled();
  });

  test('an old native build without the presence method falls back to the 24h stamp', async () => {
    localStorage.setItem('widget_key_issued:ali', String(Date.now() - 1000));
    widgets.widgetCredentialPresent.mockResolvedValue(null);
    await render({ token: jwt('ali') });
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe('backoff when the device cannot hold a widget key (final review Minor 2/3)', () => {
  test('iOS below 16.2 never asks the server for a key', async () => {
    widgets.widgetCredentialPresent.mockResolvedValue({ present: false, supported: false });
    const now = Date.now();
    const spy = jest.spyOn(Date, 'now').mockReturnValue(now);
    await render({ token: jwt('ali') });
    spy.mockReturnValue(now + 2 * DAY);
    await becomeVisible();
    expect(api.post).not.toHaveBeenCalled();
  });

  test('a credential native could not store backs off for 6 h and revokes the unused key', async () => {
    widgets.setWidgetCredential.mockResolvedValue(null); // keychain error or missing method
    widgets.widgetCredentialPresent.mockResolvedValue({ present: false });
    const now = Date.now();
    const spy = jest.spyOn(Date, 'now').mockReturnValue(now);
    await render({ token: jwt('ali') });
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(keyDeletes()).toEqual([['/widget/key', { data: { key: 'wk1' } }]]);

    spy.mockReturnValue(now + 6 * HOUR - 1000);
    await becomeVisible();
    expect(api.post).toHaveBeenCalledTimes(1);

    spy.mockReturnValue(now + 6 * HOUR + 1000);
    await becomeVisible();
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  test('an unsupported answer from setWidgetCredential also backs off', async () => {
    widgets.setWidgetCredential.mockResolvedValue({ supported: false });
    widgets.widgetCredentialPresent.mockResolvedValue(null);
    const now = Date.now();
    const spy = jest.spyOn(Date, 'now').mockReturnValue(now);
    await render({ token: jwt('ali') });
    spy.mockReturnValue(now + HOUR); // no issue stamp was set: only the backoff holds it
    await becomeVisible();
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('widget_key_issued:ali')).toBeNull();
  });
});
