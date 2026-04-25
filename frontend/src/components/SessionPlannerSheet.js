import { useState, useEffect, useCallback, useMemo } from "react";
import { X, Clock, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  buildRemainingSlotsFromAppointment,
  buildBulkSessionPayload,
  validateSessionSchedule,
  normalizeWorkingHours,
  normalizeAppointmentDateStr,
  fetchWavePlanSessions,
} from "../lib/sessionScheduling";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "../context/AuthContext";
import PlannerTimeSlotGrid from "./PlannerTimeSlotGrid";

/**
 * Tam ekran sheet — Wizard Adım 4 ve Sessions Hub ile paylaşılır.
 */
const SessionPlannerSheet = ({
  appointment,
  onComplete,
  showWizardStepBadge,
  /** Wizard: otomatik/manuel ile aynı üretilmiş satırlar; null/undefined = yerel üret */
  initialSessionRows,
}) => {
  const { t } = useTranslation();
  const { userRole, canViewAll } = useAuth();

  const [sessions, setSessions] = useState([]);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [waveLoading, setWaveLoading] = useState(false);
  const [slotRefreshToken, setSlotRefreshToken] = useState(0);
  const [allAvailable, setAllAvailable] = useState(false);
  const [plannerSettings, setPlannerSettings] = useState(null);
  const [allStaff, setAllStaff] = useState([]);

  const remainingCount = appointment
    ? (appointment.session_total || 0) - (appointment.session_number || 0)
    : 0;

  const planned = appointment?.session_number || 1;
  const total = appointment?.session_total || 0;

  useEffect(() => {
    api
      .get("/settings")
      .then((res) => setPlannerSettings(res.data || null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api
      .get("/users")
      .then((res) => setAllStaff(res.data || []))
      .catch(() => {});
  }, []);

  const qualifiedStaff = useMemo(() => {
    if (!appointment?.service_id || !plannerSettings) return [];
    let q = (allStaff || []).filter((s) =>
      (s.permitted_service_ids || []).includes(appointment.service_id)
    );
    if (!plannerSettings.admin_provides_service) {
      q = q.filter((s) => s.role !== "admin");
    }
    return q;
  }, [appointment?.service_id, plannerSettings, allStaff]);

  const showStaffPicker =
    (userRole === "admin" || userRole === "superadmin" || canViewAll) &&
    qualifiedStaff.length > 0;

  const loadWaveDefaultSessions = useCallback(async () => {
    if (!appointment || remainingCount <= 0) return;
    setWaveLoading(true);
    const fallback = buildRemainingSlotsFromAppointment(appointment, remainingCount, plannerSettings, {
      intervalMinutes: plannerSettings?.appointment_interval || 30,
      serviceDurationMinutes: appointment.service_duration ?? undefined,
    });
    const mapRow = (s, i) => ({
      date: s.date || fallback[i]?.date || "",
      time: s.time || fallback[i]?.time || "",
      staff_member_id: (s.staff_member_id && String(s.staff_member_id)) || (appointment.staff_member_id && String(appointment.staff_member_id)) || "",
      unplanned: !!s.unplanned,
      available: null,
      alternatives: [],
    });
    try {
      const data = await fetchWavePlanSessions(api, {
        service_id: appointment.service_id,
        first_session_date: normalizeAppointmentDateStr(appointment.appointment_date),
        first_session_time: appointment.appointment_time || "10:00",
        remaining_count: remainingCount,
        staff_member_id: appointment.staff_member_id || undefined,
      });
      const rows = (data.sessions || []).map((s, i) => mapRow(s, i));
      setSessions(
        rows.length
          ? rows
          : fallback.map((s, i) => mapRow({ date: s.date, time: s.time }, i))
      );
    } catch (e) {
      console.error(e);
      setSessions(fallback.map((s, i) => mapRow({ date: s.date, time: s.time }, i)));
    } finally {
      setWaveLoading(false);
      setAllAvailable(false);
    }
  }, [appointment, remainingCount, plannerSettings]);

  useEffect(() => {
    if (!appointment || remainingCount <= 0) return;
    if (Array.isArray(initialSessionRows) && initialSessionRows.length > 0) {
      setSessions(
        initialSessionRows.map((s) => ({
          date: s.date,
          time: s.time,
          staff_member_id: (s.staff_member_id && String(s.staff_member_id)) || "",
          available: s.available ?? null,
          alternatives: s.alternatives ?? [],
          unplanned: !!s.unplanned,
        }))
      );
      setAllAvailable(false);
      return;
    }
    loadWaveDefaultSessions();
  }, [
    appointment,
    appointment?.id,
    remainingCount,
    plannerSettings,
    loadWaveDefaultSessions,
    initialSessionRows,
  ]);

  const getWorkingTimeRange = useCallback(
    (date) => {
      const wh =
        normalizeWorkingHours(plannerSettings) ||
        plannerSettings?.working_hours ||
        plannerSettings?.business_hours;
      if (!wh) return null;
      const DAY_MAP = [
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
      ];
      const dayName = DAY_MAP[date.getDay()];
      const dayConfig = wh[dayName];
      if (!dayConfig || !dayConfig.enabled) return null;
      return { start: dayConfig.start || "09:00", end: dayConfig.end || "18:00" };
    },
    [plannerSettings]
  );

  const checkAvailability = useCallback(async () => {
    if (!appointment || sessions.length === 0) return;
    setChecking(true);
    try {
      const slots = sessions.map((s) => `${s.date}T${s.time}`);
      const staff_ids = sessions.map((s) => {
        const explicit = (s.staff_member_id || "").trim();
        if (explicit) return explicit;
        return null;
      });
      const response = await api.post("/availability/bulk-check", {
        service_id: appointment.service_id,
        staff_id: appointment.staff_member_id,
        slots,
        staff_ids,
      });
      const results = response.data;
      const updated = sessions.map((s, idx) => ({
        ...s,
        available: results[idx]?.available ?? null,
        alternatives: results[idx]?.alternatives || [],
        suggested_staff: results[idx]?.suggested_staff || null,
        suggested_staff_name: results[idx]?.suggested_staff_name || null,
      }));
      setSessions(updated);
      setAllAvailable(updated.every((s) => s.available === true));
    } catch (error) {
      toast.error(t("sessionPlanner.availabilityFailed"));
    } finally {
      setChecking(false);
    }
  }, [appointment, sessions, t]);

  useEffect(() => {
    if (sessions.length > 0 && sessions[0].available === null) {
      const timer = setTimeout(() => checkAvailability(), 300);
      return () => clearTimeout(timer);
    }
  }, [sessions.length]);

  const updateSession = (idx, field, value) => {
    setSessions((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value, available: null };
      return updated;
    });
    setAllAvailable(false);
  };

  const applyAlternative = (idx, altTime) => {
    setSessions((prev) => {
      const updated = [...prev];
      updated[idx] = {
        ...updated[idx],
        time: altTime,
        available: null,
        alternatives: [],
      };
      return updated;
    });
    setAllAvailable(false);
  };

  const handleCreate = async () => {
    if (!allAvailable || !appointment) return;
    setCreating(true);
    try {
      const startingNumber = (appointment.session_number || 1) + 1;
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const rawSessions = sessions.map((s) => {
        const row = { date: s.date, time: s.time };
        const st = (s.staff_member_id || "").trim();
        if (st) row.staff_member_id = st;
        return row;
      });
      const v = validateSessionSchedule(rawSessions);
      if (!v.ok) {
        toast.error(t("sessionPlanner.validationFailed"));
        return;
      }
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
      });
      await api.post("/appointments/bulk-session", payload, {
        headers: { "Idempotency-Key": idempotencyKey },
      });
      toast.success(t("sessionPlanner.sessionsPlanned", { count: sessions.length }));
      setSlotRefreshToken((x) => x + 1);
      if (onComplete) onComplete();
    } catch (error) {
      toast.error(formatApiError(error, t, t("appointments.form.operationFailed")));
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    if (onComplete) onComplete();
  };

  if (!appointment || remainingCount <= 0) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[70] flex flex-col bg-zinc-950/45 backdrop-blur-[2px]">
      <div className="flex flex-col flex-1 w-full max-w-lg mx-auto bg-white min-h-0 shadow-2xl rounded-t-2xl sm:rounded-2xl sm:my-auto sm:max-h-[min(100dvh,920px)] border border-zinc-100">
        <header className="flex items-start justify-between gap-3 px-5 pt-6 pb-4 border-b border-zinc-100/80 shrink-0 bg-zinc-50/40">
          <div className="min-w-0">
            {showWizardStepBadge && (
              <p className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-1">
                {t("sessionPlanner.wizardStepBadge")}
              </p>
            )}
            <h1 className="text-lg font-bold text-zinc-900 leading-tight">
              {t("sessionPlanner.sheetTitle")}
            </h1>
            <p className="text-sm text-zinc-600 mt-1 truncate">
              {appointment.customer_name} · {appointment.service_name} ·{" "}
              {t("sessionPlanner.completionLine", { planned, total })}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-2 rounded-xl border border-zinc-200 text-zinc-700 hover:bg-zinc-50 shrink-0"
            aria-label={t("common.close")}
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        <div className="px-5 py-4 border-b border-zinc-100 flex gap-6 text-sm shrink-0">
          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
              {t("sessionPlanner.summaryTotal")}
            </p>
            <p className="text-lg font-bold text-zinc-900">{total}</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
              {t("sessionPlanner.summaryPlanned")}
            </p>
            <p className="text-lg font-bold text-zinc-900">{planned}</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
              {t("sessionPlanner.summaryRemaining")}
            </p>
            <p className="text-lg font-bold text-zinc-900">{remainingCount}</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 min-h-0">
          <p className="text-xs text-zinc-500 leading-relaxed max-w-prose">
            {t("sessionPlanner.howItWorksShort")}
          </p>

          {waveLoading && (
            <p className="text-xs text-zinc-500 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("sessionPlanner.waveLoading")}
            </p>
          )}

          {sessions.map((session, idx) => (
            <div
              key={idx}
              className={`rounded-xl border p-4 ${
                session.available === true
                  ? "border-emerald-200/80 bg-emerald-50/40"
                  : session.available === false
                    ? "border-red-200/80 bg-red-50/40"
                    : "border-zinc-100 bg-zinc-50/30"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-bold text-zinc-600">
                  {t("sessionPlanner.sessionRow", { num: planned + idx + 1 })}
                </span>
                <div className="shrink-0">
                  {session.available === true && (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  )}
                  {session.available === false && (
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                  )}
                  {session.available === null && checking && (
                    <Loader2 className="w-4 h-4 text-zinc-400 animate-spin" />
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Input
                  type="date"
                  value={session.date}
                  onChange={(e) => updateSession(idx, "date", e.target.value)}
                  className="h-10 text-sm w-full rounded-lg border-zinc-200"
                />
                <div className="flex items-start gap-2 min-w-0">
                  <Clock className="w-4 h-4 text-zinc-400 shrink-0 mt-2" />
                  <PlannerTimeSlotGrid
                    serviceId={appointment.service_id}
                    dateStr={session.date}
                    staffId={(session.staff_member_id || "").trim() || appointment.staff_member_id}
                    excludeAppointmentId={appointment.id}
                    value={session.time}
                    onChange={(t) => updateSession(idx, "time", t)}
                    reloadToken={slotRefreshToken}
                    disabled={waveLoading}
                    className="flex-1 min-w-0"
                  />
                </div>
              </div>

              {session.unplanned && (
                <p className="text-[11px] text-amber-700 mt-1 font-medium">
                  {t("sessionPlanner.unplannedHint")}
                </p>
              )}

              {showStaffPicker && (
                <div className="mt-2 w-full min-w-0">
                  <label className="text-[11px] font-bold text-zinc-500 uppercase tracking-wide block mb-1">
                    {t("sessionPlanner.staffPerSession")}
                  </label>
                  <Select
                    value={(session.staff_member_id || "").trim() || "__default__"}
                    onValueChange={(v) =>
                      updateSession(idx, "staff_member_id", v === "__default__" ? "" : v)
                    }
                  >
                    <SelectTrigger className="h-10 w-full rounded-lg border-zinc-200 text-sm bg-white">
                      <SelectValue placeholder={t("appointments.form.selectStaff")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">{t("sessionPlanner.staffSameAsPackage")}</SelectItem>
                      {qualifiedStaff.map((u) => (
                        <SelectItem key={u.username} value={u.username}>
                          {u.full_name || u.username}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {(() => {
                const range = getWorkingTimeRange(new Date(session.date + "T12:00:00"));
                if (range && (session.time < range.start || session.time >= range.end)) {
                  return (
                    <p className="text-[11px] text-amber-700 mt-2">
                      {t("sessionPlanner.workingHoursWarn", {
                        start: range.start,
                        end: range.end,
                      })}
                    </p>
                  );
                }
                return null;
              })()}

              {session.available === false && (
                <div className="mt-2">
                  <p className="text-xs text-red-600 font-semibold">{t("sessionPlanner.conflictTitle")}</p>
                  {session.suggested_staff_name && (
                    <p className="text-[11px] text-zinc-600 mt-1">
                      {t("sessionPlanner.suggestedStaffLine", { name: session.suggested_staff_name })}
                    </p>
                  )}
                  {session.alternatives?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {session.alternatives.map((alt, aIdx) => (
                        <button
                          key={aIdx}
                          type="button"
                          onClick={() => applyAlternative(idx, alt)}
                          className="text-xs px-2 py-0.5 rounded-full border border-zinc-200 bg-white text-zinc-800 font-semibold hover:bg-zinc-50"
                        >
                          {alt}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        <footer className="border-t border-zinc-100 px-5 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shrink-0 bg-white space-y-3">
          <Button
            type="button"
            className="w-full h-12 bg-zinc-900 hover:bg-black text-white font-bold rounded-xl disabled:opacity-50 shadow-md"
            onClick={handleCreate}
            disabled={!allAvailable || creating || checking || sessions.length === 0}
          >
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin inline" /> {t("sessionPlanner.creating")}
              </>
            ) : (
              t("sessionPlanner.saveSessions", { count: sessions.length })
            )}
          </Button>
          <div className="flex items-center justify-between gap-3 text-xs text-zinc-500">
            <span>{t("sessionPlanner.editingCount", { count: sessions.length })}</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-zinc-700 h-9 px-2 shrink-0"
              onClick={checkAvailability}
              disabled={checking || creating}
            >
              {checking ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t("sessionPlanner.checking")}
                </>
              ) : (
                t("sessionPlanner.checkAvailability")
              )}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default SessionPlannerSheet;
