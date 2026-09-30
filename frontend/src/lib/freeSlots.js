/**
 * Dashboard "boş zaman" satırları — çalışma saatleri içinde randevu ve mola
 * dışında kalan aralıklar.
 */

export const timeToMinutes = (hhmm) => {
  const [h, m] = String(hhmm || "").split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
};

export const minutesToTime = (mins) =>
  `${String(Math.floor(mins / 60) % 24).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`;

/**
 * @param {object} p
 * @param {string} p.openTime "HH:mm"
 * @param {string} p.closeTime "HH:mm" — "00:00" gece yarısı (günün sonu)
 * @param {Array<[string, number]|{start: string, end: string}>} p.busy
 *   [başlangıç "HH:mm", süre dk] veya { start, end } ("HH:mm")
 * @param {string} p.nowTime "HH:mm" — geçmiş kısım gösterilmez
 * @param {number} [p.minMinutes=30] bundan kısa boşluk gösterilmez
 * @param {number} [p.step=15] rezervasyon slot adımı (açılıştan itibaren)
 * @returns {{ start: number, end: number, bookAt: number }[]} dakika cinsinden
 */
export function computeFreeSlots({ openTime, closeTime, busy, nowTime, minMinutes = 30, step = 15 }) {
  const openMin = timeToMinutes(openTime);
  const closeMin = timeToMinutes(closeTime) || 24 * 60;
  if (closeMin <= openMin) return [];

  const alignToSlot = (m) => (m <= openMin ? openMin : openMin + Math.ceil((m - openMin) / step) * step);
  const earliest = alignToSlot(timeToMinutes(nowTime));

  const intervals = (busy || [])
    .map((b) => {
      if (Array.isArray(b)) {
        const start = timeToMinutes(b[0]);
        return [start, start + (parseInt(b[1], 10) || 30)];
      }
      return [timeToMinutes(b.start), timeToMinutes(b.end)];
    })
    .filter(([s, e]) => e > s)
    .sort((a, b) => a[0] - b[0]);

  const gaps = [];
  const pushGap = (from, to) => {
    const start = Math.max(from, earliest);
    const end = Math.min(to, closeMin);
    if (end - start >= minMinutes) gaps.push({ start, end, bookAt: alignToSlot(start) });
  };

  let cursor = openMin;
  for (const [s, e] of intervals) {
    if (s > cursor) pushGap(cursor, s);
    cursor = Math.max(cursor, e);
    if (cursor >= closeMin) break;
  }
  if (cursor < closeMin) pushGap(cursor, closeMin);
  return gaps;
}
