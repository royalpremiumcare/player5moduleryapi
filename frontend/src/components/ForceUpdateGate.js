import React, { useState, useEffect, useCallback, useRef } from "react";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { CapacitorUpdater } from "@capgo/capacitor-updater";
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
// Soft "kapat" seçimi, ilgili sürüme bağlı olarak kalıcı saklanır: kullanıcı 6.9
// için kapatınca app yeniden açılsa da rahatsız edilmez; DAHA YENİ bir sürüm
// (ör. 7.0) çıkınca banner tekrar gösterilir.
const SOFT_DISMISS_KEY = "plann_soft_update_dismissed_version";

function isSoftDismissed(version) {
  try {
    return !!version && localStorage.getItem(SOFT_DISMISS_KEY) === version;
  } catch (_) {
    return false;
  }
}

function markSoftDismissed(version) {
  try {
    if (version) localStorage.setItem(SOFT_DISMISS_KEY, version);
  } catch (_) { /* storage yoksa oturum-içi ref zaten kapatır */ }
}

const ForceUpdateGate = () => {
  const [gate, setGate] = useState(null);
  const softDismissedRef = useRef(false);

  // Capgo OTA: "bundle sağlıklı açıldı" sinyali. KRİTİK: auth'tan bağımsız, en erken
  // çağrılmalı — App.js'e koyarsak login ekranında hiç çağrılmaz ve Capgo
  // appReadyTimeout (10s) sonrası bundle'ı bozuk sayıp rollback eder (sayfa yenilenir).
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    CapacitorUpdater.notifyAppReady().catch(() => { /* web/no-op önemsiz */ });
  }, []);

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
        // Bu oturumda ya da bu sürüm için daha önce kapatıldıysa gösterme.
        if (softDismissedRef.current || isSoftDismissed(result.version)) return;
        setGate({ level: 'soft', storeUrl: result.storeUrl, version: result.version });
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
        markSoftDismissed(gate.version);
        setGate(null);
      }}
    />
  );
};

export default ForceUpdateGate;
