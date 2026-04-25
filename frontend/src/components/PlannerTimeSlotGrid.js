import React, { useEffect, useState, useMemo, useCallback } from "react";
import api from "../api/api";
import { cn } from "@/lib/utils";

/**
 * Mesai içi tüm slotları gösterir; dolu olanlar gri ve disabled (randevu formu ile aynı UX).
 */
const PlannerTimeSlotGrid = ({
  serviceId,
  dateStr,
  staffId,
  excludeAppointmentId,
  value,
  onChange,
  disabled,
  className,
  reloadToken = 0,
}) => {
  const [availableSlots, setAvailableSlots] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [allSlots, setAllSlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!serviceId || !dateStr) {
      setAvailableSlots([]);
      setBusySlots([]);
      setAllSlots([]);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const params = { service_id: serviceId, date: dateStr };
      if (staffId && String(staffId).trim()) params.staff_id = String(staffId).trim();
      if (excludeAppointmentId) params.exclude_appointment_id = excludeAppointmentId;

      const res = await api.get("/availability", { params });
      const d = res.data || {};
      const av = d.available_slots || [];
      const bs = d.busy_slots || [];
      const all = d.all_slots && d.all_slots.length > 0 ? d.all_slots : [...new Set([...av, ...bs])].sort();
      setAvailableSlots(av);
      setBusySlots(bs);
      setAllSlots(all.sort());
    } catch (e) {
      console.error(e);
      setError(true);
      setAvailableSlots([]);
      setBusySlots([]);
      setAllSlots([]);
    } finally {
      setLoading(false);
    }
  }, [serviceId, dateStr, staffId, excludeAppointmentId]);

  useEffect(() => {
    load();
  }, [load, reloadToken]);

  const busySet = useMemo(() => new Set(busySlots), [busySlots]);
  const availableSet = useMemo(() => new Set(availableSlots), [availableSlots]);

  if (!serviceId || !dateStr) return null;

  if (loading && allSlots.length === 0) {
    return (
      <div className={cn("text-xs text-zinc-400 py-2", className)}>…</div>
    );
  }

  if (error || allSlots.length === 0) {
    return (
      <input
        type="time"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          "h-9 text-sm rounded-lg border border-zinc-200 bg-white px-2 font-medium min-w-[5.5rem]",
          className
        )}
      />
    );
  }

  return (
    <div className={cn("flex flex-wrap gap-1.5 max-h-36 overflow-y-auto py-0.5", className)}>
      {allSlots.map((time) => {
        const isBusy = busySet.has(time) || !availableSet.has(time);
        const isSelected = value === time;
        return (
          <button
            key={time}
            type="button"
            disabled={disabled || isBusy}
            onClick={() => !isBusy && onChange(time)}
            title={isBusy ? time : undefined}
            className={cn(
              "min-w-[3.25rem] px-2 py-1.5 rounded-lg text-xs font-bold border transition-colors",
              isSelected && !isBusy && "bg-zinc-900 text-white border-zinc-900 shadow-sm",
              !isSelected && !isBusy &&
                "bg-white border-zinc-200 text-zinc-800 hover:bg-zinc-50 hover:border-zinc-300",
              isBusy && "bg-zinc-100 border-zinc-200 text-zinc-400 cursor-not-allowed line-through decoration-zinc-400",
              disabled && "opacity-50 pointer-events-none"
            )}
          >
            {time}
          </button>
        );
      })}
    </div>
  );
};

export default PlannerTimeSlotGrid;
