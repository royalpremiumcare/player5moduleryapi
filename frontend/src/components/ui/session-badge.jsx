import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SessionBadge — Stripe-style soft capsule with dot indicator + tabular numbers.
 *
 * Visual pattern (Plan B from premium UI alternatives):
 *   ●  1·4
 *
 *   - Solda ufak dolu daire (varsayılan emerald-500) — "aktif" sinyali.
 *   - Sayı `tabular-nums` ile sabit genişlikli (1·4, 2·4, ...3·4'ün hizalanması garantili).
 *   - Beyaz zemin + ring + minimal shadow → Wise/Stripe minimalizmi.
 *
 * Tüm session badge'lerde tek-kaynak: Dashboard, Calendar, SessionPlannerDialog,
 * Customers vb. yerlerden bu component import edilir. Tasarım drift olmaz.
 *
 * @param {number} number  - Mevcut seans sırası (1, 2, ...)
 * @param {number} total   - Toplam seans (4, 6, ...)
 * @param {'sm'|'md'} size - Pill boyutu (varsayılan: md)
 * @param {'emerald'|'zinc'} tone - Dot rengi (varsayılan: emerald)
 * @param {boolean} onDark - Koyu zeminli kart üzerinde mi (badge zeminini şeffaflaştırır)
 * @param {string} className
 */
export default function SessionBadge({
  number,
  total,
  size = "md",
  tone = "emerald",
  onDark = false,
  className = "",
}) {
  if (number == null || total == null) return null;

  const sizes = {
    sm: "text-[10px] px-1.5 py-0.5 gap-1",
    md: "text-[10px] sm:text-xs px-2 py-0.5 gap-1.5",
  };

  const dotTone = tone === "zinc"
    ? "bg-zinc-900"
    : "bg-emerald-500";

  const surface = onDark
    ? "text-white bg-white/[0.08] border border-white/15"
    : "text-zinc-700 bg-white border border-zinc-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.04)]";

  return (
    <span
      className={cn(
        "inline-flex items-center font-semibold rounded-full whitespace-nowrap tabular-nums",
        sizes[size] || sizes.md,
        surface,
        className,
      )}
    >
      <span className={cn("inline-block w-1.5 h-1.5 rounded-full shrink-0", dotTone)} />
      <span>
        {number}
        <span className={cn("mx-0.5", onDark ? "text-white/40" : "text-zinc-400")}>·</span>
        {total}
      </span>
    </span>
  );
}
