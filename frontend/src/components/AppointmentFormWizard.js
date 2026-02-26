import { useState, useEffect, useRef, useMemo } from "react";
import { format, addDays, isSameDay } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import { Calendar as CalendarIcon, Clock, ArrowLeft, User, Search, X, Check, UserPlus, ChevronLeft, Loader2, Users, Import } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import axios from "axios";

// --- REHBER & TİTREŞİM ENTEGRASYONU ---
import { Capacitor } from '@capacitor/core';
import { Contacts } from '@capacitor-community/contacts';
import { Haptics, NotificationType } from '@capacitor/haptics'; // TİTREŞİM EKLENDİ
// --------------------------------------

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : "";
const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

const AppointmentFormWizard = ({ services, appointment, onSave, onCancel }) => {
  const { userRole, canViewAll } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  const dateScrollerRef = useRef(null);
  
  // State Yönetimi
  const [step, setStep] = useState(1);
  const [currentUser, setCurrentUser] = useState(null);
  const [allStaff, setAllStaff] = useState([]);
  const [settings, setSettings] = useState(null);
  
  // Form Verileri
  const [formData, setFormData] = useState({
    customer_name: "",
    phone: "",
    service_id: "",
    appointment_date: new Date(),
    appointment_time: "",
    staff_member_id: "",
    notes: ""
  });

  // Data States
  const [availableSlots, setAvailableSlots] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Filtrelemeler
  const [filteredServices, setFilteredServices] = useState([]);
  const [qualifiedStaff, setQualifiedStaff] = useState([]);

  // Hizmet Arama
  const [serviceSearchTerm, setServiceSearchTerm] = useState("");
  const [debouncedServiceSearchTerm, setDebouncedServiceSearchTerm] = useState("");
  
  // Müşteri Arama
  const [customers, setCustomers] = useState([]);
  const [customerSearchTerm, setCustomerSearchTerm] = useState("");
  const [debouncedCustomerSearchTerm, setDebouncedCustomerSearchTerm] = useState("");
  const [isNewCustomerMode, setIsNewCustomerMode] = useState(false);
  const customerListRef = useRef(null);
  const [customerListScrollTop, setCustomerListScrollTop] = useState(0);

  // --- REHBER ENTEGRASYONU STATE'LERİ ---
  const [importingContacts, setImportingContacts] = useState(false);
  const [showContactSelectionDialog, setShowContactSelectionDialog] = useState(false);
  const [fetchedContacts, setFetchedContacts] = useState([]);
  const [contactSearchTerm, setContactSearchTerm] = useState("");
  const [selectedContactPhones, setSelectedContactPhones] = useState(new Set());
  const [showNotSupportedDialog, setShowNotSupportedDialog] = useState(false);
  // ---------------------------------------

  // --- INIT & LOADERS ---

  useEffect(() => {
    loadCurrentUser();
    loadAllStaff();
    loadSettings();
    loadCustomers();
    if (appointment) {
      setFormData({
        customer_name: appointment.customer_name,
        phone: appointment.phone,
        service_id: appointment.service_id,
        appointment_date: new Date(appointment.appointment_date),
        appointment_time: appointment.appointment_time,
        staff_member_id: appointment.staff_member_id || "",
        notes: appointment.notes || ""
      });
      setStep(3);
    }
  }, [appointment]);

  useEffect(() => {
    if (formData.service_id && formData.appointment_date && step === 3) {
      loadAvailableSlots();
    }
  }, [formData.service_id, formData.appointment_date, formData.staff_member_id, step]);

  useEffect(() => {
    if (userRole === 'staff' && !canViewAll && currentUser && services.length > 0) {
      const allowed = services.filter(s => currentUser.permitted_service_ids?.includes(s.id));
      setFilteredServices(allowed);
    } else {
      setFilteredServices(services);
    }
  }, [userRole, currentUser, services]);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedServiceSearchTerm(serviceSearchTerm), 150);
    return () => clearTimeout(id);
  }, [serviceSearchTerm]);

  const visibleServices = useMemo(() => {
    const raw = filteredServices || [];
    const search = (debouncedServiceSearchTerm || "").toLowerCase();
    if (!search) return raw;
    return raw.filter((s) => String(s?.name || "").toLowerCase().includes(search));
  }, [filteredServices, debouncedServiceSearchTerm]);

  const currencySymbol = useMemo(() => {
    const phone = (settings?.support_phone || '').replace(/\s/g, '');
    return (phone.startsWith('+44') || phone.startsWith('44')) ? '£' : '₺';
  }, [settings]);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedCustomerSearchTerm(customerSearchTerm), 150);
    return () => clearTimeout(id);
  }, [customerSearchTerm]);

  const filteredCustomers = useMemo(() => {
    const raw = customers || [];
    const search = (debouncedCustomerSearchTerm || "").toLowerCase();
    const phoneSearch = String(debouncedCustomerSearchTerm || "");

    const filtered = search
      ? raw.filter((c) => {
          const name = (c?.name || "").toLowerCase();
          const phone = String(c?.phone || "");
          return name.includes(search) || phone.includes(phoneSearch);
        })
      : raw;

    const locale = i18n.language === 'tr' ? 'tr-TR' : 'en-GB';
    return filtered
      .slice()
      .sort((a, b) => {
        const aName = String(a?.name || "");
        const bName = String(b?.name || "");
        return aName.localeCompare(bName, locale, { sensitivity: 'base' });
      });
  }, [customers, debouncedCustomerSearchTerm, i18n.language]);

  useEffect(() => {
    if (formData.service_id && allStaff.length > 0) {
      let qualified = allStaff.filter(s => s.permitted_service_ids?.includes(formData.service_id));
      if (settings && !settings.admin_provides_service) {
        qualified = qualified.filter(s => s.role !== 'admin');
      }
      setQualifiedStaff(qualified);
    }
  }, [formData.service_id, allStaff, settings]);

  // --- API CALLS ---

  const loadCurrentUser = async () => {
    if (userRole === 'staff' && !canViewAll) {
      try {
        const res = await api.get("/users");
        const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
        if (token) {
          const payload = JSON.parse(atob(token.split('.')[1]));
          const user = res.data.find(u => u.username === payload.sub);
          setCurrentUser(user);
          if (user) setFormData(prev => ({ ...prev, staff_member_id: user.username }));
        }
      } catch (e) { console.error(e); }
    }
  };

  const loadAllStaff = async () => {
    try { const res = await api.get("/users"); setAllStaff(res.data || []); } catch (e) { console.error(e); }
  };
  const loadCustomers = async () => {
    try { const res = await api.get("/customers"); setCustomers(res.data || []); } catch (e) { console.error(e); }
  };
  const loadSettings = async () => {
    try { const res = await api.get("/settings"); setSettings(res.data); } catch (e) { console.error(e); }
  };

  const loadAvailableSlots = async () => {
    if (!formData.service_id || !formData.appointment_date || !settings) return;
    try {
      const dateStr = format(formData.appointment_date, "yyyy-MM-dd");
      const params = { service_id: formData.service_id, date: dateStr };
      if (formData.staff_member_id) params.staff_id = formData.staff_member_id;

      let res;
      if (userRole === 'admin' || canViewAll) {
        res = await api.get('/availability', { params });
      } else {
        const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
        if (!token) return;
        const orgId = JSON.parse(atob(token.split('.')[1])).org_id;
        res = await publicApi.get(`/public/availability/${orgId}`, { params });
      }
      setAvailableSlots(res.data.available_slots || []);
      setBusySlots(res.data.busy_slots || []);
    } catch (e) {
      console.error(e);
      setAvailableSlots([]);
    }
  };

  // --- HANDLERS ---

  // --- REHBER İŞLEMLERİ ---
  const handleImportFromContacts = async () => {
    const isSupported = Capacitor.isNativePlatform() || 
                        ('contacts' in navigator && 'ContactsManager' in window);
    
    if (!isSupported) {
      setShowNotSupportedDialog(true);
      return;
    }

    if (Capacitor.isNativePlatform()) {
      setImportingContacts(true);
      try {
        const permission = await Contacts.requestPermissions();
        if (permission.contacts !== 'granted' && permission.contacts !== 'limited') {
          toast.error("İzin verilmedi.");
          setImportingContacts(false);
          return;
        }

        const result = await Contacts.getContacts({
          projection: { name: true, phones: true }
        });

        if (!result.contacts || result.contacts.length === 0) {
          toast.info("Rehber boş.");
          setImportingContacts(false);
          return;
        }

        const normalizedContacts = result.contacts
          .map(c => ({
            name: c.name?.display || (c.name?.given + " " + (c.name?.family || "")),
            phone: c.phones?.[0]?.number
          }))
          .filter(c => c.name && c.phone);

        setFetchedContacts(normalizedContacts);
        setSelectedContactPhones(new Set());
        setContactSearchTerm("");
        setShowContactSelectionDialog(true);
        setImportingContacts(false);

      } catch (error) {
        console.error(error);
        toast.error("Rehber okunurken hata oluştu.");
        setImportingContacts(false);
      }
    }
    else if ('contacts' in navigator && 'ContactsManager' in window) {
      setImportingContacts(true);
      try {
        const webContacts = await navigator.contacts.select(['name', 'tel'], { multiple: true });
        if (webContacts && webContacts.length > 0) {
          const normalized = webContacts.map(c => ({
            name: c.name?.[0],
            phone: c.tel?.[0]
          })).filter(c => c.name && c.phone);
          
          setFetchedContacts(normalized);
          setSelectedContactPhones(new Set());
          setContactSearchTerm("");
          setShowContactSelectionDialog(true);
        }
        setImportingContacts(false);
      } catch (e) {
        setImportingContacts(false);
        toast.error("Rehber erişimi başarısız.");
      }
    }
  };

  const toggleContactSelection = (phone) => {
    const newSet = new Set(selectedContactPhones);
    if (newSet.has(phone)) {
      newSet.delete(phone);
    } else {
      newSet.add(phone);
    }
    setSelectedContactPhones(newSet);
  };

  const filteredFetchedContacts = fetchedContacts.filter(contact => 
    contact.name.toLowerCase().includes(contactSearchTerm.toLowerCase()) || 
    contact.phone.replace(/\D/g, "").includes(contactSearchTerm)
  );

  const handleSelectFromContacts = () => {
    const selectedList = fetchedContacts.filter(c => selectedContactPhones.has(c.phone));
    
    if (selectedList.length === 0) {
      toast.warning("Lütfen en az bir kişi seçin.");
      return;
    }

    const firstContact = selectedList[0];
    let cleanPhone = firstContact.phone.replace(/\D/g, "");
    if (cleanPhone.length === 10) cleanPhone = '90' + cleanPhone;
    else if (cleanPhone.length === 11 && cleanPhone.startsWith('0')) cleanPhone = '90' + cleanPhone.substring(1);

    setFormData(prev => ({
      ...prev,
      customer_name: firstContact.name.trim(),
      phone: cleanPhone
    }));

    setShowContactSelectionDialog(false);
    toast.success(`${firstContact.name} seçildi`);
  };
  // ------------------------------

  const handleSubmit = async () => {
    if (!formData.customer_name || !formData.phone || !formData.service_id || !formData.appointment_time) {
      // Hata titreşimi
      try { await Haptics.notification({ type: NotificationType.Error }); } catch (e) {}
      toast.error(t('appointments.form.fillRequiredFields'));
      return;
    }
    
    setLoading(true);
    
    try {
      const payload = { ...formData, appointment_date: format(formData.appointment_date, "yyyy-MM-dd") };
      if (userRole === 'staff' && !canViewAll && currentUser && !payload.staff_member_id) payload.staff_member_id = currentUser.username;
      if (!payload.staff_member_id) delete payload.staff_member_id;

      if (appointment) {
        await api.put(`/appointments/${appointment.id}`, payload);
        toast.success(t('appointments.form.updated'));
      } else {
        await api.post("/appointments", payload);
        toast.success(t('appointments.form.created'));
        await loadCustomers();
      }

      // --- BAŞARILI İŞLEM TİTREŞİMİ (BURASI YENİ) ---
      try {
        await Haptics.notification({ type: NotificationType.Success });
      } catch (e) {
        console.log("Haptic error", e);
      }
      // ----------------------------------------------

      await new Promise(r => setTimeout(r, 500));
      onSave();
    } catch (error) {
      // --- HATA TİTREŞİMİ ---
      try { await Haptics.notification({ type: NotificationType.Error }); } catch (e) {}
      // ---------------------
      
      toast.error(error.response?.data?.detail || t('appointments.form.operationFailed'));
    } finally {
      setLoading(false);
    }
  };

  // --- RENDER STEPS ---

  // ADIM 1: HİZMET SEÇİMİ
  const renderStep1 = () => (
    <div className="space-y-4 animate-in slide-in-from-right duration-300 pb-20">
        <div className="relative">
          <Search className="absolute left-3 top-3.5 h-5 w-5 text-zinc-400" />
          <Input 
            placeholder={t('appointments.form.searchService', 'Hizmet ara...')} 
            value={serviceSearchTerm}
            onChange={(e) => setServiceSearchTerm(e.target.value)}
            className="pl-10 h-12 backdrop-blur-md bg-white/50 md:bg-white/75 border-black rounded-xl focus:ring-zinc-900 shadow-sm"
          />
        </div>
      <div className="grid grid-cols-1 gap-3">
        {visibleServices.map((service) => (
          <div 
            key={service.id}
            onClick={() => {
              setFormData(prev => ({ ...prev, service_id: service.id }));
              setStep(2);
            }}
            className={`group p-5 backdrop-blur-xl border rounded-2xl shadow-lg hover:shadow-xl cursor-pointer transition-all duration-300 active:scale-[0.99] flex justify-between items-center
              ${formData.service_id === service.id 
                ? 'bg-zinc-900/90 border-zinc-900 text-white' 
                : 'bg-white/40 md:bg-white/70 border-white/20 hover:bg-white/60 md:hover:bg-white/80 hover:border-white/40'}
            `}
          >
            <div>
              <h3 className={`font-bold ${formData.service_id === service.id ? 'text-white' : 'text-zinc-900'}`}>
                {service.name}
              </h3>
              <p className={`text-sm mt-1 font-medium ${formData.service_id === service.id ? 'text-zinc-200' : 'text-zinc-500'}`}>
{i18n.language === 'en' ? `${currencySymbol}${Math.round(service.price)}` : `${Math.round(service.price)}${currencySymbol}`} • {service.duration || 30} {t('appointments.form.durationUnit')}
              </p>
            </div>
            <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center transition-all duration-300
              ${formData.service_id === service.id 
                ? 'border-white bg-white' 
                : 'border-zinc-200 group-hover:border-zinc-400'}
            `}>
              {formData.service_id === service.id && <Check className="w-4 h-4 text-zinc-900" strokeWidth={3} />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // ADIM 2: MÜŞTERİ SEÇİMİ
  const renderStep2 = () => {
    const LIST_HEIGHT = 420;
    const ITEM_HEIGHT = 78;
    const OVERSCAN = 6;

    const total = filteredCustomers.length;
    const startIndex = Math.max(0, Math.floor(customerListScrollTop / ITEM_HEIGHT) - OVERSCAN);
    const endIndex = Math.min(total, Math.ceil((customerListScrollTop + LIST_HEIGHT) / ITEM_HEIGHT) + OVERSCAN);
    const visible = filteredCustomers.slice(startIndex, endIndex);
    const offsetY = startIndex * ITEM_HEIGHT;
    const totalHeight = total * ITEM_HEIGHT;

    return (
      <div className="space-y-6 animate-in slide-in-from-right duration-300 pb-20">
        <div className="relative">
           <Search className="absolute left-4 top-3.5 h-5 w-5 text-zinc-400" />
           <input 
             value={customerSearchTerm}
             onChange={(e) => {
               setCustomerSearchTerm(e.target.value);
               setCustomerListScrollTop(0);
               if (customerListRef.current) {
                 customerListRef.current.scrollTop = 0;
               }
               if(isNewCustomerMode) setIsNewCustomerMode(false);
             }}
             placeholder={t('appointments.form.searchCustomer')}
             className="w-full pl-12 pr-4 py-3 backdrop-blur-xl bg-white/40 border border-white/30 rounded-xl focus:ring-2 focus:ring-zinc-900 focus:bg-white/60 outline-none transition-all shadow-sm"
           />
        </div>

        {isNewCustomerMode ? (
          <>
            {/* Manuel Müşteri Ekleme Kartı */}
            <div className="p-5 backdrop-blur-xl bg-zinc-50/50 border border-white/30 rounded-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200 shadow-lg">
              <div className="flex justify-between items-center">
                <h4 className="font-bold text-zinc-900">{t('appointments.form.newCustomer')}</h4>
                <button onClick={() => setIsNewCustomerMode(false)} className="p-1.5 hover:bg-white/50 rounded-lg transition-colors">
                  <X className="w-5 h-5 text-zinc-500"/>
                </button>
              </div>
              <Input 
                placeholder={t('customers.fields.name')} 
                value={formData.customer_name}
                onChange={(e) => setFormData(prev => ({...prev, customer_name: e.target.value}))}
                className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
              />
              <Input 
                placeholder={i18n.language === 'en' ? '+44...' : '05...'}
                value={formData.phone}
                onChange={(e) => {
                  let val = e.target.value.replace(/[^0-9+]/g, '');
                  const digits = val.replace(/[^0-9]/g, '');
                  if (digits.length <= 11) {
                    setFormData(prev => ({...prev, phone: val}));
                  }
                }}
                className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                maxLength={12}
              />
              <Button className="w-full bg-zinc-900 hover:bg-black h-12 rounded-xl font-bold shadow-lg" onClick={() => {
                if(formData.customer_name && formData.phone) setStep(3);
                else toast.error(t('appointments.form.fillRequiredFields'));
              }}>
                {t('common.continue')}
              </Button>
            </div>

            {/* Rehberden Ekle Kartı */}
            <div className="p-6 backdrop-blur-xl bg-white/40 border border-white/30 rounded-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200 shadow-lg">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-md">
                  <Import className="w-7 h-7 text-white" />
                </div>
                <div>
                  <h4 className="font-bold text-zinc-900 text-base">{t('appointments.form.importFromContacts')}</h4>
                  <p className="text-sm text-zinc-600 font-medium">{t('appointments.form.importFromContactsDesc')}</p>
                </div>
              </div>
              <Button 
                onClick={handleImportFromContacts}
                disabled={importingContacts}
                className="w-full backdrop-blur-md bg-white/60 border-2 border-white/40 hover:bg-white/80 text-zinc-900 h-14 rounded-xl font-bold shadow-sm hover:shadow-md transition-all text-base"
                variant="outline"
              >
                {importingContacts ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    {t('appointments.form.loading')}
                  </>
                ) : (
                  <>
                    <Users className="w-5 h-5 mr-2" />
                    {t('appointments.form.selectFromContacts')}
                  </>
                )}
              </Button>
            </div>
          </>
        ) : (
          <button 
            onClick={() => { setIsNewCustomerMode(true); setFormData(prev => ({...prev, customer_name: "", phone: ""})); }}
            className="w-full py-4 flex items-center justify-center gap-2 border-2 border-dashed border-zinc-300 rounded-2xl text-zinc-600 font-bold hover:bg-white/50 hover:border-zinc-400 transition-all backdrop-blur-sm shadow-sm"
          >
            <UserPlus className="h-5 w-5" />
            <span>{t('appointments.form.newCustomer')}</span>
          </button>
        )}

        {!isNewCustomerMode && (
          <div
            ref={customerListRef}
            onScroll={(e) => setCustomerListScrollTop(e.currentTarget.scrollTop)}
            className="max-h-[420px] overflow-y-auto pr-1"
            style={{ height: LIST_HEIGHT }}
          >
            <div style={{ height: totalHeight, position: 'relative' }}>
              <div style={{ transform: `translateY(${offsetY}px)` }} className="space-y-3">
                {visible.map((c) => (
                  <div
                    key={c.phone}
                    onClick={() => {
                      setFormData((prev) => ({ ...prev, customer_name: c.name, phone: c.phone }));
                      setStep(3);
                    }}
                    className="flex items-center justify-between p-4 backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl hover:bg-white/60 hover:border-white/40 hover:shadow-lg cursor-pointer group transition-all duration-300"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-xl backdrop-blur-md bg-zinc-500/10 border border-white/30 flex items-center justify-center text-zinc-700 font-bold text-lg group-hover:bg-zinc-900 group-hover:text-white transition-all duration-300 shadow-sm">
                        {(c.name || '').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-bold text-zinc-900">{c.name}</p>
                        <p className="text-xs text-zinc-500 font-medium">{c.phone}</p>
                      </div>
                    </div>
                    <Check className={`w-5 h-5 transition-colors ${formData.phone === c.phone ? 'text-zinc-900' : 'text-zinc-300'}`} strokeWidth={2.5} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ADIM 3: TARİH VE SAAT
  const renderStep3 = () => {
    const days = Array.from({ length: 14 }, (_, i) => addDays(new Date(), i));
    const scrollDatesBy = (delta) => {
      const el = dateScrollerRef.current;
      if (!el) return;
      el.scrollBy({ left: delta, behavior: 'smooth' });
    };

    const handleDateScrollerWheel = (e) => {
      const el = dateScrollerRef.current;
      if (!el) return;
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    };

    // Tüm saatleri birleştir ve sırala
    const allSlots = [...new Set([...availableSlots, ...busySlots])].sort();

    return (
      <div className="space-y-8 animate-in slide-in-from-right duration-300 pb-24">
        
        {/* Personel Seçimi */}
        {(userRole === 'admin' || canViewAll) && qualifiedStaff.length > 0 && (
          <div>
             <label className="block text-sm font-bold text-zinc-700 mb-3 uppercase tracking-wider">{t('appointments.form.selectStaff')}</label>
             <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                <button
                   type="button"
                   onClick={() => setFormData(prev => ({ ...prev, staff_member_id: "" }))}
                   className={`px-4 py-2.5 rounded-xl border text-sm font-bold whitespace-nowrap transition-all shadow-sm backdrop-blur-md
                     ${!formData.staff_member_id 
                       ? 'bg-zinc-900 text-white border-zinc-900 shadow-lg' 
                       : 'bg-white/40 text-zinc-600 border-white/30 hover:bg-white/60'}
                   `}
                >
                   {t('appointments.form.autoAssign')}
                </button>
                {qualifiedStaff.map(staff => (
                   <button
                     key={staff.username}
                     type="button"
                     onClick={() => setFormData(prev => ({ ...prev, staff_member_id: staff.username }))}
                     className={`px-4 py-2.5 rounded-xl border text-sm font-bold whitespace-nowrap transition-all flex items-center gap-2 shadow-sm backdrop-blur-md
                       ${formData.staff_member_id === staff.username 
                         ? 'bg-zinc-900 text-white border-zinc-900 shadow-lg' 
                         : 'bg-white/40 text-zinc-600 border-white/30 hover:bg-white/60'}
                     `}
                   >
                     {staff.full_name || staff.username}
                   </button>
                ))}
             </div>
          </div>
        )}

        {/* YATAY TAKVİM */}
        <div>
           <div className="flex justify-between items-center mb-4">
             <h3 className="font-bold text-zinc-900 uppercase tracking-wider text-sm">{format(formData.appointment_date, "MMMM yyyy", { locale: dateLocale })}</h3>
           </div>
           <div className="relative overflow-hidden py-2">
             <button
               type="button"
               onClick={() => scrollDatesBy(-320)}
               className="hidden md:flex absolute left-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 items-center justify-center rounded-full backdrop-blur-md bg-white/80 border border-white/30 shadow-lg hover:bg-white transition-all"
               aria-label="Scroll dates left"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700" />
             </button>
             <button
               type="button"
               onClick={() => scrollDatesBy(320)}
               className="hidden md:flex absolute right-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 items-center justify-center rounded-full backdrop-blur-md bg-white/80 border border-white/30 shadow-lg hover:bg-white transition-all"
               aria-label="Scroll dates right"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700 rotate-180" />
             </button>

             <div
               ref={dateScrollerRef}
               onWheel={handleDateScrollerWheel}
               className="flex gap-3 overflow-x-auto pb-4 scrollbar-hide px-2 md:px-12"
             >
             {days.map((date, i) => {
               const isSelected = isSameDay(date, formData.appointment_date);
               return (
                 <button 
                  type="button"
                  key={i}
                  onClick={() => setFormData(prev => ({ ...prev, appointment_date: date, appointment_time: "" }))}
                  className={`flex flex-col items-center justify-center min-w-[72px] h-[84px] rounded-2xl border transition-all duration-300 shrink-0 shadow-sm
                    ${isSelected 
                      ? 'bg-zinc-900 border-zinc-900 text-white shadow-xl' 
                      : 'backdrop-blur-xl bg-white/40 border-white/30 text-zinc-600 hover:bg-white/60 hover:border-white/40 hover:shadow-lg'}
                  `}
                >
                   <span className={`text-xs font-bold mb-1 uppercase tracking-wider ${isSelected ? 'text-zinc-300' : 'text-zinc-400'}`}>
                     {format(date, "EEE", { locale: dateLocale })}
                   </span>
                   <span className="text-2xl font-black">{format(date, "d")}</span>
                 </button>
               )
             })}
             </div>
           </div>
        </div>

        {/* SAAT GRID */}
        <div>
          <h3 className="font-bold text-zinc-900 mb-4 uppercase tracking-wider text-sm">{t('appointments.form.appointmentTime')}</h3>
          {allSlots.length === 0 ? (
             <div className="text-center p-8 border-2 border-dashed border-zinc-200 rounded-2xl backdrop-blur-sm bg-white/30">
                <Clock className="w-10 h-10 mx-auto mb-3 text-zinc-300"/>
                <p className="text-sm text-zinc-500 font-medium">{t('appointments.form.noAvailableSlots')}</p>
             </div>
          ) : (
            <div className="grid grid-cols-4 gap-3">
              {allSlots.map((time) => {
                const isAvailable = availableSlots.includes(time);
                const isBusy = busySlots.includes(time);
                const isSelected = formData.appointment_time === time;
                
                return (
                  <button
                    key={time}
                    type="button"
                    onClick={() => isAvailable && setFormData(prev => ({ ...prev, appointment_time: time }))}
                    disabled={isBusy}
                    className={`py-3 rounded-xl text-sm font-bold transition-all duration-300 border shadow-sm relative
                      ${isSelected 
                        ? 'bg-blue-600 border-blue-600 text-white shadow-lg scale-105' 
                        : isBusy 
                          ? 'bg-zinc-200/80 border-zinc-300/80 text-zinc-400 cursor-not-allowed line-through'
                          : 'backdrop-blur-xl bg-white/40 border-white/30 text-zinc-700 hover:bg-white/60 hover:border-white/40 hover:shadow-md'}
                    `}
                  >
                    {time}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* NOTLAR */}
        <div>
           <label className="block text-sm font-bold text-zinc-700 mb-3 uppercase tracking-wider">{t('appointments.form.notes')}</label>
           <textarea 
             className="w-full p-4 backdrop-blur-xl bg-white/40 border border-white/30 rounded-2xl focus:ring-2 focus:ring-zinc-900 focus:bg-white/60 outline-none text-sm font-medium transition-all shadow-sm"
             rows="3"
             placeholder={t('appointments.form.notesPlaceholder')}
             value={formData.notes}
             onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
           />
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-white md:bg-black/35 md:backdrop-blur-[1px] md:flex md:items-center md:justify-center p-0 md:p-4 animate-in fade-in duration-200">
      <div className="w-full h-full md:h-auto md:max-h-[90vh] md:max-w-[500px] bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 md:from-gray-50/40 md:via-white md:to-white md:rounded-[32px] md:shadow-2xl flex flex-col overflow-hidden relative">
        
        {/* HEADER */}
        <div className="px-6 pt-12 pb-4 md:pt-6 border-b border-white/20 flex items-center justify-between backdrop-blur-2xl bg-white/70 sticky top-0 z-20 shrink-0 shadow-sm">
          <div className="flex items-center gap-4">
            {step > 1 ? (
              <button onClick={() => setStep(step - 1)} className="p-2 -ml-2 hover:bg-white/50 rounded-xl transition-all duration-300">
                <ChevronLeft className="w-6 h-6 text-zinc-900" strokeWidth={2} />
              </button>
            ) : (
              <button onClick={onCancel} className="p-2 -ml-2 hover:bg-white/50 rounded-xl transition-all duration-300 md:hidden">
                 <X className="w-6 h-6 text-zinc-900" strokeWidth={2} />
              </button>
            )}
            <div>
              <h1 className="text-lg font-bold text-zinc-900 leading-tight">
                {step === 1 && t('appointments.form.selectService')}
                {step === 2 && t('appointments.form.selectCustomer')}
                {step === 3 && t('appointments.form.appointmentDate')}
              </h1>
              <p className="text-xs text-zinc-500 font-bold tracking-wider mt-0.5 uppercase">
                 {t('common.step')} {step}/3
              </p>
            </div>
          </div>
          <button onClick={onCancel} className="p-2 backdrop-blur-md bg-white/50 rounded-xl hover:bg-white/70 transition-all duration-300 hidden md:block shadow-sm">
            <X className="w-5 h-5 text-zinc-600" strokeWidth={2} />
          </button>
        </div>

        {/* PROGRESS BAR */}
        <div className="h-1 w-full bg-zinc-100/50 shrink-0">
          <div className="h-full bg-zinc-900 transition-all duration-500 ease-out shadow-sm" style={{ width: `${(step / 3) * 100}%` }} />
        </div>

        {/* CONTENT */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
        </div>

        {/* FOOTER ACTION */}
        {step === 3 && (
          <div className="p-6 backdrop-blur-2xl bg-white/80 border-t border-white/20 z-20 shrink-0 shadow-lg">
             <div className="flex justify-between items-center mb-4 text-sm">
                <span className="text-zinc-500 font-bold uppercase tracking-wider">{t('common.total')}</span>
                <span className="text-2xl font-black text-zinc-900">
                   {i18n.language === 'en'
                     ? `${currencySymbol}${Math.round(filteredServices.find(s => s.id === formData.service_id)?.price || 0)}`
                     : `${Math.round(filteredServices.find(s => s.id === formData.service_id)?.price || 0)}${currencySymbol}`}
                </span>
             </div>
             <Button 
               onClick={handleSubmit}
               disabled={loading || !formData.appointment_time}
               className="w-full bg-zinc-900 text-white font-bold text-base h-14 rounded-2xl shadow-xl hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed"
             >
               {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : (
                 <span className="flex items-center gap-2">
                    <Check className="w-5 h-5" strokeWidth={2.5} /> {appointment ? t('appointments.form.update') : t('appointments.form.save')}
                 </span>
               )}
             </Button>
          </div>
        )}
      </div>

      {/* Kişi Seçim Dialog */}
      <Dialog open={showContactSelectionDialog} onOpenChange={setShowContactSelectionDialog}>
        <DialogContent className="h-[80vh] flex flex-col sm:max-w-md p-0 overflow-hidden backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <DialogHeader className="px-6 py-4 border-b border-white/30 pr-12">
            <DialogTitle className="flex flex-col space-y-1">
              <span className="font-black text-zinc-900">{t('appointments.form.contactDialog.title')}</span>
              <span className="text-xs font-bold text-zinc-600">
                {t('appointments.form.contactDialog.selected', { count: selectedContactPhones.size })}
              </span>
            </DialogTitle>
          </DialogHeader>
          
          {/* Arama Alanı */}
          <div className="px-6 py-3 border-b border-white/30 backdrop-blur-md bg-white/50">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <Input 
                placeholder={t('appointments.form.contactDialog.search')} 
                value={contactSearchTerm}
                onChange={(e) => setContactSearchTerm(e.target.value)}
                className="pl-9 h-10 backdrop-blur-md bg-white/60 border-white/40 rounded-xl font-medium"
              />
            </div>
          </div>
          
          {/* Liste Alanı */}
          <div className="flex-1 overflow-y-auto px-6 py-2">
            {filteredFetchedContacts.length === 0 ? (
              <p className="text-center text-zinc-500 py-8 font-medium">{t('appointments.form.contactDialog.noResults')}</p>
            ) : (
              filteredFetchedContacts.map((contact, index) => {
                const isSelected = selectedContactPhones.has(contact.phone);
                return (
                  <div 
                    key={index}
                    className={`flex items-center justify-between py-3 border-b border-white/30 cursor-pointer transition-colors ${isSelected ? 'bg-blue-50/50' : 'hover:bg-white/50'}`}
                    onClick={() => toggleContactSelection(contact.phone)}
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${isSelected ? 'bg-blue-600 border-blue-600' : 'border-zinc-300 bg-white'}`}>
                        {isSelected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                      </div>
                      
                      <div className="flex flex-col truncate">
                        <span className="font-bold text-zinc-900 truncate">{contact.name}</span>
                        <span className="text-xs text-zinc-500 font-medium">{contact.phone}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t border-white/30 backdrop-blur-md bg-white/50">
            <Button variant="outline" onClick={() => setShowContactSelectionDialog(false)} className="mr-2 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">
              {t('appointments.form.contactDialog.cancel')}
            </Button>
            <Button onClick={handleSelectFromContacts} className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg">
              {t('appointments.form.contactDialog.useSelected', { count: selectedContactPhones.size })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Desteklenmiyor Dialog */}
      <Dialog open={showNotSupportedDialog} onOpenChange={setShowNotSupportedDialog}>
        <DialogContent className="sm:max-w-md backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <DialogHeader className="border-b border-zinc-200 pb-4">
            <DialogTitle className="text-xl font-black text-zinc-900">{t('appointments.form.contactDialog.notSupported')}</DialogTitle>
          </DialogHeader>
          <div className="py-6 space-y-4">
            <p className="text-sm text-zinc-700 font-medium leading-relaxed">
              {t('appointments.form.contactDialog.notSupportedDesc')}
            </p>
            
            <div className="space-y-3">
              <p className="text-xs font-bold text-zinc-900 uppercase tracking-wider">{t('appointments.form.contactDialog.worksOn')}</p>
              <ul className="space-y-2">
                <li className="flex items-start gap-2 text-sm text-zinc-700">
                  <span className="text-zinc-400 mt-0.5">•</span>
                  <span className="font-medium">{t('appointments.form.contactDialog.worksOnAndroid')}</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-zinc-700">
                  <span className="text-zinc-400 mt-0.5">•</span>
                  <span className="font-medium">{t('appointments.form.contactDialog.worksOnApp')}</span>
                </li>
              </ul>
              
              <div className="pt-2 mt-2 border-t border-zinc-200">
                <p className="text-xs text-zinc-500 font-medium italic leading-relaxed">
                  {t('appointments.form.contactDialog.iOSNote')}
                </p>
              </div>
            </div>
          </div>
          <DialogFooter className="border-t border-zinc-200 pt-4">
            <Button onClick={() => setShowNotSupportedDialog(false)} className="w-full bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg h-11">
              {t('appointments.form.contactDialog.understood')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AppointmentFormWizard;