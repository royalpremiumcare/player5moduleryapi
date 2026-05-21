import api from '../api/api';
import { openExternalUrl } from './openExternalUrl';

export function buildWebsiteSubscribeUrl(webUrl, code) {
  const subscribePath = `${webUrl}/subscribe`;
  if (!code) return subscribePath;
  return `${webUrl}/sso?code=${encodeURIComponent(code)}&redirect=${encodeURIComponent('/subscribe')}`;
}

/** SSO kodunu arka planda al; tıklama anında senkron açılabilsin. */
export async function prefetchWebsiteSubscribeUrl(webUrl) {
  try {
    const resp = await api.post('/sso/create');
    const code = resp?.data?.code;
    if (code) return buildWebsiteSubscribeUrl(webUrl, code);
  } catch (_) {}
  return buildWebsiteSubscribeUrl(webUrl, null);
}

export function openWebsiteSubscribe(url) {
  return openExternalUrl(url);
}
