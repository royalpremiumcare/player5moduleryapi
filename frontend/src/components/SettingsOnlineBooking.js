import { useState, useEffect } from "react";
import { ArrowLeft, Save, Image, Upload, MapPin, Link, ChevronDown, ChevronUp, ExternalLink, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api, { BACKEND_URL } from "../api/api";
import { Browser } from '@capacitor/browser';

const getFullUrl = (url) => {
  if (!url) return null;
  if (url.startsWith('http')) return url;
  return `${BACKEND_URL}${url}`;
};

const SettingsOnlineBooking = ({ onNavigate }) => {
  const { t } = useTranslation();

  const [settings, setSettings] = useState({ company_name: "", support_phone: "", logo_url: "", images: [], slug: "" });
  const [loading, setLoading] = useState(false);

  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);

  const [galleryFiles, setGalleryFiles] = useState([]);
  const [galleryUploading, setGalleryUploading] = useState(false);
  const [galleryOpen, setGalleryOpen] = useState(false);

  const [location, setLocation] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const res = await api.get("/settings");
      setSettings(res.data || {});
      setLocation(res.data?.location || null);
    } catch (_) {
      toast.error("Ayarlar yüklenemedi.");
    }
  };

  const appointmentLink = (() => {
    if (!settings.slug) return null;
    const phone = settings.support_phone || "";
    const clean = phone.replace(/\s/g, "");
    const domain = (clean.startsWith('+44') || clean.startsWith('44')) ? 'plannapp.co.uk' : 'plannapp.co';
    return `${domain}/${settings.slug}`;
  })();

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      // 1. Galeri yükle
      if (galleryFiles.length > 0) {
        setGalleryUploading(true);
        const uploaded = [];
        for (const file of galleryFiles) {
          const fd = new FormData();
          fd.append('file', file);
          try {
            const r = await api.post("/upload/image", fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            if (r?.data?.url) uploaded.push(r.data.url);
          } catch (err) {
            toast.error("Görsel yüklenemedi: " + (err.response?.data?.detail || err.message));
          }
        }
        if (uploaded.length > 0) {
          settings.images = Array.from(new Set([...(settings.images || []), ...uploaded]));
        }
        setGalleryUploading(false);
      }

      // 2. Logo yükle
      if (logoFile) {
        const fd = new FormData();
        fd.append('file', logoFile);
        try {
          const r = await api.post("/settings/logo", fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          settings.logo_url = r.data.logo_url;
        } catch (err) {
          toast.error("Logo yüklenemedi: " + (err.response?.data?.detail || err.message));
        }
      }

      // 3. Ayarları kaydet
      await api.put("/settings", settings);
      toast.success("Kaydedildi.");
      await loadData();
      setLogoFile(null);
      setLogoPreview(null);
      setGalleryFiles([]);
    } catch (_) {
      toast.error("Kaydedilemedi.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 pb-20">
      {/* Header */}
      <div className="px-4 pt-6 pb-4">
        <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
          <button
            onClick={() => onNavigate && onNavigate("settings")}
            className="flex items-center gap-2 text-zinc-700 hover:text-zinc-900 mb-4 transition-colors p-2 -ml-2 hover:bg-white/50 rounded-xl"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-bold">{t('settings.backToSettings')}</span>
          </button>
          <div>
            <h2 className="text-xl font-black text-zinc-900">Online Randevu Sayfası</h2>
            <p className="text-sm text-zinc-600 mt-1 font-medium">Müşterilerin gördüğü randevu sayfanızı yönetin.</p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSave}>
        <div className="px-4 pb-4 space-y-4">

          {/* RANDEVU LİNKİ */}
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="flex items-center gap-2 mb-3">
              <Link className="w-5 h-5 text-zinc-900" />
              <h3 className="text-base font-black text-zinc-900">Randevu Linki</h3>
            </div>
            {appointmentLink ? (
              <div className="p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm space-y-2">
                <code className="block text-sm font-mono text-zinc-700 break-all">{appointmentLink}</code>
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      try { navigator.clipboard.writeText(appointmentLink); toast.success("Kopyalandı."); }
                      catch (_) { toast.error("Kopyalanamadı."); }
                    }}
                    className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-bold hover:bg-black transition-colors"
                  >
                    {t('settings.profile.buttons.copy')}
                  </button>
                  <button
                    type="button"
                    onClick={() => Browser.open({ url: `https://${appointmentLink}` })}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" /> Aç
                  </button>
                </div>
                <div className="flex items-start gap-2 mt-3 p-3 bg-blue-50/60 border border-blue-100 rounded-xl">
                  <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-700 font-medium leading-relaxed">
                    Bu linki kopyalayıp <strong>Instagram biyografinize</strong> veya <strong>WhatsApp profilinize</strong> ekleyin — müşterileriniz doğrudan sizden online randevu alabilsin.
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-zinc-500 font-medium">Henüz randevu linki oluşturulmamış. İşletme adını kaydedin.</p>
            )}
          </div>

          {/* LOGO */}
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="flex items-center gap-2 mb-3">
              <Image className="w-5 h-5 text-zinc-900" />
              <h3 className="text-base font-black text-zinc-900">{t('settings.profile.fields.logo')}</h3>
            </div>
            <p className="text-sm text-zinc-600 font-medium mb-4">{t('settings.profile.fields.logoNote')}</p>
            <div className="flex flex-col md:flex-row gap-4 p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm">
              <div className="flex-shrink-0">
                {(logoPreview || settings.logo_url) ? (
                  <div className="relative w-32 h-32 border-2 border-white/40 rounded-xl overflow-hidden backdrop-blur-sm bg-white/60 shadow-md">
                    <img src={logoPreview || getFullUrl(settings.logo_url)} alt="Logo" className="w-full h-full object-contain" />
                  </div>
                ) : (
                  <div className="w-32 h-32 border-2 border-dashed border-white/40 rounded-xl flex items-center justify-center backdrop-blur-sm bg-white/30">
                    <Upload className="w-8 h-8 text-zinc-400" />
                  </div>
                )}
              </div>
              <div className="flex-1 space-y-2">
                <Input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (!file) return;
                    if (file.size > 5 * 1024 * 1024) { toast.error(t('settings.profile.fileSizeError')); return; }
                    setLogoFile(file);
                    setLogoPreview(URL.createObjectURL(file));
                  }}
                  className="cursor-pointer backdrop-blur-md bg-white/60 border-white/40 rounded-xl font-medium"
                />
                <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.logoFormatsNote')}</p>
              </div>
            </div>
          </div>

          {/* GALERİ (Collapsible) */}
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl shadow-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setGalleryOpen(!galleryOpen)}
              className="w-full p-6 flex items-center justify-between hover:bg-white/20 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Image className="w-5 h-5 text-zinc-900" />
                <div className="text-left">
                  <h3 className="text-base font-black text-zinc-900">{t('settings.profile.fields.gallery', 'Galeri Yönetimi')}</h3>
                  <p className="text-sm text-zinc-600 font-medium">
                    {settings.images?.length > 0 ? `${settings.images.length} görsel` : 'Henüz görsel yok'}
                  </p>
                </div>
              </div>
              {galleryOpen ? <ChevronUp className="w-5 h-5 text-zinc-900" /> : <ChevronDown className="w-5 h-5 text-zinc-900" />}
            </button>

            {galleryOpen && (
              <div className="px-6 pb-6 pt-2 space-y-4">
                {/* Yükleme Alanı */}
                <div
                  className="p-4 backdrop-blur-md bg-white/50 rounded-xl border border-dashed border-white/40 shadow-sm"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const files = Array.from(e.dataTransfer.files || []).filter(f => (f?.type || '').startsWith('image/'));
                    if (!files.length) return;
                    if (files.find(f => f.size > 8 * 1024 * 1024)) { toast.error(t('settings.profile.fileSizeError')); return; }
                    setGalleryFiles(prev => [...prev, ...files]);
                  }}
                >
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                    <div className="text-sm text-zinc-700 font-medium">
                      {t('settings.profile.fields.galleryDrop', 'Görselleri buraya sürükleyip bırakın veya seçin')}
                    </div>
                    <Input
                      type="file"
                      multiple
                      accept="image/png,image/jpeg,image/jpg,image/webp"
                      onChange={(e) => {
                        const files = Array.from(e.target.files || []);
                        if (!files.length) return;
                        if (files.find(f => f.size > 8 * 1024 * 1024)) { toast.error(t('settings.profile.fileSizeError')); return; }
                        setGalleryFiles(prev => [...prev, ...files]);
                        e.target.value = '';
                      }}
                      className="cursor-pointer backdrop-blur-md bg-white/60 border-white/40 rounded-xl font-medium"
                    />
                  </div>
                  {galleryFiles.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {galleryFiles.map((f, i) => (
                        <span key={`${f.name}-${i}`} className="px-3 py-1.5 rounded-lg bg-white/60 border border-white/40 text-xs font-bold text-zinc-700">
                          {f.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Mevcut Görseller */}
                {settings.images?.length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {settings.images.map((url) => (
                      <div key={url} className="relative rounded-xl overflow-hidden border border-white/30 bg-white/40">
                        <img src={getFullUrl(url)} alt="" className="w-full aspect-video object-cover" />
                        <button
                          type="button"
                          onClick={() => setSettings(prev => ({ ...prev, images: prev.images.filter(x => x !== url) }))}
                          className="absolute top-2 right-2 px-2 py-1 rounded-lg bg-zinc-900 text-white text-xs font-bold shadow-md"
                        >
                          {t('common.delete', 'Sil')}
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {galleryUploading && (
                  <p className="text-sm text-zinc-600 font-medium">Yükleniyor...</p>
                )}
              </div>
            )}
          </div>

          {/* KONUM */}
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="flex items-center gap-2 mb-3">
              <MapPin className="w-5 h-5 text-zinc-900" />
              <h3 className="text-base font-black text-zinc-900">{t('settings.location', 'Konum')}</h3>
            </div>
            {location?.address ? (
              <div className="p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm space-y-3">
                <p className="text-sm font-medium text-zinc-700">{location.address}</p>
                {location.coordinates && (
                  <p className="text-xs text-zinc-500">
                    {Number(location.coordinates.lat).toFixed(6)}, {Number(location.coordinates.lng).toFixed(6)}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => onNavigate && onNavigate("settings-location")}
                  className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-bold hover:bg-black transition-colors"
                >
                  Konumu Düzenle
                </button>
              </div>
            ) : (
              <div className="p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm space-y-3">
                <p className="text-sm text-zinc-500 font-medium">Henüz konum eklenmemiş.</p>
                <button
                  type="button"
                  onClick={() => onNavigate && onNavigate("settings-location")}
                  className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-bold hover:bg-black transition-colors"
                >
                  Konum Ekle
                </button>
              </div>
            )}
          </div>

          {/* KAYDET */}
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-zinc-900 hover:bg-black h-12 text-base font-bold rounded-xl shadow-lg"
            >
              <Save className="w-5 h-5 mr-2" />
              {loading ? t('settings.profile.buttons.saving') : t('settings.profile.buttons.saveSettings')}
            </Button>
          </div>

        </div>
      </form>
    </div>
  );
};

export default SettingsOnlineBooking;
