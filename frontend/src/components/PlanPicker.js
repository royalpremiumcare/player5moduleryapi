import { useState, useEffect, useCallback } from "react";
import { ArrowLeft, Check, Shield, CreditCard } from "lucide-react";
import { Card } from "@/components/ui/card";
import api from "../api/api";
import { Capacitor } from "@capacitor/core";
import { PRICING_DISPLAY, normalizePlanKey, getYearlyPrice } from "../lib/pricing";
import {
  openCheckoutInAppBrowser,
  startCheckoutWatch,
  abortCheckoutWatch,
  subscribeCheckoutEvents,
} from "../lib/inAppSubscribe";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import posthog from "../lib/posthog";
import metaPixel from "../lib/metaPixel";

const VISIBLE_PLANS = ["standart", "standard", "profesyonel", "professional", "kurumsal", "corporate"];

const getPlanPricingKey = (planName) => normalizePlanKey(planName) || "standard";

const PlanPicker = ({ onNavigate, currentUser, settings }) => {
  const { t, i18n } = useTranslation();
  const [plans, setPlans] = useState([]);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processingPlanId, setProcessingPlanId] = useState(null);
  const [billingCycle, setBillingCycle] = useState("monthly");

  const getPlanName = (planName) => {
    if (!planName) return planName;
    const key = String(planName).toLowerCase();
    return t(`settings.subscriptionPage.planNames.${key}`, { defaultValue: planName });
  };

  const loadPlans = useCallback(async () => {
    try {
      const [plansResponse, currentPlanResponse] = await Promise.all([
        api.get("/plans", { headers: { "Accept-Language": i18n.language } }),
        api.get("/plan/current"),
      ]);

      const paidPlans = plansResponse.data.plans.filter(
        (plan) => plan.id !== "tier_trial" && VISIBLE_PLANS.includes(plan.name.toLowerCase())
      );
      setPlans(paidPlans);
      setCurrentPlan(currentPlanResponse.data);
      return currentPlanResponse.data;
    } catch (error) {
      console.error("Planlar yüklenemedi:", error);
      toast.error(t("settings.subscribePage.plansLoadError"));
      return null;
    } finally {
      setLoading(false);
    }
  }, [i18n.language, t]);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get("session_id");
    if (!sessionId) return;

    toast.success(t("settings.subscribePage.paymentSuccess"), { duration: 5000 });
    api
      .post("/payments/confirm-checkout-session", { session_id: sessionId })
      .finally(() => {
        setTimeout(() => {
          loadPlans();
        }, 1000);
      });
    window.history.replaceState({}, document.title, window.location.pathname);
  }, [loadPlans, t]);

  useEffect(() => {
    return subscribeCheckoutEvents((event) => {
      if (event.type === "upgraded" || event.type === "unresolved" || event.type === "dismissed" || event.type === "browser-finished") {
        setProcessingPlanId(null);
      }
      if (event.type === "upgraded") {
        loadPlans();
      }
      if (event.type === "unresolved" && (event.elapsedMs || 0) > 8000) {
        toast.message(t("settings.subscribePage.paymentMayStillActivate"));
        loadPlans();
      }
      if (event.type === "dismissed") {
        loadPlans();
      }
    });
  }, [loadPlans, t]);

  const handleStartSubscription = async (planId) => {
    setProcessingPlanId(planId);
    try {
      const platform = Capacitor.isNativePlatform()
        ? Capacitor.getPlatform() === "ios"
          ? "ios"
          : "android"
        : "web";

      const currency = i18n.language === "en" ? "gbp" : "try";

      try {
        posthog.track("subscription_checkout_started", {
          plan_id: planId,
          billing_cycle: billingCycle,
          currency,
          platform,
        });
      } catch (_) {}

      const planMeta = plans.find((p) => p.id === planId);
      const pricingKey = planMeta ? getPlanPricingKey(planMeta.name) : null;
      const pricingDisplay = pricingKey ? PRICING_DISPLAY[currency]?.[pricingKey] : null;
      const checkoutValue = pricingDisplay?.discounted ?? pricingDisplay?.original;
      try {
        metaPixel.track("InitiateCheckout", {
          customData: {
            content_name: planMeta?.name || planId,
            content_ids: [planId],
            content_type: "subscription",
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
        platform,
        currency,
      });

      if (response.data && response.data.checkout_url) {
        try {
          metaPixel.track("AddPaymentInfo", {
            customData: {
              content_name: planMeta?.name || planId,
              content_ids: [planId],
              content_type: "subscription",
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

        const checkoutUrl = response.data.checkout_url;
        const sessionId = response.data.session_id;

        if (Capacitor.isNativePlatform()) {
          startCheckoutWatch({ sessionId, baseline: currentPlan });
          try {
            await openCheckoutInAppBrowser(checkoutUrl);
          } catch (err) {
            console.error("In-App Browser açılamadı:", err);
            abortCheckoutWatch();
            toast.error(t("settings.subscribePage.inAppBrowserError"));
            setProcessingPlanId(null);
          }
        } else {
          window.location.href = checkoutUrl;
        }
      } else {
        toast.error(t("settings.subscribePage.paymentPageError"));
        setProcessingPlanId(null);
      }
    } catch (error) {
      console.error("Ödeme işlemi başlatılamadı:", error);
      const errorMessage =
        error.response?.data?.detail || error.message || t("settings.subscribePage.paymentError");
      toast.error(errorMessage);
      setProcessingPlanId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <p className="text-sm text-gray-600">{t("settings.subscribePage.loading")}</p>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#fafafa] pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
      <div className="container mx-auto px-4 pt-6">
        <button
          onClick={() => onNavigate && onNavigate("settings")}
          className="flex items-center gap-2 text-gray-700 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="text-sm font-medium">{t("settings.subscribePage.back")}</span>
        </button>
      </div>

      <section className="pt-2 md:pt-8 pb-10 md:pb-16">
        <div className="container mx-auto px-4">
          <div className="text-center max-w-2xl mx-auto mb-8 md:mb-14">
            <span className="inline-block text-xs md:text-base font-semibold uppercase tracking-[0.18em] md:tracking-[0.22em] text-gray-500 mb-3 md:mb-4">
              {t("settings.subscribePage.title")}
            </span>
            <h2 className="text-3xl md:text-4xl lg:text-[3.5rem] font-bold tracking-tight text-gray-900 leading-[1.1] md:leading-[1.05] mb-4 md:mb-5">
              {t("landing.pricing.title", { defaultValue: "Size uygun planı seçin" })}
            </h2>
            <p className="text-sm md:text-lg text-gray-500 leading-relaxed">
              {t("settings.subscribePage.subtitle")}
            </p>

            <div className="mt-6 md:mt-9 flex flex-wrap items-center justify-center gap-x-4 md:gap-x-5 gap-y-3">
              <div className="inline-flex items-center gap-1 p-1 rounded-full bg-white border border-gray-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                <button
                  type="button"
                  onClick={() => setBillingCycle("monthly")}
                  aria-pressed={billingCycle === "monthly"}
                  className={`px-5 py-2 text-sm font-semibold rounded-full transition-all duration-200 ${
                    billingCycle === "monthly"
                      ? "bg-gray-900 text-white shadow-[0_2px_8px_rgba(17,24,39,0.18)]"
                      : "text-gray-500 hover:text-gray-900"
                  }`}
                >
                  {t("settings.subscribePage.monthly")}
                </button>
                <button
                  type="button"
                  onClick={() => setBillingCycle("yearly")}
                  aria-pressed={billingCycle === "yearly"}
                  className={`px-5 py-2 text-sm font-semibold rounded-full transition-all duration-200 ${
                    billingCycle === "yearly"
                      ? "bg-gray-900 text-white shadow-[0_2px_8px_rgba(17,24,39,0.18)]"
                      : "text-gray-500 hover:text-gray-900"
                  }`}
                >
                  {t("settings.subscribePage.yearly")}
                </button>
              </div>

              <span className="inline-flex items-center gap-2 text-sm text-gray-600">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {billingCycle === "yearly"
                  ? t("settings.subscribePage.twoMonthsFree")
                  : currentPlan?.is_first_month
                    ? t("settings.subscribePage.firstMonthDiscount")
                    : t("landing.pricing.newUserDiscount", { defaultValue: "Yeni kullanıcılara özel indirim" })}
              </span>
            </div>
          </div>

          {plans.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600">{t("landing.pricing.noPlans", { defaultValue: "Planlar yükleniyor..." })}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 lg:gap-6 max-w-6xl mx-auto items-stretch">
              {plans.map((plan) => {
                const isPopular = plan.id === "tier_4_business";
                const isYearly = billingCycle === "yearly";
                const isFirstMonth = !isYearly && currentPlan && currentPlan.is_first_month;

                const currency = i18n.language === "en" ? "gbp" : "try";
                const currencySymbol = currency === "try" ? "₺" : "£";
                const planKey = getPlanPricingKey(plan.name);
                const cell = PRICING_DISPLAY[currency]?.[planKey];

                let displayPrice;
                let originalPrice;
                let showStrike;
                let savingsLabel;
                if (isYearly) {
                  displayPrice = getYearlyPrice(currency, planKey);
                  originalPrice = (cell?.original ?? 0) * 12;
                  showStrike = true;
                  savingsLabel = t("settings.subscribePage.twoMonthsFree");
                } else if (isFirstMonth) {
                  displayPrice = cell?.discounted;
                  originalPrice = cell?.original;
                  showStrike = true;
                  savingsLabel = t("settings.subscribePage.firstMonthBadge");
                } else {
                  displayPrice = cell?.original;
                  originalPrice = null;
                  showStrike = false;
                  savingsLabel = null;
                }

                const localeCode = i18n.language === "tr" ? "tr-TR" : "en-GB";
                const isProcessing = processingPlanId === plan.id;
                const currentCycle = currentPlan?.is_yearly ? "yearly" : "monthly";
                const isCurrentPlan =
                  !!currentPlan && currentPlan.plan_id === plan.id && billingCycle === currentCycle;
                const isCycleSwitch =
                  !!currentPlan && currentPlan.plan_id === plan.id && billingCycle !== currentCycle;

                return (
                  <div
                    key={plan.id}
                    className={`relative flex flex-col rounded-[20px] md:rounded-[24px] p-5 md:p-8 lg:p-10 transition-all duration-300 ease-out ${
                      isPopular
                        ? "bg-gray-900 text-white ring-1 ring-gray-900 shadow-[0_24px_60px_-18px_rgba(17,24,39,0.4)]"
                        : "bg-white text-gray-900 ring-1 ring-gray-200/80 hover:ring-gray-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-12px_rgba(17,24,39,0.12)]"
                    } ${isCurrentPlan ? "ring-2 ring-emerald-500" : ""}`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="inline-flex items-center gap-1.5 bg-white text-gray-900 text-[10px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-full shadow-[0_4px_12px_rgba(0,0,0,0.08)] ring-1 ring-gray-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                          {t("landing.pricing.mostPopular", { defaultValue: "En popüler" })}
                        </span>
                      </div>
                    )}

                    {isCurrentPlan && !isPopular && (
                      <div className="absolute -top-3 right-4">
                        <span className="inline-flex items-center gap-1.5 bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-full shadow-[0_4px_12px_rgba(16,185,129,0.25)]">
                          {t("settings.subscribePage.currentSubscription")}
                        </span>
                      </div>
                    )}

                    <div>
                      <h3 className={`text-xl md:text-2xl font-bold tracking-tight ${isPopular ? "text-white" : "text-gray-900"}`}>
                        {getPlanName(plan.name)}
                      </h3>
                      <p className={`text-sm md:text-[15px] mt-2 leading-relaxed ${isPopular ? "text-gray-400" : "text-gray-500"}`}>
                        {t(`landing.pricing.plans.${plan.name.toLowerCase()}.description`, {
                          defaultValue: plan.target_audience_tr || "",
                        })}
                      </p>
                    </div>

                    <div className="mt-6 md:mt-8 mb-5 md:mb-7">
                      <div className="flex items-baseline">
                        <span className={`text-xl md:text-2xl font-medium ${isPopular ? "text-gray-500" : "text-gray-400"}`}>
                          {currencySymbol}
                        </span>
                        <span
                          className={`text-[2.75rem] md:text-[3.5rem] lg:text-[4rem] font-bold tracking-[-0.04em] tabular-nums leading-none ml-0.5 ${
                            isPopular ? "text-white" : "text-gray-900"
                          }`}
                        >
                          {(displayPrice ?? 0).toLocaleString(localeCode)}
                        </span>
                        <span className={`text-sm ml-2 ${isPopular ? "text-gray-500" : "text-gray-500"}`}>
                          {isYearly
                            ? t("landing.pricing.perYear", { defaultValue: "/yıl" })
                            : t("landing.pricing.perMonth", { defaultValue: "/ay" })}
                        </span>
                      </div>
                      {showStrike && originalPrice ? (
                        <div className="mt-3 flex items-center gap-2 text-sm">
                          <span className={`line-through ${isPopular ? "text-gray-600" : "text-gray-400"}`}>
                            {currencySymbol}
                            {originalPrice.toLocaleString(localeCode)}
                          </span>
                          {savingsLabel && (
                            <span
                              className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                                isPopular
                                  ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20"
                                  : "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100"
                              }`}
                            >
                              {savingsLabel}
                            </span>
                          )}
                        </div>
                      ) : (
                        <p className={`mt-2 text-sm ${isPopular ? "text-gray-400" : "text-gray-500"}`}>
                          {isYearly
                            ? t("landing.pricing.yearlyBilling", { defaultValue: "Yıllık faturalandırma" })
                            : t("landing.pricing.monthlyBilling", { defaultValue: "Aylık faturalandırma" })}
                        </p>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => !isCurrentPlan && handleStartSubscription(plan.id)}
                      disabled={isProcessing || isCurrentPlan}
                      className={`w-full py-3.5 md:py-4 rounded-xl md:rounded-2xl font-semibold text-sm md:text-base transition-all duration-200 active:scale-[0.99] disabled:cursor-not-allowed ${
                        isCurrentPlan
                          ? "bg-gray-100 text-gray-400 ring-1 ring-gray-200"
                          : isPopular
                            ? "bg-white text-gray-900 hover:bg-gray-100 shadow-[0_4px_14px_rgba(255,255,255,0.12)] disabled:opacity-60"
                            : "bg-gray-900 text-white hover:bg-gray-800 shadow-[0_4px_14px_rgba(17,24,39,0.15)] disabled:opacity-60"
                      }`}
                    >
                      {isCurrentPlan
                        ? t("settings.subscribePage.currentSubscription")
                        : isProcessing
                          ? t("settings.subscribePage.processing")
                          : isCycleSwitch
                            ? billingCycle === "yearly"
                              ? t("settings.subscribePage.switchToYearly")
                              : t("settings.subscribePage.switchToMonthly")
                            : t("settings.subscribePage.startSubscription")}
                    </button>

                    <div className={`mt-6 md:mt-8 mb-5 md:mb-6 h-px ${isPopular ? "bg-white/[0.08]" : "bg-gray-100"}`}></div>

                    <p
                      className={`text-[10px] md:text-xs font-semibold uppercase tracking-[0.16em] mb-3 md:mb-4 ${
                        isPopular ? "text-gray-500" : "text-gray-400"
                      }`}
                    >
                      {t("landing.pricing.includes", { defaultValue: "Dahil olanlar" })}
                    </p>

                    <div
                      className={`mb-4 md:mb-5 p-3.5 md:p-4 rounded-xl md:rounded-2xl ${
                        isPopular ? "bg-white/[0.04] ring-1 ring-white/10" : "bg-gray-50 ring-1 ring-gray-100"
                      }`}
                    >
                      <div className={`text-base md:text-xl font-bold tracking-tight ${isPopular ? "text-white" : "text-gray-900"}`}>
                        {["kurumsal", "corporate"].includes(plan.name.toLowerCase())
                          ? i18n.language === "tr"
                            ? "Sınırsız Randevu"
                            : "Unlimited Appointments"
                          : `${plan.quota_monthly_appointments.toLocaleString(localeCode)} ${t("settings.subscribePage.appointmentsPerMonth")}`}
                      </div>
                      <div className={`text-xs mt-1 ${isPopular ? "text-gray-500" : "text-gray-500"}`}>
                        {t("landing.pricing.monthlyLimit", { defaultValue: "Aylık limit" })}
                      </div>
                    </div>

                    <ul className="space-y-2.5 md:space-y-3 flex-1">
                      {plan.features &&
                        plan.features
                          .filter((feature) => {
                            const quotaStr = plan.quota_monthly_appointments.toLocaleString("tr-TR");
                            return !(feature.includes(quotaStr) && feature.toLowerCase().includes("randevu"));
                          })
                          .map((feature, i) => (
                            <li key={i} className="flex items-start gap-2.5 md:gap-3 text-sm md:text-[15px] leading-relaxed">
                              <Check
                                className={`w-4 h-4 md:w-5 md:h-5 flex-shrink-0 mt-0.5 ${isPopular ? "text-emerald-400" : "text-emerald-600"}`}
                                strokeWidth={2.5}
                              />
                              <span className={isPopular ? "text-gray-300" : "text-gray-600"}>{feature}</span>
                            </li>
                          ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}

          {plans.length > 0 && (
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-x-10 gap-y-3 text-xs text-gray-500">
              <div className="inline-flex items-center gap-2">
                <Shield className="w-4 h-4 text-gray-500" />
                {t("landing.pricing.trustBadge", { defaultValue: "Güvenli ödeme — Stripe altyapısı" })}
              </div>
              <div className="inline-flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-gray-500" />
                {t("landing.pricing.securePayment", { defaultValue: "Tüm büyük kartlar" })}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default PlanPicker;
