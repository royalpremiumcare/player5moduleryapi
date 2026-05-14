import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles } from 'lucide-react';

/**
 * AhaSpotlight — yeni admin'in ilk randevuyu oluşturmak için tıklayacağı
 * `.tour-new-appointment` butonunu öne çıkaran karartılmış overlay.
 *
 * UI: minimal premium zinc paleti. Önceki mavi/mor/pembe gradient kaldırıldı,
 * kullanıcı tercihine göre zinc-900 / zinc-50 / beyaz tonlarıyla yeniden yazıldı.
 *
 * Davranış:
 *  - Mount olur olmaz 50/200/500ms gecikmelerle DOM hedefini arar.
 *  - 500ms içinde bulamazsa: `onFallback()` çağrılır, kendini unmount eder.
 *  - Hedef butonu nabız atar.
 *  - Buton tıklandığında veya overlay tıklamasında `onTrigger()` çağrılır.
 *
 * Props:
 *  - onTrigger, onFallback, onTargetMissing, onShown, loading
 */
const TARGET_SELECTOR = '.tour-new-appointment';
const SEARCH_DELAYS_MS = [50, 200, 500];

const AhaSpotlight = ({ onTrigger, onFallback, onTargetMissing, onShown, loading = false }) => {
  const { t } = useTranslation();
  const [targetRect, setTargetRect] = useState(null);
  const [searchExhausted, setSearchExhausted] = useState(false);
  const onTriggerRef = useRef(onTrigger);
  const onFallbackRef = useRef(onFallback);
  const onTargetMissingRef = useRef(onTargetMissing);
  const onShownRef = useRef(onShown);
  const shownEmittedRef = useRef(false);

  useEffect(() => { onTriggerRef.current = onTrigger; }, [onTrigger]);
  useEffect(() => { onFallbackRef.current = onFallback; }, [onFallback]);
  useEffect(() => { onTargetMissingRef.current = onTargetMissing; }, [onTargetMissing]);
  useEffect(() => { onShownRef.current = onShown; }, [onShown]);

  // DOM hedef arama
  useEffect(() => {
    let cancelled = false;
    const timers = [];

    const findOnce = () => {
      if (cancelled) return null;
      const el = document.querySelector(TARGET_SELECTOR);
      if (el) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          setTargetRect({
            top: r.top,
            left: r.left,
            width: r.width,
            height: r.height,
            bottom: r.bottom,
            right: r.right,
          });
          if (!shownEmittedRef.current) {
            shownEmittedRef.current = true;
            try { onShownRef.current?.(); } catch (_) {}
          }
          return el;
        }
      }
      return null;
    };

    SEARCH_DELAYS_MS.forEach((delay, idx) => {
      const id = setTimeout(() => {
        const found = findOnce();
        if (!found && idx === SEARCH_DELAYS_MS.length - 1) {
          if (cancelled) return;
          setSearchExhausted(true);
          try { onTargetMissingRef.current?.(); } catch (_) {}
          try { onFallbackRef.current?.(); } catch (_) {}
        }
      }, delay);
      timers.push(id);
    });

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, []);

  // Resize/scroll'da hedef konumunu yenile
  useEffect(() => {
    if (!targetRect) return undefined;
    const recompute = () => {
      const el = document.querySelector(TARGET_SELECTOR);
      if (!el) return;
      const r = el.getBoundingClientRect();
      setTargetRect({
        top: r.top, left: r.left, width: r.width, height: r.height,
        bottom: r.bottom, right: r.right,
      });
    };
    window.addEventListener('resize', recompute);
    window.addEventListener('scroll', recompute, true);
    return () => {
      window.removeEventListener('resize', recompute);
      window.removeEventListener('scroll', recompute, true);
    };
  }, [targetRect]);

  const handleTargetClick = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (loading) return;
    try { onTriggerRef.current?.(); } catch (_) {}
  }, [loading]);

  if (searchExhausted || !targetRect) return null;

  // Hole boyutları — DAİRE/yuvarlak. Hedef + butonu w-14 h-14 yuvarlak.
  // Diameter = max(width,height) + padding*2 → tam dairesel hole, hem buton
  // tam ortalanır hem de etrafındaki bottom-nav bar kararma içinde kalır
  // (rectangle carve-out tekniği nav bar üstündeki butonun altında beyaz
  // dikdörtgen bırakıyordu — Sorun 3).
  const padding = 10;
  const diameter = Math.max(targetRect.width, targetRect.height) + padding * 2;
  const centerX = targetRect.left + targetRect.width / 2;
  const centerY = targetRect.top + targetRect.height / 2;
  const holeLeft = centerX - diameter / 2;
  const holeTop = centerY - diameter / 2;
  const holeWidth = diameter;
  const holeHeight = diameter;

  // Premium minimal: koyu zinc karartma
  const overlayBg = 'rgba(9, 9, 11, 0.78)';
  const z = 9990;

  // Tooltip pozisyonu
  const viewportH = typeof window !== 'undefined' ? window.innerHeight : 768;
  const viewportW = typeof window !== 'undefined' ? window.innerWidth : 360;
  const tooltipWidth = Math.min(360, viewportW - 32);
  const preferTop = targetRect.top > viewportH / 2;
  const tooltipMargin = 16;
  const tooltipTop = preferTop
    ? targetRect.top - tooltipMargin
    : targetRect.bottom + tooltipMargin;
  const tooltipLeft = Math.max(
    16,
    Math.min(targetRect.left + targetRect.width / 2 - tooltipWidth / 2, viewportW - tooltipWidth - 16)
  );

  return (
    <>
      {/* Tek dairesel hole + dev box-shadow ile dış kararma. Bu yöntem rectangle
          carve-out'a göre daha temiz: hole şekli tam dairesel olduğu için
          bottom-nav bar gibi alta taşan elementler hole DIŞINDA kalıp
          kararır — buton arkasında beyaz dikdörtgen oluşmaz. */}
      <div style={{ position: 'fixed', inset: 0, zIndex: z, pointerEvents: 'none' }}>
        <div
          style={{
            position: 'absolute',
            top: holeTop,
            left: holeLeft,
            width: holeWidth,
            height: holeHeight,
            borderRadius: '50%',
            boxShadow: `0 0 0 9999px ${overlayBg}`,
            pointerEvents: 'auto',
          }}
        />

        {/* Spotlight ring + nabız — beyaz halo, dairenin tam üstünde */}
        <div
          style={{
            position: 'absolute',
            top: holeTop,
            left: holeLeft,
            width: holeWidth,
            height: holeHeight,
            borderRadius: '50%',
            boxShadow:
              '0 0 0 2px rgba(255, 255, 255, 0.95), 0 0 0 7px rgba(255, 255, 255, 0.25), 0 0 56px rgba(255, 255, 255, 0.4)',
            animation: 'aha-pulse 1.8s ease-in-out infinite',
            pointerEvents: 'none',
          }}
        />

        {/* Hedef tıklama proxy'si — buton ile aynı boyutta, en üstte */}
        <button
          type="button"
          aria-label={t('aha.spotlight.tapTarget', 'İlk randevunu oluştur')}
          onClick={handleTargetClick}
          disabled={loading}
          style={{
            position: 'absolute',
            top: targetRect.top,
            left: targetRect.left,
            width: targetRect.width,
            height: targetRect.height,
            borderRadius: 9999,
            background: 'transparent',
            border: 'none',
            cursor: loading ? 'wait' : 'pointer',
            pointerEvents: 'auto',
          }}
        />
      </div>

      {/* Tooltip — beyaz kart, ince zinc kenarlık, premium minimal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="aha-spotlight-title"
        style={{
          position: 'fixed',
          top: Math.round(tooltipTop),
          left: Math.round(tooltipLeft),
          transform: preferTop ? 'translateY(-100%)' : 'none',
          width: tooltipWidth,
          background: '#ffffff',
          borderRadius: 16,
          padding: 0,
          boxShadow: '0 24px 80px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.06)',
          zIndex: z + 1,
          color: '#09090b',
          overflow: 'hidden',
          animation: 'aha-tooltip-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
        }}
      >
        <div style={{ padding: '20px 22px 22px' }}>
          {/* Pill badge — zinc tonu */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 10px',
              borderRadius: 999,
              background: '#f4f4f5',
              color: '#09090b',
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
              marginBottom: 12,
            }}
          >
            <Sparkles size={12} strokeWidth={2.5} />
            {t('aha.spotlight.badge', 'İlk adım')}
          </div>

          <h2
            id="aha-spotlight-title"
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 800,
              color: '#09090b',
              letterSpacing: -0.4,
              lineHeight: 1.25,
            }}
          >
            {t('aha.spotlight.title', 'İlk randevunu birlikte oluşturalım')}
          </h2>
          <p
            style={{
              margin: '10px 0 0',
              fontSize: 14,
              lineHeight: 1.6,
              color: '#52525b',
            }}
          >
            {loading
              ? t('aha.spotlight.loading', 'Mesajın hazırlanıyor — birkaç saniye…')
              : t(
                  'aha.spotlight.tooltip',
                  'Vurgulanan + butonuna dokun. Telefonuna saniyeler içinde bir doğrulama mesajı düşecek — müşterilerinin alacağı onayın aynısı.'
                )}
          </p>

          {loading && (
            <div
              aria-hidden="true"
              style={{
                marginTop: 16,
                height: 3,
                borderRadius: 999,
                background: '#f4f4f5',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: '40%',
                  background: '#09090b',
                  borderRadius: 999,
                  animation: 'aha-loading-bar 1.2s ease-in-out infinite',
                }}
              />
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes aha-pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.06); opacity: 0.85; }
        }
        @keyframes aha-loading-bar {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
        @keyframes aha-tooltip-pop {
          0% { transform: ${preferTop ? 'translateY(-100%) scale(0.95)' : 'scale(0.95)'}; opacity: 0; }
          100% { transform: ${preferTop ? 'translateY(-100%) scale(1)' : 'scale(1)'}; opacity: 1; }
        }
      `}</style>
    </>
  );
};

export default AhaSpotlight;
