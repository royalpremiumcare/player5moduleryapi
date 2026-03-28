import { useState, useEffect, useCallback, useRef } from "react";
import { Phone, PhoneCall, LogOut, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, Pause, Star } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import api from "../api/api";

const STATUS_CONFIG = {
  pool:           { label: "Havuzda",     cls: "bg-gray-100 text-gray-500" },
  claimed:        { label: "Arıyor...",   cls: "bg-yellow-100 text-yellow-700" },
  interested:     { label: "İlgilendi",   cls: "bg-blue-100 text-blue-700" },
  unreachable:    { label: "Ulaşılamadı",cls: "bg-orange-100 text-orange-700" },
  not_interested: { label: "İlgisiz",    cls: "bg-red-100 text-red-700" },
  waiting:        { label: "Beklemede",  cls: "bg-purple-100 text-purple-700" },
  registered:     { label: "Kayıt Oldu",cls: "bg-green-100 text-green-700" },
};

const CALL_STATUSES = [
  { key: "interested",     label: "İlgilendi",    icon: CheckCircle,  cls: "bg-blue-600 hover:bg-blue-700 text-white" },
  { key: "unreachable",   label: "Ulaşılamadı",  icon: PhoneCall,    cls: "bg-orange-500 hover:bg-orange-600 text-white" },
  { key: "not_interested",label: "İlgisiz",      icon: XCircle,      cls: "bg-red-500 hover:bg-red-600 text-white",  noteRequired: true },
  { key: "waiting",       label: "Beklemede",    icon: Pause,        cls: "bg-purple-500 hover:bg-purple-600 text-white", noteRequired: true },
  { key: "registered",    label: "Kayıt Oldu ✅",icon: Star,         cls: "bg-green-600 hover:bg-green-700 text-white" },
];

