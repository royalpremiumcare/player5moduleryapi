import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { format, addDays } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import io from "socket.io-client";
import {
  Calendar, Clock, Phone, Edit, Trash2, Check, X,
  MoreVertical, User, LayoutDashboard, Sun, Moon, FileText, Coffee, TrendingUp, CalendarDays, Sparkles
} from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

// --- TUR REHBERİ IMPORT ---
import TourGuide from "../components/TourGuide"; 
// --------------------------

// --- SEANS PLANLAYICI ---
import SessionPlannerDialog from "./SessionPlannerDialog";

// --- WHATSAPP ICON ---
const WhatsAppIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91C2.13 13.66 2.59 15.36 3.45 16.86L2.05 22L7.3 20.62C8.75 21.41 10.38 21.83 12.04 21.83C17.5 21.83 21.95 17.38 21.95 11.92C21.95 9.27 20.92 6.78 19.05 4.91C17.18 3.03 14.69 2 12.04 2ZM12.05 20.16C10.56 20.16 9.11 19.76 7.83 19L7.51 18.81L4.4 19.62L5.23 16.58L5.02 16.25C4.21 14.96 3.79 13.45 3.8 11.91C3.8 7.37 7.5 3.67 12.05 3.67C14.25 3.67 16.31 4.53 17.87 6.09C19.42 7.65 20.28 9.72 20.28 11.92C20.28 16.46 16.58 20.16 12.05 20.16ZM16.61 14.39C16.36 14.27 15.14 13.67 14.91 13.59C14.68 13.5 14.51 13.46 14.34 13.71C14.18 13.96 13.71 14.5 13.54 14.71C13.38 14.92 13.21 14.96 12.96 14.83C12.71 14.71 11.9 14.44 10.94 13.59C10.19 12.92 9.68 12.1 9.43 11.67C9.18 11.42 9.41 11.19 9.53 11.07C9.64 10.96 9.77 10.8 9.89 10.65C10.01 10.5 10.06 10.39 10.14 10.23C10.22 10.06 10.18 9.92 10.12 9.8C10.06 9.67 9.63 8.63 9.46 8.21C9.28 7.79 9.11 7.85 8.96 7.85C8.81 7.85 8.64 7.84 8.46 7.84C8.28 7.84 7.99 7.91 7.74 8.18C7.49 8.45 6.79 9.11 6.79 10.44C6.79 11.77 7.76 13.06 7.9 13.25C8.04 13.44 9.82 16.19 12.55 17.36C13.2 17.64 13.71 17.81 14.11 17.93C14.76 18.14 15.36 18.11 15.83 18.04C16.36 17.96 17.45 17.38 17.68 16.73C17.91 16.08 17.91 15.52 17.84 15.39C17.78 15.27 17.61 15.19 16.36 14.57L16.61 14.39Z" />
  </svg>
);

