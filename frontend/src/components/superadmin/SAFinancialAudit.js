import { useState, useEffect, useCallback } from "react";
import api from "../../api/api";
import { toast } from "sonner";
import {
  FileSearch, RefreshCw, ChevronLeft, ChevronRight, Search, X,
  CreditCard, Repeat, Banknote, Layers, AlertTriangle, Building2,
  ArrowRightLeft, Clock, Wallet, Settings2, User, Copy, Check,
  Receipt, TrendingUp, Store,
} from "lucide-react";
import { formatLocal, formatWithTz } from "../../lib/timezone";

// ---------------------------------------------------------------------------
// Para / oran biçimlendirme
// ---------------------------------------------------------------------------
const formatMoney = (minor, currency = "GBP") => {
  if (minor == null) return "—";
  const val = (Math.abs(minor) / 100).toLocaleString(
    currency === "GBP" ? "en-GB" : "tr-TR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
  );
  const sign = minor < 0 ? "-" : "";
  return currency === "GBP" ? `${sign}£${val}` : `${sign}${val} ₺`;
};

const bpsToPct = (bps) => (bps == null ? "—" : `%${(bps / 100).toFixed(2)}`);

// Sabit ücreti işlemden türet: toplam komisyon − (oran × hizmet bedeli).
// Küçük tutarlarda sabit ücret efektif oranı yükseltir; bunu ayrı göstermek için.
const derivedFixed = (r) => {
  const bps = r.fee_rate_bps;
  const svc = r.service_price_minor;
  const fee = r.platform_fee_minor ?? r.fee_amount_minor;
  if (bps == null || svc == null || fee == null) return null;
  const variable = Math.round((bps / 10000) * svc);
  const fixed = fee - variable;
  return fixed > 0 ? fixed : 0;
};

// ---------------------------------------------------------------------------
// Türkçe etiket sözlükleri (ham İngilizce değerleri kullanıcıya çevirir)
// ---------------------------------------------------------------------------
const STATE_LABELS = {
  pending:   "Ödeme Bekliyor",
  created:   "Oluşturuldu",
  captured:  "Tahsil Edildi",
  settled:   "Bankaya Geçti",
  available: "Kullanılabilir",
  reserved:  "Rezerve",
  converted: "TL'ye Çevrildi",
  paid_out:  "İşletmeye Ödendi",
  refunded:  "İade Edildi",
  disputed:  "İtiraz Edildi",
  frozen:    "Donduruldu",
  failed:    "Başarısız",
  cancelled: "İptal Edildi",
  canceled:  "İptal Edildi",
  expired:   "Süresi Doldu",
  // conversion durumları
  converting: "Çevriliyor",
  needs_manual: "Manuel Gerekli",
  completed: "Tamamlandı",
};

const STATE_STYLES = {
  pending:   "bg-amber-50 text-amber-700 border-amber-200",
  created:   "bg-zinc-100 text-zinc-600 border-zinc-200",
  captured:  "bg-blue-50 text-blue-700 border-blue-200",
  settled:   "bg-indigo-50 text-indigo-700 border-indigo-200",
  available: "bg-sky-50 text-sky-700 border-sky-200",
  reserved:  "bg-violet-50 text-violet-700 border-violet-200",
  converted: "bg-teal-50 text-teal-700 border-teal-200",
  completed: "bg-teal-50 text-teal-700 border-teal-200",
  paid_out:  "bg-emerald-50 text-emerald-700 border-emerald-200",
  refunded:  "bg-zinc-100 text-zinc-600 border-zinc-200",
  disputed:  "bg-red-50 text-red-700 border-red-200",
  frozen:    "bg-red-50 text-red-700 border-red-200",
  failed:    "bg-red-50 text-red-700 border-red-200",
  needs_manual: "bg-orange-50 text-orange-700 border-orange-200",
  cancelled: "bg-zinc-100 text-zinc-500 border-zinc-200",
  canceled:  "bg-zinc-100 text-zinc-500 border-zinc-200",
  expired:   "bg-zinc-100 text-zinc-500 border-zinc-200",
};

const PAYMENT_TYPE_LABELS = {
  business: "İşletme Ödemesi",
  subscription: "Abonelik",
};
const CHANNEL_LABELS = {
  appointment: "Randevu",
  multi_service: "Çoklu Hizmet",
  payment_link: "Ödeme Linki",
};
const FEE_PREF_LABELS = {
  seller_pays: "Komisyonu İşletme Öder",
  buyer_pays: "Komisyonu Müşteri Öder",
};

