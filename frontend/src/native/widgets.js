import { Capacitor, registerPlugin } from '@capacitor/core';

// Home Screen widget bridge: methods on the native PlannLiveActivity plugin. Works on any iOS
// device (iPhone and iPad). Every wrapper resolves to null when unsupported (web, Android, old
// native build without the method) and never throws.

const PLUGIN_NAME = 'PlannLiveActivity';
let plugin = null;

export function isWidgetSupported() {
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
  if (!isWidgetSupported()) return null;
  try {
    if (!plugin) plugin = registerPlugin(PLUGIN_NAME);
    return await plugin[method](options);
  } catch (e) {
    return null;
  }
}

export const setWidgetCredential = (options) => call('setWidgetCredential', options);
export const clearWidgetCredential = () => call('clearWidgetCredential');
export const reloadWidgets = () => call('reloadWidgets');
