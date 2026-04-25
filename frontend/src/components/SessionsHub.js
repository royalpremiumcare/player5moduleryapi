import React, { useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { format, parseISO, addDays } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { Layers, Search, Trash2, CalendarClock, Pencil } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import SessionPlannerDialog from "./SessionPlannerDialog";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { formatApiError } from "@/lib/apiError";

/** Calendar / i18n ile uyumlu — TR + EN API değerleri */
const getStatusCode = (status) => {
  if (!status) return null;
  const s = String(status).trim().toLowerCase();
  if (s === "pending" || s === "bekliyor" || s === "waiting") return "pending";
  if (s === "completed" || s === "tamamlandı" || s === "tamamlandi" || s === "done") return "completed";
  if (
    s === "cancelled" ||
    s === "canceled" ||
    s === "iptal" ||
    s === "iptal edildi" ||
    s === "iptal edıldı"
  )
    return "cancelled";
  return null;
};

const isTerminalStatus = (a) => {
  const c = getStatusCode(a.status);
  return c === "completed" || c === "cancelled";
};

const isCancellable = (a) => !isTerminalStatus(a);

function normalizeAppointmentTime(t) {
  if (!t || typeof t !== "string") return "09:00";
  const p = t.trim().split(":");
  const h = Math.min(23, Math.max(0, parseInt(p[0], 10) || 0));
  const m = Math.min(59, Math.max(0, parseInt(p[1] ?? "0", 10) || 0));
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function appointmentDateTimeMs(a) {
  if (!a?.appointment_date) return 0;
  const raw = `${a.appointment_date}T${normalizeAppointmentTime(a.appointment_time || "09:00")}`;
  const d = parseISO(raw);
  return Number.isNaN(d.getTime()) ? 0 : d.getTime();
}

/** Tamamlanan / iptal: en son işlem zamanı (cluster 3) */
function terminalActivityTimestampMs(a) {
  const raw = a.updated_at || a.completed_at || a.created_at;
  if (raw) {
    const t = new Date(raw).getTime();
    if (!Number.isNaN(t)) return t;
  }
  return appointmentDateTimeMs(a);
}

const SessionsHub = ({ appointments, onRefresh, userRole, onEditAppointment }) => {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "tr" ? tr : enGB;
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmRefundOpen, setConfirmRefundOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [refunding, setRefunding] = useState(false);
  const [plannerOpen, setPlannerOpen] = useState(false);
  const [plannerAppointment, setPlannerAppointment] = useState(null);
  const [hubTab, setHubTab] = useState("pending");
  const [searchQuery, setSearchQuery] = useState("");
  const [groupDeleteTarget, setGroupDeleteTarget] = useState(null); // { session_group_id, customer_name, count }
  const [groupDeleting, setGroupDeleting] = useState(false);

  const canManageGroup = userRole === "admin" || userRole === "superadmin";

  const handleDeleteGroupConfirmed = async () => {
    if (!groupDeleteTarget) return;
    setGroupDeleting(true);
    try {
      await api.delete(`/appointments/groups/${groupDeleteTarget.session_group_id}`);
      toast.success(
        i18n.language === "tr"
          ? `${groupDeleteTarget.count} seans silindi.`
          : `${groupDeleteTarget.count} sessions deleted.`
      );
      setGroupDeleteTarget(null);
      if (onRefresh) onRefresh();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setGroupDeleting(false);
    }
  };

  const handleEditAppointment = (apt) => {
    if (onEditAppointment) {
      onEditAppointment(apt);
    } else {
      toast.error(
        i18n.language === "tr"
          ? "Düzenleme şu an kullanılamıyor."
          : "Editing is not available right now."
      );
    }
  };

  const groups = useMemo(() => {
    const map = new Map();
    for (const apt of appointments || []) {
      const gid = apt.session_group_id;
      if (!gid) continue;
      if (!map.has(gid)) map.set(gid, []);
      map.get(gid).push(apt);
    }
    return Array.from(map.entries()).map(([id, apts]) => ({
      session_group_id: id,
      appointments: [...apts].sort(
        (a, b) => (a.session_number || 0) - (b.session_number || 0)
      ),
    }));
  }, [appointments]);

  const filteredGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return groups.filter((g) => {
      const apts = g.appointments;
      const hasOpen = apts.some((a) => !isTerminalStatus(a));
      const allClosed = apts.length > 0 && apts.every((a) => isTerminalStatus(a));
      if (hubTab === "pending") {
        if (!hasOpen) return false;
      } else if (!allClosed) return false;
      if (!q) return true;
      const first = apts[0];
      return (
        (first.customer_name || "").toLowerCase().includes(q) ||
        (first.service_name || "").toLowerCase().includes(q)
      );
    });
  }, [groups, hubTab, searchQuery]);

  /**
   * Bekleyen: küme 1 = bugün/yarın + pending; küme 2 = diğer açık seanslar — tarih+saat ASC.
   * Tamamlanan: küme 3 — terminal kayıtlarda en güncel işlem (updated_at / completed_at) DESC; eşitlikte son randevu tarihi.
   */
  const orderedFilteredGroups = useMemo(() => {
    const list = filteredGroups;
    if (list.length === 0) return [];

    const todayStr = format(new Date(), "yyyy-MM-dd");
    const tomorrowStr = format(addDays(new Date(), 1), "yyyy-MM-dd");

    const nextOpenSession = (apts) => {
      const opens = apts.filter((a) => !isTerminalStatus(a));
      if (opens.length === 0) return null;
      return [...opens].sort((x, y) => appointmentDateTimeMs(x) - appointmentDateTimeMs(y))[0];
    };

    const isVipPendingSlot = (apt) => {
      if (!apt) return false;
      if (getStatusCode(apt.status) !== "pending") return false;
      const d = apt.appointment_date;
      return d === todayStr || d === tomorrowStr;
    };

    if (hubTab === "pending") {
      return [...list].sort((ga, gb) => {
        const na = nextOpenSession(ga.appointments);
        const nb = nextOpenSession(gb.appointments);
        const vipA = isVipPendingSlot(na);
        const vipB = isVipPendingSlot(nb);
        if (vipA !== vipB) return vipA ? -1 : 1;
        return appointmentDateTimeMs(na) - appointmentDateTimeMs(nb);
      });
    }

    return [...list].sort((ga, gb) => {
      const termsA = ga.appointments.filter(isTerminalStatus);
      const termsB = gb.appointments.filter(isTerminalStatus);
      const maxA = termsA.length ? Math.max(...termsA.map(terminalActivityTimestampMs)) : 0;
      const maxB = termsB.length ? Math.max(...termsB.map(terminalActivityTimestampMs)) : 0;
      if (maxB !== maxA) return maxB - maxA;
      const apptA = termsA.length ? Math.max(...termsA.map(appointmentDateTimeMs)) : 0;
      const apptB = termsB.length ? Math.max(...termsB.map(appointmentDateTimeMs)) : 0;
      return apptB - apptA;
    });
  }, [filteredGroups, hubTab]);

  const formatSessionWhen = (a) => {
    try {
      const raw = `${a.appointment_date}T${(a.appointment_time || "00:00").length === 5 ? a.appointment_time : "09:00"}`;
      const d = parseISO(raw);
      if (Number.isNaN(d.getTime())) return `${a.appointment_date} ${a.appointment_time || ""}`;
      return format(d, "d MMMM yyyy EEEE HH:mm", { locale: dateLocale });
    } catch {
      return `${a.appointment_date} ${a.appointment_time || ""}`;
    }
  };

  const statusDotClass = (a) => {
    const c = getStatusCode(a.status);
    if (c === "completed") return "bg-emerald-500";
    if (c === "cancelled") return "bg-red-500";
    return "bg-amber-400";
  };

  const toggleAppointment = useCallback((id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleGroup = useCallback((apts) => {
    const cancellable = apts.filter(isCancellable).map((a) => a.id);
    if (cancellable.length === 0) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const allSelected = cancellable.every((id) => next.has(id));
      if (allSelected) cancellable.forEach((id) => next.delete(id));
      else cancellable.forEach((id) => next.add(id));
      return next;
    });
  }, []);

  const selectedAppts = useMemo(
    () => (appointments || []).filter((a) => selectedIds.has(a.id)),
    [appointments, selectedIds]
  );

  const canRefundBulk = useMemo(() => {
    if (userRole !== "admin" && userRole !== "superadmin") return false;
    if (selectedAppts.length === 0) return false;
    const gids = new Set(
      selectedAppts.map((a) => a.session_group_id).filter(Boolean)
    );
    if (gids.size !== 1 || !selectedAppts.every((a) => a.session_group_id)) return false;
    return selectedAppts.every((a) => a.refund_eligible === true);
  }, [selectedAppts, userRole]);

  const handleConfirmCancel = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setCancelling(true);
    try {
      await api.post("/appointments/cancel-selected", {
        appointment_ids: ids,
        refund: false,
      });
      toast.success(t("sessions.cancelSuccess"));
      setSelectedIds(new Set());
      setConfirmOpen(false);
      if (onRefresh) await onRefresh();
    } catch (err) {
      toast.error(formatApiError(err, t, t("sessions.cancelError")));
    } finally {
      setCancelling(false);
    }
  };

  const handleConfirmRefund = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setRefunding(true);
    try {
      await api.post("/appointments/cancel-selected", {
        appointment_ids: ids,
        refund: true,
      });
      toast.success(t("sessions.refundSuccess"));
      setSelectedIds(new Set());
      setConfirmRefundOpen(false);
      if (onRefresh) await onRefresh();
    } catch (err) {
      toast.error(formatApiError(err, t, t("sessions.refundError")));
    } finally {
      setRefunding(false);
    }
  };

  const selectedCount = selectedIds.size;
  const canBulkCancel =
    userRole === "admin" ||
    userRole === "staff" ||
    userRole === "superadmin";

  const canPlanRemaining = (apts) => {
    const st = apts[0]?.session_total || 0;
    if (st <= 1) return false;
    const maxNum = Math.max(0, ...apts.map((a) => a.session_number || 0));
    return maxNum < st;
  };

  const openPlannerForGroup = (apts) => {
    const sorted = [...apts].sort(
      (a, b) => (a.session_number || 0) - (b.session_number || 0)
    );
    setPlannerAppointment(sorted[0] || null);
    setPlannerOpen(true);
  };

  return (
    <div className="min-h-screen bg-gray-50/50 pb-28 font-sans px-4 py-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-zinc-900 text-white shadow-md">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{t("sessions.title")}</h1>
            <p className="text-sm text-gray-500">{t("sessions.subtitle")}</p>
          </div>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 pointer-events-none" />
          <Input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t("sessions.searchPlaceholder")}
            className="pl-9 h-11 rounded-xl border-zinc-200 bg-white text-sm"
          />
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <Button
          type="button"
          variant={hubTab === "pending" ? "default" : "outline"}
          className={
            hubTab === "pending"
              ? "bg-zinc-900 hover:bg-black text-white"
              : "border-zinc-200"
          }
          size="sm"
          onClick={() => setHubTab("pending")}
        >
          {t("sessions.tabPending")}
        </Button>
        <Button
          type="button"
          variant={hubTab === "completed" ? "default" : "outline"}
          className={
            hubTab === "completed"
              ? "bg-zinc-900 hover:bg-black text-white"
              : "border-zinc-200"
          }
          size="sm"
          onClick={() => setHubTab("completed")}
        >
          {t("sessions.tabCompleted")}
        </Button>
      </div>

      {groups.length === 0 ? (
        <Card className="p-8 text-center text-gray-500 border border-zinc-100 shadow-md rounded-xl">
          {t("sessions.empty")}
        </Card>
      ) : filteredGroups.length === 0 ? (
        <Card className="p-8 text-center text-zinc-500 border border-zinc-100 shadow-md rounded-xl">
          {groups.length > 0 ? t("sessions.noSearchResults") : t("sessions.empty")}
        </Card>
      ) : (
        <Accordion type="multiple" className="space-y-2">
          {orderedFilteredGroups.map(({ session_group_id, appointments: apts }) => {
            const first = apts[0];
            const rowSessions =
              hubTab === "completed"
                ? [...apts].sort((a, b) => appointmentDateTimeMs(a) - appointmentDateTimeMs(b))
                : apts;
            const total = first.session_total || apts.length;
            const completed = apts.filter((a) => getStatusCode(a.status) === "completed").length;
            const cancellable = apts.filter(isCancellable);
            const allGroupSelected =
              cancellable.length > 0 &&
              cancellable.every((a) => selectedIds.has(a.id));
            const showPlan =
              canPlanRemaining(apts) &&
              (userRole === "admin" ||
                userRole === "staff" ||
                userRole === "superadmin");

            return (
              <AccordionItem
                key={session_group_id}
                value={session_group_id}
                className="border border-zinc-100 rounded-xl bg-white shadow-md px-5 py-1"
              >
                <AccordionTrigger className="hover:no-underline py-5 [&>svg]:ml-2">
                  <div className="flex items-center gap-3 text-left min-w-0 flex-1">
                    {canBulkCancel && cancellable.length > 0 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleGroup(apts);
                        }}
                        className={cn(
                          "h-5 w-5 rounded border-2 shrink-0 flex items-center justify-center",
                          allGroupSelected
                            ? "bg-zinc-900 border-zinc-900"
                            : "border-zinc-300 bg-white"
                        )}
                        aria-label={t("sessions.selectGroup")}
                      >
                        {allGroupSelected && (
                          <span className="text-white text-xs leading-none">✓</span>
                        )}
                      </button>
                    )}
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <p className="font-bold text-zinc-900 truncate text-base">
                        {first.customer_name || "—"}
                      </p>
                      <p className="text-xs sm:text-sm text-zinc-600 line-clamp-2 break-words mt-0.5 leading-snug">
                        {first.service_name ? `${first.service_name} · ` : ""}
                        {t("sessions.progress", { completed, total })}
                      </p>
                    </div>
                    {canManageGroup && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setGroupDeleteTarget({
                            session_group_id,
                            customer_name: first.customer_name || "—",
                            service_name: first.service_name || "",
                            count: apts.length,
                          });
                        }}
                        className="shrink-0 h-9 w-9 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 active:bg-red-200 flex items-center justify-center transition-colors"
                        aria-label={i18n.language === "tr" ? "Paketi sil" : "Delete package"}
                        title={i18n.language === "tr" ? "Paketi sil" : "Delete package"}
                      >
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </button>
                    )}
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  {showPlan && (
                    <div className="mb-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-zinc-200 font-semibold bg-white hover:bg-zinc-50"
                        onClick={() => openPlannerForGroup(apts)}
                      >
                        <CalendarClock className="w-4 h-4 mr-2 shrink-0" />
                        {t("sessions.quickPlan")}
                      </Button>
                    </div>
                  )}
                  <ul className="space-y-2 pb-2">
                    {rowSessions.map((a) => {
                      const can = isCancellable(a);
                      const sel = selectedIds.has(a.id);
                      return (
                        <li
                          key={a.id}
                          className="flex items-start gap-2 text-sm text-zinc-900"
                        >
                          {canBulkCancel && can && (
                            <button
                              type="button"
                              onClick={() => toggleAppointment(a.id)}
                              className={cn(
                                "h-4 w-4 rounded border shrink-0 flex items-center justify-center",
                                sel
                                  ? "bg-zinc-900 border-zinc-900"
                                  : "border-zinc-300 bg-white"
                              )}
                              aria-label={t("sessions.selectSession")}
                            >
                              {sel && (
                                <span className="text-white text-[10px] leading-none">
                                  ✓
                                </span>
                              )}
                            </button>
                          )}
                          <span className="min-w-0 leading-snug flex-1">
                            <span className="font-semibold">{a.session_number ?? "—"}</span>
                            {" · "}
                            {formatSessionWhen(a)}
                            {" · "}
                            <span className="text-zinc-600">{a.status || "—"}</span>
                            <span
                              className={`ml-2 inline-block h-2 w-2 rounded-full align-middle ${statusDotClass(a)}`}
                              aria-hidden
                            />
                          </span>
                          {canManageGroup && can && (
                            <button
                              type="button"
                              onClick={() => handleEditAppointment(a)}
                              className="shrink-0 h-7 w-7 rounded-md border border-zinc-200 bg-white hover:bg-zinc-50 active:bg-zinc-100 flex items-center justify-center transition-colors"
                              aria-label={i18n.language === "tr" ? "Düzenle" : "Edit"}
                              title={i18n.language === "tr" ? "Düzenle" : "Edit"}
                            >
                              <Pencil className="w-3.5 h-3.5 text-zinc-600" />
                            </button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      )}

      {canBulkCancel && selectedCount > 0 && (
        <div className="fixed bottom-20 left-0 right-0 z-[900] px-4 safe-area-pb">
          <div className="max-w-lg mx-auto flex flex-col sm:flex-row gap-2">
            <Button
              type="button"
              variant="outline"
              className="flex-1 bg-white border-zinc-200"
              onClick={() => setSelectedIds(new Set())}
            >
              {t("sessions.clearSelection")}
            </Button>
            <Button
              type="button"
              className="flex-1 bg-zinc-900 hover:bg-black text-white font-bold"
              onClick={() => setConfirmOpen(true)}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              {t("sessions.cancelSelected", { count: selectedCount })}
            </Button>
            {canRefundBulk && (
              <Button
                type="button"
                variant="outline"
                className="flex-1 border-red-200 text-red-700 hover:bg-red-50 font-bold"
                onClick={() => setConfirmRefundOpen(true)}
              >
                {t("sessions.cancelWithRefund", { count: selectedCount })}
              </Button>
            )}
          </div>
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="rounded-xl">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("sessions.confirmCancelTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("sessions.confirmCancelDescription", { count: selectedCount })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cancelling}>{t("common.cancel")}</AlertDialogCancel>
            <Button
              type="button"
              onClick={handleConfirmCancel}
              disabled={cancelling}
              className="bg-zinc-900 hover:bg-black text-white"
            >
              {cancelling ? "…" : t("sessions.confirmCancelAction")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmRefundOpen} onOpenChange={setConfirmRefundOpen}>
        <AlertDialogContent className="rounded-xl">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("sessions.confirmRefundTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("sessions.confirmRefundDescription", { count: selectedCount })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={refunding}>{t("common.cancel")}</AlertDialogCancel>
            <Button
              type="button"
              onClick={handleConfirmRefund}
              disabled={refunding}
              className="bg-red-700 hover:bg-red-800 text-white"
            >
              {refunding ? "…" : t("sessions.confirmRefundAction")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={!!groupDeleteTarget}
        onOpenChange={(open) => { if (!open) setGroupDeleteTarget(null); }}
      >
        <AlertDialogContent className="rounded-xl">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {i18n.language === "tr" ? "Seans paketini sil" : "Delete session package"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {i18n.language === "tr"
                ? `${groupDeleteTarget?.customer_name || "Müşteri"} adlı müşterinin ${groupDeleteTarget?.service_name ? `"${groupDeleteTarget.service_name}" hizmetine ait ` : ""}${groupDeleteTarget?.count || 0} seansının tamamı (tamamlananlar dahil) kalıcı olarak silinecek. Bu işlem geri alınamaz.`
                : `All ${groupDeleteTarget?.count || 0} sessions${groupDeleteTarget?.service_name ? ` for "${groupDeleteTarget.service_name}"` : ""} of customer ${groupDeleteTarget?.customer_name || ""} (including completed ones) will be permanently deleted. This action cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={groupDeleting}>
              {t("common.cancel")}
            </AlertDialogCancel>
            <Button
              type="button"
              onClick={handleDeleteGroupConfirmed}
              disabled={groupDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {groupDeleting ? "…" : (i18n.language === "tr" ? "Kalıcı olarak sil" : "Delete permanently")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <SessionPlannerDialog
        open={plannerOpen}
        onOpenChange={setPlannerOpen}
        appointment={plannerAppointment}
        onSuccess={() => {
          setPlannerOpen(false);
          setPlannerAppointment(null);
          if (onRefresh) onRefresh();
        }}
      />
    </div>
  );
};

export default SessionsHub;
