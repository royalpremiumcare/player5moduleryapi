import { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from "react";
import { format, addDays, isSameDay, startOfDay, differenceInCalendarDays } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import { Calendar as CalendarIcon, Clock, ArrowLeft, User, Search, X, Check, UserPlus, ChevronLeft, Loader2, Users, Import, AlertTriangle, Info } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import axios from "axios";
import { Virtuoso } from 'react-virtuoso';

// --- REHBER & TİTREŞİM ENTEGRASYONU ---
import { Capacitor, registerPlugin } from '@capacitor/core';
import { Contacts } from '@capacitor-community/contacts';
import { Haptics, NotificationType } from '@capacitor/haptics'; // TİTREŞİM EKLENDİ

const ContactPicker = registerPlugin('ContactPickerPlugin');
// --------------------------------------

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatApiError } from "@/lib/apiError";
import SessionPlannerDialog from "./planner/SessionPlannerDialog";
import { fetchWavePlanSessions } from "../lib/sessionScheduling";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : "";
const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

/** API `yyyy-MM-dd` veya ISO string → yerel takvim günü (UTC kayması yüzünden yanlış gün / boş slot önlenir) */
function parseLocalAppointmentDate(value) {
  if (!value) return new Date();
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
  const s = String(value);
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (m) {
    const y = Number(m[1]);
    const mo = Number(m[2]) - 1;
    const d = Number(m[3]);
    return new Date(y, mo, d);
  }
  return new Date(value);
}

