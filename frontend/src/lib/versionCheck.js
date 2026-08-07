/**
 * Force-update sürüm kontrolü (mobil).
 *
 * Felsefe (bkz. PLANN_MIMARI_YOL_HARITASI Faz 3):
 *  - Backend YALNIZ sinyal verir; istek asla hard-reject edilmez.
 *  - Kilidi UX katmanı (ForceUpdateModal) uygular.
 *  - FAIL-OPEN: config alınamazsa / sürüm okunamazsa kullanıcı ASLA kilitlenmez.
 *  - Sadece native (Capacitor iOS/Android) için anlamlı — web zaten hep günceldir.
 *
 * İki katman:
 *  - `block`: yüklü sürüm < min_supported_version → kapatılamayan modal.
 *  - `soft` : yüklü sürüm < latest_version → kapatılabilir yumuşak uyarı.
 *  - `none` : güncel veya değerlendirilemedi.
 */

/**
 * "6.1" / "6.1.0" / "v6.1" gibi semver benzeri stringi [major, minor, patch]'e çevirir.
 * Bozuk/eksik parçalar 0 sayılır.
 */
function parseVersion(v) {
  if (!v || typeof v !== 'string') return null;
  const cleaned = v.trim().replace(/^v/i, '');
  if (!cleaned) return null;
  const parts = cleaned.split('.').map((p) => {
    const n = parseInt(p, 10);
    return Number.isFinite(n) ? n : 0;
  });
  while (parts.length < 3) parts.push(0);
  return parts.slice(0, 3);
}

/**
 * Semver karşılaştırma. a<b → -1, a==b → 0, a>b → 1.
 * Parse edilemezse null döner (çağıran tarafta güvenli-yönde ele alınır).
 */
export function compareVersions(a, b) {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa || !pb) return null;
  for (let i = 0; i < 3; i++) {
    if (pa[i] > pb[i]) return 1;
    if (pa[i] < pb[i]) return -1;
  }
  return 0;
}

/**
 * Yüklü sürüm + backend config'ine göre güncelleme durumunu hesaplar.
 *
 * @param {Object} p
 * @param {string} p.currentVersion — CapacitorApp.getInfo().version (ör. "6.1")
 * @param {'ios'|'android'|'web'} p.platform
 * @param {Object} p.config — GET /api/app/config yanıtı
 * @returns {{ level: 'block'|'soft'|'none', storeUrl: string }}
 */
export function evaluateUpdate({ currentVersion, platform, config }) {
  const none = { level: 'none', storeUrl: '' };
  // Web hiç kilitlenmez (her zaman güncel servis edilir).
  if (platform !== 'ios' && platform !== 'android') return none;
  if (!config || !currentVersion) return none;

  const minV = config.min_supported_version?.[platform];
  const latestV = config.latest_version?.[platform];
  const storeUrl = config.store_urls?.[platform] || '';

  // min_supported altı → BLOCK (fail-open: karşılaştırma belirsizse bloklama)
  const cmpMin = compareVersions(currentVersion, minV);
  if (cmpMin === -1) return { level: 'block', storeUrl };

  // latest altı → SOFT
  const cmpLatest = compareVersions(currentVersion, latestV);
  if (cmpLatest === -1) return { level: 'soft', storeUrl };

  return { level: 'none', storeUrl };
}
