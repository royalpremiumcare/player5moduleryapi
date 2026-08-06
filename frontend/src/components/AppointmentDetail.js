import { useState, useEffect, useCallback } from "react";
import { format, parseISO } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import {
  X, Phone, Calendar as CalendarIcon, Clock, User, Scissors,
  CreditCard, FileText, Loader2, AlertCircle, Layers,
} from "lucide-react";
import api from "../api/api";

/**
 * Bildirime tıklayınca açılan randevu detay sayfası.
 * GET /appointments/{id} ile veriyi çeker. Kapatınca onClose çağrılır
 * (App.js dashboard'a döner).
 */
const AppointmentDetail = ({ appointmentId, userRole, canViewAll, onClose }) => {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "tr" ? tr : enGB;
  const isTr = i18n.language === "tr";
  const currency = isTr ? "₺" : "£";
  const localeStr = isTr ? "tr-TR" : "en-GB";

  const [appointment, setAppointment] = useState(null);
  const [staffMembers, setStaffMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!appointmentId) return;
    setLoading(true);
    setError(false);
    try {
      const res = await api.get(`/appointments/${appointmentId}`);
      setAppointment(res.data);
      if (userRole === "admin" || canViewAll) {
        try {
          const staffRes = await api.get("/users");
          setStaffMembers((staffRes.data || []).filter((u) => u.role === "staff"));
        } catch (_) { /* personel adı opsiyonel */ }
      }
    } catch (e) {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [appointmentId, userRole, canViewAll]);

  useEffect(() => { load(); }, [load]);

  const getStaffName = (staffId) => {
    if (!staffId) return null;
    const s = staffMembers.find((m) => m.username === staffId);
    return s?.full_name || s?.username || null;
  };

  const calcEndTime = (time, duration) => {
    if (!time || !duration) return null;
    try {
      const [h, m] = time.split(":").map(Number);
      const total = h * 60 + m + Number(duration);
      const eh = Math.floor((total % 1440) / 60);
      const em = total % 60;
      return `${String(eh).padStart(2, "0")}:${String(em).padStart(2, "0")}`;
    } catch (_) { return null; }
  };

  const statusMeta = (status) => {
    switch (status) {
      case "Tamamlandı":
        return { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", label: isTr ? "Tamamlandı" : "Completed" };
      case "İptal":
      case "İptal Edildi":
        return { cls: "bg-red-50 text-red-700 border-red-200", label: isTr ? "İptal" : "Cancelled" };
      case "Gelmedi":
        return { cls: "bg-zinc-100 text-zinc-600 border-zinc-200", label: isTr ? "Gelmedi" : "No-show" };
      case "Ödeme Bekleniyor":
        return { cls: "bg-blue-50 text-blue-700 border-blue-200", label: isTr ? "Ödeme Bekleniyor" : "Awaiting Payment" };
      default:
        return { cls: "bg-amber-50 text-amber-700 border-amber-200", label: isTr ? "Bekliyor" : "Pending" };
    }
  };

  const Row = ({ icon: Icon, label, children }) => (
    <div className="flex items-start justify-between gap-3 py-3.5">
      <span className="flex items-center gap-2 text-sm text-zinc-500 font-medium shrink-0">
        <Icon className="w-4 h-4 text-zinc-400" />
        {label}
      </span>
      <div className="text-sm font-semibold text-zinc-900 text-right min-w-0 break-words">{children}</div>
    </div>
  );

  const multiService = Array.isArray(appointment?.services) && appointment.services.length > 1;
  const staffName = (userRole === "admin" || canViewAll) ? getStaffName(appointment?.staff_member_id) : null;
  const endTime = appointment ? calcEndTime(appointment.appointment_time, appointment.service_duration) : null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-zinc-50 overflow-y-auto animate-in fade-in slide-in-from-bottom-4 duration-300"
      style={{ paddingBottom: "calc(env(safe-area-inset-bottom) + 24px)" }}
    >
      {/* Üst çubuk: başlık + kapat */}
      <div
        className="sticky top-0 z-10 bg-zinc-50/95 backdrop-blur-sm border-b border-zinc-200"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="flex items-center justify-between h-14 px-4">
          <h1 className="text-base font-bold text-zinc-900">
            {t("appointmentDetail.title", "Randevu Detayı")}
          </h1>
          <button
            onClick={onClose}
            aria-label={t("common.close", "Kapat")}
            className="w-9 h-9 flex items-center justify-center rounded-full text-zinc-500 hover:bg-zinc-200/70 active:scale-95 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* İçerik */}
      <div className="px-4 py-5 max-w-md mx-auto">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-7 h-7 text-zinc-400 animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm p-8 text-center mt-6">
            <AlertCircle className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
            <p className="text-sm text-zinc-500 font-medium">
              {t("appointmentDetail.notFoundDesc", "Bu randevu silinmiş veya artık mevcut değil.")}
            </p>
            <button
              onClick={onClose}
              className="mt-6 w-full h-12 rounded-xl bg-zinc-900 hover:bg-black text-white font-bold shadow-sm active:scale-[0.98] transition"
            >
              {t("appointmentDetail.backToDashboard", "Panele Dön")}
            </button>
          </div>
        ) : (
          <>
            {/* Üst rozet satırı: online etiketi + durum */}
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[11px] font-semibold text-emerald-700">
                {t("appointmentDetail.onlineBadge", "Yeni Online Randevu")}
              </span>
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${statusMeta(appointment.status).cls}`}>
                {statusMeta(appointment.status).label}
              </span>
            </div>

            {/* Detay kartı */}
            <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm px-5 divide-y divide-zinc-100">
              {/* Müşteri */}
              <Row icon={User} label={t("appointmentDetail.customer", "Müşteri")}>
                {appointment.customer_name || "—"}
              </Row>

              {/* Telefon */}
              {appointment.phone && (
                <Row icon={Phone} label={t("appointmentDetail.phone", "Telefon")}>
                  <a href={`tel:${appointment.phone}`} className="text-zinc-900 hover:text-zinc-600 transition">
                    {appointment.phone}
                  </a>
                </Row>
              )}

              {/* Hizmet(ler) */}
              {multiService ? (
                <div className="py-3.5">
                  <span className="flex items-center gap-2 text-sm text-zinc-500 font-medium mb-2">
                    <Layers className="w-4 h-4 text-zinc-400" />
                    {t("appointments.fields.service", "Hizmet")}
                  </span>
                  <div className="space-y-1.5 rounded-xl border border-zinc-100 bg-zinc-50 p-3">
                    {[...appointment.services]
                      .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))
                      .map((svc, idx) => (
                        <div key={`${svc.service_id}-${idx}`} className="flex items-center justify-between gap-2">
                          <span className="text-sm text-zinc-900 flex items-center gap-2 min-w-0">
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-zinc-900 text-white text-[10px] font-bold flex-shrink-0">{idx + 1}</span>
                            <span className="truncate">{svc.name_snapshot}</span>
                          </span>
                          <span className="text-xs text-zinc-500 flex-shrink-0">
                            {svc.duration_snapshot} {isTr ? "dk" : "min"} · {Math.round(svc.price_snapshot).toLocaleString(localeStr)} {currency}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              ) : (
                <Row icon={Scissors} label={t("appointments.fields.service", "Hizmet")}>
                  {appointment.service_name}
                </Row>
              )}

              {/* Tarih (14 Mayıs Çarşamba) */}
              <Row icon={CalendarIcon} label={t("appointments.fields.date", "Tarih")}>
                {appointment.appointment_date
                  ? format(parseISO(appointment.appointment_date), "d MMMM EEEE", { locale: dateLocale })
                  : t("common.noDate", "Tarih yok")}
              </Row>

              {/* Saat */}
              <Row icon={Clock} label={t("appointments.fields.time", "Saat")}>
                <span>{appointment.appointment_time || "--:--"}</span>
                {endTime && <span className="text-zinc-400 font-normal"> – {endTime}</span>}
              </Row>

              {/* Ücret */}
              {appointment.service_price != null && appointment.service_price > 0 && (
                <Row icon={CreditCard} label={t("appointments.fields.price", "Ücret")}>
                  {Number(appointment.service_price).toLocaleString(localeStr)} {currency}
                </Row>
              )}

              {/* Personel */}
              {staffName && (
                <Row icon={User} label={t("customers.staff", "Personel")}>
                  {staffName}
                </Row>
              )}

              {/* Notlar */}
              {appointment.notes && (
                <div className="py-3.5">
                  <span className="flex items-center gap-2 text-sm text-zinc-500 font-medium mb-1.5">
                    <FileText className="w-4 h-4 text-zinc-400" />
                    {t("customers.fields.notes", "Notlar")}
                  </span>
                  <p className="text-sm text-zinc-800 leading-relaxed">{appointment.notes}</p>
                </div>
              )}
            </div>

            {/* Panele dön */}
            <button
              onClick={onClose}
              className="mt-6 w-full h-12 rounded-xl bg-zinc-900 hover:bg-black text-white font-bold shadow-sm active:scale-[0.98] transition"
            >
              {t("appointmentDetail.backToDashboard", "Panele Dön")}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AppointmentDetail;
