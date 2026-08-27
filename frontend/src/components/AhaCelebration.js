import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';

/**
 * AhaCelebration — WA mesajı başarıyla gönderildiğinde gösterilen kutlama modalı.
 *
 * UI: minimal premium zinc paleti. Önceki mavi/mor gradient kaldırıldı;
 * tek vurgu rengi olarak emerald (success) korundu, arayüz beyaz/zinc.
 *
 * Davranış:
 *  - Mount olunca confetti patlar (lazy import canvas-confetti).
 *  - autoAdvanceMs (default 15000) süresi geri sayım progress bar'ı ile gösterilir.
 *  - "Devam et" butonu auto-advance'i bekletmeden hemen geçirir.
 *
 * Props:
 *  - onContinue, onDismiss, autoAdvanceMs
 */
const AhaCelebration = ({ onContinue, onDismiss, autoAdvanceMs = 15000 }) => {
  const { t } = useTranslation();
  const [closing, setClosing] = useState(false);
  const [progress, setProgress] = useState(0);
  const onContinueRef = useRef(onContinue);
  const onDismissRef = useRef(onDismiss);

  useEffect(() => { onContinueRef.current = onContinue; }, [onContinue]);
  useEffect(() => { onDismissRef.current = onDismiss; }, [onDismiss]);

  // Confetti — zinc + emerald palet (önceki çok renkli karışım kaldırıldı)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = await import('canvas-confetti');
        if (cancelled) return;
        const confetti = mod.default || mod;
        const fire = (particleRatio, opts) => {
          confetti({
            origin: { y: 0.65 },
            colors: ['#10b981', '#059669', '#a1a1aa', '#ffffff', '#09090b'],
            ...opts,
            particleCount: Math.floor(220 * particleRatio),
          });
        };
        fire(0.25, { spread: 26, startVelocity: 55 });
        fire(0.2, { spread: 60 });
        fire(0.35, { spread: 100, decay: 0.91, scalar: 0.85 });
        fire(0.1, { spread: 120, startVelocity: 25, decay: 0.92, scalar: 1.2 });
        fire(0.1, { spread: 120, startVelocity: 45 });
        setTimeout(() => {
          if (cancelled) return;
          fire(0.15, { spread: 90, startVelocity: 35, scalar: 0.9 });
        }, 1200);
      } catch (_) {
        // canvas-confetti yoksa görsel kutlama olmaz; akış devam eder
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Auto-advance + progress bar
  useEffect(() => {
    if (!autoAdvanceMs) return undefined;
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const elapsed = now - start;
      const ratio = Math.min(1, elapsed / autoAdvanceMs);
      setProgress(ratio);
      if (ratio >= 1) {
        if (!closing) {
          setClosing(true);
          try { onDismissRef.current?.({ autoAdvanced: true }); } catch (_) {}
          try { onContinueRef.current?.(); } catch (_) {}
        }
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => raf && cancelAnimationFrame(raf);
  }, [autoAdvanceMs, closing]);

  const handleContinue = () => {
    if (closing) return;
    setClosing(true);
    try { onDismissRef.current?.({ autoAdvanced: false }); } catch (_) {}
    try { onContinueRef.current?.(); } catch (_) {}
  };

  const z = 9995;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="aha-celebration-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: z,
        background: 'rgba(9, 9, 11, 0.7)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        style={{
          width: 'min(420px, 100%)',
          // Gövde metni açıklayıcı olduğu için uzun; kısa ekranlarda (SE gibi)
          // kart viewport'u aşabiliyor. overflow:hidden yerine dikey scroll →
          // metin kırpılmaz. overflow shorthand'i overflowY'yi ezdiği için
          // yatay taşıma ayrı veriliyor.
          maxHeight: 'calc(100vh - 40px)',
          overflowY: 'auto',
          overflowX: 'hidden',
          borderRadius: 22,
          padding: 0,
          textAlign: 'center',
          background: '#ffffff',
          boxShadow: '0 32px 96px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(0, 0, 0, 0.05)',
          animation: 'aha-celebration-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
          position: 'relative',
        }}
      >
        <div style={{ padding: '34px 28px 26px' }}>
          {/* Animated success badge — emerald accent */}
          <div
            style={{
              position: 'relative',
              width: 88,
              height: 88,
              margin: '0 auto 20px',
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                background: 'radial-gradient(circle at center, rgba(16,185,129,0.18) 0%, rgba(16,185,129,0) 70%)',
                animation: 'aha-halo 2.4s ease-out infinite',
              }}
              aria-hidden="true"
            />
            <div
              style={{
                position: 'absolute',
                inset: 8,
                borderRadius: '50%',
                background: '#10b981',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 12px 28px rgba(16,185,129,0.32)',
                animation: 'aha-badge-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s both',
              }}
            >
              <Check size={40} color="#ffffff" strokeWidth={3} />
            </div>
          </div>

          {/* Delivered badge — zinc minimal */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 12px',
              borderRadius: 999,
              background: '#f4f4f5',
              color: '#09090b',
              fontSize: 11,
              fontWeight: 700,
              marginBottom: 14,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
            }}
          >
            {t('aha.celebration.deliveredBadge', 'Deneme Tamamlandı')}
          </div>

          <h2
            id="aha-celebration-title"
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 800,
              color: '#09090b',
              letterSpacing: -0.4,
              lineHeight: 1.25,
            }}
          >
            {t('aha.celebration.title', 'Telefonuna gelen mesajı gördün mü?')}
          </h2>
          <p
            style={{
              margin: '10px 4px 0',
              fontSize: 14.5,
              lineHeight: 1.6,
              color: '#52525b',
            }}
          >
            {t(
              'aha.celebration.body',
              'Bu bir örnek randevuydu ve müşteri olarak sen seçildiğin için mesaj doğrudan sana geldi. Gerçek randevularda aynı onay mesajı otomatik olarak müşterinin telefonuna gider ve senin hiçbir şey yapmana gerek kalmaz. Takviminde oluşan bu örnek randevuyu dilediğin zaman silebilirsin.'
            )}
          </p>

          <button
            type="button"
            onClick={handleContinue}
            style={{
              marginTop: 24,
              width: '100%',
              background: '#09090b',
              color: '#fff',
              fontWeight: 700,
              fontSize: 15,
              border: 'none',
              borderRadius: 12,
              padding: '15px 16px',
              cursor: 'pointer',
              boxShadow: '0 8px 22px rgba(0, 0, 0, 0.18)',
              transition: 'transform 0.15s ease',
              letterSpacing: 0.1,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            {t('aha.celebration.cta', 'Turu Başlat')}
          </button>

          {/* Auto-advance progress bar — zinc minimal */}
          <div style={{ marginTop: 16 }}>
            <div
              aria-hidden="true"
              style={{
                height: 3,
                borderRadius: 999,
                background: '#f4f4f5',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progress * 100}%`,
                  background: '#09090b',
                  borderRadius: 999,
                  transition: 'width 80ms linear',
                }}
              />
            </div>
            <p
              style={{
                margin: '10px 0 0',
                fontSize: 12,
                color: '#a1a1aa',
                fontWeight: 500,
              }}
            >
              {t('aha.celebration.autoHint', 'Tur birkaç saniye içinde otomatik olarak başlayacak...')}
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes aha-celebration-pop {
          0% { transform: scale(0.92) translateY(16px); opacity: 0; }
          100% { transform: scale(1) translateY(0); opacity: 1; }
        }
        @keyframes aha-badge-pop {
          0% { transform: scale(0.4); opacity: 0; }
          60% { transform: scale(1.1); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes aha-halo {
          0%, 100% { transform: scale(1); opacity: 0.7; }
          50% { transform: scale(1.15); opacity: 0.3; }
        }
      `}</style>
    </div>
  );
};

export default AhaCelebration;
