import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, X } from 'lucide-react';

/**
 * AhaErrorScreen — WhatsApp gönderimi başarısız olduğunda gösterilen hata modalı.
 *
 * İki net CTA (plan 1.2.A2):
 *  - "Tekrar dene" (primary) → Aha endpoint'ini tekrar çağırır (state-aware:
 *    randevu zaten varsa sadece WA'yı yeniden gönderir).
 *  - "Klasik tura geç" (secondary) → /onboarding/aha-skip(reason="wa_failed")
 *    çağırır, terminal `aha_skipped` state'ine geçer, parent klasik turu açar.
 *
 * Soft nudge: 3+ retry'da "Sorun devam ediyor; klasik tura geçmek mantıklı
 * olabilir" yardım metni belirir.
 *
 * Props:
 *  - onRetry: () => Promise<void> | void — endpoint'i tetikleyen callback
 *  - onSkip: () => Promise<void> | void
 *  - onDismiss?: () => void — X ile kapatma (state değişmez); telemetri
 *  - retryCount?: number — parent'tan gelir; 3+'ta soft nudge gösterilir
 *  - retrying?: boolean — endpoint çalışıyor; butonlar disabled
 *  - lastError?: string — debug için kullanıcıya kısa not
 */
const AhaErrorScreen = ({
  onRetry,
  onSkip,
  onDismiss,
  retryCount = 0,
  retrying = false,
  lastError = null,
}) => {
  const { t } = useTranslation();
  const [skipping, setSkipping] = useState(false);

  const handleSkip = async () => {
    if (skipping) return;
    setSkipping(true);
    try {
      await onSkip?.();
    } finally {
      setSkipping(false);
    }
  };

  const showNudge = retryCount >= 3;
  const z = 9995;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="aha-error-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: z,
        background: 'rgba(0, 0, 0, 0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        style={{
          width: 'min(440px, 100%)',
          background: '#fff',
          borderRadius: 20,
          padding: 28,
          position: 'relative',
          boxShadow: '0 24px 80px rgba(0,0,0,0.4)',
        }}
      >
        {/* X kapatma — state değişmez, sonraki login'de tekrar çıkar */}
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t('common.close', 'Kapat')}
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            background: 'transparent',
            border: 'none',
            color: '#9ca3af',
            cursor: 'pointer',
            padding: 6,
            borderRadius: 6,
          }}
        >
          <X size={20} />
        </button>

        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            background: '#fef3c7',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
          }}
        >
          <AlertTriangle size={36} color="#f59e0b" strokeWidth={2.2} />
        </div>

        <h2
          id="aha-error-title"
          style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#111827' }}
        >
          {t('aha.error.title', 'WhatsApp mesajı gönderilemedi')}
        </h2>
        <p style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.6, color: '#4b5563' }}>
          {t(
            'aha.error.body',
            'Meta WhatsApp servisinde geçici bir aksaklık olabilir. Tekrar deneyebilir veya şimdilik klasik tura geçebilirsin.'
          )}
        </p>

        {showNudge && (
          <div
            role="note"
            style={{
              marginTop: 14,
              padding: 12,
              background: '#fffbeb',
              borderRadius: 10,
              fontSize: 13,
              color: '#92400e',
            }}
          >
            {t(
              'aha.error.nudge',
              'Sorun devam ediyor; klasik tura geçmek mantıklı olabilir.'
            )}
          </div>
        )}

        {lastError && process.env.NODE_ENV !== 'production' && (
          <div style={{ marginTop: 12, fontSize: 11, color: '#9ca3af', wordBreak: 'break-word' }}>
            <code>{String(lastError).slice(0, 200)}</code>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 22 }}>
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying || skipping}
            style={{
              width: '100%',
              background: retrying ? '#9ca3af' : '#111827',
              color: '#fff',
              fontWeight: 600,
              fontSize: 15,
              border: 'none',
              borderRadius: 12,
              padding: '14px 16px',
              cursor: retrying ? 'wait' : 'pointer',
              opacity: skipping ? 0.6 : 1,
            }}
          >
            {retrying
              ? t('aha.error.retrying', 'Tekrar deneniyor…')
              : t('aha.error.retry', 'Tekrar dene')}
          </button>
          <button
            type="button"
            onClick={handleSkip}
            disabled={retrying || skipping}
            style={{
              width: '100%',
              background: 'transparent',
              color: '#6b7280',
              fontWeight: 500,
              fontSize: 14,
              border: 'none',
              padding: '10px 16px',
              cursor: skipping ? 'wait' : 'pointer',
              textDecoration: 'underline',
            }}
          >
            {skipping
              ? t('aha.error.skipping', 'Klasik tura geçiliyor…')
              : t('aha.error.skip', 'Klasik tura geç')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AhaErrorScreen;
