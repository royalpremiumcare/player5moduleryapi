import { useState, useEffect } from "react";
import { User, ArrowLeft, Save, Phone, MessageSquare, Upload, Image, Lock, ChevronDown, ChevronUp, Clock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api, { BACKEND_URL } from "../api/api";
import { useAuth } from "../context/AuthContext";

// Logo URL'ini full URL'e çevir (native için gerekli)
const getFullLogoUrl = (logoUrl) => {
  if (!logoUrl) return null;
  if (logoUrl.startsWith('http')) return logoUrl;
  return `${BACKEND_URL}${logoUrl}`;
};

const SettingsProfile = ({ onNavigate }) => {
  const { userRole, token } = useAuth();
  const { t } = useTranslation();
  const [settings, setSettings] = useState({
    company_name: "",
    support_phone: "",
    logo_url: "",
    images: [],
    slug: "",
    sms_reminder_hours: 1.0,
    business_hours: {
      monday: { is_open: true, open_time: "09:00", close_time: "18:00" },
      tuesday: { is_open: true, open_time: "09:00", close_time: "18:00" },
      wednesday: { is_open: true, open_time: "09:00", close_time: "18:00" },
      thursday: { is_open: true, open_time: "09:00", close_time: "18:00" },
      friday: { is_open: true, open_time: "09:00", close_time: "18:00" },
      saturday: { is_open: false, open_time: "09:00", close_time: "18:00" },
      sunday: { is_open: false, open_time: "09:00", close_time: "18:00" }
    }
  });
  
  // Personel için kullanıcı bilgileri
  const [userInfo, setUserInfo] = useState({
    full_name: "",
    username: "",
  });
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [galleryFiles, setGalleryFiles] = useState([]);
  const [galleryUploading, setGalleryUploading] = useState(false);
  const [businessHoursOpen, setBusinessHoursOpen] = useState(false);

  useEffect(() => {
    // Token'ı localStorage'dan al (eğer context'ten gelmiyorsa)
    const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    const storedRole = userRole || localStorage.getItem('userRole') || sessionStorage.getItem('userRole');
    
    if (storedRole === 'admin') {
      loadSettings();
    } else {
      // Staff veya belirsiz durumda kullanıcı bilgilerini yükle
      if (authToken) {
        loadUserInfo();
      }
    }
  }, []);

  const loadUserInfo = async () => {
    try {
      // Token'ı localStorage'dan al (eğer context'ten gelmiyorsa)
      let authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      
      if (!authToken) {
        toast.error(t('settings.profile.sessionNotFound'));
        return;
      }
      
      const tokenPayload = JSON.parse(atob(authToken.split('.')[1]));
      const username = tokenPayload.sub || tokenPayload.username;
      
      if (!username) {
        toast.error(t('settings.profile.userInfoError'));
        setUserInfo({
          full_name: tokenPayload.full_name || "",
          username: t('settings.profile.unknown'),
        });
        return;
      }
      
      // Kullanıcı listesinden kendi bilgilerini bul
      const response = await api.get("/users");
      const users = response.data || [];
      const currentUser = users.find(u => u.username === username);
      
      if (currentUser) {
        setUserInfo({
          full_name: currentUser.full_name || "",
          username: currentUser.username || "",
        });
      } else {
        // Fallback: Token'dan gelen bilgileri kullan
        setUserInfo({
          full_name: tokenPayload.full_name || "",
          username: username,
        });
      }
    } catch (error) {
      if (error.response && error.response.status !== 401) {
        toast.error(t('settings.profile.userInfoLoadError', { error: error.message || t('errors.generic') }));
      }
      // Hata durumunda da token'dan bilgileri yükle
      let authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      if (authToken) {
        try {
          const tokenPayload = JSON.parse(atob(authToken.split('.')[1]));
          setUserInfo({
            full_name: tokenPayload.full_name || "",
            username: tokenPayload.sub || tokenPayload.username || "",
          });
        } catch (e) {
          // Token parse hatası - sessizce geç
        }
      }
    }
  };

  const loadSettings = async () => {
    try {
      const response = await api.get("/settings");
      const data = response.data;
      // business_hours yoksa varsayılan değerleri kullan
      if (!data.business_hours) {
        data.business_hours = {
          monday: { is_open: true, open_time: "09:00", close_time: "18:00" },
          tuesday: { is_open: true, open_time: "09:00", close_time: "18:00" },
          wednesday: { is_open: true, open_time: "09:00", close_time: "18:00" },
          thursday: { is_open: true, open_time: "09:00", close_time: "18:00" },
          friday: { is_open: true, open_time: "09:00", close_time: "18:00" },
          saturday: { is_open: false, open_time: "09:00", close_time: "18:00" },
          sunday: { is_open: false, open_time: "09:00", close_time: "18:00" }
        };
      }
      setSettings(data); 
    } catch (error) {
      if (error.response && error.response.status !== 401) {
        toast.error(t('settings.profile.settingsLoadError'));
      }
    }
  };

  const handleSaveUser = async (e) => {
    e.preventDefault();

    if (newPassword && newPassword.length < 6) {
      toast.error(t('settings.profile.passwordMinLength'));
      return;
    }

    if (newPassword && newPassword !== confirmPassword) {
      toast.error(t('settings.profile.passwordMismatch'));
      return;
    }

    setLoading(true);
    try {
      const updateData = {};
      if (userInfo.full_name) {
        updateData.full_name = userInfo.full_name;
      }
      if (newPassword) {
        updateData.password = newPassword;
      }

      await api.put("/users/me", updateData);
      toast.success(t('settings.profile.profileUpdated'));
      
      setNewPassword("");
      setConfirmPassword("");
      await loadUserInfo();
      
    } catch (error) {
      const errorMessage = error.response?.data?.detail || t('settings.profile.profileUpdateError');
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();

    if (!settings.company_name) {
        toast.error(t('settings.profile.companyNameRequired'));
        return;
    }

    setLoading(true);
    try {
      if (galleryFiles.length > 0) {
        setGalleryUploading(true);
        const uploadedUrls = [];

        for (const file of galleryFiles) {
          const formData = new FormData();
          formData.append('file', file);
          try {
            const res = await api.post("/upload/image", formData, {
              headers: {
                'Content-Type': 'multipart/form-data'
              }
            });
            if (res?.data?.url) {
              uploadedUrls.push(res.data.url);
            }
          } catch (error) {
            toast.error(t('settings.profile.logoUploadError', { error: error.response?.data?.detail || error.message }));
          }
        }

        if (uploadedUrls.length > 0) {
          settings.images = Array.from(new Set([...(settings.images || []), ...uploadedUrls]));
        }
      }

      if (logoFile) {
        const formData = new FormData();
        formData.append('file', logoFile);
        
        try {
          const logoResponse = await api.post("/settings/logo", formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          });
          
          settings.logo_url = logoResponse.data.logo_url;
          toast.success(t('settings.profile.logoUploaded'));
        } catch (error) {
          toast.error(t('settings.profile.logoUploadError', { error: error.response?.data?.detail || error.message }));
        }
      }
      
      await api.put("/settings", settings); 
      toast.success(t('settings.profile.settingsSaved'));
      
      await loadSettings();
      setLogoFile(null);
      setLogoPreview(null);
      setGalleryFiles([]);
      
    } catch (error) {
      toast.error(t('settings.profile.settingsSaveError'));
    } finally {
      setGalleryUploading(false);
      setLoading(false);
    }
  };

  const currentRole = userRole || localStorage.getItem('userRole');

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
            <h2 className="text-xl font-black text-zinc-900">
              {currentRole === 'staff' ? t('settings.profile.title') : t('settings.profile.businessTitle')}
            </h2>
            <p className="text-sm text-zinc-600 mt-1 font-medium">
              {currentRole === 'staff' ? t('settings.profile.profileSubtitle') : t('settings.profile.businessSubtitle')}
            </p>
          </div>
        </div>
      </div>

      {/* Staff Profile */}
      {currentRole === 'staff' ? (
        userInfo.username ? (
          <form onSubmit={handleSaveUser}>
            <div className="px-4 pb-4 space-y-4">
              {/* Profil Bilgileri Kartı */}
              <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-black text-zinc-900 mb-1">{t('settings.profile.fields.profileInfo')}</h3>
                    <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.profileInfoNote')}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.email')}</Label>
                    <Input
                      id="username"
                      type="email"
                      value={userInfo.username}
                      disabled
                      className="backdrop-blur-md bg-zinc-100/60 border-white/40 rounded-xl h-11 font-medium"
                    />
                    <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.emailCannotChange')}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="full-name" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.fullName')}</Label>
                    <Input
                      id="full-name"
                      type="text"
                      value={userInfo.full_name}
                      onChange={(e) => setUserInfo({ ...userInfo, full_name: e.target.value })}
                      placeholder={t('settings.profile.fields.fullNamePlaceholder')}
                      className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                    />
                  </div>
                </div>
              </div>

              {/* Şifre Değiştirme Kartı */}
              <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-black text-zinc-900 mb-1">{t('settings.profile.fields.changePassword')}</h3>
                    <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.changePasswordNote')}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="new-password" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.newPassword')}</Label>
                    <Input
                      id="new-password"
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder={t('settings.profile.fields.newPasswordPlaceholder')}
                      className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                    />
                    <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.passwordMinLengthNote')}</p>
                  </div>

                  {newPassword && (
                    <div className="space-y-2">
                      <Label htmlFor="confirm-password" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.confirmPassword')}</Label>
                      <Input
                        id="confirm-password"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder={t('settings.profile.fields.confirmPasswordPlaceholder')}
                        className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Kaydet Butonu */}
              <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-zinc-900 hover:bg-black h-12 text-base font-bold rounded-xl shadow-lg"
                >
                  <Save className="w-5 h-5 mr-2" />
                  {loading ? t('settings.profile.buttons.saving') : t('settings.profile.buttons.saveProfile')}
                </Button>
              </div>
            </div>
          </form>
        ) : (
          <div className="px-4 pb-4">
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 mx-auto mb-3"></div>
                <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.buttons.loading')}</p>
              </div>
            </div>
          </div>
        )
      ) : (
        /* Admin Settings */
        <form onSubmit={handleSave}>
          <div className="px-4 pb-4 space-y-4">
            {/* KART 1: Logo */}
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-black text-zinc-900 mb-1 flex items-center gap-2">
                    <Image className="w-5 h-5" />
                    {t('settings.profile.fields.logo')}
                  </h3>
                  <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.logoNote')}</p>
                </div>

                <div className="flex flex-col md:flex-row gap-4 p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm">
                  <div className="flex-shrink-0">
                    {(logoPreview || settings.logo_url) ? (
                      <div className="relative w-32 h-32 border-2 border-white/40 rounded-xl overflow-hidden backdrop-blur-sm bg-white/60 shadow-md">
                        <img
                          src={logoPreview || getFullLogoUrl(settings.logo_url)}
                          alt="Logo"
                          className="w-full h-full object-contain"
                        />
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
                        if (file) {
                          if (file.size > 5 * 1024 * 1024) {
                            toast.error(t('settings.profile.fileSizeError'));
                            return;
                          }
                          setLogoFile(file);
                          setLogoPreview(URL.createObjectURL(file));
                        }
                      }}
                      className="cursor-pointer backdrop-blur-md bg-white/60 border-white/40 rounded-xl font-medium"
                    />
                    <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.logoFormatsNote')}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-black text-zinc-900 mb-1 flex items-center gap-2">
                    <Image className="w-5 h-5" />
                    {t('settings.profile.fields.gallery', 'Galeri Yönetimi')}
                  </h3>
                  <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.galleryNote', 'İşletmenizin portföy görsellerini yükleyin.')}</p>
                </div>

                <div
                  className="p-4 backdrop-blur-md bg-white/50 rounded-xl border border-dashed border-white/40 shadow-sm"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const files = Array.from(e.dataTransfer.files || []).filter((f) => (f?.type || '').startsWith('image/'));
                    if (files.length === 0) return;
                    const tooBig = files.find((f) => f.size > 8 * 1024 * 1024);
                    if (tooBig) {
                      toast.error(t('settings.profile.fileSizeError'));
                      return;
                    }
                    setGalleryFiles((prev) => [...prev, ...files]);
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
                        if (files.length === 0) return;
                        const tooBig = files.find((f) => f.size > 8 * 1024 * 1024);
                        if (tooBig) {
                          toast.error(t('settings.profile.fileSizeError'));
                          return;
                        }
                        setGalleryFiles((prev) => [...prev, ...files]);
                        e.target.value = '';
                      }}
                      className="cursor-pointer backdrop-blur-md bg-white/60 border-white/40 rounded-xl font-medium"
                    />
                  </div>

                  {galleryFiles.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {galleryFiles.map((f, idx) => (
                        <div key={`${f.name}-${idx}`} className="px-3 py-1.5 rounded-lg bg-white/60 border border-white/40 text-xs font-bold text-zinc-700">
                          {f.name}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {(settings.images?.length > 0) && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {(settings.images || []).map((url) => (
                      <div key={url} className="relative rounded-xl overflow-hidden border border-white/30 bg-white/40">
                        <img src={getFullLogoUrl(url)} alt="" className="w-full aspect-video object-cover" />
                        <button
                          type="button"
                          onClick={() => {
                            setSettings((prev) => ({
                              ...prev,
                              images: (prev.images || []).filter((x) => x !== url)
                            }));
                          }}
                          className="absolute top-2 right-2 px-2 py-1 rounded-lg bg-zinc-900 text-white text-xs font-bold shadow-md"
                        >
                          {t('common.delete', 'Sil')}
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {galleryUploading && (
                  <div className="text-sm text-zinc-600 font-medium">
                    {t('appointments.form.loading', 'Yükleniyor...')}
                  </div>
                )}
              </div>
            </div>

            {/* KART 2: İşletme Adı ve Telefon */}
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-black text-zinc-900 mb-1 flex items-center gap-2">
                    <User className="w-5 h-5" />
                    {t('settings.profile.fields.businessInfo')}
                  </h3>
                  <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.businessInfoNote')}</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="company-name" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.companyName')}</Label>
                  <Input
                    id="company-name"
                    type="text"
                    value={settings.company_name}
                    onChange={(e) => setSettings({ ...settings, company_name: e.target.value })}
                    required
                    className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                  />
                  <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.companyNameNote')}</p>
                  {settings.slug && (() => {
                    const phone = settings.support_phone || "";
                    const cleanPhone = phone.replace(/\s/g, "");
                    const domain = (cleanPhone.startsWith('+44') || cleanPhone.startsWith('44')) ? 'plannapp.co.uk' : 'plannapp.co';
                    const appointmentLink = `${domain}/${settings.slug}`;
                    
                    return (
                      <div className="mt-3 p-4 backdrop-blur-md bg-white/50 rounded-xl border border-white/30 shadow-sm">
                        <p className="text-xs text-zinc-600 mb-2 font-bold uppercase tracking-wider">{t('settings.profile.fields.appointmentLink')}</p>
                        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                          <code className="flex-1 text-sm font-mono backdrop-blur-sm bg-white/60 px-3 py-2.5 rounded-lg border border-white/40 text-zinc-700 break-all font-medium shadow-sm">
                            {appointmentLink}
                          </code>
                          <button
                            type="button"
                            onClick={() => {
                              try {
                                navigator.clipboard.writeText(appointmentLink);
                                toast.success(t('settings.profile.linkCopied'));
                              } catch (error) {
                                toast.error(t('settings.profile.linkCopyError'));
                              }
                            }}
                            className="px-4 py-2.5 bg-zinc-900 text-white rounded-lg hover:bg-black transition-colors text-xs font-bold whitespace-nowrap shadow-md"
                          >
                            {t('settings.profile.buttons.copy')}
                          </button>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="support-phone" className="text-sm font-bold text-zinc-700">
                    <Phone className="w-4 h-4 inline mr-1" />
                    {t('settings.profile.fields.supportPhone')}
                  </Label>
                  <Input
                    id="support-phone"
                    type="tel"
                    value={settings.support_phone || ""}
                    onChange={(e) => setSettings({ ...settings, support_phone: e.target.value })}
                    placeholder="+90 555 123 45 67"
                    required
                    className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                  />
                  <p className="text-xs text-zinc-600 font-medium">{t('settings.profile.fields.supportPhoneNote')}</p>
                </div>
              </div>
            </div>

            {/* KART 3: WhatsApp Hatırlatma */}
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-black text-zinc-900 mb-1 flex items-center gap-2">
                    <MessageSquare className="w-5 h-5" />
                    {t('settings.profile.fields.whatsappReminder')}
                  </h3>
                  <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.whatsappReminderNote')}</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="whatsapp-reminder" className="text-sm font-bold text-zinc-700">
                    {t('settings.profile.fields.reminderTime')}
                  </Label>
                  <select
                    id="whatsapp-reminder"
                    value={settings.sms_reminder_hours}
                    onChange={(e) => setSettings({ ...settings, sms_reminder_hours: parseFloat(e.target.value) })}
                    className="w-full px-4 py-2.5 backdrop-blur-md bg-white/60 border border-white/40 rounded-xl focus:ring-2 focus:ring-zinc-900 font-medium shadow-sm"
                  >
                    <option value="0.5">{t('settings.profile.reminderOptions.30min')}</option>
                    <option value="1">{t('settings.profile.reminderOptions.1hour')}</option>
                    <option value="2">{t('settings.profile.reminderOptions.2hours')}</option>
                    <option value="3">{t('settings.profile.reminderOptions.3hours')}</option>
                    <option value="6">{t('settings.profile.reminderOptions.6hours')}</option>
                    <option value="12">{t('settings.profile.reminderOptions.12hours')}</option>
                    <option value="24">{t('settings.profile.reminderOptions.24hours')}</option>
                  </select>
                </div>
              </div>
            </div>

            {/* KART 4: Çalışma Saatleri (Collapsible) */}
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl shadow-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setBusinessHoursOpen(!businessHoursOpen)}
                className="w-full p-6 flex items-center justify-between hover:bg-white/20 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-zinc-900" />
                  <div className="text-left">
                    <h3 className="text-base font-black text-zinc-900">{t('settings.profile.fields.businessHours')}</h3>
                    <p className="text-sm text-zinc-600 font-medium">{t('settings.profile.fields.businessHoursNote')}</p>
                  </div>
                </div>
                {businessHoursOpen ? (
                  <ChevronUp className="w-5 h-5 text-zinc-900" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-zinc-900" />
                )}
              </button>

              {businessHoursOpen && (
                <div className="px-6 pb-6 pt-2">
                  <div className="grid grid-cols-1 gap-2">
                    {[
                      { key: 'monday', label: t('settings.profile.days.monday') },
                      { key: 'tuesday', label: t('settings.profile.days.tuesday') },
                      { key: 'wednesday', label: t('settings.profile.days.wednesday') },
                      { key: 'thursday', label: t('settings.profile.days.thursday') },
                      { key: 'friday', label: t('settings.profile.days.friday') },
                      { key: 'saturday', label: t('settings.profile.days.saturday') },
                      { key: 'sunday', label: t('settings.profile.days.sunday') }
                    ].map((day) => {
                      const dayData = settings.business_hours?.[day.key] || { is_open: true, open_time: "09:00", close_time: "18:00" };
                      return (
                        <div key={day.key} className="flex items-center gap-2 p-3 backdrop-blur-md bg-white/60 rounded-xl border border-white/30 shadow-sm">
                          <div className="w-16 flex-shrink-0">
                            <span className="text-xs font-bold text-zinc-900">{day.label}</span>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <Switch
                              checked={dayData.is_open}
                              onCheckedChange={(checked) => {
                                setSettings({
                                  ...settings,
                                  business_hours: {
                                    ...settings.business_hours,
                                    [day.key]: {
                                      ...dayData,
                                      is_open: checked
                                    }
                                  }
                                });
                              }}
                            />
                          </div>
                          {dayData.is_open ? (
                            <div className="flex items-center gap-1.5 flex-1">
                              <Input
                                type="time"
                                value={dayData.open_time}
                                onChange={(e) => {
                                  setSettings({
                                    ...settings,
                                    business_hours: {
                                      ...settings.business_hours,
                                      [day.key]: {
                                        ...dayData,
                                        open_time: e.target.value
                                      }
                                    }
                                  });
                                }}
                                className="w-24 text-xs p-1.5 backdrop-blur-sm bg-white/80 border-white/40 rounded-lg font-medium"
                              />
                              <span className="text-zinc-400 text-xs font-bold">-</span>
                              <Input
                                type="time"
                                value={dayData.close_time}
                                onChange={(e) => {
                                  setSettings({
                                    ...settings,
                                    business_hours: {
                                      ...settings.business_hours,
                                      [day.key]: {
                                        ...dayData,
                                        close_time: e.target.value
                                      }
                                    }
                                  });
                                }}
                                className="w-24 text-xs p-1.5 backdrop-blur-sm bg-white/80 border-white/40 rounded-lg font-medium"
                              />
                            </div>
                          ) : (
                            <span className="text-xs text-zinc-400 flex-1 font-bold">{t('settings.profile.closed')}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Kaydet Butonu */}
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
      )}
    </div>
  );
};

export default SettingsProfile;