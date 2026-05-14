/**
 * Plann — Marketing Sweep View
 *
 * Pool tab'da tek bir lead'i full-card olarak gösterir. Pazarlamacı
 * büyük "ARA" butonuna basınca lead claim'lenir ve telefon dialer
 * tetiklenir; ana sayfa CallSession ekranına geçer.
 *
 * Boş havuz, yükleme ve "next-up" preview state'leri burada yönetilir.
 * Üst kısımda hangi sıradaki lead olduğu küçük bir counter ile gösterilir.
 */
import { Phone, Building2, Tag, Inbox, Loader2, ChevronRight, FileText } from "lucide-react";

export default function MarketingSweepView({
  leads,
  loading,
  claiming,
  onClaim,
  selectedSector,
  selectedBatch,
  batches,
}) {
  // Pool sıralı geliyor — ilk lead aktif kart, sıradaki preview olarak görünür.
  const current = leads[0] || null;
  const upNext = leads[1] || null;

  const activeBatchName = selectedBatch
    ? batches.find((b) => b.id === selectedBatch)?.batch_name
    : null;

  if (loading && leads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-zinc-500">
        <Loader2 className="w-7 h-7 animate-spin text-indigo-500" />
        <p className="text-sm">Leadler yükleniyor...</p>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 px-6 text-center">
        <div className="w-20 h-20 rounded-full bg-emerald-50 flex items-center justify-center">
          <Inbox className="w-10 h-10 text-emerald-500" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-zinc-900">Havuz Boş</h3>
          <p className="text-sm text-zinc-500 mt-1 max-w-xs leading-relaxed">
            {selectedSector || selectedBatch
              ? "Seçili filtre için aranacak lead kalmadı. Filtreyi değiştir veya temizle."
              : "Şu an aranacak lead yok. Daha sonra tekrar dene."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Sıra göstergesi */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-[11px] uppercase tracking-wider font-semibold text-zinc-400">
          Sıradaki Arama
        </span>
        <span className="text-[11px] text-zinc-400 font-medium">
          {leads.length} lead kuyrukta
        </span>
      </div>

      {/* Ana lead kartı */}
      <article className="bg-white rounded-3xl shadow-xl shadow-indigo-100/40 ring-1 ring-indigo-100 overflow-hidden">
        {/* Üst bant — sektör + kampanya */}
        <div className="px-6 pt-6 pb-3 flex items-center justify-between gap-3">
          {current.sector ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-700">
              <Tag className="w-3 h-3" />
              {current.sector}
            </span>
          ) : <span />}
          {activeBatchName || current.batch_name ? (
            <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold truncate max-w-[160px]">
              {activeBatchName || current.batch_name}
            </span>
          ) : null}
        </div>

        {/* Şirket adı */}
        <div className="px-6 pb-2">
          <h2 className="text-2xl font-bold text-zinc-900 leading-tight break-words">
            {current.company_name}
          </h2>
        </div>

        {/* Telefon */}
        <div className="px-6 pb-4">
          <div className="flex items-center gap-2 text-zinc-600">
            <Phone className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-mono">{current.phone}</span>
          </div>
        </div>

        {/* Geçmiş not (varsa) */}
        {current.note && (
          <div className="mx-6 mb-4 rounded-xl bg-amber-50 border border-amber-100 p-3">
            <div className="flex items-start gap-2">
              <FileText className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800 italic leading-relaxed line-clamp-3">
                "{current.note}"
              </p>
            </div>
          </div>
        )}

        {/* Büyük ARA butonu */}
        <div className="px-6 pb-6">
          <button
            type="button"
            onClick={() => onClaim(current)}
            disabled={claiming === current.id}
            className="w-full flex items-center justify-center gap-3 py-4 rounded-2xl bg-indigo-600 text-white font-semibold text-base shadow-lg shadow-indigo-200 hover:bg-indigo-700 active:scale-[0.98] transition-all disabled:opacity-60 disabled:cursor-wait"
          >
            {claiming === current.id ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Phone className="w-5 h-5" />
            )}
            {claiming === current.id ? "Bağlanıyor..." : "Ara"}
          </button>
          <p className="text-[11px] text-zinc-400 text-center mt-2">
            Numara aranır ve 15dk seninle kilitlenir.
          </p>
        </div>
      </article>

      {/* Sıradaki — küçük preview */}
      {upNext && (
        <div className="mt-4 rounded-2xl bg-white/60 ring-1 ring-zinc-200 px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-zinc-100 flex items-center justify-center flex-shrink-0">
            <Building2 className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold">
              Sırada
            </p>
            <p className="text-sm font-semibold text-zinc-700 truncate">
              {upNext.company_name}
            </p>
          </div>
          <ChevronRight className="w-4 h-4 text-zinc-300" />
        </div>
      )}
    </div>
  );
}
