import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { getStatus } from '../native/liveActivities';
import { subOf } from '../native/useLiveActivities';

const seenKey = (sub) => `la_consent_seen:${sub}`;

function wasSeen(sub) {
  try {
    return localStorage.getItem(seenKey(sub)) === '1';
  } catch (e) {
    return false;
  }
}

function markSeen(sub) {
  try {
    localStorage.setItem(seenKey(sub), '1');
  } catch (e) {
    /* storage unavailable: the sheet may show again next launch */
  }
}

/**
 * Explains iOS's Live Activity permission prompts. Opens by itself once per user after
 * login (supported plugin + org flag on); `manualOpen` reopens it from Settings.
 */
export default function LiveActivityConsentSheet({ token, orgFlagEnabled, manualOpen = false, onManualClose }) {
  const { t } = useTranslation();
  const [autoOpen, setAutoOpen] = useState(false);
  const sub = token ? subOf(token) : null;

  useEffect(() => {
    setAutoOpen(false);
    if (!sub || !orgFlagEnabled || wasSeen(sub)) return undefined;
    let cancelled = false;
    (async () => {
      const s = await getStatus();
      if (!cancelled && s?.supported === true) setAutoOpen(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [sub, orgFlagEnabled]);

  const close = () => {
    if (sub) markSeen(sub);
    setAutoOpen(false);
    if (onManualClose) onManualClose();
  };

  return (
    <Dialog open={autoOpen || manualOpen} onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('liveActivity.consent.title', 'Randevularınız kilit ekranında')}</DialogTitle>
          <DialogDescription>
            {t(
              'liveActivity.consent.body',
              'Sıradaki randevunuz kilit ekranında ve Dynamic Island\'da geri sayımla görünür. Saati gelince kendiliğinden "İşlemde" olur.'
            )}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          {t(
            'liveActivity.consent.note',
            'iOS izin isteyecek. İleride "izin vermeyi sürdürmek istiyor musunuz?" diye tekrar sorabilir. Sorarsa Her Zaman İzin Ver\'i seçin, yoksa randevular kilit ekranına gelmez.'
          )}
        </p>
        <DialogFooter className="gap-2">
          <button type="button" onClick={close} className="min-h-11 px-4 rounded-xl border border-input text-foreground">
            {t('liveActivity.consent.later', 'Şimdi değil')}
          </button>
          <button type="button" autoFocus onClick={close} className="min-h-11 px-4 rounded-xl bg-primary text-primary-foreground font-medium">
            {t('liveActivity.consent.continue', 'Devam')}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
