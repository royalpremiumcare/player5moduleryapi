import { useState, useEffect, useCallback } from "react";
import api from "../../api/api";
import { toast } from "sonner";
import {
  ArrowLeft, Send, AlertTriangle, CheckCircle2, XCircle, RefreshCcw,
  Flag, FileSpreadsheet, Clock, ShieldAlert, Inbox,
} from "lucide-react";
import { formatLocal, nextWednesdayLocal } from "../../lib/timezone";

const formatMoney = (minor, currency = "GBP") => {
  if (minor == null) return "-";
  const val = (Math.abs(minor) / 100).toLocaleString(
    currency === "GBP" ? "en-GB" : "tr-TR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
  );
  const sign = minor < 0 ? "-" : "";
  return currency === "GBP" ? `${sign}£${val}` : `${sign}${val} ₺`;
};

const TABS = [
  { key: "batches", label: "Haftalık Ödemeler", icon: Send },
  { key: "refunds", label: "İade Talepleri", icon: Inbox },
  { key: "dlq", label: "Hata Kuyruğu", icon: AlertTriangle },
  { key: "recon", label: "Mutabakat", icon: FileSpreadsheet },
  { key: "flags", label: "Özellik Bayrakları", icon: Flag },
];

export default function SAFinancialV2({ onNavigate }) {
  const [tab, setTab] = useState("batches");

  return (
    <div className="min-h-screen bg-zinc-50 p-4 md:p-6 pb-20">
      <div className="max-w-6xl mx-auto">
        <button
          onClick={() => onNavigate?.("superadmin")}
          className="flex items-center gap-2 text-zinc-600 hover:text-zinc-900 mb-4 text-sm"
        >
          <ArrowLeft className="h-4 w-4" /> SuperAdmin
        </button>

        <h1 className="text-2xl font-bold text-zinc-900 mb-1">Finansal Operasyonlar</h1>
        <p className="text-sm text-zinc-500 mb-6">
          Haftalık toplu ödemeler, iade akışı, hata kuyruğu, mutabakat ve özellik bayrağı yönetimi.
        </p>

        <div className="flex flex-wrap gap-2 mb-6 border-b border-zinc-200">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 px-3 py-2 text-sm font-medium border-b-2 transition ${
                  active
                    ? "border-zinc-900 text-zinc-900"
                    : "border-transparent text-zinc-500 hover:text-zinc-900"
                }`}
              >
                <Icon className="h-4 w-4" /> {t.label}
              </button>
            );
          })}
        </div>

        {tab === "batches" && <BatchesPane />}
        {tab === "refunds" && <RefundsPane />}
        {tab === "dlq" && <DLQPane />}
        {tab === "recon" && <ReconciliationPane />}
        {tab === "flags" && <FeatureFlagsPane />}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Wednesday Batches Pane
// -----------------------------------------------------------------------------

function BatchesPane() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [includeFailed, setIncludeFailed] = useState(false);
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkFundLoading, setBulkFundLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/financial/batches/awaiting", {
        params: {
          include_failed: includeFailed,
          include_completed: includeCompleted,
        },
      });
      setItems(res.data.items || []);
    } catch (e) {
      toast.error("Batch listesi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [includeFailed, includeCompleted]);

  useEffect(() => { load(); }, [load]);

  const prepare = async (id) => {
    if (!window.confirm("Wise'a hazırlanacak. Devam?")) return;
    try {
      const res = await api.post(`/superadmin/financial/batches/${id}/prepare-wise`);
      toast.success(`Wise quote: ${res.data.wise_quote_id || "hazır"}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail?.error || "Wise prepare başarısız");
    }
  };

  const bulkPrepare = async () => {
    const awaitingCount = items.filter((b) => b.status === "awaiting_admin_fund").length;
    if (awaitingCount === 0) {
      toast.info("Hazırlanacak batch yok");
      return;
    }
    if (!window.confirm(
      `${awaitingCount} batch tek seferde Wise'a hazırlanacak. Devam?`
    )) return;
    setBulkLoading(true);
    try {
      const res = await api.post("/superadmin/financial/batches/bulk-prepare-wise", {});
      const { processed, success, failed } = res.data || {};
      if (failed > 0) {
        toast.warning(`${success}/${processed} başarılı, ${failed} başarısız. Detay için Hata Kuyruğu'na bak.`);
      } else {
        toast.success(`${success} batch Wise'a gönderildi`);
      }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail?.error || "Toplu hazırlama başarısız");
    } finally {
      setBulkLoading(false);
    }
  };

  const confirmFund = async (id) => {
    const note = window.prompt("Manuel fund notu (opsiyonel):") || "";
    try {
      const res = await api.post(`/superadmin/financial/batches/${id}/confirm-fund`, { note });
      if (res.data.ok) {
        toast.success(`Paid out: ${res.data.paid_out_count}/${res.data.total_items}`);
      } else {
        toast.error(`Kısmi: ${res.data.status}`);
      }
      load();
    } catch (e) {
      toast.error("Confirm fund başarısız");
    }
  };

  const bulkConfirmFund = async () => {
    const pendingCount = items.filter((b) => b.status === "wise_fund_pending").length;
    if (pendingCount === 0) {
      toast.info("Fonlanacak batch yok");
      return;
    }
    if (!window.confirm(
      `${pendingCount} batch Wise'da fonlandı olarak işaretlenecek ve 'paid_out' durumuna geçirilecek. Devam?`
    )) return;
    const note = window.prompt("Toplu manuel fund notu (opsiyonel):") || "";
    setBulkFundLoading(true);
    try {
      const res = await api.post("/superadmin/financial/batches/bulk-confirm-fund", { note });
      const { processed, success, failed } = res.data || {};
      if (failed > 0) {
        toast.warning(`${success}/${processed} başarılı, ${failed} başarısız.`);
      } else {
        toast.success(`${success} batch fonlandı olarak işaretlendi`);
      }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail?.error || "Toplu fund onayı başarısız");
    } finally {
      setBulkFundLoading(false);
    }
  };

  const markFailed = async (id) => {
    const reason = window.prompt("Hata sebebi (zorunlu, >3 karakter):") || "";
    if (reason.length < 3) return;
    try {
      await api.post(`/superadmin/financial/batches/${id}/mark-failed`, { reason });
      toast.success("Batch failed olarak işaretlendi, rollback yapıldı");
      load();
    } catch (e) {
      toast.error("Mark failed başarısız");
    }
  };

  if (loading) return <LoadingBlock />;

  const awaitingItems = items.filter((b) => b.status === "awaiting_admin_fund");
  const awaitingTotal = awaitingItems.reduce(
    (acc, b) => acc + (b.total_amount_minor || 0),
    0,
  );
  const awaitingCurrency = awaitingItems[0]?.base_currency || "TRY";

  const fundPendingItems = items.filter((b) => b.status === "wise_fund_pending");
  const fundPendingTotal = fundPendingItems.reduce(
    (acc, b) => acc + (b.total_amount_minor || 0),
    0,
  );
  const fundPendingCurrency = fundPendingItems[0]?.base_currency || "TRY";

  const headerBlock = (
    <div className="space-y-3">
      <div className="bg-white border border-zinc-200 rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <p className="text-sm text-zinc-600">
          Bir sonraki Çarşamba: <strong>{nextWednesdayLocal()}</strong>
        </p>
        <div className="flex items-center gap-4 flex-wrap">
          <label className="inline-flex items-center gap-2 text-sm text-zinc-600 cursor-pointer">
            <input
              type="checkbox"
              checked={includeFailed}
              onChange={(e) => setIncludeFailed(e.target.checked)}
              className="rounded border-zinc-300"
            />
            Geçmiş başarısızları göster
          </label>
          <label className="inline-flex items-center gap-2 text-sm text-zinc-600 cursor-pointer">
            <input
              type="checkbox"
              checked={includeCompleted}
              onChange={(e) => setIncludeCompleted(e.target.checked)}
              className="rounded border-zinc-300"
            />
            Geçmiş başarıları göster
          </label>
        </div>
      </div>

      {awaitingItems.length > 0 && (
        <div className="bg-zinc-900 text-white rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm text-zinc-300">Fon bekleyen toplam</p>
            <p className="text-2xl font-bold">
              {formatMoney(awaitingTotal, awaitingCurrency)}
              <span className="text-sm font-normal text-zinc-400 ml-2">
                · {awaitingItems.length} işletme
              </span>
            </p>
          </div>
          <button
            onClick={bulkPrepare}
            disabled={bulkLoading}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg bg-white text-zinc-900 hover:bg-zinc-100 active:scale-[0.98] transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {bulkLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-zinc-900 border-t-transparent" />
                Hazırlanıyor...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Tümünü Wise'a Hazırla ({awaitingItems.length})
              </>
            )}
          </button>
        </div>
      )}

      {fundPendingItems.length > 0 && (
        <div className="bg-blue-600 text-white rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm text-blue-100">Wise'da fonlanmayı bekleyen toplam</p>
            <p className="text-2xl font-bold">
              {formatMoney(fundPendingTotal, fundPendingCurrency)}
              <span className="text-sm font-normal text-blue-200 ml-2">
                · {fundPendingItems.length} işletme
              </span>
            </p>
          </div>
          <button
            onClick={bulkConfirmFund}
            disabled={bulkFundLoading}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg bg-white text-blue-700 hover:bg-blue-50 active:scale-[0.98] transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {bulkFundLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-700 border-t-transparent" />
                İşleniyor...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Tümünü Fonlandı Olarak İşaretle ({fundPendingItems.length})
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );

  if (!items.length) {
    return (
      <div className="space-y-3">
        {headerBlock}
        <EmptyState icon={Send} label="Bekleyen batch yok." />
      </div>
    );
  }

  // Render a single batch card (used for both flat and grouped-child rows)
  const renderBatchCard = (b, { compact = false } = {}) => (
    <div
      key={b.id}
      className={`bg-white border border-zinc-200 rounded-xl p-4 ${compact ? "shadow-none" : ""}`}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-sm text-zinc-500">Org: {b.organization_name || b.organization_id}</p>
          <p className="text-xl font-bold text-zinc-900 mt-1">
            {formatMoney(b.total_amount_minor, b.base_currency)}
          </p>
          <p className="text-xs text-zinc-500 mt-1">
            {b.item_count} işlem · {formatLocal(b.created_at)}
          </p>
        </div>
        <StatusBadge status={b.status} />
      </div>
      <div className="flex gap-2 mt-4 flex-wrap">
        {b.status === "awaiting_admin_fund" && (
          <button onClick={() => prepare(b.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-black active:scale-[0.98] transition">
            Wise'a Hazırla
          </button>
        )}
        {b.status === "wise_fund_pending" && (
          <>
            <button onClick={() => confirmFund(b.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-black active:scale-[0.98] transition">
              Manuel Fund Onayladım
            </button>
            <button onClick={() => markFailed(b.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 active:scale-[0.98] transition">
              Başarısız İşaretle
            </button>
          </>
        )}
        {b.status === "queued_for_wise" && (
          <button onClick={() => markFailed(b.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 active:scale-[0.98] transition">
            Başarısız İşaretle
          </button>
        )}
        {b.status === "failed" && (
          <span className="text-xs text-zinc-500 italic py-2">
            (arşivlenmiş — aksiyon gerekmiyor)
          </span>
        )}
        {(b.status === "completed" || b.status === "partial_failure") && (
          <span className="text-xs text-zinc-500 italic py-2">
            {b.funded_at ? `Fonlandı: ${formatLocal(b.funded_at)}` : "Tamamlandı"}
          </span>
        )}
      </div>
    </div>
  );

  // Group items by wise_batch_group_id so completed/pending bulk batches show
  // as a "toplu" wrapper containing per-org "tek" child cards.
  const rendered = [];
  const seenGroups = new Set();
  for (const b of items) {
    const gid = b.wise_batch_group_id;
    if (gid && !seenGroups.has(gid)) {
      const members = items.filter((x) => x.wise_batch_group_id === gid);
      if (members.length > 1) {
        seenGroups.add(gid);
        const total = members.reduce((a, m) => a + (m.total_amount_minor || 0), 0);
        const currency = members[0]?.base_currency || "TRY";
        const allCompleted = members.every((m) => m.status === "completed");
        const anyFailed = members.some((m) => m.status === "failed" || m.status === "partial_failure");
        const groupStatus = allCompleted ? "completed" : anyFailed ? "partial_failure" : members[0]?.status;
        rendered.push(
          <div
            key={`grp-${gid}`}
            className="bg-zinc-50 border-2 border-zinc-200 rounded-xl p-3 space-y-2"
          >
            <div className="flex items-start justify-between gap-4 flex-wrap px-1 pt-1">
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500 font-semibold">
                  Toplu Wise Batch Group
                </p>
                <p className="text-lg font-bold text-zinc-900 mt-0.5">
                  {formatMoney(total, currency)}
                  <span className="text-sm font-normal text-zinc-500 ml-2">
                    · {members.length} işletme
                  </span>
                </p>
                <p className="text-[11px] text-zinc-400 font-mono mt-0.5 truncate max-w-md">
                  {gid}
                </p>
              </div>
              <StatusBadge status={groupStatus} />
            </div>
            <div className="space-y-2 pl-3 border-l-2 border-zinc-200">
              {members.map((m) => renderBatchCard(m, { compact: true }))}
            </div>
          </div>
        );
        continue;
      }
    }
    if (!gid || !seenGroups.has(gid)) {
      rendered.push(renderBatchCard(b));
    }
  }

  return (
    <div className="space-y-3">
      {headerBlock}
      {rendered}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Refund Requests Pane (SuperAdmin)
// -----------------------------------------------------------------------------

function RefundsPane() {
  const [view, setView] = useState("pending"); // pending | history
  const [items, setItems] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pendRes, histRes] = await Promise.all([
        api.get("/superadmin/refund-requests"),
        api.get("/superadmin/refund-requests/history?limit=100"),
      ]);
      setItems(pendRes.data.items || []);
      setHistory(histRes.data.items || []);
    } catch (e) {
      toast.error("Refund talepleri yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (id) => {
    if (!window.confirm("Stripe iade çağrısı yapılacak. Onaylıyor musunuz?")) return;
    try {
      const res = await api.post(`/superadmin/refund-requests/${id}/approve`);
      toast.success(`Refund: ${res.data.stripe_refund_id}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail?.error || "Approve başarısız");
    }
  };

  const reject = async (id) => {
    const reason = window.prompt("Red sebebi (zorunlu, >3 karakter):") || "";
    if (reason.length < 3) return;
    try {
      await api.post(`/superadmin/refund-requests/${id}/reject`, { reason });
      toast.success("Reddedildi");
      load();
    } catch (e) {
      toast.error("Reject başarısız");
    }
  };

  if (loading) return <LoadingBlock />;

  const executedCount = history.filter((h) => h.status === "executed").length;
  const executedTotal = history
    .filter((h) => h.status === "executed")
    .reduce((acc, h) => acc + (h.refund_amount_minor || 0), 0);

  return (
    <div className="space-y-4">
      {/* Sub-tabs */}
      <div className="inline-flex rounded-lg border border-zinc-200 bg-white p-1">
        <button
          onClick={() => setView("pending")}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
            view === "pending" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
          }`}
        >
          Bekleyen ({items.length})
        </button>
        <button
          onClick={() => setView("history")}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
            view === "history" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
          }`}
        >
          Geçmiş ({history.length})
        </button>
      </div>

      {view === "pending" && (
        <>
          {items.length === 0 ? (
            <EmptyState icon={Inbox} label="Bekleyen refund talebi yok." />
          ) : (
            <div className="space-y-3">
              {items.map((r) => {
                const overdue = r.sla_deadline && new Date(r.sla_deadline) < new Date();
                return (
                  <div key={r.id} className="bg-white border border-zinc-200 rounded-xl p-4">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <PriorityBadge priority={r.priority} />
                          {r.customer_waiting && (
                            <span className="text-[10px] bg-red-50 text-red-700 px-2 py-0.5 rounded-full border border-red-200">
                              Müşteri bekliyor
                            </span>
                          )}
                          {overdue && (
                            <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
                              SLA aşıldı
                            </span>
                          )}
                          {r.escalated && (
                            <span className="text-[10px] bg-orange-100 text-orange-800 px-2 py-0.5 rounded-full border border-orange-200">
                              Eskale edildi
                            </span>
                          )}
                        </div>
                        <p className="text-lg font-bold text-zinc-900 mt-2">
                          {formatMoney(r.refund_amount_minor, r.base_currency)}
                        </p>
                        <p className="text-sm text-zinc-700 font-medium">
                          {r.organization_name || r.organization_id}
                        </p>
                        <p className="text-sm text-zinc-600">
                          Müşteri: <span className="font-medium">{r.customer_name || "-"}</span>
                          {r.customer_phone ? ` · ${r.customer_phone}` : ""}
                        </p>
                        <p className="text-sm text-zinc-500 italic mt-1 line-clamp-2">"{r.reason}"</p>
                        <p className="text-xs text-zinc-400 mt-1">
                          {formatLocal(r.created_at)} · SLA: {formatLocal(r.sla_deadline)}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button onClick={() => approve(r.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-black active:scale-[0.98] transition">
                        <CheckCircle2 className="h-4 w-4" /> Onayla
                      </button>
                      <button onClick={() => reject(r.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 active:scale-[0.98] transition">
                        <XCircle className="h-4 w-4" /> Reddet
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {view === "history" && (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white border border-zinc-200 rounded-lg p-3">
              <p className="text-xs text-zinc-500">Onaylanmış iade</p>
              <p className="text-lg font-bold text-emerald-700">{executedCount}</p>
            </div>
            <div className="bg-white border border-zinc-200 rounded-lg p-3">
              <p className="text-xs text-zinc-500">Toplam iade tutarı</p>
              <p className="text-lg font-bold text-zinc-900">
                {history.length > 0
                  ? formatMoney(executedTotal, history[0].base_currency || "TRY")
                  : "-"}
              </p>
            </div>
            <div className="bg-white border border-zinc-200 rounded-lg p-3">
              <p className="text-xs text-zinc-500">Reddedilmiş</p>
              <p className="text-lg font-bold text-zinc-400">
                {history.filter((h) => h.status === "rejected").length}
              </p>
            </div>
          </div>

          {history.length === 0 ? (
            <EmptyState icon={Inbox} label="Henüz tamamlanmış iade talebi yok." />
          ) : (
            <div className="space-y-2">
              {history.map((r) => {
                const isExec = r.status === "executed";
                const isRej = r.status === "rejected";
                return (
                  <div
                    key={r.id}
                    className="bg-white border border-zinc-200 rounded-lg p-3 flex items-center gap-3"
                  >
                    <div
                      className={`h-9 w-9 flex-shrink-0 rounded-full flex items-center justify-center ${
                        isExec ? "bg-emerald-50" : isRej ? "bg-red-50" : "bg-zinc-100"
                      }`}
                    >
                      {isExec ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      ) : isRej ? (
                        <XCircle className="h-4 w-4 text-red-600" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-zinc-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-zinc-900 truncate">
                          {r.organization_name || r.organization_id}
                        </p>
                        <span
                          className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${
                            isExec
                              ? "bg-emerald-50 text-emerald-700"
                              : isRej
                              ? "bg-red-50 text-red-700"
                              : "bg-zinc-100 text-zinc-600"
                          }`}
                        >
                          {isExec ? "Onaylandı" : isRej ? "Reddedildi" : r.status}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500">
                        Müşteri:{" "}
                        <span className="text-zinc-700 font-medium">
                          {r.customer_name || "-"}
                        </span>
                        {r.customer_phone ? ` · ${r.customer_phone}` : ""}
                      </p>
                      {isRej && r.rejection_reason && (
                        <p className="text-xs text-red-600 italic truncate">
                          Red sebebi: {r.rejection_reason}
                        </p>
                      )}
                      <p className="text-[11px] text-zinc-400">
                        {formatLocal(r.updated_at || r.created_at)}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p
                        className={`text-sm font-bold ${
                          isExec ? "text-emerald-700" : "text-zinc-500"
                        }`}
                      >
                        {isExec ? "-" : ""}
                        {formatMoney(r.refund_amount_minor, r.base_currency)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// DLQ Pane
// -----------------------------------------------------------------------------

function DLQPane() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = statusFilter ? `?status=${statusFilter}` : "";
      const res = await api.get(`/superadmin/financial/dlq${q}`);
      setItems(res.data.items || []);
    } catch (e) {
      toast.error("DLQ yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const retry = async (id) => {
    try {
      await api.post(`/superadmin/financial/dlq/${id}/retry`);
      toast.success("Yeniden deneme planlandı");
      load();
    } catch (e) { toast.error("Yeniden deneme başarısız"); }
  };

  const resolve = async (id) => {
    const note = window.prompt("Çözüm notu (manuel olarak nasıl çözdüğünüzü yazın):") || "manuel_cozulmus";
    try {
      await api.post(`/superadmin/financial/dlq/${id}/resolve`, { note });
      toast.success("Çözüldü olarak işaretlendi");
      load();
    } catch (e) { toast.error("Çözüldü işaretleme başarısız"); }
  };

  const abandon = async (id) => {
    const note = window.prompt("Vazgeçme sebebi (neden artık denenmemeli):") || "admin_vazgecti";
    try {
      await api.post(`/superadmin/financial/dlq/${id}/abandon`, { note });
      toast.success("Vazgeçildi olarak işaretlendi");
      load();
    } catch (e) { toast.error("Vazgeçme işaretlemesi başarısız"); }
  };

  const FILTERS_TR = {
    "":              "Hepsi",
    pending:         "Bekliyor",
    manual_review:   "Manuel İnceleme",
    resolved:        "Çözüldü",
    abandoned:       "Vazgeçildi",
  };

  const FAILURE_TYPE_TR = {
    webhook_processing_failed: "Webhook İşleme Hatası",
    payout_generic_failed:     "Ödeme (Payout) Hatası",
    refund_execution_failed:   "İade Uygulama Hatası",
    batch_build_failed:        "Batch Oluşturma Hatası",
    wise_transfer_failed:      "Wise Havale Hatası",
  };

  const ENTITY_TYPE_TR = {
    stripe_webhook:    "Stripe Webhook",
    payout_batch:      "Toplu Ödeme (Batch)",
    refund_request:    "İade Talebi",
    merchant_transaction: "İşletme İşlemi",
  };

  return (
    <div className="space-y-3">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-900 leading-relaxed">
        <p className="font-medium mb-1">Hata Kuyruğu (DLQ) nedir?</p>
        <p>
          Başarısız olan finansal işlemler burada saklanır ve otomatik olarak yeniden denenir.
          Maksimum deneme sayısı aşılırsa <strong>Manuel İnceleme</strong> durumuna düşer.
          <strong> Yeniden Dene</strong>: hemen tekrar dene.
          <strong> Çözüldü</strong>: başka kanaldan manuel düzelttim, kapat.
          <strong> Vazgeç</strong>: bu kayıt artık düzeltilmeyecek, kapat.
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {Object.entries(FILTERS_TR).map(([s, label]) => (
          <button
            key={s || "all"}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 text-xs rounded-full border ${
              statusFilter === s
                ? "bg-zinc-900 text-white border-zinc-900"
                : "bg-white text-zinc-600 border-zinc-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {loading && <LoadingBlock />}
      {!loading && !items.length && <EmptyState icon={AlertTriangle} label="Hata kuyruğu boş." />}
      {items.map((item) => (
        <div key={item.id} className="bg-white border border-zinc-200 rounded-xl p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <ShieldAlert className={`h-4 w-4 ${item.status === "manual_review" ? "text-red-500" : "text-amber-500"}`} />
                <span className="text-xs bg-zinc-100 text-zinc-800 px-2 py-0.5 rounded font-medium">
                  {FAILURE_TYPE_TR[item.failure_type] || item.failure_type}
                </span>
                <StatusBadge status={item.status} />
              </div>
              <p className="text-sm text-zinc-600 mt-2">
                {ENTITY_TYPE_TR[item.source_entity_type] || item.source_entity_type}:{" "}
                <code className="text-xs bg-zinc-50 px-1 py-0.5 rounded">{item.source_entity_id}</code>
              </p>
              <p className="text-xs text-zinc-500 mt-1 line-clamp-2">
                <span className="font-medium">Hata:</span> {item.error_message}
              </p>
              <p className="text-xs text-zinc-400 mt-1">
                Deneme: {item.retry_count}/{item.max_retries} · Oluşturulma: {formatLocal(item.created_at)}
                {item.next_retry_at && item.status === "pending" && (
                  <> · Sonraki deneme: {formatLocal(item.next_retry_at)}</>
                )}
              </p>
            </div>
          </div>
          {item.status !== "resolved" && item.status !== "abandoned" && (
            <div className="flex gap-2 mt-3 flex-wrap">
              <button onClick={() => retry(item.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-white border border-zinc-200 text-zinc-900 hover:bg-zinc-50 active:scale-[0.98] transition">
                <RefreshCcw className="h-3.5 w-3.5" /> Yeniden Dene
              </button>
              <button onClick={() => resolve(item.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-black active:scale-[0.98] transition">
                <CheckCircle2 className="h-3.5 w-3.5" /> Manuel Çöz
              </button>
              <button onClick={() => abandon(item.id)} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 active:scale-[0.98] transition">
                <XCircle className="h-3.5 w-3.5" /> Vazgeç
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Reconciliation Pane
// -----------------------------------------------------------------------------

function ReconciliationPane() {
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(weekAgo);
  const [endDate, setEndDate] = useState(today);
  const [multi, setMulti] = useState(null); // { summaries: { TRY: {...}, GBP: {...} } }
  const [discrepancies, setDiscrepancies] = useState([]);
  const [showDiscrepancies, setShowDiscrepancies] = useState(false);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const [mRes, dRes] = await Promise.all([
        api.get("/superadmin/financial/reconciliation/multi_summary", {
          params: { start_iso: startDate + "T00:00:00Z", end_iso: endDate + "T23:59:59Z" },
        }),
        api.get("/superadmin/financial/reconciliation/discrepancies", {
          params: { start_iso: startDate + "T00:00:00Z", end_iso: endDate + "T23:59:59Z", limit: 200 },
        }),
      ]);
      setMulti(mRes.data);
      setDiscrepancies(dRes.data.items || []);
    } catch (e) {
      toast.error("Mutabakat hesaplanamadı");
    } finally {
      setLoading(false);
    }
  };

  const exportFile = async (format) => {
    try {
      const res = await api.get(
        `/superadmin/financial/reconciliation/export.${format}`,
        {
          params: {
            start_iso: startDate + "T00:00:00Z",
            end_iso: endDate + "T23:59:59Z",
          },
          responseType: "blob",
        },
      );
      const blob = new Blob([res.data], {
        type: format === "csv" ? "text/csv;charset=utf-8" : "application/json",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mutabakat_${startDate}_${endDate}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("İndirme başladı");
    } catch (e) {
      toast.error("Dışa aktarım başarısız");
    }
  };

  const summaries = multi?.summaries || {};
  const currencies = Object.keys(summaries);

  return (
    <div className="space-y-4">
      <div className="bg-white border border-zinc-200 rounded-xl p-4 flex gap-3 flex-wrap items-end">
        <label className="text-sm">
          <div className="text-zinc-600 mb-1">Başlangıç</div>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                 className="border border-zinc-300 rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="text-sm">
          <div className="text-zinc-600 mb-1">Bitiş</div>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                 className="border border-zinc-300 rounded-lg px-3 py-2 text-sm" />
        </label>
        <button onClick={run} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-black active:scale-[0.98] transition">Hesapla</button>
        <button onClick={() => exportFile("csv")} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-white border border-zinc-200 text-zinc-900 hover:bg-zinc-50 active:scale-[0.98] transition">CSV</button>
        <button onClick={() => exportFile("xlsx")} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-white border border-zinc-200 text-zinc-900 hover:bg-zinc-50 active:scale-[0.98] transition">XLSX</button>
      </div>

      {loading && <LoadingBlock />}

      {!loading && multi && currencies.length === 0 && (
        <EmptyState icon={FileSpreadsheet} label="Seçilen aralıkta işlem yok." />
      )}

      {!loading && currencies.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {currencies.map((cc) => {
            const s = summaries[cc];
            return (
              <div key={cc} className="bg-white border border-zinc-200 rounded-xl p-5">
                <div className="flex items-baseline justify-between mb-3">
                  <h3 className="font-semibold text-zinc-900">
                    {cc === "TRY" ? "Türk Lirası (₺)" : "İngiliz Sterlini (£)"}
                  </h3>
                  <span className="text-xs text-zinc-400">
                    {s.start_iso.slice(0, 10)} – {s.end_iso.slice(0, 10)}
                  </span>
                </div>
                <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  <Row label="Stripe Tahsilat" value={formatMoney(s.stripe_total_minor, cc)} />
                  <Row label="Platform Komisyonu" value={formatMoney(s.platform_fee_total_minor, cc)} />
                  <Row label="Stripe Ücreti (tahmin)" value={formatMoney(s.stripe_fee_total_minor, cc)} />
                  <Row label="Wise Ücreti" value={formatMoney(s.wise_fee_total_minor, cc)} />
                  <Row label="Wise Fonlanan" value={formatMoney(s.wise_funded_total_minor, cc)} />
                  <Row label="İade Kesintisi" value={formatMoney(s.refund_total_minor, cc)} />
                  <Row label="İtiraz Kaybı" value={formatMoney(s.dispute_lost_total_minor, cc)} />
                  <Row label="Bekleyen" value={formatMoney(s.pending_total_minor, cc)} />
                  <Row label="Rezerve" value={formatMoney(s.reserved_total_minor, cc)} />
                  <Row label="Ödenmiş" value={formatMoney(s.paid_out_total_minor, cc)} />
                </dl>
                <div className={`mt-4 p-3 rounded-lg ${s.alert ? "bg-red-50 border border-red-200" : "bg-emerald-50 border border-emerald-200"}`}>
                  <p className={`text-sm font-semibold ${s.alert ? "text-red-900" : "text-emerald-900"}`}>
                    Açıklanamayan Fark: {formatMoney(s.unexplained_diff_minor, cc)}
                    {s.alert ? " ⚠️" : " ✓"}
                  </p>
                  <p className="text-xs mt-1 text-zinc-600">
                    Tolerans: ±{formatMoney(s.tolerance_minor, cc)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Discrepancies panel */}
      {multi && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="font-semibold text-zinc-900">
                Açıklanamayan İşlemler{" "}
                <span className="text-sm text-zinc-500 font-normal">
                  ({discrepancies.length})
                </span>
              </h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                Ledger'a kaydedilen merchant net'i ile (customer - komisyon - ücretler) farkı 1,00'den büyük olan işlemler.
              </p>
            </div>
            <button
              onClick={() => setShowDiscrepancies((v) => !v)}
              className="text-sm px-3 py-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-800 transition"
            >
              {showDiscrepancies ? "Gizle" : "Göster"}
            </button>
          </div>

          {showDiscrepancies && (
            <div className="mt-4">
              {discrepancies.length === 0 ? (
                <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                  ✓ Kaydedilen ve beklenen tutarlar uyumlu — açıklanamayan işlem yok.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead className="bg-zinc-50">
                      <tr className="text-left text-zinc-600">
                        <th className="p-2 font-medium">İşletme</th>
                        <th className="p-2 font-medium">Müşteri Öd.</th>
                        <th className="p-2 font-medium">Komisyon</th>
                        <th className="p-2 font-medium">Stripe</th>
                        <th className="p-2 font-medium">Wise</th>
                        <th className="p-2 font-medium">Beklenen Net</th>
                        <th className="p-2 font-medium">Kayıtlı Net</th>
                        <th className="p-2 font-medium text-right">Fark</th>
                        <th className="p-2 font-medium">Tarih</th>
                      </tr>
                    </thead>
                    <tbody>
                      {discrepancies.map((d) => {
                        const cc = d.base_currency;
                        return (
                          <tr key={d.tx_id} className="border-t border-zinc-100">
                            <td className="p-2">
                              <div className="font-medium text-zinc-900 max-w-[160px] truncate">
                                {d.organization_name}
                              </div>
                              <div className="text-[10px] text-zinc-400 font-mono">
                                {(d.tx_id || "").slice(0, 8)}
                              </div>
                            </td>
                            <td className="p-2">{formatMoney(d.customer_price_minor, cc)}</td>
                            <td className="p-2">{formatMoney(d.platform_fee_minor, cc)}</td>
                            <td className="p-2">{formatMoney(d.stripe_fee_minor, cc)}</td>
                            <td className="p-2">{formatMoney(d.wise_fee_minor, cc)}</td>
                            <td className="p-2">{formatMoney(d.expected_merchant_minor, cc)}</td>
                            <td className="p-2">{formatMoney(d.recorded_merchant_minor, cc)}</td>
                            <td
                              className={`p-2 text-right font-semibold ${
                                d.delta_minor > 0 ? "text-amber-700" : "text-red-700"
                              }`}
                            >
                              {d.delta_minor > 0 ? "+" : ""}
                              {formatMoney(d.delta_minor, cc)}
                            </td>
                            <td className="p-2 text-zinc-500">
                              {(d.created_at || "").slice(0, 10)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Feature Flags Pane
// -----------------------------------------------------------------------------

function FeatureFlagsPane() {
  const [flags, setFlags] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/financial/feature-flags");
      setFlags(res.data);
    } catch (e) {
      toast.error("Flag listesi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleGlobal = async (name, current) => {
    try {
      await api.post(`/superadmin/financial/feature-flags/${name}/global`, { value: !current });
      toast.success(`${name} = ${!current}`);
      load();
    } catch (e) { toast.error("Güncellenemedi"); }
  };

  const killSwitch = async (name, disabled) => {
    if (!window.confirm(`${name} için kill switch ${disabled ? "aktif" : "pasif"} yapılacak. Emin misin?`)) return;
    try {
      await api.post(`/superadmin/financial/feature-flags/${name}/kill-switch`, { disabled });
      toast.success("Kill switch güncellendi");
      load();
    } catch (e) { toast.error("Kill switch başarısız"); }
  };

  if (loading || !flags) return <LoadingBlock />;

  return (
    <div className="space-y-5">
      <section>
        <h3 className="font-semibold text-zinc-900 mb-2">Env Flags (restart gerekir)</h3>
        <div className="bg-white border border-zinc-200 rounded-xl divide-y divide-zinc-100">
          {Object.entries(flags.env_flags).map(([name, data]) => (
            <div key={name} className="p-3 flex items-center justify-between gap-4">
              <div>
                <p className="font-mono text-sm">{name}</p>
                <p className="text-xs text-zinc-500">Restart gerekli</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${
                data.enabled ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                             : "bg-zinc-100 text-zinc-600"
              }`}>
                {data.enabled ? "ON" : "OFF"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="font-semibold text-zinc-900 mb-2">DB Flags (canlı değişir)</h3>
        <div className="bg-white border border-zinc-200 rounded-xl divide-y divide-zinc-100">
          {Object.entries(flags.db_flags).map(([name, data]) => (
            <div key={name} className="p-3 flex items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-sm">{name}</p>
                <p className="text-xs text-zinc-500">{data.description}</p>
                {data.emergency_disable && (
                  <span className="text-[10px] bg-red-100 text-red-800 px-2 py-0.5 rounded-full mt-1 inline-block">
                    KILL SWITCH ACTIVE
                  </span>
                )}
                {Object.keys(data.org_overrides || {}).length > 0 && (
                  <p className="text-[11px] text-zinc-400 mt-1">
                    Override: {Object.keys(data.org_overrides).length} org
                  </p>
                )}
              </div>
              <div className="flex gap-2 items-center">
                <button
                  onClick={() => toggleGlobal(name, data.global_default)}
                  className={`text-xs px-2 py-1 rounded ${
                    data.global_default ? "bg-emerald-600 text-white" : "bg-zinc-200 text-zinc-700"
                  }`}
                >
                  {data.global_default ? "ON" : "OFF"}
                </button>
                <button
                  onClick={() => killSwitch(name, !data.emergency_disable)}
                  className="text-xs px-2 py-1 rounded bg-red-50 text-red-700 border border-red-200"
                >
                  Kill
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function LoadingBlock() {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-8 text-center text-zinc-400">
      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-400 mx-auto mb-2" />
      Yükleniyor…
    </div>
  );
}

function EmptyState({ icon: Icon, label }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-8 text-center text-zinc-400">
      <Icon className="h-8 w-8 mx-auto mb-2 opacity-40" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <>
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-zinc-900 font-medium text-right md:text-left">{value}</dd>
    </>
  );
}

const STATUS_LABELS_TR = {
  awaiting_admin_fund: "Fon Bekliyor",
  queued_for_wise:     "Wise Sırasında",
  wise_fund_pending:   "Fonlanıyor",
  completed:           "Tamamlandı",
  failed:              "Başarısız",
  partial_failure:     "Kısmi Başarısız",
  pending:             "Bekliyor",
  retrying:            "Yeniden Deneniyor",
  manual_review:       "Manuel İnceleme",
  resolved:            "Çözüldü",
  abandoned:           "Vazgeçildi",
  executed:            "Onaylandı",
  rejected:            "Reddedildi",
};

function StatusBadge({ status }) {
  const palettes = {
    awaiting_admin_fund: "bg-amber-50 text-amber-800 border-amber-200",
    queued_for_wise:     "bg-amber-50 text-amber-800 border-amber-200",
    wise_fund_pending:   "bg-blue-50 text-blue-800 border-blue-200",
    completed:           "bg-emerald-50 text-emerald-800 border-emerald-200",
    failed:              "bg-red-50 text-red-800 border-red-200",
    partial_failure:     "bg-orange-50 text-orange-800 border-orange-200",
    pending:             "bg-amber-50 text-amber-800 border-amber-200",
    retrying:            "bg-blue-50 text-blue-800 border-blue-200",
    manual_review:       "bg-red-50 text-red-800 border-red-200",
    resolved:            "bg-emerald-50 text-emerald-800 border-emerald-200",
    abandoned:           "bg-zinc-100 text-zinc-600 border-zinc-200",
  };
  const cls = palettes[status] || "bg-zinc-100 text-zinc-600 border-zinc-200";
  return (
    <span className={`text-[11px] px-2 py-1 rounded-full border ${cls}`}>
      {STATUS_LABELS_TR[status] || status}
    </span>
  );
}

function PriorityBadge({ priority }) {
  const map = {
    urgent: "bg-red-100 text-red-800 border-red-200",
    high:   "bg-orange-100 text-orange-800 border-orange-200",
    normal: "bg-zinc-100 text-zinc-700 border-zinc-200",
  };
  return (
    <span className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full border ${map[priority] || map.normal}`}>
      {priority}
    </span>
  );
}
