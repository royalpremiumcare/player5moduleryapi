import { toast } from "sonner";
import i18n from "@/i18n";

export const NETWORK_ERROR_TOAST_ID = "load-error-network";

// Yavaş bağlantıda istek süresiz asılı kalmasın; aşılırsa "bağlantınız çok yavaş" toast'ı.
export const APPOINTMENTS_LOAD_TIMEOUT_MS = 20000;

export function getLoadErrorKind(err) {
  if (err?.code === "ECONNABORTED" || err?.code === "ETIMEDOUT") return "timeout";
  if (!err?.response || (typeof navigator !== "undefined" && navigator.onLine === false)) {
    return "network";
  }
  return "server";
}

/**
 * Veri yükleme hatası toast'ı. Aynı anda tetiklenen yüklemeler (açılış, focus,
 * visibilitychange, socket event'leri) tek toast'ta birleşir: bağlantı hataları
 * tüm konular için ortak id'yi, sunucu hataları konu bazlı id'yi kullanır.
 * 401'de interceptor zaten login'e yönlendirdiği için toast gösterilmez.
 */
export function showLoadError(subjectKey, err, t = i18n.t.bind(i18n)) {
  if (err?.response?.status === 401) return;
  const kind = getLoadErrorKind(err);
  const subject = t(`errors.loadSubject.${subjectKey}`);
  const id = kind === "server" ? `load-error-${subjectKey}` : NETWORK_ERROR_TOAST_ID;
  toast.error(t(`errors.loadFailed.${kind}`, { subject }), { id });
}
