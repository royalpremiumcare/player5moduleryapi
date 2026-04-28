/**
 * Plann — Session Planner hooks.
 * Encapsulates data fetching, optimistic saving, and planner-settings access.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { toast } from "sonner";
import api from "../../api/api";
import {
  buildRemainingSlotsFromAppointment,
  fetchWavePlanSessions,
  normalizeAppointmentDateStr,
  validateSessionSchedule,
  buildBulkSessionPayload,
  normalizeWorkingHours,
} from "../../lib/sessionScheduling";
import { formatApiError } from "../../lib/apiError";

/**
 * Converts an appointment into a set of computed sessions (date/time/staff)
 * augmented with availability info after a bulk-check round-trip.
 *
 *   sessions[i] = {
 *     date, time, staff_member_id, unplanned,
 *     available: null|true|false,
 *     alternatives: string[],
 *     suggested_staff, suggested_staff_name
 *   }
 */
export function usePlanSuggestion({ appointment, open, plannerSettings, remainingCount }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  // A monotonic counter bumped every time we populate sessions from scratch;
  // effects depending on it can reliably re-fire even when length is unchanged.
  const [reloadTick, setReloadTick] = useState(0);

  const mapRow = useCallback(
    (s, i, fallback = []) => ({
      date: s.date || fallback[i]?.date || "",
      time: s.time || fallback[i]?.time || "",
      staff_member_id: s.staff_member_id
        ? String(s.staff_member_id)
        : (appointment?.staff_member_id && String(appointment.staff_member_id)) || "",
      unplanned: !!s.unplanned,
      available: null,
      alternatives: [],
      suggested_staff: null,
      suggested_staff_name: null,
    }),
    [appointment?.staff_member_id]
  );

  const load = useCallback(async () => {
    if (!appointment || remainingCount <= 0) {
      setSessions([]);
      return;
    }
    setLoading(true);
    const fallback = buildRemainingSlotsFromAppointment(appointment, remainingCount, plannerSettings, {
      intervalMinutes: plannerSettings?.appointment_interval || 30,
      serviceDurationMinutes: appointment.service_duration ?? undefined,
    });
    try {
      const data = await fetchWavePlanSessions(api, {
        service_id: appointment.service_id,
        first_session_date: normalizeAppointmentDateStr(appointment.appointment_date),
        first_session_time: appointment.appointment_time || "10:00",
        remaining_count: remainingCount,
        staff_member_id: appointment.staff_member_id || undefined,
      });
      const rows = (data?.sessions || []).map((s, i) => mapRow(s, i, fallback));
      setSessions(rows.length ? rows : fallback.map((s, i) => mapRow(s, i, fallback)));
    } catch (e) {
      // Silent fallback — network hiccup shouldn't block the user.
      console.warn("[planner] wave-plan failed, falling back", e);
      setSessions(fallback.map((s, i) => mapRow(s, i, fallback)));
    } finally {
      setLoading(false);
      setReloadTick((x) => x + 1);
    }
  }, [appointment, remainingCount, plannerSettings, mapRow]);

  const check = useCallback(async () => {
    if (!appointment || sessions.length === 0) return;
    setChecking(true);
    try {
      const slots = sessions.map((s) => `${s.date}T${s.time}`);
      const staff_ids = sessions.map((s) => (s.staff_member_id || "").trim() || null);
      const res = await api.post("/availability/bulk-check", {
        service_id: appointment.service_id,
        staff_id: appointment.staff_member_id,
        slots,
        staff_ids,
      });
      const results = res.data || [];
      setSessions((prev) =>
        prev.map((s, i) => ({
          ...s,
          available: results[i]?.available ?? null,
          alternatives: results[i]?.alternatives || [],
          suggested_staff: results[i]?.suggested_staff || null,
          suggested_staff_name: results[i]?.suggested_staff_name || null,
        }))
      );
    } catch (e) {
      toast.error("Müsaitlik kontrolü başarısız");
    } finally {
      setChecking(false);
    }
  }, [appointment, sessions]);

  // Auto-load on open + auto-check after first load
  useEffect(() => {
    if (open && appointment && remainingCount > 0) {
      load();
    }
  }, [open, appointment, remainingCount, load]);

  // Auto-check: fires on every fresh reload (even if length is identical) so
  // re-plan / re-open reliably refreshes status dots without user action.
  useEffect(() => {
    if (open && reloadTick > 0 && sessions.length > 0) {
      const t = setTimeout(check, 250);
      return () => clearTimeout(t);
    }
  }, [reloadTick, open]);

  const patch = useCallback((idx, patchObj) => {
    setSessions((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patchObj, available: null, alternatives: [] };
      return next;
    });
  }, []);

  return { sessions, setSessions, loading, checking, load, check, patch };
}

/**
 * Fetches planner-wide settings + staff list.
 */
