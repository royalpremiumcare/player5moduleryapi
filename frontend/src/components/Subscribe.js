import { useState, useEffect } from "react";
import { ArrowLeft, Check, Globe, ExternalLink, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

const Subscribe = ({ onNavigate }) => {
  const { t, i18n } = useTranslation();
  const webUrl = i18n.language && i18n.language.toLowerCase().startsWith('en')
    ? 'https://plannapp.co.uk'
    : 'https://plannapp.co';
  
  // Pricing Display Configuration - Exact flat numbers matching Stripe Fixed Amount Coupons
  const PRICING_DISPLAY = {
    try: {
      // Math: Base Price - Coupon Amount = Discounted Price
      standard:     { original: 750,  discounted: 550 },  // 750 - 200 = 550
      professional: { original: 1000, discounted: 750 },  // 1000 - 250 = 750
      premium:      { original: 1550, discounted: 1150 }, // 1550 - 400 = 1150
      business:     { original: 1950, discounted: 1450 }, // 1950 - 500 = 1450
      enterprise:   { original: 2350, discounted: 1750 }, // 2350 - 600 = 1750
      corporate:    { original: 3600, discounted: 2700 }, // 3600 - 900 = 2700
    },
    gbp: {
      // Math: Base Price - Coupon Amount = Discounted Price
      standard:     { original: 16, discounted: 12 },     // 16 - 4 = 12
      professional: { original: 24, discounted: 18 },     // 24 - 6 = 18
      premium:      { original: 32, discounted: 24 },     // 32 - 8 = 24
      business:     { original: 40, discounted: 30 },     // 40 - 10 = 30
      enterprise:   { original: 56, discounted: 42 },     // 56 - 14 = 42
      corporate:    { original: 80, discounted: 60 },     // 80 - 20 = 60
    }
  };
  
  // Plan ismine göre pricing key'i döndür
  const getPlanPricingKey = (planName) => {
    const planNameLower = planName.toLowerCase();
    if (planNameLower.includes('standart') || planNameLower.includes('standard')) return 'standard';
    if (planNameLower.includes('profesyonel') || planNameLower.includes('professional')) return 'professional';
    if (planNameLower.includes('premium')) return 'premium';
    if (planNameLower.includes('business')) return 'business';
    if (planNameLower.includes('enterprise')) return 'enterprise';
    if (planNameLower.includes('kurumsal') || planNameLower.includes('corporate')) return 'corporate';
    return 'standard'; // fallback
  };
  
  // Plan isimleri çevirisi
  const getPlanName = (planName) => {
    const planNameMap = {
      'Standart': 'Standard',
      'Profesyonel': 'Professional',
      'Premium': 'Premium',
      'Business': 'Business',
      'Enterprise': 'Enterprise',
      'Kurumsal': 'Corporate',
    };
    return i18n.language === 'en' && planNameMap[planName] ? planNameMap[planName] : planName;
  };
  
  // App Store Compliance: Mobil uygulamada (Android/iOS) ödeme sayfasını gizle
  // Sadece native platform kontrolü yap, localStorage kontrolü yapma (web'de ?mode=app ile giriş yapıldığında localStorage'a yazılıyor)
  const isAppMode = Capacitor.isNativePlatform();
  
  // Eğer app mode ise, sadece bilgilendirme mesajı göster
  if (isAppMode) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 pb-20 flex items-center justify-center" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 w-full max-w-md">
          <Card className="bg-white/80 backdrop-blur-sm shadow-2xl border-0 rounded-3xl p-8 mx-auto text-center overflow-hidden relative">
            {/* Decorative gradient overlay */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-blue-400/10 to-purple-400/10 rounded-full blur-3xl -mr-32 -mt-32"></div>
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-purple-400/10 to-pink-400/10 rounded-full blur-3xl -ml-32 -mb-32"></div>
            
            <div className="relative z-10">
              {/* Icon */}
              <div className="mx-auto mb-6 w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
                <Globe className="w-10 h-10 text-white" />
              </div>
              
              {/* Title */}
              <h2 className="text-2xl font-bold text-gray-900 mb-3">
                {t('settings.subscribePage.subscriptionManagement')}
              </h2>
              
              {/* Description */}
              <p className="text-gray-600 mb-8 leading-relaxed px-2">
                {t('appCompliance.subscriptionInfo')}
              </p>
              
              {/* CTA Button */}
              <Button
                onClick={() => {
                  if (Capacitor.isNativePlatform()) {
                    Browser.open({ url: webUrl });
                  } else {
                    window.location.href = webUrl;
                  }
                }}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-6 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-[1.02] flex items-center justify-center gap-2 group"
              >
                <ExternalLink className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                {t('appCompliance.goToWebsite')}
              </Button>
              
              {/* Back button */}
              <button
                onClick={() => onNavigate && onNavigate("settings")}
                className="mt-6 text-sm text-gray-500 hover:text-gray-700 font-medium transition-colors duration-200 flex items-center justify-center gap-1 mx-auto"
              >
                <ArrowLeft className="w-4 h-4" />
                {t('settings.subscribePage.backToSettings')}
              </button>
            </div>
          </Card>
          
          {/* Additional info card */}
          <div className="mt-4 bg-white/60 backdrop-blur-sm rounded-2xl p-4 text-center">
            <div className="flex items-center justify-center gap-2 text-gray-600 text-sm">
              <Sparkles className="w-4 h-4 text-purple-500" />
              <span className="font-medium">
                {i18n.language === 'tr' 
                  ? 'Hızlı ve güvenli ödeme için web sitesini ziyaret edin' 
                  : 'Visit our website for quick and secure payment'}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }
  const [plans, setPlans] = useState([]);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processingPlanId, setProcessingPlanId] = useState(null);
  const [billingCycle, setBillingCycle] = useState('monthly'); // 'monthly' or 'yearly'

  useEffect(() => {
    loadPlans();
    
    // URL'de session_id varsa ödeme başarılı mesajı göster
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId) {
      toast.success(t('settings.subscribePage.paymentSuccess'), {
        duration: 5000,
      });

      // Webhook gecikmesi / misconfig durumuna karşı: backend'e confirm isteği at
      api.post("/payments/confirm-checkout-session", { session_id: sessionId })
        .then(() => {
          // Planı yeniden yükle
          setTimeout(() => {
            loadPlans();
          }, 1000);
        })
        .catch(() => {
          // Sessiz geç - plan yine de webhook ile güncellenebilir
          setTimeout(() => {
            loadPlans();
          }, 1000);
        });
      
      // URL'den session_id'yi temizle
      window.history.replaceState({}, document.title, window.location.pathname);
      
    }

    // Native: Browser kapandığında processingPlanId'yi sıfırla
    let browserListener = null;
    if (Capacitor.isNativePlatform()) {
      browserListener = Browser.addListener('browserFinished', () => {
        setProcessingPlanId(null);
        // Planları yeniden yükle (ödeme başarılı olmuş olabilir)
        loadPlans();
      });
    }

    return () => {
      if (browserListener) {
        browserListener.remove();
      }
    };
  }, []);

  const loadPlans = async () => {
    try {
      const [plansResponse, currentPlanResponse] = await Promise.all([
        api.get("/plans"),
        api.get("/plan/current")
      ]);
      
      // Trial paketini filtrele, sadece ücretli paketleri göster
      const paidPlans = plansResponse.data.plans.filter(plan => plan.id !== 'tier_trial');
      setPlans(paidPlans);
      setCurrentPlan(currentPlanResponse.data);
    } catch (error) {
      console.error("Planlar yüklenemedi:", error);
      toast.error(t('settings.subscribePage.plansLoadError'));
    } finally {
      setLoading(false);
    }
  };

  const handleStartSubscription = async (planId) => {
    setProcessingPlanId(planId);
    try {
      // Platform bilgisini belirle
      const platform = Capacitor.isNativePlatform() 
        ? (Capacitor.getPlatform() === 'ios' ? 'ios' : 'android') 
        : 'web';
      
      // Para birimi algılama (frontend'den gönderilir, backend'de de kontrol edilir)
      const currency = i18n.language === 'en' ? 'gbp' : 'try';
      
      const response = await api.post("/payments/create-checkout-session", {
        plan_id: planId,
        billing_cycle: billingCycle,
        platform: platform,
        currency: currency
      });
      
      if (response.data && response.data.checkout_url) {
        // Stripe Checkout sayfasına yönlendir
        const checkoutUrl = response.data.checkout_url;
        
        if (Capacitor.isNativePlatform()) {
          // Native (Android/iOS) - In-App Browser ile aç
          await Browser.open({ url: checkoutUrl });
        } else {
          // Web - Standart yönlendirme
          window.location.href = checkoutUrl;
        }
      } else {
        toast.error(t('settings.subscribePage.paymentPageError'));
        setProcessingPlanId(null);
      }
    } catch (error) {
      console.error("Ödeme işlemi başlatılamadı:", error);
      const errorMessage = error.response?.data?.detail || error.message || t('settings.subscribePage.paymentError');
      toast.error(errorMessage);
      setProcessingPlanId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <p className="text-sm text-gray-600">{t('settings.subscribePage.loading')}</p>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* Header */}
      <div className="px-4 pt-6 pb-4">
        <button
          onClick={() => onNavigate && onNavigate("settings")}
          className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="text-sm font-medium">{t('settings.subscribePage.back')}</span>
        </button>
        <h1 className="text-2xl font-bold text-gray-900">{t('settings.subscribePage.title')}</h1>
        <p className="text-sm text-gray-600 mt-1">{t('settings.subscribePage.subtitle')}</p>
        
        {/* Aylık / Yıllık Toggle */}
        <div className="flex items-center justify-center gap-3 mt-6">
          <span className={`text-base font-medium ${billingCycle === 'monthly' ? 'text-gray-900' : 'text-gray-400'}`}>
            {t('settings.subscribePage.monthly')}
          </span>
          <button
            onClick={() => setBillingCycle(billingCycle === 'monthly' ? 'yearly' : 'monthly')}
            className={`relative w-14 h-7 rounded-full transition-colors duration-300 flex-shrink-0 ${billingCycle === 'yearly' ? 'bg-green-500' : 'bg-gray-300'}`}
          >
            <span 
              className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform duration-300 ${billingCycle === 'yearly' ? 'translate-x-7' : 'translate-x-0'}`}
            />
          </button>
          <div className="flex items-center gap-2">
            <span className={`text-base font-medium ${billingCycle === 'yearly' ? 'text-gray-900' : 'text-gray-400'}`}>
              {t('settings.subscribePage.yearly')}
            </span>
            {billingCycle === 'yearly' && (
              <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap">
                {t('settings.subscribePage.twoMonthsFree')}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* İndirim Banner - Sadece aylık ve ilk ay için göster */}
      {billingCycle === 'monthly' && currentPlan && currentPlan.is_first_month && (
        <div className="px-4 pb-4">
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl p-6 shadow-lg">
            <h2 className="text-xl font-bold mb-2">🎉 {t('settings.subscribePage.firstMonthDiscount')}</h2>
            <p className="text-sm text-blue-50">
              {t('settings.subscribePage.firstMonthDiscountDesc')}
            </p>
            <p className="text-sm text-blue-50 mt-2">
              <strong>{t('settings.subscribePage.nextMonths')}</strong>
            </p>
          </div>
        </div>
      )}

      {/* Paket Kartları */}
      <div className="px-4 pb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map((plan) => {
            const isYearly = billingCycle === 'yearly';
            const isFirstMonth = !isYearly && currentPlan && currentPlan.is_first_month;
            
            // Currency detection - Language bazlı
            const currency = i18n.language === 'en' ? 'gbp' : 'try';
            const currencySymbol = currency === 'try' ? '₺' : '£';
            
            // Plan pricing key'i al
            const planPricingKey = getPlanPricingKey(plan.name);
            const pricing = PRICING_DISPLAY[currency][planPricingKey];
            
            // PRICING_DISPLAY'den exact flat numbers kullan
            const originalPrice = pricing.original;
            const discountedPrice = pricing.discounted;
            
            // Yıllık fiyat hesaplama (original price * 10)
            const yearlyPrice = originalPrice * 10;
            const monthlyEquivalent = Math.round(yearlyPrice / 12);
            
            const isProcessing = processingPlanId === plan.id;
            const isCurrentPlan = currentPlan && currentPlan.plan_id === plan.id;

            return (
              <Card
                key={plan.id}
                className="bg-white shadow-md border border-gray-200 rounded-xl p-6 flex flex-col"
              >
                {/* Paket Adı */}
                <h3 className="text-xl font-bold text-gray-900 mb-4">{getPlanName(plan.name)}</h3>

                {/* Fiyat */}
                <div className="mb-4">
                  {isYearly ? (
                    <>
                      <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-3xl font-bold text-blue-600">
                          {yearlyPrice.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}
                        </span>
                        <span className="text-gray-500 line-through text-lg">
                          {(originalPrice * 12).toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}
                        </span>
                      </div>
                      <p className="text-xs text-green-600 font-semibold">{t('settings.subscribePage.yearlyBadge')}</p>
                      <p className="text-xs text-gray-500 mt-1">{t('settings.subscribePage.monthlyEquivalent')}{monthlyEquivalent.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}</p>
                    </>
                  ) : isFirstMonth ? (
                    <>
                      <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-3xl font-bold text-blue-600">
                          {discountedPrice.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}
                        </span>
                        <span className="text-gray-500 line-through text-lg">
                          {originalPrice.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}
                        </span>
                      </div>
                      <p className="text-xs text-green-600 font-semibold">{t('settings.subscribePage.firstMonthBadge')}</p>
                      <p className="text-xs text-gray-500 mt-1">{t('settings.subscribePage.nextMonthsPrice')} {originalPrice.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol} {i18n.language === 'tr' ? '/ay' : '/month'}</p>
                    </>
                  ) : (
                    <>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-blue-600">
                          {originalPrice.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {currencySymbol}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{t('settings.subscribePage.perMonth')}</p>
                    </>
                  )}
                </div>

                {/* Ana Özellik (Randevu Limiti) */}
                <div className="mb-4">
                  <p className="text-base font-semibold text-gray-900">
                    {plan.quota_monthly_appointments.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {t('settings.subscribePage.appointmentsPerMonth')}
                  </p>
                </div>

                {/* Diğer Özellikler */}
                <div className="flex-1 mb-6">
                  <ul className="space-y-2">
                    {plan.features && plan.features.map((feature, index) => (
                      <li key={index} className="flex items-start gap-2 text-sm text-gray-600">
                        <Check className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Aboneliği Başlat Butonu */}
                <Button
                  onClick={() => !isCurrentPlan && handleStartSubscription(plan.id)}
                  disabled={isProcessing || isCurrentPlan}
                  className={`w-full font-bold h-12 text-base rounded-lg ${
                    isCurrentPlan 
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed' 
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }`}
                >
                  {isCurrentPlan ? t('settings.subscribePage.currentSubscription') : isProcessing ? t('settings.subscribePage.processing') : t('settings.subscribePage.startSubscription')}
                </Button>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Subscribe;



