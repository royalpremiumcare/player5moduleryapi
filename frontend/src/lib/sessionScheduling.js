/**
 * Seans paketi planlama — ilk seanstan sonra haftalık aynı saat (Wizard + SessionPlannerDialog ortak).
 */

export const WH_DAY_MAP = [
  'sunday',
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
];

/** API'den gelen appointment_date (string veya Date) → yyyy-MM-dd */
export function normalizeAppointmentDateStr(dateLike) {
  if (dateLike == null || dateLike === '') return '';
  if (typeof dateLike === 'string') return dateLike.split('T')[0];
  try {
    const d = dateLike instanceof Date ? dateLike : new Date(dateLike);
    if (Number.isNaN(d.getTime())) return '';
    return d.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

/** settings.working_hours veya settings.business_hours → { day: { enabled, start, end } } */
export function normalizeWorkingHours(settings) {
  if (!settings || typeof settings !== 'object') return null;
  const raw = settings.working_hours || settings.business_hours;
  if (!raw || typeof raw !== 'object') return null;
  const out = {};
  for (const day of WH_DAY_MAP) {
    const d = raw[day];
    if (!d) continue;
    const enabled = d.enabled !== undefined ? !!d.enabled : !!d.is_open;
    if (!enabled) {
      out[day] = { enabled: false };
      continue;
    }
    const start = d.start || d.open_time || '09:00';
    const end = d.end || d.close_time || '18:00';
    out[day] = { enabled: true, start, end };
  }
  return Object.keys(out).length ? out : null;
}

function timeToMinutes(t) {
  if (!t || typeof t !== 'string') return 0;
  const p = t.trim().split(':');
  const h = parseInt(p[0], 10);
  const m = parseInt(p[1] ?? '0', 10);
  if (Number.isNaN(h) || Number.isNaN(m)) return 0;
  return h * 60 + m;
}

function minutesToTime(total) {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** Takvim günü ekle — UTC/local kayması olmadan (toISOString ile gün kayması riski yok) */
function addDaysStr(dateStr, deltaDays) {
  const parts = dateStr.split('-').map((p) => parseInt(p, 10));
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return dateStr;
  const [y, m, d] = parts;
  const base = new Date(Date.UTC(y, m - 1, d));
  base.setUTCDate(base.getUTCDate() + deltaDays);
  const yy = base.getUTCFullYear();
  const mm = String(base.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(base.getUTCDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

function normalizeTimeHhMm(t) {
  if (!t || typeof t !== 'string') return '10:00';
  const p = t.trim().split(':');
  const h = Math.min(23, Math.max(0, parseInt(p[0], 10) || 0));
  const m = Math.min(59, Math.max(0, parseInt(p[1] ?? '0', 10) || 0));
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function getDayOpenRange(dateStr, workingHours) {
  if (!workingHours) {
    return { startMin: 9 * 60, endMin: 18 * 60 };
  }
  const d = new Date(`${dateStr}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  const dayName = WH_DAY_MAP[d.getDay()];
  const cfg = workingHours[dayName];
  if (!cfg || !cfg.enabled) return null;
  return {
    startMin: timeToMinutes(cfg.start || '09:00'),
    endMin: timeToMinutes(cfg.end || '18:00'),
  };
}

/**
 * Anchor etrafında: önce tam (liste içinde), sonra geriye yakın, sonra ileri.
 * @param {number} anchorMin
 * @param {number[]} slotMins sıralı benzersiz slot başlangıç dakikaları
 */
export function orderSlotsAroundAnchor(anchorMin, slotMins) {
  const S = [...new Set(slotMins)].filter((m) => Number.isFinite(m)).sort((a, b) => a - b);
  if (S.length === 0) return [];
  const exact = S.includes(anchorMin) ? [anchorMin] : [];
  const below = S.filter((m) => m < anchorMin).sort((a, b) => b - a);
  const above = S.filter((m) => m > anchorMin).sort((a, b) => a - b);
  return [...exact, ...below, ...above];
}

/**
 * İlk seanstan sonra kalan randevular: her biri bir önceki seansa göre **+7 gün**, **aynı saat** (haftalık tekrar).
 * İlk randevu tarihi/saati = anchor; 2. seans = +1 hafta, 3. seans = +2 hafta, …
 *
 * @returns {{ date: string, time: string }[]}
 */
export function buildRemainingPackageSessions(
  firstDateStr,
  firstTimeStr,
  remainingCount,
  serviceDurationMin,
  settingsOrWh,
  options = {}
) {
  const slots = [];
  if (!firstDateStr || !firstTimeStr || remainingCount <= 0) return slots;

  const wh =
    settingsOrWh && (settingsOrWh.business_hours || settingsOrWh.working_hours)
      ? normalizeWorkingHours(settingsOrWh)
      : settingsOrWh;

  const dur = Math.max(1, Number(serviceDurationMin) || 30);
  const timeNorm = normalizeTimeHhMm(firstTimeStr);
  const tMin = timeToMinutes(timeNorm);

  for (let i = 0; i < remainingCount; i++) {
    const dateStr = addDaysStr(firstDateStr, 7 * (i + 1));
    const range = getDayOpenRange(dateStr, wh);
    if (range && (tMin < range.startMin || tMin + dur > range.endMin)) {
      const clamped = Math.min(range.endMin - dur, Math.max(range.startMin, tMin));
      slots.push({ date: dateStr, time: minutesToTime(clamped) });
    } else {
      slots.push({ date: dateStr, time: timeNorm });
    }
  }

  return slots;
}

/**
 * Haftalık aynı saat kuralı — buildRemainingPackageSessions ile aynı.
 */
export function buildRemainingSessionsWeekly(
  firstDateStr,
  firstTime,
  remainingCount,
  workingHours,
  options = {}
) {
  const wh = workingHours && (workingHours.business_hours || workingHours.working_hours)
    ? normalizeWorkingHours(workingHours)
    : workingHours;
  const sd = options.serviceDurationMinutes ?? 30;
  return buildRemainingPackageSessions(firstDateStr, firstTime, remainingCount, sd, wh, options);
}

/**
 * SessionPlannerDialog: appointment + kalan adet ile varsayılan slot listesi.
 */
export function buildRemainingSlotsFromAppointment(appointment, remainingCount, settingsOrWh, options = {}) {
  if (!appointment || remainingCount <= 0) return [];
  const firstDateStr = normalizeAppointmentDateStr(appointment.appointment_date);
  const firstTime = appointment.appointment_time || '10:00';
  const dur =
    options.serviceDurationMinutes ??
    appointment.service_duration ??
    30;
  return buildRemainingPackageSessions(
    firstDateStr,
    firstTime,
    remainingCount,
    dur,
    settingsOrWh,
    options
  );
}

/**
 * Satır personeli yoksa paket varsayılanı; her iki yol aynı kural.
 * bulk-check: null dönen üst staff_id ile tamamlanır.
 */
export function effectiveBulkStaffForRow(rowStaff, packageDefaultStaff) {
  const r = (rowStaff || '').trim();
  if (r) return r;
  const p = (packageDefaultStaff || '').trim();
  return p || '';
}

/**
 * Wizard Adım 3 — otomatik ve manuel aynı üretici: ilk seanstan sonraki bulk satırları.
 * Eksik üretimde kalanı son geçerli slottan devam ettirerek tamamlar.
 */
export function buildWizardRemainingPackageRows({
  firstDateStr,
  firstTime,
  sessionTotal,
  settings,
  serviceDurationMinutes = 30,
  intervalMinutes = 30,
}) {
  const remaining = Math.max(0, (Number(sessionTotal) || 1) - 1);
  if (remaining === 0) {
    return { rows: [], complete: true, expectedRemaining: 0 };
  }
  const dur = Math.max(1, Number(serviceDurationMinutes) || 30);

  const rows = buildRemainingSessionsWeekly(
    firstDateStr,
    firstTime,
    remaining,
    settings,
    { serviceDurationMinutes: dur, intervalMinutes }
  );

  const complete = rows.length >= remaining;
  return {
    rows: rows.slice(0, remaining),
    complete,
    expectedRemaining: remaining,
  };
}

/**
 * POST /appointments/bulk-session gövdesi — Wizard + SessionPlanner tek şema.
 */
export function buildBulkSessionPayload({
  customer_name,
  phone,
  service_id,
  staff_member_id,
  notes,
  session_group_id,
  starting_session_number,
  session_total,
  sessions,
  // Admin "yeni paket" akışı (AppointmentFormWizard): 1. seans önce
  // POST /appointments ile yaratılır; ardından bu çağrı ile 2..N eklenir.
  // Tek WhatsApp mesajında 1. seansın da listelenmesi için bu bayrak true
  // gönderilir. Kalanları sonradan planla akışlarında (SessionPlanner*)
  // müşteri 1. seansı zaten biliyor olduğundan false bırakılır.
  notify_include_existing_sessions,
}) {
  return {
    customer_name: (customer_name || '').trim(),
    phone: (phone || '').trim(),
    service_id: (service_id || '').trim(),
    staff_member_id: staff_member_id || undefined,
    notes: notes || '',
    session_group_id: session_group_id || undefined,
    starting_session_number: Number(starting_session_number) || 1,
    session_total: session_total != null ? Number(session_total) : undefined,
    notify_include_existing_sessions: Boolean(notify_include_existing_sessions),
    sessions: (sessions || []).map((s) => {
      const row = {
        date: (s.date || '').trim(),
        time: (s.time || '').trim(),
      };
      const sid = (s.staff_member_id || '').trim();
      if (sid) row.staff_member_id = sid;
      return row;
    }),
  };
}

/**
 * İstemci tarafı ön doğrulama (sunucu tek doğruluk kaynağı).
 * @returns {{ ok: boolean, errors: string[] }}
 */
export function validateSessionSchedule(sessions) {
  const errors = [];
  if (!sessions || sessions.length === 0) {
    errors.push('empty_sessions');
    return { ok: false, errors };
  }
  sessions.forEach((s, i) => {
    if (!s.date || !/^\d{4}-\d{2}-\d{2}$/.test(s.date)) {
      errors.push(`bad_date_${i}`);
    }
    if (!s.time || !/^\d{1,2}:\d{2}$/.test(s.time)) {
      errors.push(`bad_time_${i}`);
    }
  });
  return { ok: errors.length === 0, errors };
}

/**
 * Mevcut api instance ile bulk-check.
 * @param {(string|null)[]|undefined} [staff_ids] — slots ile aynı uzunluk; null öğe paket varsayılanı staff_id kullanır.
 */
export async function checkAvailabilityForSlots(api, { service_id, staff_id, slots, staff_ids }) {
  const body = {
    service_id,
    staff_id,
    slots,
  };
  if (
    staff_ids != null &&
    Array.isArray(staff_ids) &&
    staff_ids.length === slots.length
  ) {
    body.staff_ids = staff_ids;
  }
  const res = await api.post('/availability/bulk-check', body);
  return res.data;
}

/**
 * Backend dalga planlayıcı — haftalık hedef + wave + personel fallback.
 * @returns {Promise<{ sessions: object[], unplanned_count: number, message?: string }>}
 */
export async function fetchWavePlanSessions(api, body) {
  const res = await api.post('/sessions/wave-plan', body);
  return res.data;
}
