import { useState, useEffect, useMemo } from "react";
import { Search, ArrowUpDown, ArrowUp, ArrowDown, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";

const statusStyle = (days, status) => {
  if (status === "Aktif") {
    if (days !== null && days <= 3) return "bg-red-100 text-red-700";
    if (days !== null && days <= 7) return "bg-yellow-100 text-yellow-700";
    return "bg-green-100 text-green-700";
  }
  if (status === "Trial") return "bg-blue-100 text-blue-700";
  return "bg-gray-100 text-gray-600";
};

const planBadge = (plan) => {
  if (!plan) return "bg-gray-100 text-gray-600";
  if (plan.toLowerCase().includes("premium")) return "bg-purple-100 text-purple-700";
  if (plan.toLowerCase().includes("business")) return "bg-indigo-100 text-indigo-700";
  if (plan.toLowerCase().includes("starter")) return "bg-green-100 text-green-700";
  return "bg-gray-100 text-gray-600";
};

export default function MarketingOrganizations() {
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: "asc" });

  const load = async () => {
    setLoading(true);
    try {
      const orgsRes = await api.get("/marketing/organizations");
      setOrgs(orgsRes.data.organizations || []);
    } catch (e) {
      toast.error("İşletmeler yüklenemedi");
      console.error("orgs error", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  const filteredOrgs = useMemo(() => {
    let filtered = orgs.filter((org) =>
      org.isletme_adi?.toLowerCase().includes(search.toLowerCase()) ||
      org.admin_email?.toLowerCase().includes(search.toLowerCase()) ||
      org.admin_full_name?.toLowerCase().includes(search.toLowerCase())
    );

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        const aVal = a[sortConfig.key] || "";
        const bVal = b[sortConfig.key] || "";
        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [orgs, search, sortConfig]);

  const SortIcon = ({ columnKey }) => {
    if (sortConfig.key !== columnKey) return <ArrowUpDown className="w-4 h-4 text-gray-400" />;
    return sortConfig.direction === "asc" ? <ArrowUp className="w-4 h-4 text-blue-600" /> : <ArrowDown className="w-4 h-4 text-blue-600" />;
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-2" />
        <p className="text-gray-500">Yükleniyor...</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="İşletme ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 pr-4 py-2 w-full border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <button onClick={load} className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {filteredOrgs.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">Henüz işletme bulunamadı</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th
                  onClick={() => handleSort("isletme_adi")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    İşletme Adı
                    <SortIcon columnKey="isletme_adi" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("admin_full_name")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    Yetkili
                    <SortIcon columnKey="admin_full_name" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("admin_email")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    E-posta
                    <SortIcon columnKey="admin_email" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("telefon_numarasi")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    Telefon
                    <SortIcon columnKey="telefon_numarasi" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("abonelik_paketi")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    Paket
                    <SortIcon columnKey="abonelik_paketi" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("abonelik_durumu")}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    Durum
                    <SortIcon columnKey="abonelik_durumu" />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredOrgs.map((org) => (
                <tr key={org.organization_id} className="hover:bg-gray-50">
                  <td className="px-4 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{org.isletme_adi}</div>
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{org.admin_full_name}</div>
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-500">{org.admin_email}</div>
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{org.telefon_numarasi}</div>
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${planBadge(org.abonelik_paketi)}`}>
                      {org.abonelik_paketi}
                    </span>
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${statusStyle(org.days_left, org.abonelik_durumu)}`}>
                      {org.abonelik_durumu}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
