import axios from 'axios';
import i18n from '../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : '';

// BACKEND_URL kontrolü (sadece undefined ise uyar, empty string geçerli)
if (process.env.REACT_APP_BACKEND_URL === undefined) {
  console.warn('⚠️ REACT_APP_BACKEND_URL tanımlı değil! Varsayılan olarak same-origin (/api) kullanılacak.');
  console.warn('Lütfen frontend/.env dosyasında REACT_APP_BACKEND_URL değişkenini tanımlayın.');
}

// Yeni, önceden ayarlanmış bir 'axios' örneği (instance) oluşturuyoruz
const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

// === API REQUEST TUTAMAÇ (INTERCEPTOR) ===
// Her istekten önce token'ı Authorization başlığına ekler ve dil bilgisini gönderir
api.interceptors.request.use(
  (config) => {
    // Önce localStorage'dan kontrol et, yoksa sessionStorage'dan
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Dil bilgisini Accept-Language header'ına ekle
    const rawLang = (i18n && i18n.language) ? i18n.language : (localStorage.getItem('i18nextLng') || 'en');
    const savedLang = String(rawLang).split('-')[0];
    config.headers['Accept-Language'] = savedLang;
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// === API RESPONSE TUTAMAÇ (INTERCEPTOR) ===
// 401 hatasında otomatik çıkış yapar
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    // 401 Unauthorized hatası geldiğinde otomatik logout
    if (error.response && error.response.status === 401) {
      // push/unsubscribe isteği zaten 401 dönerse sonsuz döngüye girmesin
      const requestUrl = error.config?.url || '';
      if (requestUrl.includes('/push/unsubscribe')) {
        return Promise.reject(error);
      }

      // Stripe confirm endpoint'i best-effort: token yoksa/expire olduysa kullanıcıyı zorla logout etme
      if (requestUrl.includes('/payments/confirm-checkout-session')) {
        return Promise.reject(error);
      }

      // App mode kontrolü - yönlendirmeden ÖNCE kontrol et
      const isAppMode = localStorage.getItem('is_app_mode') === 'true';

      // Push aboneliği burada silinmez — yalnızca açık logout veya Ayarlar'dan
      // bildirim kapatma aboneliği siler. Token süresi dolunca cihaz kaydı korunur.

      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      sessionStorage.removeItem('authToken');
      sessionStorage.removeItem('userRole');
      
      // App mode'a göre yönlendirme
      if (isAppMode) {
        window.location.href = '/login?mode=app';
      } else {
        window.location.href = '/';
      }
    }
    return Promise.reject(error);
  }
);

export { BACKEND_URL };
export default api;
