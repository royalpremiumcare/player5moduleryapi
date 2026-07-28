import { useState, useEffect } from "react";
import { BarChart2, Building2, MessageSquare, MessageCircle, Target, Users, LogOut, Menu, X, Wallet, Shield, Mail, Bell, FileSearch } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import SAOverview from "./superadmin/SAOverview";
import SAOrganizations from "./superadmin/SAOrganizations";
import SAContacts from "./superadmin/SAContacts";
import SAWhatsApp from "./superadmin/SAWhatsApp";
import SALeads from "./superadmin/SALeads";
import SAUsers from "./superadmin/SAUsers";
import SAFinancial from "./superadmin/SAFinancial";
import SAFinancialV2 from "./superadmin/SAFinancialV2";
import SAFinancialAudit from "./superadmin/SAFinancialAudit";
import SAEmailBroadcast from "./superadmin/SAEmailBroadcast";
import SAPushBroadcast from "./superadmin/SAPushBroadcast";

const NAV_ITEMS = [
  { id: "overview",       label: "Genel Bakış",    icon: BarChart2 },
  { id: "organizations",  label: "İşletmeler",     icon: Building2 },
  { id: "contacts",       label: "İletişim",       icon: MessageSquare },
  { id: "whatsapp",       label: "WhatsApp",       icon: MessageCircle },
  { id: "leads",          label: "Lead Yönetimi",  icon: Target },
  { id: "users",          label: "Kullanıcılar",   icon: Users },
  { id: "financial",      label: "Finansal",       icon: Wallet },
  { id: "financial-v2",   label: "Finansal v2",    icon: Shield },
  { id: "financial-audit", label: "Denetim Merkezi", icon: FileSearch },
  { id: "email",          label: "Mail Gönder",    icon: Mail },
  { id: "push",           label: "Push Bildirim",  icon: Bell },
];

const SuperAdmin = ({ onNavigate }) => {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const renderContent = () => {
    switch (activeTab) {
      case "overview":      return <SAOverview />;
      case "organizations": return <SAOrganizations />;
      case "contacts":      return <SAContacts />;
      case "whatsapp":      return <SAWhatsApp />;
      case "leads":         return <SALeads />;
      case "users":         return <SAUsers />;
      case "financial":     return <SAFinancial />;
      case "financial-v2":  return <SAFinancialV2 />;
      case "financial-audit": return <SAFinancialAudit />;
      case "email":         return <SAEmailBroadcast />;
      case "push":          return <SAPushBroadcast />;
      default:              return <SAOverview />;
    }
  };

  return (
    // h-screen yerine h-full ve w-full verdik ki fixed wrapper'a tam otursun
    <div className="superadmin-panel flex h-full w-full bg-gray-50 overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-30 w-64 bg-slate-900 flex flex-col
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
      `}>
        {/* Logo & Header: Safe Area boşluğu eklendi */}
        <div 
          className="flex items-center gap-3 px-6 pb-4 border-b border-slate-700 flex-shrink-0"
          style={{ 
            paddingTop: 'calc(max(env(safe-area-inset-top, 0px), 30px) + 12px)'
          }}
        >
          <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">P</span>
          </div>
          <div>
            <p className="text-white font-bold text-sm leading-none">PLANN</p>
            <p className="text-slate-400 text-xs mt-0.5">Super Admin</p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto p-1 text-slate-400 hover:text-white lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { setActiveTab(id); setSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === id
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Logout: Alt kısımdaki Home Indicator (çizgi) için boşluk bırakıldı */}
        <div 
          className="px-3 pt-4 border-t border-slate-700"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)' }}
        >
          <button
            onClick={() => { logout(); }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Çıkış Yap
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar: Safe Area boşluğu eklendi */}
        <header 
          className="bg-white border-b border-gray-200 flex items-center gap-4 px-4 pb-3 flex-shrink-0"
          style={{ 
            paddingTop: 'calc(max(env(safe-area-inset-top, 0px), 30px) + 10px)'
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 lg:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-semibold text-gray-900 truncate">
            {NAV_ITEMS.find(n => n.id === activeTab)?.label || "Genel Bakış"}
          </h1>
        </header>

        {/* View content: Alt kısımdaki Home Indicator (çizgi) için boşluk bırakıldı */}
        <main 
          className="flex-1 overflow-y-auto"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)' }}
        >
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default SuperAdmin;