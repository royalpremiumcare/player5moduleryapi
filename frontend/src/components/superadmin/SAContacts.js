import { useState, useEffect, useMemo } from "react";
import { Search, Phone, Mail, Clock, CheckCircle2, Trash, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

const statusMap = {
  pending:   { label: "Beklemede",  cls: "bg-yellow-100 text-yellow-700" },
  contacted: { label: "Ulaşıldı",   cls: "bg-green-100 text-green-700" },
  resolved:  { label: "Çözüldü",    cls: "bg-gray-100 text-gray-600" },
};

export default function SAContacts() {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/contact-requests");
      setContacts(res.data.contacts || []);
    } catch { toast.error("İletişim talepleri yüklenemedi"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const updateStatus = async (id, status) => {
    try {
      await api.put(`/superadmin/contact-requests/${id}/status`, { status });
      setContacts(prev => prev.map(c => c.id === id ? { ...c, status } : c));
      toast.success("Durum güncellendi");
    } catch { toast.error("Güncellenemedi"); }
  };

  const deleteContact = async (id) => {
    if (!window.confirm("Bu iletişim talebini silmek istiyor musunuz?")) return;
    try {
      await api.delete(`/superadmin/contact-requests/${id}`);
      setContacts(prev => prev.filter(c => c.id !== id));
      toast.success("Silindi");
    } catch { toast.error("Silinemedi"); }
  };

  const bulkDeleteResolved = async () => {
    const count = contacts.filter(c => c.status === "resolved").length;
    if (!count) { toast.info("Çözülen talep yok"); return; }
    if (!window.confirm(`${count} adet çözülen talebi silmek istiyor musunuz?`)) return;
    try {
      await api.delete("/superadmin/contact-requests/bulk/delete-resolved");
      toast.success(`${count} talep silindi`);
      load();
    } catch { toast.error("Toplu silme başarısız"); }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return contacts.filter(c =>
      c.name?.toLowerCase().includes(q) ||
      c.phone?.includes(q) ||
      c.email?.toLowerCase().includes(q)
    );
  }, [contacts, search]);

  const pending = contacts.filter(c => c.status === "pending").length;

  return (
    <div className="p-6">
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Ad, telefon, e-posta..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          />
        </div>
        {pending > 0 && (
          <span className="px-2.5 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded-full">
            {pending} beklemede
          </span>
        )}
        <button
          onClick={bulkDeleteResolved}
          className="px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-red-100"
        >
          Çözülenleri Sil
        </button>
        <button onClick={load} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* List */}
      <div className="space-y-3">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl p-4 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-1/3 mb-2" />
              <div className="h-3 bg-gray-100 rounded w-1/2" />
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-10 text-center text-sm text-gray-400">
            {search ? "Arama sonucu yok" : "İletişim talebi bulunamadı"}
          </div>
        ) : (
          filtered.map((c) => {
            const st = statusMap[c.status] || { label: c.status, cls: "bg-gray-100 text-gray-600" };
            return (
              <div key={c.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-gray-900">{c.name}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.cls}`}>
                        {st.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm">
                      <a href={`tel:${c.phone}`} className="flex items-center gap-1 text-indigo-600 hover:underline">
                        <Phone className="w-3.5 h-3.5" /> {c.phone}
                      </a>
                      {c.email && (
                        <a href={`mailto:${c.email}`} className="flex items-center gap-1 text-indigo-600 hover:underline">
                          <Mail className="w-3.5 h-3.5" /> {c.email}
                        </a>
                      )}
                    </div>
                    {c.message && (
                      <p className="mt-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">{c.message}</p>
                    )}
                    <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
                      <Clock className="w-3.5 h-3.5" />
                      {c.created_at ? new Date(c.created_at).toLocaleString("tr-TR") : "—"}
                    </div>
                  </div>
                  <div className="flex gap-1.5 flex-shrink-0">
                    {c.status !== "contacted" && (
                      <button
                        onClick={() => updateStatus(c.id, "contacted")}
                        className="p-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition-colors"
                        title="Ulaşıldı"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                      </button>
                    )}
                    {c.status !== "resolved" && (
                      <button
                        onClick={() => updateStatus(c.id, "resolved")}
                        className="p-2 bg-gray-50 text-gray-600 rounded-lg hover:bg-gray-100 transition-colors text-xs font-medium px-3"
                        title="Çözüldü"
                      >
                        ✓
                      </button>
                    )}
                    <button
                      onClick={() => deleteContact(c.id)}
                      className="p-2 bg-red-50 text-red-500 rounded-lg hover:bg-red-100 transition-colors"
                      title="Sil"
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
