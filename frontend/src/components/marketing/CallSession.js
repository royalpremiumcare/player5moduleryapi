/**
 * Plann — Marketing Call Session
 *
 * Pazarlamacı bir lead'i claim ettiği anda devreye giren full-screen
 * görüşme ekranı. Üstte canlı geri sayım, ortada büyük status chip'leri,
 * altta not alanı ve "Kaydet & WhatsApp" CTA.
 *
 * Tüm side-effect'ler parent'a (MarketingPanel) bırakılır — bu komponent
 * sadece UI; veriyi prop olarak alır, callback ile yukarı emit eder.
 */
import { useMemo } from "react";
import { Clock, Phone, PhoneCall, X, MessageSquare, Tag } from "lucide-react";
import { CALL_STATUSES } from "./statuses";

function formatTimer(seconds) {
  if (seconds == null) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function MarketingCallSession({
  lead,
  timeLeft,
  callStatus,
  note,
  saving,
  onStatusChange,
  onNoteChange,
  onSave,
  onRelease,
}) {
  const activeCfg = useMemo(
    () => CALL_STATUSES.find((s) => s.key === callStatus),
    [callStatus]
  );
  const noteMissing = activeCfg?.noteRequired && !note.trim();
  const lowOnTime = timeLeft != null && timeLeft < 120;

  return (
    <div className="w-full max-w-md mx-auto pb-4">
      {/* Üst banner — timer + bırak */}
      <div className="flex items-center justify-between mb-4">
        <div
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-mono font-semibold ${
            lowOnTime
              ? "bg-rose-500 text-white animate-pulse"
              : "bg-zinc-900 text-white"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          {formatTimer(timeLeft) || "—"}
        </div>
        <button
          type="button"
          onClick={onRelease}
          className="flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-rose-600 transition-colors px-2 py-1"
        >
          <X className="w-3.5 h-3.5" />
          Bırak
        </button>
      </div>

      {/* Lead başlık kartı */}
      <div className="bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-700 rounded-3xl px-6 py-5 text-white shadow-xl shadow-indigo-300/40">
        {lead.sector && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/20 text-white text-[10px] font-semibold mb-2">
            <Tag className="w-3 h-3" />
            {lead.sector}
          </span>
        )}
        <h2 className="text-xl font-bold leading-tight mb-2 break-words">
          {lead.company_name}
        </h2>
        <a
          href={`tel:${lead.phone}`}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-white/15 hover:bg-white/25 transition-colors backdrop-blur-sm"
        >
          <PhoneCall className="w-4 h-4" />
          <span className="text-sm font-mono">{lead.phone}</span>
        </a>
      </div>

      {/* Status chip grid */}
      <div className="mt-5">
        <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-2 px-1">
          Görüşme Sonucu
        </p>
        <div className="grid grid-cols-2 gap-2">
          {CALL_STATUSES.map(({ key, label, icon: Icon, accent, accentSoft, noteRequired }) => {
            const isActive = callStatus === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  onStatusChange(key);
                  if (!noteRequired) onNoteChange("");
                }}
                className={`flex items-center gap-2 px-3 py-3 rounded-2xl border-2 text-sm font-semibold transition-all active:scale-[0.97] ${
                  isActive
                    ? `${accent} shadow-md`
                    : `bg-white text-zinc-700 border-zinc-200 hover:${accentSoft}`
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="truncate">{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Not alanı */}
      <div className="mt-4">
        <div className="flex items-center justify-between px-1 mb-1.5">
          <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
            <MessageSquare className="w-3 h-3" />
            Görüşme Notu
          </p>
          {activeCfg?.noteRequired && (
            <span className="text-[10px] text-rose-500 font-bold uppercase">Zorunlu</span>
          )}
        </div>
        <textarea
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
          rows={3}
          placeholder={
            activeCfg?.noteRequired
              ? "Lütfen kısa bir not bırak (zorunlu)..."
              : "Görüşmenin kısa özetini yazabilirsin..."
          }
          className={`w-full px-3 py-2.5 rounded-2xl text-sm resize-none border-2 outline-none transition-colors leading-relaxed ${
            noteMissing
              ? "border-rose-300 bg-rose-50 focus:border-rose-400"
              : "border-zinc-200 bg-white focus:border-indigo-400"
          }`}
        />
      </div>

      {/* Kaydet CTA */}
      <div className="mt-5">
        <button
          type="button"
          onClick={onSave}
          disabled={!callStatus || saving || noteMissing}
          className="w-full py-4 rounded-2xl bg-indigo-600 text-white font-bold text-base shadow-lg shadow-indigo-200 hover:bg-indigo-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Kaydediliyor..." : "Kaydet & WhatsApp Aç"}
        </button>
        <p className="text-[11px] text-zinc-400 text-center mt-2 leading-snug">
          Kaydet'e basınca WhatsApp Business açılır, mesaj hazır gelir.
          <br />
          PDF'i 📎 ile sen eklersin.
        </p>
      </div>
    </div>
  );
}
