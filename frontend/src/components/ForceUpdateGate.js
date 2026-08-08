import React, { useState, useEffect, useCallback, useRef } from "react";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import api from "@/api/api";
import { evaluateUpdate } from "@/lib/versionCheck";
import { openAppStore } from "@/lib/appStore";
import ForceUpdateModal from "@/components/ForceUpdateModal";

/**
 * Force-update kapısı — EN ÜST SEVİYE (AppRouter'da mount).
 *
 * Neden burada? Modal AUTH'tan BAĞIMSIZ görünmeli: beni-hatırla kapalı kullanıcı
 * login ekranını görmeden, splash sonrası bloklanmalı. App.js sadece authenticated
 * iken mount olduğu için kontrol burada yaşar (tek kaynak, dağ­ıtık kopya yok).
 *
 * FAIL-OPEN: config alınamaz / getInfo patlarsa kullanıcı ASLA kilitlenmez.
 * Sadece native (iOS/Android). Web hep günceldir → hiç çalışmaz.
 */
const ForceUpdateGate = () => {
  const [gate, setGate] = useState(null);
  const softDismissedRef = useRef(false);

  const checkAppVersion = useCallback(async () => {
    try {
      if (!Capacitor.isNativePlatform()) return;
      const platform = Capacitor.getPlatform();
      const info = await CapacitorApp.getInfo();
      const currentVersion = info?.version;
      if (!currentVersion) return;
      const { data: config } = await api.get('/app/config');
      const result = evaluateUpdate({ currentVersion, platform, config });
      if (result.level === 'block') {
        setGate({ level: 'block', storeUrl: result.storeUrl });
      } else if (result.level === 'soft') {
        if (softDismissedRef.current) return; // bu oturumda kapatıldıysa gösterme
        setGate({ level: 'soft', storeUrl: result.storeUrl });
      } else {
        setGate(null);
      }
    } catch (_) {
      // FAIL-OPEN: sessizce yut, kullanıcıyı kilitleme
    }
  }, []);

  // Açılışta bir kez kontrol et.
  useEffect(() => { checkAppVersion(); }, [checkAppVersion]);

  // Uygulama öne gelince tekrar kontrol et (arka planda sürüm bumplanmış olabilir).
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let listener;
    CapacitorApp.addListener('appStateChange', ({ isActive }) => {
      if (isActive) checkAppVersion();
    }).then((l) => { listener = l; });
    return () => { if (listener) listener.remove(); };
  }, [checkAppVersion]);

  if (!gate) return null;

  return (
    <ForceUpdateModal
      level={gate.level}
      onUpdate={() => openAppStore({ store_url_web: gate.storeUrl })}
      onDismiss={() => {
        softDismissedRef.current = true;
        setGate(null);
      }}
    />
  );
};

export default ForceUpdateGate;
