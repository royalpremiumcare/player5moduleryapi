import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
import api from '../api/api';
import posthog from '../lib/posthog';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : '';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [canViewAll, setCanViewAll] = useState(false);

  useEffect(() => {
    // Önce localStorage'dan kontrol et, yoksa sessionStorage'dan
    const storedToken = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    const storedRole = localStorage.getItem('userRole') || sessionStorage.getItem('userRole');
    if (storedToken) {
      setToken(storedToken);
      setUserRole(storedRole);
      setIsAuthenticated(true);
      try {
        const payload = JSON.parse(atob(storedToken.split('.')[1]));
        setCanViewAll(payload.can_view_all_appointments || false);
        // PostHog identify — JWT'den user_id claim'ini al (backend bunu signup/login'de ekledi)
        if (payload.user_id) {
          posthog.identifyUser({
            user_id: payload.user_id,
            username: payload.sub,
            full_name: payload.full_name,
            organization_id: payload.org_id,
            company_name: payload.company_name,
            role: payload.role || storedRole,
            sector: payload.sector,
          });
        }
      } catch (e) {}
    }
  }, []);

  const login = async (username, password, rememberMe = false) => {
    try {
      // BACKEND_URL boş olabilir (same-origin için geçerli)
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      if (rememberMe) {
        formData.append('scope', 'remember_me');
      }

      const response = await axios.post(
        `${BACKEND_URL}/api/token`,
        formData,
        {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          timeout: 10000
        }
      );

      const { access_token } = response.data;
      
      // Token'ı decode ederek role bilgisini al
      const tokenPayload = JSON.parse(atob(access_token.split('.')[1]));
      const role = tokenPayload.role || 'admin';

      setToken(access_token);
      setUserRole(role);
      setCanViewAll(tokenPayload.can_view_all_appointments || false);

      // PostHog identify — login sonrası anonim distinct_id'yi user_id ile birleştir
      if (tokenPayload.user_id) {
        posthog.identifyUser({
          user_id: tokenPayload.user_id,
          username: tokenPayload.sub,
          full_name: tokenPayload.full_name,
          organization_id: tokenPayload.org_id,
          company_name: tokenPayload.company_name,
          role,
          sector: tokenPayload.sector,
        });
      }
      
      // rememberMe durumuna göre localStorage veya sessionStorage kullan
      if (rememberMe) {
        localStorage.setItem('authToken', access_token);
        localStorage.setItem('userRole', role);
      } else {
        sessionStorage.setItem('authToken', access_token);
        sessionStorage.setItem('userRole', role);
        // localStorage'dan temizle (eğer varsa)
        localStorage.removeItem('authToken');
        localStorage.removeItem('userRole');
      }
      
      setIsAuthenticated(true);
      return { success: true };

    } catch (error) {
      console.error("Giriş hatası:", error);

      let errorMessage = "Giriş sırasında bir hata oluştu.";

      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        errorMessage = "Backend sunucusuna bağlanılamıyor. Lütfen backend'in çalıştığından emin olun.";
      } else if (error.response) {
        if (error.response.status === 401) {
          errorMessage = "Kullanıcı adı veya parola hatalı.";
        } else if (error.response.status === 429) {
          errorMessage = "Çok fazla giriş denemesi. Lütfen birkaç dakika sonra tekrar deneyin.";
        } else if (error.response.status >= 500) {
          errorMessage = "Sunucu hatası. Lütfen daha sonra tekrar deneyin.";
        } else {
          errorMessage = error.response.data?.detail || errorMessage;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      setIsAuthenticated(false);
      setToken(null);
      setUserRole(null);
      setCanViewAll(false);
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      sessionStorage.removeItem('authToken');
      sessionStorage.removeItem('userRole');
      return { success: false, error: errorMessage };
    }
  };
  
  // İki aşamalı kayıt: önce WhatsApp OTP (`register-initiate`) gönderir,
  // kullanıcı kodu girince `register-verify` ile hesap oluşur ve token döner.
  // Public booking ile aynı pattern.
  const register = async (username, password, full_name, organization_name, support_phone, sector) => {
    try {
      const response = await api.post('/register-initiate', {
        username,
        password,
        full_name,
        organization_name,
        support_phone,
        sector,
      });
      // 200 = OTP gönderildi, hesap henüz oluşturulmadı
      return {
        success: true,
        verificationRequired: true,
        expiresIn: response.data?.expires_in ?? 900,
        phoneMasked: response.data?.phone_masked || '',
      };
    } catch (error) {
      console.error('❌ Register-initiate hatası:', error);
      const errorMessage = error.response?.data?.detail || 'Kayıt başlatılamadı. Lütfen bilgileri kontrol edip tekrar deneyin.';
      return { success: false, error: errorMessage };
    }
  };

  const registerVerify = async (phone, code, sector = null) => {
    try {
      const response = await api.post('/register-verify', { phone, code });
      const { access_token } = response.data || {};
      if (!access_token) {
        return { success: false, error: 'Doğrulama yanıtı geçersiz.' };
      }

      // Token'ı decode et
      const tokenPayload = JSON.parse(atob(access_token.split('.')[1]));
      const role = tokenPayload.role || 'admin';

      // PostHog: signup_completed (alias anonim → stable user_id)
      try {
        if (tokenPayload.user_id) {
          posthog.aliasAnonymous(tokenPayload.user_id);
          posthog.identifyUser({
            user_id: tokenPayload.user_id,
            username: tokenPayload.sub,
            full_name: tokenPayload.full_name,
            organization_id: tokenPayload.org_id,
            company_name: tokenPayload.company_name,
            role,
            sector,
          });
        }
        posthog.track('signup_completed', { sector: sector || null });
      } catch (e) {
        console.warn('PostHog signup tracking failed:', e);
      }

      // Auto-login: token'ı kaydet, state'i güncelle
      setToken(access_token);
      setUserRole(role);
      setCanViewAll(tokenPayload.can_view_all_appointments || false);
      // Yeni kayıt sonrası remember-me default true (kullanıcı login sayfasını görmesin)
      localStorage.setItem('authToken', access_token);
      localStorage.setItem('userRole', role);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      console.error('❌ Register-verify hatası:', error);
      const errorMessage = error.response?.data?.detail || 'Doğrulama kodu hatalı veya süresi dolmuş.';
      return { success: false, error: errorMessage };
    }
  };

  const logout = async () => {
    // App mode kontrolü
    const isAppMode = localStorage.getItem('is_app_mode') === 'true';
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                         window.navigator.standalone === true;
    
    // Backend'de push subscription'ları sil (FCM token'ı temizle)
    try {
      const currentToken = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
      if (currentToken) {
        // Token varsa backend'e unsubscribe isteği gönder
        await api.delete('/push/unsubscribe').catch(err => {
          // Hata olsa bile devam et (token geçersiz olabilir)
          console.warn('Push unsubscribe error (ignored):', err);
        });
      }
    } catch (error) {
      // Hata olsa bile devam et
      console.warn('Push unsubscribe error (ignored):', error);
    }
    
    // PostHog reset — sonraki kullanıcının funnel'ı temiz başlasın
    try { posthog.reset(); } catch (_) {}

    // State'leri temizle
    setToken(null);
    setUserRole(null);
    setCanViewAll(false);
    setIsAuthenticated(false);
    
    // Sadece auth bilgilerini sil - is_app_mode'u KORUYORUZ
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('userRole');
    
    // Herkesi login'e yönlendir - app mode ise mode=app parametresi ekle
    if (isAppMode || isStandalone) {
      window.location.href = '/login?mode=app';
    } else {
      window.location.href = '/login';
    }
  };

  return (
    <AuthContext.Provider value={{ token, isAuthenticated, userRole, canViewAll, login, register, registerVerify, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  return useContext(AuthContext);
};
