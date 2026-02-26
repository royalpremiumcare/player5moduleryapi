import { useState, useEffect, useRef } from "react";
import { Users, UserPlus, Edit, CheckSquare, Trash2, ArrowLeft, Calendar, ShieldCheck, User } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
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
  const { t, i18n } = useTranslation();
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

  const [timeBlocksStaff, setTimeBlocksStaff] = useState(null);
  const [timeBlocksDate, setTimeBlocksDate] = useState(() => {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  });
  const [timeBlocks, setTimeBlocks] = useState([]);
  const [loadingTimeBlocks, setLoadingTimeBlocks] = useState(false);
  const [newBlockStart, setNewBlockStart] = useState("12:00");
  const [newBlockEnd, setNewBlockEnd] = useState("13:00");
  const [savingTimeBlock, setSavingTimeBlock] = useState(false);
  
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newStaff, setNewStaff] = useState({
    username: "",
    full_name: "",
    payment_type: "salary",
    payment_amount: 0,
    role: "staff"
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
      toast.error(t('staff.management.loadingError'));
      setLoading(false);
    }
  };

  const loadTimeBlocks = async (staffMemberUsername, date) => {
    setLoadingTimeBlocks(true);
    try {
      const response = await api.get(`/admin/staff/${staffMemberUsername}/breaks?date=${date}`);
      setTimeBlocks(response.data?.breaks || []);
    } catch (error) {
      console.error("Zaman blokları yüklenemedi:", error);
      toast.error(t('staff.management.loadingError'));
    } finally {
      setLoadingTimeBlocks(false);
    }
  };

  const openTimeBlocksDialog = async (staffMember) => {
    setTimeBlocksStaff(staffMember);
    await loadTimeBlocks(staffMember.username, timeBlocksDate);
  };

  const handleAddTimeBlock = async () => {
    if (!timeBlocksStaff) return;
    if (!timeBlocksDate || !newBlockStart || !newBlockEnd) {
      toast.error(t('dashboard.breaks.selectTimes'));
      return;
    }
    setSavingTimeBlock(true);
    try {
      await api.post(`/admin/staff/${timeBlocksStaff.username}/breaks`, {
        date: timeBlocksDate,
        start_time: newBlockStart,
        end_time: newBlockEnd
      });
      toast.success(t('dashboard.breaks.breakAdded'));
      await loadTimeBlocks(timeBlocksStaff.username, timeBlocksDate);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('dashboard.breaks.addError'));
    } finally {
      setSavingTimeBlock(false);
    }
  };

  const handleDeleteTimeBlock = async (breakId) => {
    if (!timeBlocksStaff) return;
    try {
      await api.delete(`/admin/staff/${timeBlocksStaff.username}/breaks/${breakId}`);
      toast.success(t('dashboard.breaks.breakDeleted'));
      await loadTimeBlocks(timeBlocksStaff.username, timeBlocksDate);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('dashboard.breaks.deleteError'));
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
      
      toast.success(t('staff.management.servicesUpdated'));
      
      setStaff(prev => prev.map(s => 
        s.username === editingStaff.username 
          ? { ...s, permitted_service_ids: selectedServices }
          : s
      ));
      
      setEditingStaff(null);
    } catch (error) {
      console.error("Kaydetme hatası:", error);
      let errorMessage = t('staff.management.servicesSaveError');
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
      
      toast.success(t('staff.management.daysOffUpdated'));
      
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
      let errorMessage = t('staff.management.daysOffSaveError');
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
    
    let paymentAmount = 0;
    if (editingPaymentStaff.payment_amount) {
      if (typeof editingPaymentStaff.payment_amount === 'string') {
        const parsed = parseFloat(editingPaymentStaff.payment_amount);
        paymentAmount = isNaN(parsed) ? 0 : parsed;
      } else {
        paymentAmount = editingPaymentStaff.payment_amount;
      }
    }
    
    if (editingPaymentStaff.payment_type === "salary" && (!paymentAmount || paymentAmount <= 0)) {
      toast.error(t('staff.management.salaryRequired'));
      return;
    }
    
    if (editingPaymentStaff?.payment_type === "commission" && (!paymentAmount || paymentAmount <= 0 || paymentAmount > 100)) {
      toast.error(t('staff.management.commissionRequired'));
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
      
      toast.success(t('staff.management.paymentUpdated'));
      
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
      let errorMessage = t('staff.management.paymentSaveError');
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
      toast.error(t('staff.management.fillAllFields'));
      return;
    }
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedUsername)) {
      toast.error(t('staff.management.validEmail'));
      return;
    }

    if (!isAdmin) {
      if (newStaff.payment_type === "salary" && (!newStaff.payment_amount || newStaff.payment_amount <= 0)) {
        toast.error(t('staff.management.salaryRequired'));
        return;
      }
      
      if (newStaff.payment_type === "commission" && (!newStaff.payment_amount || newStaff.payment_amount <= 0 || newStaff.payment_amount > 100)) {
        toast.error(t('staff.management.commissionRequired'));
        return;
      }
    }

    setSaving(true);
    try {
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
      
      await api.post("/staff/add", payload);
      
      const roleText = isAdmin ? t('staff.management.adminRole') : t('staff.management.staffRole');
      toast.success(t('staff.management.staffAdded', { role: roleText }));
      
      await loadData();
      
      setNewStaff({ username: "", full_name: "", payment_type: "salary", payment_amount: 0, role: "staff" });
      setShowAddDialog(false);
    } catch (error) {
      console.error("Personel ekleme hatası:", error);
      
      let errorMessage = t('staff.management.staffAddError');
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
      toast.success(t('staff.management.staffDeleted'));
      setDeleteDialog(null);
      await loadData();
    } catch (error) {
      console.error("Silme hatası:", error);
      let errorMessage = t('staff.management.staffDeleteError');
      if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : JSON.stringify(error.response.data.detail);
      }
      toast.error(errorMessage);
    }
  };

  const handleTogglePermission = async (staffMember) => {
    try {
      const newValue = !staffMember.can_view_all_appointments;
      await api.put(`/staff/${encodeURIComponent(staffMember.username)}/toggle-permission`, {
        can_view_all_appointments: newValue
      });
      
      setStaff(prev => prev.map(s => 
        s.username === staffMember.username 
          ? { ...s, can_view_all_appointments: newValue }
          : s
      ));
      
      toast.success(newValue ? t('staff.management.permissionGranted') : t('staff.management.permissionRevoked'));
    } catch (error) {
      console.error("Yetki güncelleme hatası:", error);
      toast.error(t('staff.management.permissionUpdateError'));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 pb-20">
        <div className="px-4 pt-6 pb-4">
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 pb-20">
      {/* KART 1: Başlık ve Yeni Personel Ekle */}
      <div className="px-4 pt-6 pb-4">
        <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
          <div className="space-y-4">
            <div className="mb-4">
              <button
                onClick={() => onNavigate && onNavigate("settings")}
                className="flex items-center gap-2 text-zinc-700 hover:text-zinc-900 mb-4 transition-colors p-2 -ml-2 hover:bg-white/50 rounded-xl"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="text-sm font-bold">{t('settings.backToSettings')}</span>
              </button>
              <div>
                <h2 className="text-xl font-black text-zinc-900">{t('staff.management.title')}</h2>
                <p className="text-sm text-zinc-600 mt-1 font-medium">{t('staff.management.subtitle')}</p>
              </div>
            </div>
        
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button className="w-full bg-zinc-900 hover:bg-black h-12 text-base font-bold rounded-xl shadow-lg transition-all">
                  <UserPlus className="w-5 h-5 mr-2" />
                  {t('staff.management.newStaff')}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
                <DialogHeader className="flex-shrink-0">
                  <DialogTitle className="text-xl font-black text-zinc-900">{t('staff.management.addTitle')}</DialogTitle>
                  <DialogDescription className="text-zinc-600 font-medium">
                    {t('staff.management.addDescription')}
                  </DialogDescription>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto overflow-x-hidden py-4 px-1">
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="full_name" className="text-sm font-bold text-zinc-700">{t('staff.fields.name')} *</Label>
                        <Input
                          id="full_name"
                          value={newStaff.full_name}
                          onChange={(e) => setNewStaff({ ...newStaff, full_name: e.target.value })}
                          placeholder={t('staff.fields.name')}
                          className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="username" className="text-sm font-bold text-zinc-700">{t('settings.profile.fields.email')} *</Label>
                        <Input
                          id="username"
                          type="email"
                          value={newStaff.username}
                          onChange={(e) => setNewStaff({ ...newStaff, username: e.target.value })}
                          placeholder="ahmet@isletme.com"
                          className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-zinc-500 -mt-2 md:col-span-2 font-medium">
                      {t('staff.management.inviteEmailNote')}
                    </p>
              
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-white/30">
                      <div className="space-y-3">
                        <Label className="text-sm font-bold text-zinc-700 mb-2 block">{t('staff.management.userRole')}</Label>
                        <div className="backdrop-blur-md bg-zinc-100/60 p-1 rounded-xl flex border border-white/30 shadow-sm">
                          <button
                            type="button"
                            onClick={() => {
                              setNewStaff({ ...newStaff, role: "staff", payment_type: "salary", payment_amount: "" });
                            }}
                            className={`flex-1 py-2.5 px-3 rounded-lg font-bold transition-all text-sm ${
                              newStaff.role === "staff"
                                ? "bg-white text-blue-600 shadow-md"
                                : "text-zinc-600 hover:text-zinc-900"
                            }`}
                          >
                            <User className="w-4 h-4 inline mr-1" /> {t('staff.management.staffRole')}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setNewStaff({ ...newStaff, role: "admin", payment_type: null, payment_amount: null });
                            }}
                            className={`flex-1 py-2.5 px-3 rounded-lg font-bold transition-all text-sm ${
                              newStaff.role === "admin"
                                ? "bg-white text-purple-600 shadow-md"
                                : "text-zinc-600 hover:text-zinc-900"
                            }`}
                          >
                            <ShieldCheck className="w-4 h-4 inline mr-1" /> {t('staff.management.adminRole')}
                          </button>
                        </div>
                        <p className="text-xs text-zinc-500 font-medium">
                          {newStaff.role === "admin" 
                            ? t('staff.management.adminNote')
                            : t('staff.management.staffNote')}
                        </p>
                      </div>
                  
                      {newStaff.role === "staff" && (
                        <div className="space-y-3">
                          <Label className="text-sm font-bold text-zinc-700 mb-2 block">{t('staff.management.workModel')}</Label>
                          <div className="backdrop-blur-md bg-zinc-100/60 p-1 rounded-xl flex border border-white/30 shadow-sm">
                            <button
                              type="button"
                              onClick={() => {
                                setNewStaff({ ...newStaff, payment_type: "salary", payment_amount: "" });
                              }}
                              className={`flex-1 py-2.5 px-3 rounded-lg font-bold transition-all text-sm ${
                                newStaff.payment_type === "salary"
                                  ? "bg-white text-blue-600 shadow-md"
                                  : "text-zinc-600 hover:text-zinc-900"
                              }`}
                            >
                              {t('staff.management.fixedSalary')}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setNewStaff({ ...newStaff, payment_type: "commission", payment_amount: "" });
                              }}
                              className={`flex-1 py-2.5 px-3 rounded-lg font-bold transition-all text-sm ${
                                newStaff.payment_type === "commission"
                                  ? "bg-white text-blue-600 shadow-md"
                                  : "text-zinc-600 hover:text-zinc-900"
                              }`}
                            >
                              {t('staff.management.commission')}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                
                    {newStaff.role === "staff" && (
                      <div className="pt-4 border-t border-white/30">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {newStaff.payment_type === "salary" && (
                            <div className="space-y-2">
                              <Label htmlFor="payment_amount" className="text-sm font-bold text-zinc-700">
                                {t('staff.management.monthlySalary')}
                              </Label>
                              <div className="relative">
                                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-600 font-bold">{i18n.language === 'tr' ? '₺' : '£'}</span>
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
                                  className="pl-8 backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                                />
                              </div>
                            </div>
                          )}
                    
                          {newStaff.payment_type === "commission" && (
                            <div className="space-y-2">
                              <Label htmlFor="payment_amount" className="text-sm font-bold text-zinc-700">
                                {t('staff.management.commissionRate')}
                              </Label>
                              <div className="relative">
                                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-600 font-bold">%</span>
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
                                  className="pl-8 backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                                />
                              </div>
                              <small className="text-zinc-500 text-xs block font-medium">
                                {t('staff.management.commissionNote')}
                              </small>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                
                    <p className="text-sm text-zinc-600 pt-2 font-medium">
                      {newStaff.role === "admin" 
                        ? t('staff.management.adminDescription')
                        : t('staff.management.staffDescription')}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0 pt-4 border-t border-white/30">
                  <Button
                    onClick={() => setShowAddDialog(false)}
                    variant="outline"
                    className="flex-1 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-12 font-bold"
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    onClick={handleAddStaff}
                    disabled={saving}
                    className={`flex-1 h-12 rounded-xl font-bold shadow-lg ${newStaff.role === "admin" ? "bg-purple-600 hover:bg-purple-700" : "bg-zinc-900 hover:bg-black"}`}
                  >
                    {saving ? t('staff.management.adding') : (newStaff.role === "admin" ? t('staff.management.addAdmin') : t('staff.management.addStaff'))}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>

      {/* KART 2: Personel Ayarları */}
      <div className="px-4 py-4">
        <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-black text-zinc-900 mb-1">{t('staff.management.settingsTitle')}</h3>
              <p className="text-sm text-zinc-600 font-medium">{t('staff.management.settingsDescription')}</p>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 shadow-sm">
                <div className="flex-1">
                  <Label htmlFor="customer-can-choose-staff" className="text-sm font-bold text-zinc-900 cursor-pointer">
                    {t('staff.management.customerCanChooseStaff')}
                  </Label>
                  <p className="text-xs text-zinc-600 mt-1 font-medium">
                    {t('staff.management.customerCanChooseStaffNote')}
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
                      toast.success(t('staff.management.settingUpdated'));
                    } catch (error) {
                      toast.error(t('staff.management.settingUpdateError'));
                    }
                  }}
                />
              </div>

              <div className="flex items-center justify-between p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 shadow-sm">
                <div className="flex-1">
                  <Label htmlFor="admin-provides-service" className="text-sm font-bold text-zinc-900 cursor-pointer">
                    {t('staff.management.adminProvidesService')}
                  </Label>
                  <p className="text-xs text-zinc-600 mt-1 font-medium">
                    {t('staff.management.adminProvidesServiceNote')}
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
                      toast.success(t('staff.management.settingUpdated'));
                    } catch (error) {
                      toast.error(t('staff.management.settingUpdateError'));
                    }
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KART 3: Personel Listesi */}
      {staff.length === 0 ? (
        <div className="px-4 py-4">
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="text-center py-8">
              <Users className="w-12 h-12 text-zinc-300 mx-auto mb-3" />
              <h3 className="text-base font-black text-zinc-900 mb-2">{t('staff.management.noStaffTitle')}</h3>
              <p className="text-sm text-zinc-600 font-medium">{t('staff.management.noStaffDescription')}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="px-4 py-4 space-y-3">
          {(() => {
            const founderAdmin = staff.find(s => s.is_founder && s.role === 'admin') 
              || staff.find(s => s.role === 'admin');
            
            const isCurrentUserFounder = founderAdmin?.username === currentUser?.username;
            
            return staff.map((staffMember) => {
              const assignedServices = services.filter(s => 
                staffMember.permitted_service_ids?.includes(s.id)
              );
              const isFounder = founderAdmin?.username === staffMember.username;
              const isSelf = staffMember.username === currentUser?.username;
              const isTargetAdmin = staffMember.role === 'admin';
              
              const canEdit = isTargetAdmin ? (isCurrentUserFounder || isSelf) : true;
              const canDelete = !isSelf && !isFounder && (isTargetAdmin ? isCurrentUserFounder : true);
            
              return (
                <div key={staffMember.username} className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg hover:shadow-xl transition-all duration-300">
                  <div className="space-y-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-lg shadow-md ${
                          staffMember.role === 'admin' 
                            ? 'bg-gradient-to-br from-amber-500 to-orange-600' 
                            : 'bg-gradient-to-br from-blue-500 to-indigo-600'
                        }`}>
                          {staffMember.full_name?.charAt(0) || staffMember.username?.charAt(0) || "?"}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-base font-black text-zinc-900">
                              {staffMember.full_name || staffMember.username}
                            </h3>
                            {staffMember.role === 'admin' && (
                              <span className="px-2.5 py-0.5 text-xs font-bold bg-amber-100 text-amber-800 rounded-full shadow-sm">
                                {t('staff.management.owner')}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-zinc-600 font-medium">{staffMember.username}</p>
                        </div>
                      </div>
                    </div>

                    <div>
                      <p className="text-sm font-bold text-zinc-900 mb-2 uppercase tracking-wider">{t('staff.management.assignedServices')}</p>
                      {assignedServices.length > 0 ? (
                        <div className="space-y-1.5">
                          {assignedServices.map(service => (
                            <div key={service.id} className="flex items-center gap-2 text-sm text-zinc-700 font-medium">
                              <CheckSquare className="w-4 h-4 text-green-500" />
                              <span>{service.name}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-zinc-500 italic font-medium">{t('staff.management.noServicesAssigned')}</p>
                      )}
                    </div>

                    <div className="flex flex-col sm:flex-row gap-2">
                      {staffMember.role !== 'admin' && (
                        <>
                          {/* Payment Edit Dialog */}
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
                                className="flex-1 w-full sm:w-auto backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold shadow-sm"
                              >
                                <Edit className="w-4 h-4 mr-2" />
                                {t('staff.management.editPayment')}
                              </Button>
                            </DialogTrigger>
                      
                            <DialogContent className="max-w-md max-h-[90vh] overflow-hidden backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
                              <DialogHeader>
                                <DialogTitle className="text-xl font-black text-zinc-900">
                                  {t('staff.management.editPaymentTitle', { name: editingPaymentStaff?.full_name || editingPaymentStaff?.username })}
                                </DialogTitle>
                                <DialogDescription className="text-zinc-600 font-medium">
                                  {t('staff.management.editPaymentDescription')}
                                </DialogDescription>
                              </DialogHeader>
                          
                              <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                                <div className="space-y-3">
                                  <Label className="text-sm font-bold text-zinc-700 mb-2 block">{t('staff.management.workModel')}</Label>
                              
                                  <div className="backdrop-blur-md bg-zinc-100/60 p-1 rounded-xl flex w-full border border-white/30 shadow-sm">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        if (!editingPaymentStaff) return;
                                        const newAmount = editingPaymentStaff.payment_type === "commission" ? "" : (editingPaymentStaff.payment_amount || "");
                                        setEditingPaymentStaff({ ...editingPaymentStaff, payment_type: "salary", payment_amount: newAmount });
                                      }}
                                      className={`flex-1 py-2.5 px-4 rounded-lg font-bold transition-all ${
                                        editingPaymentStaff?.payment_type === "salary"
                                          ? "bg-white text-blue-600 shadow-md"
                                          : "text-zinc-600 hover:text-zinc-900"
                                      }`}
                                    >
                                      {t('staff.management.fixedSalary')}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        if (!editingPaymentStaff) return;
                                        const newAmount = editingPaymentStaff.payment_type === "salary" ? "" : (editingPaymentStaff.payment_amount || "");
                                        setEditingPaymentStaff({ ...editingPaymentStaff, payment_type: "commission", payment_amount: newAmount });
                                      }}
                                      className={`flex-1 py-2.5 px-4 rounded-lg font-bold transition-all ${
                                        editingPaymentStaff?.payment_type === "commission"
                                          ? "bg-white text-blue-600 shadow-md"
                                          : "text-zinc-600 hover:text-zinc-900"
                                      }`}
                                    >
                                      {t('staff.management.commission')}
                                    </button>
                                  </div>
                              
                                  {editingPaymentStaff?.payment_type === "salary" && (
                                    <div className="space-y-2">
                                      <Label htmlFor="edit_payment_amount" className="text-sm font-bold text-zinc-700">
                                        {t('staff.management.monthlySalary')}
                                      </Label>
                                      <div className="relative">
                                        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-600 font-bold">{i18n.language === 'tr' ? '₺' : '£'}</span>
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
                                          className="pl-8 backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                                        />
                                      </div>
                                    </div>
                                  )}
                              
                                  {editingPaymentStaff?.payment_type === "commission" && (
                                    <div className="space-y-2">
                                      <Label htmlFor="edit_payment_amount" className="text-sm font-bold text-zinc-700">
                                        {t('staff.management.commissionRate')}
                                      </Label>
                                      <div className="relative">
                                        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-600 font-bold">%</span>
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
                                          className="pl-8 backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                                        />
                                      </div>
                                      <small className="text-zinc-500 text-xs block font-medium">
                                        {t('staff.management.commissionNote')}
                                      </small>
                                    </div>
                                  )}
                                </div>
                              </div>
                          
                              <div className="flex gap-2 border-t border-white/30 pt-4">
                                <Button
                                  onClick={() => setEditingPaymentStaff(null)}
                                  variant="outline"
                                  className="flex-1 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-12 font-bold"
                                >
                                  {t('common.cancel')}
                                </Button>
                                <Button
                                  onClick={handleSavePayment}
                                  disabled={savingPayment}
                                  className="flex-1 bg-zinc-900 hover:bg-black rounded-xl h-12 font-bold shadow-lg"
                                >
                                  {savingPayment ? t('settings.profile.buttons.saving') : t('common.save')}
                                </Button>
                              </div>
                            </DialogContent>
                          </Dialog>

                          {/* Time Blocks Dialog */}
                          <Dialog
                            open={timeBlocksStaff?.username === staffMember.username}
                            onOpenChange={async (open) => {
                              if (!open) {
                                setTimeBlocksStaff(null);
                                setTimeBlocks([]);
                              } else {
                                await openTimeBlocksDialog(staffMember);
                              }
                            }}
                          >
                            <DialogTrigger asChild>
                              <Button
                                variant="outline"
                                className="flex-1 w-full sm:w-auto backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold shadow-sm"
                              >
                                <Calendar className="w-4 h-4 mr-2" />
                                {t('staff.management.manageTimeBlocks')}
                              </Button>
                            </DialogTrigger>

                            <DialogContent className="max-w-md max-h-[90vh] overflow-hidden backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
                              <DialogHeader>
                                <DialogTitle className="text-xl font-black text-zinc-900">
                                  {t('staff.management.blockTimeTitle')}
                                </DialogTitle>
                                <DialogDescription className="text-zinc-600 font-medium">
                                  {t('staff.management.blockTimeNote')}
                                </DialogDescription>
                              </DialogHeader>

                              <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                                <div className="space-y-2">
                                  <Label className="text-sm font-bold text-zinc-700">{t('common.date')}</Label>
                                  <Input
                                    type="date"
                                    value={timeBlocksDate}
                                    onChange={async (e) => {
                                      const next = e.target.value;
                                      setTimeBlocksDate(next);
                                      if (timeBlocksStaff?.username) {
                                        await loadTimeBlocks(timeBlocksStaff.username, next);
                                      }
                                    }}
                                    className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                                  />
                                </div>

                                <div className="p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 space-y-3 shadow-sm">
                                  <p className="text-sm font-bold text-zinc-900">{t('staff.management.blockedTimesForDate')}</p>
                                  {loadingTimeBlocks ? (
                                    <p className="text-sm text-zinc-500 font-medium">{t('common.loading')}</p>
                                  ) : timeBlocks.length === 0 ? (
                                    <p className="text-sm text-zinc-500 font-medium">{t('staff.management.noBlockedTimes')}</p>
                                  ) : (
                                    <div className="space-y-2">
                                      {timeBlocks
                                        .slice()
                                        .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''))
                                        .map((b) => (
                                          <div key={b.id} className="flex items-center justify-between p-3 backdrop-blur-sm bg-zinc-50/60 rounded-xl border border-white/30 shadow-sm">
                                            <span className="text-sm font-bold text-zinc-900">{b.start_time} - {b.end_time}</span>
                                            <Button
                                              variant="outline"
                                              size="sm"
                                              onClick={() => handleDeleteTimeBlock(b.id)}
                                              className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-lg font-bold"
                                            >
                                              {t('staff.management.unblock')}
                                            </Button>
                                          </div>
                                        ))}
                                    </div>
                                  )}
                                </div>

                                <div className="p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 space-y-3 shadow-sm">
                                  <p className="text-sm font-bold text-zinc-900">{t('staff.management.timeBlocks')}</p>
                                  <div className="grid grid-cols-2 gap-3">
                                    <div>
                                      <Label className="text-xs text-zinc-600 font-bold">{t('dashboard.breaks.startTime')}</Label>
                                      <Input
                                        type="time"
                                        value={newBlockStart}
                                        onChange={(e) => setNewBlockStart(e.target.value)}
                                        className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-10 focus:ring-2 focus:ring-zinc-900 font-medium"
                                      />
                                    </div>
                                    <div>
                                      <Label className="text-xs text-zinc-600 font-bold">{t('dashboard.breaks.endTime')}</Label>
                                      <Input
                                        type="time"
                                        value={newBlockEnd}
                                        onChange={(e) => setNewBlockEnd(e.target.value)}
                                        className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-10 focus:ring-2 focus:ring-zinc-900 font-medium"
                                      />
                                    </div>
                                  </div>
                                  <Button
                                    onClick={handleAddTimeBlock}
                                    disabled={savingTimeBlock}
                                    className="w-full bg-zinc-900 hover:bg-black rounded-xl h-11 font-bold shadow-lg"
                                  >
                                    {savingTimeBlock ? t('settings.profile.buttons.saving') : t('common.add')}
                                  </Button>
                                </div>
                              </div>

                              <div className="flex gap-2 border-t border-white/30 pt-4">
                                <Button
                                  onClick={() => setTimeBlocksStaff(null)}
                                  variant="outline"
                                  className="flex-1 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-12 font-bold"
                                >
                                  {t('common.close')}
                                </Button>
                              </div>
                            </DialogContent>
                          </Dialog>

                          {/* Days Off Dialog */}
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
                                className="flex-1 w-full sm:w-auto backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold shadow-sm"
                              >
                                <Calendar className="w-4 h-4 mr-2" />
                                {t('staff.management.editDaysOff')}
                              </Button>
                            </DialogTrigger>
                        
                            <DialogContent className="max-w-md max-h-[90vh] overflow-hidden backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
                              <DialogHeader>
                                <DialogTitle className="text-xl font-black text-zinc-900">
                                  {t('staff.management.editDaysOffTitle', { name: editingDaysOffStaff?.full_name || editingDaysOffStaff?.username })}
                                </DialogTitle>
                                <DialogDescription className="text-zinc-600 font-medium">
                                  {t('staff.management.editDaysOffDescription')}
                                </DialogDescription>
                              </DialogHeader>
                            
                              <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                                <div className="backdrop-blur-md bg-white/50 p-4 rounded-xl border border-white/30 space-y-3 shadow-sm">
                                  {[
                                    { key: 'monday', label: t('staff.management.days.monday') },
                                    { key: 'tuesday', label: t('staff.management.days.tuesday') },
                                    { key: 'wednesday', label: t('staff.management.days.wednesday') },
                                    { key: 'thursday', label: t('staff.management.days.thursday') },
                                    { key: 'friday', label: t('staff.management.days.friday') },
                                    { key: 'saturday', label: t('staff.management.days.saturday') },
                                    { key: 'sunday', label: t('staff.management.days.sunday') }
                                  ].map((day) => (
                                    <div key={day.key} className="flex items-center space-x-3">
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
                                        className="text-sm font-bold text-zinc-700 cursor-pointer"
                                      >
                                        {day.label}
                                      </Label>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            
                              <div className="flex gap-2 border-t border-white/30 pt-4">
                                <Button
                                  onClick={() => {
                                    setEditingDaysOffStaff(null);
                                    setSelectedDaysOff([]);
                                  }}
                                  variant="outline"
                                  className="flex-1 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-12 font-bold"
                                >
                                  {t('common.cancel')}
                                </Button>
                                <Button
                                  onClick={handleSaveDaysOff}
                                  disabled={savingDaysOff}
                                  className="flex-1 bg-zinc-900 hover:bg-black rounded-xl h-12 font-bold shadow-lg"
                                >
                                  {savingDaysOff ? t('settings.profile.buttons.saving') : t('common.save')}
                                </Button>
                              </div>
                            </DialogContent>
                          </Dialog>
                        </>
                      )}

                      {staffMember.role !== 'admin' && (
                        <Button
                          variant="outline"
                          onClick={() => handleTogglePermission(staffMember)}
                          className={`flex-1 w-full sm:w-auto backdrop-blur-md border-white/40 rounded-xl h-11 font-bold shadow-sm ${
                            staffMember.can_view_all_appointments
                              ? "bg-green-50 border-green-300 text-green-700 hover:bg-green-100"
                              : "bg-white/60 hover:bg-white/80"
                          }`}
                        >
                          <ShieldCheck className="w-4 h-4 mr-2" />
                          {staffMember.can_view_all_appointments ? t('staff.management.permissionActive') : t('staff.management.permissionInactive')}
                        </Button>
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
                              className="flex-1 w-full sm:w-auto backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold shadow-sm"
                            >
                              <Edit className="w-4 h-4 mr-2" />
                              {t('staff.management.editServices')}
                            </Button>
                          </DialogTrigger>
                    
                          <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
                            <DialogHeader>
                              <DialogTitle className="text-xl font-black text-zinc-900">
                                {t('staff.management.serviceAssignmentTitle', { name: editingStaff?.full_name || editingStaff?.username })}
                              </DialogTitle>
                            </DialogHeader>
                        
                            <div className="space-y-4 py-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                              <p className="text-sm text-zinc-600 font-medium">
                                {t('staff.management.selectServices')}
                              </p>
                          
                              {services.length === 0 ? (
                                <p className="text-center text-zinc-500 py-8 font-medium">
                                  {t('staff.management.noServicesYet')}
                                </p>
                              ) : (
                                <div className="grid grid-cols-1 gap-3 w-full">
                                  {services.map((service) => {
                                    const isSelected = selectedServices.includes(service.id);
                                
                                    return (
                                      <div
                                        key={service.id}
                                        onClick={() => toggleService(service.id)}
                                        className={`p-4 rounded-xl border-2 cursor-pointer transition-all backdrop-blur-md shadow-sm ${
                                          isSelected
                                            ? "border-blue-500 bg-blue-50/60"
                                            : "border-white/30 bg-white/40 hover:border-white/50 hover:bg-white/60"
                                        }`}
                                      >
                                        <div className="flex items-center gap-3">
                                          <Checkbox
                                            checked={isSelected}
                                            onCheckedChange={() => toggleService(service.id)}
                                          />
                                          <div className="flex-1">
                                            <Label className="font-bold text-zinc-900 cursor-pointer">
                                              {service.name}
                                            </Label>
                                            <p className="text-sm text-zinc-600 font-medium">{service.price}{i18n.language === 'tr' ? '₺' : '£'}</p>
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                        
                            <div className="flex gap-2 border-t border-white/30 pt-4">
                              <Button
                                onClick={() => setEditingStaff(null)}
                                variant="outline"
                                className="flex-1 backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-12 font-bold"
                              >
                                {t('common.cancel')}
                              </Button>
                              <Button
                                onClick={handleSaveServices}
                                disabled={saving}
                                className="flex-1 bg-zinc-900 hover:bg-black rounded-xl h-12 font-bold shadow-lg"
                              >
                                {saving ? t('settings.profile.buttons.saving') : t('common.save')}
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
                          className="text-red-600 hover:bg-red-50 w-full sm:w-auto backdrop-blur-md bg-white/60 border-white/40 hover:border-red-300 rounded-xl h-11 shadow-sm font-bold"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            });
          })()}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
        <AlertDialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-zinc-900">
              {deleteDialog?.role === 'admin' ? t('staff.management.deleteAdmin') : t('staff.management.deleteStaff')}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-600 font-medium">
              <strong>{deleteDialog?.full_name || deleteDialog?.username}</strong> {deleteDialog?.role === 'admin' ? t('staff.management.adminRole').toLowerCase() : t('staff.management.staffRole').toLowerCase()} {i18n.language === 'tr' ? 'silmek istediğinizden emin misiniz?' : 'Are you sure you want to delete?'} {t('customers.deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">
              {t('common.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleDeleteStaff(deleteDialog?.username)}
              className="bg-red-500 hover:bg-red-600 rounded-xl font-bold shadow-lg"
            >
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default StaffManagement;