import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : 'http://localhost:8001';

// BACKEND_URL kontrolü (sadece undefined ise uyar, empty string geçerli)
if (process.env.REACT_APP_BACKEND_URL === undefined) {
  console.warn('⚠️ REACT_APP_BACKEND_URL tanımlı değil! Varsayılan olarak http://localhost:8001 kullanılıyor.');
  console.warn('Lütfen frontend/.env dosyasında REACT_APP_BACKEND_URL değişkenini tanımlayın.');
}

// Yeni, önceden ayarlanmış bir 'axios' örneği (instance) oluşturuyoruz
const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

// === API REQUEST TUTAMAÇ (INTERCEPTOR) ===
// Her istekten önce token'ı Authorization başlığına ekler
api.interceptors.request.use(
  (config) => {
    // Önce localStorage'dan kontrol et, yoksa sessionStorage'dan
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
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
  (error) => {
    // 401 Unauthorized hatası geldiğinde otomatik logout
    if (error.response && error.response.status === 401) {
      // App mode kontrolü - yönlendirmeden ÖNCE kontrol et
      const isAppMode = localStorage.getItem('is_app_mode') === 'true';
      
      // Sadece auth bilgilerini sil - is_app_mode'u KORUYORUZ
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
