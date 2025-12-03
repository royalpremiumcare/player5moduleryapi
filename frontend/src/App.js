import { useState, useEffect, useCallback, useRef } from "react";
import "@/App.css";
import api from "./api/api"; 
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useAuth } from "./context/AuthContext";
import { io } from "socket.io-client";

import Dashboard from "@/components/Dashboard";
import CalendarView from "@/components/Calendar";
import AppointmentForm from "@/components/AppointmentForm";
import AppointmentFormWizard from "@/components/AppointmentFormWizard";
import ServiceManagement from "@/components/ServiceManagement";
import CashRegister from "@/components/CashRegister";
import Settings from "@/components/Settings";
import SettingsSubscription from "@/components/SettingsSubscription";
import SettingsProfile from "@/components/SettingsProfile";
import Finance from "@/components/Finance";
import Subscribe from "@/components/Subscribe";
import Customers from "@/components/Customers";
import ImportData from "@/components/ImportData";
import StaffManagement from "@/components/StaffManagement";
import AuditLogs from "@/components/AuditLogs";
import HelpCenter from "@/components/HelpCenter";
import SuperAdmin from "@/components/SuperAdmin";
import SetupWizard from "@/components/SetupWizard";
import ChatWidget from "@/components/ChatWidget";
import { Calendar, Briefcase, DollarSign, SettingsIcon, Users, Upload, LogOut, Moon, Sun, UserCog, FileText, Home, Plus, CreditCard, User, HelpCircle, Package, Bell } from "lucide-react";
import { useTheme } from "./context/ThemeContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";


