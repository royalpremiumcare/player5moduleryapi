/**
 * Axios/FastAPI hata gövdesinden kullanıcıya gösterilecek metin.
 * detail: string | { message, error_code, ... } | validation array
 */

/**
 * Backend `error_code` → i18n `errors.mvp.<code>`; yoksa parseApiErrorDetail ile backend mesajı.
 * @param {unknown} err axios error
 * @param {function} t i18next t
 * @param {string} fallback
 */
export function formatApiError(err, t, fallback = "") {
  const fallbackText = parseApiErrorDetail(err, fallback);
  if (!t || typeof t !== "function") return fallbackText;
  const raw = err?.response?.data?.detail;
  if (!raw || typeof raw !== "object" || Array.isArray(raw) || !raw.error_code) {
    return fallbackText;
  }
  const key = `errors.mvp.${raw.error_code}`;
  return t(key, { defaultValue: fallbackText });
}

export function parseApiErrorDetail(err, fallback = "") {
  const raw = err?.response?.data?.detail;
  if (raw == null || raw === "") return fallback;
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) {
    const parts = raw
      .map((item) => {
        if (item && typeof item === "object" && item.msg) return String(item.msg);
        return typeof item === "string" ? item : "";
      })
      .filter(Boolean);
    return parts.length ? parts.join(" ") : fallback;
  }
  if (typeof raw === "object") {
    if (raw.message) return String(raw.message);
    if (raw.error_code) return String(raw.error_code);
  }
  return fallback;
}
