/**
 * Plann — Marketing Panel (orchestrator)
 *
 * Mobile-first tele-satış paneli. Üç sekme:
 *   - Havuz       → SweepView: tek lead full-card, "Ara" tek tıkla claim+dial
 *   - Aramalarım  → MineView: pazarlamacının geçmiş aramaları, sub-filter
 *   - İşletmeler  → MarketingOrganizations (mevcut komponent)
 *
 * Bir lead claim edildiğinde tüm sekme görünümünün üzerine CallSession
 * full-screen overlay olarak yerleşir; 15 dakikalık geri sayım çalışır,
 * pazarlamacı status seçer + not yazar → "Kaydet & WhatsApp Aç" tek
 * butonla kaydedip WhatsApp Business deep link tetikler.
 *
 * State'ler ve API çağrıları burada, UI prezentasyonu alt komponentlerde.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  RefreshCw,
  LogOut,
  SlidersHorizontal,
  Phone,
  Inbox,
  Building2,
  X,
  TrendingUp,
  Target,
  CheckCircle2,
  PhoneCall,
} from "lucide-react";

import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import MarketingOrganizations from "./MarketingOrganizations";
import MarketingSweepView from "./marketing/SweepView";
import MarketingCallSession from "./marketing/CallSession";
import MarketingMineView from "./marketing/MineView";
import { CALL_STATUSES } from "./marketing/statuses";
import { openMarketingFollowUp } from "../constants/marketing";

/** Bottom tab definitions */
const TABS = [
  { key: "pool",          label: "Havuz",      icon: Inbox     },
  { key: "mine",          label: "Aramalarım", icon: PhoneCall },
  { key: "organizations", label: "İşletmeler", icon: Building2 },
];

