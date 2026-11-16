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

// Last unregister, by JWT. Logout (AuthContext) and the hook's token-cleared effect both
// unregister the same session; the later call reuses the first one's promise. A register
// re-arms it; a failed (null) unregister may be retried.
let lastUnregister = null;

export function register(options) {
  lastUnregister = null;
  return call('register', options);
}

export const reconcile = () => call('reconcile');

export function unregister(options) {
  const jwt = options?.jwt ?? null;
  if (lastUnregister && lastUnregister.jwt === jwt) return lastUnregister.promise;
  const entry = { jwt, promise: null };
  entry.promise = call('unregister', options).then((result) => {
    if (result === null && lastUnregister === entry) lastUnregister = null;
    return result;
  });
  lastUnregister = entry;
  return entry.promise;
}

export const getStatus = () => call('getStatus');
export const openSettings = () => call('openSettings');
