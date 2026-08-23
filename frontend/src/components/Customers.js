import { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import { Search, Phone, MessageSquare, ChevronRight, Plus, ArrowLeft, Trash2, Import, Users, CheckSquare, X, Edit2, XCircle } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import useDebounce from "../hooks/useDebounce";

// --- HİBRİT YAPI İÇİN GEREKLİ IMPORTLAR ---
import { Capacitor, registerPlugin } from '@capacitor/core';
import { Contacts } from '@capacitor-community/contacts';
const ContactPicker = registerPlugin('ContactPickerPlugin');
// ------------------------------------------

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import SessionBadge from "@/components/ui/session-badge";
import { SHOW_APPOINTMENT_CARD_STATUS } from "@/constants/uiFlags";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { format } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";

const Customers = ({ onNavigate, onNewAppointment, onRefresh }) => {
  const { userRole, token } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  const [currentStaffUsername, setCurrentStaffUsername] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const debouncedSearch = useDebounce(searchTerm, 300);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerHistory, setCustomerHistory] = useState(null);
  const [customerNotes, setCustomerNotes] = useState("");
  const [detailTab, setDetailTab] = useState("overview");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [customerToDelete, setCustomerToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [newCustomerDialogOpen, setNewCustomerDialogOpen] = useState(false);
  const [newCustomerData, setNewCustomerData] = useState({ name: "", phone: "" });
  const [savingCustomer, setSavingCustomer] = useState(false);
  const [settings, setSettings] = useState(null);
  
  // Müşteri Düzenleme
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editData, setEditData] = useState({ name: "", phone: "" });
  const [savingEdit, setSavingEdit] = useState(false);
  
  // --- REHBER ENTEGRASYONU STATE'LERİ ---
  const [importingContacts, setImportingContacts] = useState(false);
  const [showImportChoiceDialog, setShowImportChoiceDialog] = useState(false);
  const [showContactSelectionDialog, setShowContactSelectionDialog] = useState(false);
  
  const [fetchedContacts, setFetchedContacts] = useState([]);
  const [contactSearchTerm, setContactSearchTerm] = useState("");
  const [selectedContactPhones, setSelectedContactPhones] = useState(new Set());
  
  const [showNotSupportedDialog, setShowNotSupportedDialog] = useState(false);
  // ---------------------------------------

  const socketRef = useRef(null);
  const sentinelRef = useRef(null);
  // Race guard: eş zamanlı istekler arasından en yenisini tut, eskilerin cevabını at.
  const requestSeqRef = useRef(0);
  // Socket handler'ları ve infinite scroll güncel arama filtresini görsün.
  const searchRef = useRef("");
  useEffect(() => { searchRef.current = debouncedSearch || ""; }, [debouncedSearch]);

  const loadSettings = async () => {
    try {
      const response = await api.get("/settings");
      setSettings(response.data);
    } catch (error) { }
  };

  useEffect(() => {
    // Not: loadCustomers burada tetiklenmez. Aşağıdaki [debouncedSearch] useEffect'i
    // mount'ta bir kez (search="") çalışıp ilk sayfayı çeker → çift çağrı olmaz.
    loadSettings();
      if (userRole === 'staff') {
      loadCurrentStaffUsername();
      }
    
    if (!socketRef.current) {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const socketUrl = BACKEND_URL || window.location.origin;
      const authToken = token || localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      
      const socket = io(socketUrl, {
        path: '/api/socket.io',
        transports: ['websocket', 'polling'],
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        auth: { token: authToken || '' }
      });
      
      socketRef.current = socket;
      
      socket.on('connect', () => {
        const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
        if (token) {
          try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const organizationId = payload.org_id;
            if (organizationId) {
              socket.emit('join_organization', { organization_id: organizationId });
            }
          } catch (error) { console.error('Error parsing token:', error); }
        }
      });
      
      // Cursor pagination — event geldiğinde ilk sayfayı mevcut arama filtresi
      // ile yeniden çek. Etkilenen kayıtlar genelde en üstte olduğundan pratik
      // regresyon minimal (kaydırılan alt sayfalar sıfırlanır).
      const refetchFirstPage = () => {
        fetchCustomersRef.current({ search: searchRef.current });
      };

      socket.on('appointment_created', () => { refetchFirstPage(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('appointment_updated', () => { refetchFirstPage(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('appointment_deleted', () => { refetchFirstPage(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('customer_added', () => { refetchFirstPage(); });
      socket.on('customer_updated', () => { refetchFirstPage(); });
      socket.on('customer_deleted', (data) => {
        refetchFirstPage();
        if (selectedCustomer && data?.phone && selectedCustomer.phone === data.phone) {
          setSelectedCustomer(null); setCustomerHistory(null); setCustomerNotes("");
        }
      });
    }
    return () => {};
  }, []); 

  useEffect(() => {
    if (selectedCustomer) {
      loadCustomerHistory(selectedCustomer.phone);
      // Detay ekranı açılırken en üste scroll. PLANN panel mimarisinde ana
      // scroll body/window'da DEĞİL `#app-wrapper` üzerindedir; ayrıca iOS
      // Safari/WKWebView için body/documentElement scrollTop'u da sıfırlanır.
      try {
        const wrapper = document.getElementById('app-wrapper');
        if (wrapper) wrapper.scrollTop = 0;
        if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
        if (document.documentElement) document.documentElement.scrollTop = 0;
        if (document.body) document.body.scrollTop = 0;
        window.scrollTo(0, 0);
      } catch (_) { /* noop */ }
    } else {
      setCustomerHistory(null);
      setCustomerNotes("");
    }
  }, [selectedCustomer]);

  const loadCurrentStaffUsername = async () => {
    try {
      if (token) {
        const tokenPayload = JSON.parse(atob(token.split('.')[1]));
        setCurrentStaffUsername(tokenPayload.sub || tokenPayload.username);
      }
    } catch (error) { console.error("Kullanıcı bilgisi alınamadı:", error); }
  };

  const mapCustomer = (c) => ({
    id: c.id,
    name: c.name || "",
    phone: c.phone || "",
    totalAppointments: c.total_appointments || 0,
    isPending: (c.total_appointments || 0) === 0,
  });

  // Cursor pagination + server-side search. `cursor` yoksa ilk sayfa (reset).
  const fetchCustomers = async ({ cursor = null, search = "" } = {}) => {
    const isFirstPage = !cursor;
    const seq = ++requestSeqRef.current;
    if (isFirstPage) setLoading(true);
    else setIsFetchingMore(true);
    try {
      const params = { limit: 30 };
      if (cursor) params.cursor = cursor;
      const trimmed = (search || "").trim();
      if (trimmed) params.search = trimmed;

      const res = await api.get("/customers", { params });
      // Stale response — daha yeni bir istek başladıysa yanıtı at.
      if (seq !== requestSeqRef.current) return;

      const data = res.data || {};
      const items = Array.isArray(data.items) ? data.items.map(mapCustomer) : [];
      setCustomers((prev) => isFirstPage ? items : [...prev, ...items]);
      setNextCursor(data.next_cursor || null);
      setHasMore(Boolean(data.has_more));
    } catch (error) {
      if (error.response && error.response.status !== 401) {
        toast.error(t('customers.loadingError'));
      }
    } finally {
      if (seq === requestSeqRef.current) {
      setLoading(false);
        setIsFetchingMore(false);
      }
    }
  };

  // Socket handler'ları ve infinite scroll observer'ının stale closure yakalamaması için
  // fetchCustomers referansını ref'te güncel tut.
  const fetchCustomersRef = useRef(fetchCustomers);
  useEffect(() => { fetchCustomersRef.current = fetchCustomers; });

  // Backward-compat alias: mevcut CRUD handler'ları optimistik güncellemeden sonra
  // "arka planda listeyi yenile" niyetiyle bu fonksiyonu çağırıyor.
  const loadCustomers = () => fetchCustomersRef.current({ search: searchRef.current });

  // Tek arama-tetikleyici useEffect: mount'ta bir kez ("" ile) ve debouncedSearch
  // değiştiğinde tetiklenir. Bu, mount'ta çift `loadCustomers` çağrısı önleyerek
  // önceki refactor'daki race guard takılmasını ortadan kaldırır.
  useEffect(() => {
    fetchCustomersRef.current({ search: debouncedSearch });
  }, [debouncedSearch]);

  // IntersectionObserver — sentinel görünür olunca sonraki cursor sayfasını çek.
  useEffect(() => {
    if (!sentinelRef.current || !hasMore || isFetchingMore || loading) return;
    const el = sentinelRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry && entry.isIntersecting && nextCursor && hasMore && !isFetchingMore) {
          fetchCustomersRef.current({ cursor: nextCursor, search: searchRef.current });
        }
      },
      { rootMargin: "200px 0px", threshold: 0.01 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, isFetchingMore, loading, nextCursor]);

  const loadCustomerHistory = async (phone) => {
    try {
      setLoadingHistory(true);
      const response = await api.get(`/customers/${phone}/history`);
      let appointments = response.data.appointments || [];
      if (userRole === 'staff' && currentStaffUsername) {
        appointments = appointments.filter(apt => apt.staff_member_id === currentStaffUsername);
      }
      setCustomerHistory({ ...response.data, appointments: appointments });
      setCustomerNotes(response.data.notes || "");
    } catch (error) {
      toast.error(t('customers.historyLoadingError'));
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleCustomerClick = async (customer) => {
    setSelectedCustomer(customer);
    setDetailTab("overview");
    await loadCustomerHistory(customer.phone);
  };

  const handleCall = (phone) => {
    window.location.href = `tel:${phone}`;
  };

  const handleWhatsApp = (phone) => {
    let cleanPhone = phone.replace(/\D/g, "");
    if (cleanPhone.startsWith("0")) cleanPhone = cleanPhone.substring(1);
    if (!cleanPhone.startsWith("90")) cleanPhone = "90" + cleanPhone;
    window.open(`https://wa.me/${cleanPhone}`, "_blank");
  };

  const handleSaveNotes = async () => {
    if (selectedCustomer) {
      try {
        await api.put(`/customers/${selectedCustomer.phone}/notes`, { notes: customerNotes });
        toast.success(t('customers.notesSaved'));
      } catch (error) {
        toast.error(error.response?.data?.detail || t('customers.notesSaveError'));
      }
    }
  };

  const getInitials = (name) => {
    if (!name) return "??";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  const handleDeleteCustomer = async () => {
    if (!customerToDelete) return;
    setDeleting(true);
    try {
      const response = await api.delete(`/customers/${customerToDelete.phone}`);
      toast.success(response.data?.message || t('customers.deleteSuccess'));
      if (selectedCustomer && selectedCustomer.phone === customerToDelete.phone) {
        setSelectedCustomer(null); setCustomerHistory(null); setCustomerNotes("");
      }
      // Optimistik silme — hemen local state'den kaldır
      setCustomers(prev => prev.filter(c => c.phone !== customerToDelete.phone));
      setDeleteDialogOpen(false); setCustomerToDelete(null);
      // Arka planda tam listeyi yenile
      loadCustomers();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('customers.deleteError'));
    } finally {
      setDeleting(false);
    }
  };

  const handleAddNewCustomer = async () => {
    if (!newCustomerData.name.trim() || !newCustomerData.phone.trim()) {
      toast.error(t('customers.addValidationNamePhone'));
      return;
    }
    const cleanPhone = newCustomerData.phone.replace(/\D/g, "");
    if (cleanPhone.length < 10) {
      toast.error(t('customers.addValidationPhone'));
      return;
    }
    setSavingCustomer(true);
    try {
      const response = await api.post("/customers", {
        name: newCustomerData.name.trim(),
        phone: newCustomerData.phone.trim()
      });
      toast.success(response.data?.message || t('customers.addSuccess'));
      setNewCustomerDialogOpen(false);
      // Optimistik güncelleme — hemen local state'e ekle
      const newCust = { name: newCustomerData.name.trim(), phone: newCustomerData.phone.replace(/\D/g, ''), totalAppointments: 0, isPending: true };
      setCustomers(prev => [newCust, ...prev]);
      setNewCustomerData({ name: "", phone: "" });
      // Arka planda tam listeyi de yenile
      loadCustomers();
    } catch (error) {
      const errorMessage = error.response?.data?.detail || t('customers.addError');
      toast.error(errorMessage);
    } finally {
      setSavingCustomer(false);
    }
  };

  // --- MÜŞTERİ DÜZENLEME ---
  const handleOpenEditDialog = () => {
    if (!selectedCustomer) return;
    setEditData({ name: selectedCustomer.name, phone: selectedCustomer.phone });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!selectedCustomer || !editData.name.trim()) {
      toast.error(i18n.language === 'tr' ? 'Müşteri adı boş olamaz' : 'Customer name cannot be empty');
      return;
    }
    setSavingEdit(true);
    try {
      await api.put(`/customers/${selectedCustomer.phone}`, {
        name: editData.name.trim(),
        phone: editData.phone.trim() !== selectedCustomer.phone ? editData.phone.trim() : undefined
      });
      toast.success(i18n.language === 'tr' ? 'Müşteri güncellendi' : 'Customer updated');
      setEditDialogOpen(false);
      const updatedPhone = editData.phone.trim() || selectedCustomer.phone;
      setSelectedCustomer({ ...selectedCustomer, name: editData.name.trim(), phone: updatedPhone });
      await loadCustomers();
      await loadCustomerHistory(updatedPhone);
    } catch (error) {
      toast.error(error.response?.data?.detail || (i18n.language === 'tr' ? 'Güncelleme başarısız' : 'Update failed'));
    } finally {
      setSavingEdit(false);
    }
  };

  // --- REHBER İŞLEMLERİ ---

  const handleImportButtonClick = () => {
    // Destek kontrolü yap
    const isSupported = Capacitor.isNativePlatform() || 
                       ('contacts' in navigator && 'ContactsManager' in window);
    
    if (!isSupported) {
      setShowNotSupportedDialog(true);
      return;
    }
    
    if (Capacitor.isNativePlatform()) {
      // Native: seçim dialogu göster (Tümünü Aktar / Seçerek Aktar)
      setShowImportChoiceDialog(true);
    } else {
      // Web: browser picker direkt açılır, seçim dialogu anlamsız
      startImportProcess({ mode: 'SELECT' });
    }
  };

  const handleImportAll = async () => {
    setShowImportChoiceDialog(false);
    await startImportProcess({ mode: 'ALL' });
  };

  const handleImportSelect = async () => {
    setShowImportChoiceDialog(false);
    await startImportProcess({ mode: 'SELECT' });
  };

  const startImportProcess = async ({ mode }) => {
    if (Capacitor.isNativePlatform()) {
      setImportingContacts(true);
      let dialogOpened = false;
      try {
        const platform = Capacitor.getPlatform(); // 'ios' veya 'android'

        if (mode === 'SELECT' && platform === 'ios') {
          // iOS: Custom native plugin (CNContactPickerViewController) açar
          // İzin gerektirmez, her seferinde picker açılır
          const result = await ContactPicker.pickContacts();

          if (!result.contacts || result.contacts.length === 0) {
            toast.info("Kişi seçilmedi.");
            return;
          }

          const normalizedContacts = result.contacts
            .map(c => ({
              name: c.name || '',
              phone: c.phone || ''
            }))
            .filter(c => c.name && c.phone);

          if (normalizedContacts.length === 0) {
            toast.warning("Seçilen kişilerin telefon numarası bulunamadı.");
            return;
          }

          await saveContactsBatch(normalizedContacts);

        } else if (mode === 'SELECT' && platform === 'android') {
          // Android: Contacts.getContacts() + seçim dialogu göster
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

          const normalizedContacts = result.contacts
            .map(c => ({
              name: c.name?.display || ((c.name?.given || '') + " " + (c.name?.family || '')).trim(),
              phone: c.phones?.[0]?.number
            }))
            .filter(c => c.name && c.phone);

          setFetchedContacts(normalizedContacts);
          setSelectedContactPhones(new Set());
          setContactSearchTerm("");
          setShowContactSelectionDialog(true);
          dialogOpened = true;

        } else {
          // ALL mode: tüm rehbere erişim iste (her iki platform)
          const permission = await Contacts.requestPermissions();
          if (permission.contacts !== 'granted' && permission.contacts !== 'limited') {
            toast.error("Rehber izni verilmedi. Ayarlardan izin verin.");
            return;
          }

          const result = await Contacts.getContacts({
            projection: { name: true, phones: true }
          });

          if (!result.contacts || result.contacts.length === 0) {
            toast.info("Rehber boş veya erişim izni verilmedi.");
            return;
          }

          const normalizedContacts = result.contacts
            .map(c => ({
              name: c.name?.display || ((c.name?.given || '') + " " + (c.name?.family || '')).trim(),
              phone: c.phones?.[0]?.number
            }))
            .filter(c => c.name && c.phone);

          await saveContactsBatch(normalizedContacts);
        }

      } catch (error) {
        console.error("Contacts error:", error);
        if (!error.message?.includes('canceled') && !error.message?.includes('cancelled')) {
          toast.error("Rehber okunurken hata oluştu: " + (error.message || ''));
        }
      } finally {
        if (!dialogOpened) {
          setImportingContacts(false);
        }
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
          }));
          await saveContactsBatch(normalized);
        }
      } catch (e) {
        console.error("Web contacts error:", e);
      } finally {
        setImportingContacts(false);
      }
    }
  };

  const handleSaveSelectedContacts = async () => {
    const selectedList = fetchedContacts.filter(c => selectedContactPhones.has(c.phone));
    
    if (selectedList.length === 0) {
      toast.warning("Lütfen en az bir kişi seçin.");
      return;
    }

    setShowContactSelectionDialog(false);
    setImportingContacts(true);
    try {
      await saveContactsBatch(selectedList);
    } catch (err) {
      console.error("saveContactsBatch error:", err);
      toast.error("Kişiler eklenirken hata oluştu.");
    } finally {
      setImportingContacts(false);
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

  const saveContactsBatch = async (contactList) => {
    toast.info(`${contactList.length} kişi işleniyor...`);
    let successCount = 0;
    let duplicateCount = 0;
    let lastError = null;

    for (const contact of contactList) {
      let cleanPhone = contact.phone.replace(/\D/g, "");
      if (cleanPhone.length === 10) cleanPhone = '90' + cleanPhone;
      else if (cleanPhone.length === 11 && cleanPhone.startsWith('0')) cleanPhone = '90' + cleanPhone.substring(1);
      else if (cleanPhone.length === 12 && cleanPhone.startsWith('90')) { /* already correct */ }
      else if (cleanPhone.length === 13 && cleanPhone.startsWith('090')) cleanPhone = cleanPhone.substring(1);

      if (cleanPhone.length >= 10) {
        try {
          await api.post("/customers", { name: contact.name.trim(), phone: cleanPhone });
          successCount++;
        } catch (e) {
          const detail = e.response?.data?.detail || '';
          if (detail.includes('zaten var') || e.response?.status === 400) {
            duplicateCount++;
          } else {
            lastError = detail || e.message;
          }
          console.log(`Contact import error for ${contact.name} (${cleanPhone}):`, detail);
        }
      }
    }

    if (successCount > 0) {
      toast.success(`${successCount} kişi eklendi!${duplicateCount > 0 ? ` (${duplicateCount} zaten mevcut)` : ''}`);
      await loadCustomers();
    } else if (duplicateCount > 0) {
      toast.info(`${duplicateCount} kişi zaten kayıtlı.`);
    } else {
      toast.error(lastError || "Kişiler eklenemedi.");
    }
  };

  // Server-side arama aktif (debounced + cursor pagination) — client-side filter kaldırıldı.
  // Yalnızca kullanıcı yazarken (debounce dolmadan önce) anlık local filtre uygular ki
  // ekran boş kalmasın; sunucudan yeni sayfa gelince zaten items yenilenir.
  const filteredCustomers = searchTerm && searchTerm !== debouncedSearch
    ? customers.filter(c =>
        (c.name || '').toLocaleLowerCase('tr').includes(searchTerm.toLocaleLowerCase('tr')) ||
        (c.phone || '').includes(searchTerm)
      )
    : customers;

  if (selectedCustomer) {
    // ── Türetilmiş istatistikler (Genel Bakış sekmesi için) ──
    const appts = customerHistory?.appointments || [];
    const isCompleted = (s) => s === 'Tamamlandı' || s === 'Completed';
    const isCancelled = (s) => s === 'İptal Edildi' || s === 'İptal' || s === 'Cancelled';
    // Fiyat = randevu anındaki SNAPSHOT (sonradan hizmet fiyatı değişse de bozulmaz).
    // Çoklu hizmet kalemleri price_snapshot tutar; tekli randevu service_price tutar.
    const apptPrice = (a) => {
      if (Array.isArray(a?.services) && a.services.length) {
        return a.services.reduce((sum, x) => sum + (Number(x?.price_snapshot ?? x?.price) || 0), 0);
      }
      return Number(a?.service_price) || 0;
    };
    // Görünen hizmet adı: çoklu hizmet ise "A + B" olarak birleştir.
    const apptServiceName = (a) => {
      if (Array.isArray(a?.services) && a.services.length) {
        const joined = a.services.map(x => x?.name_snapshot).filter(Boolean).join(' + ');
        if (joined) return joined;
      }
      return a?.service_name || t('customers.noData');
    };
    const supportPhoneClean = (settings?.support_phone || '').replace(/\s/g, '');
    const currencySymbol = (supportPhoneClean.startsWith('+44') || supportPhoneClean.startsWith('44')) ? '£' : '₺';
    const formatMoney = (amount) => {
      const n = Math.round(Number(amount) || 0);
      return i18n.language === 'en'
        ? `${currencySymbol}${n.toLocaleString('en-GB')}`
        : `${n.toLocaleString('tr-TR')}${currencySymbol}`;
    };
    const formatPct = (pct) => (i18n.language === 'en' ? `${pct}%` : `%${pct}`);
    // ÖZET yalnız TAMAMLANMIŞ randevulara dayanır — ileri tarihli/bekleyen randevular
    // tamamlanana kadar özete (sayı/harcama/son randevu) yansımaz.
    const completedAppts = appts.filter(a => isCompleted(a.status));
    const totalCount = completedAppts.length;
    const totalSpent = completedAppts.reduce((s, a) => s + apptPrice(a), 0);
    const apptsByDateDesc = [...appts].sort((a, b) =>
      new Date(`${b.appointment_date}T${b.appointment_time || '00:00'}`) - new Date(`${a.appointment_date}T${a.appointment_time || '00:00'}`)
    );
    const lastApt = [...completedAppts].sort((a, b) =>
      new Date(`${b.appointment_date}T${b.appointment_time || '00:00'}`) - new Date(`${a.appointment_date}T${a.appointment_time || '00:00'}`)
    )[0];
    // Sıklık (yalnız tamamlanan): çoklu hizmet randevularında her alt hizmeti ayrı say.
    const freq = {};
    completedAppts.forEach(a => {
      if (Array.isArray(a?.services) && a.services.length) {
        a.services.forEach(x => { const n = x?.name_snapshot; if (n) freq[n] = (freq[n] || 0) + 1; });
      } else {
        const n = a?.service_name; if (n) freq[n] = (freq[n] || 0) + 1;
      }
    });
    const topServices = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const totalForPct = Object.values(freq).reduce((s, n) => s + n, 0) || 1;

    const tabs = [
      { id: 'overview', label: t('customers.tabOverview') },
      { id: 'history', label: t('customers.tabHistory') },
      { id: 'notes', label: t('customers.tabNotes') },
    ];

    const StatusBadge = ({ status }) => (
      <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
        status === t('dashboard.status.completed') || status === 'Tamamlandı' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
        status === t('dashboard.status.pending') || status === 'Bekliyor' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
        status === 'İptal Edildi' || status === 'Cancelled' ? 'bg-red-50 text-red-700 border border-red-200' :
        'bg-zinc-100 text-zinc-600 border border-zinc-200'
      }`}>{status}</span>
    );

    const AptRow = ({ apt, showSessionBadge }) => {
      const price = apptPrice(apt);
      const cancelled = isCancelled(apt.status);
      return (
        <div className="flex items-start gap-3 py-4">
          <span className="w-[68px] shrink-0 text-xs text-zinc-400 font-medium leading-snug pt-0.5">
            {format(new Date(apt.appointment_date), "d MMM yyyy", { locale: dateLocale })}
          </span>
          <div className="flex-1 min-w-0">
            <p className={`text-sm font-semibold leading-snug break-words ${cancelled ? 'text-zinc-400 line-through' : 'text-zinc-800'}`}>
              {apptServiceName(apt)}
            </p>
            {showSessionBadge && (
              <div className="mt-1"><SessionBadge number={apt.session_number} total={apt.session_total} size="sm" /></div>
            )}
            {SHOW_APPOINTMENT_CARD_STATUS && price <= 0 && (
              <div className="mt-1"><StatusBadge status={apt.status} /></div>
            )}
              </div>
          {price > 0 && (
            <span className={`shrink-0 text-sm font-semibold whitespace-nowrap pt-0.5 ${cancelled ? 'text-zinc-400 line-through' : 'text-zinc-900'}`}>
              {formatMoney(price)}
            </span>
              )}
            </div>
      );
    };

    const renderHistoryList = () => {
      if (loadingHistory) {
        return (
          <div className="text-center py-10">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 mx-auto mb-3"></div>
            <p className="text-zinc-500 font-medium text-sm">{t('customers.loading')}</p>
              </div>
        );
      }
      if (!(customerHistory && customerHistory.appointments.length > 0)) {
        return <p className="text-zinc-400 text-center py-10 font-medium text-sm">{t('customers.historyEmpty')}</p>;
      }
                const sessionGroups = {};
                const singles = [];
      apptsByDateDesc.forEach(apt => {
                  if (apt.session_group_id) {
                    if (!sessionGroups[apt.session_group_id]) sessionGroups[apt.session_group_id] = [];
                    sessionGroups[apt.session_group_id].push(apt);
                  } else {
                    singles.push(apt);
                  }
                });
                Object.values(sessionGroups).forEach(g => g.sort((a, b) => (a.session_number || 0) - (b.session_number || 0)));
                const groupEntries = Object.entries(sessionGroups).map(([gid, apts]) => ({
                  type: 'group', gid, apts,
                  sortDate: new Date(`${apts[0].appointment_date}T${apts[0].appointment_time || '00:00'}`)
                }));
                const singleEntries = singles.map(apt => ({
                  type: 'single', apt,
                  sortDate: new Date(`${apt.appointment_date}T${apt.appointment_time || '00:00'}`)
                }));
                const allEntries = [...groupEntries, ...singleEntries].sort((a, b) => b.sortDate - a.sortDate);
                return (
        <div className="divide-y divide-zinc-50">
                    {allEntries.map((entry, idx) => {
                      if (entry.type === 'single') {
                        return <AptRow key={entry.apt.id || idx} apt={entry.apt} showSessionBadge={false} />;
                      }
                      const { gid, apts } = entry;
                      const firstApt = apts[0];
                      const activeCount = apts.filter(a => a.status !== 'İptal Edildi' && a.status !== 'Cancelled').length;
                      return (
              <details key={gid} className="group py-2">
                <summary className="flex items-center justify-between py-2 cursor-pointer list-none select-none">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 bg-zinc-100 rounded-lg shrink-0">
                                <span className="text-xs font-black text-zinc-700">{apts.length}x</span>
                              </div>
                    <div className="min-w-0">
                      <p className="font-bold text-zinc-900 text-sm break-words">{apptServiceName(firstApt)}</p>
                      <p className="text-xs text-zinc-400">{activeCount}/{apts.length} {i18n.language === 'tr' ? 'aktif seans' : 'active sessions'}</p>
                              </div>
                            </div>
                            <svg className="w-4 h-4 text-zinc-400 transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                          </summary>
                <div className="pl-11">
                            {apts.map(apt => <AptRow key={apt.id} apt={apt} showSessionBadge={true} />)}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                );
    };

    const SummaryCell = ({ label, value }) => (
      <div className="px-3 text-center">
        <p className="text-[11px] text-zinc-400 font-medium mb-2 leading-snug">{label}</p>
        <p className="text-[17px] font-semibold text-zinc-900 tracking-tight tabular-nums leading-none">{value}</p>
      </div>
    );

    return (
      <div className="min-h-screen bg-zinc-50 pb-24">
        <div className="max-w-2xl mx-auto p-4 space-y-4">
          <button
            onClick={() => { setSelectedCustomer(null); setCustomerHistory(null); setCustomerNotes(""); setDetailTab("overview"); }}
            className="flex items-center gap-2 px-2 py-2 text-zinc-500 hover:text-zinc-900 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-bold">{t('customers.backToCustomers')}</span>
          </button>

          {/* Profil kartı */}
          <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm p-6">
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-zinc-700 to-zinc-900 text-white rounded-full flex items-center justify-center font-black text-2xl mb-4 shadow-sm">
                {getInitials(selectedCustomer.name)}
              </div>
              <h2 className="text-xl font-black text-zinc-900 mb-1">{selectedCustomer.name}</h2>
              <div className="flex items-center gap-1.5 text-zinc-500 font-medium text-sm mb-5">
                <Phone className="w-3.5 h-3.5" />
                <span>{selectedCustomer.phone}</span>
              </div>
              <div className="flex gap-3 w-full max-w-xs">
                <Button onClick={() => handleCall(selectedCustomer.phone)} variant="outline" className="flex-1 border-zinc-200 text-zinc-700 hover:bg-zinc-50 rounded-xl font-bold h-11">
                  <Phone className="w-4 h-4 mr-2" /> {t('customers.actions.call')}
                </Button>
                <Button onClick={() => handleWhatsApp(selectedCustomer.phone)} className="flex-1 bg-green-500 hover:bg-green-600 text-white rounded-xl font-bold shadow-sm h-11">
                  <MessageSquare className="w-4 h-4 mr-2" /> {t('customers.actions.whatsapp')}
                </Button>
              </div>
              {userRole === 'admin' && (
                <div className="flex gap-2 w-full max-w-xs mt-3">
                  <Button onClick={handleOpenEditDialog} variant="outline" className="flex-1 border-zinc-200 text-zinc-700 hover:bg-zinc-50 rounded-xl font-bold h-11">
                    <Edit2 className="w-4 h-4 mr-2" /> {i18n.language === 'tr' ? 'Düzenle' : 'Edit'}
                  </Button>
                  <Button onClick={() => { setCustomerToDelete(selectedCustomer); setDeleteDialogOpen(true); }} variant="outline" className="flex-1 border-red-200 text-red-600 hover:bg-red-50 rounded-xl font-bold h-11">
                    <Trash2 className="w-4 h-4 mr-2" /> {t('customers.deleteButton')}
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Sekmeler + içerik */}
          <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm overflow-hidden">
            <div className="flex border-b border-zinc-100">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setDetailTab(tab.id)}
                  className={`flex-1 py-3.5 text-sm font-bold transition-colors relative ${
                    detailTab === tab.id ? 'text-zinc-900' : 'text-zinc-400 hover:text-zinc-600'
                  }`}
                >
                  {tab.label}
                  {detailTab === tab.id && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-10 h-0.5 bg-zinc-900 rounded-full" />
                  )}
                </button>
              ))}
            </div>

            <div className="p-5">
              {/* GENEL BAKIŞ */}
              {detailTab === 'overview' && (
                loadingHistory ? (
                  <div className="text-center py-10">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 mx-auto mb-3"></div>
                    <p className="text-zinc-500 font-medium text-sm">{t('customers.loading')}</p>
                  </div>
                ) : (
                  <div className="space-y-5">
                    {/* Özet */}
                    <div className="rounded-xl border border-zinc-100 p-4">
                      <p className="text-sm font-semibold text-zinc-900 mb-4">{t('customers.summaryTitle')}</p>
                      <div className="grid grid-cols-3 divide-x divide-zinc-100">
                        <SummaryCell label={t('customers.summaryTotalAppointments')} value={totalCount} />
                        <SummaryCell label={t('customers.summaryTotalSpent')} value={totalSpent > 0 ? formatMoney(totalSpent) : t('customers.noData')} />
                        <SummaryCell label={t('customers.summaryLastAppointment')} value={lastApt ? format(new Date(lastApt.appointment_date), "d MMM yyyy", { locale: dateLocale }) : t('customers.noData')} />
                      </div>
                    </div>

                    {/* En Çok Yaptığı İşlemler */}
                    <div className="rounded-xl border border-zinc-100 p-4">
                      <p className="text-sm font-semibold text-zinc-900 mb-4">{t('customers.topServicesTitle')}</p>
                      {topServices.length > 0 ? (
                        <div className="space-y-4">
                          {topServices.map(([name, count]) => {
                            const pct = Math.round((count / totalForPct) * 100);
                            const barW = Math.min(100, Math.max(3, pct));
                            return (
                              <div key={name}>
                                <div className="flex items-baseline justify-between gap-3 mb-1.5">
                                  <span className="text-sm text-zinc-700 font-medium break-words min-w-0">{name}</span>
                                  <span className="shrink-0 text-sm font-bold text-zinc-900">{formatPct(pct)}</span>
                                </div>
                                <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
                                  <div className="h-full bg-zinc-900 rounded-full transition-all" style={{ width: `${barW}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-zinc-400 text-center py-6 font-medium text-sm">{t('customers.historyEmpty')}</p>
            )}
          </div>
                  </div>
                )
              )}

              {/* GEÇMİŞ — Son İşlemler */}
              {detailTab === 'history' && (
                <div>
                  <p className="text-sm font-semibold text-zinc-900 mb-2">{t('customers.recentTransactionsTitle')}</p>
                  {renderHistoryList()}
                </div>
              )}

              {/* NOTLAR */}
              {detailTab === 'notes' && (
            <div className="space-y-3">
                  <Textarea value={customerNotes} onChange={(e) => setCustomerNotes(e.target.value)} placeholder={t('customers.notesPlaceholder')} rows={5} className="bg-zinc-50 border-zinc-200 rounded-xl font-medium focus:ring-2 focus:ring-zinc-900" />
                  <Button onClick={handleSaveNotes} className="w-full bg-zinc-900 hover:bg-black text-white rounded-xl h-12 font-bold shadow-sm">
                {t('common.save')}
              </Button>
                </div>
              )}
            </div>
          </div>
        </div>
        
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-xl font-black text-zinc-900">{t('customers.deleteTitle')}</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-600 font-medium">
                {customerToDelete && (
                  <>
                    <strong>{customerToDelete.name}</strong> {i18n.language === 'tr' ? 'müşterisini ve tüm randevularını silmek istediğinize emin misiniz?' : 'customer and all their appointments?'}
                    <br /> <span className="text-red-600 font-bold">{t('customers.deleteWarning')}</span>
                  </>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleting} className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteCustomer} disabled={deleting} className="bg-red-600 hover:bg-red-700 rounded-xl font-bold shadow-lg">
                {deleting ? t('customers.deleting') : t('customers.actions.delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Müşteri Düzenleme Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
            <DialogHeader>
              <DialogTitle className="text-xl font-black text-zinc-900">
                {i18n.language === 'tr' ? 'Müşteri Düzenle' : 'Edit Customer'}
              </DialogTitle>
              <DialogDescription className="text-zinc-600 font-medium">
                {i18n.language === 'tr' ? 'Müşteri bilgilerini güncelleyin' : 'Update customer information'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>{i18n.language === 'tr' ? 'Ad Soyad' : 'Full Name'}</Label>
                <Input
                  value={editData.name}
                  onChange={(e) => setEditData(prev => ({ ...prev, name: e.target.value }))}
                  className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl"
                />
              </div>
              <div className="space-y-2">
                <Label>{i18n.language === 'tr' ? 'Telefon' : 'Phone'}</Label>
                <Input
                  value={editData.phone}
                  onChange={(e) => setEditData(prev => ({ ...prev, phone: e.target.value }))}
                  className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)} disabled={savingEdit} className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">
                {t('common.cancel')}
              </Button>
              <Button onClick={handleSaveEdit} disabled={savingEdit} className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg">
                {savingEdit ? (i18n.language === 'tr' ? 'Kaydediliyor...' : 'Saving...') : t('common.save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 pb-20">
      <div className="p-4 space-y-4">
        {onNavigate && (
          <button onClick={() => onNavigate("dashboard")} className="flex items-center gap-2 px-3 py-2 text-zinc-700 hover:text-zinc-900 hover:bg-white/50 rounded-xl transition-colors">
            <ArrowLeft className="w-5 h-5" /> <span className="text-sm font-bold">{t('customers.backToHome')}</span>
          </button>
        )}
        
        <div className="sticky top-0 z-10 backdrop-blur-2xl bg-gradient-to-br from-gray-50/80 via-blue-50/50 to-purple-50/30 pb-4 pt-2 -mx-4 px-4">
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-zinc-400" />
            <Input type="text" placeholder={t('customers.searchPlaceholder')} value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-10 backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-12 shadow-sm focus:ring-2 focus:ring-zinc-900 font-medium" />
          </div>
          
          {userRole === 'admin' && (
            <div className="space-y-2">
              <Button onClick={() => setNewCustomerDialogOpen(true)} className="w-full bg-zinc-900 hover:bg-black text-white rounded-xl h-12 font-bold shadow-lg">
                <Plus className="w-5 h-5 mr-2" /> {t('customers.newCustomer')}
              </Button>
              
              <Button
                onClick={handleImportButtonClick}
                disabled={importingContacts}
                variant="outline"
                className="w-full backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 text-zinc-700 rounded-xl h-12 font-bold shadow-sm"
              >
                {importingContacts ? (
                  <>
                    <div className="animate-spin h-5 w-5 border-2 border-zinc-900 border-t-transparent rounded-full mr-2" />
                    {t('customers.importing', 'İçe aktarılıyor...')}
                  </>
                ) : (
                  <>
                    <Import className="w-5 h-5 mr-2" />
                    {t('customers.importFromContacts', 'Rehberden Ekle')}
                  </>
                )}
              </Button>
            </div>
          )}
        </div>

        <div className="space-y-3">
          {loading ? (
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-8 text-center shadow-lg">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 mx-auto mb-3"></div>
              <p className="text-zinc-600 font-medium">{t('customers.loading')}</p>
            </div>
          ) : filteredCustomers.length === 0 ? (
            <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-8 text-center shadow-lg">
              <p className="text-zinc-600 font-medium">{t('customers.noResults')}</p>
            </div>
          ) : (
            <>
              {filteredCustomers.map((customer) => (
              <div key={customer.phone} className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-4 shadow-lg hover:shadow-xl hover:bg-white/50 transition-all duration-300">
                <div className="flex items-center gap-4">
                    <div onClick={() => handleCustomerClick(customer)} className="w-12 h-12 bg-gradient-to-br from-zinc-800 to-zinc-950 text-white rounded-xl flex items-center justify-center font-semibold text-base flex-shrink-0 cursor-pointer shadow-sm ring-1 ring-black/5">
                    {getInitials(customer.name)}
                  </div>
                  <div onClick={() => handleCustomerClick(customer)} className="flex-1 min-w-0 cursor-pointer">
                    <h3 className="text-zinc-900 font-black text-base truncate">{customer.name}</h3>
                    <p className="text-zinc-600 text-sm truncate font-medium">{customer.phone}</p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {userRole === 'admin' && (
                      <button onClick={(e) => { e.stopPropagation(); setCustomerToDelete(customer); setDeleteDialogOpen(true); }} className="p-2 text-red-600 hover:bg-red-50 rounded-xl transition-colors">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                    <ChevronRight onClick={() => handleCustomerClick(customer)} className="w-5 h-5 text-zinc-400 cursor-pointer" />
                  </div>
                </div>
              </div>
              ))}
              {/* Infinite scroll sentinel — görünür olunca sonraki cursor sayfası çekilir */}
              {hasMore && (
                <div ref={sentinelRef} className="py-4 flex items-center justify-center">
                  {isFetchingMore && (
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-900" />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      
      {/* Silme Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-zinc-900">{t('customers.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-600 font-medium">
              {customerToDelete && (
                <>
                  <strong>{customerToDelete.name}</strong> {i18n.language === 'tr' ? 'müşterisini ve tüm randevularını silmek istediğinize emin misiniz?' : 'customer and all their appointments?'}
                  <br /> <span className="text-red-600 font-bold">{t('customers.deleteWarning')}</span>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting} className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteCustomer} disabled={deleting} className="bg-red-600 hover:bg-red-700 rounded-xl font-bold shadow-lg">
              {deleting ? t('customers.deleting') : t('customers.actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      
      {/* Yeni Müşteri Dialog */}
      <Dialog open={newCustomerDialogOpen} onOpenChange={setNewCustomerDialogOpen}>
        <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-zinc-900">{t('customers.addTitle')}</DialogTitle>
            <DialogDescription className="text-zinc-600 font-medium">{t('customers.addDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new-customer-name" className="text-sm font-bold text-zinc-700">{t('customers.fields.name')} *</Label>
              <Input id="new-customer-name" type="text" placeholder={t('customers.fields.name')} value={newCustomerData.name} onChange={(e) => setNewCustomerData({ ...newCustomerData, name: e.target.value })} className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium" autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-customer-phone" className="text-sm font-bold text-zinc-700">{t('customers.fields.phone')} *</Label>
              <Input id="new-customer-phone" type="tel" placeholder={i18n.language === 'en' ? '+44 XXXX XXXXXX' : '05XX XXX XX XX'} value={newCustomerData.phone} onChange={(e) => setNewCustomerData({ ...newCustomerData, phone: e.target.value })} className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium" />
            </div>
          </div>
          <DialogFooter className="border-t border-white/30 pt-4">
            <Button variant="outline" onClick={() => { setNewCustomerDialogOpen(false); setNewCustomerData({ name: "", phone: "" }); }} disabled={savingCustomer} className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">{t('common.cancel')}</Button>
            <Button onClick={handleAddNewCustomer} disabled={savingCustomer || !newCustomerData.name.trim() || !newCustomerData.phone.trim()} className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg">
              {savingCustomer ? t('customers.saving') : t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Seçim Dialogu */}
      <Dialog open={showImportChoiceDialog} onOpenChange={setShowImportChoiceDialog}>
        <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-zinc-900">{t('customers.importDialog.title')}</DialogTitle>
            <DialogDescription className="text-zinc-600 font-medium">
              {t('customers.importDialog.desc')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-6">
            {/* Tümünü Aktar - Primary Style */}
            <button
              onClick={handleImportAll}
              className="group relative overflow-hidden backdrop-blur-xl bg-gradient-to-br from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 border-2 border-white/20 rounded-2xl p-6 transition-all duration-300 hover:shadow-2xl hover:scale-[1.02] active:scale-[0.98]"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0 group-hover:bg-white/30 transition-colors">
                  <Users className="w-6 h-6 text-white" />
                </div>
                <div className="flex flex-col items-start text-left flex-1">
                  <span className="font-black text-white text-lg mb-1">{t('customers.importDialog.importAll')}</span>
                  <span className="text-sm text-white/90 font-medium">{t('customers.importDialog.importAllDesc')}</span>
                </div>
              </div>
              <div className="absolute top-2 right-2">
                <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                  <ChevronRight className="w-4 h-4 text-white" />
                </div>
              </div>
            </button>

            {/* Seçerek Aktar - Secondary Style */}
            <button
              onClick={handleImportSelect}
              className="group relative overflow-hidden backdrop-blur-xl bg-white/60 hover:bg-white/80 border-2 border-zinc-200 hover:border-zinc-300 rounded-2xl p-6 transition-all duration-300 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center flex-shrink-0 group-hover:bg-green-200 transition-colors">
                  <CheckSquare className="w-6 h-6 text-green-600" />
                </div>
                <div className="flex flex-col items-start text-left flex-1">
                  <span className="font-black text-zinc-900 text-lg mb-1">{t('customers.importDialog.importSelect')}</span>
                  <span className="text-sm text-zinc-600 font-medium">{t('customers.importDialog.importSelectDesc')}</span>
                </div>
              </div>
              <div className="absolute top-2 right-2">
                <div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center group-hover:bg-zinc-200 transition-colors">
                  <ChevronRight className="w-4 h-4 text-zinc-600" />
                </div>
              </div>
            </button>
          </div>
          <DialogFooter className="border-t border-white/30 pt-4">
            <Button variant="outline" onClick={() => setShowImportChoiceDialog(false)} className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">{t('common.cancel')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                        {isSelected && <Users className="w-3 h-3 text-white" />}
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
            <Button onClick={handleSaveSelectedContacts} className="bg-zinc-900 hover:bg-black text-white rounded-xl font-bold shadow-lg">
              {t('customers.importDialog.addSelected', { count: selectedContactPhones.size })}
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

export default Customers;