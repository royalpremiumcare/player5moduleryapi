import { useState, useEffect, useMemo } from "react";
import {
  ArrowLeft, Sparkles, Save, Loader2, Clock, ExternalLink, AlertTriangle
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";

const MarketingAssistant = ({ onNavigate }) => {
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [services, setServices] = useState([]);
  const [daysMap, setDaysMap] = useState({});
  const [meta, setMeta] = useState({ company_name: "", slug: null, default_days: 21, sector_key: "genel", stats: {} });
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/marketing/autopilot");
      const d = res.data || {};
      setEnabled(!!d.enabled);
      setServices(d.services || []);
      const map = {};
      (d.services || []).forEach((s) => { map[s.id] = s.days; });
      setDaysMap(map);
      setMeta({
        company_name: d.company_name || t('settings.marketingAssistant.yourBusiness'),
        slug: d.slug || null,
        default_days: d.default_days || 21,
        sector_key: d.sector_key || "genel",
        stats: d.stats || {},
      });
      setDirty(false);
    } catch (_) {
      toast.error(t('settings.marketingAssistant.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const persist = async (nextEnabled, nextDays) => {
    setSaving(true);
    try {
      await api.put("/marketing/autopilot", { enabled: nextEnabled, days: nextDays });
      setDirty(false);
    } catch (_) {
      toast.error(t('settings.marketingAssistant.saveError'));
      throw _;
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (checked) => {
    const prev = enabled;
    setEnabled(checked);
    try {
      await persist(checked, daysMap);
      toast.success(checked
        ? t('settings.marketingAssistant.turnedOn')
        : t('settings.marketingAssistant.turnedOff'));
    } catch (_) {
      setEnabled(prev);
    }
  };

  const handleDayChange = (serviceId, value) => {
    const n = value === "" ? "" : Math.max(1, Math.min(365, parseInt(value, 10) || 0));
    setDaysMap((m) => ({ ...m, [serviceId]: n }));
    setDirty(true);
  };

  const handleSaveDays = async () => {
    const cleaned = {};
    Object.entries(daysMap).forEach(([k, v]) => {
      cleaned[k] = Math.max(1, Math.min(365, parseInt(v, 10) || meta.default_days));
    });
    setDaysMap(cleaned);
    try {
      await persist(enabled, cleaned);
      toast.success(t('settings.marketingAssistant.saved'));
    } catch (_) {}
  };

  // Gövde metni sektöre göre (Meta'daki gerçek şablonlarla birebir). {{1}} = müşteri adı.
  // WhatsApp *bold* işaretleri (*) önizlemede temizlenir.
  const previewBody = useMemo(() => {
    const key = meta.sector_key || "genel";
    const name = t('settings.marketingAssistant.exampleName');
    const raw = t(`settings.marketingAssistant.previewMessages.${key}`, {
      "1": name,
      defaultValue: t('settings.marketingAssistant.previewMessages.genel', { "1": name }),
    });
    return (raw || "").replace(/\*/g, "");
  }, [t, meta.sector_key]);

  const stats = meta.stats || {};
  const capLabel = `${stats.sent_this_month || 0} / ${stats.monthly_cap ?? "-"}`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-emerald-50/20 to-blue-50/20 pb-28">
      {/* Header */}
      <div className="px-4 pt-6 pb-4">
        <div className="backdrop-blur-xl bg-white/40 border border-white/20 rounded-2xl p-6 shadow-lg">
          <button
            onClick={() => onNavigate && onNavigate("settings")}
            className="flex items-center gap-2 text-zinc-700 hover:text-zinc-900 mb-4 transition-colors p-2 -ml-2 hover:bg-white/50 rounded-xl"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-bold">{t('settings.backToSettings')}</span>
          </button>
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-md shrink-0">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-black text-zinc-900">{t('settings.marketingAssistant.pageTitle')}</h2>
              <p className="text-sm text-zinc-600 mt-1 font-medium">{t('settings.marketingAssistant.pageSubtitle')}</p>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
        </div>
      ) : (
        <div className="px-4 max-w-2xl mx-auto space-y-5">

          {/* Master toggle */}
          <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-5 flex items-center justify-between">
            <div className="pr-4">
              <h3 className="text-base font-bold text-zinc-900">{t('settings.marketingAssistant.masterTitle')}</h3>
              <p className="text-sm text-zinc-500 mt-1">{t('settings.marketingAssistant.masterSubtitle')}</p>
            </div>
            <Switch checked={enabled} onCheckedChange={handleToggle} disabled={saving} className="scale-110" />
          </div>

          {enabled && (
            <>
              {/* slug uyarısı */}
              {!meta.slug && (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800 font-medium">{t('settings.marketingAssistant.noSlugWarning')}</p>
                </div>
              )}

              {/* İstatistik */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white rounded-2xl border border-zinc-200 p-4">
                  <p className="text-xs text-zinc-500 font-semibold uppercase tracking-wide">{t('settings.marketingAssistant.queued')}</p>
                  <p className="text-2xl font-black text-zinc-900 mt-1">{stats.queued || 0}</p>
                </div>
                <div className="bg-white rounded-2xl border border-zinc-200 p-4">
                  <p className="text-xs text-zinc-500 font-semibold uppercase tracking-wide">{t('settings.marketingAssistant.monthlyUsage')}</p>
                  <p className="text-2xl font-black text-zinc-900 mt-1">{capLabel}</p>
                </div>
              </div>

              {/* Canlı WhatsApp önizlemesi */}
              <div>
                <h3 className="px-1 mb-2 text-sm font-bold text-zinc-400 uppercase tracking-widest">
                  {t('settings.marketingAssistant.previewTitle')}
                </h3>
                <div className="rounded-2xl overflow-hidden shadow-md border border-zinc-200">
                  {/* WhatsApp header — gönderen daima PLANN resmi WhatsApp hesabıdır */}
                  <div className="bg-[#075E54] px-4 py-3 flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full overflow-hidden shrink-0 bg-white">
                      <img src="/plannlogo.png" alt="PLANN" className="w-full h-full object-cover" />
                    </div>
                    <div>
                      <p className="text-white font-semibold text-sm leading-none">PLANN</p>
                      <p className="text-white/70 text-[11px] mt-1">{t('settings.marketingAssistant.online')}</p>
                    </div>
                  </div>
                  {/* Chat zemini */}
                  <div className="bg-[#ECE5DD] p-4" style={{ backgroundImage: "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"20\" height=\"20\"><circle cx=\"2\" cy=\"2\" r=\"1\" fill=\"%23d9d2c8\"/></svg>')" }}>
                    <div className="bg-white rounded-xl rounded-tl-none shadow-sm p-3 max-w-[85%]">
                      {/* HEADER ({{1}} = işletme adı) — tüm şablonlarda sabit */}
                      <p className="text-[13.5px] font-bold text-zinc-900 mb-1">{meta.company_name}</p>
                      <p className="text-[13.5px] text-zinc-800 whitespace-pre-line leading-relaxed">{previewBody}</p>
                      <p className="text-[10px] text-zinc-400 text-right mt-1">10:24</p>
                    </div>
                    {/* URL butonu — WhatsApp'ta mesajın altında ayrı bir kart olarak görünür */}
                    <div className="bg-white rounded-xl shadow-sm mt-1 max-w-[85%] overflow-hidden">
                      <div className="flex items-center justify-center gap-2 text-[#00a5f4] text-sm font-semibold py-2.5">
                        <ExternalLink className="w-4 h-4" />
                        {t('settings.marketingAssistant.ctaButton')}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Hizmet süreleri akordiyon */}
              <div>
                <h3 className="px-1 mb-1 text-sm font-bold text-zinc-400 uppercase tracking-widest">
                  {t('settings.marketingAssistant.timingTitle')}
                </h3>
                <p className="px-1 mb-2 text-sm text-zinc-500">{t('settings.marketingAssistant.timingHelp')}</p>
                {services.length === 0 ? (
                  <div className="bg-white rounded-2xl border border-zinc-200 p-5 text-sm text-zinc-500">
                    {t('settings.marketingAssistant.noServices')}
                  </div>
                ) : (
                  <Accordion type="single" collapsible className="bg-white rounded-2xl border border-zinc-200 overflow-hidden divide-y divide-zinc-100">
                    <AccordionItem value="services" className="border-0">
                      <AccordionTrigger className="hover:no-underline px-5 py-4 [&>svg]:ml-2">
                        <div className="flex items-center gap-3 text-left">
                          <Clock className="w-5 h-5 text-emerald-600" />
                          <div>
                            <p className="text-sm font-bold text-zinc-900">{t('settings.marketingAssistant.timingAccordionTitle')}</p>
                            <p className="text-xs text-zinc-500 mt-0.5">{t('settings.marketingAssistant.timingAccordionSubtitle', { count: services.length })}</p>
                          </div>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-5 pb-4">
                        <div className="space-y-2">
                          {services.map((s) => (
                            <div key={s.id} className="flex items-center justify-between gap-3 py-2 border-b border-zinc-50 last:border-0">
                              <span className="text-sm font-medium text-zinc-800 flex-1 min-w-0 truncate">{s.name}</span>
                              <div className="flex items-center gap-2 shrink-0">
                                <Input
                                  type="number"
                                  min={1}
                                  max={365}
                                  inputMode="numeric"
                                  value={daysMap[s.id] ?? ""}
                                  onChange={(e) => handleDayChange(s.id, e.target.value)}
                                  className="w-20 h-11 text-center text-base font-bold"
                                />
                                <span className="text-sm text-zinc-500 w-8">{t('settings.marketingAssistant.daysShort')}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                )}
              </div>

              {/* Güvenlik kalkanları */}
              <div className="bg-white rounded-2xl border border-zinc-200 p-5 space-y-3">
                <p className="text-sm text-zinc-600 leading-relaxed">{t('settings.marketingAssistant.infoJit')}</p>
                <p className="text-sm text-zinc-600 leading-relaxed">{t('settings.marketingAssistant.infoBudget')}</p>
              </div>
            </>
          )}
        </div>
      )}

      {/* Sticky kaydet (gün değişiklikleri) */}
      {enabled && dirty && (
        <div className="fixed bottom-0 inset-x-0 p-4 bg-gradient-to-t from-white via-white to-transparent">
          <div className="max-w-2xl mx-auto">
            <Button
              onClick={handleSaveDays}
              disabled={saving}
              className="w-full h-12 bg-zinc-900 hover:bg-black text-white font-bold rounded-xl shadow-lg"
            >
              {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <><Save className="w-5 h-5 mr-2" />{t('settings.marketingAssistant.saveDays')}</>}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketingAssistant;
