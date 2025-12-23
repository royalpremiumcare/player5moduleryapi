import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight, Mail } from 'lucide-react';
import api from '../api/api';

const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isAppMode, setIsAppMode] = useState(false);

  // Sayfa yüklendiğinde en üste scroll et ve app mode kontrolü
  useEffect(() => {
    window.scrollTo(0, 0);
    
    // App mode detection
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'app') {
      localStorage.setItem('is_app_mode', 'true');
      setIsAppMode(true);
    } else if (localStorage.getItem('is_app_mode') === 'true') {
      setIsAppMode(true);
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);

    try {
      await api.post('/forgot-password', { username: email });
      setSuccess(true);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || t('auth.forgotPassword.error', 'An error occurred. Please try again.');
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen md:min-h-screen bg-white animate-slide-down py-4 md:py-0">
      <div className="w-full max-w-md px-4">
        {/* Logo & Title */}
        <div className="text-center mb-4 md:mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">PLANN</h1>
          <p className="text-gray-600">{t('brand.tagline', 'Appointment Management System')}</p>
        </div>

        <Card className="shadow-2xl border-0">
          <CardHeader className="space-y-1 pb-4 md:pb-6">
            <CardTitle className="text-2xl font-bold text-center text-gray-900">
              {t('auth.forgotPassword.title', 'Forgot Password')}
            </CardTitle>
            <p className="text-center text-sm text-gray-600">
              {t('auth.forgotPassword.subtitle', "Enter your email address and we'll send you a reset link")}
            </p>
          </CardHeader>
          <CardContent className="px-4 md:px-6">
            {success ? (
              <div className="space-y-4">
                <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded">
                  <p className="text-sm text-green-700">
                    {t('auth.forgotPassword.success', 'Password reset link has been sent to your email.')}
                  </p>
                </div>
                <Button
                  onClick={() => navigate('/login')}
                  className="w-full h-12 bg-gray-900 hover:bg-gray-800 text-white font-semibold rounded-full shadow-lg transition-all duration-200"
                >
                  {t('auth.forgotPassword.backToLogin', 'Back to Login')}
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4 md:space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
                    {t('auth.forgotPassword.email', 'Email Address')}
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={t('auth.login.emailPlaceholder', 'example@email.com')}
                      className="pl-10 h-12 border-2 focus:border-gray-900"
                      required
                    />
                  </div>
                </div>

                {error && (
                  <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                <Button 
                  type="submit" 
                  className="w-full h-12 bg-gray-900 hover:bg-gray-800 text-white font-semibold rounded-full shadow-lg transition-all duration-200" 
                  disabled={loading}
                >
                  {loading ? t('auth.forgotPassword.sending', 'Sending...') : t('auth.forgotPassword.sendButton', 'Send Reset Link')}
                </Button>
              </form>
            )}

            <div className="mt-4 md:mt-6 pt-4 md:pt-6 border-t border-gray-200 text-center">
              <Button
                variant="outline"
                onClick={() => navigate('/login')}
                className="w-full h-12 border-2 border-gray-900 text-gray-900 hover:bg-gray-900 hover:text-white font-semibold rounded-full transition-all duration-200"
              >
                {t('auth.forgotPassword.backToLogin', 'Back to Login')}
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {!isAppMode && (
          <div className="text-center mt-4 md:mt-6 mb-4 md:mb-0">
            <Button
              variant="outline"
              onClick={() => navigate('/')}
              className="text-gray-900 hover:text-white hover:bg-gray-900 border-2 border-gray-900 px-6 py-3 text-base md:text-lg font-semibold rounded-lg transition-all duration-200 shadow-md"
            >
              {t('common.backToHome', '← Back to Home')}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ForgotPasswordPage;