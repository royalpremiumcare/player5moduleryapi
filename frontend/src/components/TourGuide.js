import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const tOr = (t, key, fallback) => {
  const translated = t(key);
  return translated === key ? fallback : translated;
};

const TourGuide = ({ run, steps, onFinish }) => {
  const { t } = useTranslation();
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState(null);

  const safeSteps = useMemo(() => (Array.isArray(steps) ? steps : []), [steps]);
  const currentStep = safeSteps[index];
  const isOpen = Boolean(run && currentStep);

  const locale = useMemo(
    () => ({
      back: tOr(t, 'common.back', 'Geri'),
      close: tOr(t, 'common.close', 'Kapat'),
      last: tOr(t, 'common.finish', 'Bitir'),
      next: tOr(t, 'common.next', 'İleri'),
      skip: tOr(t, 'common.skip', 'Turu Geç'),
    }),
    [t]
  );

  const handleFinish = () => {
    // Tur bittiğinde veya kullanıcı "Geç" dediğinde
    if (onFinish) onFinish();
  };

  useEffect(() => {
    if (!run) {
      setIndex(0);
      setTargetRect(null);
      return;
    }

    setIndex(0);
  }, [run]);

  useEffect(() => {
    if (!isOpen) {
      setTargetRect(null);
      return;
    }

    const computeRect = () => {
      const target = currentStep?.target;
      if (!target || target === 'body') {
        setTargetRect(null);
        return;
      }

      const el = document.querySelector(target);
      if (!el) {
        setTargetRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setTargetRect({
        top: r.top,
        left: r.left,
        width: r.width,
        height: r.height,
        bottom: r.bottom,
        right: r.right,
      });
    };

    computeRect();
    window.addEventListener('resize', computeRect);
    window.addEventListener('scroll', computeRect, true);
    return () => {
      window.removeEventListener('resize', computeRect);
      window.removeEventListener('scroll', computeRect, true);
    };
  }, [isOpen, currentStep]);

  const goNext = () => {
    const nextIndex = index + 1;
    if (nextIndex >= safeSteps.length) {
      handleFinish();
      return;
    }
    setIndex(nextIndex);
  };

  const goBack = () => setIndex((prev) => Math.max(0, prev - 1));
  const handleSkip = () => handleFinish();

  if (!isOpen) return null;

  const stepContent = currentStep?.content;
  const placement = currentStep?.placement;
  const showBack = index > 0;
  const isLast = index === safeSteps.length - 1;
  const showSkip = index === 0;

  const overlayColor = 'rgba(0, 0, 0, 0.6)';
  const zIndex = 10000;
  const highlightPadding = 8;

  const tooltipWidth = 360;
  const tooltipMargin = 12;
  const viewportW = typeof window !== 'undefined' ? window.innerWidth : 1024;
  const viewportH = typeof window !== 'undefined' ? window.innerHeight : 768;

  const baseTooltip = (() => {
    if (!targetRect || placement === 'center') {
      return {
        top: Math.round(viewportH / 2),
        left: Math.round(viewportW / 2),
        transform: 'translate(-50%, -50%)',
      };
    }

    const left = clamp(targetRect.left + targetRect.width / 2 - tooltipWidth / 2, tooltipMargin, viewportW - tooltipWidth - tooltipMargin);
    const preferTop = targetRect.top > viewportH / 2;
    const top = preferTop
      ? clamp(targetRect.top - tooltipMargin, tooltipMargin, viewportH - tooltipMargin)
      : clamp(targetRect.bottom + tooltipMargin, tooltipMargin, viewportH - tooltipMargin);

    return {
      top: Math.round(top),
      left: Math.round(left),
      transform: preferTop ? 'translateY(-100%)' : 'none',
    };
  })();

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex }}>
      <div style={{ position: 'absolute', inset: 0, background: overlayColor }} />

      {targetRect && (
        <div
          style={{
            position: 'absolute',
            top: Math.max(0, targetRect.top - highlightPadding),
            left: Math.max(0, targetRect.left - highlightPadding),
            width: Math.max(0, targetRect.width + highlightPadding * 2),
            height: Math.max(0, targetRect.height + highlightPadding * 2),
            borderRadius: 16,
            boxShadow: '0 0 0 2px rgba(255,255,255,0.65), 0 10px 40px rgba(0,0,0,0.25)',
            pointerEvents: 'none',
          }}
        />
      )}

      <div
        role="dialog"
        aria-modal="true"
        style={{
          position: 'absolute',
          width: tooltipWidth,
          maxWidth: 'calc(100vw - 24px)',
          background: '#fff',
          borderRadius: 16,
          padding: 20,
          boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
          color: '#333',
          ...baseTooltip,
        }}
      >
        <div style={{ padding: '10px 0' }}>{stepContent}</div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, gap: 10 }}>
          <div style={{ fontSize: 12, color: '#666' }}>{safeSteps.length > 0 ? `${index + 1}/${safeSteps.length}` : ''}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {showSkip && (
              <button type="button" onClick={handleSkip} style={{ background: 'transparent', border: 'none', color: '#ef4444', fontWeight: 500, cursor: 'pointer' }}>
                {locale.skip}
              </button>
            )}
            {showBack && (
              <button type="button" onClick={goBack} style={{ background: 'transparent', border: '1px solid #e5e7eb', color: '#666', padding: '10px 16px', borderRadius: 8, cursor: 'pointer' }}>
                {locale.back}
              </button>
            )}
            <button type="button" onClick={goNext} style={{ background: '#18181b', border: 'none', color: '#fff', padding: '10px 16px', borderRadius: 8, fontWeight: 'bold', outline: 'none', cursor: 'pointer' }}>
              {isLast ? locale.last : locale.next}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TourGuide;