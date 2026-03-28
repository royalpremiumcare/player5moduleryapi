import { useState, useEffect } from "react";
import { X, UserX, Package, CreditCard, MessageCircle, Phone, AlertTriangle, CheckCheck, Send, Eye, Trash2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

const TABS = ["Özet", "Personeller", "Paket & Ödeme", "WhatsApp"];

const statusBadge = (status) => ({
  active:   "bg-green-100 text-green-700",
  trial:    "bg-blue-100 text-blue-700",
  expired:  "bg-red-100 text-red-700",
  cancelled:"bg-gray-100 text-gray-600",
}[status] || "bg-gray-100 text-gray-600");

export default function OrgDrawer({ org, plans, onClose, onRefresh }) {
  const [tab, setTab] = useState(0);
  const [staff, setStaff] = useState([]);
  const [loadingStaff, setLoadingStaff] = useState(false);
  const [waLogs, setWaLogs] = useState([]);
  const [loadingWa, setLoadingWa] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(org?.plan_id || "");
  const [selectedCycle, setSelectedCycle] = useState(org?.billing_cycle || "monthly");
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!org) return;
    setSelectedPlan(org.plan_id || "");
    setSelectedCycle(org.billing_cycle || "monthly");
    loadStaff();
  }, [org?.organization_id]);

  useEffect(() => {
    if (tab === 3) loadWaLogs();
  }, [tab]);

  const loadStaff = async () => {
    setLoadingStaff(true);
    try {
      const res = await api.get(`/superadmin/organizations/${org.organization_id}/staff`);
      setStaff(res.data.staff || []);
    } catch { toast.error("Personeller yüklenemedi"); }
    finally { setLoadingStaff(false); }
  };

  const loadWaLogs = async () => {
    setLoadingWa(true);
    try {
      const phone = org.telefon_numarasi?.replace(/\D/g, "");
      const res = await api.get(`/superadmin/whatsapp-logs?limit=100`);
      const all = res.data.logs || [];
      setWaLogs(phone ? all.filter(l => l.recipient?.includes(phone.slice(-9))) : all.slice(0, 50));
    } catch { toast.error("WA logları yüklenemedi"); }
    finally { setLoadingWa(false); }
  };

  const deleteStaff = async (staffId, name) => {
    if (!window.confirm(`"${name}" personelini silmek istiyor musunuz?`)) return;
    try {
      await api.delete(`/superadmin/organizations/${org.organization_id}/staff/${staffId}`);
      toast.success("Personel silindi");
      loadStaff();
      onRefresh?.();
    } catch { toast.error("Silinemedi"); }
  };

  const deleteOrg = async () => {
    if (!window.confirm(`"${org.isletme_adi}" işletmesini ve TÜM VERİLERİNİ silmek istiyor musunuz?\n\nBu işlem GERİ ALINAMAZ!`)) return;
    try {
      await api.delete(`/superadmin/organizations/${org.organization_id}`);
      toast.success("İşletme silindi");
      onClose();
      onRefresh?.();
    } catch { toast.error("İşletme silinemedi"); }
  };

  const assignPlan = async () => {
    if (!selectedPlan) return;
    setAssigning(true);
    try {
      await api.post(`/superadmin/organizations/${org.organization_id}/assign-plan`, {
        plan_id: selectedPlan,
        billing_cycle: selectedCycle,
      });
      toast.success("Paket atandı");
      onRefresh?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Paket atanamadı"); }
    finally { setAssigning(false); }
  };

  const waBadge = (s) => ({
    read:      "bg-purple-100 text-purple-700",
    delivered: "bg-green-100 text-green-700",
    sent:      "bg-indigo-100 text-indigo-700",
    failed:    "bg-red-100 text-red-700",
  }[s] || "bg-gray-100 text-gray-600");

  const waIcon = (s) => ({
    read:      <Eye className="w-3 h-3" />,
    delivered: <CheckCheck className="w-3 h-3" />,
    sent:      <Send className="w-3 h-3" />,
    failed:    <AlertTriangle className="w-3 h-3" />,
  }[s] || null);

  const waLabel = (s) => ({ read:"Okundu", delivered:"İletildi", sent:"Gönderildi", failed:"Başarısız" }[s] || s);

  if (!org) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-white z-50 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{org.isletme_adi}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{org.admin_full_name} · {org.admin_email}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(org.abonelik_durumu_key || "")}`}>
                {org.abonelik_durumu}
              </span>
              <span className="text-xs text-gray-400">{org.abonelik_paketi}</span>
              {org.billing_cycle === "yearly" && (
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full font-medium">Yıllık</span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 px-5">
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === i
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* ÖZET */}
          {tab === 0 && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Bu Ay Randevu", value: org.bu_ayki_randevu_sayisi },
                  { label: "Toplam Personel", value: org.toplam_personel_sayisi },
                  { label: "Toplam Ödeme", value: `${(org.toplam_odeme || 0).toLocaleString("tr-TR")} ₺` },
                  { label: "Kalan Gün", value: org.days_left !== null ? `${org.days_left} gün` : "—" },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="text-lg font-bold text-gray-900 mt-0.5">{value}</p>
                  </div>
                ))}
              </div>
              <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex gap-2">
                  <Phone className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                  <a href={`tel:${org.telefon_numarasi}`} className="text-indigo-600 hover:underline">{org.telefon_numarasi}</a>
                </div>
              </div>
              <button
                onClick={deleteOrg}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-red-50 text-red-600 rounded-xl text-sm font-medium hover:bg-red-100 transition-colors border border-red-100"
              >
                <Trash2 className="w-4 h-4" />
                İşletmeyi Sil
              </button>
            </div>
          )}

          {/* PERSONELLER */}
          {tab === 1 && (
            <div className="space-y-3">
              {loadingStaff ? (
                <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>
              ) : staff.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">Personel bulunamadı</p>
              ) : (
                staff.map((s) => (
                  <div key={s.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{s.full_name}</p>
                      <p className="text-xs text-gray-500">{s.username} · {s.role}</p>
                    </div>
                    <button
                      onClick={() => deleteStaff(s.id, s.full_name)}
                      className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <UserX className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* PAKET & ÖDEME */}
          {tab === 2 && (
            <div className="space-y-5">
              <div className="bg-gray-50 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <Package className="w-4 h-4" />
                  Mevcut Paket: <span className="text-indigo-600">{org.abonelik_paketi}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <CreditCard className="w-4 h-4" />
                  Toplam Ödeme: <strong className="text-gray-900">{(org.toplam_odeme || 0).toLocaleString("tr-TR")} ₺</strong>
                </div>
              </div>

              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700">Paket Değiştir</label>
                <select
                  value={selectedPlan}
                  onChange={(e) => setSelectedPlan(e.target.value)}
                  className="w-full p-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  <option value="">Seçin...</option>
                  {(plans || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name} — {p.price_monthly}₺/ay</option>
                  ))}
                </select>
                {selectedPlan && selectedPlan !== "tier_trial" && (
                  <div className="flex gap-2">
                    {["monthly", "yearly"].map((c) => (
                      <button
                        key={c}
                        onClick={() => setSelectedCycle(c)}
                        className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors ${
                          selectedCycle === c
                            ? c === "monthly" ? "bg-indigo-600 text-white" : "bg-emerald-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {c === "monthly" ? "Aylık" : "Yıllık"}
                      </button>
                    ))}
                  </div>
                )}
                <button
                  onClick={assignPlan}
                  disabled={!selectedPlan || assigning}
                  className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50"
                >
                  {assigning ? "Atanıyor..." : "Paketi Ata"}
                </button>
              </div>
            </div>
          )}

          {/* WHATSAPP */}
          {tab === 3 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">{waLogs.length} log</p>
                <button onClick={loadWaLogs} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                  <RefreshCw className={`w-4 h-4 text-gray-500 ${loadingWa ? "animate-spin" : ""}`} />
                </button>
              </div>
              {loadingWa ? (
                <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>
              ) : waLogs.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">Bu işletmeye ait WA logu bulunamadı</p>
              ) : (
                waLogs.map((log, idx) => (
                  <div key={`${log.message_id}-${idx}`} className={`p-3 rounded-xl border ${log.status === "failed" ? "bg-red-50 border-red-100" : "bg-gray-50 border-gray-100"}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${waBadge(log.status)}`}>
                        {waIcon(log.status)}
                        {waLabel(log.status)}
                      </span>
                      <span className="text-xs text-gray-600 font-mono">+{log.recipient}</span>
                      <span className="text-xs text-gray-400 ml-auto">
                        {log.recorded_at ? new Date(log.recorded_at).toLocaleString("tr-TR") : "—"}
                      </span>
                    </div>
                    {log.errors?.length > 0 && (
                      <div className="mt-1.5 text-xs text-red-600">
                        {log.errors.map((e, i) => <p key={i}>{e.code}: {e.title || e.message}</p>)}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
