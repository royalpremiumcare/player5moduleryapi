import { useState, useEffect, useMemo } from "react";
import { Search, Mail, Send, CheckSquare, Square, RefreshCw, Users, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

export default function SAEmailBroadcast() {
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [sendToAll, setSendToAll] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/organizations");
      setOrgs(res.data.organizations || []);
    } catch {
      toast.error("İşletmeler yüklenemedi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return orgs.filter(o =>
      o.isletme_adi?.toLowerCase().includes(q) ||
      o.admin_full_name?.toLowerCase().includes(q) ||
      o.admin_email?.toLowerCase().includes(q)
    );
  }, [orgs, search]);

  const toggleOrg = (orgId) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(orgId) ? next.delete(orgId) : next.add(orgId);
      return next;
    });
  };

  const allFilteredSelected = filtered.length > 0 && filtered.every(o => selected.has(o.organization_id));
  const toggleAllFiltered = () => {
    setSelected(prev => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        filtered.forEach(o => next.delete(o.organization_id));
      } else {
        filtered.forEach(o => next.add(o.organization_id));
      }
      return next;
    });
  };

  const recipientCount = sendToAll ? orgs.length : selected.size;

  const handleSend = async () => {
    if (!subject.trim() || !message.trim()) {
      toast.error("Konu ve mesaj zorunludur");
      return;
    }
    if (!sendToAll && selected.size === 0) {
      toast.error("En az bir işletme seçin veya 'Tüm işletmelere gönder' seçeneğini işaretleyin");
      return;
    }
    const confirmMsg = sendToAll
      ? `Mail TÜM işletmelere (${orgs.length}) gönderilecek. Emin misiniz?`
      : `Mail ${selected.size} işletmeye gönderilecek. Emin misiniz?`;
    if (!window.confirm(confirmMsg)) return;

    setSending(true);
    setResult(null);
    try {
      const res = await api.post("/superadmin/broadcast-email", {
        subject: subject.trim(),
        message: message,
        organization_ids: sendToAll ? null : Array.from(selected),
        send_to_all: sendToAll,
      });
      setResult(res.data);
      toast.success(`${res.data.sent_count} mail gönderildi${res.data.failed_count ? `, ${res.data.failed_count} başarısız` : ""}`);
      if (res.data.sent_count > 0) {
        setSubject("");
        setMessage("");
        setSelected(new Set());
        setSendToAll(false);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Mail gönderilirken hata oluştu");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Sol: Alıcı seçimi */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 flex flex-col max-h-[calc(100vh-160px)]">
        <div className="p-4 border-b border-gray-100 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-500" />
              Alıcılar
              <span className="text-xs font-normal text-gray-400">({recipientCount} seçili)</span>
            </h3>
            <button onClick={load} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
              <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Tümüne gönder */}
          <label className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-colors ${
            sendToAll ? "bg-indigo-50 border-indigo-300" : "border-gray-200 hover:bg-gray-50"
          }`}>
            <input
              type="checkbox"
              checked={sendToAll}
              onChange={e => setSendToAll(e.target.checked)}
              className="w-4 h-4 accent-indigo-600"
            />
            <span className="text-sm font-medium text-gray-800">Tüm işletmelere gönder ({orgs.length})</span>
          </label>

          {!sendToAll && (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="İşletme veya e-posta ara..."
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
              </div>
              <button
                onClick={toggleAllFiltered}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors whitespace-nowrap"
              >
                {allFilteredSelected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
                {allFilteredSelected ? "Seçimi Kaldır" : "Tümünü Seç"}
              </button>
            </div>
          )}
        </div>

        {/* Liste */}
        <div className={`flex-1 overflow-y-auto divide-y divide-gray-50 ${sendToAll ? "opacity-40 pointer-events-none" : ""}`}>
          {loading ? (
            <div className="p-6 text-center text-sm text-gray-400">Yükleniyor...</div>
          ) : filtered.length === 0 ? (
            <div className="p-6 text-center text-sm text-gray-400">İşletme bulunamadı</div>
          ) : (
            filtered.map(org => {
              const checked = selected.has(org.organization_id);
              const hasEmail = org.admin_email && org.admin_email !== "-" && org.admin_email.includes("@");
              return (
                <label
                  key={org.organization_id}
                  className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                    checked ? "bg-indigo-50/60" : "hover:bg-gray-50"
                  } ${!hasEmail ? "opacity-50" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleOrg(org.organization_id)}
                    disabled={!hasEmail}
                    className="w-4 h-4 accent-indigo-600 flex-shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{org.isletme_adi}</p>
                    <p className="text-xs text-gray-400 truncate">
                      {hasEmail ? `${org.admin_full_name} · ${org.admin_email}` : "E-posta yok"}
                    </p>
                  </div>
                </label>
              );
            })
          )}
        </div>
      </div>

      {/* Sağ: Mail içeriği */}
      <div className="space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-4">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Mail className="w-4 h-4 text-indigo-500" />
            Mail İçeriği
          </h3>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Konu</label>
            <input
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="Örn: Önemli Duyuru"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Mesaj</label>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              rows={12}
              placeholder={"Merhaba,\n\nMesajınızı buraya yazın...\n\nİyi çalışmalar"}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-y"
            />
            <p className="text-xs text-gray-400 mt-1">
              Mail, PLANN logolu şablon içinde gönderilir. Satır sonları korunur; HTML de kullanabilirsiniz.
            </p>
          </div>
          <button
            onClick={handleSend}
            disabled={sending || recipientCount === 0 || !subject.trim() || !message.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {sending ? "Gönderiliyor..." : `Gönder (${recipientCount} alıcı)`}
          </button>
        </div>

        {/* Sonuç */}
        {result && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Gönderim Sonucu</h3>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="bg-emerald-50 rounded-lg p-3">
                <p className="text-xl font-bold text-emerald-600">{result.sent_count}</p>
                <p className="text-xs text-emerald-700">Gönderildi</p>
              </div>
              <div className="bg-red-50 rounded-lg p-3">
                <p className="text-xl font-bold text-red-600">{result.failed_count}</p>
                <p className="text-xs text-red-700">Başarısız</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xl font-bold text-gray-600">{result.skipped_count}</p>
                <p className="text-xs text-gray-500">Atlandı</p>
              </div>
            </div>
            {result.failed?.length > 0 && (
              <div className="mt-3 text-xs text-red-600">
                Başarısız: {result.failed.join(", ")}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
