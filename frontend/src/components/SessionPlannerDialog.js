import { useState, useEffect, useCallback } from "react";
import { CalendarDays, Clock, AlertTriangle, CheckCircle2, Info, Loader2, X, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const SessionPlannerDialog = ({ 
  open, 
  onOpenChange, 
  appointment,
  onSuccess 
}) => {
  const { t, i18n } = useTranslation();
  const isTR = i18n.language === 'tr';

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [allAvailable, setAllAvailable] = useState(false);
  const [workingHours, setWorkingHours] = useState(null);

  const remainingCount = appointment 
    ? (appointment.session_total || 0) - (appointment.session_number || 0) 
    : 0;

  useEffect(() => {
    if (open) {
      api.get("/settings").then(res => setWorkingHours(res.data?.working_hours || null)).catch(() => {});
    }
  }, [open]);

  useEffect(() => {
    if (open && appointment && remainingCount > 0) {
      generateDefaultSessions();
    }
  }, [open, appointment, workingHours]);

  const DAY_MAP = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];

  const isWorkingDay = (date) => {
    if (!workingHours) return true;
    const dayName = DAY_MAP[date.getDay()];
    const dayConfig = workingHours[dayName];
    return dayConfig && dayConfig.enabled;
  };

  const getWorkingTimeRange = (date) => {
    if (!workingHours) return null;
    const dayName = DAY_MAP[date.getDay()];
    const dayConfig = workingHours[dayName];
    if (!dayConfig || !dayConfig.enabled) return null;
    return { start: dayConfig.start || "09:00", end: dayConfig.end || "18:00" };
  };

  const clampTimeToWorkingHours = (time, date) => {
    const range = getWorkingTimeRange(date);
    if (!range) return time;
    if (time < range.start) return range.start;
    if (time >= range.end) return range.start;
    return time;
  };

  const generateDefaultSessions = () => {
    if (!appointment) return;
    const baseDate = new Date(appointment.appointment_date);
    const baseTime = appointment.appointment_time || "10:00";
    const newSessions = [];

    let dayOffset = 7;
    let generated = 0;
    let maxAttempts = remainingCount * 14; // safety limit

    while (generated < remainingCount && maxAttempts > 0) {
      maxAttempts--;
      const sessionDate = new Date(baseDate);
      sessionDate.setDate(sessionDate.getDate() + dayOffset);

      if (isWorkingDay(sessionDate)) {
        const dateStr = sessionDate.toISOString().split('T')[0];
        const adjustedTime = clampTimeToWorkingHours(baseTime, sessionDate);
        newSessions.push({
          date: dateStr,
          time: adjustedTime,
          available: null,
          alternatives: [],
          editing: false
        });
        generated++;
        dayOffset += 7; // next week same day
      } else {
        dayOffset++; // skip to next day
      }
    }
    setSessions(newSessions);
    setAllAvailable(false);
  };

  const checkAvailability = useCallback(async () => {
    if (!appointment || sessions.length === 0) return;
    setChecking(true);
    try {
      const slots = sessions.map(s => `${s.date}T${s.time}`);
      const response = await api.post("/availability/bulk-check", {
        service_id: appointment.service_id,
        staff_id: appointment.staff_member_id,
        slots
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
      toast.error(isTR ? "Müsaitlik kontrolü başarısız" : "Availability check failed");
    } finally {
      setChecking(false);
    }
  }, [appointment, sessions]);

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
      await api.post("/appointments/bulk-session", {
        customer_name: appointment.customer_name,
        phone: appointment.phone,
        service_id: appointment.service_id,
        staff_member_id: appointment.staff_member_id,
        notes: appointment.notes || "",
        session_group_id: appointment.session_group_id,
        starting_session_number: startingNumber,
        session_total: appointment.session_total,
        sessions: sessions.map(s => ({ date: s.date, time: s.time }))
      });
      toast.success(isTR 
        ? `${sessions.length} seans başarıyla planlandı` 
        : `${sessions.length} sessions planned successfully`
      );
      onOpenChange(false);
      onSuccess && onSuccess();
    } catch (error) {
      const detail = error.response?.data?.detail || (isTR ? "Seanslar oluşturulamadı" : "Failed to create sessions");
      toast.error(detail);
    } finally {
      setCreating(false);
    }
  };

  const hasConflicts = sessions.some(s => s.available === false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl sm:max-w-[600px] max-h-[80vh] overflow-y-auto overflow-x-hidden" style={{ paddingBottom: 'max(1.5rem, calc(env(safe-area-inset-bottom, 0px) + 5rem))' }}>
        <DialogHeader>
          <DialogTitle className="text-xl font-black text-zinc-900">
            {isTR ? 'Kalan Seansları Planla' : 'Plan Remaining Sessions'}
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

        {/* Bilgi Kutusu */}
        <div className="p-4 backdrop-blur-md bg-zinc-900/5 border border-zinc-200/60 rounded-xl flex items-start gap-3">
          <Info className="w-5 h-5 text-zinc-700 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-zinc-700">
            <p className="font-bold mb-1">
              {isTR ? 'Nasıl Çalışır?' : 'How It Works?'}
            </p>
            <p className="leading-relaxed">
              {isTR 
                ? 'Tarihler otomatik oluşturuldu (haftalık). Çakışma varsa sarı uyarı ve alternatif saatler gösterilir. Tüm seanslar müsait olana kadar "Hepsini Oluştur" butonu aktif olmaz.'
                : 'Dates are auto-generated (weekly). Conflicts show yellow warnings with alternative times. "Create All" button stays disabled until all sessions are available.'}
            </p>
          </div>
        </div>

        {/* Seans Listesi */}
        <div className="space-y-3 mt-2">
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
                <Input
                  type="time"
                  value={session.time}
                  onChange={(e) => updateSession(idx, 'time', e.target.value)}
                  className="h-8 text-sm backdrop-blur-md bg-white/60 border-white/40 rounded-lg font-medium w-[5.5rem]"
                />
              </div>

              {/* Başka personele atandı bilgisi */}
              {session.suggested_staff_name && session.available === true && (
                <div className="mt-1.5 flex items-center gap-1.5 pl-1">
                  <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-semibold">
                    → {session.suggested_staff_name}
                  </span>
                  <span className="text-[10px] text-zinc-400">
                    {isTR ? '(orijinal personel dolu)' : '(original staff busy)'}
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
                        ⚠ {isTR ? `Çalışma saatleri: ${range.start} - ${range.end}` : `Working hours: ${range.start} - ${range.end}`}
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
                    {isTR ? 'Bu saatte çakışma var!' : 'Conflict at this time!'}
                  </p>
                  {session.alternatives.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-xs text-zinc-500">{isTR ? 'Alternatifler:' : 'Alternatives:'}</span>
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

        <DialogFooter className="border-t border-white/30 pt-4 flex-col sm:flex-row gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={checkAvailability}
            disabled={checking || creating}
            className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold"
          >
            {checking ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isTR ? 'Kontrol ediliyor...' : 'Checking...'}</>
            ) : (
              isTR ? 'Müsaitlik Kontrol Et' : 'Check Availability'
            )}
          </Button>
          <Button
            type="button"
            onClick={handleCreate}
            disabled={!allAvailable || creating || checking}
            className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg disabled:opacity-50"
          >
            {creating ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isTR ? 'Oluşturuluyor...' : 'Creating...'}</>
            ) : (
              isTR ? `Hepsini Oluştur (${sessions.length})` : `Create All (${sessions.length})`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SessionPlannerDialog;
