import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { format } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { Calendar as CalendarIcon, Clock, Check, AlertCircle, User, ArrowRight, ArrowLeft, Loader2 } from "lucide-react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast, Toaster } from "sonner";
import { useTranslation } from "react-i18next";
import { io } from "socket.io-client";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : "";
const API = `${BACKEND_URL}/api`;

// Public endpoint için axios instance (token gerektirmez)
const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

const PublicBookingPage = () => {
  const { slug } = useParams();
  const { t, i18n } = useTranslation();
  
  // Domain bazlı dil algılama - date-fns locale ve currency symbol
  const currentLang = i18n.language || 'tr';
  const dateLocale = currentLang === 'en' ? enGB : tr;
  const currencySymbol = currentLang === 'en' ? '£' : '₺';
  
  // Domain bazlı telefon prefix ve validation
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  const isUKDomain = hostname.includes('plannapp.co.uk');
  const phonePrefix = isUKDomain ? '+44' : '+90';
  const phonePlaceholder = isUKDomain ? 'XXXX XXXXXX' : '5XX XXX XX XX';
  
  // Telefon numarası validation: prefix'ten sonra tam 10 rakam olmalı
  const validatePhone = (phone) => {
    // Prefix'i kaldır ve sadece rakamları kontrol et
    const digits = phone.replace(/[^\d]/g, '');
    return digits.length === 10;
  };
  
  // Özel route'ları yakalamayı engelle (superadmin, dashboard, login, vb.)
  const reservedPaths = ['superadmin', 'dashboard', 'login', 'register', 'forgot-password', 'reset-password', 'setup-password'];
  if (reservedPaths.includes(slug)) {
    return null; // Bu route'lar AppRouter'da zaten tanımlı, buraya gelmemeli
  }
  
  // Sihirbaz Adım Yönetimi
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 4;
  
  // Loading & Business Data
  const [loading, setLoading] = useState(true);
  const [business, setBusiness] = useState(null);
  const [services, setServices] = useState([]);
  const [staffMembers, setStaffMembers] = useState([]);
  const [settings, setSettings] = useState(null);

  // Form States
  const [selectedService, setSelectedService] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState(null); // null = "Farketmez"
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedTime, setSelectedTime] = useState("");
  const [availableSlots, setAvailableSlots] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [allSlots, setAllSlots] = useState([]);
  
  // Customer Info
  const [customerFullName, setCustomerFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [savedUser, setSavedUser] = useState(null); // localStorage'dan gelen kullanıcı
  
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  // WebSocket için ref
  const socketRef = useRef(null);

  // Logo URL helper
  const getLogoUrl = (logoUrl) => {
    if (!logoUrl) return null;
    return logoUrl;
  };

  // "Beni Hatırla" - localStorage kontrolü
  useEffect(() => {
    const savedUserData = localStorage.getItem('plann_user');
    if (savedUserData) {
      try {
        const userData = JSON.parse(savedUserData);
        setSavedUser(userData);
        // Eski format (name + surname) veya yeni format (fullName) desteği
        if (userData.fullName) {
          setCustomerFullName(userData.fullName || "");
        } else if (userData.name || userData.surname) {
          // Eski format: name ve surname'i birleştir
          const fullName = `${userData.name || ""} ${userData.surname || ""}`.trim();
          setCustomerFullName(fullName);
        }
        setPhone(userData.phone || "");
      } catch (error) {
        console.error("localStorage parse hatası:", error);
      }
    }
  }, []);

  // İşletme verilerini yükle
  useEffect(() => {
    loadBusinessData();
  }, [slug]);

  // Tarih veya personel değiştiğinde müsait saatleri yükle
  useEffect(() => {
    if (selectedService && selectedDate && business && currentStep >= 3) {
      loadAvailableSlots();
    }
  }, [selectedService, selectedDate, selectedStaff, business, currentStep]);

  // WebSocket bağlantısı - real-time güncellemeler için
  useEffect(() => {
    if (!business || !slug) return; // Business yüklenene kadar bekle

    if (!socketRef.current) {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const socketUrl = BACKEND_URL || window.location.origin;
      
      // Public sayfa için token gerektirmez
      const socket = io(socketUrl, {
        path: '/api/socket.io',
        transports: ['websocket', 'polling'],
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        autoConnect: true,
        // Token gönderme (public sayfa için gerekli değil)
      });

      socketRef.current = socket;

      socket.on('connect', () => {
        console.log('✅ PublicBookingPage: WebSocket connected');
        // Public organization room'a join et
        socket.emit('join_public_organization', {
          slug: slug,
          organization_id: business.organization_id
        });
      });

      socket.on('joined_public_organization', (data) => {
        console.log('✅ PublicBookingPage: Joined public organization room successfully', data);
      });

      socket.on('appointment_created', (data) => {
        console.log('🔔 PublicBookingPage: appointment_created event alındı', data);
        // Randevu oluşturulduğunda müsait saatleri yeniden yükle
        if (selectedService && selectedDate && business) {
          loadAvailableSlots();
        }
      });

      socket.on('disconnect', () => {
        console.log('❌ PublicBookingPage: WebSocket disconnected');
      });

      socket.on('connect_error', (err) => {
        console.error('❌ PublicBookingPage: Socket connection error:', err);
      });
    }

    // Cleanup
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [business, slug]); // business ve slug değiştiğinde yeniden bağlan

  const loadBusinessData = async () => {
    try {
      const response = await publicApi.get(`/public/business/${slug}`);
      const data = response.data;
      
      setBusiness(data);
      setServices(data.services || []);
      setStaffMembers(data.staff_members || []);
      const loadedSettings = data.settings || {};
      setSettings(loadedSettings);
      setLoading(false);
    } catch (error) {
      console.error("❌ İşletme yüklenemedi:", error);
      toast.error(t('publicBooking.businessNotFound'));
      setLoading(false);
    }
  };

  const loadAvailableSlots = async () => {
    if (!selectedService || !selectedDate || !business) return;
    
    try {
      const dateStr = format(selectedDate, "yyyy-MM-dd");
      const params = {
        service_id: selectedService.id,
        date: dateStr
      };
      
      if (selectedStaff) {
        params.staff_id = selectedStaff;
      }
      
      const response = await publicApi.get(`/public/availability/${business.organization_id}`, {
        params: params
      });
      
      let available = response.data.available_slots || [];
      let busy = response.data.busy_slots || [];
      let all = response.data.all_slots || [];
      
      // Bugünün tarihi seçiliyse, geçmiş saatleri filtrele
      const today = format(new Date(), "yyyy-MM-dd");
      if (dateStr === today) {
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        
        const filterPastSlots = (slots) => {
          return slots.filter(slot => {
            const [slotHour, slotMinute] = slot.split(':').map(Number);
            if (slotHour > currentHour) return true;
            if (slotHour === currentHour && slotMinute > currentMinute) return true;
            return false;
          });
        };
        
        available = filterPastSlots(available);
        busy = filterPastSlots(busy);
        all = filterPastSlots(all);
      }
      
      setAvailableSlots(available);
      setBusySlots(busy);
      setAllSlots(all);
    } catch (error) {
      console.error("❌ Müsait saatler yüklenemedi:", error);
      setAvailableSlots([]);
      setBusySlots([]);
      setAllSlots([]);
    }
  };

  const getQualifiedStaff = () => {
    if (!selectedService) return [];
    return staffMembers.filter(staff => 
      staff.permitted_service_ids && staff.permitted_service_ids.includes(selectedService.id)
    );
  };

  // "Bu ben değilim" - localStorage'ı temizle
  const handleNotMe = () => {
    localStorage.removeItem('plann_user');
    setSavedUser(null);
    setCustomerFullName("");
    setPhone("");
  };

  // Adım ilerleme kontrolü
  const canGoNext = () => {
    switch (currentStep) {
      case 1:
        return selectedService !== null;
      case 2:
        return true; // Personel seçimi zorunlu değil (Farketmez varsayılan)
      case 3:
        return selectedTime !== "";
      case 4:
        return customerFullName.trim() !== "" && phone.trim() !== "";
      default:
        return false;
    }
  };

  const handleNext = () => {
    // Eğer Adım 1'den geçiyorsa ve customer_can_choose_staff kapalıysa, Adım 3'e atla
    if (currentStep === 1 && settings && !settings.customer_can_choose_staff) {
      setSelectedStaff(null); // Otomatik atama için null yap
      setCurrentStep(3); // Direkt Adım 3'e geç
      return;
    }
    
    if (canGoNext() && currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      // Eğer Adım 3'ten geri geliyorsa ve customer_can_choose_staff kapalıysa, Adım 1'e dön
      if (currentStep === 3 && settings && !settings.customer_can_choose_staff) {
        setCurrentStep(1);
        return;
      }
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedService || !selectedDate || !selectedTime || !customerFullName || !phone) {
      toast.error(t('publicBooking.errorFillAll'));
      return;
    }
    
    // Telefon numarası validation: tam 10 rakam olmalı
    if (!validatePhone(phone)) {
      toast.error(
        isUKDomain 
          ? t('publicBooking.phoneInvalidUK', { pattern: phonePrefix })
          : t('publicBooking.phoneInvalidTR', { pattern: phonePrefix })
      );
      return;
    }

    setSubmitting(true);
    try {
      const fullName = customerFullName.trim();
      
      // Telefon numarasına prefix ekle
      const fullPhoneNumber = `${phonePrefix}${phone}`;
      
      const payload = {
        customer_name: fullName,
        phone: fullPhoneNumber,
        service_id: selectedService.id,
        appointment_date: format(selectedDate, "yyyy-MM-dd"),
        appointment_time: selectedTime,
        notes: "",
        staff_member_id: selectedStaff || null
      };

      await publicApi.post(`/public/appointments`, payload, {
        params: { organization_id: business.organization_id }
      });
      
      // "Beni Hatırla" seçildiyse localStorage'a kaydet
      if (rememberMe) {
        const userData = {
          fullName: fullName,
          phone: phone.trim()
        };
        localStorage.setItem('plann_user', JSON.stringify(userData));
      }
      
      setSuccess(true);
      toast.success(t('publicBooking.appointmentCreated'));
      
      // 5 saniye sonra formu resetle
      setTimeout(() => {
        setSuccess(false);
        setCurrentStep(1);
        setSelectedService(null);
        setSelectedStaff(null);
        setSelectedDate(new Date());
        setSelectedTime("");
        setCustomerFullName("");
        setPhone("");
        setRememberMe(false);
      }, 5000);
    } catch (error) {
      const errorMessage = error.response?.data?.detail || t('publicBooking.errorCreateAppointment');
      toast.error(errorMessage);
      console.error("❌ Randevu hatası:", error);
    } finally {
      setSubmitting(false);
    }
  };

  // --- LOADING STATE ---
  if (loading) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-zinc-900" />
        <p className="mt-4 text-zinc-500 font-medium tracking-tight animate-pulse">{t('publicBooking.loading')}</p>
      </div>
    );
  }

  // --- BUSINESS NOT FOUND STATE ---
  if (!business) {
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-4">
        <Card className="p-8 text-center max-w-md border border-zinc-200 shadow-sm bg-white">
          <AlertCircle className="w-12 h-12 text-zinc-900 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-zinc-900 mb-2 tracking-tight">{t('publicBooking.businessNotFound')}</h2>
          <p className="text-zinc-500">{t('publicBooking.businessNotFoundDesc')}</p>
        </Card>
      </div>
    );
  }

  // --- SUCCESS STATE ---
  if (success) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <Toaster position="top-center" richColors theme="light" />
        <div className="text-center max-w-md w-full animate-in fade-in zoom-in duration-300">
          <div className="w-20 h-20 bg-zinc-900 text-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl">
            <Check className="w-10 h-10" />
          </div>
          <h2 className="text-3xl font-bold text-zinc-900 mb-3 tracking-tight">{t('publicBooking.appointmentCreated')}</h2>
          <p className="text-zinc-500 text-lg mb-8">{t('publicBooking.appointmentCreatedDesc')}</p>
          <div className="p-4 bg-zinc-50 rounded-lg border border-zinc-100 text-sm text-zinc-400">
             {t('publicBooking.thankYou')}
          </div>
        </div>
      </div>
    );
  }

  const qualifiedStaff = getQualifiedStaff();
  const selectedStaffName = selectedStaff 
    ? qualifiedStaff.find(s => s.username === selectedStaff)?.full_name || selectedStaff
    : t('publicBooking.anyStaff');

  // --- MAIN LAYOUT (SPLIT VIEW) ---
  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-white font-sans text-zinc-900 selection:bg-zinc-900 selection:text-white">
      <Toaster position="top-center" richColors theme="light" />
      
      {/* LEFT PANEL (Branding & Info) 
        Desktop: Fixed sidebar on the left.
        Mobile: Top header.
      */}
      <div className="w-full lg:w-[400px] xl:w-[480px] bg-zinc-950 text-white flex flex-col justify-between p-6 lg:p-12 lg:min-h-screen lg:fixed lg:left-0 lg:top-0 z-50 shrink-0">
        <div>
           {/* Logo Area */}
          <div className="flex items-center gap-4 mb-8 lg:mb-12">
            {business.logo_url ? (
              // DEĞİŞİKLİK: w-12 h-12 yerine w-16 h-16 yapıldı (mobil için büyütüldü)
              <div className="w-16 h-16 lg:w-16 lg:h-16 bg-white rounded-xl p-1 flex items-center justify-center flex-shrink-0">
                <img 
                  src={getLogoUrl(business.logo_url)}
                  alt={business.business_name}
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              // DEĞİŞİKLİK: Placeholder için de w-16 h-16 ve ikon boyutu w-8 h-8 yapıldı
              <div className="w-16 h-16 lg:w-16 lg:h-16 bg-zinc-800 rounded-xl flex items-center justify-center flex-shrink-0 border border-zinc-700">
                <CalendarIcon className="w-8 h-8 lg:w-8 lg:h-8 text-zinc-400" />
              </div>
            )}
            <div>
              <h1 className="text-lg lg:text-xl font-bold tracking-tight text-white leading-tight">
                {business.business_name}
              </h1>
              {/* DEĞİŞİKLİK: text-sm yerine mobilde text-base, masaüstünde lg:text-sm yapıldı */}
              <p className="text-zinc-400 text-base lg:text-sm">{t('publicBooking.onlineBookingSystem')}</p>
            </div>
          </div>

          {/* Desktop Only: Welcome Text (Language aware) */}
          <div className="hidden lg:block space-y-4">
            <h2 className="text-3xl xl:text-4xl font-extrabold tracking-tight text-white">
              {currentStep === 1 && t('publicBooking.step1')}
              {currentStep === 2 && t('publicBooking.step2')}
              {currentStep === 3 && t('publicBooking.step3')}
              {currentStep === 4 && t('publicBooking.step4')}
            </h2>
            <p className="text-zinc-400 text-lg leading-relaxed max-w-xs">
               {currentStep === 1 && (currentLang === 'en' 
                 ? "Please select a service to start." 
                 : "Lütfen almak istediğiniz hizmeti seçerek başlayın.")}
                 
               {currentStep === 2 && (currentLang === 'en' 
                 ? "Choose the specialist you want to work with." 
                 : "Size yardımcı olacak uzmanı seçin.")}
                 
               {currentStep === 3 && (currentLang === 'en' 
                 ? "Select the date and time that suits you best." 
                 : "Size en uygun tarih ve saati belirleyin.")}
                 
               {currentStep === 4 && (currentLang === 'en' 
                 ? "Enter your details to confirm your appointment." 
                 : "Bilgilerinizi girerek randevunuzu onaylayın.")}
            </p>
          </div>
        </div>

        {/* Desktop Footer */}
        <div className="hidden lg:block text-zinc-500 text-xs">
          <p>© {new Date().getFullYear()} {business.business_name}</p>
          <p className="mt-1 opacity-50">Powered by PLANN</p>
        </div>
      </div>

      {/* RIGHT PANEL (Action Area) 
        Desktop: Scrollable area on the right.
        Mobile: Main content below header.
      */}
      <div className="flex-1 lg:ml-[400px] xl:ml-[480px] p-4 sm:p-6 lg:p-12 xl:p-20 bg-white min-h-screen">
        <div className="max-w-3xl mx-auto w-full">
            
            {/* Progress Bar (Minimalist & Language Aware) */}
            <div className="mb-8 lg:mb-12">
               <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wider text-zinc-500 mb-2">
                  <span>
                    {currentLang === 'en' 
                      ? `Step ${currentStep} of ${totalSteps}` 
                      : `${currentStep}. Adım / ${totalSteps}`}
                  </span>
                  <span>{Math.round((currentStep / totalSteps) * 100)}%</span>
               </div>
               <div className="h-1 w-full bg-zinc-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-zinc-900 transition-all duration-500 ease-out"
                    style={{ width: `${(currentStep / totalSteps) * 100}%` }}
                  />
               </div>
            </div>

            <form onSubmit={handleSubmit} className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              
              {/* ADIM 1: Hizmet Seçimi */}
              {currentStep === 1 && (
                <div className="space-y-6">
                  <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step1')}</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {services.map((service) => (
                      <button
                        key={service.id}
                        type="button"
                        onClick={() => {
                          setSelectedService(service);
                          setSelectedStaff(null);
                        }}
                        className={`group p-6 rounded-xl border text-left transition-all duration-200 relative flex flex-col h-full ${
                          selectedService?.id === service.id
                            ? "border-zinc-900 bg-zinc-50 ring-1 ring-zinc-900"
                            : "border-zinc-200 bg-white hover:border-zinc-400 hover:shadow-sm"
                        }`}
                      >
                        <div className="flex justify-between items-start w-full mb-3">
                           <span className={`font-bold text-lg tracking-tight ${selectedService?.id === service.id ? 'text-zinc-900' : 'text-zinc-900'}`}>
                             {service.name}
                           </span>
                           {selectedService?.id === service.id && (
                             <div className="w-6 h-6 bg-zinc-900 rounded-full flex items-center justify-center">
                               <Check className="w-3 h-3 text-white" />
                             </div>
                           )}
                        </div>
                        
                        <div className="mt-auto flex items-center justify-between w-full pt-4 border-t border-dashed border-zinc-200">
                            {settings?.show_service_duration_on_public !== false && (
                                <span className="text-sm font-medium text-zinc-500 bg-zinc-100 px-2 py-1 rounded">
                                  {(service.duration || 30)} {t('publicBooking.minutes')}
                                </span>
                            )}
                            {settings?.show_service_price_on_public !== false && (
                                <span className="text-lg font-bold text-zinc-900">
                                  {currentLang === 'en' ? `${currencySymbol}${Math.round(service.price)}` : `${Math.round(service.price)}${currencySymbol}`}
                                </span>
                            )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* ADIM 2: Personel Seçimi */}
              {currentStep === 2 && settings?.customer_can_choose_staff && (
                <div className="space-y-6 max-w-md mx-auto lg:mx-0">
                  <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step2')}</h2>
                  
                  <div className="space-y-2">
                    <Label className="text-base font-semibold text-zinc-900">
                        {currentLang === 'en' ? "Specialist Selection" : "Uzman Seçimi"}
                    </Label>
                    <Select 
                      value={selectedStaff || "any"} 
                      onValueChange={(value) => setSelectedStaff(value === "any" ? null : value)}
                    >
                      <SelectTrigger className="w-full h-14 border-zinc-200 focus:ring-zinc-900 focus:border-zinc-900 text-lg">
                        <SelectValue placeholder={t('publicBooking.selectStaff')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="any">
                          <span className="font-medium">{t('publicBooking.anyStaff')}</span>
                        </SelectItem>
                        {qualifiedStaff.map((staff) => (
                          <SelectItem key={staff.username} value={staff.username}>
                            <span className="font-medium">{staff.full_name || staff.username}</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-lg text-sm text-zinc-500 flex items-start gap-3">
                    <div className="bg-zinc-200 p-1 rounded-full"><User className="w-4 h-4 text-zinc-600"/></div>
                    <p>{t('publicBooking.anyStaffDesc')}</p>
                  </div>
                </div>
              )}

              {/* ADIM 3: Tarih & Saat */}
              {currentStep === 3 && (
                <div className="space-y-8">
                  <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step3')}</h2>
                  
                  <div className="flex flex-col lg:flex-row gap-8 items-start">
                    {/* Calendar Wrapper */}
                    <div className="w-full lg:w-auto flex justify-center lg:block">
                      <div className="p-4 border border-zinc-200 rounded-xl bg-white inline-block">
                        <Calendar
                          mode="single"
                          selected={selectedDate}
                          onSelect={(date) => {
                            if (date) {
                              setSelectedDate(date);
                              setSelectedTime("");
                            }
                          }}
                          locale={dateLocale}
                          disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                          className="p-0"
                          classNames={{
                            day_selected: "bg-zinc-900 !text-white hover:bg-zinc-800 hover:!text-white focus:bg-zinc-900 focus:!text-white",
                            day_today: "bg-zinc-100 text-zinc-900 font-bold",
                          }}
                        />
                      </div>
                    </div>

                    {/* Slots Wrapper */}
                    <div className="flex-1 w-full">
                      <div className="mb-4 flex items-center justify-between">
                         <h3 className="font-bold text-zinc-900 text-lg">
                            {selectedDate ? format(selectedDate, "d MMMM yyyy", { locale: dateLocale }) : "-"}
                         </h3>
                         <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">{t('publicBooking.availableSlots')}</span>
                      </div>
                      
                      {availableSlots.length > 0 ? (
                        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4 gap-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                          {availableSlots.map((slot) => {
                            const isSelected = selectedTime === slot;
                            return (
                              <button
                                key={slot}
                                type="button"
                                onClick={() => setSelectedTime(slot)}
                                className={`py-3 px-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
                                  isSelected
                                    ? "bg-zinc-900 text-white shadow-md scale-105"
                                    : "bg-white border border-zinc-200 text-zinc-700 hover:border-zinc-900 hover:bg-zinc-50"
                                }`}
                              >
                                {slot}
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="h-48 flex flex-col items-center justify-center border-2 border-dashed border-zinc-200 rounded-xl bg-zinc-50">
                          <Clock className="w-8 h-8 text-zinc-300 mb-2" />
                          <p className="text-zinc-500 font-medium">{t('publicBooking.noAvailableSlots')}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* ADIM 4: Onay Formu */}
              {currentStep === 4 && (
                <div className="space-y-8">
                   <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step4')}</h2>

                   <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
                      {/* Sol: Form */}
                      <div className="space-y-6">
                          {savedUser && (
                            <div className="p-4 bg-zinc-50 rounded-lg border border-zinc-200 flex items-center justify-between">
                              <div>
                                <p className="font-semibold text-zinc-900">
                                  {t('publicBooking.welcome', { name: savedUser.fullName || `${savedUser.name || ''} ${savedUser.surname || ''}` })}
                                </p>
                                <p className="text-xs text-zinc-500">
                                    {currentLang === 'en' ? "Using your saved details." : "Kayıtlı bilgileriniz kullanılıyor."}
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={handleNotMe}
                                className="text-xs font-semibold underline text-zinc-900 hover:text-zinc-600"
                              >
                                {t('publicBooking.notMe')}
                              </button>
                            </div>
                          )}

                          <div className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="fullName" className="text-zinc-900 font-semibold">{t('publicBooking.fullName')}</Label>
                              <Input
                                id="fullName"
                                value={customerFullName}
                                onChange={(e) => setCustomerFullName(e.target.value)}
                                placeholder={t('publicBooking.fullNamePlaceholder')}
                                required
                                className="h-12 border-zinc-300 focus:ring-zinc-900 focus:border-zinc-900"
                              />
                            </div>
                            
                            <div className="space-y-2">
                              <Label htmlFor="phone" className="text-zinc-900 font-semibold">{t('publicBooking.phone')}</Label>
                              <div className="relative">
                                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-500 font-medium z-10">
                                  {phonePrefix}
                                </span>
                                <Input
                                  id="phone"
                                  type="tel"
                                  value={phone}
                                  onChange={(e) => {
                                    const value = e.target.value.replace(/[^\d]/g, '').slice(0, 10);
                                    setPhone(value);
                                  }}
                                  onBlur={(e) => {
                                    const value = e.target.value.trim();
                                    if (value && !validatePhone(value)) {
                                        toast.error(isUKDomain ? t('publicBooking.phoneInvalidUK', { pattern: phonePrefix }) : t('publicBooking.phoneInvalidTR', { pattern: phonePrefix }));
                                    }
                                  }}
                                  placeholder={phonePlaceholder}
                                  required
                                  className="h-12 border-zinc-300 pl-12 focus:ring-zinc-900 focus:border-zinc-900"
                                  maxLength={10}
                                />
                              </div>
                            </div>
                            
                            {!savedUser && (
                              <div className="flex items-center space-x-2 pt-2">
                                <Checkbox
                                  id="remember"
                                  checked={rememberMe}
                                  onCheckedChange={(checked) => setRememberMe(checked)}
                                  className="data-[state=checked]:bg-zinc-900 data-[state=checked]:border-zinc-900 border-zinc-300"
                                />
                                <Label htmlFor="remember" className="text-sm font-normal cursor-pointer text-zinc-600">
                                  {t('publicBooking.rememberMe')}
                                </Label>
                              </div>
                            )}
                          </div>
                      </div>

                      {/* Sağ: Özet Kartı */}
                      <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-6 h-fit">
                          <h3 className="font-bold text-zinc-900 mb-6 text-lg tracking-tight border-b border-zinc-200 pb-4">
                            {t('publicBooking.appointmentSummary')}
                          </h3>
                          <div className="space-y-4 text-sm">
                             <div className="flex justify-between">
                                <span className="text-zinc-500">{t('publicBooking.service')}</span>
                                <span className="font-bold text-zinc-900 text-right">{selectedService?.name}</span>
                             </div>
                             <div className="flex justify-between">
                                <span className="text-zinc-500">{t('publicBooking.staff')}</span>
                                <span className="font-medium text-zinc-900 text-right">{selectedStaffName}</span>
                             </div>
                             <div className="flex justify-between">
                                <span className="text-zinc-500">{t('publicBooking.date')}</span>
                                <span className="font-medium text-zinc-900 text-right">{selectedDate ? format(selectedDate, "d MMMM yyyy", { locale: dateLocale }) : "-"}</span>
                             </div>
                             <div className="flex justify-between">
                                <span className="text-zinc-500">{t('publicBooking.time')}</span>
                                <span className="font-medium text-zinc-900 text-right bg-zinc-200 px-2 rounded text-xs py-0.5 inline-flex items-center">{selectedTime || "-"}</span>
                             </div>
                             
                             <div className="border-t border-zinc-200 pt-4 mt-4 flex justify-between items-center">
                                <span className="text-zinc-600 font-medium">{t('publicBooking.price')}</span>
                                <span className="text-2xl font-bold text-zinc-900">
                                  {selectedService ? (currentLang === 'en' ? `${currencySymbol}${Math.round(selectedService.price)}` : `${Math.round(selectedService.price)}${currencySymbol}`) : "-"}
                                </span>
                             </div>
                          </div>

                          <Button
                            type="submit"
                            disabled={submitting || !canGoNext()}
                            className="w-full mt-8 bg-zinc-900 hover:bg-black text-white font-bold h-14 text-lg shadow-none rounded-lg"
                          >
                            {submitting ? (
                                <span className="flex items-center gap-2"><Loader2 className="w-5 h-5 animate-spin"/> {t('publicBooking.creatingAppointment')}</span>
                            ) : (
                                t('publicBooking.confirmAppointment')
                            )}
                          </Button>
                      </div>
                   </div>
                </div>
              )}

              {/* Navigation Buttons */}
              <div className="flex items-center justify-between mt-12 pt-6 border-t border-zinc-100">
                <Button
                  type="button"
                  onClick={handleBack}
                  disabled={currentStep === 1}
                  variant="ghost"
                  className={`flex items-center gap-2 text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 ${currentStep === 1 ? 'invisible' : ''}`}
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>{t('publicBooking.back')}</span>
                </Button>
                
                {currentStep < totalSteps && (
                  <Button
                    type="button"
                    onClick={handleNext}
                    disabled={!canGoNext()}
                    className="flex items-center gap-2 bg-zinc-900 hover:bg-black text-white px-8 h-12 rounded-lg"
                  >
                    <span>{t('publicBooking.next')}</span>
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                )}
              </div>

            </form>
        </div>
      </div>
    </div>
  );
};

export default PublicBookingPage;