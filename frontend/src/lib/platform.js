import { Capacitor } from '@capacitor/core';

export const isAndroid = () => Capacitor.getPlatform() === 'android';
export const isIOS = () => Capacitor.getPlatform() === 'ios';
export const isNative = () => Capacitor.isNativePlatform();

/**
 * Returns Tailwind classes conditionally based on platform.
 * Android does not support backdrop-blur well in WebView — use solid bg instead.
 */
export const blurCard = isAndroid()
  ? 'bg-white border border-zinc-100'
  : 'backdrop-blur-xl bg-white/40 border border-white/20';

export const blurCardHover = isAndroid()
  ? 'bg-white border border-zinc-100 hover:bg-zinc-50'
  : 'backdrop-blur-xl bg-white/40 border border-white/20 hover:bg-white/50';

export const blurHeader = isAndroid()
  ? 'bg-white border-b border-zinc-100'
  : 'backdrop-blur-2xl bg-white/70 border-b border-white/20';

export const blurFooter = isAndroid()
  ? 'bg-white border-t border-zinc-100'
  : 'backdrop-blur-2xl bg-white/80 border-t border-white/20';

export const blurInput = isAndroid()
  ? 'bg-white border border-zinc-200'
  : 'backdrop-blur-xl bg-white/40 border border-white/30';

export const blurDialog = isAndroid()
  ? 'bg-white'
  : 'backdrop-blur-2xl bg-white/95 border-white/30';
