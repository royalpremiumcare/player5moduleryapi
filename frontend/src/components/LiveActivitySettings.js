import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Switch } from './ui/switch';
import { RadioGroup, RadioGroupItem } from './ui/radio-group';
import { Label } from './ui/label';
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
    return () => {
      cancelled = true;
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

  return (
    <section aria-labelledby="la-settings-title" className="mt-8">
      <h3 id="la-settings-title" className="px-5 mb-3 text-sm font-bold text-zinc-400 uppercase tracking-widest">
        {t('liveActivity.title', 'Canlı bildirimler')}
      </h3>
      <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden divide-y divide-zinc-100">
        {status.enabled === false && (
          <div role="alert" className="p-5 bg-amber-50 text-amber-900 text-sm">
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
          <div className="p-5">
            <p id="la-scope-label" className="text-base font-medium text-zinc-900 mb-3">
              {t('liveActivity.scope', 'Kimin randevuları gösterilsin?')}
            </p>
            <RadioGroup aria-labelledby="la-scope-label" value={prefs.scope} onValueChange={(v) => save({ scope: v })}>
              <div className="flex items-center gap-3 min-h-11">
                <RadioGroupItem value="own" id="la-scope-own" />
                <Label htmlFor="la-scope-own">{t('liveActivity.scopeOwn', 'Sadece benim randevularım')}</Label>
              </div>
              <div className="flex items-center gap-3 min-h-11">
                <RadioGroupItem value="all" id="la-scope-all" />
                <Label htmlFor="la-scope-all">{t('liveActivity.scopeAll', 'Tüm personelin randevuları')}</Label>
              </div>
            </RadioGroup>
          </div>
        )}

        {prefs.can_choose_slots && (
          <div className="p-5 flex items-center justify-between gap-4">
            <label htmlFor="la-slots" className="text-base font-medium text-zinc-900">
              {t('liveActivity.slots', 'Kilit ekranında kaç randevu')}
            </label>
            <select
              id="la-slots"
              value={prefs.slot_count}
              onChange={(e) => save({ slot_count: Number(e.target.value) })}
              className="min-h-11 rounded-xl border border-zinc-200 bg-white px-3 text-base"
            >
              {SLOT_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="p-5 flex items-center justify-between gap-4">
          <label htmlFor="la-alert" className="text-base font-medium text-zinc-900">
            {t('liveActivity.startAlert', 'Randevu başladığında sesli uyarı')}
          </label>
          <Switch
            id="la-alert"
            checked={!!prefs.start_alert}
            onCheckedChange={(v) => save({ start_alert: v })}
          />
        </div>

        <div className="p-5">
          <button type="button" onClick={() => onOpenConsent && onOpenConsent()} className="min-h-11 text-sm font-medium text-zinc-600 underline">
            {t('liveActivity.howItWorks', 'Nasıl çalışır?')}
          </button>
        </div>
      </div>
    </section>
  );
}
