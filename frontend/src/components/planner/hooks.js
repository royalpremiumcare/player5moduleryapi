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
export function usePlanSuggestion({
  appointment,
  open,
  plannerSettings,
  remainingCount,
  mode = "remainder",
  packageDraft = null,
}) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  // A monotonic counter bumped every time we populate sessions from scratch;
  // effects depending on it can reliably re-fire even when length is unchanged.
  const [reloadTick, setReloadTick] = useState(0);

  // Source object for staff fallback: appointment (remainder) or packageDraft
  // (newPackage). Used inside mapRow for default staff_member_id.
  const sourceStaff = mode === "newPackage"
    ? packageDraft?.staff_member_id
    : appointment?.staff_member_id;

  const mapRow = useCallback(
    (s, i, fallback = []) => ({
      date: s.date || fallback[i]?.date || "",
      time: s.time || fallback[i]?.time || "",
      staff_member_id: s.staff_member_id
        ? String(s.staff_member_id)
        : (sourceStaff && String(sourceStaff)) || "",
      unplanned: !!s.unplanned,
      available: null,
      alternatives: [],
      suggested_staff: null,
      suggested_staff_name: null,
    }),
    [sourceStaff]
  );

  const load = useCallback(async () => {
    const isNewPackage = mode === "newPackage";

    if (isNewPackage) {
      if (!packageDraft || !packageDraft.session_total || packageDraft.session_total < 1) {
        setSessions([]);
        return;
      }
    } else if (!appointment || remainingCount <= 0) {
      setSessions([]);
      return;
    }

    setLoading(true);

    // Plan M2: newPackage mode için 1. seans draft'tan, 2..N wave-plan'dan.
    // wave-plan'a remaining_count = N - 1 gönderilir.
    const sessionTotal = isNewPackage ? packageDraft.session_total : null;
    const waveRemainingCount = isNewPackage
      ? Math.max(0, sessionTotal - 1)
      : remainingCount;

    const wavePayload = isNewPackage
      ? {
          service_id: packageDraft.service_id,
          first_session_date: packageDraft.first_session_date,
          first_session_time: packageDraft.first_session_time,
          remaining_count: waveRemainingCount,
          staff_member_id: packageDraft.staff_member_id || undefined,
        }
      : {
          service_id: appointment.service_id,
          first_session_date: normalizeAppointmentDateStr(appointment.appointment_date),
          first_session_time: appointment.appointment_time || "10:00",
          remaining_count: waveRemainingCount,
          staff_member_id: appointment.staff_member_id || undefined,
        };

    // Fallback (network hata durumunda): newPackage için sadece 1. seans
    // draft'ı içeren tek-elemanlı liste; remainder için mevcut helper.
    const fallback = isNewPackage
      ? []
      : buildRemainingSlotsFromAppointment(appointment, remainingCount, plannerSettings, {
          intervalMinutes: plannerSettings?.appointment_interval || 30,
          serviceDurationMinutes: appointment.service_duration ?? undefined,
        });

    try {
      // Sadece N>1 ise wave-plan çağrılır; N=1 (sadece 1. seans) durumunda
      // boş cevap döner ve aşağıda firstRow tek başına eklenir.
      let waveRows = [];
      if (waveRemainingCount > 0) {
        const data = await fetchWavePlanSessions(api, wavePayload);
        waveRows = (data?.sessions || []).map((s, i) => mapRow(s, i, fallback));
      }

      let rows;
      if (isNewPackage) {
        // 1. seans draft'tan prepend edilir; planner'da kullanıcı 1..N
        // gösterimi/düzenlemesi yapabilir. Atomic create için tüm N seans
        // /bulk-package'a gönderilir (useOptimisticPlan handle ediyor).
        //
        // Sorun 5 fix: kullanıcı personel seçmemişse, wave-plan'dan dönen
        // 2. seansın staff'ını 1. seansa da uygula. Backend admin fallback'i
        // tek admin'li org'larda 2..N seanslarda admin atıyor; bunu 1. seansa
        // da yansıt → planner UI'da 1. seansda admin adı boş kalmıyor.
        const firstStaff = packageDraft.staff_member_id
          ? String(packageDraft.staff_member_id)
          : (waveRows[0] && waveRows[0].staff_member_id) || "";
        const firstRow = {
          date: packageDraft.first_session_date,
          time: packageDraft.first_session_time,
          staff_member_id: firstStaff,
          unplanned: false,
          available: null,
          alternatives: [],
          suggested_staff: null,
          suggested_staff_name: null,
        };
        rows = [firstRow, ...waveRows];
      } else {
        rows = waveRows.length ? waveRows : fallback.map((s, i) => mapRow(s, i, fallback));
      }
      setSessions(rows);
    } catch (e) {
      // Silent fallback — network hiccup shouldn't block the user.
      console.warn("[planner] wave-plan failed, falling back", e);
      if (isNewPackage) {
        // newPackage'da en azından 1. seansı göster; kullanıcı 2..N için
        // tarih/saat girene kadar Submit disabled kalır.
        setSessions([
          {
            date: packageDraft.first_session_date,
            time: packageDraft.first_session_time,
            staff_member_id: packageDraft.staff_member_id
              ? String(packageDraft.staff_member_id)
              : "",
            unplanned: false,
            available: null,
            alternatives: [],
            suggested_staff: null,
            suggested_staff_name: null,
          },
        ]);
      } else {
        setSessions(fallback.map((s, i) => mapRow(s, i, fallback)));
      }
    } finally {
      setLoading(false);
      setReloadTick((x) => x + 1);
    }
  }, [appointment, remainingCount, plannerSettings, mapRow, mode, packageDraft]);

  const check = useCallback(async () => {
    if (sessions.length === 0) return;
    // newPackage modunda appointment objesi yok; service_id/staff_id'yi
    // packageDraft'tan alıyoruz. Aksi halde mevcut appointment'tan.
    const isNewPackage = mode === "newPackage";
    const serviceId = isNewPackage ? packageDraft?.service_id : appointment?.service_id;
    const fallbackStaffId = isNewPackage ? packageDraft?.staff_member_id : appointment?.staff_member_id;
    if (!serviceId) return;
    setChecking(true);
    try {
      const slots = sessions.map((s) => `${s.date}T${s.time}`);
      const staff_ids = sessions.map((s) => (s.staff_member_id || "").trim() || null);
      const res = await api.post("/availability/bulk-check", {
        service_id: serviceId,
        staff_id: fallbackStaffId,
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
  }, [appointment, sessions, mode, packageDraft]);

  // Auto-load on open + auto-check after first load.
  // newPackage mode'da appointment olmayabilir; packageDraft varsa load tetiklenir.
  useEffect(() => {
    if (!open) return;
    if (mode === "newPackage") {
      if (packageDraft && (packageDraft.session_total || 0) > 0) {
        load();
      }
    } else if (appointment && remainingCount > 0) {
      load();
    }
  }, [open, appointment, remainingCount, load, mode, packageDraft]);

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
 * Commits the planned sessions via the appropriate endpoint with optimistic
 * UI feedback and idempotent retries.
 *
 * `mode`:
 *   - "remainder" (default, BC): kalanları planla akışı. POST /bulk-session
 *     ile starting_session_number = appointment.session_number + 1.
 *     Dashboard / Calendar / SessionsHub / Customers'tan çağrılır.
 *   - "newPackage" (Plan M2): yeni paket akışı. POST /bulk-package ile
 *     atomik 1..N seans. AppointmentFormWizard step 4'ten çağrılır.
 *     packageDraft prop'u ile customer/phone/service vb. parametre alır;
 *     appointment objesi olmayabilir.
 *
 * `notifyIncludeExistingSessions` — sadece "remainder" mode için anlamlı.
 * "newPackage" mode backend tarafında zaten 1..N tüm seansları
 * listeler (notify_include_existing_sessions=True default).
 */
export function useOptimisticPlan({
  appointment,
  sessions,
  onDone,
  t,
  notifyIncludeExistingSessions = false,
  mode = "remainder",
  packageDraft = null,
}) {
  const [creating, setCreating] = useState(false);

  const submit = useCallback(async () => {
    if (mode === "newPackage" ? !packageDraft : !appointment) return;
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

      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      if (mode === "newPackage") {
        // Plan M2: yeni atomic endpoint. session_group_id frontend-generated
        // (idempotency için zorunlu — packageDraft.session_group_id).
        const draft = packageDraft || {};
        const payload = {
          customer_name: draft.customer_name,
          phone: draft.phone,
          service_id: draft.service_id,
          notes: draft.notes || "",
          session_group_id: draft.session_group_id,
          session_total: draft.session_total || sessions.length,
          sessions: rawSessions,
        };
        if (draft.staff_member_id) {
          payload.staff_member_id = draft.staff_member_id;
        }
        await api.post("/appointments/bulk-package", payload, {
          headers: { "Idempotency-Key": idempotencyKey },
        });
      } else {
        // BC: kalanları planla — POST /bulk-session (mevcut, dokunulmadı).
        const startingNumber = (Number(appointment.session_number) || 1) + 1;
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
      }

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
  }, [appointment, sessions, onDone, t, notifyIncludeExistingSessions, mode, packageDraft]);

  return { creating, submit };
}
