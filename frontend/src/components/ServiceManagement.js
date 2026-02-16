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
        className={`backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg transition-all duration-300 ${
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
              <h3 className="text-base font-black text-zinc-900 mb-1 break-words leading-tight line-clamp-2">{service.name}</h3>
              <div className="flex items-center gap-3">
                <p className="text-lg font-black text-blue-600">{Math.round(service.price)}{i18n.language === 'tr' ? '₺' : '£'}</p>
                <p className="text-sm text-zinc-600 font-bold">{(service.duration || 30)} {t('services.management.minutes')}</p>
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
  const [formData, setFormData] = useState({ name: "", price: "", duration: "30" });
  const [loading, setLoading] = useState(false);
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
      duration: (service.duration || 30).toString()
    });
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
    setFormData({ name: "", price: "", duration: "30" });
    setShowDialog(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name || !formData.price || !formData.duration) {
      toast.error(t('services.management.fillAllFields'));
      return;
    }

    const price = parseFloat(formData.price);
    if (isNaN(price) || price <= 0) {
      toast.error(t('services.management.validPrice'));
      return;
    }

    const duration = parseInt(formData.duration);
    if (isNaN(duration) || duration <= 0) {
      toast.error(t('services.management.validDuration'));
      return;
    }

    setLoading(true);
    try {
      const payload = { name: formData.name, price, duration };
      
      if (editingService) {
        await api.put(`/services/${editingService.id}`, payload);
        toast.success(t('services.management.serviceUpdated'));
      } else {
        await api.post("/services", payload);
        toast.success(t('services.management.serviceAdded'));
        setLastAddedServiceName(formData.name);
        setShowAssignReminder(true);
      }
      
      setShowDialog(false);
      setFormData({ name: "", price: "", duration: "30" });
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
        <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-zinc-900">
              {editingService ? t('services.management.editTitle') : t('services.management.addTitle')}
            </DialogTitle>
            <DialogDescription className="text-zinc-600 font-medium">
              {t('services.management.dialogDescription')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="service-name" className="text-sm font-bold text-zinc-700">{t('services.fields.name')}</Label>
              <Input
                id="service-name"
                data-testid="service-name-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('services.management.pricePlaceholder')}
                required
                className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="service-price" className="text-sm font-bold text-zinc-700">
                {t('services.fields.price')} ({i18n.language === 'tr' ? '₺' : '£'})
              </Label>
              <Input
                id="service-price"
                data-testid="service-price-input"
                type="number"
                step="0.01"
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                placeholder="0.00"
                required
                className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
              />
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
                onChange={(e) => setFormData({ ...formData, duration: e.target.value })}
                placeholder="30"
                required
                className="backdrop-blur-md bg-white/60 border-white/40 rounded-xl h-11 focus:ring-2 focus:ring-zinc-900 font-medium"
              />
              <p className="text-xs text-zinc-500 font-medium">{t('services.management.durationNote')}</p>
            </div>
            <DialogFooter className="border-t border-white/30 pt-4">
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

      <Dialog open={showAssignReminder} onOpenChange={setShowAssignReminder}>
        <DialogContent className="backdrop-blur-2xl bg-white/75 border border-white/40 rounded-3xl shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-zinc-900">
              {i18n.language === 'en' ? 'Reminder' : 'Hatırlatma'}
            </DialogTitle>
            <DialogDescription className="text-zinc-700 font-semibold">
              {i18n.language === 'en'
                ? `After adding${lastAddedServiceName ? ` “${lastAddedServiceName}”` : ''}, don’t forget to assign it to your staff from Staff Management.`
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