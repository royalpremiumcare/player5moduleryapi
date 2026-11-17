// plannapp:// derin bağlantıları (widget "+" ve randevu satırı, Live Activity kartı).
// plannapp://checkout/... burada sahiplenilmez; onu handleCheckoutDeepLink işler.

const PREFIX = 'plannapp://';

export function parseAppDeepLink(url) {
  if (typeof url !== 'string' || !url.toLowerCase().startsWith(PREFIX)) return null;
  const rest = url.slice(PREFIX.length).split('#')[0];
  const qIndex = rest.indexOf('?');
  const path = qIndex === -1 ? rest : rest.slice(0, qIndex);
  const query = qIndex === -1 ? '' : rest.slice(qIndex + 1);
  const [host, ...segments] = path.split('/');

  if (host === 'new-appointment') {
    const source = new URLSearchParams(query).get('source');
    return { kind: 'new-appointment', source: source && /^[a-z_]{1,32}$/.test(source) ? source : null };
  }

  if (host === 'appointment') {
    if (!segments[0]) return null;
    try {
      const id = decodeURIComponent(segments[0]);
      return /^[A-Za-z0-9_-]{1,64}$/.test(id) ? { kind: 'appointment', id } : null;
    } catch {
      return null;
    }
  }

  return null;
}
