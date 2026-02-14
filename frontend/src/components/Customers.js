import { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import { Search, Phone, MessageSquare, ChevronRight, Plus, ArrowLeft, Trash2, Import, Users, CheckSquare, X } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";

// --- HİBRİT YAPI İÇİN GEREKLİ IMPORTLAR ---
import { Capacitor } from '@capacitor/core';
import { Contacts } from '@capacitor-community/contacts';
// ------------------------------------------

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
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

const Customers = ({ onNavigate, onNewAppointment }) => {
  const { userRole, token } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  const [currentStaffUsername, setCurrentStaffUsername] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerHistory, setCustomerHistory] = useState(null);
  const [customerNotes, setCustomerNotes] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [customerToDelete, setCustomerToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [newCustomerDialogOpen, setNewCustomerDialogOpen] = useState(false);
  const [newCustomerData, setNewCustomerData] = useState({ name: "", phone: "" });
  const [savingCustomer, setSavingCustomer] = useState(false);
  const [settings, setSettings] = useState(null);
  
  // --- REHBER ENTEGRASYONU STATE'LERİ ---
  const [importingContacts, setImportingContacts] = useState(false);
  const [showImportChoiceDialog, setShowImportChoiceDialog] = useState(false);
  const [showContactSelectionDialog, setShowContactSelectionDialog] = useState(false);
  
  const [fetchedContacts, setFetchedContacts] = useState([]); // Tüm rehber
  const [contactSearchTerm, setContactSearchTerm] = useState(""); // Rehber içi arama
  const [selectedContactPhones, setSelectedContactPhones] = useState(new Set()); // Seçilenlerin telefonları (Unique ID olarak)
  
  const [showNotSupportedDialog, setShowNotSupportedDialog] = useState(false);
  // ---------------------------------------

  const socketRef = useRef(null);

  const loadSettings = async () => {
    try {
      const response = await api.get("/settings");
      setSettings(response.data);
    } catch (error) { }
  };

  useEffect(() => {
    const initialize = async () => {
      await loadSettings();
      if (userRole === 'staff') {
        await loadCurrentStaffUsername();
      }
      await loadCustomers();
    };
    initialize();
    
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
      
      socket.on('appointment_created', () => { loadCustomers(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('appointment_updated', () => { loadCustomers(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('appointment_deleted', () => { loadCustomers(); if (selectedCustomer) loadCustomerHistory(selectedCustomer.phone); });
      socket.on('customer_added', () => { loadCustomers(); });
      socket.on('customer_deleted', (data) => {
        loadCustomers();
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

  const loadCustomers = async () => {
    try {
      setLoading(true);
      const response = await api.get("/customers");
      const customerList = (response.data || []).map(customer => ({
        name: customer.name,
        phone: customer.phone,
        totalAppointments: customer.total_appointments || 0,
        isPending: customer.is_pending || false
      }));
      setCustomers(customerList);
    } catch (error) {
      if (error.response && error.response.status !== 401) {
        toast.error(t('customers.loadingError'));
      }
    } finally {
      setLoading(false);
    }
  };

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
      await loadCustomers();
      setDeleteDialogOpen(false); setCustomerToDelete(null);
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
      setNewCustomerData({ name: "", phone: "" });
      await loadCustomers();
    } catch (error) {
      const errorMessage = error.response?.data?.detail || t('customers.addError');
      toast.error(errorMessage);
    } finally {
      setSavingCustomer(false);
    }
  };

  // --- REHBER İŞLEMLERİ (GÜNCELLENMİŞ) ---

  const handleImportButtonClick = () => {
    setShowImportChoiceDialog(true);
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
      try {
        const permission = await Contacts.requestPermissions();
        if (permission.contacts !== 'granted') {
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

        if (mode === 'ALL') {
          await saveContactsBatch(normalizedContacts);
        } else {
          setFetchedContacts(normalizedContacts);
          setSelectedContactPhones(new Set()); // Sıfırla
          setContactSearchTerm(""); // Arama çubuğunu sıfırla
          setShowContactSelectionDialog(true);
          setImportingContacts(false);
        }

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
          }));
          await saveContactsBatch(normalized);
        } else {
          setImportingContacts(false);
        }
      } catch (e) {
        setImportingContacts(false);
      }
    }
    else {
      setShowNotSupportedDialog(true);
    }
  };

  // Seçilenleri Kaydet
  const handleSaveSelectedContacts = async () => {
    // Telefon numarasına göre filtreleyip alıyoruz
    const selectedList = fetchedContacts.filter(c => selectedContactPhones.has(c.phone));
    
    if (selectedList.length === 0) {
      toast.warning("Lütfen en az bir kişi seçin.");
      return;
    }

    setShowContactSelectionDialog(false);
    setImportingContacts(true);
    await saveContactsBatch(selectedList);
  };

  // Checkbox işaretleme mantığı (Telefon numarasına göre)
  const toggleContactSelection = (phone) => {
    const newSet = new Set(selectedContactPhones);
    if (newSet.has(phone)) {
      newSet.delete(phone);
    } else {
      newSet.add(phone);
    }
    setSelectedContactPhones(newSet);
  };

  // Arama Filtresi (İsim veya Numaraya göre)
  const filteredFetchedContacts = fetchedContacts.filter(contact => 
    contact.name.toLowerCase().includes(contactSearchTerm.toLowerCase()) || 
    contact.phone.replace(/\D/g, "").includes(contactSearchTerm)
  );

  const saveContactsBatch = async (contactList) => {
    toast.info(`${contactList.length} kişi işleniyor...`);
    let successCount = 0;

    for (const contact of contactList) {
      let cleanPhone = contact.phone.replace(/\D/g, "");
      if (cleanPhone.length === 10) cleanPhone = '90' + cleanPhone;
      else if (cleanPhone.length === 11 && cleanPhone.startsWith('0')) cleanPhone = '90' + cleanPhone.substring(1);

      if (cleanPhone.length >= 10) {
        try {
          await api.post("/customers", { name: contact.name.trim(), phone: cleanPhone });
          successCount++;
        } catch (e) { }
      }
    }

    setImportingContacts(false);
    if (successCount > 0) {
      toast.success(`${successCount} kişi eklendi!`);
      await loadCustomers();
    } else {
      toast.warning("Yeni kişi eklenmedi.");
    }
  };


  const filteredCustomers = customers.filter(customer =>
    customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    customer.phone.includes(searchTerm)
  );

  if (selectedCustomer) {
    return (
      <div className="space-y-4 pb-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => { setSelectedCustomer(null); setCustomerHistory(null); setCustomerNotes(""); }}
            className="flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-medium">{t('customers.backToCustomers')}</span>
          </button>
        </div>

        <Card className="bg-white p-6 rounded-xl shadow-sm text-center">
          <div className="flex flex-col items-center">
            <div className="w-20 h-20 bg-gray-100 text-gray-600 rounded-full flex items-center justify-center font-bold text-2xl mb-4">
              {getInitials(selectedCustomer.name)}
            </div>
            <h2 className="text-xl font-bold text-gray-900 mt-4 mb-2">{selectedCustomer.name}</h2>
            <p className="text-gray-500 mb-6">{selectedCustomer.phone}</p>
            <div className="flex gap-3 w-full max-w-xs">
              <Button onClick={() => handleCall(selectedCustomer.phone)} variant="outline" className="flex-1 border border-gray-300 text-gray-700 rounded-lg">
                <Phone className="w-4 h-4 mr-2" /> {t('customers.actions.call')}
              </Button>
              <Button onClick={() => handleWhatsApp(selectedCustomer.phone)} className="flex-1 bg-green-500 hover:bg-green-600 text-white rounded-lg">
                <MessageSquare className="w-4 h-4 mr-2" /> {t('customers.actions.whatsapp')}
              </Button>
            </div>
            {userRole === 'admin' && (
              <Button onClick={() => { setCustomerToDelete(selectedCustomer); setDeleteDialogOpen(true); }} variant="outline" className="w-full max-w-xs mt-3 border border-red-300 text-red-600 hover:bg-red-50 rounded-lg">
                <Trash2 className="w-4 h-4 mr-2" /> {t('customers.deleteButton')}
              </Button>
            )}
          </div>
        </Card>

        <Card className="bg-white p-4 rounded-xl shadow-sm mt-4">
          <h3 className="font-semibold text-gray-900 mb-3">{t('customers.historyTitle')}</h3>
          {loadingHistory ? (
            <p className="text-gray-500 text-center py-4">{t('customers.loading')}</p>
          ) : customerHistory && customerHistory.appointments.length > 0 ? (
            <div className="space-y-3">
              {customerHistory.appointments.map((apt, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div>
                    <p className="font-medium text-gray-900">
                      {format(new Date(apt.appointment_date), "d MMMM yyyy", { locale: dateLocale })}
                    </p>
                    <p className="text-sm text-gray-600">{apt.appointment_time} - {apt.service_name}</p>
                    {userRole === 'admin' && apt.staff_member_id && (!settings || settings.customer_can_choose_staff || settings.admin_provides_service) && (
                      <p className="text-xs text-gray-500 mt-1">{t('customers.staff')}: {apt.staff_member_id}</p>
                    )}
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    apt.status === t('dashboard.status.completed') || apt.status === 'Tamamlandı' ? 'bg-green-100 text-green-700' :
                    apt.status === t('dashboard.status.pending') || apt.status === 'Bekliyor' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {apt.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">{t('customers.historyEmpty')}</p>
          )}
        </Card>

        <Card className="bg-white p-4 rounded-xl shadow-sm mt-4">
          <h3 className="font-semibold text-gray-900 mb-2">{t('customers.notesTitle')}</h3>
          <div className="space-y-3">
            <Textarea value={customerNotes} onChange={(e) => setCustomerNotes(e.target.value)} placeholder={t('customers.notesPlaceholder')} rows={4} className="rounded-lg border border-gray-300" />
            <Button onClick={handleSaveNotes} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
              {t('common.save')}
            </Button>
          </div>
        </Card>
        
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('customers.deleteTitle')}</AlertDialogTitle>
              <AlertDialogDescription>
                {customerToDelete && (
                  <>
                    <strong>{customerToDelete.name}</strong> {i18n.language === 'tr' ? 'müşterisini ve tüm randevularını silmek istediğinize emin misiniz?' : 'customer and all their appointments?'}
                    <br /> <span className="text-red-600 font-semibold">{t('customers.deleteWarning')}</span>
                  </>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleting}>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteCustomer} disabled={deleting} className="bg-red-600 hover:bg-red-700">
                {deleting ? t('customers.deleting') : t('customers.actions.delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-6">
      {onNavigate && (
        <button onClick={() => onNavigate("dashboard")} className="flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors mb-2">
          <ArrowLeft className="w-5 h-5" /> <span className="text-sm font-medium">{t('customers.backToHome')}</span>
        </button>
      )}
      
      <div className="sticky top-0 z-10 bg-gray-50 pb-4 pt-2">
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input type="text" placeholder={t('customers.searchPlaceholder')} value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-10 bg-white rounded-lg border border-gray-300 shadow-sm" />
        </div>
        
        {userRole === 'admin' && (
          <div className="flex gap-2">
            <Button onClick={() => setNewCustomerDialogOpen(true)} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium">
              <Plus className="w-4 h-4 mr-2" /> {t('customers.newCustomer')}
            </Button>
            
            <Button
              onClick={handleImportButtonClick}
              disabled={importingContacts}
              variant="outline"
              className="bg-white border-gray-300 text-gray-700 hover:bg-gray-50 rounded-lg w-14 flex-shrink-0"
              title="Rehberden Kişi Ekle"
            >
              {importingContacts ? (
                <div className="animate-spin h-5 w-5 border-2 border-gray-500 border-t-transparent rounded-full" />
              ) : (
                <Import className="w-5 h-5" />
              )}
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {loading ? (
          <Card className="p-8 text-center"><p className="text-gray-500">{t('customers.loading')}</p></Card>
        ) : filteredCustomers.length === 0 ? (
          <Card className="p-8 text-center"><p className="text-gray-500">{t('customers.noResults')}</p></Card>
        ) : (
          filteredCustomers.map((customer) => (
            <Card key={customer.phone} className="p-4 mb-3 bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
              <div className="flex items-center gap-4">
                <div onClick={() => handleCustomerClick(customer)} className="w-10 h-10 bg-gray-100 text-gray-600 rounded-full flex items-center justify-center font-bold flex-shrink-0 cursor-pointer">
                  {getInitials(customer.name)}
                </div>
                <div onClick={() => handleCustomerClick(customer)} className="flex-1 min-w-0 cursor-pointer">
                  <h3 className="text-gray-900 font-semibold text-base truncate">{customer.name}</h3>
                  <p className="text-gray-500 text-sm truncate">{customer.phone}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {userRole === 'admin' && (
                    <button onClick={(e) => { e.stopPropagation(); setCustomerToDelete(customer); setDeleteDialogOpen(true); }} className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-5 h-5" />
                    </button>
                  )}
                  <ChevronRight onClick={() => handleCustomerClick(customer)} className="w-5 h-5 text-gray-400 cursor-pointer" />
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
      
      {/* Silme Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('customers.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {customerToDelete && (
                <>
                  <strong>{customerToDelete.name}</strong> {i18n.language === 'tr' ? 'müşterisini ve tüm randevularını silmek istediğinize emin misiniz?' : 'customer and all their appointments?'}
                  <br /> <span className="text-red-600 font-semibold">{t('customers.deleteWarning')}</span>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteCustomer} disabled={deleting} className="bg-red-600 hover:bg-red-700">
              {deleting ? t('customers.deleting') : t('customers.actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      
      {/* Yeni Müşteri Dialog */}
      <Dialog open={newCustomerDialogOpen} onOpenChange={setNewCustomerDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t('customers.addTitle')}</DialogTitle>
            <DialogDescription>{t('customers.addDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new-customer-name" className="text-sm font-semibold text-gray-900">{t('customers.fields.name')} *</Label>
              <Input id="new-customer-name" type="text" placeholder={t('customers.fields.name')} value={newCustomerData.name} onChange={(e) => setNewCustomerData({ ...newCustomerData, name: e.target.value })} className="rounded-lg border border-gray-300" autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-customer-phone" className="text-sm font-semibold text-gray-900">{t('customers.fields.phone')} *</Label>
              <Input id="new-customer-phone" type="tel" placeholder={i18n.language === 'en' ? '+44 XXXX XXXXXX' : '05XX XXX XX XX'} value={newCustomerData.phone} onChange={(e) => setNewCustomerData({ ...newCustomerData, phone: e.target.value })} className="rounded-lg border border-gray-300" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setNewCustomerDialogOpen(false); setNewCustomerData({ name: "", phone: "" }); }} disabled={savingCustomer}>{t('common.cancel')}</Button>
            <Button onClick={handleAddNewCustomer} disabled={savingCustomer || !newCustomerData.name.trim() || !newCustomerData.phone.trim()} className="bg-blue-600 hover:bg-blue-700 text-white">
              {savingCustomer ? t('customers.saving') : t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --- 1. SEÇİM DİALOGU (Tümünü Mü / Seçerek Mi?) --- */}
      <Dialog open={showImportChoiceDialog} onOpenChange={setShowImportChoiceDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rehberden Aktar</DialogTitle>
            <DialogDescription>
              Müşterilerinizi rehberden nasıl aktarmak istersiniz?
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-4">
            <Button 
              onClick={handleImportAll}
              className="w-full justify-start h-14 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-900" 
              variant="ghost"
            >
              <Users className="w-5 h-5 mr-3 text-blue-600" />
              <div className="flex flex-col items-start">
                <span className="font-semibold">Tümünü Aktar (Hızlı)</span>
                <span className="text-xs text-gray-500">Rehberdeki tüm kişileri tek seferde ekler.</span>
              </div>
            </Button>

            <Button 
              onClick={handleImportSelect}
              className="w-full justify-start h-14 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-900" 
              variant="ghost"
            >
              <CheckSquare className="w-5 h-5 mr-3 text-green-600" />
              <div className="flex flex-col items-start">
                <span className="font-semibold">Seçerek Aktar</span>
                <span className="text-xs text-gray-500">Listeden istediklerinizi seçip eklersiniz.</span>
              </div>
            </Button>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportChoiceDialog(false)}>İptal</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --- 2. KİŞİ SEÇİM LİSTESİ DİALOGU (ARAMALI) --- */}
      <Dialog open={showContactSelectionDialog} onOpenChange={setShowContactSelectionDialog}>
        <DialogContent className="h-[80vh] flex flex-col sm:max-w-md p-0 overflow-hidden">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle className="flex justify-between items-center">
              <span>Kişileri Seç</span>
              <span className="text-sm font-normal text-gray-500">
                {selectedContactPhones.size} kişi seçildi
              </span>
            </DialogTitle>
          </DialogHeader>
          
          {/* Arama Alanı (YENİ EKLENDİ) */}
          <div className="px-6 py-3 border-b bg-gray-50">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input 
                placeholder="İsim veya numara ile ara..." 
                value={contactSearchTerm}
                onChange={(e) => setContactSearchTerm(e.target.value)}
                className="pl-9 h-10 bg-white"
              />
            </div>
          </div>
          
          {/* Liste Alanı */}
          <div className="flex-1 overflow-y-auto px-6 py-2">
            {filteredFetchedContacts.length === 0 ? (
              <p className="text-center text-gray-500 py-4">Sonuç bulunamadı.</p>
            ) : (
              filteredFetchedContacts.map((contact, index) => {
                const isSelected = selectedContactPhones.has(contact.phone);
                return (
                  <div 
                    key={index} // Filtrelemede index güvenli değil ama sadece render için ok
                    className={`flex items-center justify-between py-3 border-b border-gray-50 cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                    onClick={() => toggleContactSelection(contact.phone)}
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      {/* Checkbox Görünümü */}
                      <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300 bg-white'}`}>
                        {isSelected && <Users className="w-3 h-3 text-white" />}
                      </div>
                      
                      <div className="flex flex-col truncate">
                        <span className="font-medium text-gray-900 truncate">{contact.name}</span>
                        <span className="text-xs text-gray-500">{contact.phone}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t bg-gray-50">
            <Button variant="outline" onClick={() => setShowContactSelectionDialog(false)} className="mr-2">
              İptal
            </Button>
            <Button onClick={handleSaveSelectedContacts} className="bg-blue-600 hover:bg-blue-700 text-white">
              Seçilenleri Ekle ({selectedContactPhones.size})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --- Desteklenmiyor Uyarısı --- */}
      <AlertDialog open={showNotSupportedDialog} onOpenChange={setShowNotSupportedDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Özellik Kullanılamıyor</AlertDialogTitle>
            <AlertDialogDescription>
              Bu tarayıcı veya cihaz "Rehberden Aktarma" özelliğini desteklemiyor.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Tamam</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  );
};

export default Customers;