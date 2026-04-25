/**
 * Plann — Manual Edit Screen (Screen B).
 *
 * Drill-in view for editing a single session. Presents a compact week strip
 * (heat-map of busy vs free days) and a slot grid that re-colors based on the
 * selected staff. Staff dropdown is filtered to qualified staff only.
 */
import React, { useState, useMemo, useEffect } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Clock, User, Check, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import PlannerTimeSlotGrid from "../PlannerTimeSlotGrid";
import { formatDateLong, getWeekDays, addDays, parseLocalDate } from "./utils";
import { useStaffAvailability } from "./hooks";

/**
 * Returns the YYYY-MM-DD string of the Monday of the week containing `dateStr`.
 * Falls back to today's Monday when the input is invalid.
 */
function mondayOf(dateStr) {
  const d = parseLocalDate(dateStr) || new Date();
  const dow = d.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  const offsetDays = dow === 0 ? -6 : 1 - dow;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return addDays(`${y}-${m}-${day}`, offsetDays);
}

function WeekStrip({ anchorDate, onPickDate, selectedDate, isTr, getDayRange }) {
  // Single source of truth: the Monday of the week currently being displayed.
  // Initialised from anchorDate; re-synced when `selectedDate` lands outside it.
  // This prevents the "jump to next week" bug caused by combining a stale
  // numeric offset with a fresh anchorDate.
  const [weekStart, setWeekStart] = useState(() => mondayOf(anchorDate));

  // External re-sync — yalnızca `selectedDate` dışarıdan değiştiğinde tetiklenir
  // (örn. "Save & Continue" sonraki seansa geçişte). Kullanıcı ok tuşlarıyla
  // hafta değiştirdiğinde bu effect tetiklenmemeli, aksi halde weekStart
  // selectedDate'in eski haftasına geri düşer ve ok tuşları çalışmaz.
  // functional updater sayesinde `weekStart` bağımlılığa konulmaya gerek yok.
  useEffect(() => {
    if (!selectedDate) return;
    const target = mondayOf(selectedDate);
    setWeekStart((prev) => (prev === target ? prev : target));
  }, [selectedDate]);

  const days = useMemo(() => getWeekDays(weekStart), [weekStart]);

  const dayShort = (dayIdx) => (isTr
    ? ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"][dayIdx]
    : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][dayIdx]);

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-2 sm:p-3">
      <div className="flex items-center justify-between mb-2 px-1">
        <button
          type="button"
          onClick={() => setWeekStart((w) => addDays(w, -7))}
          className="w-8 h-8 rounded-lg hover:bg-zinc-100 active:bg-zinc-200 flex items-center justify-center"
          aria-label={isTr ? "Önceki hafta" : "Previous week"}
        >
          <ChevronLeft className="w-4 h-4 text-zinc-700" />
        </button>
        <p className="text-xs font-bold text-zinc-700">
          {formatDateLong(days[0].dateStr, isTr ? "tr" : "en")}
        </p>
        <button
          type="button"
          onClick={() => setWeekStart((w) => addDays(w, 7))}
          className="w-8 h-8 rounded-lg hover:bg-zinc-100 active:bg-zinc-200 flex items-center justify-center"
          aria-label={isTr ? "Sonraki hafta" : "Next week"}
        >
          <ChevronRight className="w-4 h-4 text-zinc-700" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d) => {
          const isSelected = d.dateStr === selectedDate;
          const isClosed = getDayRange && !getDayRange(d.date);
          const isPast =
            d.date < new Date(new Date().setHours(0, 0, 0, 0));
          const disabled = isClosed || isPast;
          return (
            <button
              key={d.dateStr}
              type="button"
              disabled={disabled}
              onClick={() => onPickDate(d.dateStr)}
              className={`min-h-[52px] rounded-xl flex flex-col items-center justify-center gap-0.5 transition-all text-center ${
                isSelected
                  ? "bg-zinc-900 text-white shadow-md"
                  : disabled
                  ? "bg-zinc-50 text-zinc-300 cursor-not-allowed"
                  : "bg-zinc-50 hover:bg-zinc-100 active:scale-95 text-zinc-700"
              }`}
            >
              <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">
                {dayShort(d.dayIdx)}
              </span>
              <span className="text-sm font-black">{d.dayNum}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function ManualScreen({
  appointment,
  sessionIndex,
  sessions,
  sessionNumber,
  qualifiedStaff,
  showStaffPicker,
  onPatch,
  onBack,
  onSaveAndContinue,
  onSave,
  isMultiEdit,
  isTr,
  getDayRange,
}) {
  const session = sessions[sessionIndex];
  if (!session) return null;

  const isLast = sessionIndex >= sessions.length - 1;
  const staffVal = (session.staff_member_id || "").trim() || "__default__";
  const workingRange = getDayRange
    ? (() => {
        const [y, m, d] = (session.date || "").split("-").map(Number);
        if (!y) return null;
        return getDayRange(new Date(y, m - 1, d));
      })()
    : null;
  const isOutOfHours =
    workingRange && session.time && (session.time < workingRange.start || session.time >= workingRange.end);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-sm font-bold text-zinc-600 hover:text-zinc-900 min-h-[44px] min-w-[44px] -ml-1 px-2 rounded-lg hover:bg-zinc-100"
        >
          <ArrowLeft className="w-4 h-4" />
          {isTr ? "Geri" : "Back"}
        </button>
        <span className="text-sm font-bold text-zinc-400">•</span>
        <p className="text-sm font-bold text-zinc-700 truncate">
          {isTr ? `Seans ${sessionNumber}` : `Session ${sessionNumber}`}
          {session.date && (
            <span className="text-zinc-400 font-medium ml-2">
              {formatDateLong(session.date, isTr ? "tr" : "en")}
            </span>
          )}
        </p>
      </div>

      {/* Week strip */}
      <WeekStrip
        anchorDate={session.date}
        selectedDate={session.date}
        onPickDate={(d) => onPatch(sessionIndex, { date: d, time: "" })}
        isTr={isTr}
        getDayRange={getDayRange}
      />

      {/* Slot grid */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-3 sm:p-4">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-zinc-500" />
          <p className="text-xs font-bold text-zinc-700 uppercase tracking-wide">
            {isTr ? "Saati seç" : "Pick a time"}
          </p>
          {session.time && (
            <span className="ml-auto text-sm font-black text-zinc-900">{session.time}</span>
          )}
        </div>
        <PlannerTimeSlotGrid
          serviceId={appointment.service_id}
          dateStr={session.date}
          staffId={staffVal === "__default__" ? "" : staffVal}
          excludeAppointmentId={appointment.id}
          value={session.time}
          onChange={(t) => onPatch(sessionIndex, { time: t })}
        />
        {isOutOfHours && (
          <p className="mt-2 text-[11px] text-orange-700 bg-orange-50 border border-orange-200 rounded-lg px-2 py-1.5 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3 flex-shrink-0" />
            {isTr
              ? `Çalışma saati dışı (${workingRange.start}–${workingRange.end})`
              : `Outside hours (${workingRange.start}–${workingRange.end})`}
          </p>
        )}
      </div>

      {/* Staff picker — availability-aware chips */}
      {showStaffPicker && qualifiedStaff.length > 0 && (
        <StaffAvailabilityPicker
          serviceId={appointment.service_id}
          date={session.date}
          time={session.time}
          excludeAppointmentId={appointment.id}
          qualifiedStaff={qualifiedStaff}
          selected={staffVal === "__default__" ? "" : staffVal}
          onSelect={(username) =>
            onPatch(sessionIndex, { staff_member_id: username })
          }
          isTr={isTr}
        />
      )}

      {/* Footer CTA */}
      <div className="flex flex-col sm:flex-row gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onBack}
          className="rounded-xl font-bold sm:w-auto w-full order-2 sm:order-1 min-h-[48px]"
        >
          {isTr ? "Özet'e dön" : "Back to overview"}
        </Button>
        {isMultiEdit && !isLast ? (
          <Button
            type="button"
            onClick={onSaveAndContinue}
            disabled={!session.date || !session.time}
            className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg disabled:opacity-50 flex-1 order-1 sm:order-2 min-h-[48px]"
          >
            <Check className="w-4 h-4 mr-2" />
            {isTr ? `Kaydet ve devam (${sessionNumber + 1}/${(appointment?.session_total) || "?"})` : "Save & continue"}
          </Button>
        ) : (
          <Button
            type="button"
            onClick={onSave}
            disabled={!session.date || !session.time}
            className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg disabled:opacity-50 flex-1 order-1 sm:order-2 min-h-[48px]"
          >
            <Check className="w-4 h-4 mr-2" />
            {isTr ? "Onayla" : "Confirm"}
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * Availability-aware staff picker.
 *
 * UX rationale:
 *   • Shown ONLY after user has picked both a date AND a time — a staff
 *     chip is meaningless without a concrete slot.
 *   • "Package default" is always the first chip so the user can revert.
 *   • Each qualified staff chip displays a status dot:
 *       green  → backend says free at this exact slot
 *       red    → busy (chip is disabled + strikethrough)
 *       gray   → availability still being probed or unknown
 *   • Race-safety: the hook cancels stale responses internally.
 */
function StaffAvailabilityPicker({
  serviceId,
  date,
  time,
  excludeAppointmentId,
  qualifiedStaff,
  selected,
  onSelect,
  isTr,
}) {
  const { availabilityMap, loading } = useStaffAvailability({
    serviceId,
    date,
    time,
    staff: qualifiedStaff,
    excludeAppointmentId,
  });

  const needsSlot = !date || !time;

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-3 sm:p-4">
      <div className="flex items-center gap-2 mb-3">
        <User className="w-4 h-4 text-zinc-500" />
        <p className="text-xs font-bold text-zinc-700 uppercase tracking-wide">
          {isTr ? "Personel" : "Staff"}
        </p>
        {loading && !needsSlot && (
          <Loader2 className="w-3.5 h-3.5 text-zinc-400 animate-spin ml-auto" />
        )}
      </div>

      {needsSlot ? (
        <p className="text-xs text-zinc-500 italic py-2">
          {isTr
            ? "Önce tarih ve saat seçin — uygun personel otomatik listelenecek."
            : "Pick a date and time first — available staff will appear."}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {/* Auto-assign chip — admin/staff akışında Paket varsayılanı yerine
              "Otomatik atama" etiketi kullanıyoruz. Davranış aynı: staff_member_id=""
              gönderilir, backend uygun personeli kendisi seçer. */}
          <button
            type="button"
            onClick={() => onSelect("")}
            className={`px-3 py-2 rounded-xl border text-xs font-bold transition-all min-h-[40px] ${
              !selected
                ? "bg-zinc-900 border-zinc-900 text-white shadow-md"
                : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
            }`}
          >
            {isTr ? "Otomatik atama" : "Auto-assign"}
          </button>

          {qualifiedStaff.map((u) => {
            const isAvailable = availabilityMap[u.username] === true;
            const isKnown = Object.prototype.hasOwnProperty.call(availabilityMap, u.username);
            const isSelected = selected === u.username;
            const isBusy = isKnown && !isAvailable;
            return (
              <button
                key={u.username}
                type="button"
                onClick={() => !isBusy && onSelect(u.username)}
                disabled={isBusy}
                title={isBusy ? (isTr ? "Bu saatte dolu" : "Busy at this time") : ""}
                className={`px-3 py-2 rounded-xl border text-xs font-bold transition-all min-h-[40px] flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-zinc-900 border-zinc-900 text-white shadow-md"
                    : isBusy
                    ? "bg-zinc-50 border-zinc-200 text-zinc-400 line-through cursor-not-allowed"
                    : isAvailable
                    ? "bg-white border-emerald-300 text-zinc-800 hover:bg-emerald-50"
                    : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    isSelected
                      ? "bg-white"
                      : isBusy
                      ? "bg-red-400"
                      : isAvailable
                      ? "bg-emerald-500"
                      : "bg-zinc-300"
                  }`}
                />
                {u.full_name || u.username}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
