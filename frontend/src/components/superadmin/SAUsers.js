import { useState, useEffect } from "react";
import { Plus, Trash2, RefreshCw, User } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

export default function SAUsers() {
  const [users, setUsers]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm]       = useState({ username: "", password: "", full_name: "" });
  const [saving, setSaving]   = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/superadmin/users/marketing");
      setUsers(res.data.users || []);
    } catch { toast.error("Kullanıcılar yüklenemedi"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.username || !form.password) { toast.error("Kullanıcı adı ve şifre zorunlu"); return; }
    setSaving(true);
    try {
      await api.post("/superadmin/users/marketing", form);
      toast.success("Marketing kullanıcısı oluşturuldu");
      setForm({ username: "", password: "", full_name: "" });
      setShowForm(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Oluşturulamadı"); }
    finally { setSaving(false); }
  };

  const deleteUser = async (id, name) => {
    if (!window.confirm(`"${name}" kullanıcısını silmek istiyor musunuz?`)) return;
    try {
      await api.delete(`/superadmin/users/marketing/${id}`);
      toast.success("Kullanıcı silindi");
      setUsers(prev => prev.filter(u => u.id !== id));
    } catch { toast.error("Silinemedi"); }
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Marketing Kullanıcıları</h2>
          <p className="text-sm text-gray-500 mt-0.5">Tele-satış CRM erişimi olan kullanıcılar</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Yeni Kullanıcı
          </button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-indigo-100 p-5 space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">Yeni Marketing Kullanıcısı</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Ad Soyad</label>
              <input
                value={form.full_name}
                onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                placeholder="Ad Soyad"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Kullanıcı Adı *</label>
              <input
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder="kullanici_adi"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Şifre *</label>
              <input
                type="password"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="Şifre"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={create}
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {saving ? "Oluşturuluyor..." : "Oluştur"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
            >
              İptal
            </button>
          </div>
        </div>
      )}

      {/* Users list */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Yükleniyor...</div>
        ) : users.length === 0 ? (
          <div className="p-10 text-center">
            <User className="w-10 h-10 text-gray-200 mx-auto mb-3" />
            <p className="text-sm text-gray-400">Henüz marketing kullanıcısı yok</p>
            <p className="text-xs text-gray-300 mt-1">Yukarıdan yeni kullanıcı oluşturun</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Ad Soyad</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Kullanıcı Adı</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Durum</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Oluşturma</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-50/60">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.full_name || "—"}</td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{u.username}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      u.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                    }`}>
                      {u.status === "active" ? "Aktif" : u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString("tr-TR") : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => deleteUser(u.id, u.full_name || u.username)}
                      className="p-1.5 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
