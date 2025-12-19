import { useState, useEffect } from "react";
import { Package, AlertTriangle, ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';

const SettingsSubscription = ({ onNavigate }) => {
  const { t, i18n } = useTranslation();
  const [planInfo, setPlanInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingPortal, setLoadingPortal] = useState(false);
  
  // App Store Compliance: Mobil uygulamada (Android/iOS) ödeme butonlarını gizle
  // Sadece native platform kontrolü yap, localStorage kontrolü yapma (web'de ?mode=app ile giriş yapıldığında localStorage'a yazılıyor)
  const isAppMode = Capacitor.isNativePlatform();

  useEffect(() => {
    loadPlanInfo();
  }, []);

  const loadPlanInfo = async () => {
    try {
      const response = await api.get("/plan/current");
      setPlanInfo(response.data);
    } catch (error) {
      console.error("Plan bilgisi yüklenemedi:", error);
      // Silent error - don't show toast
    } finally {
      setLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    setLoadingPortal(true);
    try {
      const response = await api.post("/subscription/portal");
      // Stripe Customer Portal'a yönlendir
      const portalUrl = response.data.portal_url;
      
      if (!portalUrl) {
        throw new Error("Portal URL not received");
      }
      
      if (Capacitor.isNativePlatform()) {
        // Native (Android/iOS) - In-App Browser ile aç
        await Browser.open({ url: portalUrl });
      } else {
        // Web - Standart yönlendirme
        window.location.href = portalUrl;
      }
    } catch (error) {
      console.error("Portal oluşturma hatası:", error);
      const errorMessage = error.response?.data?.detail || error.message || t('settings.subscriptionPage.portalError');
      toast.error(errorMessage);
      setLoadingPortal(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <p className="text-sm text-gray-600">{t('settings.subscriptionPage.loading')}</p>
          </Card>
        </div>
      </div>
    );
  }

  if (!planInfo) {
    return null;
  }

  const quotaPercentage = (planInfo.quota_usage / planInfo.quota_limit * 100) || 0;
  const isLowQuota = quotaPercentage >= 90;
  const quotaRemaining = Math.max(0, planInfo.quota_limit - planInfo.quota_usage);

  return (
    <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* KART 1: Abonelik Bilgisi */}
      <div className="px-4 pt-6 pb-4">
        <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
          <div className="space-y-4">
            <div className="mb-4">
              <button
                onClick={() => onNavigate && onNavigate("settings")}
                className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="text-sm font-medium">{t('settings.backToSettings')}</span>
              </button>
              <div>
                <h2 className="text-lg font-bold text-gray-900">{t('settings.subscriptionPage.title')}</h2>
                <p className="text-sm text-gray-600 mt-1">{t('settings.subscriptionPage.subtitle')}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-base font-semibold text-gray-900">{t('settings.subscriptionPage.planPackage', { planName: planInfo.plan_name })}</p>
                  {planInfo.is_yearly && (
                    <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded-full">
                      {t('settings.subscriptionPage.yearlyPlan')}
                    </span>
                  )}
                  {!planInfo.is_trial && !planInfo.is_yearly && planInfo.billing_cycle === 'monthly' && (
                    <span className="bg-blue-100 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full">
                      {t('settings.subscriptionPage.monthlyPlan')}
                    </span>
                  )}
                </div>
                {planInfo.is_trial && planInfo.trial_days_remaining !== undefined && (
                  <p className="text-sm text-gray-600 mt-1">
                    {t('settings.subscriptionPage.daysRemaining', { days: planInfo.trial_days_remaining })}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">
                    {t('settings.subscriptionPage.appointmentQuota')}
                  </span>
                  <span className={`font-semibold ${
                    isLowQuota ? 'text-red-600' : 'text-gray-900'
                  }`}>
                    {planInfo.quota_usage.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} / {planInfo.quota_limit.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full ${
                      isLowQuota
                        ? 'bg-gradient-to-r from-yellow-400 to-red-500'
                        : 'bg-blue-600'
                    }`}
                    style={{ width: `${Math.min(quotaPercentage, 100)}%` }}
                  ></div>
                </div>
                <p className="text-xs text-gray-600">
                  {t('settings.subscriptionPage.remaining')}: <span className="font-semibold">{quotaRemaining.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')}</span> {t('settings.subscriptionPage.appointments')} 
                  {/* Yıllık paket için de "thisMonth" göster ama yanında yeşil badge var zaten */}
                  {planInfo.is_trial ? '' : ` ${t('settings.subscriptionPage.thisMonth')}`}
                </p>
              </div>

              {isLowQuota && (
                <div className="flex items-center gap-2 text-xs text-red-600 font-semibold bg-red-50 px-3 py-2 rounded-lg">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{t('settings.subscriptionPage.quotaLow')}</span>
                </div>
              )}

              {planInfo.is_trial && planInfo.trial_days_remaining !== undefined && planInfo.trial_days_remaining <= 2 && (
                <div className="flex items-center gap-2 text-xs text-red-600 font-semibold bg-red-50 px-3 py-2 rounded-lg">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{t('settings.subscriptionPage.trialEnding')}</span>
                </div>
              )}

              {/* App Store Compliance: Mobil uygulamada ödeme butonlarını gizle */}
              {!isAppMode && (
                <>
                  <Button
                    onClick={() => onNavigate && onNavigate("subscribe")}
                    className="w-full bg-blue-600 hover:bg-blue-700 h-12 text-base font-semibold rounded-full"
                  >
                    {t('settings.subscriptionPage.changePlan')}
                  </Button>

                  {!planInfo.is_trial && (
                    <button
                      onClick={handleManageSubscription}
                      disabled={loadingPortal}
                      className="w-full h-12 rounded-full text-base font-semibold transition-all duration-200 
                        bg-gradient-to-r from-gray-800 to-gray-900 text-white 
                        hover:from-gray-700 hover:to-gray-800 hover:shadow-lg
                        disabled:opacity-50 disabled:cursor-not-allowed
                        flex items-center justify-center gap-2"
                    >
                      {loadingPortal ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          {t('settings.subscriptionPage.redirecting')}
                        </>
                      ) : (
                        t('settings.subscriptionPage.manageSubscription')
                      )}
                    </button>
                  )}
                </>
              )}
              
              {/* App Mode: Bilgilendirme mesajı */}
              {isAppMode && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                  <p className="text-sm text-blue-800 mb-3">
                    {t('appCompliance.subscriptionInfo')}
                  </p>
                  <Button
                    onClick={() => {
                      const webUrl = 'https://plannapp.co';
                      if (Capacitor.isNativePlatform()) {
                        Browser.open({ url: webUrl });
                      } else {
                        window.location.href = webUrl;
                      }
                    }}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {t('appCompliance.goToWebsite')}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default SettingsSubscription;

