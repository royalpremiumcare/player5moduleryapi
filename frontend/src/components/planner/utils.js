/**
 * Plann — Session Planner utilities
 * Pure helpers for date formatting + client-side conflict resolution.
 */

const TR_DAYS_FULL = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
const TR_DAYS_SHORT = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];
const TR_MONTHS = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
const EN_DAYS_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const EN_DAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const EN_MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

export function parseLocalDate(dateStr) {
  if (!dateStr) return null;
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function formatDateLong(dateStr, lang = "tr") {
  const d = parseLocalDate(dateStr);
  if (!d) return dateStr || "";
  const isTr = lang === "tr";
  const day = isTr ? TR_DAYS_FULL[d.getDay()] : EN_DAYS_FULL[d.getDay()];
  const month = isTr ? TR_MONTHS[d.getMonth()] : EN_MONTHS[d.getMonth()];
  return isTr ? `${day} ${d.getDate()} ${month}` : `${day}, ${month} ${d.getDate()}`;
}

export function formatDateShort(dateStr, lang = "tr") {
  const d = parseLocalDate(dateStr);
  if (!d) return dateStr || "";
  const isTr = lang === "tr";
  const day = isTr ? TR_DAYS_SHORT[d.getDay()] : EN_DAYS_SHORT[d.getDay()];
  const month = isTr ? TR_MONTHS[d.getMonth()].slice(0, 3) : EN_MONTHS[d.getMonth()].slice(0, 3);
  return `${day} ${d.getDate()} ${month}`;
}

export function addDays(dateStr, days) {
  const d = parseLocalDate(dateStr);
  if (!d) return dateStr;
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addMinutes(timeStr, minutes) {
  if (!timeStr) return timeStr;
  const [h, m] = timeStr.split(":").map(Number);
  const total = h * 60 + m + minutes;
  const nh = Math.floor(total / 60) % 24;
  const nm = total % 60;
  return `${String(nh).padStart(2, "0")}:${String(nm).padStart(2, "0")}`;
}

/**
 * Weekly heat-map: given a center date, returns 7 days (Mon..Sun) with bucket info.
 */
export function getWeekDays(centerDateStr) {
  const center = parseLocalDate(centerDateStr) || new Date();
  const dow = center.getDay(); // 0=Sun
  const mondayOffset = dow === 0 ? -6 : 1 - dow;
  const monday = new Date(center);
  monday.setDate(center.getDate() + mondayOffset);
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    days.push({
      dateStr: `${y}-${m}-${day}`,
      date: d,
      dayIdx: d.getDay(),
      dayNum: d.getDate(),
    });
  }
  return days;
}

/**
 * Given a session row with a conflict + alternatives, produce human-friendly
 * suggestion chips sorted by relevance.
 *
 *   1. Same day, same staff, ±30 min
 *   2. Same day, different available staff
 *   3. Next-week same time (caller supplies)
 */
export function rankAlternatives(session, packageStaffId) {
  if (!session || session.available !== false) return [];
  const out = [];
  const baseTime = session.time || "10:00";
  const alts = Array.isArray(session.alternatives) ? session.alternatives : [];

  // 1. Same-day ±30 minute slots
  const near = alts
    .map((a) => (typeof a === "string" ? { time: a, kind: "time" } : { ...a, kind: "time" }))
    .sort((x, y) => {
      const dx = Math.abs(timeDiffMinutes(x.time, baseTime));
      const dy = Math.abs(timeDiffMinutes(y.time, baseTime));
      return dx - dy;
    })
    .slice(0, 4);
  out.push(...near);

  // 2. Suggested different staff (same time)
  if (session.suggested_staff && session.suggested_staff !== packageStaffId) {
    out.push({
      kind: "staff",
      time: session.time,
      staff_member_id: session.suggested_staff,
      staff_name: session.suggested_staff_name || "",
    });
  }

  return out;
}

function timeDiffMinutes(a, b) {
  if (!a || !b) return 9999;
  const [ah, am] = a.split(":").map(Number);
  const [bh, bm] = b.split(":").map(Number);
  return ah * 60 + am - (bh * 60 + bm);
}

/**
 * Green/amber/red summary for a session row.
 *   green  → available === true
 *   amber  → available === false (has alternatives)
 *   gray   → available === null (not yet checked)
 */
export function sessionStatus(session) {
  if (session?.available === true) return "green";
  if (session?.available === false) return "amber";
  return "gray";
}

export function conflictCount(sessions) {
  return (sessions || []).filter((s) => s.available === false).length;
}

export function allGreen(sessions) {
  return (sessions || []).length > 0 && sessions.every((s) => s.available === true);
}
