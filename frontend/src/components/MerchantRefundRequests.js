import { useState, useEffect, useCallback } from "react";
import api from "../api/api";
import { toast } from "sonner";
import { ArrowLeft, Clock, CheckCircle2, XCircle, AlertTriangle, Plus } from "lucide-react";
import { formatLocal } from "../lib/timezone";
import RefundRequestModal from "./RefundRequestModal";

const formatMoney = (minor, currency = "GBP") => {
  if (minor == null) return "-";
  const val = (Math.abs(minor) / 100).toLocaleString(
    currency === "GBP" ? "en-GB" : "tr-TR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
  );
  return currency === "GBP" ? `£${val}` : `${val} ₺`;
};

const STATUS_META = {
  pending:   { label: "Beklemede",   cls: "bg-amber-50 text-amber-800 border-amber-200",   icon: Clock },
  approved:  { label: "Onaylandı",   cls: "bg-emerald-50 text-emerald-800 border-emerald-200", icon: CheckCircle2 },
  executed:  { label: "Tamamlandı",  cls: "bg-emerald-50 text-emerald-800 border-emerald-200", icon: CheckCircle2 },
  rejected:  { label: "Reddedildi",  cls: "bg-red-50 text-red-800 border-red-200",         icon: XCircle },
  failed:    { label: "Başarısız",   cls: "bg-red-50 text-red-800 border-red-200",         icon: AlertTriangle },
};

const PRIORITY_META = {
  urgent: { label: "Acil",    cls: "bg-red-100 text-red-800 border-red-200" },
  high:   { label: "Yüksek",  cls: "bg-orange-100 text-orange-800 border-orange-200" },
  normal: { label: "Normal",  cls: "bg-zinc-100 text-zinc-700 border-zinc-200" },
};

export default function MerchantRefundRequests({ onNavigate }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = statusFilter ? `?status=${statusFilter}` : "";
      const res = await api.get(`/merchant/refund-requests${qs}`);
      setItems(res.data.items || []);
    } catch (e) {
      toast.error("İade talepleri yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-screen bg-zinc-50 p-4 pb-24">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => onNavigate?.("merchant-wallet")}
          className="flex items-center gap-2 text-zinc-600 hover:text-zinc-900 mb-4 text-sm"
        >
          <ArrowLeft className="h-4 w-4" /> Cüzdana dön
        </button>

        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900">İade Talepleri</h1>
            <p className="text-sm text-zinc-500 mt-1">
              Oluşturduğunuz iade talepleri ve durumları.
            </p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-zinc-900 text-white text-sm font-medium hover:bg-black active:scale-[0.98] transition"
          >
            <Plus className="h-4 w-4" /> Yeni
          </button>
        </div>

        {/* Status filter chips */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {["", "pending", "approved", "executed", "rejected", "failed"].map((s) => (
            <button
              key={s || "all"}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 text-xs rounded-full border transition ${
                statusFilter === s
                  ? "bg-zinc-900 text-white border-zinc-900"
                  : "bg-white text-zinc-600 border-zinc-200"
              }`}
            >
              {s ? (STATUS_META[s]?.label || s) : "Hepsi"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="bg-white rounded-xl p-8 text-center text-zinc-400">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-400 mx-auto mb-2" />
            Yükleniyor…
          </div>
        ) : !items.length ? (
          <div className="bg-white rounded-xl p-8 text-center text-zinc-400">
            <p className="text-sm">Henüz iade talebi yok.</p>
            <button
              onClick={() => setModalOpen(true)}
              className="mt-3 text-sm text-zinc-900 underline"
            >
              İlk talebinizi oluşturun
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((r) => {
              const meta = STATUS_META[r.status] || STATUS_META.pending;
              const pri = PRIORITY_META[r.priority] || PRIORITY_META.normal;
              const StatusIcon = meta.icon;
              return (
                <div key={r.id} className="bg-white border border-zinc-200 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full border ${pri.cls}`}>
                          {pri.label}
                        </span>
                        {r.customer_waiting && (
                          <span className="text-[10px] bg-red-50 text-red-700 px-2 py-0.5 rounded-full border border-red-200">
                            Müşteri bekliyor
                          </span>
                        )}
                        {r.escalated && (
                          <span className="text-[10px] bg-orange-100 text-orange-800 px-2 py-0.5 rounded-full border border-orange-200">
                            Eskale edildi
                          </span>
                        )}
                      </div>
                      <p className="font-semibold text-zinc-900">{r.customer_name || "—"}</p>
                      <p className="text-xs text-zinc-500">{r.customer_phone || ""}</p>
                      <p className="text-sm text-zinc-600 italic mt-1 line-clamp-2">"{r.reason}"</p>
                      {r.rejection_reason && (
                        <p className="text-xs text-red-700 mt-1">
                          Red sebebi: {r.rejection_reason}
                        </p>
                      )}
                      <p className="text-[11px] text-zinc-400 mt-1">
                        Talep: {formatLocal(r.created_at)}
                        {r.reviewed_at && ` · İnceleme: ${formatLocal(r.reviewed_at)}`}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-zinc-900">
                        {formatMoney(r.refund_amount_minor, r.base_currency)}
                      </p>
                      <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full border mt-1 ${meta.cls}`}>
                        <StatusIcon className="h-3 w-3" />
                        {meta.label}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <RefundRequestModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => load()}
      />
    </div>
  );
}