export default function MarketingPanel() {
  const { logout } = useAuth();

  // --- Static (mount-once) data ---
  const [profile, setProfile]   = useState(null);
  const [batches, setBatches]   = useState([]);
  const [sectors, setSectors]   = useState([]);

  // --- Tab + filter state ---
  const [tab, setTab]                     = useState("pool");
  const [selectedBatch, setSelectedBatch] = useState("");
  const [selectedSector, setSelectedSector] = useState("");
  const [showFilters, setShowFilters]     = useState(false);

  // --- Lead data (refreshes on tab/filter change) ---
  const [leads, setLeads]     = useState([]);
  const [myStats, setMyStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // --- Active call session state ---
  const [activeLead, setActiveLead] = useState(null);
  const [callStatus, setCallStatus] = useState("");
  const [note, setNote]             = useState("");
  const [saving, setSaving]         = useState(false);
  const [claiming, setClaiming]     = useState(null);
  const [timeLeft, setTimeLeft]     = useState(null);

  // ---- Data loaders --------------------------------------------------------

  const load = useCallback(
    async (currentTab = tab, batchId = selectedBatch, sector = selectedSector) => {
      if (currentTab === "organizations") {
        setLoading(false);
        return;
      }
      setLoading(true);
      const batchParam  = batchId ? `&batch_id=${batchId}` : "";
      const sectorParam = sector  ? `&sector=${encodeURIComponent(sector)}` : "";
      const [leadsR, statsR] = await Promise.allSettled([
        api.get(`/marketing/leads?tab=${currentTab}${batchParam}${sectorParam}`),
        api.get("/marketing/my-stats"),
      ]);
      if (leadsR.status === "fulfilled") setLeads(leadsR.value.data.leads || []);
      else {
        toast.error("Leadler yüklenemedi");
        console.error("leads error", leadsR.reason);
      }
      if (statsR.status === "fulfilled") setMyStats(statsR.value.data);
      else console.error("stats error", statsR.reason);
      setLoading(false);
    },
    [tab, selectedBatch, selectedSector]
  );

  // Tab/filter değişince yeniden çek
  useEffect(() => { load(tab, selectedBatch, selectedSector); }, [tab, selectedBatch, selectedSector, load]);

  // Profile / batches / sectors — mount-once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [profileR, batchesR, sectorsR] = await Promise.allSettled([
        api.get("/marketing/profile"),
        api.get("/marketing/leads/batches"),
        api.get("/marketing/leads/sectors"),
      ]);
      if (cancelled) return;
      if (profileR.status === "fulfilled") setProfile(profileR.value.data);
      if (batchesR.status === "fulfilled") setBatches(batchesR.value.data.batches || []);
      if (sectorsR.status === "fulfilled") setSectors(sectorsR.value.data.sectors || []);
    })();
    return () => { cancelled = true; };
  }, []);

  // ---- Active lead countdown (15-min claim lock) --------------------------

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
        if (tab !== "organizations") load("pool");
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activeLead?.claimed_at, tab, load]);

  // ---- Actions ------------------------------------------------------------

  const claimLead = async (lead) => {
    setClaiming(lead.id);
    try {
      const res = await api.post(`/marketing/leads/${lead.id}/claim`);
      setActiveLead(res.data.lead);
      setCallStatus("");
      setNote("");
      // Listeden çıkar — sweep view bir sonraki lead'e otomatik geçer.
      setLeads((prev) => prev.filter((l) => l.id !== lead.id));
      // Telefon dialer'ı tetikle (anchor click, native + PWA uyumlu).
      const a = document.createElement("a");
      a.href = `tel:${lead.phone}`;
      a.setAttribute("rel", "noopener");
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Lead alınamadı");
      if (tab !== "organizations") load(tab);
    } finally {
      setClaiming(null);
    }
  };

  const releaseLead = async () => {
    if (!activeLead) return;
    try {
      await api.post(`/marketing/leads/${activeLead.id}/release`);
      toast.info("Lead havuza bırakıldı");
      setActiveLead(null);
      setCallStatus("");
      setNote("");
      if (tab !== "organizations") load("pool");
    } catch {
      toast.error("Bırakılamadı");
    }
  };

  const saveLead = async () => {
    if (!callStatus) { toast.error("Arama sonucunu seçin"); return; }
    const cfg = CALL_STATUSES.find((s) => s.key === callStatus);
    if (cfg?.noteRequired && !note.trim()) {
      toast.error("Bu durum için not zorunludur");
      return;
    }
    setSaving(true);
    const currentLeadPhone = activeLead.phone;
    const currentLeadId    = activeLead.id;
    try {
      await api.put(`/marketing/leads/${currentLeadId}/status`, { status: callStatus, note });
      toast.success("Kaydedildi");
      setActiveLead(null);
      setCallStatus("");
      setNote("");
      if (tab !== "organizations") load(tab);
      // WhatsApp Business deep link (text prefilled, PDF manuel ekleniyor).
      const opened = openMarketingFollowUp(currentLeadPhone);
      if (!opened) toast.warning("WhatsApp linki açılamadı (telefon eksik)");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  // ---- Render ------------------------------------------------------------

  const hasFilters = batches.length > 0 || sectors.length > 0;
  const activeFilterCount = (selectedBatch ? 1 : 0) + (selectedSector ? 1 : 0);

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-50 to-white flex flex-col w-full">
      {/* ---- Header ---- */}
      <header
        className="px-4 py-3 flex items-center gap-3 sticky top-0 z-30 bg-white/85 backdrop-blur-lg border-b border-zinc-100"
        style={{ paddingTop: "calc(max(env(safe-area-inset-top, 0px), 12px))" }}
      >
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 shadow-sm">
          <span className="text-white font-bold text-sm">P</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-zinc-900 text-sm leading-tight">PLANN Tele-Satış</p>
          {profile && (
            <p className="text-[11px] text-zinc-500 truncate">
              {profile.full_name || profile.username}
            </p>
          )}
        </div>
        {hasFilters && tab !== "organizations" && (
          <button
            type="button"
            onClick={() => setShowFilters(true)}
            className="relative p-2 rounded-xl hover:bg-zinc-100 transition-colors"
            aria-label="Filtreler"
          >
            <SlidersHorizontal className="w-4.5 h-4.5 text-zinc-600" />
            {activeFilterCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-indigo-600 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>
        )}
        <button
          type="button"
          onClick={() => load(tab)}
          className="p-2 rounded-xl hover:bg-zinc-100 transition-colors"
          aria-label="Yenile"
        >
          <RefreshCw className={`w-4.5 h-4.5 text-zinc-600 ${loading ? "animate-spin" : ""}`} />
        </button>
        <button
          type="button"
          onClick={() => logout()}
          className="p-2 rounded-xl hover:bg-rose-50 hover:text-rose-600 text-zinc-500 transition-colors"
          aria-label="Çıkış"
        >
          <LogOut className="w-4.5 h-4.5" />
        </button>
      </header>

      {/* ---- Body ---- */}
      <main className="flex-1 overflow-y-auto px-4 pt-4 pb-32">
        {/* Mini stats — pool/mine için göster, organizations için gizle */}
        {tab !== "organizations" && myStats && (
          <div className="max-w-md mx-auto grid grid-cols-4 gap-2 mb-4">
            <StatPill icon={Phone}        label="Bugün"     value={myStats.today_called ?? "—"} accent="indigo" />
            <StatPill icon={TrendingUp}   label="Toplam"    value={myStats.total_called ?? "—"} accent="zinc" />
            <StatPill icon={Target}       label="İlgilendi" value={myStats.interested ?? "—"}   accent="emerald" />
            <StatPill icon={CheckCircle2} label="Dönüşüm"   value={myStats.conversion_rate != null ? `${myStats.conversion_rate}%` : "—"} accent="violet" />
          </div>
        )}

        {/* Tab içerikleri */}
        {tab === "pool" && (
          <MarketingSweepView
            leads={leads}
            loading={loading}
            claiming={claiming}
            onClaim={claimLead}
            selectedSector={selectedSector}
            selectedBatch={selectedBatch}
            batches={batches}
          />
        )}

        {tab === "mine" && (
          <MarketingMineView leads={leads} loading={loading} />
        )}

        {tab === "organizations" && (
          <div className="max-w-3xl mx-auto bg-white rounded-2xl ring-1 ring-zinc-200 overflow-hidden">
            <MarketingOrganizations />
          </div>
        )}
      </main>

      {/* ---- Bottom Tab Bar ---- */}
      <nav
        className="fixed bottom-0 inset-x-0 z-30 bg-white/95 backdrop-blur-lg border-t border-zinc-100 px-2"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 6px)" }}
      >
        <div className="max-w-md mx-auto grid grid-cols-3 gap-1 py-2">
          {TABS.map(({ key, label, icon: Icon }) => {
            const isActive = tab === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setTab(key);
                  setSelectedSector("");
                  setSelectedBatch("");
                }}
                className={`flex flex-col items-center gap-0.5 py-2 rounded-xl transition-colors ${
                  isActive ? "text-indigo-600 bg-indigo-50" : "text-zinc-500 hover:bg-zinc-50"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? "stroke-[2.5]" : ""}`} />
                <span className={`text-[10px] font-semibold ${isActive ? "" : ""}`}>{label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* ---- Call Session Overlay (full-screen when active) ---- */}
      {activeLead && (
        <div
          className="fixed inset-0 z-50 bg-zinc-50 overflow-y-auto"
          style={{
            paddingTop: "calc(env(safe-area-inset-top, 0px) + 12px)",
            paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 16px)",
          }}
        >
          <div className="px-4 pb-6">
            <MarketingCallSession
              lead={activeLead}
              timeLeft={timeLeft}
              callStatus={callStatus}
              note={note}
              saving={saving}
              onStatusChange={setCallStatus}
              onNoteChange={setNote}
              onSave={saveLead}
              onRelease={releaseLead}
            />
          </div>
        </div>
      )}

      {/* ---- Filter Drawer (bottom sheet) ---- */}
      {showFilters && (
        <FilterDrawer
          batches={batches}
          sectors={sectors}
          selectedBatch={selectedBatch}
          selectedSector={selectedSector}
          onBatchChange={setSelectedBatch}
          onSectorChange={setSelectedSector}
          onClose={() => setShowFilters(false)}
          onClear={() => {
            setSelectedBatch("");
            setSelectedSector("");
          }}
        />
      )}
    </div>
  );
}

