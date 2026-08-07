import React from "react";
import { useTranslation } from "react-i18next";
import { ArrowUpCircle, X } from "lucide-react";

/**
 * Force-update UI (iki katman):
 *  - level="block": kapatılamayan tam ekran modal (min_supported altı).
 *  - level="soft" : kapatılabilir yumuşak uyarı (latest altı).
 *
 * Tasarım: zinc-900 birincil, rounded-xl kart, minimalist/premium (proje dili).
 * Metinler i18n (`forceUpdate.*`). Native store'a yönlendirme parent'tan gelen
 * `onUpdate` callback'i ile yapılır (App.js `openAppStore`).
 */
const ForceUpdateModal = ({ level, onUpdate, onDismiss }) => {
  const { t } = useTranslation();

  if (level !== "block" && level !== "soft") return null;

  // ── Zorunlu güncelleme: kapatılamaz tam ekran ──
  if (level === "block") {
    return (
      <div className="fixed inset-0 z-[120] bg-black/70 flex items-center justify-center p-4">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-xl p-6 text-center animate-in fade-in zoom-in-95">
          <div className="mx-auto mb-4 w-14 h-14 rounded-full bg-zinc-900 flex items-center justify-center">
            <ArrowUpCircle className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-lg font-bold text-zinc-900 mb-2">
            {t("forceUpdate.blockTitle")}
          </h2>
          <p className="text-sm text-zinc-600 mb-6 leading-relaxed">
            {t("forceUpdate.blockBody")}
          </p>
          <button
            onClick={onUpdate}
            className="w-full h-12 bg-zinc-900 hover:bg-black text-white font-bold rounded-xl shadow-lg transition-all active:scale-[0.98]"
          >
            {t("forceUpdate.updateNow")}
          </button>
        </div>
      </div>
    );
  }

  // ── Yumuşak uyarı: alt banner, kapatılabilir ──
  return (
    <div className="fixed inset-x-0 bottom-0 z-[110] p-4 pointer-events-none">
      <div
        className="mx-auto max-w-md bg-white border border-zinc-200 rounded-xl shadow-lg p-4 flex items-center gap-3 pointer-events-auto animate-in slide-in-from-bottom"
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="shrink-0 w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center">
          <ArrowUpCircle className="w-5 h-5 text-zinc-900" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-zinc-900">
            {t("forceUpdate.softTitle")}
          </p>
          <p className="text-xs text-zinc-500 truncate">
            {t("forceUpdate.softBody")}
          </p>
        </div>
        <button
          onClick={onUpdate}
          className="shrink-0 h-9 px-4 bg-zinc-900 hover:bg-black text-white text-sm font-bold rounded-lg transition-all active:scale-95"
        >
          {t("forceUpdate.update")}
        </button>
        <button
          onClick={onDismiss}
          aria-label={t("forceUpdate.later")}
          className="shrink-0 w-8 h-8 flex items-center justify-center text-zinc-400 hover:text-zinc-700 rounded-lg"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ForceUpdateModal;
