import { useState, useEffect, useCallback, useMemo } from "react";
import { CalendarDays, Clock, AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

const SessionPlannerDialog = ({ 
  open, 
  onOpenChange, 
  appointment,
  onSuccess 
}) => {
  const { t, i18n } = useTranslation();
  const { userRole, canViewAll } = useAuth();

  const [sessions, setSessions] = useState([]);
  const [waveLoading, setWaveLoading] = useState(false);
  const [slotRefreshToken, setSlotRefreshToken] = useState(0);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [allAvailable, setAllAvailable] = useState(false);
  const [plannerSettings, setPlannerSettings] = useState(null);
  const [allStaff, setAllStaff] = useState([]);

  const remainingCount = appointment 
    ? (appointment.session_total || 0) - (appointment.session_number || 0) 
    : 0;

  useEffect(() => {
    if (open) {
      api
        .get("/settings")
        .then((res) => setPlannerSettings(res.data || null))
        .catch(() => {});
      api
        .get("/users")
        .then((res) => setAllStaff(res.data || []))
        .catch(() => {});
    }
  }, [open]);

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

  const loadDefaultSessions = useCallback(async () => {
    if (!appointment || remainingCount <= 0) return;
    setWaveLoading(true);
    const fallback = buildRemainingSlotsFromAppointment(appointment, remainingCount, plannerSettings, {
      intervalMinutes: plannerSettings?.appointment_interval || 30,
      serviceDurationMinutes: appointment.service_duration ?? undefined,
    });
    const mapRow = (s, i) => ({
      date: s.date || fallback[i]?.date || "",
      time: s.time || fallback[i]?.time || "",
      staff_member_id: s.staff_member_id
        ? String(s.staff_member_id)
        : (appointment.staff_member_id && String(appointment.staff_member_id)) || "",
      unplanned: !!s.unplanned,
      available: null,
      alternatives: [],
      editing: false,
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
      setSessions(fallback.map((s, i) => mapRow(s, i)));
    } finally {
      setWaveLoading(false);
      setAllAvailable(false);
    }
  }, [appointment, remainingCount, plannerSettings]);

  useEffect(() => {
    if (open && appointment && remainingCount > 0) {
      loadDefaultSessions();
    }
  }, [open, appointment, remainingCount, plannerSettings, loadDefaultSessions]);

  const getWorkingTimeRange = useCallback(
    (date) => {
      const wh = normalizeWorkingHours(plannerSettings) || plannerSettings?.working_hours || plannerSettings?.business_hours;
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
      const slots = sessions.map(s => `${s.date}T${s.time}`);
      const staff_ids = sessions.map((s) => {
        const v = (s.staff_member_id || "").trim();
        return v || null;
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
        editing: false
      }));
      setSessions(updated);
      setAllAvailable(updated.every(s => s.available === true));
    } catch (error) {
      toast.error(t("sessionPlanner.availabilityFailed"));
    } finally {
      setChecking(false);
    }
  }, [appointment, sessions, t]);

  useEffect(() => {
    if (open && sessions.length > 0 && sessions[0].available === null) {
      const timer = setTimeout(() => checkAvailability(), 300);
      return () => clearTimeout(timer);
    }
  }, [sessions.length, open]);

  const updateSession = (idx, field, value) => {
    setSessions(prev => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value, available: null };
      return updated;
    });
    setAllAvailable(false);
  };

  const applyAlternative = (idx, altTime) => {
    setSessions(prev => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], time: altTime, available: null, alternatives: [] };
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
      onOpenChange(false);
      onSuccess && onSuccess();
    } catch (error) {
      toast.error(formatApiError(error, t, t("appointments.form.operationFailed")));
    } finally {
      setCreating(false);
    }
  };

  const hasConflicts = sessions.some(s => s.available === false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl sm:max-w-3xl max-h-[85vh] overflow-y-auto overflow-x-hidden" style={{ paddingBottom: 'max(1.5rem, calc(env(safe-area-inset-bottom, 0px) + 5rem))' }}>
        <DialogHeader>
          <DialogTitle className="text-xl font-black text-zinc-900">
            {t("sessionPlanner.title")}
          </DialogTitle>
          <DialogDescription className="text-zinc-600 font-medium">
            {appointment?.customer_name} — {appointment?.service_name}
            {appointment?.session_number && appointment?.session_total && (
              <span className="ml-2 text-[10px] bg-zinc-800 text-white px-1.5 py-0.5 rounded font-semibold">
                {appointment.session_number}/{appointment.session_total}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col lg:flex-row gap-4 mt-2">
          <aside className="lg:w-[min(100%,280px)] shrink-0 rounded-xl border border-zinc-200 bg-zinc-50/90 p-4">
            <p className="text-xs font-bold text-zinc-500 uppercase tracking-wide mb-2">
              {t("session.package")}
            </p>
            <p className="font-bold text-zinc-900">{appointment?.customer_name}</p>
            <p className="text-sm text-zinc-600 mt-1">{appointment?.service_name}</p>
            <div className="mt-4 p-3 backdrop-blur-md bg-white/80 border border-zinc-200/60 rounded-lg flex items-start gap-2">
              <Info className="w-4 h-4 text-zinc-600 shrink-0 mt-0.5" />
              <div className="text-xs text-zinc-700">
                <p className="font-bold mb-1">{t("sessionPlanner.howItWorksTitle")}</p>
                <p className="leading-relaxed">{t("sessionPlanner.howItWorksBody")}</p>
              </div>
            </div>
          </aside>

          <div className="flex-1 min-w-0 space-y-3">
          {waveLoading && (
            <p className="text-xs text-zinc-500 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("sessionPlanner.waveLoading")}
            </p>
          )}
          {sessions.map((session, idx) => (
            <div 
              key={idx} 
              className={`p-3 rounded-xl border transition-all ${
                session.available === true 
                  ? 'backdrop-blur-md bg-green-50/50 border-green-200' 
                  : session.available === false 
                    ? 'backdrop-blur-md bg-amber-50/50 border-amber-300' 
                    : 'backdrop-blur-md bg-white/50 border-white/30'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="text-xs font-black text-zinc-500">
                  #{(appointment?.session_number || 1) + idx + 1}
                </span>
                <div className="flex-shrink-0">
                  {session.available === true && (
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                  )}
                  {session.available === false && (
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                  )}
                  {session.available === null && checking && (
                    <Loader2 className="w-4 h-4 text-zinc-400 animate-spin" />
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <CalendarDays className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                <Input
                  type="date"
                  value={session.date}
                  onChange={(e) => updateSession(idx, 'date', e.target.value)}
                  className="h-8 text-sm backdrop-blur-md bg-white/60 border-white/40 rounded-lg font-medium flex-1"
                />
                <Clock className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <PlannerTimeSlotGrid
                    serviceId={appointment.service_id}
                    dateStr={session.date}
                    staffId={(session.staff_member_id || "").trim() || appointment.staff_member_id}
                    excludeAppointmentId={appointment.id}
                    value={session.time}
                    onChange={(t) => updateSession(idx, "time", t)}
                    reloadToken={slotRefreshToken}
                    disabled={waveLoading}
                  />
                </div>
              </div>
              {session.unplanned && (
                <p className="text-[10px] text-amber-700 mt-1 font-medium">
                  {t("sessionPlanner.unplannedHint")}
                </p>
              )}

              {showStaffPicker && (
                <div className="mt-2 w-full min-w-0">
                  <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide block mb-1">
                    {t("sessionPlanner.staffPerSession")}
                  </label>
                  <Select
                    value={(session.staff_member_id || "").trim() || "__default__"}
                    onValueChange={(v) =>
                      updateSession(idx, "staff_member_id", v === "__default__" ? "" : v)
                    }
                  >
                    <SelectTrigger className="h-9 w-full rounded-lg border-zinc-200 text-sm bg-white/80">
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

              {/* Başka personele atandı bilgisi */}
              {session.suggested_staff_name && session.available === true && (
                <div className="mt-1.5 flex items-center gap-1.5 pl-1">
                  <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-semibold">
                    → {session.suggested_staff_name}
                  </span>
                  <span className="text-[10px] text-zinc-400">
                    {t("sessionPlanner.staffReassigned")}
                  </span>
                </div>
              )}

              {/* Çalışma saati dışı uyarısı */}
              {(() => {
                const range = getWorkingTimeRange(new Date(session.date + 'T00:00:00'));
                if (range && (session.time < range.start || session.time >= range.end)) {
                  return (
                    <div className="mt-1.5 flex items-center gap-1.5 pl-1">
                      <span className="text-[10px] bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">
                        ⚠{" "}
                        {t("sessionPlanner.workingHoursWarn", {
                          start: range.start,
                          end: range.end,
                        })}
                      </span>
                    </div>
                  );
                }
                return null;
              })()}

              {/* Çakışma uyarısı + alternatifler */}
              {session.available === false && (
                <div className="mt-2 pl-8">
                  <p className="text-xs font-bold text-amber-700 mb-1">
                    {t("sessionPlanner.conflictTitle")}
                  </p>
                  {session.alternatives.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-xs text-zinc-500">{t("sessionPlanner.alternatives")}</span>
                      {session.alternatives.map((alt, aIdx) => (
                        <button
                          key={aIdx}
                          type="button"
                          onClick={() => applyAlternative(idx, alt)}
                          className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-bold hover:bg-blue-200 transition-colors"
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
        </div>

        <DialogFooter className="border-t border-white/30 pt-4 flex-col sm:flex-row gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={checkAvailability}
            disabled={checking || creating}
            className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold"
          >
            {checking ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t("sessionPlanner.checking")}
              </>
            ) : (
              t("sessionPlanner.checkAvailability")
            )}
          </Button>
          <Button
            type="button"
            onClick={handleCreate}
            disabled={!allAvailable || creating || checking}
            className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg disabled:opacity-50"
          >
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t("sessionPlanner.creating")}
              </>
            ) : (
              t("sessionPlanner.createAll", { count: sessions.length })
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SessionPlannerDialog;