const Dashboard = ({ appointments, stats, userRole, onEditAppointment, onNewAppointment, onRefresh, onNavigate, onOpenChat }) => {
  const { token, canViewAll } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  // State
  const [deleteDialog, setDeleteDialog] = useState(null);
  const [settings, setSettings] = useState(null);
  const [staffMembers, setStaffMembers] = useState([]);
  const [currentStaffUsername, setCurrentStaffUsername] = useState(null);
  const [currentUserName, setCurrentUserName] = useState("");
  const [personnelStats, setPersonnelStats] = useState(null);
  const [staffFilter, setStaffFilter] = useState("all");
  const socketRef = useRef(null);
  const [expandedNoteId, setExpandedNoteId] = useState(null);
  const [upcomingVisibleCount, setUpcomingVisibleCount] = useState(10);
  // Session Planner States
  const [showSessionPlanner, setShowSessionPlanner] = useState(false);
  const [sessionPlannerAppointment, setSessionPlannerAppointment] = useState(null);

  // Break States
  const [todayBreaks, setTodayBreaks] = useState([]);
  const [showBreakDialog, setShowBreakDialog] = useState(false);
  const [newBreakStart, setNewBreakStart] = useState("12:00");
  const [newBreakEnd, setNewBreakEnd] = useState("12:30");
  const [addingBreak, setAddingBreak] = useState(false);

  // --- TOUR GUIDE STATE ---
  const [runTour, setRunTour] = useState(false);

  const dashboardTourStorageKey = useMemo(() => {
    if (!token) return null;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const username = payload.sub || payload.username || 'unknown';
      const role = payload.role || userRole || 'unknown';
      return `dashboard_tour_completed:${role}:${username}`;
    } catch (e) {
      return null;
    }
  }, [token, userRole]);

  const today = format(new Date(), "yyyy-MM-dd");
  const tomorrow = format(addDays(new Date(), 1), "yyyy-MM-dd");

  // --- HELPERS ---
  const calculateEndTime = (startTime, duration) => {
    if (!startTime || !duration) return null;
    try {
      const [hours, minutes] = startTime.split(':').map(Number);
      const totalMinutes = hours * 60 + minutes + parseInt(duration, 10);
      const endHours = Math.floor(totalMinutes / 60);
      const endMinutes = totalMinutes % 60;
      return `${String(endHours).padStart(2, '0')}:${String(endMinutes).padStart(2, '0')}`;
    } catch (e) { return null; }
  };

  const toggleNote = (id) => setExpandedNoteId(prev => prev === id ? null : id);

  // Dinamik Selamlama + Emoji
  const getTimeBasedGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return { text: t('dashboard.greetings.morning'), emoji: "☀️" };
    if (hour >= 12 && hour < 18) return { text: t('dashboard.greetings.noon'), emoji: "🌤️" };
    if (hour >= 18 && hour < 22) return { text: t('dashboard.greetings.evening'), emoji: "🌙" };
    return { text: t('dashboard.greetings.night'), emoji: "✨" };
  };

  // --- LOADERS ---
  const loadPersonnelStats = useCallback(async () => {
    try { const res = await api.get("/stats/personnel"); setPersonnelStats(res.data); } catch (e) { console.error(e); }
  }, []);

  const loadSettings = async () => {
    try { const res = await api.get("/settings"); setSettings(res.data); } catch (e) { console.error(e); }
  };

  const loadTodayBreaks = async () => {
    try { const res = await api.get(`/staff/breaks?date=${today}`); setTodayBreaks(res.data?.breaks || []); } catch (e) { console.error(e); }
  };

  const loadStaffMembers = async () => {
    if (userRole !== 'admin' && !canViewAll) return;
    try {
      const res = await api.get("/users");
      let staff = (res.data || []).filter(u => u.role === 'staff');
      if (settings?.admin_provides_service !== false) {
        const admin = (res.data || []).find(u => u.role === 'admin');
        if (admin) staff = [...staff, admin];
      }
      setStaffMembers(staff);
    } catch (e) { console.error(e); }
  };

  const loadCurrentStaffUsername = async () => {
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const username = payload.sub || payload.username;
        const fullName = payload.full_name || payload.name;
        setCurrentStaffUsername(username);
        setCurrentUserName(fullName || username || t('dashboard.userFallback'));
      } catch (e) { console.error(e); }
    }
  };

  // --- EFFECTS ---
  useEffect(() => {
    loadSettings();
    loadTodayBreaks();
    loadCurrentStaffUsername();
    if (userRole === 'staff' && !canViewAll) {
      loadPersonnelStats();
    }
    
    // --- TUR KONTROLÜ (LOCAL STORAGE) ---
    if (dashboardTourStorageKey && !localStorage.getItem(dashboardTourStorageKey)) {
      // Sayfa tam yüklensin diye azıcık beklet
      setTimeout(() => setRunTour(true), 1000);
    }
  }, [userRole, loadPersonnelStats, dashboardTourStorageKey]);

  useEffect(() => { if (settings !== null) loadStaffMembers(); }, [settings, userRole]);
  useEffect(() => { if (userRole === 'staff' && !canViewAll) loadPersonnelStats(); }, [appointments.length, userRole, canViewAll, loadPersonnelStats]);

  useEffect(() => {
    if (!socketRef.current && token) {
      const socketUrl = process.env.REACT_APP_BACKEND_URL || window.location.origin;
      const socket = io(socketUrl, { path: '/api/socket.io', transports: ['websocket', 'polling'], auth: { token: token } });
      socketRef.current = socket;
      socket.on('connect', () => { try { const p = JSON.parse(atob(token.split('.')[1])); if (p.org_id) socket.emit('join_organization', { organization_id: p.org_id }); } catch (e) {} });
      socket.on('appointment_created', () => { if (onRefresh) onRefresh(); if (userRole === 'staff' && !canViewAll) loadPersonnelStats(); });
      socket.on('appointment_updated', () => { if (onRefresh) onRefresh(); if (userRole === 'staff' && !canViewAll) loadPersonnelStats(); });
      socket.on('appointment_deleted', () => { if (onRefresh) onRefresh(); if (userRole === 'staff' && !canViewAll) loadPersonnelStats(); });
    }
    return () => { if (socketRef.current) { socketRef.current.disconnect(); socketRef.current = null; } };
  }, [token, onRefresh, userRole, loadPersonnelStats]);

  // --- HANDLERS ---
  const handleStatusChange = async (id, status) => { try { await api.put(`/appointments/${id}`, { status }); toast.success(t('dashboard.toast.statusUpdated')); onRefresh(); } catch (e) { toast.error(t('dashboard.toast.statusError')); } };
  const handleDelete = async (id) => { try { await api.delete(`/appointments/${id}`); toast.success(t('dashboard.toast.appointmentDeleted')); setDeleteDialog(null); onRefresh(); } catch (e) { toast.error(t('dashboard.toast.deleteError')); } };
  const handleAddBreak = async () => { if (!newBreakStart || !newBreakEnd) return; setAddingBreak(true); try { await api.post("/staff/breaks", { date: today, start_time: newBreakStart, end_time: newBreakEnd }); setShowBreakDialog(false); loadTodayBreaks(); } catch (e) { toast.error(e.response?.data?.detail); } finally { setAddingBreak(false); } };
  const handleDeleteBreak = async (id) => { try { await api.delete(`/staff/breaks/${id}`); toast.success(t('dashboard.breaks.breakDeleted')); loadTodayBreaks(); } catch (e) { toast.error(t('dashboard.breaks.deleteError')); } };
  const handleCall = (phone) => window.location.href = `tel:${phone}`;
  const handleWhatsApp = (phone) => { let clean = phone.replace(/\D/g, ""); if (clean.startsWith("0")) clean = clean.substring(1); if (!clean.startsWith("90")) clean = "90" + clean; window.open(`https://wa.me/${clean}`, "_blank"); };

  // --- TURU BİTİRME HANDLER'I ---
  const handleTourFinish = () => {
    if (dashboardTourStorageKey) {
      localStorage.setItem(dashboardTourStorageKey, 'true');
    }
    setRunTour(false);
  };

  // --- TUR ADIMLARI TANIMLAMASI ---
  const tourSteps = [
    {
      target: 'body',
      content: t('tour.welcome', { name: currentUserName ? `, ${currentUserName}` : '' }),
      placement: 'center',
      disableBeacon: true,
    },
    {
      target: '.tour-greeting',
      content: t('tour.greeting'),
    },
    {
      target: '.tour-stats',
      content: t('tour.stats'),
    },
    {
      target: '.tour-new-appointment',
      content: t('tour.newAppointment'),
    },
    ...(userRole === 'admin' ? [{
      target: '.tour-settings',
      content: t('tour.settings'),
    }] : []),
    ...(userRole === 'staff' ? [{
      target: '.tour-breaks',
      content: t('tour.breaks'),
    }] : []),
    {
      target: '.tour-today-flow',
      content: t('tour.todayFlow'),
    },
    {
      target: '.tour-upcoming',
      content: t('tour.upcoming')
    }
  ];

  // --- DATA FILTERING ---
  const todayAppointments = appointments.filter(apt => {
    const aptDate = apt.appointment_date || apt.date;
    if (!aptDate || aptDate !== today) return false;
    if (userRole === 'staff' && !canViewAll && currentStaffUsername && apt.staff_member_id !== currentStaffUsername) return false;
    return true;
  });

  const filteredToday = todayAppointments.filter(apt => staffFilter === "all" || apt.staff_member_id === staffFilter)
    .sort((a, b) => a.appointment_time.localeCompare(b.appointment_time));

  const morningAppointments = filteredToday.filter(apt => apt.appointment_time < "12:00");
  const afternoonAppointments = filteredToday.filter(apt => apt.appointment_time >= "12:00");

  const shouldSplit = morningAppointments.length > 0 && afternoonAppointments.length > 0;

  const filteredTomorrow = appointments.filter(apt => {
    const aptDate = apt.appointment_date || apt.date;
    if (!aptDate || aptDate !== tomorrow) return false;
    if (userRole === 'staff' && !canViewAll && currentStaffUsername && apt.staff_member_id !== currentStaffUsername) return false;
    return true;
  });
  const upcoming = appointments.filter(apt => {
    const aptDate = apt.appointment_date || apt.date;
    if (!aptDate || aptDate <= tomorrow) return false;
    if (userRole === 'staff' && !canViewAll && currentStaffUsername && apt.staff_member_id !== currentStaffUsername) return false;
    return true;
  }).filter(apt => staffFilter === "all" || apt.staff_member_id === staffFilter).sort((a, b) => (a.appointment_date || a.date).localeCompare(b.appointment_date || b.date));

  const getStaffName = (id) => { const staff = staffMembers.find(s => s.username === id); return staff?.full_name || staff?.username; };

  const displayCount = (userRole === 'admin' || canViewAll) ? stats?.today_appointments || 0 : todayAppointments.length;
  const displayRevenue = (userRole === 'admin' || canViewAll)
    ? stats?.bugunku_toplam_hizmet_tutari || 0
    : personnelStats?.total_revenue_generated || 0;

  const greeting = getTimeBasedGreeting();
  const currencySymbol = ((settings?.support_phone || '').replace(/\s/g, '').startsWith('+44') || (settings?.support_phone || '').replace(/\s/g, '').startsWith('44')) ? '£' : '₺';

  const renderAppointmentCard = (apt) => {
    const isCancelled = apt.status === "İptal" || apt.status === t('dashboard.status.cancelled');
    const isCompleted = apt.status === "Tamamlandı" || apt.status === t('dashboard.status.completed');
    const hasNote = apt.notes && apt.notes.trim().length > 0;
    const isExpanded = expandedNoteId === apt.id;
    return (
      <div
        key={apt.id}
        onClick={() => hasNote && toggleNote(apt.id)}
        className={`bg-white rounded-xl p-4 border border-gray-200 border-l-4 shadow-sm hover:bg-white/60 hover:border-t-gray-300 hover:border-r-gray-300 hover:border-b-gray-300 hover:shadow-xl hover:shadow-black/10 active:scale-[0.99] transition-all duration-300 ${isCancelled ? 'opacity-60' : ''} ${hasNote ? 'cursor-pointer' : ''} ${apt.status === "Bekliyor" || apt.status === t('dashboard.status.pending') ? 'border-l-amber-400' : apt.status === "Tamamlandı" || apt.status === t('dashboard.status.completed') ? 'border-l-green-500' : apt.status === "İptal" || apt.status === t('dashboard.status.cancelled') ? 'border-l-red-500' : 'border-l-gray-300'}`}
      >
        <div className="flex gap-4">
          <div className="flex flex-col items-center justify-center min-w-[60px] border-r border-gray-100 pr-4">
            <span className="text-xl font-black text-gray-900">{apt.appointment_time}</span>
            <span className="text-xs text-gray-500 font-medium">{calculateEndTime(apt.appointment_time, apt.service_duration)}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-start mb-1">
              <h3 className={`text-base font-bold text-gray-900 truncate ${isCancelled ? 'line-through text-gray-400' : ''}`}>{apt.customer_name}</h3>
              {isCompleted ? (
                <div className="bg-green-100 p-1.5 rounded-full shadow-sm">
                  <Check className="w-4 h-4 text-green-600" />
                </div>
              ) : isCancelled ? (
                <div className="bg-red-100 p-1.5 rounded-full shadow-sm">
                  <X className="w-4 h-4 text-red-600" />
                </div>
              ) : (
                <div className="bg-orange-100 p-1.5 rounded-full shadow-sm animate-pulse">
                  <Clock className="w-4 h-4 text-orange-600" />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 mb-3">
              <p className="text-sm text-gray-600 truncate">{apt.service_name}</p>
              {apt.session_number && apt.session_total && (
                <span className="text-[10px] bg-zinc-800 text-white px-1.5 py-0.5 rounded font-semibold tracking-wide whitespace-nowrap">
                  {apt.session_number}/{apt.session_total}
                </span>
              )}
              {hasNote && !isExpanded && <FileText className="w-3.5 h-3.5 text-amber-500 animate-pulse" />}
            </div>
            <div className="flex items-center justify-between mt-auto">
              <div className="flex gap-2">
                <button onClick={(e) => { e.stopPropagation(); handleCall(apt.phone); }} className="p-2 bg-green-50 text-green-600 hover:bg-green-100 rounded-lg transition-all hover:scale-105 active:scale-95 shadow-sm hover:shadow-md"><Phone className="w-4 h-4" /></button>
                <button onClick={(e) => { e.stopPropagation(); handleWhatsApp(apt.phone); }} className="p-2 bg-green-50 text-green-600 hover:bg-green-100 rounded-lg transition-all hover:scale-105 active:scale-95 shadow-sm hover:shadow-md"><WhatsAppIcon className="w-4 h-4" /></button>
              </div>
              <div className="flex items-center gap-2">
                {(userRole === 'admin' || canViewAll) && getStaffName(apt.staff_member_id) && (
                  <div className="flex items-center gap-1.5 bg-gray-50 px-2 py-1 rounded text-gray-600 border border-gray-100 shadow-sm">
                    <User className="w-3 h-3" />
                    <span className="text-xs font-bold">{getStaffName(apt.staff_member_id)}</span>
                  </div>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild><button onClick={(e) => e.stopPropagation()} className="p-2 hover:bg-gray-50 rounded-lg text-gray-400 transition-all hover:scale-105 active:scale-95"><MoreVertical className="w-5 h-5" /></button></DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    {!isCancelled && !isCompleted && <DropdownMenuItem onClick={() => handleStatusChange(apt.id, t('dashboard.status.cancelled'))} className="text-red-600"><X className="w-4 h-4 mr-2"/> {t('common.cancel')}</DropdownMenuItem>}
                    <DropdownMenuItem onClick={() => onEditAppointment(apt)}><Edit className="w-4 h-4 mr-2"/> {t('common.edit')}</DropdownMenuItem>
                    {apt.session_group_id && apt.session_number && apt.session_total && apt.session_number < apt.session_total && !isCancelled && (
                      <DropdownMenuItem onClick={() => { setSessionPlannerAppointment(apt); setShowSessionPlanner(true); }} className="text-blue-600">
                        <CalendarDays className="w-4 h-4 mr-2"/> {i18n.language === 'tr' ? 'Kalan Seansları Planla' : 'Plan Remaining Sessions'}
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => setDeleteDialog(apt)} className="text-red-600"><Trash2 className="w-4 h-4 mr-2"/> {t('common.delete')}</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </div>
        {isExpanded && hasNote && (
          <div className="mt-3 pt-3 border-t border-dashed border-gray-200 animate-in slide-in-from-top-1 fade-in duration-200">
            <div className="flex items-start gap-2 bg-amber-50 p-3 rounded-lg text-amber-900 text-sm shadow-sm">
              <FileText className="w-4 h-4 mt-0.5 shrink-0 text-amber-600" />
              <p className="font-medium">{apt.notes}</p>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50/50 pb-24 font-sans selection:bg-gray-200">
      
      {/* --- TUR BİLEŞENİ --- */}
      <TourGuide run={runTour} steps={tourSteps} onFinish={handleTourFinish} />

      {/* 1. HEADER — Karşılama (scroll ile kayar) */}
      <div className="px-5 pt-8 pb-4 bg-white relative">

        {/* AI Asistan Badge — sağ üst köşe */}
        {onOpenChat && (
          <button
            onClick={onOpenChat}
            className="absolute top-4 right-4 flex items-center gap-2 px-3 py-2 md:px-4 md:py-3 rounded-2xl bg-white/80 backdrop-blur-xl border border-gray-200/70 shadow-md shadow-black/8 hover:shadow-lg hover:bg-white active:scale-95 transition-all duration-200 group z-20"
          >
            <div className="w-6 h-6 md:w-9 md:h-9 rounded-lg md:rounded-xl bg-gradient-to-br from-gray-900 to-gray-700 flex items-center justify-center shrink-0">
              <Sparkles className="w-3 h-3 md:w-4 md:h-4 text-white group-hover:rotate-12 transition-transform duration-200" />
            </div>
            <div className="text-left hidden sm:block">
              <p className="text-[11px] md:text-sm font-bold text-gray-800 leading-none">AI Asistan</p>
              <p className="text-[9px] md:text-[11px] text-gray-400 leading-none mt-0.5">PLANN</p>
            </div>
          </button>
        )}

        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          {/* Sol Taraf: Karşılama */}
          <div className="tour-greeting"> {/* CLASS EKLENDI */}
            <h1 className="text-xl md:text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
              {greeting.text}, <span className="text-gray-700">{currentUserName}</span> <span className="text-2xl">{greeting.emoji}</span>
            </h1>
            <p className="text-base md:text-lg text-gray-600 font-medium mt-1.5 leading-relaxed">
              {format(new Date(), "d MMMM EEEE", { locale: dateLocale })}
            </p>
          </div>

          {/* Sağ Taraf: PERSONEL MOLA ALANI (sadece staff için) */}
          {userRole === 'staff' && (
            <div className="mt-4 md:mt-0 w-full md:w-auto md:min-w-[280px] md:mr-16 tour-breaks"> {/* CLASS EKLENDI */}
              <div className="bg-white border border-orange-100 rounded-2xl p-4 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="bg-orange-50 p-2 rounded-lg text-orange-600"><Coffee className="w-4 h-4" /></div>
                    <span className="text-sm font-bold text-gray-900">{t('dashboard.breaks.myBreaks')}</span>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setShowBreakDialog(true)} className="h-7 text-xs text-orange-600 hover:bg-orange-50 hover:text-orange-700 font-medium transition-all hover:scale-105 active:scale-95">+ {t('common.add')}</Button>
                </div>
                {todayBreaks.length > 0 ? (
                  <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide py-2 px-1">
                    {todayBreaks.map((brk) => (
                      <div key={brk.id} className="flex items-center gap-1.5 bg-orange-50 px-2 py-1 rounded-md shrink-0 border border-orange-100 shadow-sm">
                        <span className="text-xs font-bold text-orange-800">{brk.start_time}-{brk.end_time}</span>
                        <button onClick={() => handleDeleteBreak(brk.id)} className="text-orange-400 hover:text-red-500 transition-all hover:scale-105 active:scale-95"><X className="w-3 h-3" /></button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">{t('dashboard.breaks.noBreaksYet')}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 1b. İSTATİSTİK KARTLARI — Sticky (scroll'da sabit kalır) */}
      <div className="sticky z-10 bg-white/90 backdrop-blur-lg border-b border-gray-100 shadow-sm px-5 py-2" style={{ top: 'calc(env(safe-area-inset-top, 0px) + 57px)' }}>
        <div className="grid grid-cols-2 gap-2.5 tour-stats"> {/* CLASS EKLENDI */}
          {/* Randevu Sayısı */}
          <div className="bg-white rounded-lg p-2.5 border border-gray-200 hover:border-gray-300 transition-all cursor-default">
            <div className="flex items-center gap-1.5 mb-0.5">
              <CalendarDays className="w-3 h-3 text-gray-400" />
              <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('dashboard.summary.todayAppointments')}</span>
            </div>
            <p className="text-xl font-bold text-gray-900">{displayCount}</p>
          </div>

          {/* Ciro */}
          <div className="bg-white rounded-lg p-2.5 border border-gray-200 hover:border-gray-300 transition-all cursor-default">
            <div className="flex items-center gap-1.5 mb-0.5">
              <TrendingUp className="w-3 h-3 text-gray-400" />
              <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('dashboard.summary.todayRevenue')}</span>
            </div>
            <p className="text-xl font-bold text-gray-900">{i18n.language === 'en' ? `${currencySymbol}${Math.round(displayRevenue || 0).toLocaleString('en-GB')}` : `${(displayRevenue || 0).toLocaleString('tr-TR')}${currencySymbol}`}</p>
          </div>
        </div>
      </div>

      <div className="p-4 md:p-6 space-y-6">
        {/* 2. STAFF FILTER */}
        {(userRole === 'admin' || canViewAll) && staffMembers.length > 0 && (
          <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide py-3 px-1">
            <button onClick={() => setStaffFilter("all")} className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all border shadow-sm hover:shadow-md hover:scale-105 active:scale-95 ${staffFilter === "all" ? "bg-black text-white border-black" : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"}`}>{t('dashboard.todayFlow.allStaff')}</button>
            {staffMembers.map((staff) => (
              <button key={staff.username} onClick={() => setStaffFilter(staff.username)} className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all flex items-center gap-2 border shadow-sm hover:shadow-md hover:scale-105 active:scale-95 ${staffFilter === staff.username ? "bg-black text-white border-black" : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"}`}>
                {staffFilter === staff.username && <User className="w-3.5 h-3.5" />} {staff.full_name}
              </button>
            ))}
          </div>
        )}

        {/* 3. BUGÜNÜN AKIŞI */}
        <div className="tour-today-flow"> {/* CLASS EKLENDI */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base md:text-lg font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
              {t('dashboard.todayFlow.title')}
            </h2>
            <span className="text-xs md:text-sm font-bold bg-zinc-100 text-zinc-500 px-3 py-1 rounded-full shadow-sm">{filteredToday.length} {t('common.appointments')}</span>
          </div>

          {filteredToday.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 bg-white rounded-2xl border border-dashed border-gray-200 shadow-sm">
              <p className="text-sm text-gray-400 font-medium">{t('dashboard.todayFlow.noAppointments')}</p>
            </div>
          ) : (
            shouldSplit ? (
              <div className="space-y-6 md:space-y-0 md:grid md:grid-cols-2 md:gap-6">
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-sm font-bold text-orange-600 uppercase tracking-wider md:mb-4"><Sun className="w-4 h-4" /> {t('dashboard.todayFlow.beforeNoon')}</div>
                  {morningAppointments.length > 0 ? morningAppointments.map(apt => renderAppointmentCard(apt)) : <div className="p-4 text-center bg-gray-50 rounded-xl text-gray-400 text-xs italic shadow-sm">{t('dashboard.todayFlow.noAppointmentsShort')}</div>}
                </div>
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-sm font-bold text-blue-600 uppercase tracking-wider md:mb-4"><Moon className="w-4 h-4" /> {t('dashboard.todayFlow.afterNoon')}</div>
                  {afternoonAppointments.length > 0 ? afternoonAppointments.map(apt => renderAppointmentCard(apt)) : <div className="p-4 text-center bg-gray-50 rounded-xl text-gray-400 text-xs italic shadow-sm">{t('dashboard.todayFlow.noAppointmentsShort')}</div>}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredToday.map(apt => renderAppointmentCard(apt))}
              </div>
            )
          )}
        </div>

        {/* 4. YARININ RANDEVULARI */}
        {filteredTomorrow.length > 0 && (
          <>
            {filteredToday.length > 0 && (
              <div className="my-6" />
            )}
            
            <div className="tour-tomorrow">
              <div className={`flex items-center justify-between mb-4 ${filteredToday.length === 0 ? 'mt-8' : ''}`}>
              <h2 className="text-base md:text-lg font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">{t('dashboard.tomorrowAppointments.title')}</h2>
              <span className="text-xs md:text-sm font-bold bg-zinc-100 text-zinc-500 px-3 py-1 rounded-full shadow-sm">{filteredTomorrow.length} {t('common.appointments')}</span>
            </div>
            {(() => {
              const tomorrowMorning = filteredTomorrow.filter(apt => apt.appointment_time < "12:00");
              const tomorrowAfternoon = filteredTomorrow.filter(apt => apt.appointment_time >= "12:00");
              const tomorrowShouldSplit = tomorrowMorning.length > 0 && tomorrowAfternoon.length > 0;
              return (
                <>
                  {/* Mobil: her zaman tek liste */}
                  <div className="space-y-4 md:hidden">
                    {filteredTomorrow.map(apt => renderAppointmentCard(apt))}
                  </div>
                  {/* Masaüstü: split varsa 2 sütun */}
                  <div className="hidden md:block">
                    {tomorrowShouldSplit ? (
                      <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 text-sm font-bold text-orange-600 uppercase tracking-wider mb-4"><Sun className="w-4 h-4" /> {t('dashboard.todayFlow.beforeNoon')}</div>
                          {tomorrowMorning.map(apt => renderAppointmentCard(apt))}
                        </div>
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 text-sm font-bold text-blue-600 uppercase tracking-wider mb-4"><Moon className="w-4 h-4" /> {t('dashboard.todayFlow.afterNoon')}</div>
                          {tomorrowAfternoon.map(apt => renderAppointmentCard(apt))}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {filteredTomorrow.map(apt => renderAppointmentCard(apt))}
                      </div>
                    )}
                  </div>
                </>
              );
            })()}
          </div>
          </>
        )}

        {/* 5. GELECEK RANDEVULAR */}
        {upcoming.length > 0 && (
          <div className="tour-upcoming"> {/* CLASS EKLENDI */}
            <h2 className="text-base md:text-lg font-bold text-gray-900 mb-4 flex items-center gap-2 uppercase tracking-wider mt-8">{t('dashboard.upcomingAppointments.title')}</h2>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-100 overflow-hidden md:grid md:grid-cols-2 md:divide-y-0 md:gap-4 md:bg-transparent md:border-0 md:shadow-none">
              {upcoming.slice(0, upcomingVisibleCount).map((apt) => (
                (() => {
                  const hasNote = apt.notes && apt.notes.trim().length > 0;
                  const isExpanded = expandedNoteId === apt.id;
                  return (
                    <div
                      key={apt.id}
                      onClick={() => hasNote && toggleNote(apt.id)}
                      className={`p-4 hover:bg-white/60 hover:border-t-gray-300 hover:border-r-gray-300 hover:border-b-gray-300 hover:shadow-xl hover:shadow-black/10 active:scale-[0.99] transition-all duration-300 md:bg-white md:rounded-xl md:border md:border-gray-200 md:shadow-sm ${hasNote ? 'cursor-pointer' : ''}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="bg-gray-100 rounded-lg p-2 text-center min-w-[50px] shadow-sm">
                            <span className="block text-xs text-gray-500 font-bold uppercase">{format(new Date(apt.appointment_date || apt.date), "MMM", { locale: dateLocale })}</span>
                            <span className="block text-lg font-bold text-gray-900">{format(new Date(apt.appointment_date || apt.date), "d")}</span>
                          </div>
                          <div>
                            <h4 className="text-base font-bold text-gray-900">{apt.customer_name}</h4>
                            <div className="flex items-center gap-2">
                              <p className="text-sm text-gray-500">{apt.service_name} • {apt.appointment_time}</p>
                              {hasNote && !isExpanded && <FileText className="w-3.5 h-3.5 text-amber-500 animate-pulse" />}
                            </div>
                          </div>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" onClick={(e) => e.stopPropagation()} className="transition-all hover:scale-105 active:scale-95"><MoreVertical className="w-4 h-4 text-gray-400" /></Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onEditAppointment(apt); }}>
                              <Edit className="w-4 h-4 mr-2" /> {t('common.edit')}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setDeleteDialog(apt); }} className="text-red-600">
                              <Trash2 className="w-4 h-4 mr-2" /> {t('common.delete')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>

                      {isExpanded && hasNote && (
                        <div className="mt-3 pt-3 border-t border-dashed border-gray-200 animate-in slide-in-from-top-1 fade-in duration-200">
                          <div className="flex items-start gap-2 bg-amber-50 p-3 rounded-lg text-amber-900 text-sm shadow-sm">
                            <FileText className="w-4 h-4 mt-0.5 shrink-0 text-amber-600" />
                            <p className="font-medium">{apt.notes}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()
              ))}
              {upcoming.length > upcomingVisibleCount && (
                <button 
                  onClick={() => setUpcomingVisibleCount(prev => prev + 10)}
                  className="p-3 text-center bg-gray-50 hover:bg-gray-100 text-xs md:text-sm font-medium text-gray-500 md:col-span-2 rounded-xl border border-gray-200 transition-colors cursor-pointer w-full"
                >
                  + {upcoming.length - upcomingVisibleCount} {t('common.more')}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <AlertDialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
        <AlertDialogContent className="rounded-2xl max-w-xs shadow-lg">
          <AlertDialogHeader><AlertDialogTitle>{t('dashboard.deleteDialog.title')}</AlertDialogTitle><AlertDialogDescription>{t('dashboard.deleteDialog.description', { name: deleteDialog?.customer_name })}</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel className="rounded-xl transition-all hover:scale-105 active:scale-95">{t('dashboard.deleteDialog.cancel')}</AlertDialogCancel><AlertDialogAction onClick={() => handleDelete(deleteDialog?.id)} className="bg-red-600 hover:bg-red-700 rounded-xl transition-all hover:scale-105 active:scale-95">{t('dashboard.deleteDialog.delete')}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Seans Planlama Dialog */}
      <SessionPlannerDialog
        open={showSessionPlanner}
        onOpenChange={setShowSessionPlanner}
        appointment={sessionPlannerAppointment}
        onSuccess={onRefresh}
      />

      {showBreakDialog && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm animate-in fade-in">
          <Card className="w-full max-w-xs rounded-2xl shadow-2xl p-5">
            <h3 className="text-lg font-bold text-gray-900 mb-4">{t('dashboard.breaks.addBreakTitle')}</h3>
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div><label className="text-xs font-bold text-gray-500 mb-1 block">{t('common.start')}</label><input type="time" value={newBreakStart} onChange={e => setNewBreakStart(e.target.value)} className="w-full bg-gray-50 border-gray-200 rounded-lg p-2 text-sm font-bold text-gray-900 focus:ring-black shadow-sm" /></div>
              <div><label className="text-xs font-bold text-gray-500 mb-1 block">{t('common.end')}</label><input type="time" value={newBreakEnd} onChange={e => setNewBreakEnd(e.target.value)} className="w-full bg-gray-50 border-gray-200 rounded-lg p-2 text-sm font-bold text-gray-900 focus:ring-black shadow-sm" /></div>
            </div>
            <div className="flex gap-2"><Button variant="outline" onClick={() => setShowBreakDialog(false)} className="flex-1 rounded-lg h-10 text-xs transition-all hover:scale-105 active:scale-95">{t('common.cancel')}</Button><Button onClick={handleAddBreak} disabled={addingBreak} className="flex-1 rounded-lg h-10 bg-black hover:bg-gray-800 text-white text-xs transition-all hover:scale-105 active:scale-95">{addingBreak ? "..." : t('common.add')}</Button></div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default Dashboard;