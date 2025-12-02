import { useState, useEffect, useRef } from "react";
import { Users, UserPlus, Edit, CheckSquare, Trash2, ArrowLeft, Calendar, ShieldCheck, User } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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

const StaffManagement = ({ onNavigate, currentUser }) => {
  const [staff, setStaff] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingStaff, setEditingStaff] = useState(null);
  const [editingPaymentStaff, setEditingPaymentStaff] = useState(null);
  const [editingDaysOffStaff, setEditingDaysOffStaff] = useState(null);
  const [selectedDaysOff, setSelectedDaysOff] = useState([]);
  const [selectedServices, setSelectedServices] = useState([]);
  const [saving, setSaving] = useState(false);
  const [savingPayment, setSavingPayment] = useState(false);
  const [savingDaysOff, setSavingDaysOff] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState(null);
  const [settings, setSettings] = useState(null);
  const paymentDialogRef = useRef(null);
  
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newStaff, setNewStaff] = useState({
    username: "",
    full_name: "",
    payment_type: "salary",
    payment_amount: 0,
    role: "staff"  // "staff" veya "admin"
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const usersResponse = await api.get("/users");
      const allPersonnel = (usersResponse.data || []).filter(u => u.role === "staff" || u.role === "admin");
      setStaff(allPersonnel);
      
      const servicesResponse = await api.get("/services");
      setServices(servicesResponse.data || []);
      
      const settingsResponse = await api.get("/settings");
      setSettings(settingsResponse.data || {});
      
      setLoading(false);
    } catch (error) {
      console.error("Veri yüklenemedi:", error);
      toast.error("Veriler yüklenirken hata oluştu");
      setLoading(false);
    }
  };

  const openEditModal = (staffMember) => {
    setEditingStaff(staffMember);
    setSelectedServices(staffMember.permitted_service_ids || []);
  };

  const toggleService = (serviceId) => {
    setSelectedServices(prev => {
      if (prev.includes(serviceId)) {
        return prev.filter(id => id !== serviceId);
      } else {
        return [...prev, serviceId];
      }
    });
  };

  const handleSaveServices = async () => {
    if (!editingStaff) return;
    
    setSaving(true);
    try {
      await api.put(`/staff/${editingStaff.username}/services`, selectedServices, {
        headers: { 'Content-Type': 'application/json' }
      });
      
      toast.success("Personel hizmetleri güncellendi");
      
      setStaff(prev => prev.map(s => 
        s.username === editingStaff.username 
          ? { ...s, permitted_service_ids: selectedServices }
          : s
      ));
      
      setEditingStaff(null);
    } catch (error) {
      console.error("Kaydetme hatası:", error);
      let errorMessage = "Hizmetler kaydedilemedi";
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail
            .map(err => `${err.loc?.join('.')}: ${err.msg}`)
            .join(', ');
        } else {
          errorMessage = JSON.stringify(error.response.data.detail);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const openEditPaymentModal = (staffMember) => {
    setEditingPaymentStaff({
      ...staffMember,
      payment_type: staffMember.payment_type || "salary",
      payment_amount: staffMember.payment_amount || 0
    });
  };

  const openEditDaysOffModal = (staffMember) => {
    setEditingDaysOffStaff(staffMember);
    setSelectedDaysOff(staffMember.days_off || ["sunday"]);
  };


  const handleSaveDaysOff = async () => {
    if (!editingDaysOffStaff) return;
    
    setSavingDaysOff(true);
    try {
      const encodedUsername = encodeURIComponent(editingDaysOffStaff.username);
      await api.put(`/staff/${encodedUsername}/days-off`, {
        days_off: selectedDaysOff
      }, {
        headers: { 'Content-Type': 'application/json' }
      });
      
      toast.success("Personel tatil günleri güncellendi");
      
      // Local state'i güncelle
      setStaff(prev => prev.map(s => 
        s.username === editingDaysOffStaff.username 
          ? { 
              ...s, 
              days_off: selectedDaysOff
            }
          : s
      ));
      
      setEditingDaysOffStaff(null);
      setSelectedDaysOff([]);
    } catch (error) {
      console.error("Kaydetme hatası:", error);
      let errorMessage = "Tatil günleri kaydedilemedi";
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map(e => e.msg || e).join(", ");
        }
      }
      toast.error(errorMessage);
    } finally {
      setSavingDaysOff(false);
    }
  };

  const handleSavePayment = async () => {
    if (!editingPaymentStaff) return;
    
    // payment_amount'u number'a çevir
    let paymentAmount = 0;
    if (editingPaymentStaff.payment_amount) {
      if (typeof editingPaymentStaff.payment_amount === 'string') {
        const parsed = parseFloat(editingPaymentStaff.payment_amount);
        paymentAmount = isNaN(parsed) ? 0 : parsed;
      } else {
        paymentAmount = editingPaymentStaff.payment_amount;
      }
    }
    
    // Validation
    if (editingPaymentStaff.payment_type === "salary" && (!paymentAmount || paymentAmount <= 0)) {
      toast.error("Lütfen aylık maaş tutarını girin");
      return;
    }
    
    if (editingPaymentStaff?.payment_type === "commission" && (!paymentAmount || paymentAmount <= 0 || paymentAmount > 100)) {
      toast.error("Lütfen geçerli bir komisyon oranı girin (1-100)");
      return;
    }
    
    setSavingPayment(true);
    try {
      const encodedUsername = encodeURIComponent(editingPaymentStaff.username);
      await api.put(`/staff/${encodedUsername}/payment`, {
        payment_type: editingPaymentStaff?.payment_type,
        payment_amount: paymentAmount
      }, {
        headers: { 'Content-Type': 'application/json' }
      });
      
      toast.success("Personel ödeme ayarları güncellendi");
      
      // Local state'i güncelle
      setStaff(prev => prev.map(s => 
        s.username === editingPaymentStaff.username 
          ? { 
              ...s, 
              payment_type: editingPaymentStaff?.payment_type,
              payment_amount: paymentAmount
            }
          : s
      ));
      
      setEditingPaymentStaff(null);
    } catch (error) {
      console.error("Kaydetme hatası:", error);
      let errorMessage = "Ödeme ayarları kaydedilemedi";
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map(e => e.msg || e).join(", ");
        }
      }
      toast.error(errorMessage);
    } finally {
      setSavingPayment(false);
    }
  };

  const handleAddStaff = async () => {
    const trimmedUsername = newStaff.username?.trim();
    const trimmedFullName = newStaff.full_name?.trim();
    const isAdmin = newStaff.role === "admin";
    
    if (!trimmedUsername || !trimmedFullName) {
      toast.error("Lütfen tüm alanları doldurun");
      return;
    }
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedUsername)) {
      toast.error("Lütfen geçerli bir e-posta adresi girin");
      return;
    }

    // Admin için ödeme bilgisi validasyonu gerekmiyor
    if (!isAdmin) {
      if (newStaff.payment_type === "salary" && (!newStaff.payment_amount || newStaff.payment_amount <= 0)) {
        toast.error("Lütfen aylık maaş tutarını girin");
        return;
      }
      
      if (newStaff.payment_type === "commission" && (!newStaff.payment_amount || newStaff.payment_amount <= 0 || newStaff.payment_amount > 100)) {
        toast.error("Lütfen geçerli bir komisyon oranı girin (1-100)");
        return;
      }
    }

    setSaving(true);
    try {
      // payment_amount'u number'a çevir
      const paymentAmount = newStaff.payment_amount 
        ? (typeof newStaff.payment_amount === 'string' ? parseFloat(newStaff.payment_amount) : newStaff.payment_amount)
        : 0;
      
      const payload = {
        username: trimmedUsername,
        full_name: trimmedFullName,
        role: newStaff.role || "staff",
        payment_type: isAdmin ? null : (newStaff.payment_type || "salary"),
        payment_amount: isAdmin ? null : paymentAmount
      };
      
      console.log("Sending payload:", payload); // Debug için
      
      await api.post("/staff/add", payload);
      
      const roleText = isAdmin ? "Admin" : "Personel";
      toast.success(`${roleText} başarıyla eklendi ve davet e-postası gönderildi`);
      
      await loadData();
      
      setNewStaff({ username: "", full_name: "", payment_type: "salary", payment_amount: 0, role: "staff" });
      setShowAddDialog(false);
    } catch (error) {
      console.error("Personel ekleme hatası:", error);
      
      let errorMessage = "Personel eklenemedi";
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail
            .map(err => `${err.loc?.join('.')}: ${err.msg}`)
            .join(', ');
        } else {
          errorMessage = JSON.stringify(error.response.data.detail);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteStaff = async (staffId) => {
    try {
      await api.delete(`/staff/${staffId}`);
      toast.success("Personel silindi");
      setDeleteDialog(null);
      await loadData();
    } catch (error) {
      console.error("Silme hatası:", error);
      let errorMessage = "Personel silinemedi";
      if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : JSON.stringify(error.response.data.detail);
      }
      toast.error(errorMessage);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* KART 1: Başlık ve Yeni Personel Ekle */}
      <div className="px-4 pt-6 pb-4">
        <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
          <div className="space-y-4">
            <div className="mb-4">
              <button
                onClick={() => onNavigate && onNavigate("settings")}
                className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="text-sm font-medium">Ayarlara Dön</span>
              </button>
        <div>
                <h2 className="text-lg font-bold text-gray-900">Personel Yönetimi</h2>
                <p className="text-sm text-gray-600 mt-1">Personellerinizin verebileceği hizmetleri yönetin</p>
              </div>
        </div>
        
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
                <Button className="w-full bg-blue-600 hover:bg-blue-700 h-12 text-base font-semibold rounded-full">
              <UserPlus className="w-4 h-4 mr-2" />
              Yeni Personel Ekle
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Yeni Personel Ekle</DialogTitle>
              <DialogDescription>
                Yeni personel ekleyin. Personele şifresini belirlemesi için bir davet e-postası gönderilecektir.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="full_name">Ad Soyad *</Label>
                <Input
                  id="full_name"
                  value={newStaff.full_name}
                  onChange={(e) => setNewStaff({ ...newStaff, full_name: e.target.value })}
                  placeholder="Ahmet Yılmaz"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="username">E-posta (Kullanıcı Adı) *</Label>
                <Input
                  id="username"
                  type="email"
                  value={newStaff.username}
                  onChange={(e) => setNewStaff({ ...newStaff, username: e.target.value })}
                  placeholder="ahmet@isletme.com"
                />
                <p className="text-xs text-gray-500 mt-1">
                  ℹ️ Davet e-postası ile şifresini belirleyebilecek.
                </p>
              </div>
              
              {/* Rol Seçimi */}
              <div className="space-y-3 pt-4 border-t">
                <Label className="text-sm font-medium text-gray-700 mb-2 block">Kullanıcı Yetkisi</Label>
                <div className="bg-gray-100 p-1 rounded-lg flex">
                  <button
                    type="button"
                    onClick={() => {
                      setNewStaff({ ...newStaff, role: "staff", payment_type: "salary", payment_amount: "" });
                    }}
                    className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                      newStaff.role === "staff"
                        ? "bg-white text-blue-600 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    <User className="w-4 h-4 inline mr-1" /> Personel
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setNewStaff({ ...newStaff, role: "admin", payment_type: null, payment_amount: null });
                    }}
                    className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                      newStaff.role === "admin"
                        ? "bg-white text-purple-600 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    <ShieldCheck className="w-4 h-4 inline mr-1" /> Yönetici
                  </button>
                </div>
                <p className="text-xs text-gray-500">
                  {newStaff.role === "admin" 
                    ? "⚠️ Yönetici yetkileri: Tüm randevuları, personelleri ve ayarları yönetebilir." 
                    : "Personel sadece kendine atanan randevuları görebilir."}
                </p>
              </div>
              
              {/* Çalışma Modeli - Sadece Personel için */}
              {newStaff.role === "staff" && (
              <div className="space-y-3 pt-4 border-t">
                <Label className="text-sm font-medium text-gray-700 mb-2 block">Çalışma Modeli</Label>
                
                {/* Segmented Control */}
                <div className="bg-gray-100 p-1 rounded-lg flex">
                  <button
                    type="button"
                    onClick={() => {
                      setNewStaff({ ...newStaff, payment_type: "salary", payment_amount: "" });
                    }}
                    className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                      newStaff.payment_type === "salary"
                        ? "bg-white text-blue-600 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    Sabit Maaş
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setNewStaff({ ...newStaff, payment_type: "commission", payment_amount: "" });
                    }}
                    className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                      newStaff.payment_type === "commission"
                        ? "bg-white text-blue-600 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    Yüzde (Prim)
                  </button>
                </div>
                
                {/* Dinamik Input Alanı */}
                {newStaff.payment_type === "salary" && (
                  <div className="space-y-2">
                    <Label htmlFor="payment_amount" className="text-sm font-medium text-gray-700">
                      Aylık Maaş Tutarı
                    </Label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 font-medium">₺</span>
                      <Input
                        id="payment_amount"
                        type="number"
                        min="0"
                        step="0.01"
                        value={newStaff.payment_amount || ""}
                        onChange={(e) => {
                          const value = e.target.value;
                          setNewStaff({ ...newStaff, payment_amount: value === "" ? "" : value });
                        }}
                        placeholder="Örn: 30000"
                        className="pl-8"
                      />
                    </div>
                  </div>
                )}
                
                {newStaff.payment_type === "commission" && (
                  <div className="space-y-2">
                    <Label htmlFor="payment_amount" className="text-sm font-medium text-gray-700">
                      Hizmet Başına Komisyon Oranı
                    </Label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 font-medium">%</span>
                      <Input
                        id="payment_amount"
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={newStaff.payment_amount || ""}
                        onChange={(e) => {
                          const value = e.target.value;
                          setNewStaff({ ...newStaff, payment_amount: value === "" ? "" : value });
                        }}
                        placeholder="Örn: 50"
                        className="pl-8"
                      />
                    </div>
                    <small className="text-gray-500 text-xs block">
                      Personelin tamamladığı hizmet bedelinin yüzde kaçını alacağını giriniz.
                    </small>
                  </div>
                )}
              </div>
              )}
              
              <p className="text-sm text-gray-600">
                {newStaff.role === "admin" 
                  ? "Yönetici olarak eklenen kullanıcı tüm işletme ayarlarını yönetebilir."
                  : "Bu bilgilerle personel giriş yapabilecek. Daha sonra \"Hizmetleri Düzenle\" ile hangi hizmetleri verebileceğini atayabilirsiniz."}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setShowAddDialog(false)}
                variant="outline"
                className="flex-1"
              >
                İptal
              </Button>
              <Button
                onClick={handleAddStaff}
                disabled={saving}
                className={`flex-1 ${newStaff.role === "admin" ? "bg-purple-600 hover:bg-purple-700" : "bg-blue-600 hover:bg-blue-700"}`}
              >
                {saving ? "Ekleniyor..." : (newStaff.role === "admin" ? "Yönetici Ekle" : "Personel Ekle")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
          </div>
        </Card>
      </div>

      {/* KART 2: Personel Ayarları */}
      <div className="px-4 py-4">
        <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-gray-900 mb-1">Personel Ayarları</h3>
              <p className="text-sm text-gray-600">Müşteri randevu oluştururken personel seçebilsin mi?</p>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg border border-gray-200">
                <div className="flex-1">
                  <Label htmlFor="customer-can-choose-staff" className="text-sm font-semibold text-gray-900 cursor-pointer">
                    Müşteri Personel Seçebilsin
                  </Label>
                  <p className="text-xs text-gray-600 mt-1">
                    Müşteriler randevu oluştururken hangi personelden hizmet almak istediklerini seçebilir
                  </p>
                </div>
                <Switch
                  id="customer-can-choose-staff"
                  checked={settings?.customer_can_choose_staff || false}
                  onCheckedChange={async (checked) => {
                    try {
                      await api.put("/settings", {
                        ...settings,
                        customer_can_choose_staff: checked
                      });
                      setSettings(prev => ({ ...prev, customer_can_choose_staff: checked }));
                      toast.success("Ayar güncellendi");
                    } catch (error) {
                      toast.error("Ayar güncellenemedi");
                    }
                  }}
                />
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg border border-gray-200">
                <div className="flex-1">
                  <Label htmlFor="admin-provides-service" className="text-sm font-semibold text-gray-900 cursor-pointer">
                    İşletme Sahibi Hizmet Verir
                  </Label>
                  <p className="text-xs text-gray-600 mt-1">
                    İşletme sahibi (admin) de randevu alabilir ve hizmet verebilir
                  </p>
                </div>
                <Switch
                  id="admin-provides-service"
                  checked={settings?.admin_provides_service !== false}
                  onCheckedChange={async (checked) => {
                    try {
                      await api.put("/settings", {
                        ...settings,
                        admin_provides_service: checked
                      });
                      setSettings(prev => ({ ...prev, admin_provides_service: checked }));
                      toast.success("Ayar güncellendi");
                    } catch (error) {
                      toast.error("Ayar güncellenemedi");
                    }
                  }}
                />
              </div>

              {/* Mola Limiti Ayarları */}
              <div className="p-4 rounded-lg border border-gray-200 space-y-3">
                <div>
                  <Label className="text-sm font-semibold text-gray-900">Personel Mola Limiti</Label>
                  <p className="text-xs text-gray-600 mt-1">Personellerin günlük mola haklarını belirleyin</p>
                </div>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <Label htmlFor="break-limit-minutes" className="text-xs text-gray-600">Günlük Max Süre</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <Input
                        id="break-limit-minutes"
                        type="number"
                        min="15"
                        max="180"
                        step="15"
                        value={settings?.break_limit_minutes || 60}
                        onChange={async (e) => {
                          const value = parseInt(e.target.value) || 60;
                          try {
                            await api.put("/settings", { ...settings, break_limit_minutes: value });
                            setSettings(prev => ({ ...prev, break_limit_minutes: value }));
                          } catch (error) {
                            toast.error("Ayar güncellenemedi");
                          }
                        }}
                        className="w-20 h-9 text-center"
                      />
                      <span className="text-sm text-gray-600">dk</span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <Label htmlFor="break-limit-count" className="text-xs text-gray-600">Günlük Max Sayı</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <Input
                        id="break-limit-count"
                        type="number"
                        min="1"
                        max="5"
                        value={settings?.break_limit_count || 2}
                        onChange={async (e) => {
                          const value = parseInt(e.target.value) || 2;
                          try {
                            await api.put("/settings", { ...settings, break_limit_count: value });
                            setSettings(prev => ({ ...prev, break_limit_count: value }));
                          } catch (error) {
                            toast.error("Ayar güncellenemedi");
                          }
                        }}
                        className="w-20 h-9 text-center"
                      />
                      <span className="text-sm text-gray-600">mola</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* KART 3: Personel Listesi */}
      {staff.length === 0 ? (
        <div className="px-4 py-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <div className="text-center py-8">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-gray-900 mb-2">Henüz Personel Yok</h3>
              <p className="text-sm text-gray-600">Personel eklemek için "Yeni Personel Ekle" butonunu kullanın</p>
            </div>
        </Card>
        </div>
      ) : (
        <div className="px-4 py-4 space-y-3">
          {(() => {
            // Kurucu admin'i bul (is_founder flag'i olan veya ilk admin)
            const founderAdmin = staff.find(s => s.is_founder && s.role === 'admin') 
              || staff.find(s => s.role === 'admin');
            
            // Mevcut kullanıcı kurucu mu?
            const isCurrentUserFounder = founderAdmin?.username === currentUser?.username;
            
            return staff.map((staffMember) => {
            const assignedServices = services.filter(s => 
              staffMember.permitted_service_ids?.includes(s.id)
            );
            const isFounder = founderAdmin?.username === staffMember.username;
            const isSelf = staffMember.username === currentUser?.username;
            const isTargetAdmin = staffMember.role === 'admin';
            
            // Düzenleme butonu gösterilsin mi?
            // - Kendi hizmetlerini herkes düzenleyebilir
            // - Diğer admin'lerin hizmetlerini sadece kurucu admin düzenleyebilir
            const canEdit = isTargetAdmin ? (isCurrentUserFounder || isSelf) : true;
            
            // Silme butonu gösterilsin mi?
            // - Kendi üzerinde gösterme
            // - Kurucu admin silinemez
            // - Admin'leri sadece kurucu admin silebilir
            const canDelete = !isSelf && !isFounder && (isTargetAdmin ? isCurrentUserFounder : true);
            
            return (
              <Card key={staffMember.username} className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg ${
                      staffMember.role === 'admin' 
                        ? 'bg-gradient-to-br from-amber-500 to-orange-600' 
                        : 'bg-gradient-to-br from-blue-500 to-indigo-600'
                    }`}>
                      {staffMember.full_name?.charAt(0) || staffMember.username?.charAt(0) || "?"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold text-gray-900">
                          {staffMember.full_name || staffMember.username}
                        </h3>
                        {staffMember.role === 'admin' && (
                          <span className="px-2 py-0.5 text-xs font-semibold bg-amber-100 text-amber-800 rounded-full">
                            SAHİBİ
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600">{staffMember.username}</p>
                    </div>
                  </div>
                </div>

                  <div>
                    <p className="text-sm font-semibold text-gray-900 mb-2">Verebileceği Hizmetler:</p>
                  {assignedServices.length > 0 ? (
                    <div className="space-y-1">
                      {assignedServices.map(service => (
                          <div key={service.id} className="flex items-center gap-2 text-sm text-gray-700">
                          <CheckSquare className="w-4 h-4 text-green-500" />
                            <span>{service.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 italic">Henüz hizmet atanmamış</p>
                  )}
                </div>

                <div className="flex flex-col sm:flex-row gap-2">
                  {staffMember.role !== 'admin' && (
                    <>
                      <Dialog 
                        open={editingPaymentStaff?.username === staffMember.username}
                        onOpenChange={(open) => {
                          if (!open) {
                            setEditingPaymentStaff(null);
                          } else {
                            openEditPaymentModal(staffMember);
                          }
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button 
                            variant="outline" 
                            className="flex-1 w-full sm:w-auto"
                          >
                            <Edit className="w-4 h-4 mr-2" />
                            Ödeme Ayarları
                          </Button>
                        </DialogTrigger>
                      
                        <DialogContent 
                          className="max-w-md max-h-[90vh] overflow-hidden"
                        >
                          <DialogHeader>
                            <DialogTitle>
                              {editingPaymentStaff?.full_name || editingPaymentStaff?.username} - Ödeme Ayarları
                            </DialogTitle>
                            <DialogDescription>
                              Personelin çalışma modelini ve ödeme ayarlarını düzenleyin.
                            </DialogDescription>
                          </DialogHeader>
                          
                          <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                            {/* Çalışma Modeli */}
                            <div className="space-y-3">
                              <Label className="text-sm font-medium text-gray-700 mb-2 block">Çalışma Modeli</Label>
                              
                              {/* Segmented Control */}
                              <div className="bg-gray-100 p-1 rounded-lg flex w-full">
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (!editingPaymentStaff) return;
                                    // payment_type değiştiğinde payment_amount'u temizle (sadece commission'dan salary'ye geçerken)
                                    const newAmount = editingPaymentStaff.payment_type === "commission" ? "" : (editingPaymentStaff.payment_amount || "");
                                    setEditingPaymentStaff({ ...editingPaymentStaff, payment_type: "salary", payment_amount: newAmount });
                                  }}
                                  className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                                    editingPaymentStaff?.payment_type === "salary"
                                      ? "bg-white text-blue-600 shadow-sm"
                                      : "text-gray-500 hover:text-gray-700"
                                  }`}
                                >
                                  Sabit Maaş
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (!editingPaymentStaff) return;
                                    // payment_type değiştiğinde payment_amount'u temizle (sadece salary'den commission'a geçerken)
                                    const newAmount = editingPaymentStaff.payment_type === "salary" ? "" : (editingPaymentStaff.payment_amount || "");
                                    setEditingPaymentStaff({ ...editingPaymentStaff, payment_type: "commission", payment_amount: newAmount });
                                  }}
                                  className={`flex-1 py-2 px-4 rounded-md font-medium transition-all ${
                                    editingPaymentStaff?.payment_type === "commission"
                                      ? "bg-white text-blue-600 shadow-sm"
                                      : "text-gray-500 hover:text-gray-700"
                                  }`}
                                >
                                  Yüzde (Prim)
                                </button>
                              </div>
                              
                              {/* Dinamik Input Alanı */}
                              {editingPaymentStaff?.payment_type === "salary" && (
                                <div className="space-y-2">
                                  <Label htmlFor="edit_payment_amount" className="text-sm font-medium text-gray-700">
                                    Aylık Maaş Tutarı
                                  </Label>
                                  <div className="relative">
                                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 font-medium">₺</span>
                                    <Input
                                      id="edit_payment_amount"
                                      type="number"
                                      min="0"
                                      step="0.01"
                                      value={editingPaymentStaff?.payment_amount || ""}
                                      onChange={(e) => {
                                        if (!editingPaymentStaff) return;
                                        const value = e.target.value;
                                        setEditingPaymentStaff({ ...editingPaymentStaff, payment_amount: value === "" ? "" : value });
                                      }}
                                      placeholder="Örn: 30000"
                                      className="pl-8"
                                    />
                                  </div>
                                </div>
                              )}
                              
                              {editingPaymentStaff?.payment_type === "commission" && (
                                <div className="space-y-2">
                                  <Label htmlFor="edit_payment_amount" className="text-sm font-medium text-gray-700">
                                    Hizmet Başına Komisyon Oranı
                                  </Label>
                                  <div className="relative">
                                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 font-medium">%</span>
                                    <Input
                                      id="edit_payment_amount"
                                      type="number"
                                      min="0"
                                      max="100"
                                      step="0.1"
                                      value={editingPaymentStaff?.payment_amount || ""}
                                      onChange={(e) => {
                                        if (!editingPaymentStaff) return;
                                        const value = e.target.value;
                                        setEditingPaymentStaff({ ...editingPaymentStaff, payment_amount: value === "" ? "" : value });
                                      }}
                                      placeholder="Örn: 50"
                                      className="pl-8"
                                    />
                                  </div>
                                  <small className="text-gray-500 text-xs block">
                                    Personelin tamamladığı hizmet bedelinin yüzde kaçını alacağını giriniz.
                                  </small>
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex gap-2">
                            <Button
                              onClick={() => setEditingPaymentStaff(null)}
                              variant="outline"
                              className="flex-1"
                            >
                              İptal
                            </Button>
                            <Button
                              onClick={handleSavePayment}
                              disabled={savingPayment}
                              className="flex-1 bg-blue-600 hover:bg-blue-700"
                            >
                              {savingPayment ? "Kaydediliyor..." : "Kaydet"}
                            </Button>
                          </div>
                        </DialogContent>
                      </Dialog>

                      <Dialog
                        open={editingDaysOffStaff?.username === staffMember.username}
                        onOpenChange={(open) => {
                          if (!open) {
                            setEditingDaysOffStaff(null);
                          } else {
                            openEditDaysOffModal(staffMember);
                          }
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button 
                            variant="outline" 
                            className="flex-1 w-full sm:w-auto"
                          >
                            <Calendar className="w-4 h-4 mr-2" />
                            Tatil Günleri
                          </Button>
                        </DialogTrigger>
                        
                        <DialogContent 
                          className="max-w-md max-h-[90vh] overflow-hidden"
                        >
                            <DialogHeader>
                              <DialogTitle>
                                {editingDaysOffStaff?.full_name || editingDaysOffStaff?.username} - Tatil Günleri
                              </DialogTitle>
                              <DialogDescription>
                                Personelin çalışmadığı günleri işaretleyin. Diğer günler, 'Genel İşletme Saatleri'ne uymalıdır.
                              </DialogDescription>
                            </DialogHeader>
                            
                            <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                              <div className="bg-white p-4 rounded-lg border border-gray-200 space-y-2">
                                {[
                                  { key: 'monday', label: 'Pazartesi' },
                                  { key: 'tuesday', label: 'Salı' },
                                  { key: 'wednesday', label: 'Çarşamba' },
                                  { key: 'thursday', label: 'Perşembe' },
                                  { key: 'friday', label: 'Cuma' },
                                  { key: 'saturday', label: 'Cumartesi' },
                                  { key: 'sunday', label: 'Pazar' }
                                ].map((day) => (
                                  <div key={day.key} className="flex items-center space-x-2">
                                    <Checkbox
                                      id={`day-off-${day.key}-${staffMember.username}`}
                                      checked={selectedDaysOff.includes(day.key)}
                                      onCheckedChange={(checked) => {
                                        if (checked) {
                                          setSelectedDaysOff([...selectedDaysOff, day.key]);
                                        } else {
                                          setSelectedDaysOff(selectedDaysOff.filter(d => d !== day.key));
                                        }
                                      }}
                                    />
                                    <Label
                                      htmlFor={`day-off-${day.key}-${staffMember.username}`}
                                      className="text-sm font-medium text-gray-700 cursor-pointer"
                                    >
                                      {day.label}
                                    </Label>
                                  </div>
                                ))}
                              </div>
                            </div>
                            
                            <div className="flex gap-2">
                              <Button
                                onClick={() => {
                                  setEditingDaysOffStaff(null);
                                  setSelectedDaysOff([]);
                                }}
                                variant="outline"
                                className="flex-1"
                              >
                                İptal
                              </Button>
                              <Button
                                onClick={handleSaveDaysOff}
                                disabled={savingDaysOff}
                                className="flex-1 bg-blue-600 hover:bg-blue-700"
                              >
                                {savingDaysOff ? "Kaydediliyor..." : "Kaydet"}
                              </Button>
                            </div>
                          </DialogContent>
                      </Dialog>
                    </>
                  )}
                  
                  {canEdit && (
                  <Dialog
                    open={editingStaff?.username === staffMember.username}
                    onOpenChange={(open) => {
                      if (!open) {
                        setEditingStaff(null);
                      } else {
                        openEditModal(staffMember);
                      }
                    }}
                  >
                    <DialogTrigger asChild>
                      <Button 
                        variant="outline" 
                        className="flex-1 w-full sm:w-auto"
                      >
                        <Edit className="w-4 h-4 mr-2" />
                        Hizmetleri Düzenle
                      </Button>
                    </DialogTrigger>
                    
                    <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden">
                        <DialogHeader>
                          <DialogTitle>
                            {editingStaff?.full_name || editingStaff?.username} - Hizmet Ataması
                          </DialogTitle>
                        </DialogHeader>
                        
                        <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                          <p className="text-sm text-gray-600">
                            Bu personelin verebileceği hizmetleri seçin:
                          </p>
                          
                          {services.length === 0 ? (
                            <p className="text-center text-gray-500 py-8">
                              Henüz hizmet eklenmemiş. Önce "Hizmet Yönetimi" sayfasından hizmet ekleyin.
                            </p>
                          ) : (
                            <div className="grid grid-cols-1 gap-3 w-full">
                              {services.map((service) => {
                                const isSelected = selectedServices.includes(service.id);
                                
                                return (
                                  <div
                                    key={service.id}
                                    onClick={() => toggleService(service.id)}
                                    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                                      isSelected
                                        ? "border-blue-500 bg-blue-50"
                                        : "border-gray-200 hover:border-blue-300"
                                    }`}
                                  >
                                    <div className="flex items-center gap-3">
                                      <Checkbox
                                        checked={isSelected}
                                        onCheckedChange={() => toggleService(service.id)}
                                      />
                                      <div className="flex-1">
                                        <Label className="font-semibold text-gray-900 cursor-pointer">
                                          {service.name}
                                        </Label>
                                        <p className="text-sm text-gray-600">{service.price}₺</p>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                        
                        <div className="flex gap-2">
                          <Button
                            onClick={() => setEditingStaff(null)}
                            variant="outline"
                            className="flex-1"
                          >
                            İptal
                          </Button>
                          <Button
                            onClick={handleSaveServices}
                            disabled={saving}
                              className="flex-1 bg-blue-600 hover:bg-blue-700"
                          >
                            {saving ? "Kaydediliyor..." : "Kaydet"}
                          </Button>
                        </div>
                      </DialogContent>
                  </Dialog>
                  )}
                  
                  {canDelete && (
                    <Button
                      onClick={() => setDeleteDialog(staffMember)}
                      variant="outline"
                      size="icon"
                      className="text-red-600 hover:bg-red-50 w-full sm:w-auto"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
                </div>
              </Card>
            );
          });
          })()}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{deleteDialog?.role === 'admin' ? 'Yöneticiyi Sil' : 'Personeli Sil'}</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{deleteDialog?.full_name || deleteDialog?.username}</strong> {deleteDialog?.role === 'admin' ? 'yöneticisini' : 'personelini'} silmek istediğinizden emin misiniz?
              Bu işlem geri alınamaz.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>İptal</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleDeleteStaff(deleteDialog?.username)}
              className="bg-red-500 hover:bg-red-600"
            >
              Sil
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default StaffManagement;
