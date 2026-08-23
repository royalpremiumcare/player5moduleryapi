import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";
import {
  CalendarDays, Users, Wallet, UserCog, Package, TrendingUp, TrendingDown,
  ArrowLeft, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";

// Grafik renk paleti (zinc/mavi/emerald aksanlı, premium his)
const PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#6366f1"];

const STATUS_COLORS = {
  "Tamamlandı": "#10b981",
  "Bekliyor": "#f59e0b",
  "İptal": "#ef4444",
  "İptal Edildi": "#ef4444",
  "Gelmedi": "#a1a1aa",
  "Ödeme Bekleniyor": "#3b82f6",
};

const MODE_COLORS = { on_site: "#71717a", online: "#3b82f6", deposit: "#f59e0b" };

const Statistics = ({ userRole, onNavigate, settings }) => {
  const { t, i18n } = useTranslation();
  const [range, setRange] = useState("this_year");
  const [tab, setTab] = useState("appointments");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const currencySymbol = useMemo(() => {
    const p = (settings?.support_phone || "").replace(/\s/g, "");
    return (p.startsWith("+44") || p.startsWith("44")) ? "£" : "₺";
  }, [settings]);

  const formatMoney = useCallback((amount) => {
    const n = Math.round(Number(amount) || 0);
    return i18n.language === "en"
      ? `${currencySymbol}${n.toLocaleString("en-GB")}`
      : `${n.toLocaleString("tr-TR")}${currencySymbol}`;
  }, [currencySymbol, i18n.language]);

  const shortNum = useCallback((n) => {
    const v = Number(n) || 0;
    if (Math.abs(v) >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
    if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}k`;
    return String(Math.round(v));
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/stats/analytics", { params: { range } });
      setData(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || t("stats.loadError", "İstatistikler yüklenemedi"));
    } finally {
      setLoading(false);
    }
  }, [range, t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const weekdayLabels = useMemo(() => (
    i18n.language === "en"
      ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
      : ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
  ), [i18n.language]);

  const fmtLabel = useCallback((label) => {
    if (!label) return "";
    if (label.length === 7) {
      const [y, m] = label.split("-");
      const d = new Date(Number(y), Number(m) - 1, 1);
      return d.toLocaleDateString(i18n.language === "en" ? "en-GB" : "tr-TR", { month: "short" });
    }
    const d = new Date(label);
    return d.toLocaleDateString(i18n.language === "en" ? "en-GB" : "tr-TR", { day: "2-digit", month: "short" });
  }, [i18n.language]);

  const ranges = [
    { id: "today", label: t("stats.range.today", "Bugün") },
    { id: "this_week", label: t("stats.range.thisWeek", "Bu Hafta") },
    { id: "this_month", label: t("stats.range.thisMonth", "Bu Ay") },
    { id: "last_month", label: t("stats.range.lastMonth", "Geçen Ay") },
    { id: "this_year", label: t("stats.range.thisYear", "Bu Yıl") },
  ];

  const tabs = [
    { id: "appointments", label: t("stats.tabs.appointments", "Randevular"), icon: CalendarDays },
    { id: "customers", label: t("stats.tabs.customers", "Müşteriler"), icon: Users },
    { id: "kasa", label: t("stats.tabs.kasa", "Kasa"), icon: Wallet },
    { id: "personnel", label: t("stats.tabs.personnel", "Personel"), icon: UserCog },
    { id: "services", label: t("stats.tabs.services", "Hizmetler"), icon: Package },
  ];

  const s = data?.summary || {};
  const ts = data?.timeseries || [];

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="max-w-5xl mx-auto px-4 pt-4 pb-28">
        {/* Başlık */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => onNavigate && onNavigate("dashboard")}
            className="p-2 -ml-2 rounded-lg hover:bg-zinc-100 transition-colors"
            aria-label={t("common.back", "Geri")}
          >
            <ArrowLeft className="w-5 h-5 text-zinc-600" />
          </button>
          <h1 className="text-xl font-bold text-zinc-900">{t("stats.title", "İstatistikler")}</h1>
        </div>

        {/* Tarih aralığı seçici */}
        <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 mb-4 no-scrollbar">
          {ranges.map((r) => (
            <button
              key={r.id}
              onClick={() => setRange(r.id)}
              className={`shrink-0 px-4 h-9 rounded-full text-sm font-medium transition-colors border ${
                range === r.id
                  ? "bg-zinc-900 text-white border-zinc-900"
                  : "bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Sekmeler */}
        <div className="flex gap-1 overflow-x-auto pb-1 mb-5 border-b border-zinc-200 no-scrollbar">
          {tabs.map((tb) => {
            const Icon = tb.icon;
            const active = tab === tb.id;
            return (
              <button
                key={tb.id}
                onClick={() => setTab(tb.id)}
                className={`shrink-0 flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  active
                    ? "border-zinc-900 text-zinc-900"
                    : "border-transparent text-zinc-500 hover:text-zinc-800"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tb.label}
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 text-zinc-400">
            <Loader2 className="w-7 h-7 animate-spin mb-3" />
            <p className="text-sm">{t("stats.loading", "Yükleniyor...")}</p>
          </div>
        ) : !data ? (
          <div className="text-center py-24 text-zinc-400 text-sm">
            {t("stats.noData", "Veri yok")}
          </div>
        ) : (
          <>
            {tab === "appointments" && (
              <AppointmentsTab data={data} s={s} ts={ts} t={t} fmtLabel={fmtLabel} weekdayLabels={weekdayLabels} />
            )}
            {tab === "customers" && (
              <CustomersTab data={data} s={s} t={t} fmtLabel={fmtLabel} formatMoney={formatMoney} />
            )}
            {tab === "kasa" && (
              <KasaTab data={data} s={s} ts={ts} t={t} fmtLabel={fmtLabel} formatMoney={formatMoney} shortNum={shortNum} />
            )}
            {tab === "personnel" && (
              <PersonnelTab data={data} t={t} formatMoney={formatMoney} shortNum={shortNum} />
            )}
            {tab === "services" && (
              <ServicesTab data={data} t={t} formatMoney={formatMoney} shortNum={shortNum} />
            )}
          </>
        )}
      </div>
    </div>
  );
};

/* ─── Ortak sunum bileşenleri ─────────────────────────────────────────── */

const KpiCard = ({ label, value, sub, accent = "text-zinc-900", icon: Icon }) => (
  <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm p-4">
    <div className="flex items-center justify-between">
      <p className="text-xs font-medium text-zinc-500">{label}</p>
      {Icon && <Icon className="w-4 h-4 text-zinc-300" />}
    </div>
    <p className={`text-2xl font-semibold tracking-tight mt-1.5 ${accent}`}>{value}</p>
    {sub != null && <p className="text-xs text-zinc-400 mt-0.5 truncate">{sub}</p>}
  </div>
);

const ChartCard = ({ title, children, right }) => (
  <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm p-4 sm:p-5">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-sm font-semibold text-zinc-800">{title}</h3>
      {right}
    </div>
    {children}
  </div>
);

const EmptyChart = ({ label }) => (
  <div className="h-[220px] flex items-center justify-center text-sm text-zinc-300">{label}</div>
);

const LegendDots = ({ items }) => (
  <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
    {items.map((it, idx) => (
      <div key={idx} className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: it.color }} />
        <span className="text-xs text-zinc-500">{it.name}</span>
        {it.value != null && <span className="text-xs font-medium text-zinc-700">{it.value}</span>}
      </div>
    ))}
  </div>
);

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #e4e4e7",
  boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
  fontSize: 12,
};

/* ─── RANDEVULAR ──────────────────────────────────────────────────────── */

const AppointmentsTab = ({ data, s, ts, t, fmtLabel, weekdayLabels }) => {
  const byStatus = (data.appointments?.by_status || []).map((x, i) => ({
    name: x.status, value: x.count, color: STATUS_COLORS[x.status] || PALETTE[i % PALETTE.length],
  }));
  const bySource = (data.appointments?.by_source || []).map((x) => ({
    name: x.source === "public_booking" ? t("stats.source.online", "Online") : t("stats.source.manual", "Manuel"),
    value: x.count,
    color: x.source === "public_booking" ? "#3b82f6" : "#a1a1aa",
  }));
  const weekday = (data.appointments?.by_weekday || []).map((x) => ({
    name: weekdayLabels[x.weekday] || String(x.weekday), count: x.count,
  }));
  const hours = (data.appointments?.by_hour || []).map((x) => ({
    name: `${String(x.hour).padStart(2, "0")}`, count: x.count,
  }));
  const trend = ts.map((x) => ({ name: fmtLabel(x.label), Randevu: x.appointments }));

  const statusSum = (names) => (data.appointments?.by_status || [])
    .filter((x) => names.includes(x.status))
    .reduce((sum, x) => sum + x.count, 0);
  const cancelledCount = statusSum(["İptal", "İptal Edildi"]);
  const deletedCount = statusSum(["Gelmedi"]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label={t("stats.kpi.totalAppointments", "Toplam Randevu")} value={s.total_appointments ?? 0} icon={CalendarDays} />
        <KpiCard label={t("stats.kpi.completed", "Tamamlanan")} value={s.completed_appointments ?? 0} accent="text-emerald-600" />
        <KpiCard label={t("stats.kpi.cancelled", "İptal Olan")} value={cancelledCount} accent="text-red-600" />
        <KpiCard label={t("stats.kpi.deleted", "Silinen")} value={deletedCount} accent="text-zinc-600" />
      </div>

      <ChartCard title={t("stats.chart.appointmentTrend", "Randevu Trendi")}>
        {trend.length ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trend} margin={{ left: -18, right: 6, top: 6 }}>
              <defs>
                <linearGradient id="apptGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} minTickGap={16} />
              <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} allowDecimals={false} width={34} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="Randevu" stroke="#3b82f6" strokeWidth={2} fill="url(#apptGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title={t("stats.chart.byStatus", "Duruma Göre Dağılım")}>
          {byStatus.some((x) => x.value > 0) ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={byStatus} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {byStatus.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <LegendDots items={byStatus.map((x) => ({ name: x.name, value: x.value, color: x.color }))} />
            </>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>

        <ChartCard title={t("stats.chart.bySource", "Kaynağa Göre")}>
          {bySource.some((x) => x.value > 0) ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={bySource} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {bySource.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <LegendDots items={bySource.map((x) => ({ name: x.name, value: x.value, color: x.color }))} />
            </>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title={t("stats.chart.byWeekday", "Haftanın Günü")}>
          {weekday.some((x) => x.count > 0) ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={weekday} margin={{ left: -20, right: 6, top: 6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} allowDecimals={false} width={34} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#fafafa" }} formatter={(v) => [v, t("stats.tooltip.appointments", "Randevu")]} />
                <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} maxBarSize={38} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>

        <ChartCard title={t("stats.chart.byHour", "Saat Dağılımı")}>
          {hours.some((x) => x.count > 0) ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={hours} margin={{ left: -20, right: 6, top: 6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} minTickGap={8} />
                <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} allowDecimals={false} width={34} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#fafafa" }} formatter={(v) => [v, t("stats.tooltip.appointments", "Randevu")]} />
                <Bar dataKey="count" fill="#14b8a6" radius={[6, 6, 0, 0]} maxBarSize={26} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>
      </div>
    </div>
  );
};

/* ─── MÜŞTERİLER ──────────────────────────────────────────────────────── */

const CustomersTab = ({ data, s, t, fmtLabel, formatMoney }) => {
  const nvr = data.customers?.new_vs_returning || { new: 0, returning: 0 };
  const nvrPie = [
    { name: t("stats.customers.new", "Yeni"), value: nvr.new, color: "#3b82f6" },
    { name: t("stats.customers.returning", "Geri Dönen"), value: nvr.returning, color: "#10b981" },
  ];
  const series = (data.customers?.new_series || []).map((x) => ({ name: fmtLabel(x.label), Yeni: x.count }));
  const top = data.customers?.top || [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <KpiCard label={t("stats.kpi.totalCustomers", "Toplam Müşteri")} value={s.total_customers ?? 0} icon={Users} />
        <KpiCard label={t("stats.kpi.newCustomers", "Yeni Müşteri")} value={s.new_customers ?? 0} accent="text-blue-600" />
        <KpiCard label={t("stats.kpi.returning", "Geri Dönen")} value={nvr.returning ?? 0} accent="text-emerald-600" />
      </div>

      <ChartCard title={t("stats.chart.newCustomerTrend", "Yeni Müşteri Trendi")}>
        {series.length ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={series} margin={{ left: -18, right: 6, top: 6 }}>
              <defs>
                <linearGradient id="custGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} minTickGap={16} />
              <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} allowDecimals={false} width={34} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="Yeni" stroke="#3b82f6" strokeWidth={2} fill="url(#custGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title={t("stats.chart.newVsReturning", "Yeni vs Geri Dönen")}>
          {(nvr.new + nvr.returning) > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={nvrPie} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {nvrPie.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <LegendDots items={nvrPie.map((x) => ({ name: x.name, value: x.value, color: x.color }))} />
            </>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>

        <ChartCard title={t("stats.chart.allCustomers", "Tüm Müşteriler")} right={<span className="text-xs text-zinc-400">{top.length}</span>}>
          {top.length ? (
            <div className="divide-y divide-zinc-50">
              {top.map((c, i) => (
                <div key={i} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-6 h-6 shrink-0 rounded-full bg-zinc-100 text-zinc-500 text-xs font-semibold flex items-center justify-center">{i + 1}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-800 truncate">{c.name}</p>
                      <p className="text-xs text-zinc-400">{c.visits} {t("stats.customers.visits", "ziyaret")}</p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-zinc-900 tabular-nums">{formatMoney(c.spent)}</span>
                </div>
              ))}
            </div>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>
      </div>
    </div>
  );
};

/* ─── KASA ────────────────────────────────────────────────────────────── */

const KasaTab = ({ data, s, ts, t, fmtLabel, formatMoney, shortNum }) => {
  const incExp = ts.map((x) => ({ name: fmtLabel(x.label), Gelir: x.income, Gider: x.expense }));
  const modeLabels = {
    on_site: t("stats.mode.onSite", "Yerinde"),
    online: t("stats.mode.online", "Tamamı Online"),
    deposit: t("stats.mode.deposit", "Kapora"),
  };
  const modePie = (data.kasa?.income_by_mode || []).map((x) => ({
    name: modeLabels[x.mode] || x.mode, value: x.amount, count: x.count, color: MODE_COLORS[x.mode] || "#a1a1aa",
  }));
  const cats = (data.kasa?.expense_by_category || []).map((x) => ({ name: x.category, amount: x.amount }));
  const incSvc = (data.kasa?.income_by_service || []).map((x) => ({ name: x.name, amount: x.amount }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label={t("stats.kpi.income", "Gelir")} value={formatMoney(s.total_income)} accent="text-emerald-600" icon={TrendingUp} />
        <KpiCard label={t("stats.kpi.expense", "Gider")} value={formatMoney(s.total_expense)} accent="text-red-600" icon={TrendingDown} />
        <KpiCard label={t("stats.kpi.net", "Net Kâr")} value={formatMoney(s.net_profit)} accent={s.net_profit >= 0 ? "text-zinc-900" : "text-red-600"} />
        <KpiCard label={t("stats.kpi.avgTicket", "Ort. Fiş")} value={formatMoney(s.avg_ticket)} accent="text-zinc-900" />
      </div>

      <ChartCard title={t("stats.chart.incomeExpense", "Gelirler ve Giderler")}>
        {incExp.length ? (
          <>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={incExp} margin={{ left: -6, right: 6, top: 6 }}>
                <defs>
                  <linearGradient id="incGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} minTickGap={16} />
                <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} width={44} tickFormatter={shortNum} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatMoney(v)} />
                <Area type="monotone" dataKey="Gelir" stroke="#10b981" strokeWidth={2} fill="url(#incGrad)" />
                <Area type="monotone" dataKey="Gider" stroke="#ef4444" strokeWidth={2} fill="url(#expGrad)" />
              </AreaChart>
            </ResponsiveContainer>
            <LegendDots items={[
              { name: t("stats.kpi.income", "Gelir"), color: "#10b981" },
              { name: t("stats.kpi.expense", "Gider"), color: "#ef4444" },
            ]} />
          </>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title={t("stats.chart.incomeByMode", "Gelir Dağılımı (Tahsilat)")}>
          {modePie.some((x) => x.value > 0) ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={modePie} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {modePie.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatMoney(v)} />
                </PieChart>
              </ResponsiveContainer>
              <LegendDots items={modePie.map((x) => ({ name: x.name, value: formatMoney(x.value), color: x.color }))} />
            </>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>

        <ChartCard title={t("stats.chart.expenseByCategory", "Giderler (Kategori)")}>
          {cats.length ? (
            <ResponsiveContainer width="100%" height={Math.max(200, cats.length * 40)}>
              <BarChart data={cats} layout="vertical" margin={{ left: 8, right: 12, top: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} tickFormatter={shortNum} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} width={90} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [formatMoney(v), t("stats.kpi.expense", "Gider")]} cursor={{ fill: "#fafafa" }} />
                <Bar dataKey="amount" fill="#f59e0b" radius={[0, 6, 6, 0]} maxBarSize={26} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>
      </div>

      <ChartCard title={t("stats.chart.incomeByService", "Hizmete Göre Gelir")}>
        {incSvc.length ? (
          <ResponsiveContainer width="100%" height={Math.max(200, incSvc.length * 40)}>
            <BarChart data={incSvc} layout="vertical" margin={{ left: 8, right: 12, top: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} tickFormatter={shortNum} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} width={110} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [formatMoney(v), t("stats.kpi.income", "Gelir")]} cursor={{ fill: "#fafafa" }} />
              <Bar dataKey="amount" fill="#3b82f6" radius={[0, 6, 6, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>
    </div>
  );
};

/* ─── PERSONEL ────────────────────────────────────────────────────────── */

const PersonnelTab = ({ data, t, formatMoney, shortNum }) => {
  const rows = (data.personnel || []).map((p) => ({
    ...p,
    displayName: p.username === "__unassigned__" ? t("stats.personnel.unassigned", "Atanmamış") : (p.full_name || p.username),
  }));
  const chart = rows.map((p) => ({ name: p.displayName, Ciro: p.revenue }));
  const topEarner = rows[0];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <KpiCard label={t("stats.kpi.activeStaff", "Personel")} value={rows.length} icon={UserCog} />
        <KpiCard label={t("stats.kpi.topEarner", "En Çok Ciro")} value={topEarner ? formatMoney(topEarner.revenue) : "—"} sub={topEarner?.displayName} accent="text-emerald-600" />
      </div>

      <ChartCard title={t("stats.chart.revenueByStaff", "Personele Göre Ciro")}>
        {chart.some((x) => x.Ciro > 0) ? (
          <ResponsiveContainer width="100%" height={Math.max(200, chart.length * 44)}>
            <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 12, top: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} tickFormatter={shortNum} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} width={100} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatMoney(v)} cursor={{ fill: "#fafafa" }} />
              <Bar dataKey="Ciro" fill="#8b5cf6" radius={[0, 6, 6, 0]} maxBarSize={30} />
            </BarChart>
          </ResponsiveContainer>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>

      <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm overflow-hidden">
        <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-100 text-xs font-semibold text-zinc-400 uppercase tracking-wide">
          <div className="col-span-6">{t("stats.table.staff", "Personel")}</div>
          <div className="col-span-2 text-right">{t("stats.table.completed", "Randevu")}</div>
          <div className="col-span-4 text-right">{t("stats.table.revenue", "Ciro")}</div>
        </div>
        {rows.length ? rows.map((p, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-zinc-50 last:border-0 items-center">
            <div className="col-span-6 text-sm font-medium text-zinc-800 truncate">{p.displayName}</div>
            <div className="col-span-2 text-right text-sm text-zinc-600 tabular-nums">{p.completed}</div>
            <div className="col-span-4 text-right text-sm font-semibold text-zinc-900 tabular-nums">{formatMoney(p.revenue)}</div>
          </div>
        )) : <div className="py-10 text-center text-sm text-zinc-300">{t("stats.noData", "Veri yok")}</div>}
      </div>
    </div>
  );
};

/* ─── HİZMETLER ───────────────────────────────────────────────────────── */

const ServicesTab = ({ data, t, formatMoney, shortNum }) => {
  const services = data.services || [];
  const topByCount = services.slice(0, 8).map((x) => ({ name: x.name, Adet: x.count }));
  const mixSource = services.slice(0, 6);
  const mixTotal = mixSource.reduce((sum, x) => sum + x.count, 0) || 1;
  const mix = mixSource.map((x, i) => ({ name: x.name, value: x.count, color: PALETTE[i % PALETTE.length] }));
  const topService = services[0];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <KpiCard label={t("stats.kpi.serviceCount", "Hizmet Çeşidi")} value={services.length} icon={Package} />
        <KpiCard label={t("stats.kpi.topService", "En Popüler")} value={topService ? topService.name : "—"} sub={topService ? `${topService.count} ${t("stats.services.times", "kez")}` : null} accent="text-zinc-900" />
      </div>

      <ChartCard title={t("stats.chart.mostBooked", "En Çok Alınan Hizmetler")}>
        {topByCount.some((x) => x.Adet > 0) ? (
          <ResponsiveContainer width="100%" height={Math.max(200, topByCount.length * 40)}>
            <BarChart data={topByCount} layout="vertical" margin={{ left: 8, right: 12, top: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} width={110} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#fafafa" }} />
              <Bar dataKey="Adet" fill="#10b981" radius={[0, 6, 6, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title={t("stats.chart.serviceMix", "Hizmet Karması")}>
          {mix.some((x) => x.value > 0) ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={mix} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {mix.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <LegendDots items={mix.map((x) => ({ name: x.name, value: `%${Math.round((x.value / mixTotal) * 100)}`, color: x.color }))} />
            </>
          ) : <EmptyChart label={t("stats.noData", "Veri yok")} />}
        </ChartCard>

        <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm overflow-hidden">
          <div className="grid grid-cols-12 px-4 py-3 border-b border-zinc-100 text-xs font-semibold text-zinc-400 uppercase tracking-wide">
            <div className="col-span-6">{t("stats.table.service", "Hizmet")}</div>
            <div className="col-span-2 text-right">{t("stats.table.count", "Adet")}</div>
            <div className="col-span-4 text-right">{t("stats.table.revenue", "Ciro")}</div>
          </div>
          {services.length ? services.slice(0, 12).map((sv, i) => (
            <div key={i} className="grid grid-cols-12 px-4 py-3 border-b border-zinc-50 last:border-0 items-center">
              <div className="col-span-6 text-sm font-medium text-zinc-800 truncate">{sv.name}</div>
              <div className="col-span-2 text-right text-sm text-zinc-600 tabular-nums">{sv.count}</div>
              <div className="col-span-4 text-right text-sm font-semibold text-zinc-900 tabular-nums">{formatMoney(sv.revenue)}</div>
            </div>
          )) : <div className="py-10 text-center text-sm text-zinc-300">{t("stats.noData", "Veri yok")}</div>}
        </div>
      </div>
    </div>
  );
};

export default Statistics;
