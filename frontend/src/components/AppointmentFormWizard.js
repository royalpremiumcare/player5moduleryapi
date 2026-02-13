import { useState, useEffect, useRef } from "react";
import { format, addDays, isSameDay } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import { Calendar as CalendarIcon, Clock, ArrowLeft, User, Search, X, Check, UserPlus, ChevronLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : "";
const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

const AppointmentFormWizard = ({ services, appointment, onSave, onCancel }) => {
  const { userRole } = useAuth();
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
  const [busySlots, setBusySlots] = useState([]); // Dolu saatleri bilmek için
  const [loading, setLoading] = useState(false);
  
  // Filtrelemeler
  const [filteredServices, setFilteredServices] = useState([]);
  const [qualifiedStaff, setQualifiedStaff] = useState([]);
  
  // Müşteri Arama
  const [customers, setCustomers] = useState([]);
  const [customerSearchTerm, setCustomerSearchTerm] = useState("");
  const [isNewCustomerMode, setIsNewCustomerMode] = useState(false);

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
      setStep(3); // Düzenlemedeyse sona git
    }
  }, [appointment]);

  useEffect(() => {
    if (formData.service_id && formData.appointment_date && step === 3) {
      loadAvailableSlots();
    }
  }, [formData.service_id, formData.appointment_date, formData.staff_member_id, step]);

  useEffect(() => {
    if (userRole === 'staff' && currentUser && services.length > 0) {
      const allowed = services.filter(s => currentUser.permitted_service_ids?.includes(s.id));
      setFilteredServices(allowed);
    } else {
      setFilteredServices(services);
    }
  }, [userRole, currentUser, services]);

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
    if (userRole === 'staff') {
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
      const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      if (!token) return;
      const orgId = JSON.parse(atob(token.split('.')[1])).org_id;

      const params = { service_id: formData.service_id, date: dateStr };
      if (formData.staff_member_id) params.staff_id = formData.staff_member_id;

      const res = await publicApi.get(`/public/availability/${orgId}`, { params });
      setAvailableSlots(res.data.available_slots || []);
      setBusySlots(res.data.busy_slots || []);
    } catch (e) {
      console.error(e);
      setAvailableSlots([]);
    }
  };

  // --- HANDLERS ---

  const handleSubmit = async () => {
    if (!formData.customer_name || !formData.phone || !formData.service_id || !formData.appointment_time) {
      toast.error(t('appointments.form.fillRequiredFields'));
      return;
    }
    setLoading(true);
    try {
      const payload = { ...formData, appointment_date: format(formData.appointment_date, "yyyy-MM-dd") };
      if (userRole === 'staff' && currentUser && !payload.staff_member_id) payload.staff_member_id = currentUser.username;
      if (!payload.staff_member_id) delete payload.staff_member_id;

      if (appointment) {
        await api.put(`/appointments/${appointment.id}`, payload);
        toast.success(t('appointments.form.updated'));
      } else {
        await api.post("/appointments", payload);
        toast.success(t('appointments.form.created'));
        await loadCustomers();
      }
      await new Promise(r => setTimeout(r, 500));
      onSave();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('appointments.form.operationFailed'));
    } finally {
      setLoading(false);
    }
  };

  // --- RENDER STEPS ---

  // ADIM 1: HİZMET SEÇİMİ (Kart Görünümü)
  const renderStep1 = () => (
    <div className="space-y-4 animate-in slide-in-from-right duration-300 pb-20">
      <div className="relative">
        <Search className="absolute left-3 top-3.5 h-5 w-5 text-zinc-400" />
        <Input 
          placeholder={t('appointments.form.searchService', 'Hizmet ara...')} 
          className="pl-10 h-12 bg-zinc-50 border-zinc-200 rounded-xl focus:ring-zinc-900"
          // Basit filtreleme eklenebilir
        />
      </div>
      <div className="grid grid-cols-1 gap-3">
        {filteredServices.map((service) => (
          <div 
            key={service.id}
            onClick={() => {
              setFormData(prev => ({ ...prev, service_id: service.id }));
              setStep(2);
            }}
            className={`group p-4 bg-white border rounded-xl shadow-sm hover:border-zinc-400 cursor-pointer transition-all active:scale-[0.99] flex justify-between items-center
              ${formData.service_id === service.id ? 'border-zinc-900 ring-1 ring-zinc-900 bg-zinc-50' : 'border-zinc-100'}
            `}
          >
            <div>
              <h3 className="font-semibold text-zinc-900">{service.name}</h3>
              <p className="text-sm text-zinc-500 mt-1">
                {Math.round(service.price)}{i18n.language === 'tr' ? '₺' : '£'} • {service.duration || 30} dk
              </p>
            </div>
            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors
              ${formData.service_id === service.id ? 'border-zinc-900 bg-zinc-900' : 'border-zinc-200 group-hover:border-zinc-400'}
            `}>
              {formData.service_id === service.id && <Check className="w-3 h-3 text-white" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // ADIM 2: MÜŞTERİ SEÇİMİ (Hibrit Arama)
  const renderStep2 = () => {
    const filteredCustomers = customers.filter(c => 
      c.name.toLowerCase().includes(customerSearchTerm.toLowerCase()) || c.phone.includes(customerSearchTerm)
    );

    return (
      <div className="space-y-6 animate-in slide-in-from-right duration-300 pb-20">
        <div className="relative">
           <Search className="absolute left-4 top-3.5 h-5 w-5 text-zinc-400" />
           <input 
             value={customerSearchTerm}
             onChange={(e) => {
               setCustomerSearchTerm(e.target.value);
               if(isNewCustomerMode) setIsNewCustomerMode(false);
             }}
             placeholder={t('appointments.form.searchCustomer')}
             className="w-full pl-12 pr-4 py-3 bg-white border border-zinc-200 rounded-xl focus:ring-2 focus:ring-zinc-900 outline-none transition-all"
           />
        </div>

        {isNewCustomerMode ? (
          <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
             <div className="flex justify-between items-center">
                <h4 className="font-semibold text-zinc-900">{t('appointments.form.newCustomer')}</h4>
                <button onClick={() => setIsNewCustomerMode(false)}><X className="w-5 h-5 text-zinc-500"/></button>
             </div>
             <Input 
               placeholder={t('customers.fields.name')} 
               value={formData.customer_name}
               onChange={(e) => setFormData(prev => ({...prev, customer_name: e.target.value}))}
               className="bg-white"
             />
             <Input 
               placeholder={i18n.language === 'en' ? '+44...' : '05...'}
               value={formData.phone}
               onChange={(e) => {
                 let val = e.target.value.replace(/[^0-9+]/g, ''); // Basit temizlik
                 setFormData(prev => ({...prev, phone: val}));
               }}
               className="bg-white"
             />
             <Button className="w-full bg-zinc-900 hover:bg-black" onClick={() => {
                 if(formData.customer_name && formData.phone) setStep(3);
                 else toast.error(t('appointments.form.fillRequiredFields'));
             }}>
               {t('common.continue')}
             </Button>
          </div>
        ) : (
          <button 
            onClick={() => { setIsNewCustomerMode(true); setFormData(prev => ({...prev, customer_name: "", phone: ""})); }}
            className="w-full py-3 flex items-center justify-center gap-2 border-2 border-dashed border-zinc-300 rounded-xl text-zinc-600 font-medium hover:bg-zinc-50 hover:border-zinc-400 transition-all"
          >
            <UserPlus className="h-5 w-5" />
            <span>{t('appointments.form.newCustomer')}</span>
          </button>
        )}

        {!isNewCustomerMode && (
          <div className="space-y-2">
            {filteredCustomers.slice(0, 5).map(c => (
              <div 
                key={c.phone}
                onClick={() => {
                  setFormData(prev => ({ ...prev, customer_name: c.name, phone: c.phone }));
                  setStep(3);
                }}
                className="flex items-center justify-between p-3 bg-white border border-zinc-100 rounded-xl hover:border-zinc-300 cursor-pointer group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-600 font-bold group-hover:bg-zinc-900 group-hover:text-white transition-colors">
                    {c.name.charAt(0)}
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900">{c.name}</p>
                    <p className="text-xs text-zinc-500">{c.phone}</p>
                  </div>
                </div>
                <Check className={`w-5 h-5 ${formData.phone === c.phone ? 'text-zinc-900' : 'text-zinc-200'}`} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ADIM 3: TARİH VE SAAT (Modern Görünüm)
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

    return (
      <div className="space-y-8 animate-in slide-in-from-right duration-300 pb-24">
        
        {/* Personel Seçimi (Opsiyonel) */}
        {userRole === 'admin' && qualifiedStaff.length > 0 && (
          <div>
             <label className="block text-sm font-medium text-zinc-700 mb-2">{t('appointments.form.selectStaff')}</label>
             <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                <button
                   onClick={() => setFormData(prev => ({ ...prev, staff_member_id: "" }))}
                   className={`px-4 py-2 rounded-full border text-sm font-medium whitespace-nowrap transition-all
                     ${!formData.staff_member_id ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200'}
                   `}
                >
                   {t('appointments.form.autoAssign')}
                </button>
                {qualifiedStaff.map(staff => (
                   <button
                     key={staff.username}
                     onClick={() => setFormData(prev => ({ ...prev, staff_member_id: staff.username }))}
                     className={`px-4 py-2 rounded-full border text-sm font-medium whitespace-nowrap transition-all flex items-center gap-2
                       ${formData.staff_member_id === staff.username ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200'}
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
           <div className="flex justify-between items-center mb-2">
             <h3 className="font-semibold text-zinc-900">{format(formData.appointment_date, "MMMM yyyy", { locale: dateLocale })}</h3>
           </div>
           <div className="relative">
             <button
               type="button"
               onClick={() => scrollDatesBy(-320)}
               className="hidden md:flex absolute left-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 items-center justify-center rounded-full bg-white border border-zinc-200 shadow-sm hover:bg-zinc-50"
               aria-label="Scroll dates left"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700" />
             </button>
             <button
               type="button"
               onClick={() => scrollDatesBy(320)}
               className="hidden md:flex absolute right-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 items-center justify-center rounded-full bg-white border border-zinc-200 shadow-sm hover:bg-zinc-50"
               aria-label="Scroll dates right"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700 rotate-180" />
             </button>

             <div
               ref={dateScrollerRef}
               onWheel={handleDateScrollerWheel}
               className="flex gap-3 overflow-x-auto pb-4 scrollbar-hide -mx-2 px-2 md:mx-0 md:px-12"
             >
             {days.map((date, i) => {
               const isSelected = isSameDay(date, formData.appointment_date);
               return (
                 <button 
                   key={i}
                   onClick={() => setFormData(prev => ({ ...prev, appointment_date: date, appointment_time: "" }))}
                   className={`flex flex-col items-center justify-center min-w-[72px] h-[84px] rounded-2xl border transition-all shrink-0
                     ${isSelected 
                       ? 'bg-zinc-900 border-zinc-900 text-white shadow-lg scale-105' 
                       : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-300'}
                   `}
                 >
                   <span className={`text-xs font-medium mb-1 ${isSelected ? 'text-zinc-300' : 'text-zinc-400'}`}>
                     {format(date, "EEE", { locale: dateLocale })}
                   </span>
                   <span className="text-2xl font-bold">{format(date, "d")}</span>
                 </button>
               )
             })}
             </div>
           </div>
        </div>

        {/* SAAT GRID */}
        <div>
          <h3 className="font-semibold text-zinc-900 mb-4">{t('appointments.form.appointmentTime')}</h3>
          {availableSlots.length === 0 && busySlots.length === 0 ? (
             <div className="text-center p-6 border-2 border-dashed border-zinc-200 rounded-xl text-zinc-500">
                <Clock className="w-8 h-8 mx-auto mb-2 opacity-50"/>
                {t('appointments.form.noAvailableSlots')}
             </div>
          ) : (
            <div className="grid grid-cols-4 gap-3">
              {/* Müsait ve Dolu Saatleri Birleştirip Sıralayalım (Opsiyonel, şimdilik sadece available gösteriyoruz, busy göstermek istersen logic eklenebilir) */}
              {availableSlots.map((time) => (
                <button
                  key={time}
                  onClick={() => setFormData(prev => ({ ...prev, appointment_time: time }))}
                  className={`py-3 rounded-xl text-sm font-semibold transition-all border
                    ${formData.appointment_time === time 
                      ? 'bg-blue-600 border-blue-600 text-white shadow-md scale-105' 
                      : 'bg-white border-zinc-200 text-zinc-700 hover:border-zinc-900 hover:bg-zinc-50'}
                  `}
                >
                  {time}
                </button>
              ))}
              {/* Dolu Saatleri Silik Göster (Opsiyonel) */}
              {busySlots.map((time) => (
                 <button key={time} disabled className="py-3 rounded-xl text-sm font-medium border border-transparent bg-zinc-50 text-zinc-300 cursor-not-allowed">
                    {time}
                 </button>
              ))}
            </div>
          )}
        </div>

        {/* NOTLAR */}
        <div>
           <label className="block text-sm font-medium text-zinc-700 mb-2">{t('appointments.form.notes')}</label>
           <textarea 
             className="w-full p-3 bg-white border border-zinc-200 rounded-xl focus:ring-2 focus:ring-zinc-900 outline-none text-sm"
             rows="2"
             placeholder={t('appointments.form.notesPlaceholder')}
             value={formData.notes}
             onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
           />
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-white md:bg-black/50 md:flex md:items-center md:justify-center p-0 md:p-4 animate-in fade-in duration-200">
      <div className="w-full h-full md:h-auto md:max-h-[90vh] md:max-w-[500px] bg-white md:rounded-[32px] md:shadow-2xl flex flex-col overflow-hidden relative">
        
        {/* HEADER */}
        <div className="px-6 pt-12 pb-4 md:pt-6 border-b border-zinc-100 flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-20 shrink-0">
          <div className="flex items-center gap-4">
            {step > 1 ? (
              <button onClick={() => setStep(step - 1)} className="p-2 -ml-2 hover:bg-zinc-100 rounded-full transition-colors">
                <ChevronLeft className="w-6 h-6 text-zinc-900" />
              </button>
            ) : (
              <button onClick={onCancel} className="p-2 -ml-2 hover:bg-zinc-100 rounded-full transition-colors md:hidden">
                 <X className="w-6 h-6 text-zinc-900" />
              </button>
            )}
            <div>
              <h1 className="text-lg font-bold text-zinc-900 leading-tight">
                {step === 1 && t('appointments.form.selectService')}
                {step === 2 && t('appointments.form.selectCustomer')}
                {step === 3 && t('appointments.form.appointmentDate')}
              </h1>
              <p className="text-xs text-zinc-400 font-medium tracking-wide mt-0.5">
                 {t('common.step')} {step}/3
              </p>
            </div>
          </div>
          <button onClick={onCancel} className="p-2 bg-zinc-100 rounded-full hover:bg-zinc-200 transition-colors hidden md:block">
            <X className="w-5 h-5 text-zinc-500" />
          </button>
        </div>

        {/* PROGRESS BAR */}
        <div className="h-1 w-full bg-zinc-100 shrink-0">
          <div className="h-full bg-zinc-900 transition-all duration-500 ease-out" style={{ width: `${(step / 3) * 100}%` }} />
        </div>

        {/* CONTENT */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
        </div>

        {/* FOOTER ACTION */}
        {step === 3 && (
          <div className="p-6 bg-white border-t border-zinc-100 z-20 shrink-0">
             <div className="flex justify-between items-center mb-4 text-sm">
                <span className="text-zinc-500">{t('common.total')}</span>
                <span className="text-xl font-bold text-zinc-900">
                   {filteredServices.find(s => s.id === formData.service_id)?.price}₺
                </span>
             </div>
             <Button 
               onClick={handleSubmit}
               disabled={loading || !formData.appointment_time}
               className="w-full bg-zinc-900 text-white font-bold text-lg h-14 rounded-2xl shadow-xl shadow-zinc-900/10 hover:bg-black transition-all"
             >
               {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : (
                 <span className="flex items-center gap-2">
                    <Check className="w-5 h-5" /> {appointment ? t('appointments.form.update') : t('appointments.form.save')}
                 </span>
               )}
             </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AppointmentFormWizard;