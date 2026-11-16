import { useState, useEffect } from "react";
import { ArrowLeft, Bell, BellOff, Wrench } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Switch } from "./ui/switch";
import LiveActivitySettings from "./LiveActivitySettings";
import { SettingItem, SectionTitle } from "./settings/SettingRows";
import { Capacitor, registerPlugin } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

const FCMTokenPlugin = Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios'
  ? registerPlugin('FCMTokenPlugin')
  : null;

const SettingsNotifications = ({ onNavigate, onOpenLiveActivityConsent }) => {
  const { t } = useTranslation();
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [permissionStatus, setPermissionStatus] = useState('default');
  const [isSubscribing, setIsSubscribing] = useState(false);

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
            <h2 className="text-xl font-black text-zinc-900">{t('settings.notificationSettings')}</h2>
            <p className="text-sm text-zinc-600 mt-1 font-medium">{t('settings.notificationSettingsSubtitle')}</p>
          </div>
        </div>
      </div>

      <div className="px-4 max-w-3xl mx-auto">
        <SectionTitle title={t('settings.notifications')} />
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

        <LiveActivitySettings onOpenConsent={onOpenLiveActivityConsent} />
      </div>
    </div>
  );
};

export default SettingsNotifications;
