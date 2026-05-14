import React, { useEffect, useLayoutEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Edit, X, Trash2 } from 'lucide-react';

/**
 * SwipeableAppointmentCard — WhatsApp tarzı snap-swipe etkileşimi.
 *
 * Davranış (plan §2.2):
 *  - Sağa swipe → 100px reveal: Düzenle (mavi) butonu açılır.
 *  - Sola swipe → 160px reveal: İptal (turuncu, 80px) + Sil (kırmızı, 80px).
 *  - Threshold: |dx| > 50px VEYA |velocity| > 400 px/s.
 *  - dragConstraints {-160, +100} → "tamamen kaydır → sil" fiziksel olarak imkânsız.
 *  - Eşik geçişinde **bir kez** haptic; drag boyunca spam yok.
 *  - Tap-to-close: parent `openCardId` lift ederek başka kart açıldığında bu kapanır.
 *  - Click vs drag: hareket < 5px → onTap; aksi halde click yutulur.
 *  - Desktop fallback: pointer:fine → swipe disabled, sadece children + dropdown.
 *
 * Props:
 *  - children: ReactNode (mevcut kart içeriği)
 *  - onEdit, onCancel, onDelete: callback'ler — buton tıklamasıyla tetiklenir
 *  - onTap?: () => void — drag yokken card click (note expand vb.)
 *  - disabled?: boolean — bitmiş/iptal randevular için swipe kapalı
 *  - isOpen?: 'left' | 'right' | null — controlled mode (parent yönetir)
 *  - onOpenChange?: (state) => void — controlled mode için
 */

const SWIPE_THRESHOLD_PX = 64; // commit için minimum görsel offset
const VELOCITY_THRESHOLD_PX_S = 600; // hızlı flick eşiği
const TAP_MAX_DRAG_PX = 8;
const INTENT_DECISION_PX = 18; // yatay niyet için minimum dx (kazara açılmayı önler)
const HORIZONTAL_DOMINANCE = 1.5; // |dx| > |dy| * 1.5 olmalı (daha kararlı yön)
const REVEAL_LEFT = 100; // Edit
const REVEAL_RIGHT = 160; // Cancel + Delete
const SPRING_DURATION_MS = 240;

