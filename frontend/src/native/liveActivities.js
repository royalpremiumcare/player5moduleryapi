import { Capacitor, registerPlugin } from '@capacitor/core';

// Bridge to the native PlannLiveActivity Capacitor plugin (iOS 16.2+ only).
// Every wrapper resolves to null when unsupported and never throws.

const PLUGIN_NAME = 'PlannLiveActivity';
let plugin = null;

export function isLiveActivitySupported() {
  try {
    return (
      Capacitor.isNativePlatform() &&
      Capacitor.getPlatform() === 'ios' &&
      Capacitor.isPluginAvailable(PLUGIN_NAME)
    );
  } catch (e) {
    return false;
  }
}

async function call(method, options) {
  if (!isLiveActivitySupported()) return null;
  try {
    if (!plugin) plugin = registerPlugin(PLUGIN_NAME);
    return await plugin[method](options);
  } catch (e) {
    return null;
  }
}

export const register = (options) => call('register', options);
export const reconcile = () => call('reconcile');
export const unregister = (options) => call('unregister', options);
export const getStatus = () => call('getStatus');
export const openSettings = () => call('openSettings');
