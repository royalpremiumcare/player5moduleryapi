import { useState, useEffect, useMemo } from "react";
import { Search, ArrowUpDown, ArrowUp, ArrowDown, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";
import OrgDrawer from "./OrgDrawer";

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
  if (plan.toLowerCase().includes("trial")) return "bg-blue-100 text-blue-700";
  return "bg-gray-100 text-gray-600";
};

export default function SAOrganizations() {
  const [orgs, setOrgs] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: "isletme_adi", dir: "asc" });
  const [selectedOrg, setSelectedOrg] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [orgsRes, plansRes] = await Promise.all([
        api.get("/superadmin/organizations"),
        api.get("/superadmin/plans"),
      ]);
      setOrgs(orgsRes.data.organizations || []);
      setPlans(plansRes.data.plans || []);
    } catch { toast.error("İşletmeler yüklenemedi"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const toggleSort = (key) => {
    setSort(prev => ({ key, dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc" }));
  };

  const SortIcon = ({ k }) => {
    if (sort.key !== k) return <ArrowUpDown className="w-3 h-3 text-gray-400" />;
    return sort.dir === "asc" ? <ArrowUp className="w-3 h-3 text-indigo-600" /> : <ArrowDown className="w-3 h-3 text-indigo-600" />;
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let list = orgs.filter(o =>
      o.isletme_adi?.toLowerCase().includes(q) ||
      o.admin_full_name?.toLowerCase().includes(q) ||
      o.admin_email?.toLowerCase().includes(q) ||
      o.telefon_numarasi?.includes(q)
    );
    list = [...list].sort((a, b) => {
      let av = a[sort.key], bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number")
        return sort.dir === "asc" ? av - bv : bv - av;
      av = String(av || "").toLowerCase();
      bv = String(bv || "").toLowerCase();
      return sort.dir === "asc" ? av.localeCompare(bv, "tr") : bv.localeCompare(av, "tr");
    });
    return list;
  }, [orgs, search, sort]);

  const cols = [
    { key: "isletme_adi",           label: "İşletme" },
    { key: "abonelik_paketi",       label: "Paket" },
    { key: "days_left",             label: "Kalan Gün" },
    { key: "bu_ayki_randevu_sayisi",label: "Bu Ay Randevu" },
    { key: "toplam_odeme",          label: "Toplam Ödeme" },
    { key: "abonelik_durumu",       label: "Durum" },
  ];

  return (
    <div className="p-6">
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="İşletme, admin, e-posta..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          />
        </div>
        <span className="text-sm text-gray-500">{filtered.length} işletme</span>
        <button onClick={load} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                {cols.map(({ key, label }) => (
                  <th
                    key={key}
                    onClick={() => toggleSort(key)}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide cursor-pointer hover:bg-gray-100 transition-colors whitespace-nowrap"
                  >
                    <span className="flex items-center gap-1">
                      {label} <SortIcon k={key} />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {cols.map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-gray-100 rounded w-24" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={cols.length} className="px-4 py-10 text-center text-sm text-gray-400">
                    {search ? "Arama sonucu bulunamadı" : "Henüz işletme yok"}
                  </td>
                </tr>
              ) : (
                filtered.map((org) => (
                  <tr
                    key={org.organization_id}
                    onClick={() => setSelectedOrg(org)}
                    className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900">{org.isletme_adi}</p>
                        <p className="text-xs text-gray-400">{org.admin_full_name}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${planBadge(org.abonelik_paketi)}`}>
                        {org.abonelik_paketi}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-medium ${
                        org.days_left !== null && org.days_left <= 3 ? "text-red-600" :
                        org.days_left !== null && org.days_left <= 7 ? "text-yellow-600" : "text-gray-700"
                      }`}>
                        {org.days_left !== null ? `${org.days_left} gün` : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{org.bu_ayki_randevu_sayisi}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {(org.toplam_odeme || 0).toLocaleString("tr-TR")} ₺
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusStyle(org.days_left, org.abonelik_durumu)}`}>
                        {org.abonelik_durumu}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Org Drawer */}
      {selectedOrg && (
        <OrgDrawer
          org={selectedOrg}
          plans={plans}
          onClose={() => setSelectedOrg(null)}
          onRefresh={() => { load(); setSelectedOrg(null); }}
        />
      )}
    </div>
  );
}
