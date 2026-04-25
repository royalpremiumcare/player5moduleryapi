import { useState, useEffect } from "react";
import api from "../api/api";
import { toast } from "sonner";
import { X, Search, AlertCircle } from "lucide-react";

const formatMoney = (minor, currency = "GBP") => {
  if (minor == null) return "-";
  const val = (Math.abs(minor) / 100).toLocaleString(
    currency === "GBP" ? "en-GB" : "tr-TR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
  );
  return currency === "GBP" ? `£${val}` : `${val} ₺`;
};

const formatDateTR = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
};

/**
 * Merchant refund request modal.
 *
 * Props:
 *   - open: bool
 *   - onClose: () => void
 *   - onCreated: (refundRequest) => void
 *   - prefillTransactionId: optional
 */
export default function RefundRequestModal({ open, onClose, onCreated, prefillTransactionId = null }) {
  const [step, setStep] = useState("search"); // search | form
  const [query, setQuery] = useState("");
  const [searchBy, setSearchBy] = useState("name");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);

  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [priority, setPriority] = useState("normal");
  const [customerWaiting, setCustomerWaiting] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setStep("search");
      setQuery(""); setResults([]); setSelected(null);
      setAmount(""); setReason(""); setPriority("normal");
      setCustomerWaiting(false); setNote("");
    }
  }, [open]);

  useEffect(() => {
    if (prefillTransactionId && open) {
      // Load the transaction directly
      api.get(`/merchant/transactions?per_page=1`).then(() => {
        // This is a shortcut: in real use, we'd have a dedicated endpoint
        setStep("form");
      }).catch(() => {});
    }
  }, [prefillTransactionId, open]);

  const search = async () => {
    if (!query && searchBy !== "date") return;
    setSearching(true);
    try {
      const res = await api.get("/merchant/customers/search", {
        params: { q: query, by: searchBy, limit: 30 },
      });
      setResults(res.data.items || []);
    } catch (e) {
      toast.error("Arama başarısız");
    } finally {
      setSearching(false);
    }
  };

  const pick = (tx) => {
    setSelected(tx);
    setAmount(((tx.amount_display_minor || 0) / 100).toFixed(2));
    setStep("form");
  };

  const submit = async () => {
    if (!selected) return;
    const reasonTrim = reason.trim();
    if (reasonTrim.length < 3) {
      toast.error("Sebep zorunlu (en az 3 karakter)");
      return;
    }
    const amtMinor = Math.round(parseFloat(amount || "0") * 100);
    if (!amtMinor || amtMinor <= 0) {
      toast.error("Geçerli bir tutar girin");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post("/merchant/refund-requests", {
        merchant_transaction_id: selected.id,
        refund_amount_minor: amtMinor,
        reason: reasonTrim,
        priority,
        customer_waiting: customerWaiting,
        note,
      });
      toast.success("İade oluşturuldu ve onaya gönderildi");
      onCreated?.(res.data);
      onClose?.();
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Talep oluşturulamadı");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
        <div className="p-5 border-b border-zinc-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-zinc-900">İade Talebi Oluştur</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {step === "search" ? "Müşteri veya ödeme arayın" : "Talep detayları"}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-zinc-100 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto flex-1">
          {step === "search" && (
            <>
              <div className="flex gap-2 mb-3">
                {[
                  { key: "name", label: "İsim" },
                  { key: "phone", label: "Telefon" },
                  { key: "date", label: "Tarih" },
                  { key: "amount", label: "Tutar" },
                ].map((o) => (
                  <button
                    key={o.key}
                    onClick={() => setSearchBy(o.key)}
                    className={`px-3 py-1 text-xs rounded-full border ${
                      searchBy === o.key
                        ? "bg-zinc-900 text-white border-zinc-900"
                        : "bg-white text-zinc-600 border-zinc-200"
                    }`}
                  >{o.label}</button>
                ))}
              </div>
              <div className="flex gap-2 mb-4">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={
                    searchBy === "date" ? "YYYY-MM-DD" :
                    searchBy === "amount" ? "50.00" :
                    "Müşteri ismi..."
                  }
                  className="flex-1 h-11 rounded-lg border border-zinc-300 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  onKeyDown={(e) => e.key === "Enter" && search()}
                />
                <button
                  onClick={search}
                  className="px-4 h-11 rounded-lg bg-zinc-900 text-white text-sm font-medium hover:bg-black flex items-center gap-2"
                >
                  <Search className="h-4 w-4" /> Ara
                </button>
              </div>

              {searching && <p className="text-sm text-zinc-400">Aranıyor...</p>}
              <div className="space-y-2">
                {results.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => pick(r)}
                    className="w-full text-left p-3 rounded-lg border border-zinc-200 hover:bg-zinc-50 transition"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-medium text-zinc-900">{r.customer_name || "-"}</p>
                        <p className="text-xs text-zinc-500">{r.customer_phone || "-"}</p>
                        <p className="text-xs text-zinc-400 mt-0.5">{formatDateTR(r.created_at)}</p>
                      </div>
                      <p className="font-semibold text-zinc-900">
                        {formatMoney(r.amount_display_minor, r.base_currency)}
                      </p>
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-1">State: {r.state}</p>
                  </button>
                ))}
                {!searching && query && !results.length && (
                  <p className="text-sm text-zinc-400">Sonuç bulunamadı.</p>
                )}
              </div>
            </>
          )}

          {step === "form" && selected && (
            <>
              <div className="bg-zinc-50 rounded-lg p-3 mb-4">
                <p className="text-xs text-zinc-500">Seçilen ödeme</p>
                <p className="font-semibold text-zinc-900">{selected.customer_name} · {selected.customer_phone}</p>
                <p className="text-sm text-zinc-600">{formatMoney(selected.amount_display_minor, selected.base_currency)}</p>
              </div>

              <label className="block text-sm mb-3">
                <span className="text-zinc-700 font-medium">İade Tutarı</span>
                <input
                  type="number" step="0.01" value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="mt-1 w-full h-11 rounded-lg border border-zinc-300 px-3 text-sm"
                />
              </label>

              <div className="block text-sm mb-3">
                <span className="text-zinc-700 font-medium">Öncelik</span>
                <div className="flex gap-2 mt-1">
                  {[
                    { k: "normal", l: "Normal" },
                    { k: "high", l: "Yüksek" },
                    { k: "urgent", l: "Acil" },
                  ].map((o) => (
                    <button
                      key={o.k}
                      onClick={() => setPriority(o.k)}
                      className={`px-3 py-2 text-xs rounded-lg border flex-1 ${
                        priority === o.k
                          ? "bg-zinc-900 text-white border-zinc-900"
                          : "bg-white text-zinc-600 border-zinc-200"
                      }`}
                    >{o.l}</button>
                  ))}
                </div>
                {priority === "urgent" && (
                  <p className="text-[11px] text-amber-700 mt-1 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" /> Günde max 2 acil talep; aşım → otomatik Yüksek'e düşer.
                  </p>
                )}
              </div>

              <label className="block text-sm mb-3">
                <span className="text-zinc-700 font-medium">Sebep <span className="text-red-500">*</span></span>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  placeholder="Neden iade gerekiyor?"
                  className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                />
              </label>

              <label className="block text-sm mb-3">
                <span className="text-zinc-700 font-medium">Not (opsiyonel)</span>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="mt-1 w-full h-11 rounded-lg border border-zinc-300 px-3 text-sm"
                />
              </label>

              <label className="flex items-center gap-2 text-sm mb-4">
                <input
                  type="checkbox"
                  checked={customerWaiting}
                  onChange={(e) => setCustomerWaiting(e.target.checked)}
                  className="rounded"
                />
                <span className="text-zinc-700">Müşteri bekliyor (kırmızı rozet eklenir)</span>
              </label>
            </>
          )}
        </div>

        <div className="p-4 border-t border-zinc-100 flex gap-2 justify-end">
          {step === "form" && (
            <button
              onClick={() => setStep("search")}
              className="px-4 h-11 rounded-lg bg-white border border-zinc-200 text-zinc-700 text-sm"
            >Geri</button>
          )}
          <button
            onClick={onClose}
            className="px-4 h-11 rounded-lg bg-white border border-zinc-200 text-zinc-700 text-sm"
          >İptal</button>
          {step === "form" && (
            <button
              onClick={submit}
              disabled={submitting || !reason.trim()}
              className="px-4 h-11 rounded-lg bg-zinc-900 text-white text-sm font-medium hover:bg-black disabled:opacity-50"
            >{submitting ? "Gönderiliyor..." : "Talep Oluştur"}</button>
          )}
        </div>
      </div>
    </div>
  );
}
