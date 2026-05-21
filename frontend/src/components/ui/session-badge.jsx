import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SessionBadge — Mini segmented progress bar (Linear/Notion tarzı).
 *
 * Visual pattern:
 *   ▪▪▫▫  1/4
 *
 *   - Tamamlanan seanslar dolu segment, kalanlar açık gri.
 *   - Yanında kompakt tabular sayı.
 *
 * @param {number} number  - Mevcut seans sırası (1, 2, ...)
 * @param {number} total   - Toplam seans (4, 6, ...)
 * @param {'sm'|'md'} size - Boyut (varsayılan: md)
 * @param {boolean} onDark - Koyu zeminli kart üzerinde mi
 * @param {string} className
 */
export default function SessionBadge({
  number,
  total,
  size = "md",
  onDark = false,
  className = "",
}) {
  if (number == null || total == null) return null;

  const barSizes = {
    sm: "h-1.5 w-2",
    md: "h-1.5 w-2.5",
  };

  const labelSizes = {
    sm: "text-[11px]",
    md: "text-xs sm:text-[13px]",
  };

  const gapSizes = {
    sm: "gap-2",
    md: "gap-2",
  };

  const segmentGap = {
    sm: "gap-0.5",
    md: "gap-1",
  };

  const filledTone = onDark ? "bg-white" : "bg-zinc-900";
  const emptyTone = onDark ? "bg-white/25" : "bg-zinc-200";
  const textTone = onDark ? "text-white/70" : "text-zinc-500";

  const barClass = barSizes[size] || barSizes.md;
  const segmentCount = Math.min(Math.max(total, 1), 10);

  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap tabular-nums",
        gapSizes[size] || gapSizes.md,
        className,
      )}
    >
      <span className={cn("inline-flex items-center", segmentGap[size] || segmentGap.md)} aria-hidden="true">
        {Array.from({ length: segmentCount }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "rounded-full shrink-0",
              barClass,
              i < number ? filledTone : emptyTone,
            )}
          />
        ))}
      </span>
      <span className={cn("font-semibold tracking-tight", labelSizes[size] || labelSizes.md, textTone)}>
        {number}/{total}
      </span>
    </span>
  );
}
