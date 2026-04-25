/**
 * Plann — Smart Suggestion Screen (Screen A).
 *
 * Default experience. Shows the AI-generated plan at a glance with status
 * pills per session. Conflicts are surfaced inline with one-tap alternatives.
 * Tapping a row drills into the ManualScreen for fine-grained editing.
 */
import React from "react";
import { CheckCircle2, AlertTriangle, Clock, Edit3, Loader2, Sparkles, User, ChevronRight, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDateShort, rankAlternatives, conflictCount } from "./utils";

function StatusDot({ status }) {
  if (status === "green") return <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0" aria-label="Uygun" />;
  if (status === "amber") return <span className="w-2.5 h-2.5 rounded-full bg-amber-500 flex-shrink-0" aria-label="Çakışma" />;
  return <span className="w-2.5 h-2.5 rounded-full bg-zinc-300 flex-shrink-0" aria-label="Kontrol ediliyor" />;
}

/**
 * Single-row session summary. Mobile-first: stacks on narrow screens,
 * goes horizontal on sm+ breakpoints.
 */
function SessionRow({
  session,
  index,
  sessionNumber,
  staffName,
  onApplyAlternative,
  onOpenManual,
  isTr,
}) {
  const status = session.available === true ? "green" : session.available === false ? "amber" : "gray";
  const alts = rankAlternatives(session, session.staff_member_id);

  return (
    <div
      className={`rounded-2xl border transition-all ${
        status === "green"
          ? "border-emerald-200 bg-emerald-50/40"
          : status === "amber"
          ? "border-amber-300 bg-amber-50/60"
          : "border-zinc-200 bg-white"
      }`}
    >
      <button
        type="button"
        onClick={() => onOpenManual(index)}
        className="w-full text-left p-3 sm:p-4 flex items-center gap-3 active:opacity-70 transition-opacity min-h-[64px]"
      >
        <div className="flex-shrink-0 w-9 h-9 rounded-full bg-white border border-zinc-200 flex items-center justify-center text-xs font-black text-zinc-700">
          {sessionNumber}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusDot status={status} />
            <span className="font-bold text-zinc-900 text-sm sm:text-base truncate">
              {formatDateShort(session.date, isTr ? "tr" : "en")}
            </span>
            <span className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-zinc-700">
              <Clock className="w-3.5 h-3.5" /> {session.time}
            </span>
          </div>
          {staffName && (
            <p className="mt-0.5 text-xs text-zinc-500 truncate flex items-center gap-1">
              <User className="w-3 h-3" /> {staffName}
            </p>
          )}
          {status === "amber" && (
            <p className="mt-1 text-xs text-amber-800 font-semibold">
              {isTr ? "Bu saat dolu" : "This time is taken"}
            </p>
          )}
          {session.unplanned && status === "gray" && (
            <p className="mt-0.5 text-[11px] text-zinc-500">
              {isTr ? "Uygun slot bulunamadı — düzenle" : "No auto-slot — edit"}
            </p>
          )}
        </div>
        <Edit3 className="w-4 h-4 text-zinc-400 flex-shrink-0" />
      </button>

      {status === "amber" && alts.length > 0 && (
        <div className="border-t border-amber-200 p-3 bg-white/60">
          <p className="text-[11px] font-bold text-amber-900 uppercase tracking-wide mb-2">
            {isTr ? "Hemen çöz:" : "Quick fix:"}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {alts.map((alt, aIdx) => (
              <button
                key={aIdx}
                type="button"
                onClick={() => onApplyAlternative(index, alt)}
                className="px-3 py-1.5 rounded-full bg-white border border-amber-300 text-amber-900 text-xs font-bold hover:bg-amber-100 active:scale-95 transition-all min-h-[32px]"
              >
                {alt.kind === "staff" ? (
                  <>→ {alt.staff_name || "Diğer personel"}</>
                ) : (
                  alt.time
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Loading skeleton when the suggestion is being computed.
 */
function SkeletonRow({ i }) {
  return (
    <div
      className="rounded-2xl border border-zinc-200 bg-white p-4 flex items-center gap-3 animate-pulse"
      style={{ animationDelay: `${i * 80}ms` }}
    >
      <div className="w-9 h-9 rounded-full bg-zinc-100" />
      <div className="flex-1 space-y-2">
        <div className="h-3 w-32 rounded bg-zinc-100" />
        <div className="h-2.5 w-20 rounded bg-zinc-100" />
      </div>
    </div>
  );
}

function ConflictBanner({ count, onAutoFix, isTr, fixing }) {
  if (count <= 0) return null;
  return (
    <div className="rounded-2xl border border-amber-300 bg-gradient-to-r from-amber-50 to-amber-100 p-3 sm:p-4 flex items-center gap-3">
      <div className="flex-shrink-0 w-9 h-9 rounded-full bg-amber-500 text-white flex items-center justify-center">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-amber-900 text-sm">
          {isTr ? `${count} çakışma var` : `${count} conflicts found`}
        </p>
        <p className="text-xs text-amber-800">
          {isTr ? "Önerilen alternatifi tek tıkla uygula" : "One tap applies the suggested alternative"}
        </p>
      </div>
      {onAutoFix && (
        <Button
          type="button"
          size="sm"
          onClick={onAutoFix}
          disabled={fixing}
          className="bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold text-xs whitespace-nowrap"
        >
          {fixing ? <Loader2 className="w-4 h-4 animate-spin" /> : (
            <><Wand2 className="w-3.5 h-3.5 mr-1.5" />{isTr ? "Otomatik çöz" : "Auto-fix"}</>
          )}
        </Button>
      )}
    </div>
  );
}

export default function SmartScreen({
  appointment,
  sessions,
  loading,
  checking,
  staffLookup,
  remainingCount,
  onOpenManual,
  onApplyAlternative,
  onAutoFix,
  onRecheck,
  isTr,
}) {
  const startingNumber = (Number(appointment?.session_number) || 0) + 1;
  const cCount = conflictCount(sessions);
  const allReady = sessions.length > 0 && sessions.every((s) => s.available === true);

  return (
    <div className="space-y-3 sm:space-y-4">
      {/* Summary header */}
      <div className="rounded-2xl bg-gradient-to-br from-zinc-900 to-zinc-700 text-white p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-white/70">
              {isTr ? "Akıllı öneri" : "Smart suggestion"}
            </p>
            <p className="text-lg sm:text-xl font-black leading-tight truncate">
              {appointment?.customer_name}
            </p>
            <p className="text-xs sm:text-sm text-white/80 truncate">
              {appointment?.service_name}
            </p>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className="text-2xl sm:text-3xl font-black">{remainingCount}</div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-white/70">
              {isTr ? "Kalan seans" : "Remaining"}
            </p>
          </div>
        </div>
      </div>

      {/* Conflict banner */}
      <ConflictBanner
        count={cCount}
        onAutoFix={onAutoFix}
        isTr={isTr}
        fixing={checking}
      />

      {/* Check-in-progress pill */}
      {checking && cCount === 0 && (
        <div className="text-xs text-zinc-500 flex items-center gap-2 px-1">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          {isTr ? "Müsaitlik kontrol ediliyor..." : "Checking availability..."}
        </div>
      )}

      {/* Session list */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: Math.max(3, remainingCount || 3) }).map((_, i) => (
            <SkeletonRow key={i} i={i} />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s, i) => (
            <SessionRow
              key={i}
              session={s}
              index={i}
              sessionNumber={startingNumber + i}
              staffName={
                s.staff_member_id && staffLookup[s.staff_member_id]?.full_name
                  ? staffLookup[s.staff_member_id].full_name
                  : ""
              }
              onApplyAlternative={onApplyAlternative}
              onOpenManual={onOpenManual}
              isTr={isTr}
            />
          ))}
        </div>
      )}

      {/* Tip row for all-green state */}
      {!loading && allReady && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 flex items-start gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-emerald-900 font-semibold">
            {isTr ? "Tüm seanslar uygun — kaydetmeye hazır." : "All sessions available — ready to save."}
          </p>
        </div>
      )}

      {/* Re-check link for stale state */}
      {!loading && !checking && sessions.some((s) => s.available === null) && (
        <button
          type="button"
          onClick={onRecheck}
          className="w-full text-xs text-zinc-500 hover:text-zinc-900 font-semibold py-2 flex items-center justify-center gap-1.5 min-h-[44px]"
        >
          <ChevronRight className="w-3.5 h-3.5" />
          {isTr ? "Tekrar kontrol et" : "Re-check availability"}
        </button>
      )}
    </div>
  );
}