// Desktop'ta swipe kapalı (sadece dropdown menü kullanılır)
function isCoarsePointerDevice() {
  if (typeof window === 'undefined' || !window.matchMedia) return true;
  return window.matchMedia('(pointer: coarse)').matches;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

async function triggerHaptic() {
  // @capacitor/haptics web'de no-op döner; native'de hafif titreşim
  try {
    const mod = await import('@capacitor/haptics');
    const Haptics = mod.Haptics || mod.default?.Haptics || mod.default;
    const ImpactStyle = mod.ImpactStyle || mod.default?.ImpactStyle;
    if (Haptics?.impact && ImpactStyle?.Light) {
      Haptics.impact({ style: ImpactStyle.Light });
    }
  } catch (_) {
    // Paket yok / web platformu — sessizce yut
  }
}

const SwipeableAppointmentCard = ({
  children,
  onEdit,
  onCancel,
  onDelete,
  onTap,
  disabled = false,
  isOpen = null,
  onOpenChange = null,
}) => {
  const { t } = useTranslation();
  const isControlled = onOpenChange !== null;
  const [internalOpen, setInternalOpen] = useState(null);
  const openState = isControlled ? isOpen : internalOpen;

  // Stale closure'ı önlemek için onOpenChange'i ref'le sarıyoruz.
  // Aksi halde useCallback dep listesinde olmadığı için snapTo eski referansı çağırır.
  const onOpenChangeRef = useRef(onOpenChange);
  useEffect(() => { onOpenChangeRef.current = onOpenChange; }, [onOpenChange]);

  const setOpenState = useCallback((next) => {
    if (isControlled) {
      onOpenChangeRef.current?.(next);
    } else {
      setInternalOpen(next);
    }
  }, [isControlled]);

  // ===== REF-BASED RENDER (WhatsApp seviye akıcılık) =====
  // Drag sırasında setState YAPMIYORUZ. DOM'u doğrudan ref üzerinden
  // güncelliyoruz — React reconciliation maliyeti rAF döngüsünden çıkıyor.
  const cardInnerRef = useRef(null);
  const leftPanelRef = useRef(null);
  const rightPanelRef = useRef(null);
  const xRef = useRef(0); // mevcut görsel offset

  const trackingRef = useRef({
    pointerId: null,
    startX: 0,
    startY: 0,
    startTime: 0,
    lastX: 0,
    lastTime: 0,
    velocity: 0,
    movedX: 0,
    crossedThreshold: false,
    intent: null, // 'horizontal' | 'vertical' | null
    baseOffset: 0, // pointerDown anındaki GERÇEK DOM offset (xRef.current)
    startedOpenState: null, // pointerDown anındaki openState semantic değeri
  });
  const animCancelRef = useRef(null);
  const isCoarse = useRef(isCoarsePointerDevice()).current;

  // DOM'u doğrudan güncelle — render trigger etmez
  const applyTransform = useCallback((val) => {
    xRef.current = val;
    const card = cardInnerRef.current;
    if (card) {
      card.style.transform = `translate3d(${val}px, 0, 0)`;
    }
    const leftVisible = val > 0.5;
    const rightVisible = val < -0.5;
    const left = leftPanelRef.current;
    if (left) {
      left.style.opacity = leftVisible ? '1' : '0';
      left.style.visibility = leftVisible ? 'visible' : 'hidden';
    }
    const right = rightPanelRef.current;
    if (right) {
      right.style.opacity = rightVisible ? '1' : '0';
      right.style.visibility = rightVisible ? 'visible' : 'hidden';
    }
  }, []);

  // rAF tabanlı snap animasyonu — applyTransform ile (setState yok)
  const animateTo = useCallback((toX, durationMs, onDone) => {
    if (animCancelRef.current) animCancelRef.current();
    const fromX = xRef.current;
    const delta = toX - fromX;
    if (Math.abs(delta) < 0.5) {
      applyTransform(toX);
      onDone?.();
      return;
    }
    const start = performance.now();
    let raf;
    const step = (now) => {
      const elapsed = now - start;
      if (elapsed >= durationMs) {
        applyTransform(toX);
        animCancelRef.current = null;
        onDone?.();
        return;
      }
      const t = elapsed / durationMs;
      const eased = easeOutCubic(t);
      applyTransform(fromX + delta * eased);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    animCancelRef.current = () => {
      if (raf) cancelAnimationFrame(raf);
      animCancelRef.current = null;
    };
  }, [applyTransform]);

  const snapTo = useCallback((target, openLabel) => {
    animateTo(target, SPRING_DURATION_MS);
    setOpenState(openLabel);
  }, [animateTo, setOpenState]);

  // Anlık (animasyonsuz) sıfırlama — scroll/outside-pointerdown gibi
  // perf-kritik path'ler için. setState YAPMADAN önce DOM'u hemen sıfırlar
  // ve cancelAnimationFrame ile rAF zincirini durdurur.
  const closeInstant = useCallback(() => {
    if (animCancelRef.current) animCancelRef.current();
    applyTransform(0);
    setOpenState(null);
  }, [applyTransform, setOpenState]);

  // Initial mount: doğru başlangıç pozisyonunu uygula (controlled mode için)
  useLayoutEffect(() => {
    const initial = openState === 'left' ? REVEAL_LEFT : openState === 'right' ? -REVEAL_RIGHT : 0;
    applyTransform(initial);
    // sadece mount'ta — sonraki openState değişiklikleri aşağıdaki effect ile animasyonlu
    // eslint-disable-next-line
  }, []);

  // Controlled openState değişimi → animasyonla snap
  useEffect(() => {
    const target = openState === 'left' ? REVEAL_LEFT : openState === 'right' ? -REVEAL_RIGHT : 0;
    if (Math.abs(xRef.current - target) < 0.5) return;
    // pointer aktifken animation tetikleme — kullanıcı drag ediyor
    if (trackingRef.current.pointerId !== null) return;
    animateTo(target, SPRING_DURATION_MS);
  }, [openState, animateTo]);

  // Sayfa scroll edilince ya da kart dışına dokunulunca otomatik kapansın
  useEffect(() => {
    if (openState === null) return undefined;
    let triggered = false;
    const closeIfIdle = () => {
      // Drag aktifken yok say
      if (trackingRef.current.pointerId !== null) return;
      // Idempotent: scroll burst sırasında bir kez snap yeterli — her event'te
      // yeni rAF animasyonu başlatmak ana iş parçacığını kasar
      if (triggered) return;
      triggered = true;
      // Animasyonsuz instant close → scroll perf'ini koru, kasma yok
      closeInstant();
    };
    const onOutsidePointerDown = (e) => {
      if (trackingRef.current.pointerId !== null) return;
      const target = e.target;
      if (cardInnerRef.current?.contains(target)) return;
      if (leftPanelRef.current?.contains(target)) return;
      if (rightPanelRef.current?.contains(target)) return;
      if (triggered) return;
      triggered = true;
      closeInstant();
    };

    // capture: true → herhangi bir scroll container'dan da yakala
    document.addEventListener('scroll', closeIfIdle, { passive: true, capture: true });
    window.addEventListener('scroll', closeIfIdle, { passive: true });
    window.addEventListener('wheel', closeIfIdle, { passive: true });
    document.addEventListener('pointerdown', onOutsidePointerDown, true);
    return () => {
      document.removeEventListener('scroll', closeIfIdle, { capture: true });
      window.removeEventListener('scroll', closeIfIdle);
      window.removeEventListener('wheel', closeIfIdle);
      document.removeEventListener('pointerdown', onOutsidePointerDown, true);
    };
  }, [openState, closeInstant]);

  const handlePointerDown = (e) => {
    if (disabled || !isCoarse) return;
    if (e.pointerType === 'mouse') return; // mouse'da swipe kapalı
    const tracking = trackingRef.current;
    tracking.pointerId = e.pointerId;
    tracking.startX = e.clientX;
    tracking.startY = e.clientY;
    tracking.startTime = performance.now();
    tracking.lastX = e.clientX;
    tracking.lastTime = tracking.startTime;
    tracking.velocity = 0;
    tracking.movedX = 0;
    tracking.crossedThreshold = false;
    tracking.intent = null;
    // ÖNEMLİ: baseOffset'i DOM'un GERÇEK pozisyonundan al — animasyon ortasında
    // pointerdown olursa, openState semantic değeri ile xRef.current desync olabilir.
    // Bu desync, drag başlarken kartın aniden başka bir pozisyona "sıçramasına" sebep olur
    // (sağa çekince sol açılma vb.).
    tracking.baseOffset = xRef.current;
    tracking.startedOpenState = openState;
    // animateTo gibi devam eden bir snap varsa iptal et — kullanıcı yeni drag'e başlıyor
    if (animCancelRef.current) animCancelRef.current();
  };

  const handlePointerMove = (e) => {
    const tracking = trackingRef.current;
    if (tracking.pointerId !== e.pointerId) return;

    const dx = e.clientX - tracking.startX;
    const dy = e.clientY - tracking.startY;
    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);

    // İlk hareket: yatay/dikey niyet kararı.
    if (tracking.intent === null) {
      // Önce dikey kontrol — diagonal scroll'da swipe açılmasını önler
      // (yatay 18px'e ulaşmadan önce dikey 6px → vertical commit)
      if (absDy >= 6 && absDy >= absDx) {
        tracking.intent = 'vertical';
        return; // Body scroll'a izin ver
      }
      // Yatay karar: dx >= 18px VE dx > dy * 1.5 olmalı (kazara açılmayı önler)
      if (absDx >= INTENT_DECISION_PX && absDx > absDy * HORIZONTAL_DOMINANCE) {
        tracking.intent = 'horizontal';
        try { e.target.setPointerCapture?.(e.pointerId); } catch (_) {}
      } else {
        return; // Henüz karar verilemedi, bekle
      }
    }

    if (tracking.intent !== 'horizontal') return;

    // Pointer down anındaki offset'e göre relative — snap'e göre değil
    let nextX = tracking.baseOffset + dx;

    // Constraint: -REVEAL_RIGHT .. +REVEAL_LEFT (hafif elastik kenar)
    if (nextX > REVEAL_LEFT) nextX = REVEAL_LEFT + (nextX - REVEAL_LEFT) * 0.06;
    if (nextX < -REVEAL_RIGHT) nextX = -REVEAL_RIGHT + (nextX + REVEAL_RIGHT) * 0.06;

    // Velocity (px/s, son frame'e göre)
    const now = performance.now();
    const dt = now - tracking.lastTime;
    if (dt > 0) {
      const dxFrame = e.clientX - tracking.lastX;
      tracking.velocity = (dxFrame / dt) * 1000;
    }
    tracking.lastX = e.clientX;
    tracking.lastTime = now;
    tracking.movedX = Math.abs(dx);

    // Eşik geçişi → tek seferlik haptic
    const willOpenLeft = nextX <= -SWIPE_THRESHOLD_PX;
    const willOpenRight = nextX >= SWIPE_THRESHOLD_PX;
    if ((willOpenLeft || willOpenRight) && !tracking.crossedThreshold) {
      tracking.crossedThreshold = true;
      triggerHaptic();
    } else if (!willOpenLeft && !willOpenRight) {
      tracking.crossedThreshold = false;
    }

    // setState YOK — direkt DOM transform
    applyTransform(nextX);
  };

  const handlePointerEnd = (e) => {
    const tracking = trackingRef.current;
    if (tracking.pointerId !== e.pointerId) return;
    tracking.pointerId = null;

    // Yatay drag yapılmadıysa hiçbir şey yapma — tap işlemini
    // handleClickCapture halledecek.
    if (tracking.intent !== 'horizontal') return;

    const finalX = xRef.current;
    const v = tracking.velocity;
    // Semantic state'e göre dal seç — animasyon ortasındaki ara değerlere
    // güvenmek yerine pointerDown anında neyin "açık" sayıldığını kullan.
    const wasOpenLeft = tracking.startedOpenState === 'left';
    const wasOpenRight = tracking.startedOpenState === 'right';
    const startedOpen = wasOpenLeft || wasOpenRight;

    // ===== KAPALI BAŞLADI: pozisyon/velocity ile yön açma =====
    if (!startedOpen) {
      if (finalX < -SWIPE_THRESHOLD_PX || v < -VELOCITY_THRESHOLD_PX_S) {
        snapTo(-REVEAL_RIGHT, 'right');
        return;
      }
      if (finalX > SWIPE_THRESHOLD_PX || v > VELOCITY_THRESHOLD_PX_S) {
        snapTo(REVEAL_LEFT, 'left');
        return;
      }
      snapTo(0, null);
      return;
    }

    // ===== AÇIK BAŞLADI: sadece "kapama" veya "açık kalma" — ters yön AÇMAZ =====
    // Aynı yöne tekrar swipe veya ters yöne flick → 0'a kapat veya açık tut.
    // Bu, sola açıkken hızlı sağa flick'in yan-bounce / ters panele atlamasını engeller.
    if (wasOpenRight) {
      // sağ panel açıktı (x ~ -160). Geri yönde yeterli hareket veya pozitif velocity → kapat
      const movedBackEnough = finalX > -REVEAL_RIGHT + SWIPE_THRESHOLD_PX;
      const flickedBack = v > VELOCITY_THRESHOLD_PX_S * 0.6;
      if (movedBackEnough || flickedBack) {
        snapTo(0, null);
      } else {
        snapTo(-REVEAL_RIGHT, 'right'); // hala açık kalsın
      }
      return;
    }
    if (wasOpenLeft) {
      const movedBackEnough = finalX < REVEAL_LEFT - SWIPE_THRESHOLD_PX;
      const flickedBack = v < -VELOCITY_THRESHOLD_PX_S * 0.6;
      if (movedBackEnough || flickedBack) {
        snapTo(0, null);
      } else {
        snapTo(REVEAL_LEFT, 'left');
      }
      return;
    }
  };

  const handleClickCapture = (e) => {
    // Drag yapıldıysa click'i yut (cardInner.onClick tetiklenmesin)
    const tracking = trackingRef.current;
    if (tracking.intent === 'horizontal' || tracking.movedX > TAP_MAX_DRAG_PX) {
      e.preventDefault();
      e.stopPropagation();
      tracking.movedX = 0;
      tracking.intent = null;
      return;
    }

    // İnteraktif child element (3 nokta menü trigger, action button, link) ise
    // capture phase'te yutmadan geç — yoksa child onClick'leri çalışmaz (Sorun 3).
    // Açık state'te yine de kapatma davranışını koru (aşağıda).
    const isInteractiveTarget = e.target?.closest?.(
      'button, a, [role="menuitem"], [role="button"], input, select, textarea, [data-no-swipe-tap]'
    );

    // Açıkken card'a tıklanırsa kapat (action butonu hariç)
    if (openState !== null) {
      // Sol/sağ panel butonlarına tıklamayı zaten action handler'lar yönetir;
      // alttaki kart üzerinde herhangi bir interactive tıklama da kartı kapatsın.
      e.preventDefault();
      e.stopPropagation();
      snapTo(0, null);
      return;
    }

    // İnteraktif hedefe tıklanmışsa onTap'i tetikleme (3 nokta dropdown vb. açılsın)
    if (isInteractiveTarget) return;

    // Normal tap — children'ın onClick'ini durdur ve onTap çağır
    if (onTap) {
      e.preventDefault();
      e.stopPropagation();
      onTap();
    }
  };

  const handleEdit = (e) => {
    e.stopPropagation();
    snapTo(0, null);
    onEdit?.();
  };
  const handleCancel = (e) => {
    e.stopPropagation();
    snapTo(0, null);
    onCancel?.();
  };
  const handleDelete = (e) => {
    e.stopPropagation();
    snapTo(0, null);
    onDelete?.();
  };

  // Desktop fallback — swipe yok, sadece children render
  if (!isCoarse || disabled) {
    return (
      <div onClick={onTap} style={{ cursor: onTap ? 'pointer' : undefined }}>
        {children}
      </div>
    );
  }

  // ÖNEMLİ: transform/opacity/visibility JSX inline style'da yok!
  // React her render'da bu inline style'ları DOM'a yazar ve applyTransform'un
  // ref-bazlı manipülasyonunu üzerine yazıp animasyonu sıçratırdı.
  // Bu değerler artık SADECE applyTransform üzerinden uygulanır
  // (mount'ta useLayoutEffect, drag'de pointermove, snap'te animateTo).

  return (
    <div
      className="relative overflow-hidden rounded-xl"
      style={{ touchAction: 'pan-y' }}
    >
      {/* Sol aksiyon (sağa swipe sonucu görünür) — Düzenle (mavi) */}
      <div
        ref={leftPanelRef}
        className="absolute inset-y-0 left-0 flex items-center justify-center pointer-events-none"
        style={{ width: REVEAL_LEFT }}
      >
        <button
          type="button"
          onClick={handleEdit}
          aria-label={t('common.edit', 'Düzenle')}
          className="w-full h-full flex flex-col items-center justify-center bg-blue-500 text-white font-semibold gap-1 transition-colors hover:bg-blue-600 pointer-events-auto"
        >
          <Edit className="w-5 h-5" />
          <span className="text-xs">{t('common.edit', 'Düzenle')}</span>
        </button>
      </div>

      {/* Sağ aksiyon (sola swipe sonucu görünür) — İptal + Sil */}
      <div
        ref={rightPanelRef}
        className="absolute inset-y-0 right-0 flex pointer-events-none"
        style={{ width: REVEAL_RIGHT }}
      >
        <button
          type="button"
          onClick={handleCancel}
          aria-label={t('common.cancel', 'İptal')}
          className="w-1/2 h-full flex flex-col items-center justify-center bg-orange-500 text-white font-semibold gap-1 transition-colors hover:bg-orange-600 pointer-events-auto"
        >
          <X className="w-5 h-5" />
          <span className="text-xs">{t('common.cancel', 'İptal')}</span>
        </button>
        <button
          type="button"
          onClick={handleDelete}
          aria-label={t('common.delete', 'Sil')}
          className="w-1/2 h-full flex flex-col items-center justify-center bg-red-500 text-white font-semibold gap-1 transition-colors hover:bg-red-600 pointer-events-auto"
        >
          <Trash2 className="w-5 h-5" />
          <span className="text-xs">{t('common.delete', 'Sil')}</span>
        </button>
      </div>

      {/* Drag-edilebilir kart içeriği — transform DOM ref ile uygulanır */}
      <div
        ref={cardInnerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onPointerCancel={handlePointerEnd}
        onClickCapture={handleClickCapture}
        style={{
          willChange: 'transform',
          position: 'relative',
          zIndex: 1,
          backfaceVisibility: 'hidden',
          WebkitBackfaceVisibility: 'hidden',
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default SwipeableAppointmentCard;
