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
import BusinessMap from "./BusinessMap";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : "";
const API = `${BACKEND_URL}/api`;

const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

const PublicBookingPage = () => {
  const { slug } = useParams();
  const { t, i18n } = useTranslation();
  
  const currentLang = i18n.language || 'tr';
  const dateLocale = currentLang === 'en' ? enGB : tr;
  const currencySymbol = currentLang === 'en' ? '£' : '₺';
  
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  const isUKDomain = hostname.includes('plannapp.co.uk');
  const phonePrefix = isUKDomain ? '+44' : '+90';
  const phonePlaceholder = isUKDomain ? 'XXXX XXXXXX' : '5XX XXX XX XX';
  
  const validatePhone = (phone) => {
    const digits = phone.replace(/[^\d]/g, '');
    return digits.length === 10;
  };
  
  const reservedPaths = ['superadmin', 'dashboard', 'login', 'register', 'forgot-password', 'reset-password', 'setup-password'];
  if (reservedPaths.includes(slug)) {
    return null;
  }
  
  // STATE YÖNETİMİ
  const [currentStep, setCurrentStep] = useState(1); // Internal Step (1: Service, 2: Staff, 3: Date, 4: Info)
  
  const [loading, setLoading] = useState(true);
  const [business, setBusiness] = useState(null);
  const [services, setServices] = useState([]);
  const [staffMembers, setStaffMembers] = useState([]);
  const [settings, setSettings] = useState(null);

  const [selectedService, setSelectedService] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedTime, setSelectedTime] = useState("");
  const [availableSlots, setAvailableSlots] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [allSlots, setAllSlots] = useState([]);
  
  const [customerFullName, setCustomerFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [savedUser, setSavedUser] = useState(null);
  
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const resetTimeoutRef = useRef(null);
  const socketRef = useRef(null);

  // --- HELPER: GÖRÜNEN ADIM HESAPLAMA ---
  // Eğer personel seçimi kapalıysa toplam adım 3, açıksa 4 olmalı.
  const showStaffStep = settings?.customer_can_choose_staff ?? true; // Varsayılan true
  const totalVisualSteps = showStaffStep ? 4 : 3;

  const getVisualStepNumber = (internalStep) => {
    if (showStaffStep) return internalStep;
    
    // Personel seçimi yoksa:
    // Internal 1 (Hizmet) -> Visual 1
    // Internal 2 (Personel) -> Atlanıyor
    // Internal 3 (Tarih) -> Visual 2
    // Internal 4 (Bilgi) -> Visual 3
    if (internalStep === 1) return 1;
    if (internalStep === 3) return 2;
    if (internalStep === 4) return 3;
    return internalStep;
  };

  const currentVisualStep = getVisualStepNumber(currentStep);

  const getLogoUrl = (logoUrl) => {
    if (!logoUrl) return null;
    return logoUrl;
  };

  useEffect(() => {
    const savedUserData = localStorage.getItem('plann_user');
    if (savedUserData) {
      try {
        const userData = JSON.parse(savedUserData);
        setSavedUser(userData);
        if (userData.fullName) {
          setCustomerFullName(userData.fullName || "");
        } else if (userData.name || userData.surname) {
          const fullName = `${userData.name || ""} ${userData.surname || ""}`.trim();
          setCustomerFullName(fullName);
        }
        setPhone(userData.phone || "");
      } catch (error) {
        console.error("localStorage parse hatası:", error);
      }
    }
  }, []);

  useEffect(() => {
    loadBusinessData();
  }, [slug]);

  useEffect(() => {
    if (selectedService && selectedDate && business && currentStep >= 3) {
      loadAvailableSlots();
    }
  }, [selectedService, selectedDate, selectedStaff, business, currentStep]);

  // WebSocket
  useEffect(() => {
    if (!business || !slug) return;

    if (!socketRef.current) {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const socketUrl = BACKEND_URL || window.location.origin;
      
      const socket = io(socketUrl, {
        path: '/api/socket.io',
        transports: ['websocket', 'polling'],
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        autoConnect: true,
      });

      socketRef.current = socket;

      socket.on('connect', () => {
        socket.emit('join_public_organization', {
          slug: slug,
          organization_id: business.organization_id
        });
      });

      socket.on('appointment_created', (data) => {
        if (selectedService && selectedDate && business) {
          loadAvailableSlots();
        }
      });
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [business, slug]);

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

  const handleNotMe = () => {
    localStorage.removeItem('plann_user');
    setSavedUser(null);
    setCustomerFullName("");
    setPhone("");
  };

  const canGoNext = () => {
    switch (currentStep) {
      case 1:
        return selectedService !== null;
      case 2:
        return true; 
      case 3:
        return selectedTime !== "";
      case 4:
        return customerFullName.trim() !== "" && phone.trim() !== "";
      default:
        return false;
    }
  };

  const handleNext = () => {
    // Manuel ilerleme için standart kontrol
    if (currentStep === 1 && !showStaffStep) {
      setSelectedStaff(null); 
      setCurrentStep(3); // Adım 2'yi atla
      return;
    }
    
    if (canGoNext() && currentStep < 4) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      if (currentStep === 3 && !showStaffStep) {
        setCurrentStep(1); // Adım 2'yi atla, 1'e dön
        return;
      }
      setCurrentStep(prev => prev - 1);
    }
  };

  // --- ACTION HANDLERS WITH AUTO-ADVANCE ---
  
  // Hizmet seçildiğinde çalışır
  const handleServiceSelect = (service) => {
    setSelectedService(service);
    setSelectedStaff(null);
    
    // Çift tıklama sorununu çözmek için:
    // Doğrudan state güncellemesi beklemeden bir sonraki adıma geçişi planla
    setTimeout(() => {
        if (!showStaffStep) {
            setCurrentStep(3); // Personeli atla, Tarihe git
        } else {
            setCurrentStep(2); // Personele git
        }
    }, 300);
  };

  // Saat seçildiğinde çalışır
  const handleTimeSelect = (slot) => {
    setSelectedTime(slot);
    
    // Çift tıklama sorununu çözmek için:
    // "canGoNext" kontrolüne güvenmek yerine direkt 4. adıma atlatıyoruz.
    // Çünkü kullanıcı zaten geçerli bir saate tıkladı.
    setTimeout(() => {
        setCurrentStep(4);
    }, 300);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedService || !selectedDate || !selectedTime || !customerFullName || !phone) {
      toast.error(t('publicBooking.errorFillAll'));
      return;
    }
    
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
      
      if (rememberMe) {
        const userData = {
          fullName: fullName,
          phone: phone.trim()
        };
        localStorage.setItem('plann_user', JSON.stringify(userData));
      }
      
      setSuccess(true);
      toast.success(t('publicBooking.appointmentCreated'));
      
      if (resetTimeoutRef.current) {
        clearTimeout(resetTimeoutRef.current);
      }
      resetTimeoutRef.current = setTimeout(() => {
        resetTimeoutRef.current = null;
        setSuccess(false);
        setCurrentStep(1);
        setSelectedService(null);
        setSelectedStaff(null);
        setSelectedDate(new Date());
        setSelectedTime("");
        setAvailableSlots([]);
        setBusySlots([]);
        setAllSlots([]);
        setRememberMe(false);
      }, 20000);
    } catch (error) {
      const errorMessage = error.response?.data?.detail || t('publicBooking.errorCreateAppointment');
      toast.error(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-zinc-900" />
        <p className="mt-4 text-zinc-500 font-medium tracking-tight animate-pulse">{t('publicBooking.loading')}</p>
      </div>
    );
  }

  const qualifiedStaff = getQualifiedStaff();
  const selectedStaffName = selectedStaff
    ? qualifiedStaff.find(s => s.username === selectedStaff)?.full_name || selectedStaff
    : t('publicBooking.anyStaff');

  const resetToStart = () => {
    if (resetTimeoutRef.current) {
      clearTimeout(resetTimeoutRef.current);
      resetTimeoutRef.current = null;
    }
    setSuccess(false);
    setCurrentStep(1);
    setSelectedService(null);
    setSelectedStaff(null);
    setSelectedDate(new Date());
    setSelectedTime("");
    setAvailableSlots([]);
    setBusySlots([]);
    setAllSlots([]);
    setRememberMe(false);
  };

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

  if (success) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <Toaster position="top-center" richColors theme="light" />
        <div className="text-center max-w-2xl w-full animate-in fade-in zoom-in duration-300">
          <div className="w-20 h-20 bg-zinc-900 text-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl">
            <Check className="w-10 h-10" />
          </div>
          <h2 className="text-3xl font-bold text-zinc-900 mb-3 tracking-tight">{t('publicBooking.appointmentCreated')}</h2>
          <p className="text-zinc-500 text-lg mb-8">{t('publicBooking.appointmentCreatedDesc')}</p>

          <div className="mb-8 p-6 bg-zinc-50 rounded-xl border border-zinc-200 text-left">
            <div className="font-bold text-zinc-900 text-lg">{business.business_name}</div>
            {(business?.location?.address || settings?.address) && (
              <div className="text-sm text-zinc-500 mt-1">{business?.location?.address || settings?.address}</div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 text-sm">
              <div className="flex justify-between bg-white border border-zinc-200 rounded-lg px-3 py-2">
                <span className="text-zinc-500">{t('publicBooking.service')}</span>
                <span className="font-semibold text-zinc-900">{selectedService?.name || '-'}</span>
              </div>
              <div className="flex justify-between bg-white border border-zinc-200 rounded-lg px-3 py-2">
                <span className="text-zinc-500">{t('publicBooking.time')}</span>
                <span className="font-semibold text-zinc-900">{selectedTime || '-'}</span>
              </div>
              <div className="flex justify-between bg-white border border-zinc-200 rounded-lg px-3 py-2">
                <span className="text-zinc-500">{t('publicBooking.date')}</span>
                <span className="font-semibold text-zinc-900">{selectedDate ? format(selectedDate, "d MMMM yyyy", { locale: dateLocale }) : '-'}</span>
              </div>
              <div className="flex justify-between bg-white border border-zinc-200 rounded-lg px-3 py-2">
                <span className="text-zinc-500">{t('publicBooking.staff')}</span>
                <span className="font-semibold text-zinc-900">{selectedStaffName}</span>
              </div>
            </div>
          </div>

          {business?.location?.coordinates && (
            <div className="mb-8 text-left">
              <BusinessMap location={business.location} />
            </div>
          )}

          <div className="p-4 bg-zinc-50 rounded-lg border border-zinc-100 text-sm text-zinc-400">
             {t('publicBooking.thankYou')}
          </div>

          <div className="mt-6">
            <Button
              type="button"
              onClick={resetToStart}
              className="bg-zinc-900 hover:bg-black text-white font-bold h-12 px-6 rounded-lg"
            >
              {currentLang === 'en' ? 'Back to start' : 'Anasayfaya Dön'}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-white font-sans text-zinc-900 selection:bg-zinc-900 selection:text-white">
      <Toaster position="top-center" richColors theme="light" />
      
      {/* LEFT PANEL */}
      <div className="w-full lg:w-[400px] xl:w-[480px] bg-zinc-950 text-white flex flex-col justify-between p-6 lg:p-12 lg:min-h-screen lg:fixed lg:left-0 lg:top-0 z-50 shrink-0">
        <div>
          <div className="flex items-center gap-4 mb-8 lg:mb-12">
            {business.logo_url ? (
              <div className="w-16 h-16 lg:w-16 lg:h-16 bg-white rounded-xl p-1 flex items-center justify-center flex-shrink-0">
                <img 
                  src={getLogoUrl(business.logo_url)}
                  alt={business.business_name}
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              <div className="w-16 h-16 lg:w-16 lg:h-16 bg-zinc-800 rounded-xl flex items-center justify-center flex-shrink-0 border border-zinc-700">
                <CalendarIcon className="w-8 h-8 lg:w-8 lg:h-8 text-zinc-400" />
              </div>
            )}
            <div>
              <h1 className="text-lg lg:text-xl font-bold tracking-tight text-white leading-tight">
                {business.business_name}
              </h1>
              <p className="text-zinc-400 text-base lg:text-sm">{t('publicBooking.onlineBookingSystem')}</p>
            </div>
          </div>

          <div className="hidden lg:block space-y-4">
            <h2 className="text-3xl xl:text-4xl font-extrabold tracking-tight text-white">
              {/* BURADA currentVisualStep kullanıyoruz */}
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

        <div className="hidden lg:block text-zinc-500 text-xs">
          <p>© {new Date().getFullYear()} {business.business_name}</p>
          <p className="mt-1 opacity-50">Powered by PLANN</p>
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="flex-1 lg:ml-[400px] xl:ml-[480px] p-4 sm:p-6 lg:p-12 xl:p-20 bg-white min-h-screen">
        <div className="max-w-3xl mx-auto w-full">

            {/* BACK BUTTON */}
            <div className="mb-6 flex items-center justify-between min-h-[40px]">
                {currentVisualStep > 1 ? (
                    <Button
                        type="button"
                        onClick={handleBack}
                        variant="ghost"
                        className="flex items-center gap-2 text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 pl-0 -ml-2 transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5" />
                        <span className="text-base font-medium">{t('publicBooking.back')}</span>
                    </Button>
                ) : (
                    <div></div>
                )}
            </div>
            
            {/* Progress Bar (Visual Step Kullanımı) */}
            <div className="mb-8 lg:mb-12">
               <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wider text-zinc-500 mb-2">
                 <span>
                   {currentLang === 'en' 
                     ? `Step ${currentVisualStep} of ${totalVisualSteps}` 
                     : `${currentVisualStep}. Adım / ${totalVisualSteps}`}
                 </span>
                 <span>{Math.round((currentVisualStep / totalVisualSteps) * 100)}%</span>
               </div>
               <div className="h-1 w-full bg-zinc-100 rounded-full overflow-hidden">
                 <div 
                   className="h-full bg-zinc-900 transition-all duration-500 ease-out"
                   style={{ width: `${(currentVisualStep / totalVisualSteps) * 100}%` }}
                 />
               </div>
            </div>

            <form onSubmit={handleSubmit}>
              
              {/* ADIM 1: Hizmet Seçimi */}
              {currentStep === 1 && (
                <div key="step1" className="space-y-6 animate-in slide-in-from-right-8 fade-in duration-300">
                  <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step1')}</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {services.map((service) => (
                      <button
                        key={service.id}
                        type="button"
                        onClick={() => handleServiceSelect(service)}
                        className={`group p-6 rounded-xl border text-left transition-all duration-200 relative flex flex-col h-full ${
                          selectedService?.id === service.id
                            ? "border-zinc-900 bg-zinc-50 ring-1 ring-zinc-900 scale-[1.02]"
                            : "border-zinc-200 bg-white hover:border-zinc-400 hover:shadow-sm"
                        }`}
                      >
                        <div className="flex justify-between items-start w-full mb-3">
                           <span className={`font-bold text-lg tracking-tight ${selectedService?.id === service.id ? 'text-zinc-900' : 'text-zinc-900'}`}>
                             {service.name}
                           </span>
                           {selectedService?.id === service.id && (
                             <div className="w-6 h-6 bg-zinc-900 rounded-full flex items-center justify-center animate-in zoom-in duration-200">
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

              {/* ADIM 2: Personel Seçimi (Sadece ayar açıksa gösterilir) */}
              {currentStep === 2 && showStaffStep && (
                <div key="step2" className="space-y-6 max-w-md mx-auto lg:mx-0 animate-in slide-in-from-right-8 fade-in duration-300">
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
                <div key="step3" className="space-y-8 animate-in slide-in-from-right-8 fade-in duration-300">
                  <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step3')}</h2>
                  
                  <div className="flex flex-col lg:flex-row gap-8 items-start">
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
                                onClick={() => handleTimeSelect(slot)}
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
                <div key="step4" className="space-y-8 animate-in slide-in-from-right-8 fade-in duration-300">
                    <h2 className="lg:hidden text-2xl font-bold text-zinc-900 tracking-tight">{t('publicBooking.step4')}</h2>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
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

              {currentStep === 2 && (
                  <div className="flex items-center justify-end mt-12 pt-6 border-t border-zinc-100">
                      <Button
                        type="button"
                        onClick={handleNext}
                        disabled={!canGoNext()}
                        className="flex items-center gap-2 bg-zinc-900 hover:bg-black text-white px-8 h-12 rounded-lg"
                      >
                        <span>{t('publicBooking.next')}</span>
                        <ArrowRight className="w-4 h-4" />
                      </Button>
                  </div>
              )}

            </form>
        </div>
      </div>
    </div>
  );
};

export default PublicBookingPage;