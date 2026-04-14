import { useState, useEffect, useMemo } from "react";
import { Send, CheckCheck, Eye, AlertTriangle, MessageCircle, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

const STATUS_CONFIG = {
  sent:      { label: "Gönderildi",  cls: "bg-indigo-100 text-indigo-700",  icon: Send },
  delivered: { label: "İletildi",    cls: "bg-green-100 text-green-700",    icon: CheckCheck },
  read:      { label: "Okundu",      cls: "bg-purple-100 text-purple-700",  icon: Eye },
  failed:    { label: "Başarısız",   cls: "bg-red-100 text-red-700",        icon: AlertTriangle },
};

export default function SAWhatsApp() {
  const [data, setData]         = useState({ logs: [], total: 0, summary: { sent: 0, delivered: 0, read: 0, failed: 0 } });
  const [loading, setLoading]   = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch]     = useState("");

  const load = async (sf = statusFilter) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: 300 });
      if (sf) params.set("status_filter", sf);
      const res = await api.get(`/superadmin/whatsapp-logs?${params}`);
      setData(res.data);
    } catch { toast.error("WA logları yüklenemedi"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleFilter = (s) => {
    const next = statusFilter === s ? "" : s;
    setStatusFilter(next);
    load(next);
  };

  const filtered = useMemo(() => {
    if (!search.trim()) return data.logs;
    const q = search.toLowerCase();
    return data.logs.filter(l =>
      l.recipient?.includes(q) ||
      l.message_id?.toLowerCase().includes(q) ||
      l.org_name?.toLowerCase().includes(q)
    );
  }, [data.logs, search]);

  const summaryCards = [
    { key: "sent",      ...STATUS_CONFIG.sent,      value: data.summary.sent },
    { key: "delivered", ...STATUS_CONFIG.delivered,  value: data.summary.delivered },
    { key: "read",      ...STATUS_CONFIG.read,       value: data.summary.read },
    { key: "failed",    ...STATUS_CONFIG.failed,     value: data.summary.failed },
  ];

  return (
    <div className="p-6 space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {summaryCards.map(({ key, label, cls, icon: Icon, value }) => (
          <button
            key={key}
            onClick={() => handleFilter(key)}
            className={`bg-white rounded-xl shadow-sm border p-4 text-left transition-all ${
              statusFilter === key ? "border-indigo-400 ring-2 ring-indigo-200" : "border-gray-100 hover:border-gray-200"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${cls}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-gray-500">{label}</p>
                <p className="text-xl font-bold text-gray-900">{value}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Total + toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Alıcı no veya mesaj ID..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 outline-none"
          />
        </div>
        <span className="text-sm text-gray-500">{filtered.length} / {data.total} log</span>
        {statusFilter && (
          <button onClick={() => handleFilter("")} className="text-xs text-indigo-600 underline">
            Filtreyi kaldır
          </button>
        )}
        <button onClick={() => load()} className="p-2 hover:bg-gray-100 rounded-lg ml-auto">
          <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Durum</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">İşletme</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Alıcı</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Kaynak</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Tarih</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Hata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded w-20" /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-400">
                    {statusFilter ? `"${STATUS_CONFIG[statusFilter]?.label}" durumunda log yok` : "Log bulunamadı"}
                  </td>
                </tr>
              ) : (
                filtered.map((log, idx) => {
                  const cfg = STATUS_CONFIG[log.status] || {};
                  const Icon = cfg.icon;
                  const isFailed = log.status === "failed";
                  return (
                    <tr key={`${log.message_id}-${idx}`} className={isFailed ? "bg-red-50/50" : "hover:bg-gray-50/60"}>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.cls || ""}`}>
                          {Icon && <Icon className="w-3 h-3" />}
                          {cfg.label || log.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">{log.org_name || <span className="text-gray-400 italic">—</span>}</td>
                      <td className="px-4 py-3 font-mono text-gray-700">+{log.recipient}</td>
                      <td className="px-4 py-3 text-xs">
                        {(() => {
                          const src = (log.source || log.template_name || "").toLowerCase();
                          if (src.includes("reminder")) return <span className="text-amber-600">Hatırlatma</span>;
                          if (src.includes("confirm") || src.includes("booking")) return <span className="text-green-600">Online</span>;
                          if (src.includes("session") || src.includes("seans")) return <span className="text-purple-600">Seans</span>;
                          return <span className="text-blue-600">Panel</span>;
                        })()}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                        {log.recorded_at ? new Date(log.recorded_at).toLocaleString("tr-TR") : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {log.errors?.length > 0 && (
                          <div className="text-xs text-red-600">
                            {log.errors.map((e, i) => (
                              <p key={i}><strong>{e.code}</strong>: {e.title || e.message || JSON.stringify(e)}</p>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
