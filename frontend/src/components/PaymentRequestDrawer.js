import { useState, useEffect, useMemo, useRef } from "react";
import api from "../api/api";
import { toast } from "sonner";
import { X, Search, Plus, Send, Loader2, User, Check, AlertCircle, Info } from "lucide-react";

/**
 * Pay-by-Link ("Ödeme İste") drawer.
 *
 * Tasarım dili: wallet alanındaki RefundRequestModal ile aynı çizgi —
 * minimalist, zinc paleti, yumuşak köşeler, saf Tailwind, lucide ikonları.
 *
 * Responsive: masaüstünde sağ Drawer, mobilde alttan Bottom-Sheet.
 *
 * Props:
 *   - open: bool
 *   - onClose: () => void
 *   - baseCurrency: "TRY" | "GBP"
 *   - currencySymbol: string ("₺" / "£")
 *   - onSubmit: async ({ customer_name, customer_phone, description, amount }) => void
 *       Optimistic UI parent (MerchantWallet) tarafında yönetilir.
 */
export default function PaymentRequestDrawer({
  open,
  onClose,
  baseCurrency = "TRY",
  currencySymbol = "₺",
  onSubmit,
}) {
  const [show, setShow] = useState(false);

  const [customers, setCustomers] = useState([]);
  const [query, setQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selected, setSelected] = useState(null); // { name, phone }

  const [addingNew, setAddingNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [savingNew, setSavingNew] = useState(false);

  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Minimum tahsilat tutarı (major birim) — backend MIN_ONLINE_PAYMENT_MINOR ile uyumlu
  const minMajor = baseCurrency === "GBP" ? 5 : 300;
  const minDisplay = `${currencySymbol}${minMajor.toLocaleString(baseCurrency === "GBP" ? "en-GB" : "tr-TR")}`;

  const dropdownRef = useRef(null);

  // Entrance animation + reset on close
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => setShow(true), 10);
      return () => clearTimeout(t);
    }
    setShow(false);
    setQuery(""); setSelected(null); setDropdownOpen(false);
    setAddingNew(false); setNewName(""); setNewPhone("");
    setDescription(""); setAmount(""); setError("");
  }, [open]);

  // Load customers when opened
  useEffect(() => {
    if (!open) return;
    api.get("/customers")
      .then((res) => setCustomers(Array.isArray(res.data) ? res.data : []))
      .catch(() => setCustomers([]));
  }, [open]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return customers.slice(0, 50);
    return customers
      .filter((c) =>
        (c.name || "").toLowerCase().includes(q) ||
        (c.phone || "").toLowerCase().includes(q)
      )
      .slice(0, 50);
  }, [customers, query]);

  const pickCustomer = (c) => {
    setSelected({ name: c.name, phone: c.phone });
    setQuery(c.name || c.phone || "");
    setDropdownOpen(false);
  };

  const handleAddNew = async () => {
    const name = newName.trim();
    const phone = newPhone.trim();
    if (!name) { toast.error("İsim zorunlu"); return; }
    if (phone.length < 10) { toast.error("Geçerli bir telefon girin"); return; }
    setSavingNew(true);
    try {
      await api.post("/customers", { name, phone });
      const created = { name, phone };
      setCustomers((prev) => [created, ...prev]);
      pickCustomer(created);
      setAddingNew(false);
      setNewName(""); setNewPhone("");
      toast.success("Müşteri eklendi");
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Müşteri eklenemedi");
    } finally {
      setSavingNew(false);
    }
  };

  const handleSubmit = async () => {
    setError("");
    if (!selected || !selected.phone) {
      setError("Lütfen bir müşteri seçin");
      return;
    }
    if (!description.trim()) {
      setError("Açıklama zorunlu");
      return;
    }
    const amt = parseFloat(String(amount).replace(",", "."));
    if (!amt || amt <= 0) {
      setError("Geçerli bir tutar girin");
      return;
    }
    if (amt < minMajor) {
      setError(`Minimum tutar ${minDisplay} olmalıdır`);
      return;
    }

    setSubmitting(true);
    const payload = {
      customer_name: selected.name || "",
      customer_phone: selected.phone,
      description: description.trim(),
      amount: amt,
    };
    // Optimistic UI: drawer anında kapanır, parent geçici satırı yönetir.
    onClose?.();
    try {
      await onSubmit?.(payload);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/50 transition-opacity duration-300 ${show ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />

      {/* Panel — mobile bottom-sheet / desktop right drawer */}
      <div
        className={`absolute bg-white shadow-xl flex flex-col
          inset-x-0 bottom-0 rounded-t-2xl max-h-[90vh]
          md:inset-y-0 md:right-0 md:left-auto md:bottom-auto md:h-full md:w-full md:max-w-md md:rounded-t-none md:rounded-l-2xl
          transition-transform duration-300 ease-out
          ${show ? "translate-y-0 md:translate-x-0" : "translate-y-full md:translate-y-0 md:translate-x-full"}`}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-zinc-900">Ödeme İste</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Müşteriye WhatsApp ile tahsilat linki gönderin</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-zinc-100 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {/* Nasıl çalışır bilgilendirmesi */}
          <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2.5 flex items-start gap-2">
            <Info className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
            <p className="text-[11px] leading-relaxed text-blue-800">
              Müşteriye ödeme tutarını içeren bir <b>WhatsApp mesajı</b> gönderilir.
              Müşteri linke tıklayıp kartıyla güvenli şekilde öder; ödeme onaylanınca
              tutar otomatik olarak cüzdanınıza eklenir.
            </p>
          </div>

          {/* Customer searchable dropdown */}
          <div ref={dropdownRef}>
            <span className="text-sm text-zinc-700 font-medium">Müşteri</span>
            <div className="relative mt-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
              <input
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSelected(null); setDropdownOpen(true); }}
                onFocus={() => setDropdownOpen(true)}
                placeholder="İsim veya telefon ile ara..."
                className="w-full h-11 rounded-lg border border-zinc-300 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
              {selected && (
                <Check className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-emerald-500" />
              )}

              {dropdownOpen && (
                <div className="absolute z-10 mt-1 w-full bg-white border border-zinc-200 rounded-lg shadow-lg max-h-56 overflow-y-auto">
                  {filtered.length > 0 ? (
                    filtered.map((c, i) => (
                      <button
                        key={`${c.phone}_${i}`}
                        onClick={() => pickCustomer(c)}
                        className="w-full text-left px-3 py-2 hover:bg-zinc-50 flex items-center gap-2"
                      >
                        <User className="h-4 w-4 text-zinc-400 shrink-0" />
                        <span className="flex-1 min-w-0">
                          <span className="block text-sm text-zinc-900 truncate">{c.name || "-"}</span>
                          <span className="block text-xs text-zinc-500">{c.phone}</span>
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="px-3 py-2 text-sm text-zinc-400">Müşteri bulunamadı</p>
                  )}
                  <button
                    onClick={() => { setAddingNew(true); setDropdownOpen(false); setNewName(query); }}
                    className="w-full text-left px-3 py-2 border-t border-zinc-100 text-sm text-zinc-700 hover:bg-zinc-50 flex items-center gap-2"
                  >
                    <Plus className="h-4 w-4" /> Yeni müşteri ekle
                  </button>
                </div>
              )}
            </div>

            {/* Inline quick-add */}
            {addingNew && (
              <div className="mt-2 p-3 rounded-lg border border-zinc-200 bg-zinc-50 space-y-2">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="İsim"
                  className="w-full h-10 rounded-lg border border-zinc-300 px-3 text-sm"
                />
                <input
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="Telefon (5xx...)"
                  className="w-full h-10 rounded-lg border border-zinc-300 px-3 text-sm"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => setAddingNew(false)}
                    className="flex-1 h-9 rounded-lg bg-white border border-zinc-200 text-zinc-600 text-sm"
                  >İptal</button>
                  <button
                    onClick={handleAddNew}
                    disabled={savingNew}
                    className="flex-1 h-9 rounded-lg bg-zinc-900 text-white text-sm font-medium hover:bg-black disabled:opacity-50 flex items-center justify-center gap-1.5"
                  >
                    {savingNew ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    Ekle
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Description */}
          <label className="block">
            <span className="text-sm text-zinc-700 font-medium">Açıklama</span>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Örn. Saç bakım paketi"
              className="mt-1 w-full h-11 rounded-lg border border-zinc-300 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </label>

          {/* Amount */}
          <label className="block">
            <span className="text-sm text-zinc-700 font-medium">Tutar</span>
            <div className="relative mt-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 text-sm">{currencySymbol}</span>
              <input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => { setAmount(e.target.value); setError(""); }}
                placeholder="0,00"
                className="w-full h-11 rounded-lg border border-zinc-300 pl-8 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <p className="text-[11px] text-zinc-400 mt-1">Para birimi: {baseCurrency} · Minimum {minDisplay}</p>
          </label>
        </div>

        {/* Footer action */}
        <div className="p-4 border-t border-zinc-100">
          {error && (
            <div className="mb-3 rounded-lg bg-red-50 border border-red-200 px-3 py-2 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
              <p className="text-xs text-red-700">{error}</p>
            </div>
          )}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full h-12 rounded-xl bg-zinc-900 text-white text-sm font-semibold hover:bg-black disabled:opacity-50 flex items-center justify-center gap-2 active:scale-[0.99] transition"
          >
            {submitting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
            Ödeme Linkini Gönder
          </button>
        </div>
      </div>
    </div>
  );
}
