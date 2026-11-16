import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

const asList = (value) => (Array.isArray(value) ? value : []);

/** "a **b** c" -> ['a ', <strong>b</strong>, ' c'] (only the bold markers; no HTML). */
function withBold(line) {
  return line.split('**').map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}

/**
 * Explains Live Activities and iOS's two permission prompts. Presentational: the App decides
 * when it is open. Dismissing it (Escape, tapping outside, the close button) counts as onLater.
 */
export default function LiveActivityConsentSheet({ open, onAllow, onLater }) {
  const { t } = useTranslation();
  const bullets = asList(t('liveActivity.consent.bullets', { returnObjects: true }));
  const steps = asList(t('liveActivity.consent.steps', { returnObjects: true }));

  return (
    <Dialog open={!!open} onOpenChange={(next) => !next && onLater && onLater()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('liveActivity.consent.title', 'Randevularınız kilit ekranında')}</DialogTitle>
          <DialogDescription>{t('liveActivity.consent.intro')}</DialogDescription>
        </DialogHeader>
        <ul className="list-disc ps-5 space-y-1 text-sm text-foreground">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
        <p className="text-sm text-muted-foreground">{t('liveActivity.consent.outro')}</p>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{t('liveActivity.consent.permissionsTitle')}</p>
          <ol className="list-decimal ps-5 space-y-1 text-sm text-foreground">
            {steps.map((s) => (
              <li key={s}>{withBold(s)}</li>
            ))}
          </ol>
        </div>
        <DialogFooter className="gap-2">
          <button type="button" onClick={onLater} className="min-h-11 px-4 rounded-xl border border-input text-foreground">
            {t('liveActivity.consent.later', 'Şimdi değil')}
          </button>
          <button type="button" autoFocus onClick={onAllow} className="min-h-11 px-4 rounded-xl bg-primary text-primary-foreground font-medium">
            {t('liveActivity.consent.allow', 'İzin ver')}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
