/**
 * Plann — Marketing Mine View
 *
 * "Aramalarım" sekmesinde pazarlamacının geçmişte temas kurduğu lead'leri
 * gösterir. Üst kısımda durum filtre chip'leri, altında zaman sırasına göre
 * lead listesi. Her kart tıklanabilir: telefon dial'ı veya WhatsApp aç.
 *
 * Backend bütün filtrelenmiş listeyi `tab=mine` ile döndürüyor; bu komponent
 * sadece UI'da sub-filter (status chip) uyguluyor. Geri sayım veya claim
 * mantığı içermez — o akış SweepView + CallSession'a aittir.
 */
import { useMemo, useState } from "react";
import { Phone, MessageCircle, Inbox, Loader2, FileText, Tag, CalendarClock } from "lucide-react";
import { STATUS_CONFIG } from "./statuses";
import { openMarketingFollowUp } from "../../constants/marketing";

const SUBFILTERS = [
  { key: "all",            label: "Tümü"        },
  { key: "interested",     label: "İlgilendi"   },
  { key: "waiting",        label: "Beklemede"   },
  { key: "registered",     label: "Kayıt"       },
  { key: "unreachable",    label: "Ulaşılamadı" },
  { key: "not_interested", label: "İlgisiz"     },
];

function formatRelative(iso) {
  if (!iso) return "";
  try {
    const date = new Date(iso);
    const diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60) return "az önce";
    if (diff < 3600) return `${Math.floor(diff / 60)} dk önce`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} sa önce`;
    return date.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
  } catch (_) {
    return "";
  }
}

export default function MarketingMineView({ leads, loading }) {
  const [subFilter, setSubFilter] = useState("all");

  const filtered = useMemo(() => {
    if (subFilter === "all") return leads;
    return leads.filter((l) => l.status === subFilter);
  }, [leads, subFilter]);

  // Per-status counts for chip badges
  const counts = useMemo(() => {
    const c = { all: leads.length };
    for (const s of leads) c[s.status] = (c[s.status] || 0) + 1;
    return c;
  }, [leads]);

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Sub-filter chips */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
        {SUBFILTERS.map(({ key, label }) => {
          const isActive = subFilter === key;
          const n = counts[key];
          return (
            <button
              key={key}
              type="button"
              onClick={() => setSubFilter(key)}
              className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                isActive
                  ? "bg-zinc-900 text-white"
                  : "bg-white text-zinc-600 ring-1 ring-zinc-200 hover:bg-zinc-50"
              }`}
            >
              {label}
              {typeof n === "number" && n > 0 && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    isActive ? "bg-white/20 text-white" : "bg-zinc-100 text-zinc-500"
                  }`}
                >
                  {n}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Liste */}
      <div className="mt-3 space-y-2">
        {loading && filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-zinc-500">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            <p className="text-sm">Yükleniyor...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-2xl ring-1 ring-zinc-200 px-6 py-12 text-center">
            <Inbox className="w-9 h-9 text-zinc-300 mx-auto mb-2" />
            <p className="text-sm text-zinc-500">
              {subFilter === "all"
                ? "Henüz arama yapmadın."
                : "Bu filtrede lead yok."}
            </p>
          </div>
        ) : (
          filtered.map((lead) => {
            const st = STATUS_CONFIG[lead.status] || STATUS_CONFIG.pool;
            return (
              <article
                key={lead.id}
                className="bg-white rounded-2xl ring-1 ring-zinc-200 px-4 py-3 hover:ring-indigo-200 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-1">
                  <h3 className="font-semibold text-zinc-900 text-sm truncate flex-1 min-w-0">
                    {lead.company_name}
                  </h3>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${st.chip}`}
                  >
                    {st.label}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
                  {lead.sector && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                      <Tag className="w-3 h-3" />
                      {lead.sector}
                    </span>
                  )}
                  <span className="text-[11px] text-zinc-600 font-mono">
                    {lead.phone}
                  </span>
                  {lead.updated_at && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-zinc-400">
                      <CalendarClock className="w-3 h-3" />
                      {formatRelative(lead.updated_at)}
                    </span>
                  )}
                </div>

                {lead.note && (
                  <div className="flex items-start gap-1.5 mb-2">
                    <FileText className="w-3 h-3 text-zinc-300 mt-0.5 flex-shrink-0" />
                    <p className="text-[11px] text-zinc-500 italic line-clamp-2 leading-relaxed">
                      "{lead.note}"
                    </p>
                  </div>
                )}

                <div className="flex items-center gap-2 mt-2">
                  <a
                    href={`tel:${lead.phone}`}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 transition-colors text-xs font-semibold text-zinc-700"
                  >
                    <Phone className="w-3.5 h-3.5" />
                    Tekrar Ara
                  </a>
                  <button
                    type="button"
                    onClick={() => openMarketingFollowUp(lead.phone)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-50 hover:bg-emerald-100 transition-colors text-xs font-semibold text-emerald-700"
                  >
                    <MessageCircle className="w-3.5 h-3.5" />
                    WhatsApp
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
