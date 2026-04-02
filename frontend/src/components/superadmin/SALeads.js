import { useState, useEffect, useRef } from "react";
import { Upload, Trash2, RefreshCw, BarChart2, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

const STATUS_LABELS = {
  pool:           { label: "Havuzda",    cls: "bg-gray-100 text-gray-600" },
  claimed:        { label: "Alındı",     cls: "bg-yellow-100 text-yellow-700" },
  interested:     { label: "İlgilendi",  cls: "bg-blue-100 text-blue-700" },
  unreachable:    { label: "Ulaşılamadı",cls: "bg-orange-100 text-orange-700" },
  not_interested: { label: "İlgisiz",    cls: "bg-red-100 text-red-700" },
  waiting:        { label: "Beklemede",  cls: "bg-purple-100 text-purple-700" },
  registered:     { label: "Kayıt Oldu", cls: "bg-green-100 text-green-700" },
};

export default function SALeads() {
  const [stats, setStats]         = useState(null);
  const [batches, setBatches]     = useState([]);
  const [leads, setLeads]         = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [batchFilter, setBatchFilter]   = useState("");
  const [page, setPage]               = useState(1);
  const PAGE_SIZE = 50;

  // Upload wizard
  const [uploadStep, setUploadStep]   = useState(0); // 0=idle, 1=mapping
  const [previewData, setPreviewData] = useState(null);
  const [fileObj, setFileObj]         = useState(null); // actual File object
  const [companyCol, setCompanyCol]   = useState("");
  const [phoneCol, setPhoneCol]       = useState("");
  const [sectorCol, setSectorCol]     = useState(""); // YENİ: Sektör sütunu için state eklendi
  const [batchName, setBatchName]     = useState("");
  const [uploading, setUploading]     = useState(false);
  const fileRef = useRef();

  const load = async (currentPage = page) => {
    setLoading(true);
    try {
      const skip = (currentPage - 1) * PAGE_SIZE;
      const params = new URLSearchParams({ limit: PAGE_SIZE, skip });
      if (statusFilter) params.set("status_filter", statusFilter);
      if (batchFilter) params.set("batch_id", batchFilter);
      const [statsRes, batchRes, leadsRes] = await Promise.all([
        api.get("/superadmin/leads/stats"),
        api.get("/superadmin/leads/batches"),
        api.get(`/superadmin/leads?${params.toString()}`),
      ]);
      setStats(statsRes.data);
      setBatches(batchRes.data.batches || []);
      setLeads(leadsRes.data.leads || []);
      setTotal(leadsRes.data.total || 0);
    } catch { toast.error("Veriler yüklenemedi"); }
    finally { setLoading(false); }
  };

  useEffect(() => { setPage(1); }, [statusFilter, batchFilter]);
  useEffect(() => { load(page); }, [page, statusFilter, batchFilter]);

  const handleFile = async (file) => {
    if (!file) return;
    setFileObj(file);
    setBatchName(file.name.replace(/\.[^.]+$/, ""));
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/superadmin/leads/upload/preview", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPreviewData(res.data);
      setUploadStep(1);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Dosya okunamadı");
    }
  };

  const confirmUpload = async () => {
    // YENİ: Sektör sütunu da kontrol ediliyor
    if (!companyCol || !phoneCol || !sectorCol || !batchName) {
      toast.error("Lütfen tüm alanları doldurun"); return;
    }
    if (!fileObj) { toast.error("Dosya bulunamadı, lütfen tekrar yükleyin"); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", fileObj);
      formData.append("batch_name", batchName);
      formData.append("company_col", companyCol);
      formData.append("phone_col", phoneCol);
      formData.append("sector_col", sectorCol); // YENİ: Backend'e sektör kolonunu da gönderiyoruz
      
      const res = await api.post("/superadmin/leads/upload/confirm", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(res.data.message);
      setUploadStep(0);
      setPreviewData(null);
      setFileObj(null);
      setCompanyCol("");
      setPhoneCol("");
      setSectorCol(""); // YENİ: Yükleme bitince state'i sıfırlıyoruz
      // Yeni yüklenen batch'i otomatik seç
      if (res.data.batch_id) setBatchFilter(res.data.batch_id);
      setPage(1);
      load(1);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Yükleme başarısız");
    } finally { setUploading(false); }
  };

  const deleteBatch = async (id, name) => {
    if (!window.confirm(`"${name}" yüklemesini ve tüm leadlerini silmek istiyor musunuz?`)) return;
    try {
      await api.delete(`/superadmin/leads/batch/${id}`);
      toast.success("Batch silindi");
      load();
    } catch { toast.error("Silinemedi"); }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Toplam",       value: stats.total,          cls: "bg-gray-50" },
            { label: "Havuzda",      value: stats.pool,           cls: "bg-gray-50" },
            { label: "İlgilendi",    value: stats.interested,     cls: "bg-blue-50 text-blue-700" },
            { label: "Beklemede",    value: stats.waiting,        cls: "bg-purple-50 text-purple-700" },
            { label: "Kayıt Oldu",   value: stats.registered,     cls: "bg-green-50 text-green-700" },
            { label: "Dönüşüm %",   value: `${stats.conversion_rate}%`, cls: "bg-indigo-50 text-indigo-700" },
          ].map(({ label, value, cls }) => (
            <div key={label} className={`rounded-xl p-3 border border-gray-100 ${cls}`}>
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-xl font-bold mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Upload Card */}
      {uploadStep === 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Lead Yükle (CSV / XLSX)</h3>
          <div
            className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-400 transition-colors"
            onClick={() => fileRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); }}
          >
            <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-600">Dosyayı sürükle veya <span className="text-indigo-600 font-medium">seç</span></p>
            <p className="text-xs text-gray-400 mt-1">CSV, XLSX desteklenir</p>
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={e => handleFile(e.target.files[0])} />
          </div>
        </div>
      )}

      {/* Upload Step 1 — Column mapping */}
      {uploadStep === 1 && previewData && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Sütun Eşleştir</h3>
            <button onClick={() => setUploadStep(0)} className="text-sm text-gray-400 hover:text-gray-600">İptal</button>
          </div>
          <p className="text-sm text-gray-500">
            <strong>{fileObj?.name}</strong> — {previewData.preview?.length} satır önizleme
          </p>

          {/* Preview table */}
          <div className="overflow-x-auto rounded-lg border border-gray-100">
            <table className="text-xs w-full">
              <thead>
                <tr className="bg-gray-50">
                  {previewData.columns?.map(col => (
                    <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.preview?.map((row, i) => (
                  <tr key={i} className="border-t border-gray-50">
                    {previewData.columns?.map(col => (
                      <td key={col} className="px-3 py-1.5 text-gray-700 whitespace-nowrap max-w-[120px] truncate">{row[col]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* YENİ: Grid yapısı 4 kolona çıkarıldı */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Batch Adı</label>
              <input
                value={batchName}
                onChange={e => setBatchName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                placeholder="Batch adı..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Şirket Adı Sütunu</label>
              <select
                value={companyCol}
                onChange={e => setCompanyCol(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="">Seçin...</option>
                {previewData.columns?.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Telefon Sütunu</label>
              <select
                value={phoneCol}
                onChange={e => setPhoneCol(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="">Seçin...</option>
                {previewData.columns?.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            {/* YENİ: Sektör Sütunu Seçimi Eklendi */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sektör Sütunu</label>
              <select
                value={sectorCol}
                onChange={e => setSectorCol(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="">Seçin...</option>
                {previewData.columns?.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <button
            onClick={confirmUpload}
            disabled={uploading || !companyCol || !phoneCol || !sectorCol || !batchName}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            {uploading ? "Yükleniyor..." : "Leadleri Yükle"}
          </button>
        </div>
      )}

      {/* Batches */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Yükleme Geçmişi</h3>
          <button onClick={load} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <RefreshCw className={`w-4 h-4 text-gray-400 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
        {batches.length === 0 ? (
          <p className="p-5 text-sm text-gray-400 text-center">Henüz yükleme yapılmadı</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {batches.map(b => (
              <div key={b.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{b.batch_name}</p>
                  <p className="text-xs text-gray-400">
                    {b.total} lead · {b.uploaded_by_name} · {new Date(b.created_at).toLocaleDateString("tr-TR")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setBatchFilter(batchFilter === b.id ? "" : b.id)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                      batchFilter === b.id ? "bg-indigo-100 text-indigo-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {batchFilter === b.id ? "Filtreyi Kaldır" : "Filtrele"}
                  </button>
                  <button
                    onClick={() => deleteBatch(b.id, b.batch_name)}
                    className="p-1.5 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lead table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-5 py-3 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Lead Havuzu</h3>
          <span className="text-sm text-gray-400">{total} kayıt</span>
          {batchFilter && (
            <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">
              {batches.find(b => b.id === batchFilter)?.batch_name || "Seçili Batch"}
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <select
              value={batchFilter}
              onChange={e => setBatchFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
            >
              <option value="">Tüm Kampanyalar</option>
              {batches.map(b => (
                <option key={b.id} value={b.id}>{b.batch_name} ({b.total})</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
            >
              <option value="">Tüm Durumlar</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Şirket</th>
                {/* YENİ: Sektör Başlığı */}
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Sektör</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Telefon</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Durum</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Pazarlamacı</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Not</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Batch</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded w-24" /></td>
                    ))}
                  </tr>
                ))
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">Lead bulunamadı</td>
                </tr>
              ) : (
                leads.map(l => {
                  const st = STATUS_LABELS[l.status] || { label: l.status, cls: "bg-gray-100 text-gray-600" };
                  return (
                    <tr key={l.id} className="hover:bg-gray-50/60">
                      <td className="px-4 py-3 font-medium text-gray-900">{l.company_name}</td>
                      {/* YENİ: Sektör Verisi */}
                      <td className="px-4 py-3 text-gray-600 text-xs">{l.sector || "—"}</td>
                      <td className="px-4 py-3 text-gray-600 font-mono text-xs">{l.phone}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.cls}`}>{st.label}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs">{l.claimed_by_name || "—"}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs max-w-[150px] truncate">{l.note || "—"}</td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{l.batch_name || "—"}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50/50">
            <span className="text-xs text-gray-500">
              {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} / {total} kayıt
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                ← Önceki
              </button>
              <span className="px-3 py-1.5 text-xs font-medium text-gray-700">
                {page} / {Math.ceil(total / PAGE_SIZE)}
              </span>
              <button
                onClick={() => setPage(p => Math.min(Math.ceil(total / PAGE_SIZE), p + 1))}
                disabled={page >= Math.ceil(total / PAGE_SIZE)}
                className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Sonraki →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}