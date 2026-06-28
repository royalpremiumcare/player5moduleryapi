import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useLocation } from "react-router-dom";
import "@/App.css";
import api from "./api/api"; 
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useAuth } from "./context/AuthContext";
import { io } from "socket.io-client";
import { Capacitor, registerPlugin } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { StatusBar, Style } from '@capacitor/status-bar';

import Dashboard from "@/components/Dashboard";
import CalendarView from "@/components/Calendar";
import SessionsHub from "@/components/SessionsHub";
import AppointmentForm from "@/components/AppointmentForm";
import AppointmentFormWizard from "@/components/AppointmentFormWizard";
import ServiceManagement from "@/components/ServiceManagement";
import CashRegister from "@/components/CashRegister";
import Settings from "@/components/Settings";
import SettingsSubscription from "@/components/SettingsSubscription";
import SettingsProfile from "@/components/SettingsProfile";
import LocationSettings from "@/components/LocationSettings";
import SettingsOnlineBooking from "@/components/SettingsOnlineBooking";
import Finance from "@/components/Finance";
import MerchantWallet from "@/components/MerchantWallet";
import MerchantPaymentSettings from "@/components/MerchantPaymentSettings";
import MerchantRefundRequests from "@/components/MerchantRefundRequests";
import Subscribe from "@/components/Subscribe";
import Customers from "@/components/Customers";
import ImportData from "@/components/ImportData";
import StaffManagement from "@/components/StaffManagement";
import AuditLogs from "@/components/AuditLogs";
import HelpCenter from "@/components/HelpCenter";
import SuperAdmin from "@/components/SuperAdmin";
import MarketingPanel from "@/components/MarketingPanel";
import { computeHasActiveSessions } from "@/lib/sessionPackageNav";
import SetupWizard from "@/components/SetupWizard";
import ChatWidget from "@/components/ChatWidget";
import AhaSpotlight from "@/components/AhaSpotlight";
import AhaCelebration from "@/components/AhaCelebration";
import AhaErrorScreen from "@/components/AhaErrorScreen";
import posthog from "@/lib/posthog";
import metaPixel from "@/lib/metaPixel";
import { loadChatwoot, setChatwootUser } from "@/lib/chatwoot";
import { Briefcase, DollarSign, SettingsIcon, Users, Upload, LogOut, Moon, Sun, UserCog, FileText, Home, Plus, CreditCard, User, HelpCircle, Package, Bell, Layers, Calendar } from "lucide-react";
import { useTheme } from "./context/ThemeContext";
import { useTranslation } from "react-i18next";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { PushNotifications } from '@capacitor/push-notifications';

const FCMTokenPlugin = Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios'
  ? registerPlugin('FCMTokenPlugin')
  : null;

