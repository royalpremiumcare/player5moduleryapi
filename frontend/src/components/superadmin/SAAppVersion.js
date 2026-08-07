import { useState, useEffect, useCallback } from "react";
import { Smartphone, Save, RefreshCw, AlertTriangle, Apple, Play, ListChecks } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/api";

/**
 * Süper Admin — Uygulama Sürüm Yönetimi (Force-Update kontrol paneli).
 *
 * GET /api/app/config → mevcut eşikleri gösterir.
 * PUT /api/superadmin/app-config → deploy'suz günceller.
 *
 * Amaç: min_supported / latest sürümlerini "curl'de unutulan komut" olmaktan
 * çıkarıp panelde görünür, tek tıkla düzenlenebilir bir operasyon kontrolü yapmak.
 */
const emptyCfg = {
  min_supported_version: { ios: "", android: "" },
  latest_version: { ios: "", android: "" },
  store_urls: { ios: "", android: "" },
};

const SAAppVersion = () => {
  const [cfg, setCfg] = useState(emptyCfg);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/app/config");
      setCfg({
        min_supported_version: {
          ios: data?.min_supported_version?.ios || "",
          android: data?.min_supported_version?.android || "",
        },
        latest_version: {
          ios: data?.latest_version?.ios || "",
          android: data?.latest_version?.android || "",
        },
        store_urls: {
          ios: data?.store_urls?.ios || "",
          android: data?.store_urls?.android || "",
        },
      });
    } catch (err) {
      toast.error("Sürüm ayarları yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setField = (group, platform, value) => {
    setCfg((prev) => ({ ...prev, [group]: { ...prev[group], [platform]: value } }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/superadmin/app-config", cfg);
      setCfg({
        min_supported_version: { ...emptyCfg.min_supported_version, ...data?.min_supported_version },
        latest_version: { ...emptyCfg.latest_version, ...data?.latest_version },
        store_urls: { ...emptyCfg.store_urls, ...data?.store_urls },
      });
      toast.success("Sürüm ayarları kaydedildi");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  const PlatformCard = ({ platform, Icon, title }) => (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5 text-gray-700" />
        <h3 className="font-semibold text-gray-900">{title}</h3>
      </div>
      <div className="space-y-3">
        <label className="block">
          <span className="text-xs font-medium text-gray-500">Minimum desteklenen sürüm (zorunlu güncelleme eşiği)</span>
          <input
            value={cfg.min_supported_version[platform]}
            onChange={(e) => setField("min_supported_version", platform, e.target.value)}
            placeholder="0.0.0"
            className="mt-1 w-full h-11 px-3 rounded-lg border border-gray-300 text-base focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-500">En güncel sürüm (yumuşak uyarı eşiği)</span>
          <input
            value={cfg.latest_version[platform]}
            onChange={(e) => setField("latest_version", platform, e.target.value)}
            placeholder="6.1"
            className="mt-1 w-full h-11 px-3 rounded-lg border border-gray-300 text-base focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-500">Mağaza linki</span>
          <input
            value={cfg.store_urls[platform]}
            onChange={(e) => setField("store_urls", platform, e.target.value)}
            placeholder="https://..."
            className="mt-1 w-full h-11 px-3 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          />
        </label>
      </div>
    </div>
  );

  return (
    <div className="p-4 lg:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Smartphone className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-bold text-gray-900">Uygulama Sürüm Yönetimi</h2>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-50"
          title="Yenile"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Force-update eşikleri. Değişiklik <strong>anında</strong> geçerli olur (deploy gerekmez).
        Backend yalnız sinyal verir; kilidi uygulama gösterir.
      </p>

      {/* Kritik uyarı */}
      <div className="flex gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-amber-800 leading-relaxed">
          <p className="font-semibold mb-1">Minimum sürümü yükseltmeden önce oku</p>
          <p>
            <strong>Minimum desteklenen sürüm</strong>, bu değerin ALTINDAKİ tüm kullanıcıları
            kapatılamayan bir güncelleme ekranına kilitler. Yalnızca force-update kodunu içeren
            sürüm (v6.1+) mağazalarda yayılıp kullanıcıların çoğuna ulaştıktan <strong>sonra</strong>
            yavaşça yükselt. Yeni bir mağaza sürümü çıktığında bunu güncellemeyi buradan hatırla.
          </p>
        </div>
      </div>

      {/* Release checklist — her yeni sürümde yapılacaklar */}
      <div className="flex gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5">
        <ListChecks className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-900 leading-relaxed w-full">
          <p className="font-semibold mb-2">Yeni sürüm çıkardığımda yapmam gerekenler</p>

          <div className="flex items-center gap-1.5 font-semibold text-blue-800 mt-1 mb-1">
            <Apple className="w-4 h-4" /> iOS
          </div>
          <ol className="list-decimal list-inside space-y-0.5 mb-3">
            <li>
              <code className="bg-blue-100 px-1 rounded">ios/App/App.xcodeproj/project.pbxproj</code> →
              {" "}<code className="bg-blue-100 px-1 rounded">MARKETING_VERSION</code> +{" "}
              <code className="bg-blue-100 px-1 rounded">CURRENT_PROJECT_VERSION</code> bir artır.
            </li>
            <li>commit → push (Codemagic otomatik TestFlight'a atar).</li>
            <li>App Store'a MANUEL terfi et; yayılmayı bekle.</li>
            <li>
              Yeni sürüm kullanıcıların çoğuna ulaşınca buradan{" "}
              <strong>En güncel sürüm (iOS)</strong> alanını yeni sürüme çek.
            </li>
            <li>
              <strong>Minimum desteklenen (iOS)</strong>'i ise ancak eski sürümler iyice azalınca,
              yavaşça yükselt (aksi halde eski kullanıcılar kilitlenir).
            </li>
          </ol>

          <div className="flex items-center gap-1.5 font-semibold text-blue-800 mb-1">
            <Play className="w-4 h-4" /> Android
          </div>
          <ol className="list-decimal list-inside space-y-0.5">
            <li>
              <code className="bg-blue-100 px-1 rounded">android/app/build.gradle</code> →
              {" "}<code className="bg-blue-100 px-1 rounded">versionCode</code> +{" "}
              <code className="bg-blue-100 px-1 rounded">versionName</code> bir artır
              {" "}(<strong>PC'de değil, GİT'te</strong>).
            </li>
            <li>commit → push → PC'de temiz <code className="bg-blue-100 px-1 rounded">git pull</code>.</li>
            <li>Android Studio → AAB → Play Store'a yükle; yayılmayı bekle.</li>
            <li>
              Yayılınca buradan <strong>En güncel sürüm (Android)</strong> alanını yeni sürüme çek.
            </li>
            <li>
              <strong>Minimum desteklenen (Android)</strong>'i eski sürümler azalınca yavaşça yükselt.
            </li>
          </ol>
        </div>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-12">Yükleniyor…</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <PlatformCard platform="ios" Icon={Apple} title="iOS" />
            <PlatformCard platform="android" Icon={Play} title="Android" />
          </div>

          <div className="mt-5 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 h-12 px-6 bg-zinc-900 hover:bg-black text-white font-bold rounded-xl shadow-lg transition-all active:scale-[0.98] disabled:opacity-60"
            >
              <Save className="w-4 h-4" />
              {saving ? "Kaydediliyor…" : "Kaydet"}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default SAAppVersion;
