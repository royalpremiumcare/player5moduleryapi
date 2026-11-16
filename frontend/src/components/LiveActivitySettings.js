import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Check, Info, Layers, Users, Volume2 } from 'lucide-react';
import { Switch } from './ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { SettingItem, SectionTitle } from './settings/SettingRows';
import api from '../api/api';
import { getStatus, openSettings } from '../native/liveActivities';

const SLOT_OPTIONS = [1, 2, 3, 4, 5];

/**
 * "Canlı bildirimler" section of Settings. Renders nothing unless the native plugin
 * reports supported === true and the server says the org's Live Activities flag is on.
 * Which controls appear is decided by the server (can_choose_scope / can_choose_slots).
 */
export default function LiveActivitySettings({ onOpenConsent }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [prefs, setPrefs] = useState(null);
  const [sheet, setSheet] = useState(null); // 'scope' | 'slots' | null

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await getStatus();
      if (cancelled || s?.supported !== true) return;
      try {
        const res = await api.get('/live-activities/preferences');
        if (cancelled) return;
        setStatus(s);
        setPrefs(res.data);
      } catch (e) {
        /* leave the section hidden */
      }
    })();
    // Back from iOS Settings: re-read the status so the "disabled" banner is current.
    const onVisible = async () => {
      if (document.visibilityState !== 'visible') return;
      const s = await getStatus();
      if (!cancelled && s?.supported === true) setStatus(s);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  if (status?.supported !== true || prefs?.enabled !== true) return null;

  const save = async (patch) => {
    try {
      const res = await api.put('/live-activities/preferences', patch);
      setPrefs((p) => ({ ...p, ...res.data }));
      toast.success(t('liveActivity.saved', 'Kaydedildi'));
    } catch (e) {
      toast.error(t('liveActivity.saveError', 'Kaydedilemedi, tekrar deneyin'));
    }
  };

  const scopeLabel = (v) =>
    v === 'own'
      ? t('liveActivity.scopeOwn', 'Sadece benim randevularım')
      : t('liveActivity.scopeAll', 'Tüm personelin randevuları');

  const sheetConfig =
    sheet === 'scope'
      ? {
          title: t('liveActivity.scope', 'Kimin randevuları gösterilsin?'),
          current: prefs.scope,
          options: [
            { value: 'own', label: scopeLabel('own') },
            { value: 'all', label: scopeLabel('all') },
          ],
          patch: (v) => ({ scope: v }),
        }
      : sheet === 'slots'
        ? {
            title: t('liveActivity.slots', 'Kilit ekranında kaç randevu'),
            current: prefs.slot_count,
            options: SLOT_OPTIONS.map((n) => ({ value: n, label: String(n) })),
            patch: (v) => ({ slot_count: v }),
          }
        : null;

  const choose = (value) => {
    const patch = sheetConfig.patch(value);
    setSheet(null);
    if (value !== sheetConfig.current) save(patch);
  };

  return (
    <section aria-label={t('liveActivity.title', 'Canlı bildirimler')}>
      <SectionTitle title={t('liveActivity.title', 'Canlı bildirimler')} />
      <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
        {status.enabled === false && (
          <div role="alert" className="p-5 bg-amber-50 text-amber-900 text-sm border-b border-zinc-100">
            <p>
              {t(
                'liveActivity.disabledBanner',
                'Canlı Etkinlikler iOS ayarlarında kapalı. Randevular kilit ekranına gelmez.'
              )}
            </p>
            <button
              type="button"
              onClick={() => openSettings()}
              className="mt-3 min-h-11 px-4 rounded-xl bg-amber-900 text-white font-medium"
            >
              {t('liveActivity.openIosSettings', 'iOS Ayarlarını Aç')}
            </button>
          </div>
        )}

        {prefs.can_choose_scope && (
          <SettingItem
            icon={Users}
            title={t('liveActivity.scope', 'Kimin randevuları gösterilsin?')}
            subtitle={scopeLabel(prefs.scope)}
            onClick={() => setSheet('scope')}
          />
        )}

        {prefs.can_choose_slots && prefs.scope === 'all' && (
          <SettingItem
            icon={Layers}
            title={t('liveActivity.slots', 'Kilit ekranında kaç randevu')}
            subtitle={String(prefs.slot_count)}
            onClick={() => setSheet('slots')}
          />
        )}

        <SettingItem
          icon={Volume2}
          title={t('liveActivity.startAlert', 'Randevu başladığında sesli uyarı')}
          rightElement={
            <Switch
              aria-label={t('liveActivity.startAlert', 'Randevu başladığında sesli uyarı')}
              checked={!!prefs.start_alert}
              onCheckedChange={(v) => save({ start_alert: v })}
              className="scale-110"
            />
          }
        />

        <SettingItem
          icon={Info}
          title={t('liveActivity.howItWorks', 'Nasıl çalışır?')}
          onClick={() => onOpenConsent && onOpenConsent()}
        />
      </div>

      <Dialog open={sheetConfig !== null} onOpenChange={(open) => !open && setSheet(null)}>
        {sheetConfig && (
          <DialogContent aria-describedby={undefined}>
            <DialogHeader>
              <DialogTitle>{sheetConfig.title}</DialogTitle>
            </DialogHeader>
            <div className="-mx-2">
              {sheetConfig.options.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  data-option={o.value}
                  onClick={() => choose(o.value)}
                  className="flex w-full min-h-11 items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-base text-zinc-900 active:bg-zinc-50"
                >
                  <span>{o.label}</span>
                  {o.value === sheetConfig.current && (
                    <Check className="w-5 h-5 text-zinc-900" strokeWidth={2} aria-hidden="true" />
                  )}
                </button>
              ))}
            </div>
          </DialogContent>
        )}
      </Dialog>
    </section>
  );
}