const stateLabel = (s) => STATE_LABELS[s] || s || "—";
const typeLabel = (t) => PAYMENT_TYPE_LABELS[t] || t || "—";
const channelLabel = (c) => CHANNEL_LABELS[c] || c || "";
const feePrefLabel = (f) => FEE_PREF_LABELS[f] || f || "—";

// Filtre seçenekleri
const PAYMENT_TYPES = [
  { v: "", l: "Tüm ödeme türleri" },
  { v: "business", l: "İşletme Ödemesi" },
  { v: "subscription", l: "Abonelik" },
];
const STATES = [
  { v: "", l: "Tüm tahsilatlar (varsayılan)" },
  { v: "captured", l: "Tahsil Edildi" },
  { v: "settled", l: "Bankaya Geçti" },
  { v: "available", l: "Kullanılabilir" },
  { v: "converted", l: "TL'ye Çevrildi" },
  { v: "paid_out", l: "İşletmeye Ödendi" },
  { v: "refunded", l: "İade Edildi" },
];
const MARKETS = [
  { v: "", l: "Tüm pazarlar" },
  { v: "GBP", l: "İngiltere (£)" },
  { v: "TRY", l: "Türkiye (₺)" },
];
const CONVERTED = [
  { v: "", l: "Dönüşüm: hepsi" },
  { v: "true", l: "Çevrilenler" },
  { v: "false", l: "Çevrilmeyenler" },
];

// ---------------------------------------------------------------------------
// UI atomları
// ---------------------------------------------------------------------------
function StateBadge({ state }) {
  const cls = STATE_STYLES[state] || "bg-zinc-100 text-zinc-600 border-zinc-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap ${cls}`}>
      {stateLabel(state)}
    </span>
  );
}

function LoadingBlock() {
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-10 text-center text-zinc-400">
      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-500 mx-auto mb-3" />
      Yükleniyor…
    </div>
  );
}

function EmptyState({ icon: Icon, label }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-10 text-center text-zinc-400">
      <Icon className="h-9 w-9 mx-auto mb-3 opacity-40" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard?.writeText(String(text));
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="p-1 rounded hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
      title="Kopyala"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function Field({ label, value, mono = false, copy = false }) {
  const empty = value == null || value === "" || value === "—";
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-zinc-100 last:border-0">
      <span className="text-xs text-zinc-500 flex-shrink-0">{label}</span>
      <span className="flex items-center gap-1 min-w-0">
        <span className={`text-xs text-right break-all ${empty ? "text-zinc-300" : "text-zinc-900"} ${mono ? "font-mono" : "font-medium"}`}>
          {empty ? "—" : value}
        </span>
        {copy && !empty && <CopyButton text={value} />}
      </span>
    </div>
  );
}

