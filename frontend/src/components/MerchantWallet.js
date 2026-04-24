import { useState, useEffect, useCallback } from "react";
import api from "../api/api";
import { toast } from "sonner";
import { Wallet, ArrowUpRight, ArrowDownLeft, Snowflake, Clock, TrendingUp, Send, ChevronDown, Shield, AlertTriangle, ArrowLeft, Undo2 } from "lucide-react";
import RefundRequestModal from "./RefundRequestModal";

const formatMoney = (minor, currency) => {
  if (currency === "GBP") {
    const whole = Math.floor(Math.abs(minor) / 100);
    const frac = Math.abs(minor) % 100;
    const sign = minor < 0 ? "-" : "";
    return `${sign}£${whole.toLocaleString("en-GB")}.${String(frac).padStart(2, "0")}`;
  }
  const whole = Math.floor(Math.abs(minor) / 100);
  const frac = Math.abs(minor) % 100;
  const sign = minor < 0 ? "-" : "";
  return `${sign}${whole.toLocaleString("tr-TR")},${String(frac).padStart(2, "0")} ₺`;
};

export default function MerchantWallet({ onNavigate }) {
  const [wallet, setWallet] = useState(null);
  const [walletV2Status, setWalletV2Status] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [payoutHistory, setPayoutHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [payoutLoading, setPayoutLoading] = useState(false);
  const [txPage, setTxPage] = useState(1);
  const [txTotal, setTxTotal] = useState(0);
  const [showPaymentInfo, setShowPaymentInfo] = useState(false);
  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [features, setFeatures] = useState({ refund_requests_ui: true });

  const loadFeatures = useCallback(async () => {
    try {
      const res = await api.get("/merchant/features");
      setFeatures(res.data || { refund_requests_ui: true });
    } catch (err) {
      // endpoint yoksa veya hata olursa default'a düş
      setFeatures({ refund_requests_ui: true });
    }
  }, []);

  const loadWallet = useCallback(async () => {
    try {
      const res = await api.get("/merchant/wallet");
      setWallet(res.data);
    } catch (err) {
      console.error("Wallet load error:", err);
    }
    // PLANN v2: additional status endpoint (falls back gracefully)
    try {
      const res2 = await api.get("/merchant/wallet/status");
      setWalletV2Status(res2.data);
    } catch (err) {
      // endpoint may not be deployed yet — ignore silently
      setWalletV2Status(null);
    }
  }, []);

  const loadTransactions = useCallback(async (page = 1) => {
    try {
      const res = await api.get(`/merchant/transactions?page=${page}&per_page=20`);
      setTransactions(res.data.items || []);
      setTxTotal(res.data.total || 0);
      setTxPage(page);
    } catch (err) {
      console.error("Transactions load error:", err);
    }
  }, []);

  const loadPayoutHistory = useCallback(async () => {
    try {
      const res = await api.get("/merchant/payout/history?per_page=10");
      setPayoutHistory(res.data.items || []);
    } catch (err) {
      console.error("Payout history load error:", err);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([loadWallet(), loadTransactions(), loadPayoutHistory(), loadFeatures()]);
      setLoading(false);
    };
    load();
  }, [loadWallet, loadTransactions, loadPayoutHistory, loadFeatures]);

  const handleRequestPayout = async () => {
    if (!wallet?.payout_enabled) {
      toast.error("Ödeme talebi için koşullar sağlanmıyor");
      return;
    }
    setPayoutLoading(true);
    try {
      const res = await api.post("/merchant/payout/request");
      if (res.data.status === "processing") {
        toast.success(`Ödeme gönderildi: ${res.data.amount_display}`);
      } else if (res.data.status === "pending_review") {
        toast.info(res.data.message);
      }
      await loadWallet();
      await loadPayoutHistory();
    } catch (err) {
      const d = err.response?.data?.detail;
      const base =
        typeof d === "string"
          ? d
          : d?.message ||
            (d?.wise_response ? `${d.message || "Wise hatası"}: ${String(d.wise_response).slice(0, 280)}` : null) ||
            "Ödeme talebi başarısız";
      const msg = d && typeof d === "object" && d.hint ? `${base} ${d.hint}` : base;
      toast.error(msg);
    } finally {
      setPayoutLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!wallet) {
    return (
      <div className="p-4 pb-24 max-w-lg mx-auto space-y-4">
        <button onClick={() => onNavigate && onNavigate("settings")} className="flex items-center gap-2 text-gray-600 hover:text-gray-900">
          <ArrowLeft className="h-5 w-5" /> <span className="text-sm">Geri</span>
        </button>
        <div className="text-center text-gray-500 py-12">Cüzdan bilgisi yüklenemedi. Lütfen ödeme ayarlarınızı tamamlayın.</div>
      </div>
    );
  }

  const bc = wallet.base_currency;
  const sym = wallet.currency_symbol;

  const stateLabels = {
    pending: "Beklemede", authorized: "Onaylandı", captured: "Alındı",
    settled: "Yerleşti", available: "Kullanılabilir", reserved: "Ayrılmış",
    paid_out: "Ödendi", frozen: "Dondurulmuş", disputed: "İtirazlı",
    resolved_won: "İtiraz Kazanıldı", resolved_lost: "İtiraz Kaybedildi",
    refunded: "İade Edildi", canceled: "İptal", failed: "Başarısız", async_failed: "Başarısız",
  };

  const stateColors = {
    available: "text-green-600 bg-green-50", paid_out: "text-blue-600 bg-blue-50",
    pending: "text-yellow-600 bg-yellow-50", captured: "text-yellow-600 bg-yellow-50",
    settled: "text-emerald-600 bg-emerald-50", reserved: "text-purple-600 bg-purple-50",
    frozen: "text-red-600 bg-red-50", disputed: "text-red-600 bg-red-50",
    resolved_won: "text-green-600 bg-green-50", resolved_lost: "text-red-600 bg-red-50",
    refunded: "text-orange-600 bg-orange-50", canceled: "text-gray-500 bg-gray-50",
    failed: "text-red-600 bg-red-50", async_failed: "text-red-600 bg-red-50",
  };

  return (
    <div className="p-4 pb-24 max-w-lg mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate && onNavigate("settings")}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          </button>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Wallet className="h-5 w-5" /> Cüzdan
          </h1>
        </div>
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-600">
          {bc}
        </span>
      </div>

      {/* Unified Balance Card — merges v1 bakiye + v2 batch status */}
      <UnifiedBalanceCard
        wallet={wallet}
        v2Status={walletV2Status}
        currency={bc}
        payoutLoading={payoutLoading}
        onRequestPayout={handleRequestPayout}
      />

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-100 dark:border-gray-700">
          <Clock className="h-4 w-4 text-yellow-500 mb-1" />
          <p className="text-xs text-gray-500">Bekleyen</p>
          <p className="text-sm font-semibold text-gray-900 dark:text-white">{formatMoney(wallet.pending, bc)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-100 dark:border-gray-700">
          <Snowflake className="h-4 w-4 text-blue-400 mb-1" />
          <p className="text-xs text-gray-500">Dondurulmuş</p>
          <p className="text-sm font-semibold text-gray-900 dark:text-white">{formatMoney(wallet.frozen, bc)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-100 dark:border-gray-700">
          <TrendingUp className="h-4 w-4 text-green-500 mb-1" />
          <p className="text-xs text-gray-500">Toplam Kazanç</p>
          <p className="text-sm font-semibold text-gray-900 dark:text-white">{formatMoney(wallet.total_earned, bc)}</p>
        </div>
      </div>

      {/* PLANN v2 — Refund Request Button (SA kill-switch ile kapatılabilir) */}
      {features.refund_requests_ui && (
        <button
          onClick={() => setRefundModalOpen(true)}
          className="w-full py-2.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 bg-white border border-zinc-200 text-zinc-800 hover:bg-zinc-50 active:scale-[0.98] transition"
        >
          <Undo2 className="h-4 w-4" />
          İade Talebi Oluştur
        </button>
      )}

      {/* Info note — collapsible */}
      <div
        className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 cursor-pointer select-none"
        onClick={() => setShowPaymentInfo(prev => !prev)}
      >
        <div className="flex items-center gap-2.5">
          <Shield className="h-4 w-4 text-slate-500 flex-shrink-0" />
          <p className="text-xs font-semibold text-slate-700 flex-1">Ödeme süreçleri hakkında</p>
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${showPaymentInfo ? 'rotate-180' : ''}`} />
        </div>
        {showPaymentInfo && (
          <ul className="text-xs text-slate-600 space-y-0.5 mt-2.5 ml-6.5 pl-[26px]">
            <li>• Ödemeler alındıktan sonra <span className="font-bold text-slate-800">~2 iş günü</span> içinde kullanılabilir bakiyeye geçer.</li>
            <li>• İade penceresi: ilk <span className="font-bold text-slate-800">48 saat</span> içinde müşteriye iade yapılabilir.</li>
            <li>• IBAN değişikliği sonrası güvenlik bekleme süresi: <span className="font-bold text-slate-800">48 saat</span>.</li>
            <li>• Ödeme eşiğine ulaşıldığında bakiyeniz <span className="font-bold text-slate-800">her Çarşamba</span> otomatik olarak hesabınıza geçer.</li>
          </ul>
        )}
      </div>

      {/* Payout warnings */}
      {!wallet.payout_enabled && wallet.payout_enabled_reasons?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-amber-700">
            <p className="font-medium mb-1">Ödeme için gereken koşullar:</p>
            <ul className="space-y-0.5">
              {wallet.payout_enabled_reasons.map((r, i) => (
                <li key={i}>• {reasonLabels[r] || r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
        {[
          { id: "overview", label: "İşlemler" },
          { id: "payouts", label: "Ödemeler" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              activeTab === tab.id
                ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Transaction List */}
      {activeTab === "overview" && (
        <div className="space-y-2">
          {transactions.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-8">Henüz işlem yok</p>
          ) : (
            transactions.map((tx) => (
              <div
                key={tx.id}
                className="bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-100 dark:border-gray-700 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {(() => {
                    // Only actual refund transactions (type=refund) are outgoing.
                    // A payment tx with state=refunded still represents the incoming
                    // payment event — the reversal is shown as a separate refund row.
                    const isRefundTx = tx.type === "refund";
                    const isIncoming = tx.type === "payment";
                    return (
                      <div className={`p-2 rounded-lg ${isIncoming ? "bg-green-50" : "bg-red-50"}`}>
                        {isIncoming ? (
                          <ArrowDownLeft className="h-4 w-4 text-green-600" />
                        ) : (
                          <ArrowUpRight className="h-4 w-4 text-red-600" />
                        )}
                      </div>
                    );
                  })()}
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {tx.type === "refund" ? "İade" : tx.type === "payment" ? "Ödeme" : tx.type === "payout" ? "Gönderim" : tx.type}
                    </p>
                    {tx.customer_name && (
                      <p className="text-xs font-medium text-gray-600 dark:text-gray-300">{tx.customer_name}</p>
                    )}
                    <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString("tr-TR")} {new Date(tx.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                </div>
                <div className="text-right">
                  {(() => {
                    const isIncoming = tx.type === "payment";
                    return (
                      <p className={`text-sm font-semibold ${isIncoming ? "text-green-600" : "text-red-600"}`}>
                        {isIncoming ? "+" : "-"}{(tx.amount_display || "").replace(/^-/, "")}
                      </p>
                    );
                  })()}
                  {(() => {
                    // For fully-refunded payments, suppress the redundant "İade Edildi"
                    // badge because a separate refund row in the same list already
                    // conveys the reversal clearly.
                    if (tx.type === "payment" && tx.state === "refunded") return null;
                    return (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${stateColors[tx.state] || "text-gray-500 bg-gray-50"}`}>
                        {stateLabels[tx.state] || tx.state}
                      </span>
                    );
                  })()}
                </div>
              </div>
            ))
          )}

          {txTotal > 20 && (
            <div className="flex justify-center gap-2 pt-2">
              <button
                onClick={() => loadTransactions(txPage - 1)}
                disabled={txPage <= 1}
                className="px-3 py-1 text-sm rounded-lg border disabled:opacity-30"
              >
                ←
              </button>
              <span className="text-sm text-gray-500 py-1">{txPage}</span>
              <button
                onClick={() => loadTransactions(txPage + 1)}
                disabled={txPage * 20 >= txTotal}
                className="px-3 py-1 text-sm rounded-lg border disabled:opacity-30"
              >
                →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Payout History */}
      {activeTab === "payouts" && (
        <div className="space-y-2">
          {payoutHistory.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-8">Henüz ödeme geçmişi yok</p>
          ) : (
            payoutHistory.map((p) => (
              <div
                key={p.id}
                className="bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-100 dark:border-gray-700 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{p.total_display}</p>
                  <p className="text-xs text-gray-400">
                    {p.payout_rail === "bacs" ? "BACS" : "Banka Transferi"} • {new Date(p.created_at).toLocaleDateString("tr-TR")}
                  </p>
                </div>
                {(() => {
                  const batchLabels = {
                    completed: { text: "Tamamlandı", cls: "bg-green-50 text-green-600" },
                    processing: { text: "İşleniyor", cls: "bg-blue-50 text-blue-600" },
                    failed: { text: "Başarısız", cls: "bg-red-50 text-red-600" },
                    partial_failure: { text: "Kısmen başarılı", cls: "bg-amber-50 text-amber-700" },
                    awaiting_admin_fund: { text: "Onay bekleniyor", cls: "bg-zinc-100 text-zinc-600" },
                    queued_for_wise: { text: "Bankaya hazırlanıyor", cls: "bg-blue-50 text-blue-600" },
                    wise_fund_pending: { text: "Banka onayı bekleniyor", cls: "bg-blue-50 text-blue-600" },
                    draft: { text: "Hazırlanıyor", cls: "bg-zinc-100 text-zinc-600" },
                  };
                  const l = batchLabels[p.status] || { text: p.status, cls: "bg-gray-50 text-gray-500" };
                  return (
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${l.cls}`}>
                      {l.text}
                    </span>
                  );
                })()}
              </div>
            ))
          )}
        </div>
      )}

      {/* PLANN v2 — Refund Request Modal */}
      <RefundRequestModal
        open={refundModalOpen}
        onClose={() => setRefundModalOpen(false)}
        onCreated={() => {
          loadTransactions();
          loadWallet();
        }}
      />
    </div>
  );
}

const reasonLabels = {
  kyc_not_verified: "KYC kimlik doğrulaması tamamlanmadı. Ödeme ayarlarından doğrulama yapabilirsiniz.",
  recipient_not_verified: "Banka hesap bilgileri henüz doğrulanmadı. İlk ödeme transferinde banka tarafından otomatik doğrulanacaktır.",
  has_frozen_balance: "Dondurulmuş bakiye mevcut — itiraz süreci devam ediyor",
  iban_cooldown_active: "IBAN değişiklik güvenlik süresi aktif (48 saat). Bu süre dolmadan ödeme talep edilemez.",
  below_tier_limit: "Mevcut bakiye, kademenizin minimum ödeme eşiğinin altında",
  settings_not_found: "Ödeme ayarları bulunamadı. Lütfen ödeme ayarlarınızı tamamlayın.",
  wallet_not_found: "Cüzdan bulunamadı — destek ile iletişime geçin",
};

// ----- Unified Balance Card (v1 bakiye + v2 batch status, tek gövdede) -----
function UnifiedBalanceCard({ wallet, v2Status, currency, payoutLoading, onRequestPayout }) {
  const fmt = (m) => formatMoney(m || 0, currency);

  // v2 durum varsa onu kullan, yoksa v1 alanlarından türet
  const v2 = v2Status && v2Status.status && v2Status.status !== "no_wallet" ? v2Status : null;
  const kind = v2?.status || (wallet.payout_enabled ? "threshold_met" : "under_threshold");

  const available = v2?.available_balance_minor ?? wallet.effective_available;
  const threshold = v2?.threshold_minor ?? wallet.tier_limit;
  const pctRaw = v2?.progress_bps != null
    ? Math.round(v2.progress_bps / 100)
    : (wallet.progress_pct || 0);
  const pct = Math.min(100, Math.max(0, pctRaw));
  const remaining = v2?.remaining_to_threshold_minor ?? Math.max(0, (threshold || 0) - (available || 0));

  // Durum paleti — sadece alt mesaj şeridinin rengini belirler
  const palettes = {
    under_threshold: { strip: "bg-zinc-50 border-zinc-200 text-zinc-700",    icon: Clock,        label: "Eşiğe ulaşılmadı" },
    threshold_met:   { strip: "bg-emerald-50 border-emerald-200 text-emerald-800", icon: TrendingUp, label: "Eşik aşıldı, ödeme için hazır" },
    queued:          { strip: "bg-amber-50 border-amber-200 text-amber-900", icon: Send,         label: "Ödeme havuzuna alındı" },
    wise_pending:    { strip: "bg-blue-50 border-blue-200 text-blue-900",    icon: Clock,        label: "Banka onayı bekleniyor" },
    payout_stopped:  { strip: "bg-red-50 border-red-200 text-red-900",       icon: AlertTriangle, label: "Ödemeler durduruldu" },
    suspended:       { strip: "bg-red-100 border-red-300 text-red-900",      icon: AlertTriangle, label: "Hesap askıda" },
  };
  const p = palettes[kind] || palettes.under_threshold;
  const Icon = p.icon;

  let contextMsg = null;
  if (kind === "under_threshold") {
    contextMsg = <>Bu Çarşamba ödeme almak için <b>{fmt(remaining)}</b> daha işlem hacmine ulaşmalısınız.</>;
  } else if (kind === "threshold_met") {
    const formatTR = (iso) => {
      if (!iso) return "";
      const [y, m, d] = iso.split("-");
      return (y && m && d) ? `${d}.${m}.${y}` : iso;
    };
    const dateStr = formatTR(v2?.next_batch_date);
    contextMsg = <>Eşiği aştınız — bir sonraki Çarşamba{dateStr ? ` (${dateStr})` : ""} hesabınıza aktarılacak.</>;
  } else if (kind === "queued") {
    contextMsg = <><b>{fmt(v2?.active_batch?.total_amount_minor)}</b> bu Çarşamba hesabınıza aktarılmak üzere hazırlandı.</>;
  } else if (kind === "wise_pending") {
    contextMsg = <>Ödemeniz bankada işleniyor, aynı gün içinde hesabınıza geçecek.</>;
  } else if (kind === "payout_stopped") {
    contextMsg = <>Cüzdanınızda <b>{fmt(v2?.pending_debt_minor)}</b> bekleyen borç oluştu. Borç kapanana kadar ödemeler durduruldu.</>;
  } else if (kind === "suspended") {
    contextMsg = <>Hesabınız askıda — destek ile iletişime geçin.</>;
  }

  return (
    <div className="bg-gradient-to-br from-gray-50 to-white rounded-2xl p-5 border border-gray-200 shadow-sm">
      <p className="text-sm text-gray-500 font-medium">Kullanılabilir Bakiye</p>
      <p className="text-3xl font-bold mt-1 text-gray-900">{fmt(available)}</p>
      {wallet.refund_reserve > 0 && (
        <p className="text-xs text-gray-400 mt-1">
          İade rezervi: {fmt(wallet.refund_reserve)}
        </p>
      )}

      {/* Progress bar — sadece threshold anlamlıysa göster */}
      {threshold > 0 && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Ödeme eşiği: {fmt(threshold)}</span>
            <span>%{pct}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-zinc-900 rounded-full h-2 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Contextual status strip */}
      {contextMsg && (
        <div className={`mt-4 rounded-xl border px-3 py-2.5 flex items-start gap-2 ${p.strip}`}>
          <Icon className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1 text-xs">
            <p className="font-semibold">{p.label}</p>
            <p className="opacity-90 mt-0.5">{contextMsg}</p>
          </div>
        </div>
      )}

    </div>
  );
}
