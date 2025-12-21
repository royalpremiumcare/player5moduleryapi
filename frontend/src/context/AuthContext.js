import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
import api from '../api/api'; 

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : 'http://localhost:8001';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);

  useEffect(() => {
    // Önce localStorage'dan kontrol et, yoksa sessionStorage'dan
    const storedToken = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    const storedRole = localStorage.getItem('userRole') || sessionStorage.getItem('userRole');
    if (storedToken) {
      setToken(storedToken);
      setUserRole(storedRole);
      setIsAuthenticated(true);
    }
  }, []);

  const login = async (username, password, rememberMe = false) => {
    try {
      // BACKEND_URL boş olabilir (same-origin için geçerli)
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

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
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      sessionStorage.removeItem('authToken');
      sessionStorage.removeItem('userRole');
      return { success: false, error: errorMessage };
    }
  };
  
  const register = async (username, password, full_name, organization_name, support_phone, sector) => {
    try {
      console.log('🔵 AuthContext: Register isteği başlıyor...', { username, full_name, organization_name, support_phone, sector });
      
      const response = await api.post('/register', { 
        username, 
        password, 
        full_name, 
        organization_name,
        support_phone,
        sector
      });
      
      console.log('✅ AuthContext: Register başarılı', response.data);

      if (response.status === 200) {
        return { success: true };
      }
    } catch (error) {
      console.error('❌ Kayıt hatası (AuthContext):', error);
      console.error('Error response:', error.response?.data);
      console.error('Error status:', error.response?.status);
      const errorMessage = error.response?.data?.detail || 'Kayıt sırasında bir hata oluştu. Kullanıcı adı mevcut olabilir.';
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
    
    // State'leri temizle
    setToken(null);
    setUserRole(null);
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
    <AuthContext.Provider value={{ token, isAuthenticated, userRole, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  return useContext(AuthContext);
};
