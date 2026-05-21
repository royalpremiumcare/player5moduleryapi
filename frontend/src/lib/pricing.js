// PLANN — Subscribe.js ↔ LandingPage tek-kaynak (Single Source of Truth) fiyat tablosu.
//
// Bu tablo Stripe Fixed Amount Coupon değerleriyle 1:1 senkrondur ve sayısal
// değerler hem landing sayfasında hem de uygulama içi /subscribe ekranında
// aynı kaynaktan okunur. Drift (iki dosyanın tutarsızlaşması) önlenir.
//
// Plan anahtarları LOWERCASE ve dil-bağımsız (EN slug). Türkçe gelen
// plan adları (kurumsal/standart/profesyonel) `normalizePlanKey` aracılığı
// ile EN slug'a normalize edilir.
//
// Yıllık fiyat: monthly * 10 (2 ay ücretsiz). Stripe lookup_key'ler
// `{plan}_{cycle}_{currency}` formatında.

export const PRICING = {
  try: {
    standard:     { original: 1090, discounted: 990  },
    professional: { original: 1490, discounted: 1390 },
    premium:      { original: 1550, discounted: 1150 },
    business:     { original: 1950, discounted: 1450 },
    enterprise:   { original: 2350, discounted: 1750 },
    corporate:    { original: 2850, discounted: 2490 },
  },
  gbp: {
    standard:     { original: 16, discounted: 12 },  // 16 - 4 = 12
    professional: { original: 24, discounted: 18 },  // 24 - 6 = 18
    premium:      { original: 32, discounted: 24 },  // 32 - 8 = 24
    business:     { original: 40, discounted: 30 },  // 40 - 10 = 30
    enterprise:   { original: 56, discounted: 42 },  // 56 - 14 = 42
    corporate:    { original: 80, discounted: 60 },  // 80 - 20 = 60
  },
};

/**
 * Hem TR (standart/profesyonel/kurumsal) hem EN (standard/professional/corporate)
 * gelen plan ismini EN slug'a indirger. Plan tablosu erişimi her yerden bu
 * fonksiyon üzerinden gider.
 *
 * @param {string} planName  - "Standart", "Premium", "Corporate", vb.
 * @returns {string|null}    - "standard" | "professional" | "premium" | "business" | "enterprise" | "corporate" | null
 */
export function normalizePlanKey(planName) {
  const k = String(planName || '').toLowerCase().trim();
  if (!k) return null;
  if (k.includes('standart') || k.includes('standard')) return 'standard';
  if (k.includes('profesyonel') || k.includes('professional')) return 'professional';
  if (k.includes('premium')) return 'premium';
  if (k.includes('business')) return 'business';
  if (k.includes('enterprise')) return 'enterprise';
  if (k.includes('kurumsal') || k.includes('corporate')) return 'corporate';
  return null;
}

/**
 * Yıllık fiyat: aylık * 10 (2 ay ücretsiz teaser).
 * @param {'try'|'gbp'} currency
 * @param {string} planKey       - EN slug ("standard", vb.)
 * @returns {number|null}
 */
export function getYearlyPrice(currency, planKey) {
  const monthly = PRICING[currency]?.[planKey]?.original;
  return monthly ? Math.round(monthly * 10) : null;
}

/**
 * UI yardımcı — tek aylık fiyat veya indirimli fiyatı verir.
 * @param {'try'|'gbp'} currency
 * @param {string} planKey
 * @param {{ discounted?: boolean }} [opts]
 * @returns {number|null}
 */
export function getMonthlyPrice(currency, planKey, { discounted = false } = {}) {
  const cell = PRICING[currency]?.[planKey];
  if (!cell) return null;
  return discounted ? cell.discounted : cell.original;
}

// Legacy isim — Subscribe.js içindeki eski PRICING_DISPLAY ile uyumluluk.
export const PRICING_DISPLAY = PRICING;

export default PRICING;