function App() {
  const { logout, userRole, token } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { t, i18n } = useTranslation();
  const bottomNavRef = useRef(null);

  const ENABLE_SETUP_WIZARD = false;
  const isSpecialRole = userRole === 'superadmin' || userRole === 'marketing';
  
  const [currentView, setCurrentView] = useState(() => {
    if (userRole === 'superadmin') return 'superadmin';
    if (userRole === 'marketing') return 'marketing';
    return 'dashboard';
  });
  const [services, setServices] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [settings, setSettings] = useState(null);
  const [showPaymentSuccess, setShowPaymentSuccess] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  // ===== AHA ACTIVATION STATE =====
  // 'idle' | 'spotlight' | 'triggering' | 'celebration' | 'error' | 'skipped'
  const [ahaUiState, setAhaUiState] = useState('idle');
  const [ahaRetryCount, setAhaRetryCount] = useState(0);
  const [ahaLastError, setAhaLastError] = useState(null);
  const [forceStartTour, setForceStartTour] = useState(false);

  const hasActiveSessions = useMemo(
    () => computeHasActiveSessions(appointments),
    [appointments]
  );

  useEffect(() => {
    if (!hasActiveSessions && currentView === "sessions") {
      setCurrentView("dashboard");
    }
  }, [hasActiveSessions, currentView]);

  // ===== GÖRÜNÜM GEÇMİŞİ + iOS GERİ KAYDIRMA =====
  // Panel navigasyonu history kullanmadığı için (setCurrentView state),
  // görünüm geçmişini ayrı bir yığında tutuyoruz ve sol kenardan sağa
  // kaydırma jestiyle bir önceki görünüme dönüyoruz.
  const viewHistoryRef = useRef([]);
  const skipHistoryRef = useRef(false);
  const prevViewRef = useRef(currentView);

  useEffect(() => {
    const prev = prevViewRef.current;
    if (prev !== currentView) {
      if (skipHistoryRef.current) {
        skipHistoryRef.current = false;
      } else {
        viewHistoryRef.current.push(prev);
        if (viewHistoryRef.current.length > 50) viewHistoryRef.current.shift();
      }
      prevViewRef.current = currentView;
    }
  }, [currentView]);

  const goBack = useCallback(() => {
    // 1) Açık form/modal varsa önce onu kapat
    if (showForm) {
      setShowForm(false);
      return true;
    }
    // 2) Görünüm geçmişinden bir önceki ekrana dön
    const stack = viewHistoryRef.current;
    if (stack.length > 0) {
      const target = stack.pop();
      skipHistoryRef.current = true;
      setShowForm(false);
      setCurrentView(target);
      return true;
    }
    return false;
  }, [showForm]);

  // iOS sol-kenar kaydırma (geri) jesti
  useEffect(() => {
    if (Capacitor.getPlatform() !== 'ios') return;
    const EDGE_PX = 30;      // sol kenardan başlama eşiği
    const THRESH_PX = 70;    // minimum yatay kayma
    let tracking = false;
    let startX = 0, startY = 0, startT = 0;
    const onStart = (e) => {
      const tp = e.touches && e.touches[0];
      if (!tp) { tracking = false; return; }
      if (tp.clientX <= EDGE_PX) {
        tracking = true; startX = tp.clientX; startY = tp.clientY; startT = Date.now();
      } else {
        tracking = false;
      }
    };
    const onEnd = (e) => {
      if (!tracking) return;
      tracking = false;
      const tp = e.changedTouches && e.changedTouches[0];
      if (!tp) return;
      const dx = tp.clientX - startX;
      const dy = Math.abs(tp.clientY - startY);
      const dt = Date.now() - startT;
      // Yatay, sağa doğru, hızlı ve yeterince uzun bir kaydırma
      if (dx > THRESH_PX && dy < 80 && dt < 600) {
        goBack();
      }
    };
    document.addEventListener('touchstart', onStart, { passive: true });
    document.addEventListener('touchend', onEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onStart);
      document.removeEventListener('touchend', onEnd);
    };
  }, [goBack]);
  
  // Notification states
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const notificationsRef = useRef([]);
  const location = useLocation();

  useEffect(() => {
    document.title = i18n.language?.toLowerCase().startsWith('tr')
      ? 'PLANN | Yönetim Paneli'
      : 'PLANN | Dashboard';
  }, [i18n.language]);

  // Chatwoot live-chat SDK — load once (web + native).
  // Launcher bubble is hidden; opened programmatically via openLiveChat().
  useEffect(() => {
    loadChatwoot();
  }, []);

  // Identify the logged-in user inside Chatwoot so agents see the company
  // name + admin name instead of an auto-generated handle (e.g. "small-dew").
  // Runs whenever auth + settings change; the SDK may still be loading,
  // setChatwootUser buffers and replays on `chatwoot:ready`.
  //
  // Backend'den HMAC identifier_hash fetch ederiz. Chatwoot panelinde
  // "User Identity Validation" açıksa bu zorunludur; aksi halde setUser çağrısı
  // sessizce reddedilir ve panelde "small-dew" gibi anonymous handle görünür.
  // Identify the logged-in user inside Chatwoot
  useEffect(() => {
    if (!token || !settings) return;
    let payload;
    try {
      payload = JSON.parse(atob(token.split(".")[1]));
    } catch (_) {
      return;
    }
    const identifier = payload.user_id || payload.sub;
    if (!identifier) return;

    const companyName = settings.company_name || "";
    const adminName = payload.full_name || payload.sub || "";
    const displayName = companyName && adminName
      ? `${companyName} — ${adminName}`
      : (companyName || adminName || String(identifier));

    let cancelled = false;
    (async () => {
      let identifierHash;
      try {
        const res = await api.get("/me/chatwoot-identity");
        if (res?.data?.identifier_hash) identifierHash = res.data.identifier_hash;
      } catch (_) {}
      
      if (cancelled) return;

      const chatwootData = {
        name: displayName,
        email: payload.sub,
        phone_number: settings.support_phone || undefined,
        company_name: companyName || undefined,
        identifier_hash: identifierHash,
        custom_attributes: {
          organization_id: payload.org_id,
          role: payload.role || userRole,
          sector: payload.sector || settings.sector,
          plan: settings.subscription_status || settings.plan || undefined,
        },
      };

      const runIdentify = () => {
        if (window.$chatwoot) {
          window.$chatwoot.setUser(String(identifier), chatwootData);
        }
      };

      // Android Capacitor yükleme gecikmesine karşı koruma
      if (window.$chatwoot && window.$chatwoot.hasLoaded) {
        runIdentify();
      } else {
        window.addEventListener("chatwoot:ready", runIdentify);
      }
      
    })();
    return () => { cancelled = true; };
  }, [token, settings, userRole]);

  // VIEW DEĞİŞİMİNDE SCROLL'U EN BAŞA AL
  // Login sonrası body overflow:hidden olduğu için window.scrollTo(0,0)
  // çalışmıyor — gerçek scroll #app-wrapper üzerinde. Bu yüzden alt sayfaya
  // navigate ettiğimizde manuel olarak wrapper.scrollTop = 0 ile sıfırlıyoruz.
  // Aksi takdirde Personel/Hizmet/İletişim/Online Randevu gibi alt sayfalar
  // bir önceki sayfanın scroll pozisyonundan açılıyordu.
  useEffect(() => {
    const wrapper = document.getElementById("app-wrapper");
    if (wrapper) {
      wrapper.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    // Yedek: window scroll'u da sıfırla (login öncesi state için).
    if (typeof window !== "undefined" && window.scrollTo) {
      window.scrollTo(0, 0);
    }
  }, [currentView]);

  // APP SCROLL KİLİDİ YÖNETİMİ
  useEffect(() => {
    if (token) {
      // Kullanıcı giriş yapmış (Paneldeyiz) -> Ekranı kilitle, kaydırmayı app-wrapper yapsın
      document.documentElement.classList.add('app-locked');
      document.body.classList.add('app-locked');
    } else {
      // Kullanıcı giriş yapmamış (Landing Page / Login) -> Kilidi aç, normal web sitesi gibi kaysın
      document.documentElement.classList.remove('app-locked');
      document.body.classList.remove('app-locked');
    }

    // Component unmount olursa temizlik yap
    return () => {
      document.documentElement.classList.remove('app-locked');
      document.body.classList.remove('app-locked');
    };
  }, [token]);

  // App mode detection - PWA/APK olarak açıldığında is_app_mode set et
  useEffect(() => {
    const urlParams = new URLSearchParams(location.search);
    const modeParam = urlParams.get('mode');
    
    // URL'de mode=app varsa kaydet
    if (modeParam === 'app') {
      localStorage.setItem('is_app_mode', 'true');
    }
    
    // Native Capacitor uygulaması ise app mode olarak işaretle
    if (Capacitor.isNativePlatform()) {
      localStorage.setItem('is_app_mode', 'true');
    }
    
    // Standalone modda açıldıysa (PWA olarak yüklendi) da app mode olarak işaretle
    if (window.matchMedia('(display-mode: standalone)').matches || 
        window.navigator.standalone === true) {
      localStorage.setItem('is_app_mode', 'true');
    }
  }, []);

  // Deep link handling for native apps (Stripe payment success/cancel)
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      const handleDeepLink = CapacitorApp.addListener('appUrlOpen', (event) => {
        console.log('🔗 Deep link received:', event.url);
        
        if (event.url.includes('payment-success')) {
          toast.success("🎉 Ödeme başarılı! Planınız güncellendi.", { duration: 5000 });
          setCurrentView('dashboard');
        } else if (event.url.includes('subscribe')) {
          // Cancel - subscribe sayfasında kal
          setCurrentView('subscribe');
        }
      });

      return () => {
        handleDeepLink.remove();
      };
    }
  }, []);

  // URL routing - path'den view'ı oku ve URL değişikliklerini dinle
  useEffect(() => {
    const handleRouteChange = () => {
      const path = window.location.pathname;
      const hash = window.location.hash;
      const urlParams = new URLSearchParams(window.location.search);
      const paymentStatus = urlParams.get('payment');
      const search = window.location.search;
      const href = window.location.href;
      
      console.log('🔍 URL Changed:', { path, hash, search, href, userRole, paymentStatus });
      
      // Hash routing ile PayTR/Stripe dönüşü (authentication korunur)
      if (hash.startsWith('#/payment-success')) {
        console.log('✅ Payment successful via hash routing');
        // Stripe success URL hash içinde session_id taşıyabilir: #/payment-success?session_id=...
        const queryStart = hash.indexOf('?');
        let sessionId = null;
        if (queryStart !== -1) {
          const queryString = hash.substring(queryStart + 1);
          const hashParams = new URLSearchParams(queryString);
          sessionId = hashParams.get('session_id');
        }

        // Fallback: Bazı redirect senaryolarında session_id hash içine değil query string'e düşebilir
        if (!sessionId) {
          sessionId = urlParams.get('session_id');
        }

        const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');

        console.log('💳 payment-success params:', {
          hasSessionId: Boolean(sessionId),
          hasAuthToken: Boolean(authToken),
        });

        if (sessionId && authToken) {
          // Webhook gelmezse bile planı güncellemek için confirm endpoint
          console.log('🔁 Sending confirm-checkout-session request:', { sessionId });
          api.post('/payments/confirm-checkout-session', { session_id: sessionId })
            .then(() => {
              // Stats'ı ve ekranı tazele
              if (typeof loadStats === 'function') loadStats();
            })
            .catch(() => {
              // Sessiz geç - webhook ile güncellenebilir
            });
        } else if (sessionId && !authToken) {
          console.warn('⚠️ payment-success: sessionId var ama authToken yok; confirm isteği atlanıyor. Önce login olunmalı.');
        }

        if (authToken) {
          setCurrentView('dashboard');
        } else if (userRole === 'admin') {
          setCurrentView('dashboard');
        }
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
      } else if (hash.startsWith('#/payment-failed')) {
        console.log('❌ Payment failed via hash routing');
        setCurrentView('subscribe');
        setShowForm(false);
        toast.error('Ödeme işlemi başarısız oldu. Lütfen tekrar deneyin.', {
          duration: 5000,
        });
        // Hash'i temizle
        window.location.hash = '';
      } else if (hash.startsWith('#/subscribe') && userRole === 'admin') {
        // Stripe cancel_url gibi durumlarda subscribe sayfasına düşür
        setCurrentView('subscribe');
        setShowForm(false);
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
        if (response.status === 200) {
          // Mevcut kullanıcının username'ini token'dan al
          const tokenPayload = JSON.parse(atob(token.split('.')[1]));
          const username = tokenPayload.sub;
          const user = response.data?.find(u => u.username === username);
          
          if (user) {
            setCurrentUser(user);
            // Admin ve onboarding tamamlanmamışsa sihirbazı göster
            if (user.role === 'admin' && !user.onboarding_completed) {
              if (ENABLE_SETUP_WIZARD) setShowOnboarding(true);
            }
            // Aha activation state machine — yalnızca admin
            if (user.role === 'admin') {
              const aState = user.activation_state;
              if (aState === 'pending_aha_appointment') {
                setAhaUiState('spotlight');
              } else if (aState === 'aha_wa_failed') {
                setAhaUiState('error');
                setAhaLastError(user.aha_wa_last_error || null);
              }
              // aha_completed / aha_skipped / skip_aha_no_phone / not_applicable → idle
            }
          }
        }
      } catch (error) {
        console.error("Onboarding kontrolü yapılamadı:", error);
      }
    }
  }, [userRole, token, ENABLE_SETUP_WIZARD]);

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
      
      // 'Bekliyor' durumundaki ve sadece public_booking kaynaklı randevuları bildirim olarak ekle
      // Adminin kendi oluşturduğu randevular bildirim olarak gösterilmez
      const pendingAppointments = allAppointments.filter(appt => 
        appt.status === 'Bekliyor' && appt.source === 'public_booking'
      );
      
      // Okunmuş bildirimleri localStorage'dan al
      const readNotificationIds = JSON.parse(localStorage.getItem('readNotificationIds') || '[]');
      
      // Bildirim formatına dönüştür - okunmuş durumu localStorage'dan kontrol et
      const newNotifications = pendingAppointments.map(appt => ({
        id: appt.id, // Unique ID kullan
        read: readNotificationIds.includes(appt.id), // localStorage'dan kontrol et
        type: 'new_appointment',
        title: 'Yeni Randevu',
        message: `${appt.customer_name} - ${appt.service_name}`,
        details: `${appt.appointment_date} ${appt.appointment_time}`,
        time: appt.created_at || new Date().toISOString()
      }));
      
      // En yeni en üstte olacak şekilde sırala (time'a göre descending)
      newNotifications.sort((a, b) => {
        const timeA = new Date(a.time).getTime();
        const timeB = new Date(b.time).getTime();
        return timeB - timeA; // En yeni en üstte
      });
      
      setNotifications(newNotifications);

      console.log("✅ Randevular yüklendi:", allAppointments.length, "randevu");
      if (pendingAppointments.length > 0) {
        console.log("🔔 Bekleyen public booking randevuları bildirime eklendi:", pendingAppointments.length);
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

  // Role-based initial view
  useEffect(() => {
    if (userRole === 'superadmin') {
      setCurrentView('superadmin');
    } else if (userRole === 'marketing') {
      setCurrentView('marketing');
    }
  }, [userRole]);

  useEffect(() => {
    if (isSpecialRole) return; // superadmin/marketing için veri yükleme
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
    const isNative = Capacitor.isNativePlatform();
    const debugPush = async (step, data, error) => {
      try { await api.post('/push/debug', { step, data, error: error ? String(error) : null, platform: Capacitor.getPlatform() }); } catch(e) {}
    };
    
    if (isNative) {
      // Native (Android/iOS) Push Notification Logic
      const platform = Capacitor.getPlatform();
      await debugPush('start', { platform, isNative });
      try {
        const permissionStatus = await PushNotifications.requestPermissions();
        await debugPush('permission', { receive: permissionStatus.receive });
        
        if (permissionStatus.receive === 'granted') {

          // iOS: FCMTokenPlugin ile doğrudan FCM token al (registration event'a bağımlı değil)
          if (platform === 'ios') {
            await debugPush('ios_branch', { hasFCMPlugin: !!FCMTokenPlugin });
            if (FCMTokenPlugin) {
              try {
                await debugPush('ios_calling_registerAndGetToken', {});
                const fcmResult = await FCMTokenPlugin.registerAndGetToken();
                await debugPush('ios_token_result', { hasToken: !!(fcmResult && fcmResult.token), tokenPrefix: fcmResult?.token?.substring(0, 20) });
                if (fcmResult && fcmResult.token) {
                  await api.post('/push/subscribe', {
                    subscription: {
                      endpoint: fcmResult.token,
                      keys: { p256dh: '', auth: '' },
                      platform: 'ios'
                    }
                  });
                  setPushSubscribed(true);
                  await debugPush('ios_subscribe_success', {});
                } else {
                  await debugPush('ios_token_empty', {});
                }
              } catch (fcmError) {
                await debugPush('ios_fcm_error', {}, fcmError?.message || String(fcmError));
              }
            } else {
              await debugPush('ios_no_plugin', {});
            }
          } else {
            // Android: Capacitor registration event kullan
            await PushNotifications.register();
            
            PushNotifications.addListener('registration', async (token) => {
              console.log('📱 Android Push Token:', token.value);
              await api.post('/push/subscribe', {
                subscription: {
                  endpoint: token.value,
                  keys: { p256dh: '', auth: '' },
                  platform: platform
                }
              });
              setPushSubscribed(true);
            });

            PushNotifications.addListener('registrationError', (error) => {
               console.error('❌ Native Push registration error:', error);
            });
          }

          // Bildirim alındığında (hem iOS hem Android)
          PushNotifications.addListener('pushNotificationReceived', (notification) => {
             console.log('🔔 Native Notification received:', notification);
             setNotifications(prev => [{
               id: notification.id || Date.now().toString(),
               read: false,
               type: 'new_appointment',
               title: notification.title,
               message: notification.body,
               time: new Date().toISOString()
             }, ...prev]);
             toast.info(`${notification.title}: ${notification.body}`);
          });

          // Bildirime tıklandığında
          PushNotifications.addListener('pushNotificationActionPerformed', (notification) => {
             console.log('👆 Notification clicked:', notification);
          });
        } else {
          await debugPush('permission_denied', { receive: permissionStatus.receive });
        }
      } catch (error) {
        await debugPush('native_error', {}, error?.message || String(error));
      }
      return;
    }

    // Web Push Logic (Mevcut kod)
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
  
  // Token değiştiğinde push subscription'ı yenile (cross-account sorununu önlemek için)
  const prevTokenRef = useRef(token);
  useEffect(() => {
    // Token değiştiğinde (yeni login) pushSubscribed state'ini false yap
    if (prevTokenRef.current !== token) {
      if (prevTokenRef.current !== null && token !== null) {
        // Token değişti (yeni kullanıcı giriş yaptı), subscription'ı sıfırla
        console.log('🔄 Token changed, resetting push subscription');
        setPushSubscribed(false);
      }
      prevTokenRef.current = token;
    }
  }, [token]);

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
        transports: ['websocket'],
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
        
        // Personel ise sadece kendi randevuları için bildirim göster (can_view_all_appointments yetkisi yoksa)
        if (user?.role === 'staff' && !user?.can_view_all_appointments && appointment?.staff_member_id !== user?.username) {
          console.log("🔕 Bildirim gösterilmedi - başka personelin randevusu");
          return;
        }
        
        if (appointment?.source === 'public_booking') {
          // In-app notification ekle
          const newNotification = {
            id: appointment.id || Date.now(),
            type: 'new_appointment',
            title: '🔔 Yeni Online Randevu!',
            message: `${appointment.customer_name} - ${appointment.service_name}`,
            details: `${appointment.appointment_date} ${appointment.appointment_time}`,
            time: appointment.created_at || new Date().toISOString(),
            read: false,
            appointmentId: appointment.id
          };
          
          // notificationsRef kullanarak güncelle (closure sorunu için)
          // En yeni en üstte olacak şekilde ekle ve sırala
          if (typeof setNotifications === 'function') {
            setNotifications(prev => {
              // Mevcut bildirimlerden bu ID'yi çıkar (duplicate önlemek için)
              const filtered = prev.filter(n => n.id !== newNotification.id);
              const updated = [newNotification, ...filtered].slice(0, 20);
              
              // En yeni en üstte olacak şekilde sırala
              updated.sort((a, b) => {
                const timeA = new Date(a.time).getTime();
                const timeB = new Date(b.time).getTime();
                return timeB - timeA; // En yeni en üstte
              });
              
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

      socket.on('appointments_bulk_updated', () => {
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

  // Fix layout on mount
  useEffect(() => {
    const fixLayout = () => {
      window.scrollTo(0, 0);
      window.dispatchEvent(new Event("resize"));
    };

    const timer = setTimeout(fixLayout, 150);
    return () => clearTimeout(timer);
  }, []);

  // Initialize StatusBar
  useEffect(() => {
    const initStatusBar = async () => {
      if (Capacitor.isNativePlatform()) {
        try {
          await StatusBar.setOverlaysWebView({ overlay: true });
          // İkonların koyu/siyah olması için Style.Light kullanıyoruz (Beyaz arka plan için)
          await StatusBar.setStyle({ style: Style.Light }); 
          // Status bar arka planını beyaz yapıyoruz
          await StatusBar.setBackgroundColor({ color: '#ffffff' }); 
        } catch (error) {
          console.error("StatusBar ayarlanırken hata:", error);
        }
      }
    };
    initStatusBar();
  }, []);

  // Radix reflow hack for PWA/Native
  useEffect(() => {
    // Sadece PWA veya Native App modunda çalışsın
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone || Capacitor.isNativePlatform();
    
    if (isStandalone) {
      // Tarayıcıyı ekranı yeniden ölçmeye zorla (Reflow Hack)
      requestAnimationFrame(() => {
        const originalOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden'; // Radix'in yaptığını taklit et
        
        requestAnimationFrame(() => {
          document.body.style.overflow = originalOverflow; // Hemen geri al
        });
      });
    }
  }, []);
  
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

    // Funnel: first_real_appointment_created — Aha sonrası ilk gerçek randevu
    // Tek seferlik trigger; her admin için localStorage flag'i ile dedupe edilir.
    try {
      if (userRole === 'admin' && currentUser?.user_id) {
        const flagKey = `aha_first_real_apt_tracked:${currentUser.user_id}`;
        if (!localStorage.getItem(flagKey)) {
          posthog.track('first_real_appointment_created');

          // Meta: Schedule — admin dashboard'undan ilk gerçek randevu oluşturuldu.
          // Tek seferlik (flag dedupe). Pixel + CAPI tek event_id ile dedupe edilir.
          try {
            metaPixel.track('Schedule', {
              customData: {
                content_name: currentUser?.business_name || currentUser?.organization_name || 'PLANN',
                content_category: 'first_real_appointment',
              },
              userData: {
                external_id: currentUser.user_id,
                contact_email: currentUser.username,
                contact_phone: settings?.support_phone,
                contact_name: currentUser.full_name,
              },
            });
          } catch (_) {}

          localStorage.setItem(flagKey, '1');
        }
      }
    } catch (_) {}
    console.log("✅ Appointments refreshed, form closed");
  };
  const handleEditAppointment = (appointment) => {
    setSelectedAppointment(appointment);
    setShowForm(true);
  };

  // ===== AHA ACTIVATION HANDLERS =====
  const triggerAha = useCallback(async () => {
    if (ahaUiState === 'triggering') return;
    const isRetry = ahaRetryCount > 0;
    setAhaUiState('triggering');
    setAhaLastError(null);
    // Event: ilk tetikleme button_clicked, sonrakiler retry_clicked
    posthog.track(isRetry ? 'aha_retry_clicked' : 'aha_button_clicked', {
      attempt_no: ahaRetryCount + 1,
    });
    try {
      const response = await api.post('/onboarding/aha-test-appointment', {});
      const data = response?.data || {};
      if (data.activation_state === 'aha_completed') {
        setCurrentUser((prev) => prev ? { ...prev, activation_state: 'aha_completed' } : prev);
        setAhaUiState('celebration');
        posthog.track('aha_appointment_created', {
          wa_status: 'sent',
          service_id: data.appointment?.service_id,
        });
      } else if (data.activation_state === 'aha_wa_failed') {
        setCurrentUser((prev) => prev ? { ...prev, activation_state: 'aha_wa_failed' } : prev);
        setAhaLastError(data.wa_error || 'wa_delivery_failed');
        setAhaRetryCount((c) => c + 1);
        setAhaUiState('error');
        posthog.track('aha_appointment_created', {
          wa_status: 'failed',
          service_id: data.appointment?.service_id,
        });
        posthog.track('aha_wa_failed', {
          error: (data.wa_error || 'unknown').slice(0, 200),
          attempt_no: ahaRetryCount + 1,
        });
      } else {
        // Beklenmeyen yanıt → güvenli fallback
        setAhaLastError(`unexpected_state:${data.activation_state || 'unknown'}`);
        setAhaUiState('error');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail === 'support_phone_missing') {
        // Backend skip_aha_no_phone state'ine aldı; klasik tura geç
        setCurrentUser((prev) => prev ? { ...prev, activation_state: 'skip_aha_no_phone' } : prev);
        setAhaUiState('skipped');
        setForceStartTour(true);
        posthog.track('aha_skipped', { reason: 'no_phone' });
        return;
      }
      const code = err?.response?.status || 'network';
      const errMsg = `http_${code}: ${detail || err?.message || 'unknown'}`;
      setAhaLastError(errMsg);
      setAhaRetryCount((c) => c + 1);
      setAhaUiState('error');
      posthog.track('aha_wa_failed', {
        error: errMsg.slice(0, 200),
        attempt_no: ahaRetryCount + 1,
      });
    }
  }, [ahaUiState, ahaRetryCount]);

  const handleAhaSkip = useCallback(async (reason = 'user_choice') => {
    try {
      await api.post('/onboarding/aha-skip', { reason });
    } catch (err) {
      // Skip best-effort: backend ulaşılamasa bile client tarafı continue etsin
      console.warn('Aha skip endpoint failed; continuing client-side:', err);
    }
    setCurrentUser((prev) => prev ? { ...prev, activation_state: 'aha_skipped' } : prev);
    setAhaUiState('skipped');
    setForceStartTour(true);
    posthog.track('aha_skipped', { reason });
  }, []);

  const handleAhaSpotlightFallback = useCallback(() => {
    // DOM hedefi 500ms içinde bulunamadı — state değişmez, sadece klasik tura geç
    setAhaUiState('idle');
    setForceStartTour(true);
    posthog.track('aha_target_missing', { route: window.location.pathname });
  }, []);

  const handleAhaSpotlightShown = useCallback(() => {
    posthog.track('aha_spotlight_shown', {
      support_phone_present: Boolean(currentUser?.activation_state === 'pending_aha_appointment'),
    });
  }, [currentUser]);

  const handleAhaCelebrationContinue = useCallback(() => {
    setAhaUiState('idle');
    setForceStartTour(true);
  }, []);

  const handleAhaCelebrationDismiss = useCallback(({ autoAdvanced } = {}) => {
    posthog.track('aha_celebration_dismissed', { auto_advanced: !!autoAdvanced });
  }, []);

  const handleAhaErrorDismiss = useCallback(() => {
    // X ile kapatma: state değişmez, sadece UI gizlenir; sonraki login'de tekrar çıkar
    setAhaUiState('idle');
    posthog.track('aha_modal_dismissed_without_choice');
  }, []);

  const handleNewAppointment = () => {
    // Aha modunda klasik form yerine endpoint'i tetikle
    if (
      userRole === 'admin' &&
      currentUser?.activation_state === 'pending_aha_appointment' &&
      ahaUiState !== 'triggering'
    ) {
      triggerAha();
      return;
    }
    setSelectedAppointment(null);
    setShowForm(true);
  };


  return (
    // YENİ FIXED WRAPPER MİMARİSİ BAŞLANGICI
    <div 
      id="app-wrapper"
      className="fixed inset-0 overflow-y-auto bg-white dark:bg-gray-900 transition-colors w-full h-full"
      style={{ 
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        height: '100%',
        width: '100%'
      }}
    >

      {/* Setup Wizard - Onboarding */}
      {ENABLE_SETUP_WIZARD && showOnboarding && (
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

      {/* Special roles (superadmin, marketing) kendi layout'larını içeriyor */}
      {isSpecialRole && currentView === 'superadmin' && <SuperAdmin />}
      {isSpecialRole && currentView === 'marketing' && <MarketingPanel />}

      {/* Normal kullanıcı UI — sadece admin/staff */}
      {!isSpecialRole && (
      <>

      
      {/* TopBar - Üst Navigasyon Barı */}
      {!showForm && (
        <header 
          className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm"
          style={{ 
            // max(..., 15px) ile boşluğu düşürdük, daha ince ve şık bir görünüm elde ettik
            // + 5px ile de ikonların çok dibine yapışmamasını sağlamaya devam ediyoruz
            paddingTop: 'calc(max(env(safe-area-inset-top, 0px), 15px) + 5px)', 
            fontFamily: 'Inter, sans-serif' 
          }}
        >
          {/* pt-0 yaparak logo ve ikonların header içindeki konumunu yukarı çektik */}
          <div className="container mx-auto px-4 pt-0 pb-2">
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
                <DropdownMenu modal={false} open={showNotifications} onOpenChange={setShowNotifications}>
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
                  <DropdownMenuContent align="end" sideOffset={8} className="w-72 sm:w-80 max-h-[60vh] overflow-y-auto p-0 rounded-xl border border-gray-200 bg-white shadow-xl">
                    <div className="px-3 py-2.5 border-b border-gray-100 flex items-center justify-between sticky top-0 z-10 bg-white rounded-t-xl">
                      <span className="font-bold text-gray-900 text-sm">{t('notifications.title')}</span>
                      {notifications.length > 0 && (
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            setNotifications(prev => prev.map(n => ({...n, read: true})));
                            const allIds = notifications.map(n => n.id);
                            const existingIds = JSON.parse(localStorage.getItem('readNotificationIds') || '[]');
                            localStorage.setItem('readNotificationIds', JSON.stringify([...new Set([...existingIds, ...allIds])]));
                          }}
                          className="text-[11px] font-medium text-blue-600 hover:text-blue-700 transition-colors"
                        >
                          {t('notifications.markAllRead')}
                        </button>
                      )}
                    </div>
                    {notifications.length === 0 ? (
                      <div className="py-8 px-4 text-center">
                        <Bell className="w-6 h-6 text-gray-300 mx-auto mb-2" />
                        <p className="text-xs text-gray-400">{t('notifications.empty')}</p>
                      </div>
                    ) : (
                      <div>
                        {notifications.map(notification => (
                          <DropdownMenuItem 
                            key={notification.id} 
                            className={`px-3 py-2.5 cursor-pointer border-b border-gray-50 last:border-0 rounded-none focus:bg-gray-50 ${!notification.read ? 'bg-blue-50/40' : ''}`}
                            onClick={() => {
                              setNotifications(prev => prev.map(n => 
                                n.id === notification.id ? {...n, read: true} : n
                              ));
                              const existingIds = JSON.parse(localStorage.getItem('readNotificationIds') || '[]');
                              if (!existingIds.includes(notification.id)) {
                                localStorage.setItem('readNotificationIds', JSON.stringify([...existingIds, notification.id]));
                              }
                              setShowNotifications(false);
                            }}
                          >
                            <div className="flex items-start gap-2 w-full">
                              <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${!notification.read ? 'bg-blue-500' : 'bg-transparent'}`} />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <p className="text-xs font-semibold text-gray-800 truncate">{notification.message}</p>
                                  <span className="text-[10px] text-gray-400 flex-shrink-0">
                                    {new Date(notification.time).toLocaleTimeString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB', { hour: '2-digit', minute: '2-digit' })}
                                  </span>
                                </div>
                                {notification.details && (
                                  <p className="text-[11px] text-gray-500 truncate mt-0.5">{notification.details}</p>
                                )}
                              </div>
                            </div>
                          </DropdownMenuItem>
                        ))}
                      </div>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </header>
      )}

      <main className={(currentView === "dashboard" || currentView === "sessions" || currentView === "settings" || currentView === "settings-subscription" || currentView === "settings-profile" || currentView === "settings-location" || currentView === "settings-online-booking" || currentView === "subscribe" || currentView === "staff" || currentView === "services" || currentView === "help-center") && !showForm ? "" : "container mx-auto px-4 py-6"}>
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
            activationState={currentUser?.activation_state}
            ahaOverlayActive={ahaUiState !== 'idle'}
            forceStartTour={forceStartTour}
            onForceStartTourConsumed={() => setForceStartTour(false)}
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
            onOpenChat={() => setChatOpen(true)}
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
        {currentView === "sessions" && (
          <SessionsHub
            appointments={appointments}
            userRole={userRole}
            onEditAppointment={(apt) => {
              setSelectedAppointment(apt);
              setShowForm(true);
              setCurrentView("dashboard");
            }}
            onRefresh={async () => {
              await loadAppointments();
              if (userRole === "admin") await loadStats();
            }}
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
            onRefresh={async () => {
              await loadAppointments();
              if (userRole === 'admin') await loadStats();
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

        {currentView === "settings-location" && userRole === 'admin' && (
          <LocationSettings
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
          />
        )}
        {currentView === "settings-online-booking" && userRole === 'admin' && (
          <SettingsOnlineBooking
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
        {currentView === "merchant-wallet" && userRole === 'admin' && (
          <MerchantWallet onNavigate={(view) => { setCurrentView(view); setShowForm(false); }} />
        )}
        {currentView === "merchant-refund-requests" && userRole === 'admin' && (
          <MerchantRefundRequests onNavigate={(view) => { setCurrentView(view); setShowForm(false); }} />
        )}
        {currentView === "merchant-payment-settings" && userRole === 'admin' && (
          <MerchantPaymentSettings onNavigate={(view) => { setCurrentView(view); setShowForm(false); }} />
        )}
        {currentView === "subscribe" && userRole === 'admin' && (
          <Subscribe 
            onNavigate={(view) => {
              setCurrentView(view);
              setShowForm(false);
            }}
            currentUser={currentUser}
            settings={settings}
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
      </main>

      {/* Alt Navigasyon: Dashboard | Seanslar | + | Müşteriler | Ayarlar — Takvim Dashboard’dan */}
      {(currentView === "dashboard" || currentView === "sessions" || currentView === "calendar") && !showForm && (
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
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
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
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                currentView === "dashboard"
                  ? "text-gray-900"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <Home className="w-5 h-5" />
              <span className="text-xs font-medium">{t('nav.dashboard', 'Dashboard')}</span>
            </button>

            {hasActiveSessions ? (
              <button
                type="button"
                onClick={() => {
                  setCurrentView("sessions");
                  setShowForm(false);
                }}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                  currentView === "sessions" ? "text-gray-900" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <Layers className="w-5 h-5" />
                <span className="text-xs font-medium">{t('nav.sessions', 'Sessions')}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setCurrentView("calendar");
                  setShowForm(false);
                }}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                  currentView === "calendar" ? "text-gray-900" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <Calendar className="w-5 h-5" />
                <span className="text-xs font-medium">{t('nav.calendar', 'Calendar')}</span>
              </button>
            )}

            {/* Yeni Randevu Ekle — koyu gri + hafif mavi gölge (seçenek 4). */}
            <button
              onClick={handleNewAppointment}
              className="aha-fab-plus relative flex items-center justify-center w-14 h-14 rounded-full -mt-4 tour-new-appointment text-white bg-gradient-to-b from-zinc-700 to-zinc-900 border border-zinc-600/45 shadow-[0_5px_16px_rgba(59,130,246,0.2),0_2px_6px_rgba(0,0,0,0.22)] hover:from-zinc-700 hover:to-black hover:shadow-[0_6px_18px_rgba(59,130,246,0.24),0_3px_8px_rgba(0,0,0,0.24)] active:scale-[0.97] transition-[transform,box-shadow,background] duration-150"
            >
              <Plus className="w-6 h-6" strokeWidth={2.25} />
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
              <span className="text-xs font-medium">{t('nav.customers', 'Customers')}</span>
            </button>

            {/* Ayarlar */}
            <button
              onClick={() => {
                setCurrentView("settings");
                setShowForm(false);
              }}
              className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors text-gray-600 hover:text-gray-900 tour-settings"
            >
              <SettingsIcon className="w-5 h-5" />
              <span className="text-xs font-medium">{t('nav.settings', 'Settings')}</span>
            </button>
          </div>
        </div>
      )}

      {/* AI Chatbot Widget - Sadece giriş yapmış kullanıcılara göster */}
      {token && currentUser && (currentView === "dashboard" || currentView === "sessions" || currentView === "calendar") && !showForm && !showOnboarding && (
        <ChatWidget
          user={{
            username: currentUser.username,
            full_name: currentUser.full_name,
            role: userRole
          }}
          externalOpen={chatOpen}
          onExternalClose={() => setChatOpen(false)}
        />
      )}

      {/* ===== AHA ACTIVATION OVERLAY'LERİ ===== */}
      {/* Yalnızca admin + dashboard view + form kapalı + setup wizard kapalı iken */}
      {token && userRole === 'admin' && currentUser && currentView === 'dashboard' && !showForm && !showOnboarding && (
        <>
          {/* Spotlight: pending_aha_appointment iken */}
          {(ahaUiState === 'spotlight' || ahaUiState === 'triggering') && (
            <AhaSpotlight
              loading={ahaUiState === 'triggering'}
              onTrigger={triggerAha}
              onFallback={handleAhaSpotlightFallback}
              onShown={handleAhaSpotlightShown}
            />
          )}
          {/* Celebration: aha_completed sonrası */}
          {ahaUiState === 'celebration' && (
            <AhaCelebration
              onContinue={handleAhaCelebrationContinue}
              onDismiss={handleAhaCelebrationDismiss}
            />
          )}
          {/* Error: aha_wa_failed iken */}
          {ahaUiState === 'error' && (
            <AhaErrorScreen
              onRetry={triggerAha}
              onSkip={() => handleAhaSkip('wa_failed')}
              onDismiss={handleAhaErrorDismiss}
              retryCount={ahaRetryCount}
              retrying={ahaUiState === 'triggering'}
              lastError={ahaLastError}
            />
          )}
        </>
      )}
      
      {/* Toaster bileşenini safe-area kadar aşağı itiyoruz */}
      <Toaster 
        position="top-center" 
        richColors 
        style={{ zIndex: 9999 }}
        toastOptions={{
          style: {
            marginTop: 'calc(env(safe-area-inset-top, 0px) + 16px)'
          }
        }}
      />
      </>
      )}
    </div>
  );
}

export default App;