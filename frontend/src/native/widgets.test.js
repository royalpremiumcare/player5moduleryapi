import { Capacitor, registerPlugin } from '@capacitor/core';
import { setWidgetCredential, clearWidgetCredential, reloadWidgets } from './widgets';

jest.mock('@capacitor/core', () => {
  const plugin = {
    setWidgetCredential: jest.fn(),
    clearWidgetCredential: jest.fn(),
    reloadWidgets: jest.fn(),
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

beforeEach(() => {
  jest.clearAllMocks();
  registerPlugin.mockReturnValue(plugin);
  Capacitor.isNativePlatform.mockReturnValue(true);
  Capacitor.getPlatform.mockReturnValue('ios');
  Capacitor.isPluginAvailable.mockReturnValue(true);
  plugin.setWidgetCredential.mockResolvedValue({});
  plugin.clearWidgetCredential.mockResolvedValue({});
  plugin.reloadWidgets.mockResolvedValue({});
});

test('forwards the three calls to the native plugin on iOS', async () => {
  await setWidgetCredential({ key: 'k', baseUrl: 'https://x' });
  await clearWidgetCredential();
  await reloadWidgets();
  expect(plugin.setWidgetCredential).toHaveBeenCalledWith({ key: 'k', baseUrl: 'https://x' });
  expect(plugin.clearWidgetCredential).toHaveBeenCalledTimes(1);
  expect(plugin.reloadWidgets).toHaveBeenCalledTimes(1);
});

test('reloadWidgets is a no-op off iOS', async () => {
  Capacitor.getPlatform.mockReturnValue('android');
  expect(await reloadWidgets()).toBeNull();
  expect(await clearWidgetCredential()).toBeNull();
  expect(await setWidgetCredential({ key: 'k', baseUrl: 'b' })).toBeNull();
  expect(plugin.reloadWidgets).not.toHaveBeenCalled();
  expect(plugin.clearWidgetCredential).not.toHaveBeenCalled();
  expect(plugin.setWidgetCredential).not.toHaveBeenCalled();
});

test('no-op when the plugin is unavailable', async () => {
  Capacitor.isPluginAvailable.mockReturnValue(false);
  expect(await reloadWidgets()).toBeNull();
  expect(plugin.reloadWidgets).not.toHaveBeenCalled();
});

test('never throws when the method is missing (old native build) or rejects', async () => {
  const saved = plugin.reloadWidgets;
  plugin.reloadWidgets = undefined;
  await expect(reloadWidgets()).resolves.toBeNull();
  plugin.reloadWidgets = saved;
  plugin.clearWidgetCredential.mockRejectedValue(new Error('boom'));
  await expect(clearWidgetCredential()).resolves.toBeNull();
});