function Section({ icon: Icon, title, children, badge }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-7 w-7 rounded-lg bg-zinc-100 flex items-center justify-center">
          <Icon className="h-4 w-4 text-zinc-600" />
        </div>
        <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
        <div className="ml-auto">{badge}</div>
      </div>
      {children}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub, accent = "zinc" }) {
  const accents = {
    zinc: "text-zinc-900",
    emerald: "text-emerald-600",
    teal: "text-teal-600",
    blue: "text-blue-600",
  };
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className="h-4 w-4 text-zinc-400" />
        <p className="text-xs text-zinc-500">{label}</p>
      </div>
      <p className={`text-lg font-bold ${accents[accent] || accents.zinc}`}>{value}</p>
      {sub && <p className="text-xs text-zinc-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detay çekmecesi — tam yaşam döngüsü
// ---------------------------------------------------------------------------
function AuditDrawer({ txId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get(`/superadmin/financial/audit/transaction/${txId}`);
        if (alive) setData(res.data);
      } catch (err) {
        toast.error(err.response?.data?.detail || "İşlem detayı yüklenemedi");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [txId]);

  const tx = data?.transaction || {};
  const cur = tx.base_currency || "GBP";
  const snap = data?.pricing_snapshot || {};
  const conv = data?.conversion;
  const recon = data?.stripe_payout_reconciliation;
  const batch = data?.payout_batch;
  const quote = data?.wise_quote;
  const wallet = data?.wallet || {};
  const computed = data?.computed || {};
  const drift = data?.settings_drift || {};
  const current = data?.current_settings || {};

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-zinc-50 z-50 flex flex-col shadow-2xl">
        {/* Başlık */}
        <div className="flex items-center justify-between px-5 py-4 bg-white border-b border-zinc-200 flex-shrink-0">
          <div className="min-w-0">
            <p className="text-xs text-zinc-500">İşlem Denetimi</p>
            <div className="flex items-center gap-1">
              <p className="text-sm font-mono font-semibold text-zinc-900 truncate">{txId}</p>
              <CopyButton text={txId} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!loading && <StateBadge state={tx.state} />}
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-500">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <LoadingBlock />
          ) : (
            <>
              {/* İşletme & Müşteri */}
              <Section icon={Building2} title="İşletme & Müşteri">
                <Field label="İşletme" value={data?.organization?.company_name} />
                <Field label="İşletme No" value={data?.organization?.id} mono copy />
                {tx.customer_name && <Field label="Müşteri Adı" value={tx.customer_name} />}
                {tx.customer_phone && <Field label="Müşteri Telefonu" value={tx.customer_phone} />}
                <Field label="Oluşturulma" value={formatWithTz(tx.created_at)} />
                <Field label="Ödeme Türü" value={typeLabel(tx.payment_type)} />
                <Field label="Kanal" value={channelLabel(tx.payment_channel) || "—"} />
                <Field label="Pazar" value={cur === "GBP" ? "İngiltere (£)" : "Türkiye (₺)"} />
                {tx.appointment_id && <Field label="Randevu No" value={tx.appointment_id} mono copy />}
              </Section>

              {/* Tutarlar */}
              <Section icon={Banknote} title="Tutarlar">
                <Field label="Hizmet Bedeli" value={formatMoney(tx.service_price_minor, cur)} />
                <Field label="Müşterinin Ödediği" value={formatMoney(tx.customer_price_minor, cur)} />
                <Field label="İşletmenin Neti (cüzdana geçen)" value={formatMoney(tx.merchant_net_minor, cur)} />
                <Field label="PLANN Komisyonu" value={formatMoney(tx.platform_fee_minor ?? tx.fee_amount_minor, cur)} />
                <Field
                  label="Efektif Komisyon (müşteri ödemesine göre)"
                  value={computed.effective_commission_pct_on_customer != null ? `%${computed.effective_commission_pct_on_customer}` : "—"}
                />
                <Field
                  label="Efektif Komisyon (hizmet bedeline göre)"
                  value={computed.effective_commission_pct_on_service != null ? `%${computed.effective_commission_pct_on_service}` : "—"}
                />
                <Field label="Brüte Tamamlama (gross-up)" value={tx.gross_up_applied ? "Evet" : "Hayır"} />
                {(() => {
                  const f = derivedFixed({ fee_rate_bps: tx.fee_rate_bps, service_price_minor: tx.service_price_minor, platform_fee_minor: tx.platform_fee_minor ?? tx.fee_amount_minor });
                  if (!f) return null;
                  return (
                    <div className="mt-2 text-xs text-zinc-500 bg-zinc-50 border border-zinc-200 rounded-lg p-2 leading-relaxed">
                      <b>Neden efektif oran nominalden yüksek?</b> Komisyon = kademe oranı (<b>{bpsToPct(tx.fee_rate_bps)}</b>) × hizmet bedeli
                      {" + "}<b>{formatMoney(f, cur)}</b> sabit ücret. Küçük tutarlarda sabit ücret oranı yükseltir.
                      {tx.fee_preference === "buyer_pays"
                        ? " Bu işlemde komisyonu müşteri öder — işletmenin netine yansımaz."
                        : " Bu tutar işletmenin netinden düşülür."}
                    </div>
                  );
                })()}
              </Section>

              {/* Komisyon anlık görüntüsü */}
              <Section
                icon={Settings2}
                title="Komisyon Ayarı — Anlık Görüntü"
                badge={(drift.tier_changed || drift.fee_preference_changed) ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    <AlertTriangle className="h-3 w-3" /> Ayarlar değişmiş
                  </span>
                ) : null}
              >
                <Field label="Komisyon Kademesi" value={snap.tier || tx.commission_tier} />
                <Field label="Komisyon Oranı" value={bpsToPct(snap.commission_rate_bps ?? tx.fee_rate_bps)} />
                <Field label="Sabit Ücret" value={formatMoney(snap.commission_fixed_fee_minor ?? tx.commission_fixed_fee_minor, cur)} />
                <Field label="Ödeme Modu" value={feePrefLabel(snap.fee_preference || tx.fee_preference)} />
                <Field label="Kayıt Zamanı" value={snap.captured_at ? formatLocal(snap.captured_at) : "—"} />
                {(drift.tier_changed || drift.fee_preference_changed) && (
                  <div className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">
                    Güncel ayar: kademe <b>{current.tier || "—"}</b>, mod <b>{feePrefLabel(current.fee_preference)}</b>.
                    Bu işlem, oluşturulduğu andaki değerlerle işlenir (tek doğruluk kaynağı).
                  </div>
                )}
              </Section>

              {/* Stripe */}
              <Section icon={CreditCard} title="Stripe — Tahsilat & Bankaya Geçiş">
                <Field label="Ödeme Oturumu (Checkout)" value={tx.stripe_checkout_session_id} mono copy />
                <Field label="Ödeme Niyeti (PaymentIntent)" value={tx.stripe_payment_intent_id} mono copy />
                <Field label="Tahsilat No (Charge)" value={tx.stripe_charge_id} mono copy />
                <Field label="Bakiye Hareketi No" value={tx.stripe_balance_transaction_id} mono copy />
                <Field label="Stripe Ücreti (tahmini)" value={formatMoney(tx.stripe_fee_minor, cur)} />
                <Field label="Stripe Ücreti (gerçek, £)" value={formatMoney(tx.stripe_fee_gbp_minor, "GBP")} />
                <Field label="Bankaya Geçen Brüt (£)" value={formatMoney(tx.gross_amount_gbp_minor, "GBP")} />
                <Field label="Bankaya Geçen Net (£)" value={formatMoney(tx.amount_settled_gbp_minor, "GBP")} />
                <Field label="Banka Aktarım No (Payout)" value={tx.stripe_payout_id} mono copy />
              </Section>

              {/* Payout mutabakatı */}
              {recon && (
                <Section icon={ArrowRightLeft} title="Stripe Aktarım Mutabakatı">
                  <Field label="Aktarım No (Payout)" value={recon.stripe_payout_id || recon.id} mono copy />
                  <Field label="İşletme İşlem Sayısı" value={recon.business_count ?? recon.matched_count} />
                  <Field label="İşletme Toplamı (£)" value={formatMoney(recon.business_total_minor, "GBP")} />
                  <Field label="Abonelik/Diğer (£)" value={formatMoney(recon.subscription_total_minor ?? recon.other_total_minor, "GBP")} />
                  <Field label="Aktarım Toplamı (£)" value={formatMoney(recon.payout_total_minor, "GBP")} />
                  <Field label="Mutabakat Zamanı" value={recon.created_at ? formatLocal(recon.created_at) : "—"} />
                </Section>
              )}

              {/* Wise dönüşümü */}
              <Section
                icon={Repeat}
                title="Wise Dönüşümü (£ → ₺)"
                badge={conv ? <StateBadge state={conv.status} /> : (
                  <span className="text-xs text-zinc-400">kayıt yok</span>
                )}
              >
                {conv ? (
                  <>
                    <Field label="Kaynak (£)" value={formatMoney(conv.source_gbp_minor, "GBP")} />
                    <Field label="Hedef (₺)" value={formatMoney(conv.target_try_minor, "TRY")} />
                    <Field label="Kur" value={conv.rate_micro ? (conv.rate_micro / 1_000_000).toFixed(4) : "—"} />
                    <Field label="Wise Ücreti" value={formatMoney(conv.wise_fee_minor, "GBP")} />
                    <Field label="Wise Teklif No (Quote)" value={conv.wise_quote_id} mono copy />
                    <Field label="Wise Hareket No (Movement)" value={conv.wise_movement_id} mono copy />
                    <Field label="Deneme Sayısı" value={conv.retry_count ?? 0} />
                    {conv.last_error && <Field label="Son Hata" value={conv.last_error} />}
                    <Field label="Güncelleme" value={conv.updated_at ? formatLocal(conv.updated_at) : "—"} />
                  </>
                ) : (
                  <p className="text-xs text-zinc-400">
                    {tx.converted ? "İşlem çevrilmiş görünüyor ancak dönüşüm kaydı bulunamadı." :
                     tx.payment_type === "subscription" ? "Abonelik geliri — £ olarak kalır, çevrilmez." :
                     "Henüz dönüşüm yapılmadı."}
                  </p>
                )}
                {tx.amount_settled_try_minor != null && (
                  <Field label="Yerleşen Tutar (₺)" value={formatMoney(tx.amount_settled_try_minor, "TRY")} />
                )}
              </Section>

              {/* Toplu ödeme */}
              <Section
                icon={Layers}
                title="Toplu Ödeme (Çarşamba)"
                badge={batch ? <StateBadge state={batch.status} /> : <span className="text-xs text-zinc-400">kayıt yok</span>}
              >
                {batch ? (
                  <>
                    <Field label="Toplu Ödeme No" value={batch.id} mono copy />
                    <Field label="Durum" value={stateLabel(batch.status)} />
                    <Field label="Toplu Ödeme Tutarı" value={formatMoney(batch.total_amount_minor ?? batch.total_minor, batch.base_currency || "TRY")} />
                    <Field label="İşlem Sayısı" value={(batch.item_transaction_ids || []).length || batch.item_count} />
                    <Field label="Wise Transfer No" value={tx.wise_transfer_id || batch.wise_transfer_id} mono copy />
                    <Field label="Oluşturulma" value={batch.created_at ? formatLocal(batch.created_at) : "—"} />
                    {batch.paid_at && <Field label="Ödenme" value={formatLocal(batch.paid_at)} />}
                  </>
                ) : (
                  <p className="text-xs text-zinc-400">Bu işlem henüz bir toplu ödemeye dahil edilmedi.</p>
                )}
                {quote && (
                  <div className="mt-2 pt-2 border-t border-zinc-100">
                    <Field label="Wise Teklif No" value={quote.wise_quote_id || quote.id} mono copy />
                    <Field label="Teklif Kuru" value={quote.rate} />
                  </div>
                )}
              </Section>

              {/* Cüzdan */}
              <Section icon={Wallet} title="İşletme Cüzdanı (güncel)">
                <Field label="Bekleyen Bakiye" value={formatMoney(wallet.pending_balance_minor, wallet.base_currency || cur)} />
                <Field label="Kullanılabilir Bakiye" value={formatMoney(wallet.available_balance_minor, wallet.base_currency || cur)} />
                <Field label="£ Havuz Bakiyesi" value={formatMoney(wallet.pool_balance_gbp_minor, "GBP")} />
              </Section>

              {/* Zaman çizelgesi */}
              <Section icon={Clock} title="Durum Geçmişi">
                <div className="space-y-2">
                  {(data?.state_history || []).length === 0 && (
                    <p className="text-xs text-zinc-400">Geçmiş kaydı yok.</p>
                  )}
                  {(data?.state_history || []).map((h, i) => (
                    <div key={i} className="flex items-center gap-3 text-xs">
                      <span className="text-zinc-400 font-mono w-40 flex-shrink-0">
                        {h.timestamp ? formatLocal(h.timestamp) : "—"}
                      </span>
                      <StateBadge state={h.state} />
                      {h.trigger && <span className="text-zinc-400">({h.trigger})</span>}
                    </div>
                  ))}
                </div>
              </Section>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Ana ekran
// ---------------------------------------------------------------------------
export default function SAFinancialAudit() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(50);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);

  // Filtreler
  const [q, setQ] = useState("");
  const [qInput, setQInput] = useState("");
  const [state, setState] = useState("");
  const [paymentType, setPaymentType] = useState("");
  const [market, setMarket] = useState("");
  const [converted, setConverted] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const buildParams = useCallback(() => {
    const params = { page, per_page: perPage };
    if (q.trim()) params.q = q.trim();
    if (state) params.state = state;
    if (paymentType) params.payment_type = paymentType;
    if (market) params.market = market;
    if (converted) params.converted = converted;
    if (startDate) params.start_iso = startDate + "T00:00:00Z";
    if (endDate) params.end_iso = endDate + "T23:59:59Z";
    return params;
  }, [page, perPage, q, state, paymentType, market, converted, startDate, endDate]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/financial/audit/transactions", { params: buildParams() });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Denetim listesi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const loadSummary = useCallback(async () => {
    try {
      const { page: _p, per_page: _pp, ...rest } = buildParams();
      const res = await api.get("/superadmin/financial/audit/summary", { params: rest });
      setSummary(res.data);
    } catch {
      /* özet opsiyonel */
    }
  }, [buildParams]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadSummary(); }, [loadSummary]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const applySearch = () => { setPage(1); setQ(qInput); };
  const resetFilters = () => {
    setQInput(""); setQ(""); setState(""); setPaymentType("");
    setMarket(""); setConverted(""); setStartDate(""); setEndDate("");
    setPage(1);
  };

  const activeFilterCount = [q, state, paymentType, market, converted, startDate, endDate].filter(Boolean).length;

  return (
    <div className="min-h-full bg-zinc-50 p-4 md:p-6 space-y-5">
      {/* Başlık */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-zinc-900 flex items-center justify-center flex-shrink-0">
            <FileSearch className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">Finansal Denetim Merkezi</h2>
            <p className="text-xs text-zinc-500">
              Her ödemenin oluşturulmadan işletmeye ödemeye kadar tüm yaşam döngüsü, komisyon ayarları ve maliyetler.
            </p>
          </div>
        </div>
        <button
          onClick={() => { load(); loadSummary(); }}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-black text-white text-sm font-medium transition-colors active:scale-[0.98]"
        >
          <RefreshCw className="h-4 w-4" /> Yenile
        </button>
      </div>

      {/* Özet kartları */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={Receipt} label="Toplam İşlem" value={(summary.total || 0).toLocaleString("tr-TR")} />
          {Object.entries(summary.by_currency || {}).map(([curr, m]) => (
            <StatCard
              key={curr}
              icon={curr === "GBP" ? TrendingUp : Store}
              label={`${curr === "GBP" ? "İngiltere (£)" : "Türkiye (₺)"} • ${m.count} işlem`}
              value={formatMoney(m.customer_total, curr)}
              sub={`Komisyon: ${formatMoney(m.platform_fee_total, curr)}${curr === "GBP" ? ` • Çevrilen: ${m.converted_count}/${m.count}` : ""}`}
              accent={curr === "GBP" ? "teal" : "emerald"}
            />
          ))}
        </div>
      )}

      {/* Durum çipleri */}
      {summary?.by_state && Object.keys(summary.by_state).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(summary.by_state).map(([st, cnt]) => (
            <button
              key={st}
              onClick={() => { setState(st === state ? "" : st); setPage(1); }}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${
                state === st ? "ring-2 ring-zinc-900 ring-offset-1 " : ""
              }${STATE_STYLES[st] || "bg-zinc-100 text-zinc-600 border-zinc-200"}`}
            >
              {stateLabel(st)} <span className="opacity-70">({cnt})</span>
            </button>
          ))}
        </div>
      )}

      {/* Filtreler */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row gap-2">
          <div className="flex-1 flex items-center gap-2 px-3 py-2 border border-zinc-300 rounded-lg focus-within:ring-2 focus-within:ring-zinc-900 focus-within:border-zinc-900 transition-all">
            <Search className="h-4 w-4 text-zinc-400" />
            <input
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
              placeholder="İşlem no, tahsilat no, aktarım no, telefon, randevu…"
              className="flex-1 text-sm outline-none bg-transparent"
            />
          </div>
          <button onClick={applySearch} className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-black text-white text-sm font-medium transition-colors active:scale-[0.98]">
            Ara
          </button>
          <button onClick={resetFilters} className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700 hover:bg-zinc-50 text-sm transition-colors">
            Temizle{activeFilterCount ? ` (${activeFilterCount})` : ""}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <select value={state} onChange={(e) => { setState(e.target.value); setPage(1); }} className="px-2.5 py-2 border border-zinc-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900">
            {STATES.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          <select value={paymentType} onChange={(e) => { setPaymentType(e.target.value); setPage(1); }} className="px-2.5 py-2 border border-zinc-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900">
            {PAYMENT_TYPES.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          <select value={market} onChange={(e) => { setMarket(e.target.value); setPage(1); }} className="px-2.5 py-2 border border-zinc-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900">
            {MARKETS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          <select value={converted} onChange={(e) => { setConverted(e.target.value); setPage(1); }} className="px-2.5 py-2 border border-zinc-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900">
            {CONVERTED.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          <div className="flex items-center gap-1">
            <input type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setPage(1); }} className="w-full px-2 py-2 border border-zinc-300 rounded-lg text-xs bg-white" />
            <input type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setPage(1); }} className="w-full px-2 py-2 border border-zinc-300 rounded-lg text-xs bg-white" />
          </div>
        </div>
      </div>

      {/* Tablo */}
      {loading ? (
        <LoadingBlock />
      ) : items.length === 0 ? (
        <EmptyState icon={FileSearch} label="Filtreye uygun işlem bulunamadı." />
      ) : (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-zinc-50 text-zinc-500 text-xs border-b border-zinc-200">
                  <th className="text-left font-medium px-3 py-3">Tarih</th>
                  <th className="text-left font-medium px-3 py-3">İşletme</th>
                  <th className="text-left font-medium px-3 py-3">Müşteri</th>
                  <th className="text-left font-medium px-3 py-3">Tür / Kanal</th>
                  <th className="text-right font-medium px-3 py-3">Tahsilat</th>
                  <th className="text-right font-medium px-3 py-3">İşletme Neti</th>
                  <th className="text-right font-medium px-3 py-3">Komisyon</th>
                  <th className="text-center font-medium px-3 py-3">Komisyon Oranı</th>
                  <th className="text-center font-medium px-3 py-3">Dönüşüm</th>
                  <th className="text-center font-medium px-3 py-3">Durum</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedTx(r.id)}
                    className="border-t border-zinc-100 hover:bg-zinc-50 cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-3 text-xs text-zinc-500 whitespace-nowrap">{formatLocal(r.created_at, null, { style: "short" })}</td>
                    <td className="px-3 py-3 max-w-[150px] truncate font-medium text-zinc-800">{r.company_name || <span className="text-zinc-300">—</span>}</td>
                    <td className="px-3 py-3 max-w-[150px] truncate text-zinc-700">
                      {r.customer_name
                        ? r.customer_name
                        : r.customer_phone
                          ? <span className="text-zinc-500">{r.customer_phone}</span>
                          : <span className="text-zinc-300">—</span>}
                    </td>
                    <td className="px-3 py-3 text-xs whitespace-nowrap">
                      <span className="text-zinc-700">{typeLabel(r.payment_type)}</span>
                      {r.payment_channel && <span className="text-zinc-400"> · {channelLabel(r.payment_channel)}</span>}
                    </td>
                    <td className="px-3 py-3 text-right font-semibold text-zinc-900 whitespace-nowrap">{formatMoney(r.customer_price_minor, r.base_currency)}</td>
                    <td className="px-3 py-3 text-right text-zinc-700 whitespace-nowrap">{formatMoney(r.merchant_net_minor, r.base_currency)}</td>
                    <td className="px-3 py-3 text-right text-emerald-700 whitespace-nowrap">{formatMoney(r.platform_fee_minor, r.base_currency)}</td>
                    <td className="px-3 py-3 text-center whitespace-nowrap">
                      <span className="text-sm font-medium text-zinc-800">{bpsToPct(r.fee_rate_bps)}</span>
                      {(() => { const f = derivedFixed(r); return f ? <span className="block text-xs text-zinc-400">+{formatMoney(f, r.base_currency)} sabit</span> : null; })()}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {r.base_currency === "GBP" && r.payment_type === "business" ? (
                        r.converted
                          ? <span className="inline-flex items-center gap-1 text-teal-600 text-xs font-medium"><Repeat className="h-3 w-3" /> ₺</span>
                          : <span className="text-zinc-400 text-xs">bekliyor</span>
                      ) : <span className="text-zinc-300 text-xs">—</span>}
                    </td>
                    <td className="px-3 py-3 text-center"><StateBadge state={r.state} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sayfalama */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-100">
            <p className="text-xs text-zinc-500">Toplam {total.toLocaleString("tr-TR")} işlem • Sayfa {page}/{totalPages}</p>
            <div className="flex gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded-lg border border-zinc-200 hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-zinc-200 hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedTx && <AuditDrawer txId={selectedTx} onClose={() => setSelectedTx(null)} />}
    </div>
  );
}
