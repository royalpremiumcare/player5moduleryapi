// Giriş yapılmamışken gelen derin bağlantıyı girişten sonra uygulamak için sakla.
const KEY = 'plann_pending_deep_link';
const MAX_AGE_MS = 10 * 60 * 1000;

export function savePending(intent) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify({ intent, at: Date.now() }));
  } catch {
    /* storage kapalı: sessizce geç */
  }
}

export function clearPending() {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* noop */
  }
}

export function takePending(now = Date.now()) {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    clearPending();
    const { intent, at } = JSON.parse(raw);
    if (!intent || typeof at !== 'number' || now - at > MAX_AGE_MS) return null;
    return intent;
  } catch {
    return null;
  }
}
