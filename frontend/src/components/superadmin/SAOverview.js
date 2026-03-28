import { useState, useEffect } from "react";
import { TrendingUp, Building2, DollarSign, TrendingDown, Calendar, MessageCircle, UserPlus, RefreshCw } from "lucide-react";
import api from "../../api/api";

const StatCard = ({ label, value, sub, icon: Icon, color, loading }) => (
  <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-1">
          {loading ? <span className="animate-pulse text-gray-300">—</span> : value}
        </p>
        {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      </div>
      <div className={`p-2.5 rounded-xl ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
    </div>
  </div>
);

export default function SAOverview() {
  const [financial, setFinancial] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [finRes, statsRes] = await Promise.all([
        api.get("/superadmin/financial-stats"),
        api.get("/superadmin/stats"),
      ]);
      setFinancial(finRes.data);
      setStats(statsRes.data);
    } catch (e) {
      console.error("Overview load error", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const fmt = (n) => (n || 0).toLocaleString("tr-TR");

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Platform Özeti</h2>
          <p className="text-sm text-gray-500 mt-0.5">Gerçek zamanlı SaaS metrikleri</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Yenile
        </button>
      </div>

      {/* Primary KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="MRR"
          value={`${fmt(financial?.mrr)} ₺`}
          sub="Aylık Tekrarlayan Gelir"
          icon={TrendingUp}
          color="bg-indigo-500"
          loading={loading}
        />
        <StatCard
          label="Toplam Ciro"
          value={`${fmt(financial?.total_revenue)} ₺`}
          sub="Tüm zamanlar"
          icon={DollarSign}
          color="bg-emerald-500"
          loading={loading}
        />
        <StatCard
          label="Aktif İşletme"
          value={fmt(financial?.active_businesses)}
          sub={`Toplam: ${fmt(stats?.toplam_isletme)}`}
          icon={Building2}
          color="bg-blue-500"
          loading={loading}
        />
        <StatCard
          label="Churn (30 gün)"
          value={fmt(financial?.churn_last_30d)}
          sub="İptal / Süresi dolan"
          icon={TrendingDown}
          color="bg-red-500"
          loading={loading}
        />
      </div>

      {/* Secondary KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          label="Bu Ay Yeni Kayıt"
          value={fmt(financial?.new_registrations_this_month)}
          sub="Yeni işletme kayıtları"
          icon={UserPlus}
          color="bg-violet-500"
          loading={loading}
        />
        <StatCard
          label="Bu Ay Randevu"
          value={fmt(financial?.total_appointments_this_month)}
          sub="Platform geneli"
          icon={Calendar}
          color="bg-amber-500"
          loading={loading}
        />
        <StatCard
          label="WA Başarı Oranı"
          value={`${financial?.wa_success_rate ?? "—"}%`}
          sub="Son 7 gün (iletilen+okunan)"
          icon={MessageCircle}
          color="bg-green-500"
          loading={loading}
        />
      </div>

      {/* Info box */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
        <p className="text-sm text-indigo-700 font-medium">Toplam Kullanıcı</p>
        <p className="text-2xl font-bold text-indigo-900 mt-1">
          {loading ? "—" : fmt(stats?.toplam_aktif_kullanici)}
        </p>
        <p className="text-xs text-indigo-500 mt-1">Admin + Personel hesapları</p>
      </div>
    </div>
  );
}
