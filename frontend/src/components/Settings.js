import { useState, useEffect } from "react";
import { 
  Package, User, UserCog, Briefcase, HelpCircle, LogOut, ChevronRight, 
  ArrowLeft, DollarSign, Bell, BellOff, MapPin, Wrench, ShieldCheck, Globe,
  Wallet, CreditCard, Phone, MessageCircle, Mail, Headphones, Sparkles
} from "lucide-react"; 
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { WHATSAPP_PHONE_DISPLAY, WHATSAPP_URL, openLiveChat } from "../constants/contact";
import { Capacitor, registerPlugin } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

const FCMTokenPlugin = Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios'
  ? registerPlugin('FCMTokenPlugin')
  : null;

// --- YARDIMCI BİLEŞEN: AYAR SATIRI ---
// Tasarım Dili: Minimalist & Kurumsal
const SettingItem = ({ 
  icon: Icon, 
  title, 
  subtitle, 
  onClick, 
  rightElement, 
  isDestructive = false,
  className = ""
}) => (
  <div 
    onClick={onClick} 
    className={`flex items-center justify-between p-5 bg-white active:bg-zinc-50 transition-colors cursor-pointer first:rounded-t-2xl last:rounded-b-2xl border-b last:border-0 border-zinc-100 ${className}`}
  >
    <div className="flex items-center gap-4">
      {/* İkon Alanı: Renkli yerine "Kurumsal Gri" ve Çerçeveli */}
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 border shadow-sm ${
        isDestructive 
          ? 'bg-red-50 border-red-100 text-red-600' 
          : 'bg-zinc-50 border-zinc-200 text-zinc-600'
      }`}>
        <Icon className="w-6 h-6" strokeWidth={1.5} />
      </div>
      
      <div>
        <p className={`text-base font-medium ${isDestructive ? 'text-red-600' : 'text-zinc-900'}`}>
          {title}
        </p>
        {subtitle && <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
    <div className="pl-3">
      {rightElement || <ChevronRight className="w-5 h-5 text-zinc-300" />}
    </div>
  </div>
);

// --- YARDIMCI BİLEŞEN: KATEGORİ BAŞLIĞI ---
const SectionTitle = ({ title }) => (
  <h3 className="px-5 mb-3 mt-8 text-sm font-bold text-zinc-400 uppercase tracking-widest">
    {title}
  </h3>
);

const Settings = ({ onNavigate, userRole, onLogout }) => {
  const { t } = useTranslation();
  const isStaff = userRole === 'staff' || userRole === 'personnel';
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [permissionStatus, setPermissionStatus] = useState('default');
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [showContact, setShowContact] = useState(false);

  // İletişim alt-sayfası açılırken / kapanırken scroll'u en başa al.
  // Settings.js içinde currentView değişmediği için App.js global scroll
  // reset tetiklenmiyor; alt-sayfaya özel manuel sıfırlama gerekiyor.
  useEffect(() => {
    const wrapper = document.getElementById("app-wrapper");
    if (wrapper) wrapper.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [showContact]);

  // --- BİLDİRİM MANTIĞI ---
  // Switch backend aboneliğine göre çalışır (OS izni ≠ kayıtlı cihaz).
  useEffect(() => {
    const syncPushStatus = async () => {
      const isNative = Capacitor.isNativePlatform();
      if (isNative) {
        try {
          const status = await PushNotifications.checkPermissions();
          setPermissionStatus(status.receive);
        } catch {
          setPermissionStatus('default');
        }
      } else if ('Notification' in window) {
        setPermissionStatus(Notification.permission);
      }
      try {
        const res = await api.get('/push/status');
        setPushSubscribed(!!res.data?.subscribed);
      } catch {
        setPushSubscribed(false);
      }
    };
    syncPushStatus();
  }, []);

  const handleEnableNotifications = async () => {
    const isNative = Capacitor.isNativePlatform();
    
    // Native (Android/iOS)
    if (isNative) {
      setIsSubscribing(true);
      try {
        const permStatus = await PushNotifications.requestPermissions();
        if (permStatus.receive === 'granted') {
          const platform = Capacitor.getPlatform();

          if (platform === 'ios' && FCMTokenPlugin) {
            // iOS: FCMTokenPlugin ile doğrudan FCM token al
            const fcmResult = await FCMTokenPlugin.registerAndGetToken();
            if (fcmResult && fcmResult.token) {
              await api.post('/push/subscribe', {
                subscription: {
                  endpoint: fcmResult.token,
                  keys: { p256dh: '', auth: '' },
                  platform: 'ios'
                }
              });
              setPushSubscribed(true);
            }
          } else {
            // Android: Capacitor registration event kullan
            await PushNotifications.register();
            PushNotifications.addListener('registration', async (token) => {
              await api.post('/push/subscribe', {
                subscription: {
                  endpoint: token.value,
                  keys: { p256dh: '', auth: '' },
                  platform: platform
                }
              });
              setPushSubscribed(true);
            });
          }
          setPushSubscribed(true);
          setPermissionStatus('granted');
          toast.success(t('settings.notificationsEnabledSuccess'));
        } else {
          setPermissionStatus('denied');
          toast.error(t('settings.notificationsPermissionDenied'));
        }
      } catch (error) {
        toast.error(t('settings.notificationsEnableError'));
      } finally {
        setIsSubscribing(false);
      }
      return;
    }
    
    // Web
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      toast.error(t('settings.notificationsBrowserNotSupported'));
      return;
    }

    setIsSubscribing(true);
    try {
      const permission = await Notification.requestPermission();
      setPermissionStatus(permission);
      
      if (permission === 'granted') {
        const registration = await navigator.serviceWorker.ready;
        const vapidResponse = await api.get('/push/vapid-key');
        const vapidPublicKey = vapidResponse.data.publicKey;
        
        const urlBase64ToUint8Array = (base64String) => {
          const padding = '='.repeat((4 - base64String.length % 4) % 4);
          const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
          const rawData = window.atob(base64);
          const outputArray = new Uint8Array(rawData.length);
          for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
          }
          return outputArray;
        };

        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });

        await api.post('/push/subscribe', { subscription: subscription.toJSON() });
        setPushSubscribed(true);
        toast.success(t('settings.notificationsEnabledSuccess'));
      } else if (permission === 'denied') {
        toast.error(t('settings.notificationsPermissionDeniedWeb'));
      }
    } catch (error) {
      toast.error(t('settings.notificationsEnableError'));
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleDisableNotifications = async () => {
    setIsSubscribing(true);
    try {
      await api.delete('/push/unsubscribe');
      setPushSubscribed(false);
      toast.success(t('settings.notificationsDisabledSuccess'));
    } catch (error) {
      toast.error(t('settings.notificationsDisableError'));
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleToggleNotifications = async (checked) => {
    if (checked) await handleEnableNotifications();
    else await handleDisableNotifications();
  };

  const handleRepairNotifications = async () => {
    try {
      toast.info(t('settings.notificationsRepairing'));
      const isNative = Capacitor.isNativePlatform();
      
      if (isNative) {
        const permStatus = await PushNotifications.requestPermissions();
        if (permStatus.receive === 'granted') {
          await PushNotifications.register();
          PushNotifications.addListener('registration', async (token) => {
            await api.post('/push/subscribe', {
              subscription: {
                endpoint: token.value,
                keys: { p256dh: '', auth: '' },
                platform: Capacitor.getPlatform()
              }
            });
            toast.success(t('settings.notificationsRepaired'));
          });
        }
      } else if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) await sub.unsubscribe();
        window.location.reload();
      }
    } catch (error) {
      toast.error(t('settings.notificationsRepairError'));
    }
  };

  // --- RENDER ---

  if (showContact) {
    return (
      <div className="min-h-screen bg-gray-50/50 pb-24 font-sans selection:bg-gray-200">
        <div className="px-5 pt-8 pb-4 bg-white border-b border-gray-100 sticky top-0 z-10 shadow-sm">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowContact(false)}
              className="p-2 -ml-2 rounded-full hover:bg-gray-100 text-zinc-600 transition-colors"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">{t('settings.contact', 'İletişim')}</h1>
            </div>
          </div>
        </div>
        <div className="px-5 mt-6 space-y-3">
          <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
            <SettingItem
              icon={Headphones}
              title={t('settings.liveChat', 'Canlı Destek')}
              subtitle={t('settings.liveChatSubtitle', 'Anında yazışın, hızlıca yardım alın')}
              onClick={() => openLiveChat()}
              // showContact'i kapatma — widget kapatıldığında kullanıcı
              // İletişim sayfasına geri dönmeli, Ayarlar'a değil.
            />
            <SettingItem
              icon={MessageCircle}
              title="WhatsApp"
              subtitle={t('settings.whatsappSubtitle', { defaultValue: 'WhatsApp üzerinden hızlı destek' })}
              onClick={() => window.open(WHATSAPP_URL, '_blank', 'noopener,noreferrer')}
            />
            <SettingItem
              icon={Mail}
              title="E-posta"
              subtitle="info@plannapp.co"
              onClick={() => window.open('mailto:info@plannapp.co')}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 pb-24 font-sans selection:bg-gray-200">
      
      {/* HEADER */}
      <div className="px-5 pt-8 pb-4 bg-white border-b border-gray-100 sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <button
            onClick={() => onNavigate && onNavigate("dashboard")}
            className="p-2 -ml-2 rounded-full hover:bg-gray-100 text-zinc-600 transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 tracking-tight leading-none">{t('settings.title')}</h1>
            <p className="text-sm text-zinc-500 mt-1 font-medium">{t('settings.subtitle')}</p>
          </div>
        </div>
      </div>

      <div className="p-5 max-w-3xl mx-auto">
        
        {/* GRUP 1: HESAP & ABONELİK */}
        <SectionTitle title={t('settings.sections.accountPlan')} />
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
          
          {/* Profil (Herkes) */}
          <SettingItem 
            icon={User} 
            title={t('settings.profile.title')}
            subtitle={userRole === 'admin' ? t('settings.businessDescription') : t('settings.profileDescription')}
            onClick={() => onNavigate && onNavigate("settings-profile")}
          />

          {/* Abonelik (Sadece Admin) */}
          {userRole === 'admin' && (
            <SettingItem 
              icon={Package} 
              title={t('settings.subscription')}
              subtitle={t('settings.subscriptionDescription')}
              onClick={() => onNavigate && onNavigate("settings-subscription")}
            />
          )}
        </div>

        {/* GRUP 2: İŞLETME YÖNETİMİ (Sadece Admin) */}
        {userRole === 'admin' && (
          <>
            <SectionTitle title={t('settings.sections.businessManagement')} />
            <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
              
              <SettingItem 
                icon={Globe} 
                title={t('settings.onlineBookingPageTitle')}
                subtitle={t('settings.onlineBookingPageSubtitle')}
                onClick={() => onNavigate && onNavigate("settings-online-booking")}
              />

              <SettingItem 
                icon={UserCog} 
                title={t('settings.staffManagement')}
                subtitle={t('settings.staffManagementSubtitle')}
                onClick={() => onNavigate && onNavigate("staff")}
              />

              <SettingItem 
                icon={Briefcase} 
                title={t('settings.serviceManagement')}
                subtitle={t('settings.serviceManagementSubtitle')}
                onClick={() => onNavigate && onNavigate("services")}
              />

              <SettingItem 
                icon={DollarSign} 
                title={t('settings.financeManagement')}
                subtitle={t('settings.financeManagementSubtitle')}
                onClick={() => onNavigate && onNavigate("settings-finance")}
              />
            </div>

            {/* PAZARLAMA */}
            <SectionTitle title={t('settings.sections.marketing')} />
            <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
              <SettingItem 
                icon={Sparkles} 
                title={t('settings.marketingAssistant.title')}
                subtitle={t('settings.marketingAssistant.subtitle')}
                onClick={() => onNavigate && onNavigate("marketing-assistant")}
              />
            </div>

            {/* ÖDEME YÖNETİMİ */}
            <SectionTitle title="Ödeme Yönetimi" />
            <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
              <SettingItem 
                icon={Wallet} 
                title="Cüzdan"
                subtitle="Bakiye, işlemler ve ödeme talepleri"
                onClick={() => onNavigate && onNavigate("merchant-wallet")}
              />
              <SettingItem 
                icon={CreditCard} 
                title="Ödeme Ayarları"
                subtitle="Banka bilgileri, komisyon ve ödeme tercihleri"
                onClick={() => onNavigate && onNavigate("merchant-payment-settings")}
              />
            </div>
          </>
        )}

        {/* GRUP 3: UYGULAMA AYARLARI */}
        <SectionTitle title={t('settings.sections.appPreferences')} />
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
          
          {/* Bildirimler (Switch) — backend aboneliğine göre; OS izni ayrı kalır */}
          <SettingItem 
            icon={pushSubscribed ? Bell : BellOff} 
            title={t('settings.notifications')}
            subtitle={
              pushSubscribed
                ? t('settings.notificationsOn')
                : permissionStatus === 'granted'
                  ? t('settings.notificationsOffButPermissionGranted')
                  : t('settings.notificationsOff')
            }
            rightElement={
              <Switch 
                checked={pushSubscribed}
                onCheckedChange={handleToggleNotifications}
                disabled={isSubscribing}
                className="scale-110"
              />
            }
          />

          {/* Bildirim Onarma */}
          <SettingItem 
            icon={Wrench} 
            title={t('settings.notificationsRepair')}
            subtitle={t('settings.notificationsRepairSubtitle')}
            onClick={handleRepairNotifications}
          />
        </div>

        {/* GRUP 4: DESTEK & ÇIKIŞ */}
        <SectionTitle title={t('settings.sections.other')} />
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
          
          <SettingItem 
            icon={HelpCircle} 
            title={t('settings.helpCenter')}
            subtitle={t('settings.helpCenterSubtitle')}
            onClick={() => onNavigate && onNavigate("help-center")}
          />

          <SettingItem
            icon={Phone}
            title={t('settings.contact', 'İletişim')}
            subtitle={t('settings.contactSubtitle', 'Telefon, WhatsApp, E-posta')}
            onClick={() => setShowContact(true)}
          />

          <SettingItem 
            icon={LogOut} 
            title={t('settings.logout')}
            subtitle={t('settings.logoutSubtitle')}
            onClick={onLogout}
            isDestructive={true}
          />
        </div>

        {/* Versiyon Bilgisi */}
        <div className="mt-10 text-center pb-6">
          <div className="inline-flex items-center justify-center gap-2 px-3 py-1 rounded-full bg-zinc-100 border border-zinc-200">
             <ShieldCheck className="w-3 h-3 text-zinc-400" />
             <p className="text-xs font-medium text-zinc-500">v1.0.2 Secure Build</p>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Settings;