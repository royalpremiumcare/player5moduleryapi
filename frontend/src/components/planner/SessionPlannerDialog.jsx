/**
 * Plann — Session Planner shell.
 *
 * Mobile-first dialog that orchestrates the two screens:
 *   • SmartScreen    — default, instant overview with conflict resolution
 *   • ManualScreen   — drill-in for per-session editing (slot grid + mini week)
 *
 * On mobile (<640px) the dialog becomes a full-height sheet with sticky
 * header + sticky footer CTA. On desktop it stays as a centered modal.
 */
import React, { useState, useMemo, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { X, CalendarDays, Loader2, PackageX, Check, RotateCcw } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useAuth } from "../../context/AuthContext";

import SmartScreen from "./SmartScreen";
import ManualScreen from "./ManualScreen";
import { usePlanSuggestion, usePlannerSettings, useOptimisticPlan } from "./hooks";
import { allGreen } from "./utils";

const SessionPlannerDialog = ({ open, onOpenChange, appointment, onSuccess, notifyIncludeExistingSessions = false }) => {
  const { t, i18n } = useTranslation();
  const isTr = i18n.language === "tr";
  const { userRole, canViewAll } = useAuth();

  const [screen, setScreen] = useState("smart"); // "smart" | "manual"
  const [manualIndex, setManualIndex] = useState(0);

  const remainingCount = appointment
    ? Math.max(0, (Number(appointment.session_total) || 0) - (Number(appointment.session_number) || 0))
    : 0;

  const { plannerSettings, allStaff, getDayRange } = usePlannerSettings(open);

  const { sessions, setSessions, loading, checking, load, check, patch } =
    usePlanSuggestion({ appointment, open, plannerSettings, remainingCount });

  // Reset screen when dialog opens / closes
  useEffect(() => {
    if (open) {
      setScreen("smart");
      setManualIndex(0);
    }
  }, [open]);

  // Staff lookup map for quick name resolution
  const staffLookup = useMemo(() => {
    const map = {};
    (allStaff || []).forEach((u) => { map[u.username] = u; });
    return map;
  }, [allStaff]);

  const qualifiedStaff = useMemo(() => {
    if (!appointment?.service_id || !plannerSettings) return [];
    const users = allStaff || [];
    let q = users.filter((u) =>
      Array.isArray(u.permitted_service_ids) &&
      u.permitted_service_ids.includes(appointment.service_id)
    );
    if (!plannerSettings.admin_provides_service) {
      q = q.filter((s) => s.role !== "admin");
    }
    return q;
  }, [appointment?.service_id, plannerSettings, allStaff]);

  const showStaffPicker =
    (userRole === "admin" || userRole === "superadmin" || canViewAll) &&
    qualifiedStaff.length > 0;

  // Apply one alternative (from conflict chip). Supports time-only or staff-swap.
  const applyAlternative = useCallback(
    (idx, alt) => {
      const p = {};
      if (alt.time) p.time = alt.time;
      if (alt.kind === "staff" && alt.staff_member_id) p.staff_member_id = alt.staff_member_id;
      patch(idx, p);
      // Re-check shortly after patching so the status dot updates inline.
      setTimeout(check, 200);
    },
    [patch, check]
  );

  // Auto-fix: apply the first alternative of every amber session.
  const autoFix = useCallback(() => {
    let touched = false;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.available !== false) return s;
        const firstAlt = (s.alternatives || [])[0];
        if (!firstAlt) return s;
        touched = true;
        const t = typeof firstAlt === "string" ? firstAlt : firstAlt.time;
        return { ...s, time: t || s.time, available: null, alternatives: [] };
      })
    );
    if (touched) setTimeout(check, 200);
  }, [setSessions, check]);

  const { creating, submit } = useOptimisticPlan({
    appointment,
    sessions,
    onDone: () => {
      onOpenChange(false);
      onSuccess && onSuccess();
    },
    t,
    notifyIncludeExistingSessions,
  });

  const isEmpty = !appointment || remainingCount <= 0;
  const startingNumber = (Number(appointment?.session_number) || 0) + 1;
  const ready = allGreen(sessions);

  // -----  RENDER  ---------------------------------------------------------

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden border-0 sm:border sm:border-white/30 bg-white rounded-none sm:rounded-3xl shadow-2xl sm:max-w-3xl w-full max-w-full h-[100dvh] sm:h-auto sm:max-h-[92vh] flex flex-col [&>button.absolute]:hidden"
        style={{
          paddingTop: "env(safe-area-inset-top, 0px)",
          paddingBottom: "env(safe-area-inset-bottom, 0px)",
        }}
      >
        {/* STICKY HEADER */}
        <div className="flex-shrink-0 border-b border-zinc-200 bg-white px-4 py-3 sm:px-5 sm:py-4 flex items-center gap-3">
          <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-zinc-100 flex items-center justify-center">
            <CalendarDays className="w-4 h-4 text-zinc-700" />
          </div>
          <div className="flex-1 min-w-0 overflow-hidden">
            <DialogTitle className="text-sm sm:text-base font-black text-zinc-900 leading-tight flex items-center gap-1.5 min-w-0">
              <span className="truncate">{t("sessionPlanner.title")}</span>
              {appointment?.session_number != null && appointment?.session_total != null && (
                <span className="flex-shrink-0 inline-flex items-center text-[9px] font-bold text-zinc-600 bg-zinc-100 border border-zinc-200/80 px-1.5 py-0.5 rounded-full whitespace-nowrap tracking-tight">
                  {appointment.session_number}/{appointment.session_total}
                </span>
              )}
            </DialogTitle>
            <DialogDescription className="text-[11px] sm:text-xs text-zinc-500 truncate">
              {[appointment?.customer_name, appointment?.service_name].filter(Boolean).join(" · ")}
            </DialogDescription>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="flex-shrink-0 w-9 h-9 rounded-full hover:bg-zinc-100 active:bg-zinc-200 flex items-center justify-center"
            aria-label={isTr ? "Kapat" : "Close"}
          >
            <X className="w-4 h-4 text-zinc-600" />
          </button>
        </div>

        {/* SCROLLABLE BODY */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-4 sm:px-5 sm:py-5 bg-zinc-50">
          {isEmpty ? (
            <EmptyState isTr={isTr} onClose={() => onOpenChange(false)} />
          ) : screen === "smart" ? (
            <SmartScreen
              appointment={appointment}
              sessions={sessions}
              loading={loading}
              checking={checking}
              staffLookup={staffLookup}
              remainingCount={remainingCount}
              onOpenManual={(idx) => {
                setManualIndex(idx);
                setScreen("manual");
              }}
              onApplyAlternative={applyAlternative}
              onAutoFix={autoFix}
              onRecheck={check}
              isTr={isTr}
            />
          ) : (
            <ManualScreen
              appointment={appointment}
              sessionIndex={manualIndex}
              sessions={sessions}
              sessionNumber={startingNumber + manualIndex}
              qualifiedStaff={qualifiedStaff}
              showStaffPicker={showStaffPicker}
              onPatch={(idx, p) => {
                patch(idx, p);
                setTimeout(check, 200);
              }}
              onBack={() => setScreen("smart")}
              onSaveAndContinue={() => {
                if (manualIndex < sessions.length - 1) {
                  setManualIndex((i) => i + 1);
                } else {
                  setScreen("smart");
                }
              }}
              onSave={() => setScreen("smart")}
              isMultiEdit={false}
              isTr={isTr}
              getDayRange={getDayRange}
            />
          )}
        </div>

        {/* STICKY FOOTER (Smart screen only) */}
        {!isEmpty && screen === "smart" && (
          <div className="flex-shrink-0 border-t border-zinc-200 bg-white px-4 py-3 sm:px-5 sm:py-4 flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={load}
              disabled={loading || creating}
              className="rounded-xl font-bold flex-shrink-0 min-h-[52px] px-3 sm:px-4"
              aria-label={isTr ? "Yeniden öner" : "Re-plan"}
              title={isTr ? "Yeniden öner" : "Re-plan"}
            >
              <RotateCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline ml-2">{isTr ? "Yeniden öner" : "Re-plan"}</span>
            </Button>
            <Button
              type="button"
              onClick={submit}
              disabled={!ready || creating || loading}
              className="flex-1 bg-zinc-900 hover:bg-black text-white rounded-xl font-black shadow-lg disabled:opacity-40 min-h-[52px] text-sm sm:text-base"
            >
              {creating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {t("sessionPlanner.creating")}
                </>
              ) : ready ? (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  {isTr
                    ? `${sessions.length} Seansı Planla`
                    : `Plan ${sessions.length} Sessions`}
                </>
              ) : loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {isTr ? "Hazırlanıyor..." : "Preparing..."}
                </>
              ) : (
                isTr ? "Çakışmaları çöz" : "Resolve conflicts"
              )}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

function EmptyState({ isTr, onClose }) {
  return (
    <div className="py-10 flex flex-col items-center text-center gap-3 px-4">
      <div className="w-14 h-14 rounded-full bg-zinc-100 flex items-center justify-center">
        <PackageX className="w-7 h-7 text-zinc-400" />
      </div>
      <h3 className="font-bold text-zinc-900">
        {isTr ? "Planlanacak seans yok" : "No sessions to plan"}
      </h3>
      <p className="text-sm text-zinc-600 max-w-sm">
        {isTr
          ? "Bu paketin tüm seansları planlanmış veya paket seans sayısı bulunamadı."
          : "All sessions already planned or session count is missing."}
      </p>
      <Button onClick={onClose} variant="outline" className="mt-2 rounded-xl min-h-[44px]">
        {isTr ? "Kapat" : "Close"}
      </Button>
    </div>
  );
}

export default SessionPlannerDialog;