export function usePlannerSettings(open) {
  const [plannerSettings, setPlannerSettings] = useState(null);
  const [allStaff, setAllStaff] = useState([]);
  useEffect(() => {
    if (!open) return;
    api.get("/settings").then((r) => setPlannerSettings(r.data || null)).catch(() => {});
    api.get("/users").then((r) => setAllStaff(r.data || [])).catch(() => {});
  }, [open]);

  const workingHours = useMemo(
    () => normalizeWorkingHours(plannerSettings) || plannerSettings?.working_hours || plannerSettings?.business_hours || null,
    [plannerSettings]
  );

  const getDayRange = useCallback(
    (date) => {
      if (!workingHours || !date) return null;
      const dayName = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"][date.getDay()];
      const cfg = workingHours[dayName];
      if (!cfg || !cfg.enabled) return null;
      return { start: cfg.start || "09:00", end: cfg.end || "18:00" };
    },
    [workingHours]
  );

  return { plannerSettings, allStaff, workingHours, getDayRange };
}

/**
 * Given a concrete date+time+service, asks the backend which of the supplied
 * staff are available at that moment. Returns a map `{ [username]: bool }`.
 *
 *   • Re-runs automatically whenever date/time/qualifiedStaff change
 *   • Uses a monotonically-increasing requestId to discard stale responses
 *     (protects against the "clicked 9:00 then 10:00 quickly → 9:00 reply
 *     arrived last and overwrote the correct 10:00 result" race)
 *   • Returns `loading: true` only on the first probe; subsequent reprobes
 *     keep the previous result visible to avoid chip flicker
 */
export function useStaffAvailability({ serviceId, date, time, staff, excludeAppointmentId }) {
  const [map, setMap] = useState({});
  const [loading, setLoading] = useState(false);

  // Signature used as dep — stable identity keeps effect tight.
  const staffKey = useMemo(() => (staff || []).map((s) => s.username).join("|"), [staff]);

  useEffect(() => {
    if (!serviceId || !date || !time || !(staff && staff.length)) {
      setMap({});
      return;
    }
    let cancelled = false;
    setLoading((prev) => (Object.keys(map).length === 0 ? true : prev));
    const slots = staff.map(() => `${date}T${time}`);
    const staff_ids = staff.map((s) => s.username);
    api
      .post("/availability/bulk-check", {
        service_id: serviceId,
        slots,
        staff_ids,
        exclude_appointment_id: excludeAppointmentId || undefined,
      })
      .then((res) => {
        if (cancelled) return;
        const results = res?.data?.results || [];
        const next = {};
        results.forEach((r, i) => {
          const uname = staff_ids[i];
          // Accept multiple backend response shapes defensively
          const ok = r?.available === true || r?.ok === true || r?.is_available === true;
          next[uname] = !!ok;
        });
        setMap(next);
      })
      .catch(() => {
        if (cancelled) return;
        // Fallback to "unknown" — UI will show staff as selectable but
        // without a green dot, consistent with the rest of the planner.
        setMap({});
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line
  }, [serviceId, date, time, staffKey, excludeAppointmentId]);

  return { availabilityMap: map, loading };
}

/**
 * Commits the planned sessions via the bulk-session endpoint with optimistic
 * UI feedback and idempotent retries.
 *
 * `notifyIncludeExistingSessions` — Yeni paket akışında (AppointmentFormWizard
 * "Manuel Planla") 1. seans bu dialogtan önce POST /appointments ile yaratılır.
 * Müşteriye gidecek tek SESSION_PACKAGE WhatsApp mesajında 1. seansın da
 * listelenmesi için backend'e bayrak gönderilir. "Kalanları sonradan planla"
 * akışlarında (Dashboard / Calendar / SessionsHub / Customers) müşteri 1.
 * seansı zaten önceki mesajdan biliyor olduğu için bayrak false bırakılır ve
 * yalnızca yeni planlananlar listelenir.
 */
export function useOptimisticPlan({ appointment, sessions, onDone, t, notifyIncludeExistingSessions = false }) {
  const [creating, setCreating] = useState(false);

  const submit = useCallback(async () => {
    if (!appointment) return;
    setCreating(true);
    try {
      const rawSessions = sessions.map((s) => {
        const row = { date: s.date, time: s.time };
        const st = (s.staff_member_id || "").trim();
        if (st) row.staff_member_id = st;
        return row;
      });
      const v = validateSessionSchedule(rawSessions);
      if (!v.ok) {
        toast.error(t ? t("sessionPlanner.validationFailed") : "Lütfen tarih ve saatleri kontrol edin.");
        return false;
      }
      const startingNumber = (Number(appointment.session_number) || 1) + 1;
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const payload = buildBulkSessionPayload({
        customer_name: appointment.customer_name,
        phone: appointment.phone,
        service_id: appointment.service_id,
        staff_member_id: appointment.staff_member_id,
        notes: appointment.notes || "",
        session_group_id: appointment.session_group_id,
        starting_session_number: startingNumber,
        session_total: appointment.session_total,
        sessions: rawSessions,
        notify_include_existing_sessions: notifyIncludeExistingSessions,
      });
      await api.post("/appointments/bulk-session", payload, {
        headers: { "Idempotency-Key": idempotencyKey },
      });
      toast.success(
        t
          ? t("sessionPlanner.sessionsPlanned", { count: sessions.length })
          : `${sessions.length} seans planlandı`
      );
      onDone && onDone();
      return true;
    } catch (e) {
      toast.error(
        formatApiError(e, t, t ? t("appointments.form.operationFailed") : "İşlem başarısız")
      );
      return false;
    } finally {
      setCreating(false);
    }
  }, [appointment, sessions, onDone, t, notifyIncludeExistingSessions]);

  return { creating, submit };
}