// =================================================================
// Local components — keep small UI bits next to the orchestrator.
// =================================================================

/** Compact stat pill shown in the header strip. */
function StatPill({ icon: Icon, label, value, accent = "indigo" }) {
  const accents = {
    indigo:  "bg-indigo-50 text-indigo-700",
    zinc:    "bg-zinc-100 text-zinc-700",
    emerald: "bg-emerald-50 text-emerald-700",
    violet:  "bg-violet-50 text-violet-700",
  };
  return (
    <div className="bg-white rounded-2xl ring-1 ring-zinc-200 px-2 py-2 flex flex-col items-center text-center">
      <div className={`w-6 h-6 rounded-lg flex items-center justify-center mb-1 ${accents[accent] || accents.indigo}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <p className="text-base font-bold text-zinc-900 leading-none">{value}</p>
      <p className="text-[9px] text-zinc-400 uppercase tracking-wider mt-1">{label}</p>
    </div>
  );
}

/** Bottom-sheet filter drawer (Kampanya + Sektör). */
function FilterDrawer({
  batches,
  sectors,
  selectedBatch,
  selectedSector,
  onBatchChange,
  onSectorChange,
  onClose,
  onClear,
}) {
  const closeRef = useRef(null);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === closeRef.current) onClose(); }}
      ref={closeRef}
    >
      <div
        className="bg-white rounded-t-3xl shadow-2xl px-5 pt-4 pb-6"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 24px)" }}
      >
        <div className="w-10 h-1 rounded-full bg-zinc-300 mx-auto mb-4" />
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold text-zinc-900">Filtrele</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-100"
            aria-label="Kapat"
          >
            <X className="w-4 h-4 text-zinc-500" />
          </button>
        </div>

        {batches.length > 0 && (
          <div className="mb-4">
            <label className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1.5 block">
              Kampanya
            </label>
            <select
              value={selectedBatch}
              onChange={(e) => onBatchChange(e.target.value)}
              className="w-full border-2 border-zinc-200 rounded-xl px-3 py-2.5 text-sm focus:border-indigo-400 outline-none bg-white"
            >
              <option value="">Tüm kampanyalar</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>{b.batch_name}</option>
              ))}
            </select>
          </div>
        )}

        {sectors.length > 0 && (
          <div className="mb-4">
            <label className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-1.5 block">
              Sektör
            </label>
            <select
              value={selectedSector}
              onChange={(e) => onSectorChange(e.target.value)}
              className="w-full border-2 border-zinc-200 rounded-xl px-3 py-2.5 text-sm focus:border-indigo-400 outline-none bg-white"
            >
              <option value="">Tüm sektörler</option>
              {sectors.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex gap-2 mt-2">
          <button
            type="button"
            onClick={onClear}
            className="flex-1 py-2.5 rounded-xl bg-zinc-100 text-zinc-700 font-semibold text-sm hover:bg-zinc-200 transition-colors"
          >
            Temizle
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl bg-indigo-600 text-white font-semibold text-sm hover:bg-indigo-700 transition-colors"
          >
            Uygula
          </button>
        </div>
      </div>
    </div>
  );
}
