import { useState, useEffect } from "react";
import { ArrowLeft, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "../api/api";
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { toast } from "sonner";

const Subscribe = ({ onNavigate }) => {
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
      toast.success("🎉 Ödeme başarılı! Planınız güncellendi.", {
        duration: 5000,
      });
      
      // URL'den session_id'yi temizle
      window.history.replaceState({}, document.title, window.location.pathname);
      
      // Planı yeniden yükle
      setTimeout(() => {
        loadPlans();
      }, 1000);
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
      toast.error("Planlar yüklenemedi");
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
      
      const response = await api.post("/payments/create-checkout-session", {
        plan_id: planId,
        billing_cycle: billingCycle,
        platform: platform
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
        toast.error("Ödeme sayfası oluşturulamadı");
        setProcessingPlanId(null);
      }
    } catch (error) {
      console.error("Ödeme işlemi başlatılamadı:", error);
      const errorMessage = error.response?.data?.detail || error.message || "Ödeme işlemi başlatılamadı";
      toast.error(errorMessage);
      setProcessingPlanId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: 'Inter, sans-serif' }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <p className="text-sm text-gray-600">Planlar yükleniyor...</p>
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
          <span className="text-sm font-medium">Geri Dön</span>
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Abonelik Paketleri</h1>
        <p className="text-sm text-gray-600 mt-1">Size uygun paketi seçin</p>
        
        {/* Aylık / Yıllık Toggle */}
        <div className="flex items-center justify-center gap-3 mt-6">
          <span className={`text-base font-medium ${billingCycle === 'monthly' ? 'text-gray-900' : 'text-gray-400'}`}>
            Aylık
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
              Yıllık
            </span>
            {billingCycle === 'yearly' && (
              <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap">
                2 Ay Ücretsiz
              </span>
            )}
          </div>
        </div>
      </div>

      {/* İndirim Banner - Sadece aylık ve ilk ay için göster */}
      {billingCycle === 'monthly' && currentPlan && currentPlan.is_first_month && (
        <div className="px-4 pb-4">
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl p-6 shadow-lg">
            <h2 className="text-xl font-bold mb-2">🎉 İlk Aya Özel %25 İndirim!</h2>
            <p className="text-sm text-blue-50">
              İlk ay özel fırsatı! Seçtiğiniz paketin ilk ay ödemesi <strong>%25 indirimli</strong>.
            </p>
            <p className="text-sm text-blue-50 mt-2">
              <strong>Sonraki aylarda</strong> normal fiyattan otomatik olarak tahsilat yapılacaktır.
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
            
            // Yıllık fiyat hesaplama
            const yearlyPrice = plan.price_yearly || (plan.price_monthly * 10);
            const monthlyEquivalent = Math.round(yearlyPrice / 12);
            
            // Aylık fiyat hesaplama
            const discountedPrice = isFirstMonth ? Math.round(plan.price_monthly * 0.75) : plan.price_monthly;
            const originalPrice = plan.price_monthly;
            
            const isProcessing = processingPlanId === plan.id;
            const isCurrentPlan = currentPlan && currentPlan.plan_id === plan.id;

            return (
              <Card
                key={plan.id}
                className="bg-white shadow-md border border-gray-200 rounded-xl p-6 flex flex-col"
              >
                {/* Paket Adı */}
                <h3 className="text-xl font-bold text-gray-900 mb-4">{plan.name}</h3>

                {/* Fiyat */}
                <div className="mb-4">
                  {isYearly ? (
                    <>
                      <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-3xl font-bold text-blue-600">
                          {yearlyPrice.toLocaleString('tr-TR')} ₺
                        </span>
                        <span className="text-gray-500 line-through text-lg">
                          {(originalPrice * 12).toLocaleString('tr-TR')} ₺
                        </span>
                      </div>
                      <p className="text-xs text-green-600 font-semibold">Yıllık (2 ay ücretsiz)</p>
                      <p className="text-xs text-gray-500 mt-1">Aylık karşılığı: ~{monthlyEquivalent.toLocaleString('tr-TR')} ₺</p>
                    </>
                  ) : isFirstMonth ? (
                    <>
                      <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-3xl font-bold text-blue-600">
                          {discountedPrice.toLocaleString('tr-TR')} ₺
                        </span>
                        <span className="text-gray-500 line-through text-lg">
                          {originalPrice.toLocaleString('tr-TR')} ₺
                        </span>
                      </div>
                      <p className="text-xs text-green-600 font-semibold">İlk ay %25 indirimli</p>
                      <p className="text-xs text-gray-500 mt-1">Sonraki aylar: {originalPrice.toLocaleString('tr-TR')} ₺/ay</p>
                    </>
                  ) : (
                    <>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-blue-600">
                          {originalPrice.toLocaleString('tr-TR')} ₺
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">/ Aylık</p>
                    </>
                  )}
                </div>

                {/* Ana Özellik (Randevu Limiti) */}
                <div className="mb-4">
                  <p className="text-base font-semibold text-gray-900">
                    {plan.quota_monthly_appointments.toLocaleString('tr-TR')} Randevu / Aylık
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
                  {isCurrentPlan ? "Mevcut Abonelik" : isProcessing ? "İşleniyor..." : "Aboneliği Başlat"}
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



