import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Capacitor, registerPlugin } from '@capacitor/core';
import { useLiveActivities } from './useLiveActivities';
import * as la from './liveActivities';

jest.mock('@capacitor/core', () => {
  const plugin = {
    register: jest.fn(),
    reconcile: jest.fn(),
    unregister: jest.fn(),
    getStatus: jest.fn(),
    openSettings: jest.fn(),
  };
  return {
    __plugin: plugin,
    Capacitor: {
      isNativePlatform: jest.fn(),
      getPlatform: jest.fn(),
      isPluginAvailable: jest.fn(),
    },
    registerPlugin: jest.fn(() => plugin),
  };
});

const plugin = require('@capacitor/core').__plugin;

global.IS_REACT_ACT_ENVIRONMENT = true;

const jwt = (sub) => `h.${btoa(JSON.stringify({ sub }))}.s`;

let container;
let root;
let latest;

function Probe(props) {
  latest = useLiveActivities(props);
  return null;
}

async function render(props) {
  await act(async () => {
    root.render(<Probe {...props} />);
  });
}

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
}

beforeEach(() => {
  jest.clearAllMocks();
  registerPlugin.mockReturnValue(plugin);
  Capacitor.isNativePlatform.mockReturnValue(true);
  Capacitor.getPlatform.mockReturnValue('ios');
  Capacitor.isPluginAvailable.mockReturnValue(true);
  plugin.register.mockResolvedValue({ supported: true, deviceId: 'd', newSecret: 's' });
  plugin.reconcile.mockResolvedValue({ ended: 0, startedLocally: 0 });
  plugin.unregister.mockResolvedValue({ supported: true, ended: 0 });
  plugin.getStatus.mockResolvedValue({ supported: true, enabled: true, iosVersion: '17.0' });
  setVisibility('visible');
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

describe('useLiveActivities', () => {
  test('no-op without plugin', async () => {
    Capacitor.isPluginAvailable.mockReturnValue(false);
    await render({ token: jwt('ali'), orgFlagEnabled: true });
    expect(plugin.register).not.toHaveBeenCalled();
    expect(plugin.reconcile).not.toHaveBeenCalled();
    expect(la.isLiveActivitySupported()).toBe(false);
  });

  test('no-op on non-iOS platforms', async () => {
    Capacitor.getPlatform.mockReturnValue('android');
    await render({ token: jwt('ali'), orgFlagEnabled: true });
    expect(plugin.register).not.toHaveBeenCalled();
  });

  test('no-op when org flag off', async () => {
    await render({ token: jwt('ali'), orgFlagEnabled: false });
    expect(plugin.register).not.toHaveBeenCalled();
    expect(plugin.reconcile).not.toHaveBeenCalled();
  });

  test('register once per login', async () => {
    const token = jwt('ali');
    await render({ token, orgFlagEnabled: true });
    await render({ token, orgFlagEnabled: true });
    expect(plugin.register).toHaveBeenCalledTimes(1);
    expect(plugin.register).toHaveBeenCalledWith({
      apiBaseUrl: window.location.origin,
      jwt: token,
      fcmToken: undefined,
    });
    expect(plugin.reconcile).toHaveBeenCalledTimes(1);
    expect(latest.status).toEqual({ supported: true, enabled: true, iosVersion: '17.0' });
  });

  test('does not treat supported:false as a registration and does not loop', async () => {
    plugin.register.mockResolvedValue({ supported: false });
    const token = jwt('ali');
    await render({ token, orgFlagEnabled: true });
    await render({ token, orgFlagEnabled: true });
    expect(plugin.register).toHaveBeenCalledTimes(1);
    expect(plugin.reconcile).not.toHaveBeenCalled();
  });

  test('reconcile on visible', async () => {
    await render({ token: jwt('ali'), orgFlagEnabled: true });
    plugin.reconcile.mockClear();
    setVisibility('hidden');
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(plugin.reconcile).not.toHaveBeenCalled();
    setVisibility('visible');
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(plugin.reconcile).toHaveBeenCalledTimes(1);
  });

  test('unregister on logout then register on next login', async () => {
    const t1 = jwt('ali');
    await render({ token: t1, orgFlagEnabled: true });
    await render({ token: null, orgFlagEnabled: true });
    expect(plugin.unregister).toHaveBeenCalledTimes(1);
    expect(plugin.unregister).toHaveBeenCalledWith({ jwt: t1 });
    const t2 = jwt('veli');
    await render({ token: t2, orgFlagEnabled: true });
    expect(plugin.register).toHaveBeenCalledTimes(2);
    expect(plugin.register).toHaveBeenLastCalledWith(expect.objectContaining({ jwt: t2 }));
    plugin.reconcile.mockClear();
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(plugin.reconcile).toHaveBeenCalledTimes(1);
  });

  test('wrappers swallow plugin errors', async () => {
    for (const m of Object.keys(plugin)) plugin[m].mockRejectedValue(new Error('boom'));
    await expect(la.register({})).resolves.toBeNull();
    await expect(la.reconcile()).resolves.toBeNull();
    await expect(la.unregister({ jwt: 'x' })).resolves.toBeNull();
    await expect(la.getStatus()).resolves.toBeNull();
    await expect(la.openSettings()).resolves.toBeNull();
  });

  test('wrappers resolve null when unsupported', async () => {
    Capacitor.isNativePlatform.mockReturnValue(false);
    await expect(la.register({})).resolves.toBeNull();
    expect(plugin.register).not.toHaveBeenCalled();
    expect(registerPlugin).toBeDefined();
  });
});
