/**
 * Plann — Marketing call-disposition constants.
 *
 * Shared by sweep view, call session, and history list so the labels,
 * colors and "note required" rules stay identical across screens.
 */
import { CheckCircle, PhoneOff, XCircle, Pause, Star, Sparkles } from "lucide-react";

/**
 * Badge style for past leads in the history view.
 * `chip` is a single class string (background + text).
 */
export const STATUS_CONFIG = {
  pool:           { label: "Havuzda",     chip: "bg-zinc-100 text-zinc-500" },
  claimed:        { label: "Arıyor...",   chip: "bg-amber-100 text-amber-700" },
  interested:     { label: "İlgilendi",   chip: "bg-emerald-100 text-emerald-700" },
  unreachable:    { label: "Ulaşılamadı", chip: "bg-zinc-200 text-zinc-700" },
  not_interested: { label: "İlgisiz",     chip: "bg-rose-100 text-rose-700" },
  waiting:        { label: "Beklemede",   chip: "bg-amber-100 text-amber-800" },
  registered:     { label: "Kayıt Oldu",  chip: "bg-indigo-100 text-indigo-700" },
};

/**
 * Selectable dispositions in the call session screen. Order matters —
 * the most-likely outcome ("İlgilendi") comes first; destructive
 * outcomes ("İlgisiz") are last. `noteRequired` forces the user to
 * type a note before saving.
 *
 * `accent` defines a Tailwind classNames for the active selection
 * state (large pill on the call session screen).
 */
export const CALL_STATUSES = [
  {
    key: "interested",
    label: "İlgilendi",
    icon: CheckCircle,
    accent: "bg-emerald-600 text-white border-emerald-600",
    accentSoft: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  {
    key: "waiting",
    label: "Beklemede",
    icon: Pause,
    accent: "bg-amber-500 text-white border-amber-500",
    accentSoft: "bg-amber-50 text-amber-700 border-amber-200",
    noteRequired: true,
  },
  {
    key: "unreachable",
    label: "Ulaşılamadı",
    icon: PhoneOff,
    accent: "bg-zinc-700 text-white border-zinc-700",
    accentSoft: "bg-zinc-50 text-zinc-700 border-zinc-200",
  },
  {
    key: "not_interested",
    label: "İlgisiz",
    icon: XCircle,
    accent: "bg-rose-600 text-white border-rose-600",
    accentSoft: "bg-rose-50 text-rose-700 border-rose-200",
    noteRequired: true,
  },
  {
    key: "registered",
    label: "Kayıt Oldu",
    icon: Star,
    accent: "bg-indigo-600 text-white border-indigo-600",
    accentSoft: "bg-indigo-50 text-indigo-700 border-indigo-200",
  },
];

export const SuccessIcon = Sparkles;
