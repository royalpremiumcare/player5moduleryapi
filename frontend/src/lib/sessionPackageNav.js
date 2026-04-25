/**
 * Alt çubukta "Seanslar" sekmesinin görünürlüğü — App.js ile aynı kural.
 * Aktif çok seanslı paket: session_group_id + session_total>1 ve grupta en az bir açık (terminal olmayan) randevu.
 */
const TERMINAL = new Set(["Tamamlandı", "İptal", "İptal Edildi", "Cancelled"]);

export function computeHasActiveSessions(appointments) {
  const groups = new Map();
  for (const a of appointments || []) {
    const gid = a.session_group_id;
    const st = a.session_total;
    if (!gid || !st || st <= 1) continue;
    if (!groups.has(gid)) groups.set(gid, []);
    groups.get(gid).push(a);
  }
  for (const [, list] of groups) {
    const total = list[0]?.session_total || 0;
    const open = list.filter((x) => !TERMINAL.has(x.status || "")).length;
    if (total > 1 && open > 0) return true;
  }
  return false;
}
