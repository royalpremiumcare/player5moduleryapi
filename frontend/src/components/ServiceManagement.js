import { useState, useEffect, useMemo } from "react";
import { Briefcase, Edit, Trash2, Plus, ArrowLeft, GripVertical } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  DndContext,
  closestCenter,
  useSensor,
  useSensors,
  PointerSensor,
  TouchSensor,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

const SortableServiceCard = ({ service, i18n, t, onEdit, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: service.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div
        data-testid={`service-card-${service.id}`}
        className={`backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg transition-[box-shadow,background-color,opacity,transform] duration-200 ${
          isDragging ? 'opacity-80 ring-2 ring-blue-500 shadow-2xl scale-105' : 'hover:shadow-xl hover:bg-white/50'
        }`}
      >
        <div className="flex items-start justify-between gap-3 min-w-0">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <button
              type="button"
              {...attributes}
              {...listeners}
              className="p-2 -ml-2 rounded-xl text-zinc-400 hover:text-zinc-600 active:bg-white/50 touch-none transition-colors"
              aria-label={t('services.management.dragToReorder', 'Sürükleyerek sırala')}
            >
              <GripVertical className="w-5 h-5" />
            </button>

            <div className="w-11 h-11 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
              <Briefcase className="w-5 h-5 text-white" />
            </div>

            <div className="flex-1 min-w-0">
              <h3 className="text-base font-black text-zinc-900 mb-1 break-words leading-tight">{service.name}</h3>
              <div className="flex items-center gap-3 flex-wrap">
                <p className="text-lg font-black text-blue-600">{Math.round(service.price)}{i18n.language === 'tr' ? '₺' : '£'}</p>
                <p className="text-sm text-zinc-600 font-bold">{(service.duration || 30)} {t('services.management.minutes')}</p>
                {service.session_count && service.session_count > 1 && (
                  <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-bold">
                    {service.session_count} {i18n.language === 'tr' ? 'seans' : 'sessions'}
                  </span>
                )}
                {service.payment_rule && service.payment_rule !== 'on_site' && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                    service.payment_rule === 'online' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {service.payment_rule === 'online' 
                      ? (i18n.language === 'tr' ? 'Online Ödeme' : 'Online Payment')
                      : (i18n.language === 'tr' 
                          ? `Kapora ${service.deposit_amount ? Math.round(service.deposit_amount) + '₺' : '%' + (service.deposit_percentage || 30)}`
                          : `Deposit ${service.deposit_amount ? '£' + Math.round(service.deposit_amount) : (service.deposit_percentage || 30) + '%'}`)}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-2 flex-shrink-0 self-start">
            <Button
              data-testid={`edit-service-${service.id}`}
              onClick={() => onEdit(service)}
              size="sm"
              variant="outline"
              className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold shadow-sm"
            >
              <Edit className="w-4 h-4 mr-1" />
              <span className="hidden sm:inline">{t('common.edit')}</span>
            </Button>
            <Button
              data-testid={`delete-service-${service.id}`}
              onClick={() => onDelete(service)}
              size="sm"
              variant="outline"
              className="text-red-600 hover:bg-red-50 backdrop-blur-md bg-white/60 border-white/40 hover:border-red-300 rounded-xl font-bold shadow-sm"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ServiceManagement = ({ services, onRefresh, onNavigate }) => {
  const { t, i18n } = useTranslation();
  const [showDialog, setShowDialog] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState(null);
  const [showAssignReminder, setShowAssignReminder] = useState(false);
  const [lastAddedServiceName, setLastAddedServiceName] = useState("");
  const [editingService, setEditingService] = useState(null);
  const [formData, setFormData] = useState({ name: "", price: "", duration: "30", isSessionPackage: false, sessionCount: "2", paymentRule: "on_site", depositAmount: "" });
  const [loading, setLoading] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [settings, setSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [orderedServices, setOrderedServices] = useState([]);
  const [reordering, setReordering] = useState(false);

  useEffect(() => {
    setOrderedServices(Array.isArray(services) ? services : []);
  }, [services]);

  const serviceIds = useMemo(() => orderedServices.map((s) => s.id), [orderedServices]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } })
  );

  const handleEdit = (service) => {
    setEditingService(service);
    setFormData({ 
      name: service.name, 
      price: service.price.toString(),
      duration: (service.duration || 30).toString(),
      isSessionPackage: !!(service.session_count && service.session_count > 1),
      sessionCount: (service.session_count && service.session_count > 1) ? service.session_count.toString() : "2",
      paymentRule: service.payment_rule || "on_site",
      depositAmount: service.deposit_amount ? service.deposit_amount.toString() : ""
    });
    setFormErrors({});
    setShowDialog(true);
  };

  const persistOrder = async (nextServices) => {
    setReordering(true);
    try {
      await api.post('/services/reorder', { service_ids: nextServices.map(s => s.id) });
      toast.success(t('services.management.reordered', 'Sıralama güncellendi'));
      onRefresh();
    } catch (error) {
      toast.error(t('services.management.reorderFailed', 'Sıralama güncellenemedi'));
      onRefresh();
    } finally {
      setReordering(false);
    }
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    setOrderedServices((prev) => {
      const oldIndex = prev.findIndex((s) => s.id === active.id);
      const newIndex = prev.findIndex((s) => s.id === over.id);
      if (oldIndex < 0 || newIndex < 0) return prev;
      const next = arrayMove(prev, oldIndex, newIndex);
      persistOrder(next);
      return next;
    });
  };

  const handleNew = () => {
    setEditingService(null);
    setFormData({ name: "", price: "", duration: "30", isSessionPackage: false, sessionCount: "2", paymentRule: "on_site", depositAmount: "" });
    setFormErrors({});
    setShowDialog(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errors = {};
    
    if (!formData.name || !formData.price || !formData.duration) {
      if (!formData.name) errors.name = i18n.language === 'tr' ? 'Hizmet adı gereklidir.' : 'Service name is required.';
      if (!formData.price) errors.price = i18n.language === 'tr' ? 'Fiyat gereklidir.' : 'Price is required.';
      if (!formData.duration) errors.duration = i18n.language === 'tr' ? 'Süre gereklidir.' : 'Duration is required.';
      setFormErrors(errors);
      return;
    }

    const price = parseFloat(formData.price);
    if (isNaN(price) || price <= 0) {
      setFormErrors({ price: i18n.language === 'tr' ? 'Geçerli bir fiyat girin.' : 'Enter a valid price.' });
      return;
    }

    if (formData.paymentRule === 'online' && price < 300) {
      setFormErrors({ price: i18n.language === 'tr' ? 'Online ödeme için hizmet fiyatı en az 300₺ olmalıdır.' : 'Service price must be at least £5 for online payment.' });
      return;
    }
    if (formData.paymentRule === 'deposit' && price < 300) {
      setFormErrors({ price: i18n.language === 'tr' ? 'Kapora için hizmet fiyatı en az 300₺ olmalıdır.' : 'Service price must be at least £5 for deposit.' });
      return;
    }
    if (formData.paymentRule === 'deposit') {
      const dep = parseFloat(formData.depositAmount) || 0;
      if (dep < 200) {
        setFormErrors({ depositAmount: i18n.language === 'tr' ? 'Kapora tutarı en az 200₺ olmalıdır.' : 'Deposit must be at least £3.' });
        return;
      }
      if (dep > price) {
        setFormErrors({ depositAmount: i18n.language === 'tr' ? 'Kapora tutarı, hizmetin toplam fiyatını aşamaz.' : 'Deposit cannot exceed the service price.' });
        return;
      }
    }

    const duration = parseInt(formData.duration);
    if (isNaN(duration) || duration <= 0) {
      setFormErrors({ duration: i18n.language === 'tr' ? 'Geçerli bir süre girin.' : 'Enter a valid duration.' });
      return;
    }
    setFormErrors({});

    setLoading(true);
    try {
      const payload = { 
        name: formData.name, price, duration, 
        session_count: formData.isSessionPackage ? parseInt(formData.sessionCount) : null,
        payment_rule: formData.paymentRule || "on_site",
        deposit_amount: formData.paymentRule === "deposit" ? parseFloat(formData.depositAmount) || null : null
      };
      
      if (editingService) {
        await api.put(`/services/${editingService.id}`, payload);
        toast.success(t('services.management.serviceUpdated'));
      } else {
        await api.post("/services", payload);
        toast.success(t('services.management.serviceAdded'));
        // Yeni hizmet artık backend'de tüm aktif admin+staff'a otomatik atanıyor.
        // Personel Yönetimi hatırlatma dialog'una artık gerek yok; gerekirse aşağıdaki satırları aç.
        // setLastAddedServiceName(formData.name);
        // setShowAssignReminder(true);
      }
      
      setShowDialog(false);
      setFormData({ name: "", price: "", duration: "30", isSessionPackage: false, sessionCount: "2", paymentRule: "on_site", depositAmount: "" });
      onRefresh();
    } catch (error) {
      toast.error(t('services.management.operationFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (serviceId) => {
    try {
      await api.delete(`/services/${serviceId}`);
      toast.success(t('services.management.serviceDeleted'));
      setDeleteDialog(null);
      onRefresh();
    } catch (error) {
      toast.error(t('services.management.deleteFailed'));
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await api.get("/settings");
      setSettings(response.data);
    } catch (error) {
      console.error("Ayarlar yüklenemedi:", error);
    }
  };

  const handleSettingsChange = async (field, value) => {
    if (!settings) return;
    
    setSavingSettings(true);
    try {
      const updatedSettings = { ...settings, [field]: value };
      await api.put("/settings", updatedSettings);
      setSettings(updatedSettings);
      toast.success(t('services.management.settingUpdated'));
    } catch (error) {
      toast.error(t('services.management.settingUpdateFailed'));
      console.error("Settings update error:", error);
    } finally {
      setSavingSettings(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-purple-50/20 pb-20">
      {/* KART 1: Başlık ve Yeni Hizmet Ekle */}
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
                <h2 className="text-xl font-black text-zinc-900">{t('services.management.title')}</h2>
                <p className="text-sm text-zinc-600 mt-1 font-medium">{t('services.management.subtitle')}</p>
              </div>
            </div>

            <Button
              data-testid="add-service-button"
              onClick={handleNew}
              className="w-full bg-zinc-900 hover:bg-black h-12 text-base font-bold rounded-xl shadow-lg transition-all"
            >
              <Plus className="w-5 h-5 mr-2" />
              {t('services.management.newService')}
            </Button>
          </div>
        </div>
      </div>

      {/* KART: Online Randevu Ayarları */}
      <div className="px-4 pt-4 pb-4">
        <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-black text-zinc-900 mb-1">{t('services.management.onlineSettings')}</h3>
              <p className="text-sm text-zinc-600 font-medium">{t('services.management.onlineSettingsDescription')}</p>
            </div>
            
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 shadow-sm">
                <div className="flex-1">
                  <Label htmlFor="show-duration" className="text-sm font-bold text-zinc-900 cursor-pointer">
                    {t('services.management.showDuration')}
                  </Label>
                  <p className="text-xs text-zinc-600 mt-1 font-medium">{t('services.management.showDurationNote')}</p>
                </div>
                <Switch
                  id="show-duration"
                  checked={settings?.show_service_duration_on_public !== false}
                  onCheckedChange={(checked) => handleSettingsChange("show_service_duration_on_public", checked)}
                  disabled={savingSettings || !settings}
                />
              </div>

              <div className="flex items-center justify-between p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 shadow-sm">
                <div className="flex-1">
                  <Label htmlFor="show-price" className="text-sm font-bold text-zinc-900 cursor-pointer">
                    {t('services.management.showPrice')}
                  </Label>
                  <p className="text-xs text-zinc-600 mt-1 font-medium">{t('services.management.showPriceNote')}</p>
                </div>
                <Switch
                  id="show-price"
                  checked={settings?.show_service_price_on_public !== false}
                  onCheckedChange={(checked) => handleSettingsChange("show_service_price_on_public", checked)}
                  disabled={savingSettings || !settings}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KART 2: Hizmet Listesi */}
      {services.length === 0 ? (
        <div className="px-4 py-4">
          <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
            <div className="text-center py-8">
              <Briefcase className="w-12 h-12 text-zinc-300 mx-auto mb-3" />
              <h3 className="text-base font-black text-zinc-900 mb-2">{t('services.management.noServicesTitle')}</h3>
              <p className="text-sm text-zinc-600 font-medium">{t('services.management.noServicesDescription')}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="px-4 py-4 space-y-3">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={serviceIds} strategy={verticalListSortingStrategy}>
              <div className="space-y-3">
                {orderedServices.map((service) => (
                  <SortableServiceCard
                    key={service.id}
                    service={service}
                    i18n={i18n}
                    t={t}
                    onEdit={handleEdit}
                    onDelete={setDeleteDialog}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>

          {reordering && (
            <div className="text-center text-xs text-zinc-500 pt-2 font-bold animate-pulse">
              {t('common.saving', 'Kaydediliyor...')}
            </div>
          )}
        </div>
      )}

      {/* Service Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl max-h-[85vh] flex flex-col">
          <DialogHeader className="flex-shrink-0 pb-2">
            <DialogTitle className="text-xl font-black text-zinc-900">
              {editingService ? t('services.management.editTitle') : t('services.management.addTitle')}
            </DialogTitle>
            <DialogDescription className="text-zinc-600 font-medium">
              {t('services.management.dialogDescription')}
            </DialogDescription>
          </DialogHeader>
          {/* `pr-2` scroll bar için sağ tarafta nefes payı bırakır;
              input köşeleri artık scrollbar'ın altına girmez. */}
          <form onSubmit={handleSubmit} className="space-y-4 overflow-y-auto flex-1 pr-2">
            {/* Section: Temel Bilgiler */}
            <div className="flex items-center gap-3">
              <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-zinc-400">
                {i18n.language === 'tr' ? 'Temel Bilgiler' : 'Basic Info'}
              </h3>
              <div className="flex-1 h-px bg-zinc-200/70" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="service-name" className="text-sm font-bold text-zinc-700">{t('services.fields.name')}</Label>
              <Input
                id="service-name"
                data-testid="service-name-input"
                value={formData.name}
                onChange={(e) => { setFormErrors(prev => { const { name: _, ...rest } = prev; return rest; }); setFormData({ ...formData, name: e.target.value }); }}
                placeholder={t('services.management.pricePlaceholder')}
                required
                className={`backdrop-blur-md bg-white/60 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium ${formErrors.name ? 'border-red-400 border' : 'border-white/40'}`}
              />
              {formErrors.name && <p className="text-xs text-red-500 font-medium">{formErrors.name}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="service-price" className="text-sm font-bold text-zinc-700">
                {t('services.fields.price')} ({i18n.language === 'tr' ? '₺' : '£'})
              </Label>
              <Input
                id="service-price"
                data-testid="service-price-input"
                type="number"
                step="1"
                value={formData.price}
                onChange={(e) => { setFormErrors(prev => { const { price: _, ...rest } = prev; return rest; }); setFormData({ ...formData, price: e.target.value }); }}
                placeholder="0"
                required
                className={`backdrop-blur-md bg-white/60 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium ${formErrors.price ? 'border-red-400 border' : 'border-white/40'}`}
              />
              {formErrors.price 
                ? <p className="text-xs text-red-500 font-medium">{formErrors.price}</p>
                : (formData.paymentRule === 'online' || formData.paymentRule === 'deposit') && (
                  <p className="text-xs text-zinc-400 font-medium">
                    {i18n.language === 'tr' ? 'Online ödeme için minimum tutar 300₺' : 'Minimum amount for online payment £5'}
                  </p>
                )
              }
            </div>
            <div className="space-y-2">
              <Label htmlFor="service-duration" className="text-sm font-bold text-zinc-700">{t('services.fields.duration')}</Label>
              <Input
                id="service-duration"
                data-testid="service-duration-input"
                type="number"
                min="1"
                step="1"
                value={formData.duration}
                onChange={(e) => { setFormErrors(prev => { const { duration: _, ...rest } = prev; return rest; }); setFormData({ ...formData, duration: e.target.value }); }}
                placeholder="30"
                required
                className={`backdrop-blur-md bg-white/60 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium ${formErrors.duration ? 'border-red-400 border' : 'border-white/40'}`}
              />
              {formErrors.duration 
                ? <p className="text-xs text-red-500 font-medium">{formErrors.duration}</p>
                : <p className="text-xs text-zinc-500 font-medium">{t('services.management.durationNote')}</p>
              }
            </div>
            {/* Section: Paket Tipi */}
            <div className="flex items-center gap-3 pt-2">
              <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-zinc-400">
                {i18n.language === 'tr' ? 'Paket Tipi' : 'Package Type'}
              </h3>
              <div className="flex-1 h-px bg-zinc-200/70" />
            </div>
            <div className="flex items-center justify-between p-4 rounded-xl backdrop-blur-md bg-white/50 border border-white/30 shadow-sm">
              <div className="flex-1">
                <Label htmlFor="session-toggle" className="text-sm font-bold text-zinc-900 cursor-pointer">
                  {i18n.language === 'tr' ? 'Bu hizmet bir seans paketi mi?' : 'Is this a session package?'}
                </Label>
                <p className="text-xs text-zinc-600 mt-1 font-medium">
                  {i18n.language === 'tr' ? 'Açarsanız seans sayısı girmeniz gerekir' : 'If enabled, you need to enter the number of sessions'}
                </p>
              </div>
              <Switch
                id="session-toggle"
                checked={formData.isSessionPackage}
                onCheckedChange={(checked) => setFormData({ ...formData, isSessionPackage: checked })}
              />
            </div>
            {formData.isSessionPackage && (
              <div className="space-y-2 animate-in fade-in duration-200">
                <Label htmlFor="session-count" className="text-sm font-bold text-zinc-700">
                  {i18n.language === 'tr' ? 'Kaç Seans?' : 'How many sessions?'}
                </Label>
                <Input
                  id="session-count"
                  type="number"
                  min="2"
                  max="50"
                  value={formData.sessionCount}
                  onChange={(e) => setFormData({ ...formData, sessionCount: e.target.value })}
                  placeholder="7"
                  required
                  className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
                />
                <p className="text-xs text-zinc-500 font-medium">
                  {i18n.language === 'tr' ? 'Minimum 2 seans gereklidir' : 'Minimum 2 sessions required'}
                </p>
              </div>
            )}

            {/* Section: Ödeme */}
            <div className="flex items-center gap-3 pt-2">
              <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-zinc-400">
                {i18n.language === 'tr' ? 'Ödeme' : 'Payment'}
              </h3>
              <div className="flex-1 h-px bg-zinc-200/70" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-bold text-zinc-700">
                {i18n.language === 'tr' ? 'Ödeme Kuralı' : 'Payment Rule'}
              </Label>
              <select
                value={formData.paymentRule}
                onChange={(e) => {
                  const rule = e.target.value;
                  const price = parseFloat(formData.price) || 0;
                  if (rule === 'online' && price > 0 && price < 300) {
                    setFormErrors(prev => ({ ...prev, price: i18n.language === 'tr' ? 'Online ödeme için hizmet fiyatı en az 300₺ olmalıdır.' : 'Service price must be at least £5 for online payment.' }));
                    return;
                  }
                  if (rule === 'deposit' && price > 0 && price < 300) {
                    setFormErrors(prev => ({ ...prev, price: i18n.language === 'tr' ? 'Kapora için hizmet fiyatı en az 300₺ olmalıdır.' : 'Service price must be at least £5 for deposit.' }));
                    return;
                  }
                  setFormErrors(prev => { const { price: _, ...rest } = prev; return rest; });
                  setFormData({ ...formData, paymentRule: rule });
                }}
                className="w-full backdrop-blur-md bg-white/60 border border-white/40 rounded-xl h-11 px-3 text-sm font-medium text-zinc-900 focus:ring-2 focus:ring-zinc-900 focus:outline-none"
              >
                <option value="on_site">{i18n.language === 'tr' ? 'Yerinde Ödeme' : 'Pay On Site'}</option>
                <option value="online">{i18n.language === 'tr' ? 'Tamamı Online Ödeme' : 'Full Online Payment'}</option>
                <option value="deposit">{i18n.language === 'tr' ? 'Sadece Kapora' : 'Deposit Only'}</option>
              </select>
              <p className="text-xs text-zinc-500 font-medium">
                {formData.paymentRule === 'online'
                  ? (i18n.language === 'tr' ? 'Müşteri randevu alırken ödemenin tamamını online yapar.' : 'Customer pays full amount online when booking.')
                  : formData.paymentRule === 'deposit'
                    ? (i18n.language === 'tr' ? 'Müşteri randevu alırken sabit kapora öder, kalanı işletmede.' : 'Customer pays fixed deposit online, rest at venue.')
                    : (i18n.language === 'tr' ? 'Müşteri ödemeyi işletmede yapar, online ödeme alınmaz.' : 'Customer pays at the venue, no online payment.')
                }
              </p>
            </div>

            {formData.paymentRule === 'deposit' && (
              <div className="space-y-2 animate-in fade-in duration-200">
                <Label htmlFor="deposit-amount" className="text-sm font-bold text-zinc-700">
                  {i18n.language === 'tr' ? 'Kapora Tutarı (₺)' : 'Deposit Amount (£)'}
                </Label>
                <Input
                  id="deposit-amount"
                  type="number"
                  min="200"
                  max={Math.round(parseFloat(formData.price) || 0) || 9999}
                  value={formData.depositAmount}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0;
                    const price = parseFloat(formData.price) || 0;
                    if (val > price && price > 0) {
                      setFormErrors(prev => ({ ...prev, depositAmount: i18n.language === 'tr' ? 'Kapora tutarı, hizmetin toplam fiyatını aşamaz.' : 'Deposit cannot exceed the service price.' }));
                      return;
                    }
                    setFormErrors(prev => { const { depositAmount: _, ...rest } = prev; return rest; });
                    setFormData({ ...formData, depositAmount: e.target.value });
                  }}
                  placeholder={i18n.language === 'tr' ? 'Min 200₺' : 'Min £3'}
                  required
                  className={`backdrop-blur-md bg-white/60 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium ${formErrors.depositAmount ? 'border-red-400 border' : 'border-white/40'}`}
                />
                {formErrors.depositAmount
                  ? <p className="text-xs text-red-500 font-medium">{formErrors.depositAmount}</p>
                  : <p className="text-xs text-zinc-500 font-medium">
                      {i18n.language === 'tr' 
                        ? 'Min 200₺. Kalan tutar işletmede ödenir.'
                        : 'Min £3. Rest is paid at venue.'}
                    </p>
                }
              </div>
            )}

            <DialogFooter className="flex-shrink-0 border-t border-white/30 pt-4 bg-white/95 sticky bottom-0">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => setShowDialog(false)}
                className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold"
              >
                {t('common.cancel')}
              </Button>
              <Button
                data-testid="save-service-button"
                type="submit"
                disabled={loading}
                className="bg-zinc-900 hover:bg-black rounded-xl h-11 font-bold shadow-lg"
              >
                {loading ? t('settings.profile.buttons.saving') : t('common.save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/*
        Hizmet ekledikten sonra 'önce personele atayın' hatırlatması.
        Backend artık yeni hizmeti tüm aktif admin+staff'a otomatik atadığı için dialog kullanılmıyor.
        Geri açmak istersen bu bloğu yorum dışına çıkar ve yukarıdaki setLastAddedServiceName/setShowAssignReminder çağrılarını da aç.

      <Dialog open={showAssignReminder} onOpenChange={setShowAssignReminder}>
        <DialogContent className="backdrop-blur-2xl bg-white/75 border border-white/40 rounded-3xl shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-zinc-900">
              {i18n.language === 'en' ? 'Reminder' : 'Hatırlatma'}
            </DialogTitle>
            <DialogDescription className="text-zinc-700 font-semibold">
              {i18n.language === 'en'
                ? `After adding${lastAddedServiceName ? ` “${lastAddedServiceName}”` : ''}, don't forget to assign it to your staff from Staff Management.`
                : `Hizmeti${lastAddedServiceName ? ` “${lastAddedServiceName}”` : ''} ekledikten sonra, lütfen Personel Yönetimi sayfasından personelinize tanımlamayı unutmayın.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="border-t border-white/30 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowAssignReminder(false)}
              className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl h-11 font-bold"
            >
              {i18n.language === 'en' ? 'Close' : 'Kapat'}
            </Button>
            <Button
              type="button"
              onClick={() => {
                setShowAssignReminder(false);
                onNavigate && onNavigate("staff");
              }}
              className="bg-zinc-900 hover:bg-black rounded-xl h-11 font-bold shadow-lg"
            >
              {i18n.language === 'en' ? 'Go to Staff Management' : 'Personel Yönetimi’ne Git'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      */}

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
        <AlertDialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-zinc-900">{t('services.management.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-600 font-medium">
              {t('services.management.deleteDescription', { name: deleteDialog?.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="backdrop-blur-md bg-white/60 border-white/40 hover:bg-white/80 rounded-xl font-bold">
              {t('common.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-service"
              onClick={() => handleDelete(deleteDialog?.id)}
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

export default ServiceManagement;