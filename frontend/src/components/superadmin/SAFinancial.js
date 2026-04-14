import { useState, useEffect, useCallback } from "react";
import api from "../../api/api";
import { toast } from "sonner";
import {
  Wallet, CheckCircle, AlertCircle, Eye, Lock, Unlock,
  RefreshCw, ChevronLeft, ChevronRight, Search, TrendingUp,
  DollarSign, Users, Shield, Trash2
} from "lucide-react";

const formatMoney = (minor, currency = "GBP") => {
  const amount = (minor || 0) / 100;
  const symbol = currency === "GBP" ? "£" : "₺";
  return `${symbol}${amount.toLocaleString("en-GB", { minimumFractionDigits: 2 })}`;
};

export default function SAFinancial() {
  const [overview, setOverview] = useState(null);
  const [wallets, setWallets] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [market, setMarket] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [searchTerm, setSearchTerm] = useState("");
  const [tab, setTab] = useState("wallets");

  const loadOverview = useCallback(async () => {
    try {
      const res = await api.get("/superadmin/financial/overview");
      setOverview(res.data);
    } catch (err) {
      console.error("Overview load error:", err);
    }
  }, []);

  const loadWallets = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: perPage };
      if (market) params.market = market;
      const res = await api.get("/superadmin/financial/wallets", { params });
      setWallets(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error("Wallets load error:", err);
      toast.error("Cüzdan listesi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [page, perPage, market]);

  useEffect(() => { loadOverview(); }, [loadOverview]);
  useEffect(() => { loadWallets(); }, [loadWallets]);

  const handleKycApprove = async (orgId) => {
    setActionLoading((prev) => ({ ...prev, [`kyc_${orgId}`]: true }));
    try {
      await api.post(`/superadmin/financial/kyc/${orgId}/verify`);
      toast.success("KYC onaylandı");
      await loadWallets();
    } catch (err) {
      toast.error(err.response?.data?.detail || "KYC onay hatası");
    } finally {
      setActionLoading((prev) => ({ ...prev, [`kyc_${orgId}`]: false }));
    }
  };

  const handleDeleteWallet = async (orgId) => {
    if (!window.confirm("Bu yetim cüzdanı silmek istediğinize emin misiniz? Bu işlem geri alınamaz.")) return;
    setActionLoading((prev) => ({ ...prev, [`del_${orgId}`]: true }));
    try {
      await api.delete(`/superadmin/financial/wallet/${orgId}`);
      toast.success("Cüzdan silindi");
      await loadWallets();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Silme hatası");
    } finally {
      setActionLoading((prev) => ({ ...prev, [`del_${orgId}`]: false }));
    }
  };

  const handleFreeze = async (orgId) => {
    if (!window.confirm("Bu cüzdanı dondurmak istediğinize emin misiniz?")) return;
    setActionLoading((prev) => ({ ...prev, [`freeze_${orgId}`]: true }));
    try {
      await api.post(`/superadmin/financial/wallet/${orgId}/freeze`);
      toast.success("Cüzdan donduruldu");
      await loadWallets();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Dondurma hatası");
    } finally {
      setActionLoading((prev) => ({ ...prev, [`freeze_${orgId}`]: false }));
    }
  };

  const totalPages = Math.ceil(total / perPage);

  const filteredWallets = searchTerm
    ? wallets.filter((w) =>
        (w.organization_id || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
        (w.org_name || "").toLowerCase().includes(searchTerm.toLowerCase())
      )
    : wallets;

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Wallet className="h-6 w-6" /> Finansal Yönetim
        </h1>
        <button
          onClick={() => { loadOverview(); loadWallets(); }}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          title="Yenile"
        >
          <RefreshCw className="h-5 w-5 text-gray-600" />
        </button>
      </div>

      {/* Overview Cards */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <DollarSign className="h-3.5 w-3.5" /> Toplam Havuz (GBP)
            </div>
            <p className="text-lg font-bold text-gray-900">{overview.total_pool_gbp_display}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <DollarSign className="h-3.5 w-3.5" /> Toplam Havuz (TRY)
            </div>
            <p className="text-lg font-bold text-gray-900">{overview.total_pool_try_display}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <Users className="h-3.5 w-3.5" /> GBP İşletmeler
            </div>
            <p className="text-lg font-bold text-gray-900">{overview.gbp_merchant_count}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <Users className="h-3.5 w-3.5" /> TRY İşletmeler
            </div>
            <p className="text-lg font-bold text-gray-900">{overview.try_merchant_count}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <TrendingUp className="h-3.5 w-3.5" /> GBP/TRY Kur
            </div>
            <p className="text-lg font-bold text-gray-900">{overview.current_rate_display || overview.current_gbp_try_rate_display || "N/A"}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {[
          { id: "wallets", label: "Cüzdanlar" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? "border-zinc-900 text-zinc-900"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Org ID veya isim ara..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
          />
        </div>
        <select
          value={market}
          onChange={(e) => { setMarket(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
        >
          <option value="">Tüm Pazarlar</option>
          <option value="GBP">GBP</option>
          <option value="TRY">TRY</option>
        </select>
      </div>

      {/* Wallets Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : filteredWallets.length === 0 ? (
        <div className="text-center text-gray-500 py-12">Cüzdan bulunamadı</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase">İşletme</th>
                <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase">Para Birimi</th>
                <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase">Kullanılabilir</th>
                <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase">Bekleyen</th>
                <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase">Dondurulan</th>
                <th className="text-center py-3 px-3 text-xs font-medium text-gray-500 uppercase">KYC</th>
                <th className="text-center py-3 px-3 text-xs font-medium text-gray-500 uppercase">İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {filteredWallets.map((w) => {
                const bc = w.base_currency || "GBP";
                const kycVerified = w.kyc_verified;
                return (
                  <tr key={w.organization_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-3">
                      <div className="text-sm font-medium text-gray-900">{w.org_name || <span className="text-gray-400 italic">Silinmiş İşletme</span>}</div>
                      {w.admin_name && (
                        <div className="text-[11px] text-gray-500">Admin: {w.admin_name}</div>
                      )}
                      {w.account_holder_name && (
                        <div className="text-[11px] text-indigo-600">IBAN Sahibi: {w.account_holder_name}</div>
                      )}
                      {w.iban && (
                        <div
                          className="text-[11px] font-mono text-gray-500 cursor-pointer hover:text-indigo-600 transition-colors"
                          title="Kopyalamak için tıkla"
                          onClick={() => { navigator.clipboard.writeText(w.iban); toast.success("IBAN kopyalandı"); }}
                        >
                          IBAN: {w.iban}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        bc === "GBP" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"
                      }`}>
                        {bc}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-medium text-gray-900">
                      {formatMoney(w.available_balance_minor, bc)}
                    </td>
                    <td className="py-3 px-3 text-right text-gray-600">
                      {formatMoney(w.pending_balance_minor, bc)}
                    </td>
                    <td className="py-3 px-3 text-right text-gray-600">
                      {formatMoney(w.frozen_balance_minor, bc)}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {kycVerified ? (
                        <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                          <CheckCircle className="h-3.5 w-3.5" /> Onaylı
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-600 text-xs">
                          <AlertCircle className="h-3.5 w-3.5" /> Bekliyor
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {!kycVerified && (
                          <button
                            onClick={() => handleKycApprove(w.organization_id)}
                            disabled={actionLoading[`kyc_${w.organization_id}`]}
                            className="p-1.5 rounded-lg text-green-600 hover:bg-green-50 transition-colors disabled:opacity-50"
                            title="KYC Onayla"
                          >
                            {actionLoading[`kyc_${w.organization_id}`] ? (
                              <div className="animate-spin h-4 w-4 border-2 border-green-600 border-t-transparent rounded-full" />
                            ) : (
                              <Shield className="h-4 w-4" />
                            )}
                          </button>
                        )}
                        <button
                          onClick={() => handleFreeze(w.organization_id)}
                          disabled={actionLoading[`freeze_${w.organization_id}`]}
                          className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                          title="Cüzdanı Dondur"
                        >
                          {actionLoading[`freeze_${w.organization_id}`] ? (
                            <div className="animate-spin h-4 w-4 border-2 border-red-600 border-t-transparent rounded-full" />
                          ) : (
                            <Lock className="h-4 w-4" />
                          )}
                        </button>
                        {!w.org_name && (w.available_balance_minor || 0) === 0 && (w.pending_balance_minor || 0) === 0 && (
                          <button
                            onClick={() => handleDeleteWallet(w.organization_id)}
                            disabled={actionLoading[`del_${w.organization_id}`]}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                            title="Yetim Cüzdanı Sil"
                          >
                            {actionLoading[`del_${w.organization_id}`] ? (
                              <div className="animate-spin h-4 w-4 border-2 border-red-600 border-t-transparent rounded-full" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-gray-500">
            Toplam {total} cüzdan • Sayfa {page}/{totalPages}
          </p>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
