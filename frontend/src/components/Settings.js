import { useState, useEffect } from "react";
import { Package, User, UserCog, Briefcase, HelpCircle, LogOut, ChevronRight, CreditCard, ArrowLeft, DollarSign, ChartBar, Bell, BellOff } from "lucide-react"; 
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

const Settings = ({ onNavigate, userRole, onLogout }) => {
  const { t } = useTranslation();
  const [notificationStatus, setNotificationStatus] = useState('default');
  const [isSubscribing, setIsSubscribing] = useState(false);

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
    
    // Native (Android/iOS) Push Notification
    if (isNative) {
      setIsSubscribing(true);
      try {
        const permStatus = await PushNotifications.requestPermissions();
        
        if (permStatus.receive === 'granted') {
          await PushNotifications.register();
          
          // Token dinleyicisi
          PushNotifications.addListener('registration', async (token) => {
            console.log('📱 Native Push Token:', token.value);
            await api.post('/push/subscribe', {
              subscription: {
                endpoint: token.value,
                keys: { p256dh: '', auth: '' },
                platform: Capacitor.getPlatform()
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
        console.error('Native Push Error:', error);
        toast.error(t('settings.notificationsEnableError'));
      } finally {
        setIsSubscribing(false);
      }
      return;
    }
    
    // Web Push Notification
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      toast.error(t('settings.notificationsBrowserNotSupported'));
      return;
    }

    setIsSubscribing(true);
    try {
      const permission = await Notification.requestPermission();
      setNotificationStatus(permission);
      
      if (permission === 'granted') {
        // Service worker'ı al ve subscribe ol
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
      console.error('Bildirim etkinleştirme hatası:', error);
      toast.error(t('settings.notificationsEnableError'));
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleDisableNotifications = async () => {
    setIsSubscribing(true);
    try {
      // Backend'den subscription'ı sil
      await api.delete('/push/unsubscribe');
      setNotificationStatus('default');
      toast.success(t('settings.notificationsDisabledSuccess'));
    } catch (error) {
      console.error('Bildirim kapatma hatası:', error);
      toast.error(t('settings.notificationsDisableError'));
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleToggleNotifications = async (checked) => {
    if (checked) {
      await handleEnableNotifications();
    } else {
      await handleDisableNotifications();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
      <div className="px-4 pt-6 pb-4">
        <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
        <div className="space-y-4">
            <div className="mb-4">
              <button
                onClick={() => onNavigate && onNavigate("dashboard")}
                className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="text-sm font-medium">{t('settings.backToHome')}</span>
              </button>
              <div>
                <h2 className="text-lg font-bold text-gray-900">{t('settings.title')}</h2>
                <p className="text-sm text-gray-600 mt-1">{t('settings.subtitle')}</p>
              </div>
            </div>

            <div className="space-y-2">
              {/* Personel için sadece Profilim göster */}
              {userRole === 'staff' && (
                <button
                  onClick={() => onNavigate && onNavigate("settings-profile")}
                  className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                      <User className="w-5 h-5 text-green-600" />
              </div>
              <div>
                      <p className="text-base font-semibold text-gray-900">{t('settings.profile')}</p>
                      <p className="text-xs text-gray-600">{t('settings.profileDescription')}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </button>
              )}

              {/* Admin için tüm ayarlar */}
              {userRole === 'admin' && (
                <>
                  {/* 1. İşletme Ayarları */}
                  <button
                    onClick={() => onNavigate && onNavigate("settings-profile")}
                    className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                        <User className="w-5 h-5 text-green-600" />
                      </div>
                      <div>
                        <p className="text-base font-semibold text-gray-900">{t('settings.business')}</p>
                        <p className="text-xs text-gray-600">{t('settings.businessDescription')}</p>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>

                  {/* 2. Personel Yönetimi */}
                  <button
                    onClick={() => onNavigate && onNavigate("staff")}
                    className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                        <UserCog className="w-5 h-5 text-purple-600" />
                </div>
                      <div>
                        <p className="text-base font-semibold text-gray-900">{t('settings.staffManagement')}</p>
                        <p className="text-xs text-gray-600">{t('settings.staffManagementDescription')}</p>
              </div>
            </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>

                  {/* 3. Hizmet Yönetimi */}
                  <button
                    onClick={() => onNavigate && onNavigate("services")}
                    className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                        <Briefcase className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                        <p className="text-base font-semibold text-gray-900">{t('settings.serviceManagement')}</p>
                        <p className="text-xs text-gray-600">{t('settings.serviceManagementDescription')}</p>
              </div>
            </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>

                  {/* 4. Finans & Kasa Yönetimi */}
                  <button
                    onClick={() => onNavigate && onNavigate("settings-finance")}
                    className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <DollarSign className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-base font-semibold text-gray-900">{t('settings.financeManagement')}</p>
                      <p className="text-xs text-gray-600">{t('settings.financeManagementDescription')}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </button>

                  {/* 5. Abonelik ve Faturalandırma */}
                  <button
                    onClick={() => onNavigate && onNavigate("settings-subscription")}
                    className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Package className="w-5 h-5 text-blue-600" />
              </div>
                      <div>
                        <p className="text-base font-semibold text-gray-900">{t('settings.subscription')}</p>
                        <p className="text-xs text-gray-600">{t('settings.subscriptionDescription')}</p>
            </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>
                </>
              )}

              {/* Bildirim Ayarları - Switch */}
              <div className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 bg-white">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    notificationStatus === 'granted' ? 'bg-green-100' : 'bg-gray-100'
                  }`}>
                    {notificationStatus === 'granted' ? (
                      <Bell className="w-5 h-5 text-green-600" />
                    ) : (
                      <BellOff className="w-5 h-5 text-gray-500" />
                    )}
                  </div>
                  <div>
                    <p className="text-base font-semibold text-gray-900">{t('settings.notifications')}</p>
                    <p className="text-xs text-gray-600">
                      {notificationStatus === 'granted' 
                        ? t('settings.notificationsEnabled')
                        : t('settings.notificationsDisabled')}
                    </p>
                  </div>
                </div>
                <Switch 
                  checked={notificationStatus === 'granted'}
                  onCheckedChange={handleToggleNotifications}
                  disabled={isSubscribing}
                />
              </div>

              <button
                onClick={() => onNavigate && onNavigate("help-center")}
                className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <HelpCircle className="w-5 h-5 text-indigo-600" />
            </div>
              <div>
                    <p className="text-base font-semibold text-gray-900">{t('settings.helpCenter')}</p>
                    <p className="text-xs text-gray-600">{t('settings.helpCenterDescription')}</p>
            </div>
          </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </button>

              <button
                onClick={async () => {
                  try {
                    toast.info(t('settings.notificationsRepairing'));
                    const isNative = Capacitor.isNativePlatform();
                    
                    if (isNative) {
                      // Native için: İzin iste ve yeniden kayıt ol
                      const permStatus = await PushNotifications.requestPermissions();
                      if (permStatus.receive === 'granted') {
                        await PushNotifications.register();
                        
                        PushNotifications.addListener('registration', async (token) => {
                          console.log('📱 Native Push Token (repair):', token.value);
                          await api.post('/push/subscribe', {
                            subscription: {
                              endpoint: token.value,
                              keys: { p256dh: '', auth: '' },
                              platform: Capacitor.getPlatform()
                            }
                          });
                          toast.success(t('settings.notificationsRepaired'));
                        });
                      } else {
                        toast.error(t('settings.notificationsPermissionDenied'));
                      }
                    } else if ('serviceWorker' in navigator) {
                      const reg = await navigator.serviceWorker.ready;
                      const sub = await reg.pushManager.getSubscription();
                      if (sub) {
                        await sub.unsubscribe();
                        console.log('Eski abonelik silindi');
                      }
                      // Sayfayı yenileyerek App.js'deki otomatik aboneliği tetikle
                      window.location.reload();
                    } else {
                      toast.error(t('settings.notificationsBrowserNotSupportedRepair'));
                    }
                  } catch (error) {
                    console.error('Bildirim onarım hatası:', error);
                    toast.error(t('settings.notificationsRepairError'));
                  }
                }}
                className="w-full flex items-center justify-between p-4 rounded-lg border border-orange-200 hover:bg-orange-50 transition-colors text-left mb-3"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                    <Bell className="w-5 h-5 text-orange-600" />
                  </div>
                  <div>
                    <p className="text-base font-semibold text-orange-700">{t('settings.notificationsRepair')}</p>
                    <p className="text-xs text-orange-600">{t('settings.notificationsRepairDescription')}</p>
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-orange-400" />
              </button>

              <button
                onClick={onLogout}
                className="w-full flex items-center justify-between p-4 rounded-lg border border-red-200 hover:bg-red-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                    <LogOut className="w-5 h-5 text-red-600" />
              </div>
              <div>
                    <p className="text-base font-semibold text-red-600">{t('settings.logout')}</p>
                    <p className="text-xs text-red-500">{t('settings.logoutDescription')}</p>
              </div>
            </div>
                <ChevronRight className="w-5 h-5 text-red-400" />
              </button>
            </div>
          </div>
      </Card>
      </div>
    </div>
  );
};

export default Settings;