const AppointmentFormWizard = ({ services, appointment, onSave, onCancel }) => {
  const { userRole, canViewAll } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  const dateScrollerRef = useRef(null);
  const stepRef = useRef(1);
  /**
   * Ref to the scrollable <div> that hosts renderStep1/2/3 content.
   * We attach a useEffect below that resets its scrollTop whenever `step`
   * changes, so each wizard step starts at the top (fixes the "scroll stays
   * at previous position when navigating between steps" UX bug).
   */
  const contentScrollRef = useRef(null);

  // State Yönetimi
  const [step, setStep] = useState(1);
  stepRef.current = step;
  // Plan M2: yeni paket akışı tek atomik /bulk-package call'unda yaratılır.
  // Step 3 → step 4 geçişinde 1. seansı önceden POST etmiyoruz; bu yüzden
  // sheetAppointment yerine sadece "draft" tutuyoruz. SessionPlannerDialog
  // mode="newPackage" + packageDraft prop'ları ile 1..N seansı tek seferde
  // /bulk-package'a gönderir. Eski yetim-temizleme guard (manualPlanCompletedRef
  // + DELETE /appointments) artık gereksiz — DB'ye HİÇBİR şey yazılmamıştır.
  const [packageDraft, setPackageDraft] = useState(null);
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
    notes: "",
  });

  // Data States
  const [availableSlots, setAvailableSlots] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [availabilityNonce, setAvailabilityNonce] = useState(0);
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
        appointment_date: parseLocalAppointmentDate(appointment.appointment_date),
        appointment_time: appointment.appointment_time,
        staff_member_id: appointment.staff_member_id || "",
        notes: appointment.notes || "",
      });
      setStep(3);
    }
  }, [appointment]);

  useEffect(() => {
    if (step !== 2) return;
    const id = requestAnimationFrame(() => {
      try {
        customerListRef.current?.scrollToIndex(0);
      } catch (e) {
        /* Virtuoso */
      }
    });
    return () => cancelAnimationFrame(id);
  }, [step]);

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
    const search = (debouncedServiceSearchTerm || "").toLocaleLowerCase('tr');
    if (!search) return raw;
    return raw.filter((s) => String(s?.name || "").toLocaleLowerCase('tr').includes(search));
  }, [filteredServices, debouncedServiceSearchTerm]);

  const currencySymbol = useMemo(() => {
    const phone = (settings?.support_phone || '').replace(/\s/g, '');
    return (phone.startsWith('+44') || phone.startsWith('44')) ? '£' : '₺';
  }, [settings]);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedCustomerSearchTerm(customerSearchTerm), 150);
    return () => clearTimeout(id);
  }, [customerSearchTerm]);

  const selectedService = useMemo(
    () => services.find((s) => s.id === formData.service_id),
    [services, formData.service_id]
  );
  const isNewMultiPackage =
    !appointment && selectedService?.session_count && selectedService.session_count > 1;
  const wizardTotalSteps = isNewMultiPackage ? 4 : 3;

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;

      if (showContactSelectionDialog || showNotSupportedDialog) return;
      if (stepRef.current === 4) return;

      const target = e.target;
      if (!target || !(target instanceof Element)) return;

      if (target.closest('[data-wizard-keyboard-disabled="true"]')) return;
      if (target.closest('[role="dialog"]')) return;
      if (target.closest('[role="menu"]')) return;
      if (target.closest('[role="listbox"]')) return;

      const tag = target.tagName?.toLowerCase();
      const blockWizardArrows =
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        tag === "button" ||
        tag === "option" ||
        tag === "a" ||
        target.isContentEditable;

      if (blockWizardArrows) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setStep((s) => Math.max(1, s - 1));
        return;
      }

      if (e.key === "ArrowRight") {
        e.preventDefault();
        setStep((s) => {
          if (s >= wizardTotalSteps) return s;
          if (s === 3) return s;
          return s + 1;
        });
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [wizardTotalSteps, showContactSelectionDialog, showNotSupportedDialog]);

  const filteredCustomers = useMemo(() => {
    const raw = customers || [];
    const search = (debouncedCustomerSearchTerm || "").toLocaleLowerCase('tr');
    const phoneSearch = String(debouncedCustomerSearchTerm || "");

    const filtered = search
      ? raw.filter((c) => {
          const name = (c?.name || "").toLocaleLowerCase('tr');
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

  const loadAvailableSlots = useCallback(async () => {
    if (!formData.service_id || !formData.appointment_date || !settings) return;
    try {
      const dateStr = format(formData.appointment_date, "yyyy-MM-dd");
      const params = { service_id: formData.service_id, date: dateStr };
      if (formData.staff_member_id) params.staff_id = formData.staff_member_id;
      if (appointment?.id) params.exclude_appointment_id = appointment.id;

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
      setBusySlots([]);
    }
  }, [
    formData.service_id,
    formData.appointment_date,
    formData.staff_member_id,
    settings,
    userRole,
    canViewAll,
    appointment?.id,
  ]);

  useEffect(() => {
    if (formData.service_id && formData.appointment_date && step === 3 && settings) {
      loadAvailableSlots();
    }
  }, [loadAvailableSlots, step, availabilityNonce]);

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
        const platform = Capacitor.getPlatform(); // 'ios' veya 'android'
        let normalizedContacts = [];

        if (platform === 'ios') {
          // iOS: Custom native plugin (CNContactPickerViewController) açar
          const result = await ContactPicker.pickContacts();

          if (!result.contacts || result.contacts.length === 0) {
            toast.info("Kişi seçilmedi.");
            return;
          }

          normalizedContacts = result.contacts
            .map(c => ({
              name: c.name || '',
              phone: c.phone || ''
            }))
            .filter(c => c.name && c.phone);
        } else {
          // Android: Contacts.getContacts() kullan
          const permission = await Contacts.requestPermissions();
          if (permission.contacts !== 'granted') {
            toast.error("Rehber izni verilmedi. Ayarlardan izin verin.");
            return;
          }

          const result = await Contacts.getContacts({
            projection: { name: true, phones: true }
          });

          if (!result.contacts || result.contacts.length === 0) {
            toast.info("Rehber boş.");
            return;
          }

          normalizedContacts = result.contacts
            .map(c => ({
              name: c.name?.display || ((c.name?.given || '') + " " + (c.name?.family || '')).trim(),
              phone: c.phones?.[0]?.number
            }))
            .filter(c => c.name && c.phone);
        }

        if (normalizedContacts.length === 0) {
          toast.warning("Kişilerin telefon numarası bulunamadı.");
          return;
        }

        setFetchedContacts(normalizedContacts);
        setSelectedContactPhones(new Set(normalizedContacts.map(c => c.phone)));
        setContactSearchTerm("");
        setShowContactSelectionDialog(true);

      } catch (error) {
        console.error("Contacts error:", error);
        if (!error.message?.includes('canceled') && !error.message?.includes('cancelled')) {
          toast.error("Rehber okunurken hata oluştu: " + (error.message || ''));
        }
      } finally {
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
          setSelectedContactPhones(new Set(normalized.map(c => c.phone)));
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

  const filteredFetchedContacts = useMemo(() => fetchedContacts.filter(contact =>
    contact.name.toLowerCase().includes(contactSearchTerm.toLowerCase()) ||
    contact.phone.replace(/\D/g, "").includes(contactSearchTerm)
  ), [fetchedContacts, contactSearchTerm]);

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

  const buildAppointmentPayload = () => {
    const payload = {
      ...formData,
      appointment_date: format(formData.appointment_date, "yyyy-MM-dd"),
    };
    if (userRole === "staff" && !canViewAll && currentUser && !payload.staff_member_id) {
      payload.staff_member_id = currentUser.username;
    }
    if (!payload.staff_member_id) delete payload.staff_member_id;
    return payload;
  };

  /**
   * Plan M2 sonrası: paket alanları artık handlePackagePlanStart içinde
   * üretiliyor (session_group_id frontend-generated, 1..N atomik). Tek
   * seans randevu yaratımında session_count>1 olamaz (isNewMultiPackage
   * branch ayrı), yine de güvenlik için no-op koruyucu.
   */
  const attachNewPackageFields = (payload, svc) => {
    if (svc?.session_count && svc.session_count > 1) {
      payload.session_group_id = crypto.randomUUID();
      payload.session_number = 1;
      payload.session_total = svc.session_count;
      payload.payment_status = "package_included";
      payload.skip_confirmation_whatsapp = true;
    }
  };

  /**
   * Form-state validate + packageDraft inşa eden yardımcı.
   * Her iki paket başlatıcısı (auto + manual) ortak girdi doğrulaması
   * ve draft üretimi için bunu çağırır.
   * @returns {object|null} draft objesi veya validasyon başarısızsa null
   */
  const buildPackageDraft = useCallback(() => {
    if (!formData.customer_name || !formData.phone || !formData.service_id || !formData.appointment_time) {
      try {
        Haptics.notification({ type: NotificationType.Error });
      } catch (e) {}
      toast.error(t("appointments.form.fillRequiredFields"));
      return null;
    }
    if (!selectedService?.session_count || selectedService.session_count <= 1) {
      return null;
    }
    const sessionTotal = selectedService.session_count;
    const sessionGroupId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const staffId = (formData.staff_member_id || "").trim() || null;
    return {
      customer_name: formData.customer_name,
      phone: formData.phone,
      service_id: formData.service_id,
      service_name: selectedService.name,
      staff_member_id: staffId,
      service_duration: selectedService.duration ?? 30,
      first_session_date: format(formData.appointment_date, "yyyy-MM-dd"),
      first_session_time: formData.appointment_time,
      session_group_id: sessionGroupId,
      session_total: sessionTotal,
      notes: formData.notes || "",
    };
  }, [formData, selectedService, t]);

  /**
   * Plan M2: Manuel paket akışı.
   *
   * HİÇBİR API çağrısı yapmaz; packageDraft + setStep(4) ile
   * SessionPlannerDialog'u mode="newPackage" açar. Kullanıcı dialog
   * içinde "Kaydet" derken atomik POST /bulk-package tek transaction'da
   * 1..N seansı yaratır. X'e basarsa DB temiz kalır.
   */
  const handlePackagePlanManual = useCallback(() => {
    const draft = buildPackageDraft();
    if (!draft) return;
    setPackageDraft(draft);
    setStep(4);
    try {
      Haptics.notification({ type: NotificationType.Success });
    } catch (e) {}
  }, [buildPackageDraft]);

  /**
   * Plan M2: Otomatik paket akışı (eski "Otomatik Planla" davranışı geri).
   *
   * wave-plan API'sinden 2..N seansı öner → 1. seans + öneriler birleşip
   * atomik POST /bulk-package ile tek seferde yaratılır. Dialog HİÇ
   * AÇILMAZ; başarılıysa direkt onSave() çağrılır.
   *
   * wave-plan başarısız (network / öneri yetersiz) ise sessizce manuel
   * akışa düşer (dialog açılır, kullanıcı planlar). Bu sayede yeni
   * atomik garanti korunur, eski UX akıcılığı geri gelir.
   */
  const handlePackagePlanAuto = useCallback(async () => {
    const draft = buildPackageDraft();
    if (!draft) return;
    setLoading(true);
    const idempotencyKey =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try {
      const sessionTotal = draft.session_total;
      const need = Math.max(0, sessionTotal - 1);
      let waveRows = [];
      if (need > 0) {
        try {
          const wave = await fetchWavePlanSessions(api, {
            service_id: draft.service_id,
            first_session_date: draft.first_session_date,
            first_session_time: draft.first_session_time,
            remaining_count: need,
            staff_member_id: draft.staff_member_id || undefined,
          });
          const planned = (wave?.sessions || []).filter((s) => s.date && s.time && !s.unplanned);
          if (planned.length === need) {
            waveRows = planned.map((s) => ({
              date: s.date,
              time: s.time,
              staff_member_id: s.staff_member_id || undefined,
            }));
          }
        } catch (waveErr) {
          console.warn("[wizard] wave-plan auto failed, falling back to manual", waveErr);
        }
      }
      // Wave-plan yeterli seans önermediyse manuel akışa düş.
      if (need > 0 && waveRows.length !== need) {
        toast.info(t("appointments.form.packageBulkIncompleteToSheet", { defaultValue: "Otomatik öneri yetersiz; planlamayı tamamla." }));
        setPackageDraft(draft);
        setStep(4);
        return;
      }
      const firstRow = {
        date: draft.first_session_date,
        time: draft.first_session_time,
      };
      if (draft.staff_member_id) firstRow.staff_member_id = draft.staff_member_id;
      const rows = [firstRow, ...waveRows];
      const payload = {
        customer_name: draft.customer_name,
        phone: draft.phone,
        service_id: draft.service_id,
        notes: draft.notes || "",
        session_group_id: draft.session_group_id,
        session_total: sessionTotal,
        sessions: rows,
      };
      if (draft.staff_member_id) payload.staff_member_id = draft.staff_member_id;
      await api.post("/appointments/bulk-package", payload, {
        headers: { "Idempotency-Key": idempotencyKey },
      });
      toast.success(t("appointments.form.packageBulkScheduled", { count: sessionTotal }));
      try {
        await Haptics.notification({ type: NotificationType.Success });
      } catch (e) {}
      await loadCustomers();
      setAvailabilityNonce((n) => n + 1);
      await new Promise((r) => setTimeout(r, 400));
      onSave();
    } catch (err) {
      console.error("[wizard] auto bulk-package failed", err);
      const msg = formatApiError(err, t, t("appointments.form.operationFailed"));
      toast.error(msg);
      try {
        await Haptics.notification({ type: NotificationType.Error });
      } catch (e) {}
      // POST hatasında da manuel dialog açıp kullanıcıya planlama şansı ver.
      setPackageDraft(draft);
      setStep(4);
    } finally {
      setLoading(false);
    }
  }, [buildPackageDraft, t, loadCustomers, onSave]);

  const handleSubmit = async () => {
    if (isNewMultiPackage) return;

    if (!formData.customer_name || !formData.phone || !formData.service_id || !formData.appointment_time) {
      try {
        await Haptics.notification({ type: NotificationType.Error });
      } catch (e) {}
      toast.error(t("appointments.form.fillRequiredFields"));
      return;
    }

    setLoading(true);

    try {
      const payload = buildAppointmentPayload();

      if (!appointment) {
        const svc = services.find((s) => s.id === formData.service_id);
        attachNewPackageFields(payload, svc);
      }

      if (appointment) {
        await api.put(`/appointments/${appointment.id}`, payload);
        toast.success(t("appointments.form.updated"));
      } else {
        await api.post("/appointments", payload);
        toast.success(t("appointments.form.created"));
        await loadCustomers();
      }

      setAvailabilityNonce((n) => n + 1);
      await loadAvailableSlots();

      try {
        await Haptics.notification({ type: NotificationType.Success });
      } catch (e) {
        console.log("Haptic error", e);
      }

      await new Promise((r) => setTimeout(r, 500));
      onSave();
    } catch (error) {
      try {
        await Haptics.notification({ type: NotificationType.Error });
      } catch (e) {}

      toast.error(formatApiError(error, t, t("appointments.form.operationFailed")));
    } finally {
      setLoading(false);
    }
  };

  // --- MEMOIZED COMPUTATIONS (renderStep dışında) ---

  const days = useMemo(() => {
    const today = startOfDay(new Date());
    const selected = formData.appointment_date
      ? startOfDay(formData.appointment_date)
      : today;
    const windowStart = today <= selected ? today : selected;
    const daysFromStartToSelected = Math.max(0, differenceInCalendarDays(selected, windowStart));
    const count = Math.max(60, daysFromStartToSelected + 14);
    return Array.from({ length: count }, (_, i) => addDays(windowStart, i));
  }, [formData.appointment_date]);

  useLayoutEffect(() => {
    if (step !== 3) return;
    const scroller = dateScrollerRef.current;
    if (!scroller) return;
    const selected = formData.appointment_date
      ? startOfDay(formData.appointment_date)
      : null;
    if (!selected) return;
    const idx = days.findIndex((d) => isSameDay(d, selected));
    if (idx < 0) return;
    const btn = scroller.children[idx];
    if (btn && typeof btn.scrollIntoView === "function") {
      btn.scrollIntoView({ inline: "center", block: "nearest", behavior: "auto" });
    }
  }, [step, days, formData.appointment_date, appointment?.id]);

  const allSlots = useMemo(
    () => [...new Set([...availableSlots, ...busySlots])].sort(),
    [availableSlots, busySlots]
  );

  /**
   * Scrolls the horizontal date strip by `delta` px.
   *
   * Why not `scrollBy({ behavior:'smooth' })`?
   *   iOS Safari ignores successive smooth-scroll calls while a previous
   *   smooth animation is in flight → after 1-2 taps the arrow appears
   *   unresponsive. We instead compute an explicit, clamped target and
   *   call `scrollTo(target)` so every tap reliably moves the scroller.
   */
  // Step-change effect: reset content scroll to top whenever we navigate
  // between wizard steps. rAF defers until after the new DOM is committed.
  useEffect(() => {
    const el = contentScrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      if (typeof el.scrollTo === "function") {
        el.scrollTo({ top: 0, behavior: "auto" });
      } else {
        el.scrollTop = 0;
      }
    });
    if (typeof window !== "undefined" && window.scrollTo) {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  }, [step]);

  const scrollDatesBy = useCallback((delta) => {
    const el = dateScrollerRef.current;
    if (!el) return;
    const max = Math.max(0, el.scrollWidth - el.clientWidth);
    const target = Math.min(max, Math.max(0, el.scrollLeft + delta));
    // If already at edge, nothing to do — avoids fake "unresponsive" feel.
    if (Math.abs(target - el.scrollLeft) < 1) return;
    if (typeof el.scrollTo === "function") {
      el.scrollTo({ left: target, behavior: "smooth" });
    } else {
      el.scrollLeft = target;
    }
  }, []);

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
            className={`group p-5 backdrop-blur-xl border rounded-2xl shadow-lg hover:shadow-xl cursor-pointer transition-[background-color,border-color,box-shadow] duration-200 active:scale-[0.99] flex justify-between items-center
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
              {service.session_count && service.session_count > 1 && (
                <span className={`inline-block text-xs mt-1.5 px-2 py-0.5 rounded-full font-bold ${formData.service_id === service.id ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-700'}`}>
                  {service.session_count} {i18n.language === 'tr' ? 'Seanslık Paket' : 'Session Package'}
                </span>
              )}
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
    return (
      <div className="space-y-6 animate-in slide-in-from-right duration-300 pb-20">
        <div className="relative">
           <Search className="absolute left-4 top-3.5 h-5 w-5 text-zinc-400" />
           <input 
             value={customerSearchTerm}
             onChange={(e) => {
               setCustomerSearchTerm(e.target.value);
               if (customerListRef.current) customerListRef.current.scrollToIndex(0);
               if(isNewCustomerMode) setIsNewCustomerMode(false);
             }}
             placeholder={t('appointments.form.searchCustomer')}
             className="w-full pl-12 pr-4 py-3 backdrop-blur-xl bg-white/40 border border-white/30 rounded-xl focus:ring-2 focus:ring-zinc-900 focus:bg-white/60 outline-none transition-colors shadow-sm"
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
          <Virtuoso
            ref={customerListRef}
            style={{ height: 420 }}
            data={filteredCustomers}
            overscan={200}
            itemContent={(_, c) => (
              <div className="pb-3">
                <div
                  onClick={() => {
                    setFormData((prev) => ({ ...prev, customer_name: c.name, phone: c.phone }));
                    setStep(3);
                  }}
                  className="flex items-center justify-between p-4 backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl hover:bg-white/60 hover:border-white/40 hover:shadow-lg cursor-pointer group transition-colors duration-200"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center text-zinc-700 font-bold text-lg group-hover:bg-zinc-900 group-hover:text-white transition-colors duration-200 shadow-sm">
                      {(c.name || '').charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-bold text-zinc-900">{c.name}</p>
                      <p className="text-xs text-zinc-500 font-medium">{c.phone}</p>
                    </div>
                  </div>
                  <Check className={`w-5 h-5 transition-colors ${formData.phone === c.phone ? 'text-zinc-900' : 'text-zinc-300'}`} strokeWidth={2.5} />
                </div>
              </div>
            )}
          />
        )}
      </div>
    );
  };

  // ADIM 3: TARİH VE SAAT
  // CLS fix: Adım 2 → 3 geçişinde transform tabanlı `slide-in-from-right`
  // animasyonu devam ederken `qualifiedStaff`, `selectedService` ve `allSlots`
  // async olarak güncelleniyor; bu da staff chip'leri / amber bilgi kartı /
  // slot grid'inin yükseklik hesaplamasını yeniden tetikleyerek görünür bir
  // titremeye neden oluyordu. Çözüm:
  //  1) Animasyonu `fade-in`'e çevirdik (sadece opacity, transform yok).
  //  2) Step 3 dış wrapper'ına stabil bir `min-h` verdik — içerik yüklenirken
  //     kapsayıcı yüksekliği değişmez.
  //  3) Staff picker + amber notice bloklarını tek, sabit `min-h`'lı bir
  //     container'a aldık; ikisi arası geçiş layout shift yaratmaz.
  const renderStep3 = () => {
    return (
      <div className="space-y-8 animate-in fade-in duration-200 pb-24 min-h-[760px]">
        
        {/* Seans Paketi Bilgilendirmesi */}
        {(() => {
          const selectedSvc = services.find(s => s.id === formData.service_id);
          if (selectedSvc?.session_count && selectedSvc.session_count > 1) {
            return (
              <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl flex items-start gap-2.5">
                <CalendarIcon className="w-4 h-4 text-zinc-700 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-zinc-900">
                  <p className="font-bold">
                    {i18n.language === 'tr' 
                      ? `Bu hizmet ${selectedSvc.session_count} seanslık bir pakettir.`
                      : `This service is a ${selectedSvc.session_count}-session package.`}
                  </p>
                  <p className="mt-1 text-zinc-600">
                    {t('appointments.form.wizard.packageHintShort')}
                  </p>
                </div>
              </div>
            );
          }
          return null;
        })()}

        {/* Personel seçimi bölgesi — sabit min-h ile; staff picker ve amber
            bilgi kartı arasındaki async geçişin CLS yaratmaması için tek
            kapsayıcıya alındı. Boş (seçili servis yok) durumda da yüksekliği
            korur, böylece adım 2 → 3 geçişinde titreme oluşmaz. */}
        {(userRole === 'admin' || canViewAll) && (
          <div className="min-h-[96px]">
            {qualifiedStaff.length > 0 ? (
              <div>
                <label className="block text-sm font-bold text-zinc-700 mb-3 uppercase tracking-wider">{t('appointments.form.selectStaff')}</label>
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                  <button
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, staff_member_id: "" }))}
                    className={`px-4 py-2.5 rounded-xl border text-sm font-bold whitespace-nowrap transition-colors shadow-sm backdrop-blur-md
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
                      className={`px-4 py-2.5 rounded-xl border text-sm font-bold whitespace-nowrap transition-colors flex items-center gap-2 shadow-sm backdrop-blur-md
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
            ) : selectedService ? (
              // Hizmet seçili ama kalifiye personel yok — admin için unassigned bilgisi.
              // Sarı uyarı yerine zinc tonu + Info ikonu (uyarı değil bilgi).
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 flex items-start gap-2">
                <Info className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" />
                <div className="text-xs text-zinc-700 leading-relaxed">
                  <p className="font-bold text-zinc-900 mb-0.5">
                    {i18n.language === 'tr' ? 'Personelsiz randevu' : 'Unassigned appointment'}
                  </p>
                  <p className="text-zinc-500">
                    {i18n.language === 'tr'
                      ? 'Personel sayfasından bu hizmete personel atayabilirsin.'
                      : 'You can assign a staff member for this service later.'}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/*
          YATAY TAKVİM + SAAT
          CLS fix: the whole block is wrapped in a container with a stable
          min-height so async slot-loading doesn't cause a layout shift
          (the "jitter" seen when switching to step 3). Desktop also gets
          a two-column grid so the date strip and time grid share space.
        */}
        <div
          data-wizard-keyboard-disabled="true"
          className="space-y-8 min-h-[520px]"
        >
        {/* YATAY TAKVİM */}
        <div>
           <div className="flex justify-between items-center mb-4">
             <h3 className="font-bold text-zinc-900 uppercase tracking-wider text-sm">{format(formData.appointment_date, "MMMM yyyy", { locale: dateLocale })}</h3>
           </div>
           <div className="relative overflow-hidden py-2 isolate">
             <button
               type="button"
               onMouseDown={(e) => e.preventDefault()}
               onClick={(e) => {
                 e.preventDefault();
                 e.stopPropagation();
                 scrollDatesBy(-320);
               }}
               className="hidden md:flex absolute left-2 top-1/2 -translate-y-1/2 z-20 h-9 w-9 items-center justify-center rounded-full backdrop-blur-md bg-white/80 border border-white/30 shadow-lg hover:bg-white active:scale-95 transition-transform"
               aria-label="Scroll dates left"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700 pointer-events-none" />
             </button>
             <button
               type="button"
               onMouseDown={(e) => e.preventDefault()}
               onClick={(e) => {
                 e.preventDefault();
                 e.stopPropagation();
                 scrollDatesBy(320);
               }}
               className="hidden md:flex absolute right-2 top-1/2 -translate-y-1/2 z-20 h-9 w-9 items-center justify-center rounded-full backdrop-blur-md bg-white/80 border border-white/30 shadow-lg hover:bg-white active:scale-95 transition-transform"
               aria-label="Scroll dates right"
             >
               <ChevronLeft className="w-5 h-5 text-zinc-700 rotate-180 pointer-events-none" />
             </button>

             <div
               ref={dateScrollerRef}
               className="relative z-10 flex gap-3 overflow-x-auto pb-4 scrollbar-hide px-2 md:px-12"
             >
             {days.map((date) => {
               const isSelected = isSameDay(date, formData.appointment_date);
               return (
                 <button 
                  type="button"
                  key={format(date, "yyyy-MM-dd")}
                  onClick={() => setFormData(prev => ({ ...prev, appointment_date: date, appointment_time: "" }))}
                  className={`flex flex-col items-center justify-center min-w-[72px] h-[84px] rounded-2xl border transition-[background-color,border-color,box-shadow,color] duration-200 shrink-0 shadow-sm
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

        {/* SAAT GRID — stable min-height prevents CLS while slots fetch */}
        <div className="min-h-[320px]">
          <h3 className="font-bold text-zinc-900 mb-4 uppercase tracking-wider text-sm">{t('appointments.form.appointmentTime')}</h3>
          {allSlots.length === 0 ? (
             <div className="text-center p-8 border-2 border-dashed border-zinc-200 rounded-2xl backdrop-blur-sm bg-white/30 min-h-[240px] flex flex-col items-center justify-center">
                <Clock className="w-10 h-10 mx-auto mb-3 text-zinc-300"/>
                <p className="text-sm text-zinc-500 font-medium">{t('appointments.form.noAvailableSlots')}</p>
             </div>
          ) : (
            <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
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
                    className={`py-3 rounded-xl text-sm font-bold transition-[background-color,border-color,box-shadow,transform,color] duration-200 border shadow-sm relative overflow-hidden
                      ${isSelected
                        ? 'bg-blue-600 border-blue-600 text-white shadow-lg scale-105'
                        : isBusy
                          ? 'bg-zinc-100 border-zinc-200 text-zinc-300 cursor-not-allowed line-through decoration-2 decoration-zinc-400 opacity-70 pointer-events-none'
                          : 'backdrop-blur-xl bg-white border-zinc-200 text-zinc-800 hover:bg-zinc-50 hover:border-zinc-300 hover:shadow-md'}
                    `}
                    style={isBusy ? {
                      backgroundImage: 'repeating-linear-gradient(45deg, transparent 0, transparent 6px, rgba(161,161,170,0.15) 6px, rgba(161,161,170,0.15) 7px)',
                    } : undefined}
                  >
                    {time}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        </div>

        {/* NOTLAR */}
        <div>
           <label className="block text-sm font-bold text-zinc-700 mb-3 uppercase tracking-wider">{t('appointments.form.notes')}</label>
           <textarea 
             className="w-full p-4 backdrop-blur-xl bg-white/40 border border-white/30 rounded-2xl focus:ring-2 focus:ring-zinc-900 focus:bg-white/60 outline-none text-sm font-medium transition-colors shadow-sm"
             rows="3"
             placeholder={t('appointments.form.notesPlaceholder')}
             value={formData.notes}
             onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
           />
        </div>
      </div>
    );
  };

  if (step === 4 && packageDraft) {
    return (
      <SessionPlannerDialog
        open={true}
        onOpenChange={(o) => {
          if (!o) {
            // Plan M2: Kullanıcı X'e bastı / backdrop'a tıkladı. HİÇBİR API
            // çağrısı YAPILMAMIŞTI (handlePackagePlanStart sadece state
            // setledi). DB temiz, yetim seans yok. State'i sıfırla, çağıranı
            // bilgilendir.
            setPackageDraft(null);
            onSave();
          }
        }}
        mode="newPackage"
        packageDraft={packageDraft}
        onSuccess={() => {
          // Atomik /bulk-package başarılı: 1..N seans tek transaction'da
          // yaratıldı. State'i temizle ve listenerleri uyandır.
          setPackageDraft(null);
          onSave();
        }}
        // newPackage modunda backend zaten notify_include_existing_sessions=
        // True ile çağırıyor (1..N tüm seansları içeren tek SESSION_PACKAGE
        // mesajı). Prop'a gerek yok; default false bırakıyoruz.
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-white md:bg-black/35 md:backdrop-blur-[1px] md:flex md:items-center md:justify-center p-0 md:p-4 animate-in fade-in duration-200">
      <div className="w-full h-full md:h-auto md:max-h-[92vh] md:max-w-3xl lg:max-w-5xl bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 md:from-gray-50/40 md:via-white md:to-white md:rounded-[32px] md:shadow-2xl flex flex-col overflow-hidden relative">
        
        {/* HEADER */}
        <div className="px-6 pt-12 pb-4 md:pt-6 border-b border-white/20 flex items-center justify-between backdrop-blur-2xl bg-white/70 sticky top-0 z-20 shrink-0 shadow-sm">
          <div className="flex items-center gap-4">
            {step > 1 && (
              <button onClick={() => setStep(step - 1)} className="p-2 -ml-2 hover:bg-white/50 rounded-xl transition-colors duration-200">
                <ChevronLeft className="w-6 h-6 text-zinc-900" strokeWidth={2} />
              </button>
            )}
            {step === 1 && (
              <button onClick={onCancel} className="p-2 -ml-2 hover:bg-white/50 rounded-xl transition-colors duration-200 md:hidden">
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
                 {t("common.step")} {step}/{wizardTotalSteps}
              </p>
            </div>
          </div>
          <button onClick={onCancel} className="p-2 backdrop-blur-md bg-white/50 rounded-xl hover:bg-white/70 transition-all duration-300 shadow-sm">
            <X className="w-5 h-5 text-zinc-600" strokeWidth={2} />
          </button>
        </div>

        {/* PROGRESS BAR */}
        <div className="h-1 w-full bg-zinc-100/50 shrink-0">
          <div
            className="h-full bg-zinc-900 transition-all duration-500 ease-out shadow-sm"
            style={{ width: `${(step / wizardTotalSteps) * 100}%` }}
          />
        </div>

        {/* CONTENT */}
        <div
          ref={contentScrollRef}
          className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 scrollbar-hide"
        >
          <div className="mx-auto w-full max-w-2xl lg:max-w-4xl">
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
          </div>
        </div>

        {/* FOOTER ACTION */}
        {step === 3 && (
          <div
            className="px-6 pt-6 backdrop-blur-2xl bg-white/80 border-t border-white/20 z-20 shrink-0 shadow-lg"
            style={{ paddingBottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))' }}
          >
             <div className="flex justify-between items-center mb-4 text-sm">
                <span className="text-zinc-500 font-bold uppercase tracking-wider">{t('common.total')}</span>
                <span className="text-2xl font-black text-zinc-900">
                   {i18n.language === 'en'
                     ? `${currencySymbol}${Math.round(filteredServices.find(s => s.id === formData.service_id)?.price || 0)}`
                     : `${Math.round(filteredServices.find(s => s.id === formData.service_id)?.price || 0)}${currencySymbol}`}
                </span>
             </div>
             {isNewMultiPackage ? (
               <div className="flex flex-col gap-3">
                 <Button
                   type="button"
                   onClick={handlePackagePlanAuto}
                   disabled={loading || !formData.appointment_time}
                   className="w-full bg-zinc-900 text-white font-bold text-base h-14 rounded-2xl shadow-xl hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                 >
                   {loading ? (
                     <Loader2 className="w-6 h-6 animate-spin" />
                   ) : (
                     <span className="flex items-center justify-center gap-2">
                       <Check className="w-5 h-5" strokeWidth={2.5} /> {t('appointments.form.wizard.autoPlan')}
                     </span>
                   )}
                 </Button>
                 <Button
                   type="button"
                   variant="outline"
                   onClick={handlePackagePlanManual}
                   disabled={loading || !formData.appointment_time}
                   className="w-full h-14 rounded-2xl border-zinc-200 font-bold text-zinc-900 bg-white hover:bg-zinc-50 disabled:opacity-50"
                 >
                   {loading ? (
                     <Loader2 className="w-6 h-6 animate-spin" />
                   ) : (
                     t('appointments.form.wizard.manualPlan')
                   )}
                 </Button>
               </div>
             ) : (
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
             )}
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