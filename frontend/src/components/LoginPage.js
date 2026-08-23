import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { Capacitor } from '@capacitor/core';
import { Globe } from 'lucide-react';

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isAppMode, setIsAppMode] = useState(false);

  const { login } = useAuth();

  // Sayfa yüklendiğinde en üste scroll et ve app mode kontrolü
  useEffect(() => {
    window.scrollTo(0, 0);
    
    // Native Capacitor uygulaması kontrolü
    if (Capacitor.isNativePlatform()) {
      localStorage.setItem('is_app_mode', 'true');
      setIsAppMode(true);
      
      // Android/iOS'te login sayfasına ?mode=app parametresi ekle (HashRouter için)
      const urlParams = new URLSearchParams(location.search);
      if (!urlParams.get('mode')) {
        urlParams.set('mode', 'app');
        navigate(`/login?${urlParams.toString()}`, { replace: true });
        return;
      }
    }

    // App mode detection from URL (HashRouter compatible)
    const urlParams = new URLSearchParams(location.search);
    const modeParam = urlParams.get('mode');
    
    if (modeParam === 'app') {
      localStorage.setItem('is_app_mode', 'true');
      setIsAppMode(true);
    } else if (localStorage.getItem('is_app_mode') === 'true') {
      setIsAppMode(true);
    }
  }, [location, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const urlParams = new URLSearchParams(location.search);
    const redirectParam = urlParams.get('redirect');
    const allowedRedirectPaths = new Set(['/subscribe']);
    const redirectPath = redirectParam && allowedRedirectPaths.has(redirectParam) ? redirectParam : '/';

    try {
      const result = await login(username, password, rememberMe);

      if (!result.success) {
        setError(result.error || t('auth.login.error'));
        setLoading(false);
      } else {
        // Başarılı giriş
        navigate(redirectPath, { replace: true });
      }
    } catch (err) {
      setError(err.message || t('auth.login.errorGeneric'));
      setLoading(false);
    }
  };

  const fieldLabel = "block text-[11px] font-semibold uppercase tracking-[0.15em] text-[#8c8c88]";
  const fieldInput = "w-full h-12 bg-white border border-[#e5e5e3] rounded-lg px-4 text-base text-[#1a1a1a] placeholder:text-[#c4c4c0] focus:border-[#1a1a1a] focus:outline-none transition-colors";

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fbfbfa] text-[#1a1a1a] px-6 py-10 animate-slide-down">
      <div className="w-full max-w-sm">
        {/* Dil değiştirici */}
        <div className="flex justify-end mb-6">
          <button
            type="button"
            onClick={() => i18n.changeLanguage(i18n.language === 'tr' ? 'en' : 'tr')}
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-[#8c8c88] hover:text-[#1a1a1a] transition-colors"
          >
            <Globe className="w-3.5 h-3.5" strokeWidth={1.75} />
            {i18n.language === 'tr' ? 'EN' : 'TR'}
          </button>
        </div>

        {/* Logo */}
        <div className="text-center mb-9">
          <h1 className="font-serif font-light tracking-[0.4em] text-[26px] uppercase text-[#1a1a1a]">{t('brand.name')}</h1>
          <p className="mt-4 text-[13px] tracking-[0.06em] text-[#8c8c88] font-serif italic">{t('auth.login.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="username" className={fieldLabel}>{t('auth.login.email')}</label>
            <input
              id="username"
              type="email"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('auth.login.emailPlaceholder')}
              className={fieldInput}
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className={fieldLabel}>{t('auth.login.password')}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className={fieldInput}
              required
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 accent-[#1a1a1a]"
            />
            <span className="text-[13px] text-[#6a6a68]">{t('auth.login.rememberMe')}</span>
          </label>

          {error && (
            <div className="border border-[#e9d5d2] bg-[#fbf5f4] px-4 py-3 rounded-lg">
              <p className="text-[13px] text-[#9b3b34]">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-[#1a1a1a] text-white text-[12px] font-semibold uppercase tracking-[0.2em] rounded-lg hover:bg-black transition-colors disabled:opacity-60"
          >
            {loading ? t('auth.login.loggingIn') : t('auth.login.loginButton')}
          </button>

          <button
            type="button"
            onClick={() => navigate('/forgot-password')}
            className="w-full text-center text-[12px] tracking-[0.04em] text-[#8c8c88] hover:text-[#1a1a1a] transition-colors"
          >
            {t('auth.login.forgotPassword')}
          </button>
        </form>

        <div className="mt-8 pt-7 border-t border-[#ececea] text-center">
          <p className="text-[13px] text-[#8c8c88] mb-4 font-serif italic">{t('auth.login.noAccount')}</p>
          <button
            type="button"
            onClick={() => navigate('/register')}
            className="w-full h-12 border border-[#1a1a1a] text-[#1a1a1a] text-[12px] font-semibold uppercase tracking-[0.2em] rounded-lg hover:bg-[#1a1a1a] hover:text-white transition-colors"
          >
            {t('auth.login.createAccount')}
          </button>
        </div>

        {/* Ana ekrana dön — sadece web'de */}
        {!isAppMode && (
          <div className="text-center mt-6">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="text-[11px] uppercase tracking-[0.2em] text-[#a8a8a4] hover:text-[#1a1a1a] transition-colors"
            >
              {t('common.backToHome')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
