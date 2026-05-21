import { useState, useEffect } from "react";
import { ArrowLeft, Check, Globe, ExternalLink, Shield, CreditCard } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { openExternalUrl } from "../lib/openExternalUrl";
import { PRICING_DISPLAY, normalizePlanKey, getYearlyPrice } from "../lib/pricing";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import posthog from "../lib/posthog";
import metaPixel from "../lib/metaPixel";

const Subscribe = ({ onNavigate, currentUser, settings }) => {
  const { t, i18n } = useTranslation();
  const webUrl = i18n.language && i18n.language.toLowerCase().startsWith('en')
    ? 'https://plannapp.co.uk'
    : 'https://plannapp.co';
  const websiteSubscribeUrl = `${webUrl}/subscribe`;
  
  // M9: PRICING_DISPLAY ve plan key normalize'i artık tek kaynak `lib/pricing.js`
  // üzerinden geliyor (LandingPage.js da aynı modülü kullanır → drift önleme).

  /** Subscribe.js fallback için "standard" döner — pricing.js null dönerse. */
  const getPlanPricingKey = (planName) => normalizePlanKey(planName) || 'standard';
  
  // Plan isimleri çevirisi (i18n lookup; Trial → Deneme dahil)
  const getPlanName = (planName) => {
    if (!planName) return planName;
    const key = String(planName).toLowerCase();
    return t(`settings.subscriptionPage.planNames.${key}`, { defaultValue: planName });
  };
  
  // App Store Compliance: Mobil uygulamada (Android/iOS) ödeme sayfasını gizle
  // Sadece native platform kontrolü yap, localStorage kontrolü yapma (web'de ?mode=app ile giriş yapıldığında localStorage'a yazılıyor)
  const isAppMode = Capacitor.isNativePlatform();
  
  // Eğer app mode ise, sadece bilgilendirme mesajı göster
  if (isAppMode) {
    return (
      <div className="min-h-screen bg-white pb-20 flex items-center justify-center" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 w-full max-w-md">
          <Card className="bg-white shadow-xl border border-gray-200 rounded-3xl p-8 mx-auto text-center">
            <div>
              <div className="mx-auto mb-6 w-16 h-16 rounded-2xl border border-gray-200 flex items-center justify-center bg-white">
                <Globe className="w-8 h-8 text-gray-900" />
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
                onClick={async () => {
                  try {
                    const resp = await api.post('/sso/create');
                    const code = resp?.data?.code;
                    const ssoUrl = `${webUrl}/sso?code=${encodeURIComponent(code || '')}&redirect=${encodeURIComponent('/subscribe')}`;
                    await openExternalUrl(ssoUrl);
                  } catch (e) {
                    await openExternalUrl(websiteSubscribeUrl);
                  }
                }}
                className="w-full bg-gray-900 hover:bg-gray-800 text-white font-semibold py-6 rounded-2xl shadow-md transition-colors flex items-center justify-center gap-2"
              >
                <ExternalLink className="w-5 h-5" />
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

          <div className="mt-4 text-center text-xs text-gray-500">
            {webUrl.replace('https://', '')}
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
        api.get("/plans", { headers: { 'Accept-Language': i18n.language } }),
        api.get("/plan/current")
      ]);
      
      // Sadece 3 paket göster: Standart, Profesyonel, Kurumsal
      const VISIBLE_PLANS = ['standart', 'standard', 'profesyonel', 'professional', 'kurumsal', 'corporate'];
      const paidPlans = plansResponse.data.plans.filter(plan =>
        plan.id !== 'tier_trial' && VISIBLE_PLANS.includes(plan.name.toLowerCase())
      );
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

      // Funnel: subscription_checkout_started — checkout URL'sine yönlendirmeden ÖNCE
      try {
        posthog.track('subscription_checkout_started', {
          plan_id: planId,
          billing_cycle: billingCycle,
          currency,
          platform,
        });
      } catch (_) {}

      // Meta: InitiateCheckout — fiyat bilgisi tahminî, currency uppercase.
      const planMeta = plans.find((p) => p.id === planId);
      const pricingKey = planMeta ? getPlanPricingKey(planMeta.name) : null;
      const pricingDisplay = pricingKey ? PRICING_DISPLAY[currency]?.[pricingKey] : null;
      const checkoutValue = pricingDisplay?.discounted ?? pricingDisplay?.original;
      try {
        metaPixel.track('InitiateCheckout', {
          customData: {
            content_name: planMeta?.name || planId,
            content_ids: [planId],
            content_type: 'subscription',
            value: checkoutValue,
            currency: currency.toUpperCase(),
            num_items: 1,
          },
          userData: {
            contact_email: currentUser?.username,
            contact_phone: settings?.support_phone,
            contact_name: currentUser?.full_name,
            external_id: currentUser?.user_id,
          },
        });
      } catch (_) {}

      const response = await api.post("/payments/create-checkout-session", {
        plan_id: planId,
        billing_cycle: billingCycle,
        platform: platform,
        currency: currency
      });
      
      if (response.data && response.data.checkout_url) {
        // Meta: AddPaymentInfo — Stripe Checkout sayfası açılmadan hemen önce.
        try {
          metaPixel.track('AddPaymentInfo', {
            customData: {
              content_name: planMeta?.name || planId,
              content_ids: [planId],
              content_type: 'subscription',
              value: checkoutValue,
              currency: currency.toUpperCase(),
            },
            userData: {
              contact_email: currentUser?.username,
              contact_phone: settings?.support_phone,
              contact_name: currentUser?.full_name,
              external_id: currentUser?.user_id,
            },
          });
        } catch (_) {}

        // Stripe Checkout sayfasına yönlendir:
        //  - Native (Capacitor): App.openUrl() ile sistem tarayıcısı (Plan 12.4
        //    fallback'i ile birlikte).
        //  - Web: aynı sekmede window.location.href ile yönlendir. Async POST
        //    sonrası window.open(_blank) çağrısı çoğu mobil tarayıcıda popup
        //    blocker'a takılıyor (user gesture'dan kopuk); "Aboneliği Başlat"
        //    butonuna basınca hiçbir şey olmuyor gibi görünüyordu (Sorun 3).
        //    Aynı sekmede yönlendirme = popup engellenmiyor + Stripe başarı
        //    sayfası geri yönlendiriyor.
        const checkoutUrl = response.data.checkout_url;
        if (Capacitor.isNativePlatform()) {
          await openExternalUrl(checkoutUrl);
        } else {
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
    <div className="min-h-screen bg-[#fafafa] pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* Geri butonu — uygulama içi top-bar */}
      <div className="container mx-auto px-4 pt-6">
        <button
          onClick={() => onNavigate && onNavigate("settings")}
          className="flex items-center gap-2 text-gray-700 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="text-sm font-medium">{t('settings.subscribePage.back')}</span>
        </button>
      </div>

      {/* Section header (LandingPage pricing ile birebir tipografi ama mobile-first) */}
      <section className="pt-2 md:pt-8 pb-10 md:pb-16">
        <div className="container mx-auto px-4">
          <div className="text-center max-w-2xl mx-auto mb-8 md:mb-14">
            <span className="inline-block text-xs md:text-base font-semibold uppercase tracking-[0.18em] md:tracking-[0.22em] text-gray-500 mb-3 md:mb-4">
              {t('settings.subscribePage.title')}
            </span>
            <h2 className="text-3xl md:text-4xl lg:text-[3.5rem] font-bold tracking-tight text-gray-900 leading-[1.1] md:leading-[1.05] mb-4 md:mb-5">
              {t('landing.pricing.title', { defaultValue: 'Size uygun planı seçin' })}
            </h2>
            <p className="text-sm md:text-lg text-gray-500 leading-relaxed">
              {t('settings.subscribePage.subtitle')}
            </p>

            {/* Billing toggle — Segmented pill (LandingPage ile aynı) */}
            <div className="mt-6 md:mt-9 flex flex-wrap items-center justify-center gap-x-4 md:gap-x-5 gap-y-3">
              <div className="inline-flex items-center gap-1 p-1 rounded-full bg-white border border-gray-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                <button
                  type="button"
                  onClick={() => setBillingCycle('monthly')}
                  aria-pressed={billingCycle === 'monthly'}
                  className={`px-5 py-2 text-sm font-semibold rounded-full transition-all duration-200 ${
                    billingCycle === 'monthly'
                      ? 'bg-gray-900 text-white shadow-[0_2px_8px_rgba(17,24,39,0.18)]'
                      : 'text-gray-500 hover:text-gray-900'
                  }`}
                >
                  {t('settings.subscribePage.monthly')}
                </button>
                <button
                  type="button"
                  onClick={() => setBillingCycle('yearly')}
                  aria-pressed={billingCycle === 'yearly'}
                  className={`px-5 py-2 text-sm font-semibold rounded-full transition-all duration-200 ${
                    billingCycle === 'yearly'
                      ? 'bg-gray-900 text-white shadow-[0_2px_8px_rgba(17,24,39,0.18)]'
                      : 'text-gray-500 hover:text-gray-900'
                  }`}
                >
                  {t('settings.subscribePage.yearly')}
                </button>
              </div>

              <span className="inline-flex items-center gap-2 text-sm text-gray-600">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {billingCycle === 'yearly'
                  ? t('settings.subscribePage.twoMonthsFree')
                  : (currentPlan?.is_first_month
                      ? t('settings.subscribePage.firstMonthDiscount')
                      : t('landing.pricing.newUserDiscount', { defaultValue: 'Yeni kullanıcılara özel indirim' }))}
              </span>
            </div>
          </div>

          {/* Plan kartları */}
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-2 border-gray-200 border-t-gray-900 mx-auto"></div>
              <p className="mt-4 text-sm text-gray-500">{t('common.loading')}</p>
            </div>
          ) : plans.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600">{t('landing.pricing.noPlans', { defaultValue: 'Planlar yükleniyor...' })}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 lg:gap-6 max-w-6xl mx-auto items-stretch">
              {plans.map((plan) => {
                const isPopular = plan.id === 'tier_4_business';
                const isYearly = billingCycle === 'yearly';
                const isFirstMonth = !isYearly && currentPlan && currentPlan.is_first_month;

                const currency = i18n.language === 'en' ? 'gbp' : 'try';
                const currencySymbol = currency === 'try' ? '₺' : '£';
                const planKey = getPlanPricingKey(plan.name);
                const cell = PRICING_DISPLAY[currency]?.[planKey];

                // Görüntülenecek fiyat ve eski (üzeri çizili) fiyat seçimi
                let displayPrice, originalPrice, showStrike, savingsLabel;
                if (isYearly) {
                  const yearlyTotal = getYearlyPrice(currency, planKey);
                  displayPrice = Math.round(yearlyTotal / 12); // ay başına denk gelen
                  originalPrice = cell?.original; // aylık (12 ay × original karşılaştırması bonus)
                  showStrike = true;
                  savingsLabel = t('settings.subscribePage.twoMonthsFree');
                } else if (isFirstMonth) {
                  displayPrice = cell?.discounted;
                  originalPrice = cell?.original;
                  showStrike = true;
                  savingsLabel = t('settings.subscribePage.firstMonthBadge');
                } else {
                  displayPrice = cell?.original;
                  originalPrice = null;
                  showStrike = false;
                  savingsLabel = null;
                }

                const localeCode = i18n.language === 'tr' ? 'tr-TR' : 'en-GB';
                const isProcessing = processingPlanId === plan.id;
                const isCurrentPlan = currentPlan && currentPlan.plan_id === plan.id;

                return (
                  <div
                    key={plan.id}
                    className={`relative flex flex-col rounded-[20px] md:rounded-[24px] p-5 md:p-8 lg:p-10 transition-all duration-300 ease-out ${
                      isPopular
                        ? 'bg-gray-900 text-white ring-1 ring-gray-900 shadow-[0_24px_60px_-18px_rgba(17,24,39,0.4)]'
                        : 'bg-white text-gray-900 ring-1 ring-gray-200/80 hover:ring-gray-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-12px_rgba(17,24,39,0.12)]'
                    } ${isCurrentPlan ? 'ring-2 ring-emerald-500' : ''}`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="inline-flex items-center gap-1.5 bg-white text-gray-900 text-[10px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-full shadow-[0_4px_12px_rgba(0,0,0,0.08)] ring-1 ring-gray-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                          {t('landing.pricing.mostPopular', { defaultValue: 'En popüler' })}
                        </span>
                      </div>
                    )}

                    {isCurrentPlan && !isPopular && (
                      <div className="absolute -top-3 right-4">
                        <span className="inline-flex items-center gap-1.5 bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-full shadow-[0_4px_12px_rgba(16,185,129,0.25)]">
                          {t('settings.subscribePage.currentSubscription')}
                        </span>
                      </div>
                    )}

                    {/* Plan adı + açıklama */}
                    <div>
                      <h3 className={`text-xl md:text-2xl font-bold tracking-tight ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                        {getPlanName(plan.name)}
                      </h3>
                      <p className={`text-sm md:text-[15px] mt-2 leading-relaxed ${isPopular ? 'text-gray-400' : 'text-gray-500'}`}>
                        {t(`landing.pricing.plans.${plan.name.toLowerCase()}.description`, { defaultValue: plan.target_audience_tr || '' })}
                      </p>
                    </div>

                    {/* Fiyat */}
                    <div className="mt-6 md:mt-8 mb-5 md:mb-7">
                      <div className="flex items-baseline">
                        <span className={`text-xl md:text-2xl font-medium ${isPopular ? 'text-gray-500' : 'text-gray-400'}`}>
                          {currencySymbol}
                        </span>
                        <span className={`text-[2.75rem] md:text-[3.5rem] lg:text-[4rem] font-bold tracking-[-0.04em] tabular-nums leading-none ml-0.5 ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                          {(displayPrice ?? 0).toLocaleString(localeCode)}
                        </span>
                        <span className={`text-sm ml-2 ${isPopular ? 'text-gray-500' : 'text-gray-500'}`}>
                          {t('landing.pricing.perMonth', { defaultValue: '/ay' })}
                        </span>
                      </div>
                      {showStrike && originalPrice ? (
                        <div className="mt-3 flex items-center gap-2 text-sm">
                          <span className={`line-through ${isPopular ? 'text-gray-600' : 'text-gray-400'}`}>
                            {currencySymbol}{(isYearly ? originalPrice : originalPrice).toLocaleString(localeCode)}
                          </span>
                          {savingsLabel && (
                            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                              isPopular
                                ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20'
                                : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100'
                            }`}>
                              {savingsLabel}
                            </span>
                          )}
                        </div>
                      ) : (
                        <p className={`mt-2 text-sm ${isPopular ? 'text-gray-400' : 'text-gray-500'}`}>
                          {isYearly
                            ? t('landing.pricing.yearlyBilling', { defaultValue: 'Yıllık faturalandırma' })
                            : t('landing.pricing.monthlyBilling', { defaultValue: 'Aylık faturalandırma' })}
                        </p>
                      )}
                    </div>

                    {/* CTA */}
                    <button
                      type="button"
                      onClick={() => !isCurrentPlan && handleStartSubscription(plan.id)}
                      disabled={isProcessing || isCurrentPlan}
                      className={`w-full py-3.5 md:py-4 rounded-xl md:rounded-2xl font-semibold text-sm md:text-base transition-all duration-200 active:scale-[0.99] disabled:cursor-not-allowed ${
                        isCurrentPlan
                          ? 'bg-gray-100 text-gray-400 ring-1 ring-gray-200'
                          : isPopular
                            ? 'bg-white text-gray-900 hover:bg-gray-100 shadow-[0_4px_14px_rgba(255,255,255,0.12)] disabled:opacity-60'
                            : 'bg-gray-900 text-white hover:bg-gray-800 shadow-[0_4px_14px_rgba(17,24,39,0.15)] disabled:opacity-60'
                      }`}
                    >
                      {isCurrentPlan
                        ? t('settings.subscribePage.currentSubscription')
                        : isProcessing
                          ? t('settings.subscribePage.processing')
                          : t('settings.subscribePage.startSubscription')}
                    </button>

                    {/* Divider */}
                    <div className={`mt-6 md:mt-8 mb-5 md:mb-6 h-px ${isPopular ? 'bg-white/[0.08]' : 'bg-gray-100'}`}></div>

                    {/* "What's included" label */}
                    <p className={`text-[10px] md:text-xs font-semibold uppercase tracking-[0.16em] mb-3 md:mb-4 ${isPopular ? 'text-gray-500' : 'text-gray-400'}`}>
                      {t('landing.pricing.includes', { defaultValue: 'Dahil olanlar' })}
                    </p>

                    {/* Quota highlight */}
                    <div className={`mb-4 md:mb-5 p-3.5 md:p-4 rounded-xl md:rounded-2xl ${
                      isPopular ? 'bg-white/[0.04] ring-1 ring-white/10' : 'bg-gray-50 ring-1 ring-gray-100'
                    }`}>
                      <div className={`text-base md:text-xl font-bold tracking-tight ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                        {['kurumsal', 'corporate'].includes(plan.name.toLowerCase())
                          ? (i18n.language === 'tr' ? 'Sınırsız Randevu' : 'Unlimited Appointments')
                          : `${plan.quota_monthly_appointments.toLocaleString(localeCode)} ${t('settings.subscribePage.appointmentsPerMonth')}`}
                      </div>
                      <div className={`text-xs mt-1 ${isPopular ? 'text-gray-500' : 'text-gray-500'}`}>
                        {t('landing.pricing.monthlyLimit', { defaultValue: 'Aylık limit' })}
                      </div>
                    </div>

                    {/* Features list */}
                    <ul className="space-y-2.5 md:space-y-3 flex-1">
                      {plan.features &&
                        plan.features
                          .filter((feature) => {
                            const quotaStr = plan.quota_monthly_appointments.toLocaleString('tr-TR');
                            return !(feature.includes(quotaStr) && feature.toLowerCase().includes('randevu'));
                          })
                          .map((feature, i) => (
                            <li key={i} className="flex items-start gap-2.5 md:gap-3 text-sm md:text-[15px] leading-relaxed">
                              <Check
                                className={`w-4 h-4 md:w-5 md:h-5 flex-shrink-0 mt-0.5 ${isPopular ? 'text-emerald-400' : 'text-emerald-600'}`}
                                strokeWidth={2.5}
                              />
                              <span className={isPopular ? 'text-gray-300' : 'text-gray-600'}>{feature}</span>
                            </li>
                          ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}

          {/* Trust bar (LandingPage ile aynı) */}
          {!loading && plans.length > 0 && (
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-x-10 gap-y-3 text-xs text-gray-500">
              <div className="inline-flex items-center gap-2">
                <Shield className="w-4 h-4 text-gray-500" />
                {t('landing.pricing.trustBadge', { defaultValue: 'Güvenli ödeme — Stripe altyapısı' })}
              </div>
              <div className="inline-flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-gray-500" />
                {t('landing.pricing.securePayment', { defaultValue: 'Tüm büyük kartlar' })}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default Subscribe;



