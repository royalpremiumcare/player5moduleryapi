import { useState, useEffect, useMemo } from "react";
import { 
  Building2, DollarSign, Calendar, Users, Search, ArrowUpDown, ArrowUp, ArrowDown, 
  Phone, Mail, MessageSquare, Clock, CheckCircle2, MessageCircle, Trash2, Trash, 
  ArrowLeft, Package, CreditCard, X, ChevronDown, ChevronUp, UserX, Settings
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import api from "../api/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const SuperAdmin = ({ onNavigate }) => {
  const [stats, setStats] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [contactRequests, setContactRequests] = useState([]);
  const [plans, setPlans] = useState([]);
  const [activeTab, setActiveTab] = useState("organizations");
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [contactSearchTerm, setContactSearchTerm] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: 'isletme_adi', direction: 'asc' });
  const [contactSortConfig, setContactSortConfig] = useState({ key: 'created_at', direction: 'desc' });
  const [expandedOrg, setExpandedOrg] = useState(null);
  const [assignPlanModal, setAssignPlanModal] = useState({ open: false, org: null });
  const [selectedPlan, setSelectedPlan] = useState('');
  const [selectedCycle, setSelectedCycle] = useState('monthly');
  const [staffList, setStaffList] = useState([]);
  const [loadingStaff, setLoadingStaff] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsResponse, orgsResponse, contactsResponse, plansResponse] = await Promise.all([
        api.get("/superadmin/stats"),
        api.get("/superadmin/organizations"),
        api.get("/superadmin/contact-requests"),
        api.get("/superadmin/plans")
      ]);
      setStats(statsResponse.data);
      setOrganizations(orgsResponse.data.organizations || []);
      setContactRequests(contactsResponse.data.contacts || []);
      setPlans(plansResponse.data.plans || []);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error("Bu sayfaya erişim yetkiniz yok");
      } else {
        toast.error("Veriler yüklenemedi");
      }
    } finally {
      setLoading(false);
    }
  };

  const loadStaff = async (orgId) => {
    setLoadingStaff(true);
    try {
      const response = await api.get(`/superadmin/organizations/${orgId}/staff`);
      setStaffList(response.data.staff || []);
    } catch (error) {
      toast.error("Personel listesi yüklenemedi");
    } finally {
      setLoadingStaff(false);
    }
  };

  const handleExpandOrg = async (orgId) => {
    if (expandedOrg === orgId) {
      setExpandedOrg(null);
      setStaffList([]);
    } else {
      setExpandedOrg(orgId);
      await loadStaff(orgId);
    }
  };

  const handleAssignPlan = async () => {
    if (!selectedPlan || !assignPlanModal.org) return;
    
    try {
      await api.post(`/superadmin/organizations/${assignPlanModal.org.organization_id}/assign-plan`, {
        plan_id: selectedPlan,
        billing_cycle: selectedCycle
      });
      toast.success("Paket başarıyla atandı");
      setAssignPlanModal({ open: false, org: null });
      setSelectedPlan('');
      setSelectedCycle('monthly');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Paket atanamadı");
    }
  };

  const handleDeleteOrganization = async (org) => {
    if (!window.confirm(`"${org.isletme_adi}" işletmesini ve TÜM VERİLERİNİ silmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz!`)) {
      return;
    }
    
    try {
      await api.delete(`/superadmin/organizations/${org.organization_id}`);
      toast.success("İşletme silindi");
      loadData();
    } catch (error) {
      toast.error("İşletme silinemedi");
    }
  };

  const handleDeleteStaff = async (orgId, staffId, staffName) => {
    if (!window.confirm(`"${staffName}" personelini silmek istediğinize emin misiniz?`)) {
      return;
    }
    
    try {
      await api.delete(`/superadmin/organizations/${orgId}/staff/${staffId}`);
      toast.success("Personel silindi");
      loadStaff(orgId);
      loadData();
    } catch (error) {
      toast.error("Personel silinemedi");
    }
  };

  const handleStatusUpdate = async (contactId, newStatus) => {
    try {
      await api.put(`/superadmin/contact-requests/${contactId}/status`, { status: newStatus });
      setContactRequests(prev => 
        prev.map(contact => contact.id === contactId ? { ...contact, status: newStatus } : contact)
      );
      toast.success("Durum güncellendi");
    } catch (error) {
      toast.error("Durum güncellenirken hata oluştu");
    }
  };

  const handleDeleteContact = async (contactId) => {
    if (!window.confirm("Bu iletişim talebini silmek istediğinize emin misiniz?")) return;
    try {
      await api.delete(`/superadmin/contact-requests/${contactId}`);
      setContactRequests(prev => prev.filter(contact => contact.id !== contactId));
      toast.success("İletişim talebi silindi");
    } catch (error) {
      toast.error("Silme işlemi başarısız");
    }
  };

  // Filtreleme ve sıralama
  const filteredAndSortedOrgs = useMemo(() => {
    let filtered = organizations.filter(org => {
      const searchLower = searchTerm.toLowerCase();
      return (
        org.isletme_adi?.toLowerCase().includes(searchLower) ||
        org.telefon_numarasi?.includes(searchTerm) ||
        org.admin_full_name?.toLowerCase().includes(searchLower) ||
        org.admin_email?.toLowerCase().includes(searchLower)
      );
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
        }
        aVal = String(aVal || '').toLowerCase();
        bVal = String(bVal || '').toLowerCase();
        return sortConfig.direction === 'asc' ? aVal.localeCompare(bVal, 'tr') : bVal.localeCompare(aVal, 'tr');
      });
    }
    return filtered;
  }, [organizations, searchTerm, sortConfig]);

  const filteredAndSortedContacts = useMemo(() => {
    let filtered = contactRequests.filter(contact => {
      const searchLower = contactSearchTerm.toLowerCase();
      return (
        contact.name?.toLowerCase().includes(searchLower) ||
        contact.phone?.includes(contactSearchTerm) ||
        contact.email?.toLowerCase().includes(searchLower)
      );
    });

    if (contactSortConfig.key) {
      filtered.sort((a, b) => {
        let aVal = a[contactSortConfig.key];
        let bVal = b[contactSortConfig.key];
        if (contactSortConfig.key === 'created_at') {
          aVal = new Date(aVal || 0).getTime();
          bVal = new Date(bVal || 0).getTime();
        }
        if (typeof aVal === 'string') aVal = aVal.toLowerCase();
        if (typeof bVal === 'string') bVal = bVal.toLowerCase();
        return contactSortConfig.direction === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
      });
    }
    return filtered;
  }, [contactRequests, contactSearchTerm, contactSortConfig]);

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const SortIcon = ({ columnKey }) => {
    if (sortConfig.key !== columnKey) return <ArrowUpDown className="ml-1 h-3 w-3 text-gray-400" />;
    return sortConfig.direction === 'asc' 
      ? <ArrowUp className="ml-1 h-3 w-3 text-blue-600" />
      : <ArrowDown className="ml-1 h-3 w-3 text-blue-600" />;
  };

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header - Mobile Responsive */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => onNavigate && onNavigate('dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl md:text-2xl font-bold text-gray-900">Super Admin</h1>
                <p className="text-xs md:text-sm text-gray-500 hidden sm:block">Platform Yönetimi</p>
              </div>
            </div>
            <button
              onClick={loadData}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="Yenile"
            >
              <Settings className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-4 md:py-6">
        {/* Stats Cards - Mobile Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-6">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Building2 className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500">İşletme</p>
                <p className="text-xl font-bold">{stats?.toplam_isletme || 0}</p>
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Aylık Gelir</p>
                <p className="text-xl font-bold">{(stats?.toplam_gelir_bu_ay || 0).toLocaleString('tr-TR')}₺</p>
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Calendar className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Randevu</p>
                <p className="text-xl font-bold">{(stats?.toplam_randevu_bu_ay || 0).toLocaleString('tr-TR')}</p>
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <Users className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Kullanıcı</p>
                <p className="text-xl font-bold">{(stats?.toplam_aktif_kullanici || 0).toLocaleString('tr-TR')}</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
          <button
            onClick={() => setActiveTab("organizations")}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
              activeTab === "organizations"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-100"
            }`}
          >
            İşletmeler ({organizations.length})
          </button>
          <button
            onClick={() => setActiveTab("contacts")}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors relative ${
              activeTab === "contacts"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-100"
            }`}
          >
            İletişim ({contactRequests.length})
            {contactRequests.filter(c => c.status === "pending").length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {contactRequests.filter(c => c.status === "pending").length}
              </span>
            )}
          </button>
        </div>

        {/* Organizations Tab */}
        {activeTab === "organizations" && (
          <div className="space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                type="text"
                placeholder="İşletme, telefon veya admin adı ile ara..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 bg-white"
              />
            </div>

            {/* Sort Buttons - Mobile */}
            <div className="flex gap-2 overflow-x-auto pb-2">
              {[
                { key: 'isletme_adi', label: 'Ad' },
                { key: 'abonelik_paketi', label: 'Paket' },
                { key: 'days_left', label: 'Kalan Gün' },
                { key: 'toplam_odeme', label: 'Ödeme' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => handleSort(key)}
                  className={`flex items-center px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                    sortConfig.key === key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {label}
                  <SortIcon columnKey={key} />
                </button>
              ))}
            </div>

            {/* Organizations List - Card Based for Mobile */}
            <div className="space-y-3">
              {filteredAndSortedOrgs.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  {searchTerm ? "Arama sonucu bulunamadı" : "Henüz işletme kaydı yok"}
                </Card>
              ) : (
                filteredAndSortedOrgs.map((org) => (
                  <Card key={org.organization_id} className="overflow-hidden">
                    {/* Main Row */}
                    <div 
                      className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => handleExpandOrg(org.organization_id)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-gray-900 truncate">{org.isletme_adi}</h3>
                            {org.billing_cycle === 'yearly' && (
                              <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full font-medium">
                                Yıllık
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 truncate">{org.admin_full_name} • {org.admin_email}</p>
                          <p className="text-sm text-gray-500">{org.telefon_numarasi}</p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            org.abonelik_paketi === 'Premium' ? 'bg-purple-100 text-purple-700' :
                            org.abonelik_paketi === 'Business' ? 'bg-indigo-100 text-indigo-700' :
                            org.plan_id === 'tier_trial' ? 'bg-gray-100 text-gray-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {org.abonelik_paketi}
                          </span>
                          <span className={`text-xs font-medium ${
                            org.days_left !== null && org.days_left <= 3 ? 'text-red-600' :
                            org.days_left !== null && org.days_left <= 7 ? 'text-yellow-600' :
                            'text-gray-500'
                          }`}>
                            {org.abonelik_durumu}
                          </span>
                        </div>
                      </div>
                      
                      {/* Stats Row */}
                      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {org.bu_ayki_randevu_sayisi} randevu
                        </span>
                        <span className="flex items-center gap-1">
                          <Users className="w-3.5 h-3.5" />
                          {org.toplam_personel_sayisi} personel
                        </span>
                        <span className="flex items-center gap-1 font-semibold text-gray-900">
                          <CreditCard className="w-3.5 h-3.5" />
                          {org.toplam_odeme.toLocaleString('tr-TR')} ₺
                        </span>
                        {expandedOrg === org.organization_id ? (
                          <ChevronUp className="w-4 h-4 ml-auto" />
                        ) : (
                          <ChevronDown className="w-4 h-4 ml-auto" />
                        )}
                      </div>
                    </div>

                    {/* Expanded Content */}
                    {expandedOrg === org.organization_id && (
                      <div className="border-t bg-gray-50 p-4 space-y-4">
                        {/* Actions */}
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setAssignPlanModal({ open: true, org });
                              setSelectedPlan(org.plan_id);
                              setSelectedCycle(org.billing_cycle);
                            }}
                            className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                          >
                            <Package className="w-4 h-4" />
                            Paket Ata
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteOrganization(org);
                            }}
                            className="flex items-center gap-1.5 px-3 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                            İşletmeyi Sil
                          </button>
                        </div>

                        {/* Staff List */}
                        <div>
                          <h4 className="text-sm font-medium text-gray-700 mb-2">Personeller ({staffList.length})</h4>
                          {loadingStaff ? (
                            <p className="text-sm text-gray-500">Yükleniyor...</p>
                          ) : staffList.length === 0 ? (
                            <p className="text-sm text-gray-500">Personel yok</p>
                          ) : (
                            <div className="space-y-2">
                              {staffList.map((staff) => (
                                <div key={staff.id} className="flex items-center justify-between bg-white p-3 rounded-lg">
                                  <div>
                                    <p className="text-sm font-medium text-gray-900">{staff.full_name}</p>
                                    <p className="text-xs text-gray-500">{staff.username}</p>
                                  </div>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteStaff(org.organization_id, staff.id, staff.full_name);
                                    }}
                                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                  >
                                    <UserX className="w-4 h-4" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </Card>
                ))
              )}
            </div>

            <p className="text-sm text-gray-500 text-center">
              Toplam {filteredAndSortedOrgs.length} işletme
            </p>
          </div>
        )}

        {/* Contacts Tab */}
        {activeTab === "contacts" && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                type="text"
                placeholder="Ad, telefon veya e-posta ile ara..."
                value={contactSearchTerm}
                onChange={(e) => setContactSearchTerm(e.target.value)}
                className="pl-10 bg-white"
              />
            </div>

            <div className="space-y-3">
              {filteredAndSortedContacts.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  {contactSearchTerm ? "Arama sonucu bulunamadı" : "Henüz iletişim talebi yok"}
                </Card>
              ) : (
                filteredAndSortedContacts.map((contact) => (
                  <Card key={contact.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-gray-900">{contact.name}</h3>
                        <div className="flex flex-wrap gap-3 mt-1 text-sm text-gray-500">
                          <a href={`tel:${contact.phone}`} className="flex items-center gap-1 text-blue-600">
                            <Phone className="w-3.5 h-3.5" />
                            {contact.phone}
                          </a>
                          {contact.email && (
                            <a href={`mailto:${contact.email}`} className="flex items-center gap-1 text-blue-600">
                              <Mail className="w-3.5 h-3.5" />
                              {contact.email}
                            </a>
                          )}
                        </div>
                        {contact.message && (
                          <p className="mt-2 text-sm text-gray-600 bg-gray-50 p-2 rounded">{contact.message}</p>
                        )}
                        <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                          <Clock className="w-3.5 h-3.5" />
                          {contact.created_at ? new Date(contact.created_at).toLocaleString('tr-TR') : '-'}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          contact.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                          contact.status === 'contacted' ? 'bg-green-100 text-green-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {contact.status === 'pending' ? 'Beklemede' :
                           contact.status === 'contacted' ? 'Ulaşıldı' : contact.status}
                        </span>
                        <div className="flex gap-1">
                          {contact.status !== 'contacted' && (
                            <button
                              onClick={() => handleStatusUpdate(contact.id, 'contacted')}
                              className="p-1.5 bg-green-100 text-green-600 rounded hover:bg-green-200 transition-colors"
                              title="Ulaşıldı"
                            >
                              <CheckCircle2 className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteContact(contact.id)}
                            className="p-1.5 bg-red-100 text-red-600 rounded hover:bg-red-200 transition-colors"
                            title="Sil"
                          >
                            <Trash className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Assign Plan Modal */}
      {assignPlanModal.open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Paket Ata</h3>
              <button
                onClick={() => setAssignPlanModal({ open: false, org: null })}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <p className="text-sm text-gray-500 mb-4">
              <strong>{assignPlanModal.org?.isletme_adi}</strong> için paket seçin
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Paket</label>
                <select
                  value={selectedPlan}
                  onChange={(e) => setSelectedPlan(e.target.value)}
                  className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Seçin...</option>
                  {plans.map((plan) => (
                    <option key={plan.id} value={plan.id}>
                      {plan.name} - {plan.price_monthly}₺/ay
                    </option>
                  ))}
                </select>
              </div>

              {selectedPlan && selectedPlan !== 'tier_trial' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Periyot</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedCycle('monthly')}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        selectedCycle === 'monthly'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Aylık
                    </button>
                    <button
                      onClick={() => setSelectedCycle('yearly')}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        selectedCycle === 'yearly'
                          ? 'bg-green-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      Yıllık
                    </button>
                  </div>
                </div>
              )}

              <button
                onClick={handleAssignPlan}
                disabled={!selectedPlan}
                className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Paketi Ata
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SuperAdmin;
