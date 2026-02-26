import { useState, useEffect } from "react";
import { 
  Package, User, UserCog, Briefcase, HelpCircle, LogOut, ChevronRight, 
  ArrowLeft, DollarSign, Bell, BellOff, MapPin, Wrench, ShieldCheck, Globe
} from "lucide-react"; 
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
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
  const [notificationStatus, setNotificationStatus] = useState('default');
  const [isSubscribing, setIsSubscribing] = useState(false);

  // --- BİLDİRİM MANTIĞI ---
  useEffect(() => {
    const checkNotificationStatus = async () => {
      const isNative = Capacitor.isNativePlatform();
      if (isNative) {
        try {
          const status = await PushNotifications.checkPermissions();
          setNotificationStatus(status.receive);
        } catch {
          setNotificationStatus('default');
        }
      } else if ('Notification' in window) {
        setNotificationStatus(Notification.permission);
      }
    };
    checkNotificationStatus();
  }, []);

  const handleEnableNotifications = async () => {
    const isNative = Capacitor.isNativePlatform();
    
    // Native (Android/iOS)
    if (isNative) {
      setIsSubscribing(true);
      try {
        const permStatus = await PushNotifications.requestPermissions();
        if (permStatus.receive === 'granted') {
          await PushNotifications.register();
          PushNotifications.addListener('registration', async (token) => {
            let pushToken = token.value;
            const platform = Capacitor.getPlatform();

            // iOS: APNs token yerine FCM token al
            if (platform === 'ios' && FCMTokenPlugin) {
              try {
                const fcmResult = await FCMTokenPlugin.getToken();
                if (fcmResult && fcmResult.token) {
                  pushToken = fcmResult.token;
                }
              } catch (fcmError) {
                console.error('FCM token error:', fcmError);
              }
            }

            await api.post('/push/subscribe', {
              subscription: {
                endpoint: pushToken,
                keys: { p256dh: '', auth: '' },
                platform: platform
              }
            });
          });
          setNotificationStatus('granted');
          toast.success(t('settings.notificationsEnabledSuccess'));
        } else {
          setNotificationStatus('denied');
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
      setNotificationStatus(permission);
      
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
      setNotificationStatus('default');
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
          </>
        )}

        {/* GRUP 3: UYGULAMA AYARLARI */}
        <SectionTitle title={t('settings.sections.appPreferences')} />
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
          
          {/* Bildirimler (Switch) */}
          <SettingItem 
            icon={notificationStatus === 'granted' ? Bell : BellOff} 
            title={t('settings.notifications')}
            subtitle={notificationStatus === 'granted' ? t('settings.notificationsOn') : t('settings.notificationsOff')}
            rightElement={
              <Switch 
                checked={notificationStatus === 'granted'}
                onCheckedChange={handleToggleNotifications}
                disabled={isSubscribing}
                className="scale-110" // Switch'i biraz büyüttük
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