function App() {
  const { logout, userRole, token } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const bottomNavRef = useRef(null);
  
  const [currentView, setCurrentView] = useState("dashboard");
  const [services, setServices] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [settings, setSettings] = useState(null);
  const [showPaymentSuccess, setShowPaymentSuccess] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  
  // Notification states
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const notificationsRef = useRef([]);

  // App mode detection - PWA/APK olarak açıldığında is_app_mode set et
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const modeParam = urlParams.get('mode');
    
    // URL'de mode=app varsa kaydet
    if (modeParam === 'app') {
      localStorage.setItem('is_app_mode', 'true');
    }
    
    // Standalone modda açıldıysa (PWA olarak yüklendi) da app mode olarak işaretle
    if (window.matchMedia('(display-mode: standalone)').matches || 
        window.navigator.standalone === true) {
      localStorage.setItem('is_app_mode', 'true');
    }
  }, []);

  // URL routing - path'den view'ı oku ve URL değişikliklerini dinle
  useEffect(() => {
    const handleRouteChange = () => {
      const path = window.location.pathname;
      const hash = window.location.hash;
      const urlParams = new URLSearchParams(window.location.search);
      const paymentStatus = urlParams.get('payment');
      
      console.log('🔍 URL Changed:', { path, hash, userRole, paymentStatus });
      
      // Hash routing ile PayTR dönüşü (authentication korunur)
      if (hash === '#/payment-success' && userRole === 'admin') {
        console.log('✅ Payment successful via hash routing');
        setCurrentView('dashboard');
        setShowForm(false);
        setShowPaymentSuccess(true);
        toast.success('🎉 Ödeme başarıyla tamamlandı! Aboneliğiniz aktif edildi.', {
          duration: 8000,
          position: 'top-center',
          className: 'text-lg font-bold',
        });
        // Hash'i temizle
        window.location.hash = '';
        // Banner'ı 10 saniye sonra kapat
        setTimeout(() => setShowPaymentSuccess(false), 10000);
      } else if (hash === '#/payment-failed') {
        console.log('❌ Payment failed via hash routing');
        setCurrentView('subscribe');
        setShowForm(false);
        toast.error('Ödeme işlemi başarısız oldu. Lütfen tekrar deneyin.', {
          duration: 5000,
        });
        // Hash'i temizle
        window.location.hash = '';
      }
      // /subscribe path kontrolü (PayTR eski URL'lerle döndüğünde)
      else if (path === '/subscribe') {
        const status = urlParams.get('status');
        console.log('🔍 /subscribe path detected, status:', status);
        
        if (status === 'success' && userRole === 'admin') {
          console.log('✅ Payment successful via /subscribe path');
          // Kullanıcıyı login sayfasına değil, ana sayfaya yönlendir
          window.location.href = '/?payment=success';
        } else if (status === 'failed') {
          console.log('❌ Payment failed via /subscribe path');
          window.location.href = '/?payment=failed';
        } else if (userRole === 'admin') {
          // Normal subscribe sayfası
          setCurrentView('subscribe');
          setShowForm(false);
        }
      }
      // Query string ile PayTR dönüşü (fallback)
      else if (paymentStatus === 'success' && userRole === 'admin') {
        console.log('✅ Payment successful via query string');
        setCurrentView('dashboard');
        setShowForm(false);
        setShowPaymentSuccess(true);
        toast.success('🎉 Ödeme başarıyla tamamlandı! Aboneliğiniz aktif edildi.', {
          duration: 8000,
          position: 'top-center',
          className: 'text-lg font-bold',
        });
        // URL'den parametreyi temizle
        window.history.replaceState({}, '', '/');
        // Banner'ı 10 saniye sonra kapat
        setTimeout(() => setShowPaymentSuccess(false), 10000);
      } else if (paymentStatus === 'failed') {
        console.log('❌ Payment failed via query string');
        setCurrentView('subscribe');
        setShowForm(false);
        toast.error('Ödeme işlemi başarısız oldu. Lütfen tekrar deneyin.', {
          duration: 5000,
        });
        // URL'den parametreyi temizle
        window.history.replaceState({}, '', '/');
      } else if (path === '/superadmin' && userRole === 'superadmin') {
        console.log('✅ Setting view to superadmin');
        setCurrentView('superadmin');
        setShowForm(false);
      }
    };

    // İlk yükleme
    handleRouteChange();

    // URL değişikliklerini dinle (browser back/forward buttons & hash changes)
    window.addEventListener('popstate', handleRouteChange);
    window.addEventListener('hashchange', handleRouteChange);
    
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
      window.removeEventListener('hashchange', handleRouteChange);
    };
  }, [userRole]);

  // Define load functions before useEffect hooks
  const loadSettings = useCallback(async () => {
    try {
      const response = await api.get("/settings");
      setSettings(response.data);
    } catch (error) {
      console.error("Settings yüklenemedi:", error);
    }
  }, []);

  // Check if user needs onboarding
  const checkOnboarding = useCallback(async () => {
    if (userRole === 'admin') {
      try {
        const response = await api.get("/users");
        const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
        if (authToken) {
          const payload = JSON.parse(atob(authToken.split('.')[1]));
          const username = payload.sub;
          const user = response.data?.find(u => u.username === username);
          
          if (user) {
            setCurrentUser(user);
            // Admin ve onboarding tamamlanmamışsa sihirbazı göster
            if (user.role === 'admin' && !user.onboarding_completed) {
              setShowOnboarding(true);
            }
          }
        }
      } catch (error) {
        console.error("Onboarding kontrolü yapılamadı:", error);
      }
    }
  }, [userRole, token]);

  const loadServices = useCallback(async () => {
    try {
      const response = await api.get("/services"); 
      setServices(response.data);
    } catch (error) {
      toast.error("Hizmetler yüklenemedi");
    }
  }, []);

  const loadAppointments = useCallback(async () => {
    try {
      const response = await api.get("/appointments"); 
      const allAppointments = response.data || [];
      setAppointments(allAppointments);
      
      // 'Bekliyor' durumundaki randevuları bildirim olarak ekle
      // Sadece son 24 saatte oluşturulanları veya ileri tarihli olanları alabiliriz
      // Şimdilik tüm 'Bekliyor' randevularını alalım
      const pendingAppointments = allAppointments.filter(appt => appt.status === 'Bekliyor');
      
      // Okunmuş bildirimleri localStorage'dan al
      const readNotificationIds = JSON.parse(localStorage.getItem('readNotificationIds') || '[]');
      
      // Bildirim formatına dönüştür - okunmuş durumu localStorage'dan kontrol et
      setNotifications(pendingAppointments.map(appt => ({
        id: appt.id, // Unique ID kullan
        read: readNotificationIds.includes(appt.id), // localStorage'dan kontrol et
        type: 'new_appointment',
        title: 'Yeni Randevu',
        message: `${appt.customer_name} - ${appt.service_name}`,
        details: `${appt.appointment_date} ${appt.appointment_time}`,
        time: appt.created_at || new Date().toISOString()
      })));

      console.log("✅ Randevular yüklendi:", allAppointments.length, "randevu");
      if (pendingAppointments.length > 0) {
        console.log("🔔 Bekleyen randevular bildirime eklendi:", pendingAppointments.length);
      }
    } catch (error) {
      console.error("❌ Randevular yüklenemedi:", error);
      toast.error("Randevular yüklenemedi");
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const response = await api.get("/stats/dashboard"); 
      setStats(response.data);
    } catch (error) {
      console.error("İstatistikler yüklenemedi:", error);
    }
  }, []);

  useEffect(() => {
    loadServices();
    loadAppointments();
    loadSettings();
    checkOnboarding();
    if (userRole === 'admin') {
      loadStats();
    }
  }, [userRole, loadServices, loadAppointments, loadSettings, loadStats, checkOnboarding]); 

  // Push Notification Subscription
  const subscribeToPush = useCallback(async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.log('Push notifications not supported');
      return;
    }
    
    try {
      // Mevcut izni kontrol et
      const currentPermission = Notification.permission;
      console.log('📱 Current notification permission:', currentPermission);
      
      // Eğer izin zaten reddedilmişse, tekrar sormayalım
      if (currentPermission === 'denied') {
        console.log('❌ Notification permission was previously denied');
        return; // Sessizce çık, toast gösterme
      }
      
      // Bildirim izni iste (sadece 'default' durumunda sorar)
      const permission = await Notification.requestPermission();
      console.log('📱 Requested notification permission:', permission);
      
      if (permission !== 'granted') {
        console.log('❌ Notification permission denied');
        // Sadece kullanıcı aktif olarak reddettiyse uyar
        if (currentPermission === 'default') {
          toast.info('Bildirim izni verilmedi. Bildirimleri açmak için tarayıcı ayarlarından izin verin.', { duration: 5000 });
        }
        return;
      }
      
      // Service worker'ı al
      const registration = await navigator.serviceWorker.ready;
      
      // VAPID public key al
      const vapidResponse = await api.get('/push/vapid-key');
      const vapidPublicKey = vapidResponse.data.publicKey;
      
      // URL-safe base64'ü Uint8Array'e çevir
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
      
      // Push subscription oluştur
      let subscription = await registration.pushManager.getSubscription();
      
      // Mevcut abonelik varsa key kontrolü yap
      if (subscription) {
        const newKey = urlBase64ToUint8Array(vapidPublicKey);
        const currentKeyBuffer = subscription.options.applicationServerKey;
        
        let keysMatch = false;
        if (currentKeyBuffer) {
          const currentKey = new Uint8Array(currentKeyBuffer);
          if (currentKey.length === newKey.length) {
            keysMatch = true;
            for(let i=0; i<currentKey.length; i++) {
              if(currentKey[i] !== newKey[i]) {
                keysMatch = false;
                break;
              }
            }
          }
        }

        if (!keysMatch) {
          console.warn('⚠️ Existing subscription has different key. Unsubscribing...');
          await subscription.unsubscribe();
          subscription = null;
        }
      }

      if (!subscription) {
        try {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
          });
        } catch (subError) {
           // InvalidStateError durumunda bir kez daha unsubscribe deneyelim
           if (subError.name === 'InvalidStateError') {
             const existing = await registration.pushManager.getSubscription();
             if (existing) await existing.unsubscribe();
             subscription = await registration.pushManager.subscribe({
               userVisibleOnly: true,
               applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
             });
           } else {
             throw subError;
           }
        }
      }
      
      // Backend'e gönder
      await api.post('/push/subscribe', {
        subscription: subscription.toJSON()
      });
      
      setPushSubscribed(true);
      console.log('✅ Push notification subscription successful');
      
    } catch (error) {
      console.error('Push subscription error:', error);
    }
  }, []);
  
  // Token değiştiğinde push subscribe ol
  useEffect(() => {
    if (token && !pushSubscribed) {
      // Küçük bir gecikme ile subscribe ol (SW hazır olsun)
      const timer = setTimeout(() => {
        subscribeToPush();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [token, pushSubscribed, subscribeToPush]);

  // WebSocket setup for real-time updates
  const socketRef = useRef(null);
  const listenersInitializedRef = useRef(false);
  const userRoleRef = useRef(userRole);
  const currentUserRef = useRef(currentUser);
  const loadAppointmentsRef = useRef(loadAppointments);
  const loadStatsRef = useRef(loadStats);
  
  // Keep refs in sync with current functions
  useEffect(() => {
    userRoleRef.current = userRole;
    currentUserRef.current = currentUser;
    loadAppointmentsRef.current = loadAppointments;
    loadStatsRef.current = loadStats;
  }, [userRole, currentUser, loadAppointments, loadStats]);
  
  // Initialize socket only once on mount
  useEffect(() => {
    if (!socketRef.current) {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const socketUrl = BACKEND_URL || window.location.origin;
      const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      
      // Initialize Socket.IO connection
      const socket = io(socketUrl, {
        path: '/api/socket.io',
        transports: ['websocket', 'polling'],
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        autoConnect: true,
        auth: {
          token: authToken || ''
        }
      });
      
      socketRef.current = socket;
      
      const handleConnect = () => {
        // Get organization_id from token
        const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
        if (authToken) {
          try {
            const payload = JSON.parse(atob(authToken.split('.')[1]));
            const organizationId = payload.org_id;
            if (organizationId) {
              socket.emit('join_organization', { organization_id: organizationId });
            }
          } catch (error) {
            // Token parse error - silent
          }
        }
      };
      
      // Set up event listeners immediately
      socket.on('connect', handleConnect);
      
      // If socket is already connected, join immediately
      if (socket.connected) {
        handleConnect();
      }
      
      socket.on('disconnect', () => {});
      socket.on('connect_error', () => {});
      socket.on('connection_established', () => {});
      socket.on('joined_organization', () => {});
      
      // Real-time appointment events - use refs to get current function values
      socket.on('appointment_created', (data) => {
        console.log("🔔 WebSocket: appointment_created event received", data);
        
        // Sadece public booking'den gelen randevular için in-app bildirim göster
        const appointment = data?.appointment;
        const user = currentUserRef.current;
        
        // Personel ise sadece kendi randevuları için bildirim göster
        if (user?.role === 'staff' && appointment?.staff_member_id !== user?.username) {
          console.log("🔕 Bildirim gösterilmedi - başka personelin randevusu");
          return;
        }
        
        if (appointment?.source === 'public_booking') {
          // In-app notification ekle
          const newNotification = {
            id: Date.now(),
            type: 'new_appointment',
            title: '🔔 Yeni Online Randevu!',
            message: `${appointment.customer_name} - ${appointment.service_name}`,
            details: `${appointment.appointment_date} ${appointment.appointment_time}`,
            time: new Date(),
            read: false,
            appointmentId: appointment.id
          };
          
          // notificationsRef kullanarak güncelle (closure sorunu için)
          if (typeof setNotifications === 'function') {
            setNotifications(prev => {
              const updated = [newNotification, ...prev].slice(0, 20);
              return updated;
            });
          }
          
        }
        
        if (loadAppointmentsRef.current) {
          console.log("🔄 Loading appointments...");
          loadAppointmentsRef.current();
        }
        if (userRoleRef.current === 'admin' && loadStatsRef.current) {
          loadStatsRef.current();
        }
      });
      
      socket.on('appointment_updated', () => {
        if (loadAppointmentsRef.current) {
          loadAppointmentsRef.current();
        }
        if (userRoleRef.current === 'admin' && loadStatsRef.current) {
          loadStatsRef.current();
        }
      });
      
      socket.on('appointment_deleted', () => {
        if (loadAppointmentsRef.current) {
          loadAppointmentsRef.current();
        }
        if (userRoleRef.current === 'admin' && loadStatsRef.current) {
          loadStatsRef.current();
        }
      });
      
      listenersInitializedRef.current = true;
    }
    
    // No cleanup - socket persists for component lifetime
  }, []); // Empty dependency array - only run once on mount
  
  // Re-join organization when token changes
  useEffect(() => {
    if (socketRef.current && socketRef.current.connected && token) {
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          const organizationId = payload.org_id;
          if (organizationId) {
            socketRef.current.emit('join_organization', { organization_id: organizationId });
          }
        } catch (error) {
        // Token parse error - silent
      }
    }
  }, [token]);
  
  // Fallback: visibility and focus events for when user returns to tab
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadAppointments();
        if (userRoleRef.current === 'admin') {
          loadStats();
        }
      }
    };
    
    const handleFocus = () => {
      loadAppointments();
      if (userRoleRef.current === 'admin') {
        loadStats();
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [loadAppointments, loadStats]);
  
  // DON'T cleanup socket - let it persist for the entire app lifetime
  // Socket will automatically cleanup when browser tab closes
  // Cleanup was causing socket to disconnect unnecessarily

  // iOS Chrome için alt navigasyon barı sabitleme
  useEffect(() => {
    const isIOSChrome = /CriOS/i.test(navigator.userAgent);
    if (!isIOSChrome || !bottomNavRef.current) return;

    const bottomNav = bottomNavRef.current;
    
    const handleScroll = () => {
      // Alt navigasyon barını her zaman en altta tut
      if (bottomNav) {
        bottomNav.style.position = 'fixed';
        bottomNav.style.bottom = '0';
        bottomNav.style.left = '0';
        bottomNav.style.right = '0';
        bottomNav.style.transform = 'translateZ(0)';
        bottomNav.style.webkitTransform = 'translateZ(0)';
      }
    };

    const handleResize = () => {
      handleScroll();
    };

    // İlk yüklemede ve scroll/resize event'lerinde çalıştır
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize, { passive: true });
    window.addEventListener('orientationchange', handleResize, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
    };
  }, [currentView, showForm]);

  const handleAppointmentSaved = async () => {
    console.log("🔄 handleAppointmentSaved called - refreshing appointments...");
    await loadAppointments();
    if (userRole === 'admin') {
      await loadStats();
    }
    setShowForm(false);
    setSelectedAppointment(null);
    console.log("✅ Appointments refreshed, form closed");
  };
  const handleEditAppointment = (appointment) => {
    setSelectedAppointment(appointment);
    setShowForm(true);
  };
  const handleNewAppointment = () => {
    setSelectedAppointment(null);
    setShowForm(true);
  };


  return (
    <div className="App min-h-screen bg-white dark:bg-gray-900 transition-colors">
      <Toaster position="top-center" richColors />

      {/* Setup Wizard - Onboarding */}
      {showOnboarding && (
        <SetupWizard
          onComplete={() => {
            setShowOnboarding(false);
            // Verileri yeniden yükle
            loadServices();
            loadAppointments();
            loadSettings();
            if (userRole === 'admin') {
              loadStats();
            }
          }}
        />
      )}

      {/* TopBar - Üst Navigasyon Barı */}
      {!showForm && (
        <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm" style={{ fontFamily: 'Inter, sans-serif' }}>
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              {/* Sol Bölüm: PLANN Logosu */}
              <div className="flex-shrink-0">
                <h1 className="text-xl font-bold text-gray-900" style={{ fontFamily: 'Inter, sans-serif' }}>
                  PLANN
                </h1>
              </div>

              {/* Orta Bölüm: İşletme Adı */}
              <div className="flex-1 flex justify-center px-4 min-w-0">
                <h2 className="text-lg font-semibold text-gray-800 truncate max-w-full text-center">
                  {settings?.company_name || "İşletme Adı"}
                </h2>
              </div>

              {/* Sağ Bölüm: SuperAdmin + Bildirim Zili */}
              <div className="flex-shrink-0 flex items-center gap-2">
                {userRole === 'superadmin' && (
                  <button
                    onClick={() => {
                      setCurrentView('superadmin');
                      setShowForm(false);
                      window.history.pushState({}, '', '/superadmin');
                    }}
                    className="p-2 hover:bg-blue-100 rounded-lg transition-colors"
                    title="SuperAdmin Panel"
                  >
                    <UserCog className="w-6 h-6 text-blue-600" />
                  </button>
                )}
                <DropdownMenu open={showNotifications} onOpenChange={setShowNotifications}>
                  <DropdownMenuTrigger asChild>
                    <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors relative">
                      <Bell className="w-6 h-6 text-gray-700" />
                      {notifications.filter(n => !n.read).length > 0 && (
                        <span className="absolute -top-1 -right-1 min-w-[20px] h-5 bg-red-500 rounded-full text-white text-xs flex items-center justify-center font-bold px-1">
                          {notifications.filter(n => !n.read).length > 9 ? '9+' : notifications.filter(n => !n.read).length}
                        </span>
                      )}
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-y-auto">
                    <div className="p-3 font-semibold border-b flex items-center justify-between">
                      <span>Bildirimler</span>
                      {notifications.length > 0 && (
                        <button 
                          onClick={() => {
                            // Tüm bildirimleri okundu olarak işaretle
                            setNotifications(prev => prev.map(n => ({...n, read: true})));
                            // localStorage'a kaydet
                            const allIds = notifications.map(n => n.id);
                            const existingIds = JSON.parse(localStorage.getItem('readNotificationIds') || '[]');
                            const mergedIds = [...new Set([...existingIds, ...allIds])];
                            localStorage.setItem('readNotificationIds', JSON.stringify(mergedIds));
                          }}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Tümünü okundu işaretle
                        </button>
                      )}
                    </div>
                    {notifications.length === 0 ? (
                      <div className="p-6 text-center text-gray-500">
                        <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                        <p>Henüz bildirim yok</p>
                        <p className="text-xs mt-1">Online randevular burada görünecek</p>
                      </div>
                    ) : (
                      notifications.map(notification => (
                        <DropdownMenuItem 
                          key={notification.id} 
                          className={`flex flex-col items-start p-3 cursor-pointer border-b last:border-b-0 ${!notification.read ? 'bg-blue-50' : ''}`}
                          onClick={() => {
                            setNotifications(prev => prev.map(n => 
                              n.id === notification.id ? {...n, read: true} : n
                            ));
                            setShowNotifications(false);
                          }}
                        >
                          <div className="flex items-start gap-2 w-full">
                            <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${!notification.read ? 'bg-blue-500' : 'bg-gray-300'}`} />
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm">{notification.title}</p>
                              <p className="text-sm text-gray-600 truncate">{notification.message}</p>
                              {notification.details && (
                                <p className="text-xs text-gray-500 mt-0.5">{notification.details}</p>
                              )}
                              <p className="text-xs text-gray-400 mt-1">
                                {new Date(notification.time).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </div>
                          </div>
                        </DropdownMenuItem>
                      ))
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </header>
      )}

      <main className={(currentView === "dashboard" || currentView === "settings" || currentView === "settings-subscription" || currentView === "settings-profile" || currentView === "subscribe" || currentView === "staff" || currentView === "services" || currentView === "help-center") && !showForm ? "" : "container mx-auto px-4 py-6"}>
        {/* Ödeme Başarı Banner'ı */}
        {showPaymentSuccess && (
          <div className="bg-gradient-to-r from-green-500 to-emerald-600 text-white px-4 py-6 shadow-lg sticky top-0 z-50 animate-in slide-in-from-top">
            <div className="container mx-auto flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="bg-white/20 p-3 rounded-full">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xl font-bold mb-1">🎉 Ödeme Başarılı!</h3>
                  <p className="text-green-50">Aboneliğiniz başarıyla aktif edildi. Artık tüm özelliklere erişebilirsiniz.</p>
                </div>
              </div>
              <button
                onClick={() => setShowPaymentSuccess(false)}
                className="text-white/80 hover:text-white p-2 rounded-lg hover:bg-white/10 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}
        
        {currentView === "dashboard" && !showForm && (
          <Dashboard
            appointments={appointments}
            stats={stats}
            userRole={userRole}
            onEditAppointment={handleEditAppointment}
            onNewAppointment={handleNewAppointment}
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
            onRefresh={async () => {
              await loadAppointments();
              if (userRole === 'admin') {
                await loadStats();
              }
            }}
          />
        )}

        {showForm && (
          <AppointmentFormWizard
            services={services}
            appointment={selectedAppointment}
            onSave={handleAppointmentSaved}
            onCancel={() => {
              setShowForm(false);
              setSelectedAppointment(null);
            }}
          />
        )}

        {currentView === "calendar" && (
          <CalendarView
            onEditAppointment={(apt) => {
              setSelectedAppointment(apt);
              setShowForm(true);
              setCurrentView("dashboard");
            }}
            onNewAppointment={handleNewAppointment}
          />
        )}
        {currentView === "customers" && (
          <Customers 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
            onNewAppointment={() => {
              setCurrentView("dashboard");
              setShowForm(true);
              setSelectedAppointment(null);
            }}
          />
        )}
        {currentView === "services" && userRole === 'admin' && (
          <ServiceManagement 
            services={services} 
            onRefresh={loadServices}
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "staff" && userRole === 'admin' && (
          <StaffManagement 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
            currentUser={currentUser}
          />
        )}
        {currentView === "cash" && userRole === 'admin' && ( <CashRegister /> )}
        {currentView === "audit" && userRole === 'admin' && ( <AuditLogs /> )}
        {currentView === "import" && userRole === 'admin' && (
          <ImportData
            onImportComplete={() => {
              loadAppointments();
              loadStats();
              toast.success("Veriler yüklendi! Randevular sayfasını kontrol edin.");
            }}
          />
        )}
        {currentView === "settings" && (
          <Settings 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
            userRole={userRole}
            onLogout={logout}
          />
        )}
        {currentView === "settings-subscription" && userRole === 'admin' && (
          <SettingsSubscription 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "settings-profile" && (
          <SettingsProfile 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "settings-finance" && userRole === 'admin' && (
          <Finance 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "subscribe" && userRole === 'admin' && (
          <Subscribe 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "help-center" && (
          <HelpCenter 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "superadmin" && userRole === 'superadmin' && (
          <SuperAdmin 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
              // Dashboard'a dönünce URL'yi temizle
              if (view === 'dashboard') {
                window.history.pushState({}, '', '/');
              }
            }}
          />
        )}
      </main>

      {/* Alt Navigasyon Barı (Dashboard ve Calendar görünümlerinde) */}
      {(currentView === "dashboard" || currentView === "calendar") && !showForm && (
        <div 
          ref={bottomNavRef}
          className="bg-white border-t border-gray-200 shadow-lg bottom-nav-fixed" 
          style={{ 
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 1000,
            width: '100%',
            maxWidth: '100vw',
            WebkitTransform: 'translateZ(0)',
            transform: 'translateZ(0)',
            WebkitBackfaceVisibility: 'hidden',
            backfaceVisibility: 'hidden',
            WebkitTransition: 'none',
            transition: 'none'
          }}
        >
          <div className="flex items-center justify-around px-2 py-2">
            {/* Anasayfa */}
            <button
              onClick={() => {
                setCurrentView("dashboard");
                setShowForm(false);
              }}
              className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors text-blue-600"
            >
              <Home className="w-5 h-5" />
              <span className="text-xs font-medium">Anasayfa</span>
            </button>

            {/* Takvim */}
            <button
              onClick={() => {
                setCurrentView("calendar");
                setShowForm(false);
              }}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                currentView === "calendar" ? "text-blue-600" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <Calendar className="w-5 h-5" />
              <span className="text-xs font-medium">Takvim</span>
            </button>

            {/* Yeni Randevu Ekle (Ana Renk - Mavi) */}
            <button
              onClick={handleNewAppointment}
              className="flex items-center justify-center w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors -mt-4"
            >
              <Plus className="w-6 h-6" />
            </button>

            {/* Müşteriler */}
            <button
              onClick={() => {
                setCurrentView("customers");
                setShowForm(false);
              }}
              className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors text-gray-600 hover:text-gray-900"
            >
              <Users className="w-5 h-5" />
              <span className="text-xs font-medium">Müşteriler</span>
            </button>

            {/* Ayarlar */}
            <button
              onClick={() => {
                setCurrentView("settings");
                setShowForm(false);
              }}
              className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors text-gray-600 hover:text-gray-900"
            >
              <SettingsIcon className="w-5 h-5" />
              <span className="text-xs font-medium">Ayarlar</span>
            </button>
          </div>
        </div>
      )}

      {/* AI Chatbot Widget - Sadece giriş yapmış kullanıcılara göster */}
      {token && currentUser && (
        <ChatWidget user={{
          username: currentUser.username,
          full_name: currentUser.full_name,
          role: userRole
        }} />
      )}
    </div>
  );
}

export default App;
