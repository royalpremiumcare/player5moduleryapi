import { useState, useEffect } from "react";
import { Package, User, UserCog, Briefcase, HelpCircle, LogOut, ChevronRight, CreditCard, ArrowLeft, DollarSign, ChartBar, Bell, BellOff } from "lucide-react"; 
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

const Settings = ({ onNavigate, userRole, onLogout }) => {
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
          toast.success('Bildirimler başarıyla etkinleştirildi!');
        } else {
          setNotificationStatus('denied');
          toast.error('Bildirim izni verilmedi');
        }
      } catch (error) {
        console.error('Native Push Error:', error);
        toast.error('Bildirim etkinleştirilemedi');
      } finally {
        setIsSubscribing(false);
      }
      return;
    }
    
    // Web Push Notification
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      toast.error('Bu tarayıcı bildirimleri desteklemiyor');
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
        toast.success('Bildirimler başarıyla etkinleştirildi!');
      } else if (permission === 'denied') {
        toast.error('Bildirim izni reddedildi. Tarayıcı ayarlarından izin verin.');
      }
    } catch (error) {
      console.error('Bildirim etkinleştirme hatası:', error);
      toast.error('Bildirim etkinleştirilemedi');
    } finally {
      setIsSubscribing(false);
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
                <span className="text-sm font-medium">Anasayfaya Dön</span>
              </button>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Ayarlar</h2>
                <p className="text-sm text-gray-600 mt-1">Hesap ve sistem ayarlarınızı yönetin</p>
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
                      <p className="text-base font-semibold text-gray-900">Profilim</p>
                      <p className="text-xs text-gray-600">Kişisel bilgiler ve hesap ayarları</p>
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
                        <p className="text-base font-semibold text-gray-900">İşletme Ayarları</p>
                        <p className="text-xs text-gray-600">İşletme bilgileri ve genel ayarlar</p>
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
                        <p className="text-base font-semibold text-gray-900">Personel Yönetimi</p>
                        <p className="text-xs text-gray-600">Personel ekleme ve yönetimi</p>
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
                        <p className="text-base font-semibold text-gray-900">Hizmet Yönetimi</p>
                        <p className="text-xs text-gray-600">Hizmet ekleme ve fiyatlandırma</p>
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
                      <p className="text-base font-semibold text-gray-900">Finans & Kasa Yönetimi</p>
                      <p className="text-xs text-gray-600">Gelir, Gider ve Personel Ödemelerini Yönetin</p>
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
                        <p className="text-base font-semibold text-gray-900">Abonelik ve Faturalandırma</p>
                        <p className="text-xs text-gray-600">Paket bilgileri ve ödeme ayarları</p>
            </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>
                </>
              )}

              {/* Bildirim Ayarları */}
              <button
                onClick={handleEnableNotifications}
                disabled={isSubscribing || notificationStatus === 'granted'}
                className={`w-full flex items-center justify-between p-4 rounded-lg border transition-colors text-left ${
                  notificationStatus === 'granted' 
                    ? 'border-green-200 bg-green-50' 
                    : notificationStatus === 'denied'
                    ? 'border-yellow-200 bg-yellow-50 hover:bg-yellow-100'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    notificationStatus === 'granted' ? 'bg-green-100' : 
                    notificationStatus === 'denied' ? 'bg-yellow-100' : 'bg-gray-100'
                  }`}>
                    {notificationStatus === 'granted' ? (
                      <Bell className="w-5 h-5 text-green-600" />
                    ) : (
                      <BellOff className="w-5 h-5 text-yellow-600" />
                    )}
                  </div>
                  <div>
                    <p className="text-base font-semibold text-gray-900">
                      {isSubscribing ? 'Etkinleştiriliyor...' : 
                       notificationStatus === 'granted' ? 'Bildirimler Açık' : 
                       notificationStatus === 'denied' ? 'Bildirimleri Etkinleştir' : 
                       'Bildirimleri Etkinleştir'}
                    </p>
                    <p className="text-xs text-gray-600">
                      {notificationStatus === 'granted' 
                        ? 'Yeni randevular için bildirim alacaksınız' 
                        : notificationStatus === 'denied'
                        ? 'Tarayıcı ayarlarından izin verin'
                        : 'Yeni randevu bildirimleri almak için etkinleştirin'}
                    </p>
                  </div>
                </div>
                {notificationStatus === 'granted' ? (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">Aktif</span>
                ) : (
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                )}
              </button>

              <button
                onClick={() => onNavigate && onNavigate("help-center")}
                className="w-full flex items-center justify-between p-4 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <HelpCircle className="w-5 h-5 text-indigo-600" />
            </div>
              <div>
                    <p className="text-base font-semibold text-gray-900">Yardım Merkezi</p>
                    <p className="text-xs text-gray-600">Sık sorulan sorular ve destek</p>
            </div>
          </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </button>

              <button
                onClick={async () => {
                  try {
                    toast.info('Bildirim ayarları onarılıyor...');
                    if ('serviceWorker' in navigator) {
                      const reg = await navigator.serviceWorker.ready;
                      const sub = await reg.pushManager.getSubscription();
                      if (sub) {
                        await sub.unsubscribe();
                        console.log('Eski abonelik silindi');
                      }
                      // Sayfayı yenileyerek App.js'deki otomatik aboneliği tetikle
                      window.location.reload();
                    } else {
                      toast.error('Tarayıcınız bildirimleri desteklemiyor');
                    }
                  } catch (error) {
                    console.error('Bildirim onarım hatası:', error);
                    toast.error('Onarım başarısız oldu');
                  }
                }}
                className="w-full flex items-center justify-between p-4 rounded-lg border border-orange-200 hover:bg-orange-50 transition-colors text-left mb-3"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                    <Bell className="w-5 h-5 text-orange-600" />
                  </div>
                  <div>
                    <p className="text-base font-semibold text-orange-700">Bildirimleri Onar</p>
                    <p className="text-xs text-orange-600">Bildirim gelmiyorsa buna tıklayın</p>
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
                    <p className="text-base font-semibold text-red-600">Çıkış Yap</p>
                    <p className="text-xs text-red-500">Hesabınızdan güvenli şekilde çıkış yapın</p>
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