export default function MarketingPanel() {
  const { logout } = useAuth();
  const [profile, setProfile]       = useState(null);
  const [myStats, setMyStats]       = useState(null);
  const [tab, setTab]               = useState("pool"); // "pool" | "mine"
  const [leads, setLeads]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [activeLead, setActiveLead] = useState(null);
  const [callStatus, setCallStatus] = useState("");
  const [note, setNote]             = useState("");
  const [saving, setSaving]         = useState(false);
  const [claiming, setClaiming]     = useState(null);
  const [batches, setBatches]       = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(""); // batch_id filtresi

  // Countdown timer for claimed lead (15 min)
  const [timeLeft, setTimeLeft] = useState(null);
  const callCardRef = useRef(null);

  const load = useCallback(async (currentTab = tab, batchId = selectedBatch) => {
    setLoading(true);
    const batchParam = batchId ? `&batch_id=${batchId}` : "";
    const [leadsR, statsR, profileR, batchesR] = await Promise.allSettled([
      api.get(`/marketing/leads?tab=${currentTab}${batchParam}`),
      api.get("/marketing/my-stats"),
      profile ? Promise.resolve({ data: profile }) : api.get("/marketing/profile"),
      api.get("/marketing/leads/batches"),
    ]);
    if (leadsR.status === "fulfilled") setLeads(leadsR.value.data.leads || []);
    else { toast.error("Leadler yüklenemedi"); console.error("leads error", leadsR.reason); }
    if (statsR.status === "fulfilled") setMyStats(statsR.value.data);
    else console.error("stats error", statsR.reason?.response?.data || statsR.reason);
    if (profileR.status === "fulfilled" && !profile) setProfile(profileR.value.data);
    if (batchesR.status === "fulfilled") setBatches(batchesR.value.data.batches || []);
    else console.error("batches error", batchesR.reason?.response?.data || batchesR.reason);
    setLoading(false);
  }, [tab, profile, selectedBatch]);

  useEffect(() => { load(tab, selectedBatch); }, [tab, selectedBatch]);

  // Countdown for active lead
  useEffect(() => {
    if (!activeLead?.claimed_at) { setTimeLeft(null); return; }
    const expiry = new Date(activeLead.claimed_at).getTime() + 15 * 60 * 1000;
    const tick = () => {
      const remaining = Math.max(0, Math.floor((expiry - Date.now()) / 1000));
      setTimeLeft(remaining);
      if (remaining === 0) {
        setActiveLead(null);
        setCallStatus("");
        setNote("");
        toast.warning("Lead süresi doldu, havuza geri döndü");
        load("pool");
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activeLead?.claimed_at]);

  const claimLead = async (lead) => {
    setClaiming(lead.id);
    try {
      const res = await api.post(`/marketing/leads/${lead.id}/claim`);
      setActiveLead(res.data.lead);
      setCallStatus("");
      setNote("");
      setLeads(prev => prev.filter(l => l.id !== lead.id));
      // tel: linkini görünmez anchor ile aç — page state korunur
      const a = document.createElement("a");
      a.href = `tel:${lead.phone}`;
      a.setAttribute("rel", "noopener");
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Lead alınamadı");
      load(tab);
    } finally { setClaiming(null); }
  };

  const releaseLead = async () => {
    if (!activeLead) return;
    try {
      await api.post(`/marketing/leads/${activeLead.id}/release`);
      toast.info("Lead havuza bırakıldı");
      setActiveLead(null);
      setCallStatus("");
      setNote("");
      load("pool");
    } catch { toast.error("Bırakılamadı"); }
  };

  const saveLead = async () => {
    if (!callStatus) { toast.error("Arama sonucunu seçin"); return; }
    const cfg = CALL_STATUSES.find(s => s.key === callStatus);
    if (cfg?.noteRequired && !note.trim()) {
      toast.error("Bu durum için not zorunludur"); return;
    }
    setSaving(true);
    try {
      await api.put(`/marketing/leads/${activeLead.id}/status`, { status: callStatus, note });
      toast.success("Kaydedildi");
      setActiveLead(null);
      setCallStatus("");
      setNote("");
      load("mine");
      setTab("mine");
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    finally { setSaving(false); }
  };

  const fmtTime = (s) => {
    if (s === null) return "";
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-slate-900 text-white px-4 py-3 flex items-center gap-3 flex-shrink-0">
        <div className="w-7 h-7 bg-indigo-500 rounded-lg flex items-center justify-center">
          <span className="font-bold text-xs">P</span>
        </div>
        <span className="font-semibold text-sm">PLANN Tele-Satış</span>
        {profile && (
          <span className="text-slate-400 text-sm ml-1">— {profile.full_name || profile.username}</span>
        )}
        <div className="ml-auto flex items-center gap-3">
          <button onClick={() => load(tab)} className="p-1.5 hover:bg-slate-800 rounded-lg transition-colors">
            <RefreshCw className={`w-4 h-4 text-slate-400 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => logout()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors"
          >
            <LogOut className="w-4 h-4" /> Çıkış
          </button>
        </div>
      </header>

      <div className={`flex-1 max-w-2xl mx-auto w-full px-4 py-5 space-y-4 ${activeLead ? "pb-[420px]" : "pb-6"}`}>
        {/* My Stats */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Bugün",       value: myStats?.today_called ?? "—" },
            { label: "Toplam",      value: myStats?.total_called ?? "—" },
            { label: "İlgilendi",   value: myStats?.interested ?? "—" },
            { label: "Dönüşüm",    value: myStats ? `${myStats.conversion_rate}%` : "—" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-xl font-bold text-gray-900 mt-0.5">{value}</p>
            </div>
          ))}
        </div>

        {/* Active call card — fixed overlay */}
        {activeLead && (
          <div ref={callCardRef} className="fixed inset-x-0 bottom-0 z-50 px-4 pb-4 pt-2 bg-gradient-to-t from-black/40 to-transparent">
          <div className="bg-white rounded-2xl shadow-2xl border border-indigo-100 overflow-hidden max-w-2xl mx-auto">
            {/* Call header */}
            <div className="bg-indigo-600 px-5 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                  <Phone className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-white font-semibold">{activeLead.company_name}</p>
                  <a href={`tel:${activeLead.phone}`} className="text-indigo-200 text-sm hover:text-white flex items-center gap-1">
                    <PhoneCall className="w-3.5 h-3.5" />
                    {activeLead.phone}
                  </a>
                </div>
              </div>
              {timeLeft !== null && (
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-mono ${
                  timeLeft < 120 ? "bg-red-500 text-white animate-pulse" : "bg-white/20 text-white"
                }`}>
                  <Clock className="w-3.5 h-3.5" />
                  {fmtTime(timeLeft)}
                </div>
              )}
            </div>

            <div className="p-5 space-y-4">
              {/* Status buttons */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Arama Sonucu</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {CALL_STATUSES.map(({ key, label, icon: Icon, cls }) => (
                    <button
                      key={key}
                      onClick={() => { setCallStatus(key); if (!["not_interested","waiting"].includes(key)) setNote(""); }}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                        callStatus === key
                          ? cls + " ring-2 ring-offset-1 ring-current"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Note */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  Görüşme Notu
                  {["not_interested","waiting"].includes(callStatus) && (
                    <span className="text-red-500 ml-1">*zorunlu</span>
                  )}
                </p>
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  rows={3}
                  placeholder="Görüşme notunu girin..."
                  className={`w-full border rounded-xl px-3 py-2 text-sm resize-none focus:ring-2 outline-none transition-colors ${
                    ["not_interested","waiting"].includes(callStatus) && !note.trim()
                      ? "border-red-200 focus:ring-red-300"
                      : "border-gray-200 focus:ring-indigo-500 focus:border-indigo-500"
                  }`}
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={saveLead}
                  disabled={!callStatus || saving}
                  className="flex-1 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50"
                >
                  {saving ? "Kaydediliyor..." : "Kaydet"}
                </button>
                <button
                  onClick={releaseLead}
                  className="px-4 py-2.5 bg-gray-100 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
                >
                  Bırak
                </button>
              </div>
            </div>
          </div>
          </div>
        )}

        {/* Kampanya Seçici */}
        {batches.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-4 py-3 flex items-center gap-3">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex-shrink-0">Kampanya</span>
            <select
              value={selectedBatch}
              onChange={e => setSelectedBatch(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-gray-50"
            >
              <option value="">Tümü</option>
              {batches.map(b => (
                <option key={b.id} value={b.id}>
                  {b.batch_name} ({b.total} lead)
                </option>
              ))}
            </select>
            {selectedBatch && (
              <button
                onClick={() => setSelectedBatch("")}
                className="text-xs text-gray-400 hover:text-gray-600 flex-shrink-0"
              >
                Temizle
              </button>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
          {[
            { key: "pool", label: "Havuz" },
            { key: "mine", label: "Aramalarım" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === key ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Lead list */}
        <div className="space-y-2">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl p-4 animate-pulse">
                <div className="h-4 bg-gray-100 rounded w-1/3 mb-2" />
                <div className="h-3 bg-gray-100 rounded w-1/4" />
              </div>
            ))
          ) : leads.length === 0 ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-10 text-center">
              <Phone className="w-10 h-10 text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">
                {tab === "pool"
                ? (selectedBatch ? "Bu kampanyada aranacak lead yok" : "Havuzda aranacak lead yok")
                : "Henüz arama yapmadınız"}
              </p>
            </div>
          ) : (
            leads.map((lead) => {
              const st = STATUS_CONFIG[lead.status] || STATUS_CONFIG.pool;
              const isActive = activeLead?.id === lead.id;
              return (
                <div
                  key={lead.id}
                  className={`bg-white rounded-xl shadow-sm border p-4 transition-all ${
                    isActive ? "border-indigo-300 ring-1 ring-indigo-200" : "border-gray-100"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-2">
                        <p className="font-semibold text-gray-900 break-words">{lead.company_name}</p>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 mt-0.5 ${st.cls}`}>
                          {st.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 font-mono mt-0.5">{lead.phone}</p>
                      {!selectedBatch && lead.batch_name && (
                        <p className="text-xs text-indigo-400 mt-0.5">{lead.batch_name}</p>
                      )}
                      {lead.note && (
                        <p className="text-xs text-gray-400 mt-1 italic">"{lead.note}"</p>
                      )}
                    </div>
                    {tab === "pool" && !activeLead && (
                      <button
                        onClick={() => claimLead(lead)}
                        disabled={claiming === lead.id}
                        className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-60 flex-shrink-0"
                      >
                        <Phone className="w-4 h-4" />
                        {claiming === lead.id ? "..." : "Ara"}
                      </button>
                    )}
                    {tab === "mine" && lead.status !== "claimed" && (
                      <a
                        href={`tel:${lead.phone}`}
                        className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors flex-shrink-0"
                      >
                        <Phone className="w-4 h-4" />
                        Ara
                      </a>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
