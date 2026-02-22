import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Calendar, Check, Menu, X, Clock, Users, Smartphone, BarChart3, Bell, Shield, Zap, TrendingUp, Star, MessageSquare, FileText, UserCheck, CircleDollarSign, ChevronDown, Phone, Mail, Globe, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import SeoLinks from "./SeoLinks";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL !== undefined ? process.env.REACT_APP_BACKEND_URL : window.location.origin;

import { Capacitor } from '@capacitor/core';

// Public endpoint için axios instance (token gerektirmez)
const publicApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

const LandingPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const whatsappUrl = "https://wa.me/905405953250";
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState(null);
  const [contactModalOpen, setContactModalOpen] = useState(false);

  useEffect(() => {
    document.title = i18n.language?.toLowerCase().startsWith('tr')
      ? 'PLANN | Randevu Sistemi'
      : 'PLANN | Appointment System';
  }, [i18n.language]);
  
  // PWA/APK kontrolü - Uygulama modundaysa login'e yönlendir
  useEffect(() => {
    // Native Capacitor uygulaması mı?
    const isNative = Capacitor.isNativePlatform();
    
    // PWA standalone modunda mı? (iOS veya Android)
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                         window.navigator.standalone === true;
    
    // Native veya PWA standalone ise login'e yönlendir
    if (isNative || isStandalone) {
      navigate('/login?mode=app', { replace: true });
    }
  }, [navigate]);

  const [contactForm, setContactForm] = useState({
    name: "",
    phone: "",
    email: "",
    message: ""
  });
  const [contactFormLoading, setContactFormLoading] = useState(false);
  const [contactFormSuccess, setContactFormSuccess] = useState(false);
  const badgeAssetBase = process.env.PUBLIC_URL || '';
  const badgeAssetVersion = '4';
  const dashboardAssetBase = process.env.PUBLIC_URL || '';
  const dashboardAssetVersion = '1';
  const dashboardImageSrc = i18n.language?.toLowerCase().startsWith('tr')
    ? `${dashboardAssetBase}/screenshots/landing-dashboard-tr.png?v=${dashboardAssetVersion}`
    : `${dashboardAssetBase}/screenshots/landing-dashboard-en.png?v=${dashboardAssetVersion}`;
  // GBP Fiyatlandırma (İngilizce seçildiğinde)
  // monthly: normal fiyat, monthlyDiscounted: %25 indirimli (yuvarlanmış), yearly: yıllık fiyat
  const gbpPricing = {
    'standart': { monthly: 16, monthlyDiscounted: 12, yearly: 160 },
    'standard': { monthly: 16, monthlyDiscounted: 12, yearly: 160 },
    'profesyonel': { monthly: 24, monthlyDiscounted: 18, yearly: 240 },
    'professional': { monthly: 24, monthlyDiscounted: 18, yearly: 240 },
    'premium': { monthly: 32, monthlyDiscounted: 24, yearly: 320 },
    'business': { monthly: 40, monthlyDiscounted: 30, yearly: 400 },
    'enterprise': { monthly: 56, monthlyDiscounted: 42, yearly: 560 },
    'kurumsal': { monthly: 80, monthlyDiscounted: 60, yearly: 800 },
    'corporate': { monthly: 80, monthlyDiscounted: 60, yearly: 800 },
  };

  // TL İlk Ay İndirimli Fiyatlar (Türkçe seçildiğinde)
  const tlFirstMonthPricing = {
    'standart': 990,
    'standard': 990,
    'profesyonel': 1390,
    'professional': 1390,
    'premium': 1150,
    'business': 1450,
    'enterprise': 1750,
    'kurumsal': 2490,
    'corporate': 2490,
  };

  // TL Normal Aylık Fiyatlar (Türkçe seçildiğinde)
  const tlMonthlyPricing = {
    'standart': 1090,
    'standard': 1090,
    'profesyonel': 1490,
    'professional': 1490,
    'premium': 1550,
    'business': 1950,
    'enterprise': 2350,
    'kurumsal': 2850,
    'corporate': 2850,
  };

  // Para birimi ve fiyat formatlama
  const formatPrice = (plan, isYearly, hasDiscount) => {
    const planKey = plan.name.toLowerCase();
    const isEnglish = i18n.language === 'en';
    
    if (isEnglish && gbpPricing[planKey]) {
      let price;
      if (isYearly) {
        price = gbpPricing[planKey].yearly;
      } else if (hasDiscount) {
        price = gbpPricing[planKey].monthlyDiscounted;
      } else {
        price = gbpPricing[planKey].monthly;
      }
      return { price, currency: '£', locale: 'en-GB' };
    }
    
    // TL fiyatları (sabit tablo) - aylık küsüratları yuvarla
    const baseMonthlyPrice = tlMonthlyPricing[planKey] ?? Math.round(plan.price_monthly_original ?? plan.price_monthly);
    let price;
    if (isYearly) {
      price = Math.round(baseMonthlyPrice * 10); // yıllık = aylık * 10 (2 ay ücretsiz)
    } else if (hasDiscount) {
      // İndirimli fiyat: Önce sabit değerleri kontrol et, sonra backend, son olarak %25 indirim
      if (tlFirstMonthPricing[planKey]) {
        price = tlFirstMonthPricing[planKey];
      } else if (plan.price_monthly_discounted) {
        price = Math.round(plan.price_monthly_discounted);
      } else {
        price = Math.round(baseMonthlyPrice * 0.75); // %25 indirim
      }
    } else {
      price = baseMonthlyPrice;
    }
    return { price, currency: '₺', locale: 'tr-TR' };
  };

  // Orijinal fiyatı hesapla (indirim gösterimi için)
  const getOriginalPrice = (plan, isYearly) => {
    const planKey = plan.name.toLowerCase();
    const isEnglish = i18n.language === 'en';
    
    if (isEnglish && gbpPricing[planKey]) {
      const price = isYearly 
        ? gbpPricing[planKey].monthly * 12 
        : gbpPricing[planKey].monthly;
      return { price, currency: '£', locale: 'en-GB' };
    }
    
    // TL fiyatları - aylık küsüratları yuvarla
    const baseMonthlyPrice = tlMonthlyPricing[planKey] ?? Math.round(plan.price_monthly_original ?? plan.price_monthly);
    const price = isYearly 
      ? Math.round(baseMonthlyPrice * 12) 
      : baseMonthlyPrice;
    return { price, currency: '₺', locale: 'tr-TR' };
  };

  // Backend'den gelen özellikleri çevir
  const translateFeature = (feature) => {
    const normalizedFeature = (feature || '').trim();
    const lowerFeature = normalizedFeature.toLowerCase();
    if (lowerFeature.startsWith('yapay zeka akıllı asistan')) {
      if (lowerFeature.includes('limitsiz')) {
        return t('landing.pricing.features.aiAssistantUnlimited');
      }
      return t('landing.pricing.features.aiAssistant');
    }

    const featureMap = {
      // WhatsApp
      'WhatsApp hatırlatma': t('landing.pricing.features.whatsappReminder'),
      'WhatsApp Hatırlatma': t('landing.pricing.features.whatsappReminder'),
      // SMS
      'SMS hatırlatma': t('landing.pricing.features.smsReminder'),
      'SMS Hatırlatma': t('landing.pricing.features.smsReminder'),
      // Staff
      'Sınırsız personel': t('landing.pricing.features.unlimitedStaff'),
      'Sınırsız Personel': t('landing.pricing.features.unlimitedStaff'),
      // Customers
      'Sınırsız müşteri': t('landing.pricing.features.unlimitedCustomers'),
      'Sınırsız Müşteri': t('landing.pricing.features.unlimitedCustomers'),
      // Services
      'Sınırsız hizmet': t('landing.pricing.features.unlimitedServices'),
      'Sınırsız Hizmet': t('landing.pricing.features.unlimitedServices'),
      // Booking page
      'Online rezervasyon sayfası': t('landing.pricing.features.bookingPage'),
      'Online Rezervasyon Sayfası': t('landing.pricing.features.bookingPage'),
      'Online randevu': t('landing.pricing.features.bookingPage'),
      'Online Randevu': t('landing.pricing.features.bookingPage'),
      // Notifications
      'Anlık bildirimler': t('landing.pricing.features.instantNotifications'),
      'Anlık Bildirimler': t('landing.pricing.features.instantNotifications'),
      // Revenue stats
      'Gelir gider istatistikleri': t('landing.pricing.features.revenueStats'),
      'Gelir Gider İstatistikleri': t('landing.pricing.features.revenueStats'),
      'Gelir & gider istatistikleri': t('landing.pricing.features.revenueStats'),
      'Gelir & Gider İstatistikleri': t('landing.pricing.features.revenueStats'),
      'İstatistikler': t('landing.pricing.features.revenueStats'),
      // AI Assistant
      'AI akıllı asistan': t('landing.pricing.features.aiAssistant'),
      'AI Akıllı Asistan': t('landing.pricing.features.aiAssistant'),
      'Yapay Zeka Akıllı Asistan': t('landing.pricing.features.aiAssistant'),
      'Yapay Zeka Akıllı Asistan (Limitsiz)': t('landing.pricing.features.aiAssistantUnlimited'),
      // Priority support
      'Öncelikli destek': t('landing.pricing.features.prioritySupport'),
      'Öncelikli Destek': t('landing.pricing.features.prioritySupport'),
      // Custom integrations
      'Özel entegrasyonlar': t('landing.pricing.features.customIntegrations'),
      'Özel Entegrasyonlar': t('landing.pricing.features.customIntegrations'),
      // Appointment reminder
      'Randevu hatırlatma dahil': t('landing.pricing.features.appointmentReminder'),
      'Randevu Hatırlatma Dahil': t('landing.pricing.features.appointmentReminder'),
    };
    return featureMap[normalizedFeature] || feature;
  };

  // Animasyonlu kelimeler - dil değişince güncellenir
  const getWords = () => {
    const wordsArray = t('landing.hero.words', { returnObjects: true });
    return Array.isArray(wordsArray) ? wordsArray : ["Fast", "Practical", "Easy", "Affordable"];
  };
  const [wordIndex, setWordIndex] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      // Kelime değiştir (fade efekti olmadan direkt değişim)
      setWordIndex((prev) => (prev + 1) % getWords().length);
    }, 700); // Her 0.7 saniyede bir değiş
    
    return () => clearInterval(interval);
  }, [i18n.language]);


  // Modal açıldığında sayfayı en üste scroll et (mobil Chrome için)
  useEffect(() => {
    if (contactModalOpen) {
      // Kısa bir gecikme ile scroll et (modal render olana kadar bekle)
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // Mobil Chrome için ekstra güvence
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
      }, 100);
    }
  }, [contactModalOpen]);
  
  // Sayfa yüklendiğinde scroll'u en üste al (mobil ve masaüstü için)
  useEffect(() => {
    window.scrollTo(0, 0);
    
    // iOS Chrome için footer alt boşluğu düzeltmesi
    const isIOSChrome = /CriOS/i.test(navigator.userAgent);
    if (isIOSChrome) {
      const removeBottomSpace = () => {
        const footer = document.querySelector('.landing-footer');
        if (footer) {
          footer.style.paddingBottom = '0';
          footer.style.marginBottom = '0';
          const lastChild = footer.querySelector('div:last-child > div:last-child');
          if (lastChild) {
            lastChild.style.paddingBottom = '0';
            lastChild.style.marginBottom = '0';
          }
        }
        document.body.style.paddingBottom = '0';
        document.body.style.marginBottom = '0';
        document.documentElement.style.paddingBottom = '0';
        document.documentElement.style.marginBottom = '0';
      };
      
      removeBottomSpace();
      setTimeout(removeBottomSpace, 100);
      setTimeout(removeBottomSpace, 500);
      window.addEventListener('resize', removeBottomSpace);
      
      return () => {
        window.removeEventListener('resize', removeBottomSpace);
      };
    }
  }, []);

  // Smooth scroll için anchor link click handler - Scroll offset düzeltmesi
  useEffect(() => {
    const handleAnchorClick = (e) => {
      const anchor = e.target.closest('a[href^="#"]');
      if (anchor) {
        const href = anchor.getAttribute('href');
        if (href && href.startsWith('#') && href !== '#') {
          e.preventDefault();
          const targetId = href.substring(1);
          const targetElement = document.getElementById(targetId);
          if (targetElement) {
            const headerOffset = 80; // Header yüksekliği için offset
            const elementPosition = targetElement.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
              top: Math.max(0, offsetPosition), // Negatif değerleri önle
              behavior: 'smooth'
            });
          }
        }
      }
    };

    // Event delegation kullanarak tüm anchor linklere listener ekle
    document.addEventListener('click', handleAnchorClick);

    return () => {
      document.removeEventListener('click', handleAnchorClick);
    };
  }, []);

  const features = [
    {
      icon: MessageSquare,
      title: t('landing.features.autoSms.title'),
      description: t('landing.features.autoSms.description')
    },
    {
      icon: Calendar,
      title: t('landing.features.onlineBooking.title'),
      description: t('landing.features.onlineBooking.description')
    },
    {
      icon: MapPin,
      title: t('landing.features.location.title'),
      description: t('landing.features.location.description')
    },
    {
      icon: Users,
      title: t('landing.features.customerManagement.title'),
      description: t('landing.features.customerManagement.description')
    },
    {
      icon: Calendar,
      title: t('landing.features.calendarManagement.title'),
      description: t('landing.features.calendarManagement.description')
    },
    {
      icon: UserCheck,
      title: t('landing.features.staffManagement.title'),
      description: t('landing.features.staffManagement.description')
    },
    {
      icon: Smartphone,
      title: t('landing.features.multiDevice.title'),
      description: t('landing.features.multiDevice.description')
    },
    {
      icon: CircleDollarSign,
      title: t('landing.features.financeManagement.title'),
      description: t('landing.features.financeManagement.description')
    },
    {
      icon: BarChart3,
      title: t('landing.features.reporting.title'),
      description: t('landing.features.reporting.description')
    }
  ];

  const testimonials = i18n.language === 'tr' ? [
    { name: "Ayşe K.", role: "Güzellik Salonu", content: "PLANN ile randevularımız hiç karışmıyor. Hatırlatma SMS'lerini müşterilerimiz çok beğeniyor." },
    { name: "Mehmet D.", role: "Diyetisyen", content: "Arayüz çok sade, her şey yerli yerinde. Takvim özelliği hayat kurtarıyor." },
    { name: "Elif T.", role: "Kuaför", content: "Personel yönetimi sayesinde hangi çalışanın hangi saatte ne işi var görebiliyorum." },
    { name: "Serkan B.", role: "Psikolog", content: "PLANN, zaman yönetimimizi tamamen değiştirdi. İnanılmaz pratik." },
    { name: "Merve Y.", role: "Estetisyen", content: "Müşteri sayımız arttıkça PLANN ile kontrolü sağlamak çok daha kolaylaştı." },
    { name: "Zeynep A.", role: "Veteriner", content: "Hem masaüstü hem telefonda çok güzel çalışıyor. Müşterilerim de çok memnun." }
  ] : [
    { name: "Sarah K.", role: "Beauty Salon", content: "With PLANN, our appointments never get mixed up. Our customers love the reminder SMS." },
    { name: "Michael D.", role: "Dietitian", content: "The interface is so clean, everything is in its place. The calendar feature is a lifesaver." },
    { name: "Emma T.", role: "Hair Salon", content: "Thanks to staff management, I can see which employee is doing what at which time." },
    { name: "James B.", role: "Psychologist", content: "PLANN has completely changed our time management. Incredibly practical." },
    { name: "Sophie Y.", role: "Aesthetician", content: "As our customer numbers grew, PLANN made it so much easier to stay in control." },
    { name: "Rachel A.", role: "Veterinarian", content: "Works brilliantly on both desktop and mobile. My clients are very pleased too." }
  ];

  const [plans, setPlans] = useState([]);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [billingCycle, setBillingCycle] = useState('monthly'); // 'monthly' or 'yearly'

  useEffect(() => {
    // Backend'den planları çek
    const fetchPlans = async () => {
      try {
        const response = await publicApi.get('/plans');
        console.log('API Response:', response.data);
        // Landing page'de sadece 3 paket göster: Standart, Profesyonel, Kurumsal
        const VISIBLE_PLANS = ['standart', 'standard', 'profesyonel', 'professional', 'kurumsal', 'corporate'];
        const paidPlans = (response.data.plans || []).filter(p =>
          p.id !== 'tier_trial' && VISIBLE_PLANS.includes(p.name.toLowerCase())
        );
        console.log('Filtered Plans:', paidPlans);
        if (paidPlans.length > 0) {
          setPlans(paidPlans);
        } else {
          console.warn('No plans found in response');
        }
      } catch (error) {
        console.error('Planlar yüklenemedi:', error);
        console.error('Error details:', error.response?.data || error.message);
        // Hata durumunda bile plans array'ini boş bırak (UI'da loading false olacak)
      } finally {
        setLoadingPlans(false);
      }
    };
    fetchPlans();
  }, []);

  const faqs = [
    { question: t('landing.faq.q1'), answer: t('landing.faq.a1') },
    { question: t('landing.faq.q2'), answer: t('landing.faq.a2') },
    { question: t('landing.faq.q3'), answer: t('landing.faq.a3') },
    { question: t('landing.faq.q4'), answer: t('landing.faq.a4') },
    { question: t('landing.faq.q5'), answer: t('landing.faq.a5') },
    { question: t('landing.faq.q6'), answer: t('landing.faq.a6') },
    { question: t('landing.faq.q7'), answer: t('landing.faq.a7') },
    { question: t('landing.faq.q8'), answer: t('landing.faq.a8') },
    { question: t('landing.faq.q9'), answer: t('landing.faq.a9') },
    { question: t('landing.faq.q10'), answer: t('landing.faq.a10') },
    { question: t('landing.faq.q11'), answer: t('landing.faq.a11') }
  ];

  return (
    <div className="min-h-screen bg-[#fafafa] landing-page-container">
      {/* Banner - Full Width Top (Mobilde header üstünde, Desktop'ta header altında) */}
      <div className="w-full bg-gray-900 text-white py-2 md:hidden">
        <div className="container mx-auto px-4 text-center">
          <span className="text-sm font-medium">
            {t('landing.banner')}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <header className="sticky top-0 z-50 bg-[#fafafa] border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("/")}>
              <span className="text-2xl font-bold text-gray-900">
                PLANN
              </span>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.features')}</a>
              <a href="#pricing" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.pricing')}</a>
              <a href="#testimonials" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.testimonials')}</a>
              <a href="#faq" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.faq')}</a>
            </nav>

            {/* Desktop Buttons */}
            <div className="hidden md:flex items-center gap-4">
              {/* Language Switcher - Test */}
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => i18n.changeLanguage(i18n.language === 'tr' ? 'en' : 'tr')}
                className="font-medium text-gray-600 hover:text-blue-600"
              >
                <Globe className="w-4 h-4 mr-1" />
                {i18n.language === 'tr' ? '🇬🇧 EN' : '🇹🇷 TR'}
              </Button>
              <Button variant="ghost" onClick={() => navigate("/login")} className="font-medium">
                {t('nav.login')}
              </Button>
              <Button onClick={() => navigate("/register")} className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-medium shadow-md">
                {t('nav.register')}
              </Button>
            </div>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-gray-100"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>

          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden py-4 border-t border-gray-200">
              <nav className="flex flex-col gap-4">
                <a href="#features" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.features')}</a>
                <a href="#pricing" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.pricing')}</a>
                <a href="#testimonials" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.testimonials')}</a>
                <a href="#faq" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">{t('nav.faq')}</a>
                {/* Language Switcher - Mobile */}
                <Button 
                  variant="ghost" 
                  onClick={() => i18n.changeLanguage(i18n.language === 'tr' ? 'en' : 'tr')}
                  className="justify-start font-medium text-gray-600 hover:text-blue-600 px-0"
                >
                  <Globe className="w-4 h-4 mr-2" />
                  {i18n.language === 'tr' ? '🇬🇧 English (UK)' : '🇹🇷 Türkçe'}
                </Button>
                <div className="flex flex-col gap-2 pt-4 border-t border-gray-200">
                  <Button variant="outline" onClick={() => navigate("/login")} className="w-full">
                    {t('nav.login')}
                  </Button>
                  <Button onClick={() => navigate("/register")} className="w-full bg-gradient-to-r from-blue-500 to-indigo-600">
                    {t('nav.register')}
                  </Button>
                </div>
              </nav>
            </div>
          )}
        </div>
      </header>

      {/* Hero Section - Exact JetPlan Style */}
      <section className="relative pt-0 pb-8 md:pt-4 md:pb-20 bg-[#fafafa] overflow-hidden">
        {/* Banner - Desktop'ta Hero Section içinde */}
        <div className="hidden md:block w-full bg-gray-900 text-white py-2.5 mb-6">
          <div className="container mx-auto px-4 text-center">
            <span className="text-base font-medium">
              {t('landing.banner')}
            </span>
          </div>
        </div>
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-4xl mx-auto text-center">
            <h1 className="text-5xl md:text-7xl font-bold text-gray-900 mb-6 leading-tight flex flex-col md:flex-row items-center justify-center gap-2 md:gap-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              <span className="block md:inline-block whitespace-nowrap">{t('landing.hero.with')}</span>
              <span className="block md:inline-block bg-gray-900 text-white py-2 md:py-3 px-5 md:px-8 relative text-center whitespace-nowrap" style={{ minWidth: 'fit-content', width: 'fit-content', boxSizing: 'border-box' }}>
                <span className="block" style={{ whiteSpace: 'nowrap' }}>
                  {getWords()[wordIndex]}
                </span>
              </span>
              <span className="block md:inline-block whitespace-nowrap">{t('landing.hero.appointment')}</span>
            </h1>
            
            <p className="text-xl md:text-2xl text-gray-700 mb-10 leading-relaxed">
              {t('landing.hero.subtitle')}<br/>
              {t('landing.hero.subtitle2')}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
              <div className="flex flex-col items-center gap-2">
                <Button 
                  onClick={() => navigate("/register")}
                  className="bg-gray-900 text-white hover:bg-gray-800 px-10 py-6 text-lg font-semibold rounded-full shadow-lg"
                >
                  {t('landing.hero.trialButton')}
                </Button>
                <p className="text-base text-gray-600 text-center">
                  {t('landing.hero.trialNote')}
                </p>
              </div>
              <Button 
                variant="outline"
                onClick={() => {
                  // Mobil Chrome için sayfayı en üste scroll et
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                  setTimeout(() => {
                    setContactModalOpen(true);
                  }, 150);
                }}
                className="bg-transparent border-2 border-gray-900 text-gray-900 hover:bg-gray-100 px-10 py-6 text-lg font-semibold rounded-full"
              >
                {t('landing.hero.callButton')}
              </Button>
              <Button 
                variant="outline"
                onClick={() => window.open(whatsappUrl, '_blank', 'noopener,noreferrer')}
                className="bg-transparent border-2 border-gray-900 text-gray-900 hover:bg-gray-100 px-10 py-6 text-lg font-semibold rounded-full"
              >
                <MessageSquare className="w-5 h-5 mr-2" />
                {t('landing.hero.whatsappButton')}
              </Button>
            </div>

            {/* Demo Image */}
            <div className="mt-16 relative">
              <div className="absolute bottom-6 right-6 bg-white rounded-xl shadow-xl px-4 py-3 flex items-center gap-2 z-10 animate-bounce">
                <MessageSquare className="w-5 h-5 text-green-500" />
                <span className="text-sm font-semibold text-gray-700">{t('landing.hero.newAppointments')}</span>
              </div>
              <div className="bg-white rounded-2xl shadow-2xl p-4 border border-gray-200">
                <img 
                  src={dashboardImageSrc}
                  alt={i18n.language?.toLowerCase().startsWith('tr') ? 'PLANN Dashboard Önizleme' : 'PLANN Dashboard Preview'}
                  className="w-full h-auto rounded-xl"
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = 'https://customer-assets.emergentagent.com/job_16055e0a-771d-4ca0-9203-6958116f17b9/artifacts/1spiinqz_IMG_6383.jpeg';
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 bg-[#fafafa] border-t border-gray-200">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-8">
              {i18n.language === 'tr' ? 'Mobil Uygulamayı İndirin' : 'Download the Mobile App'}
            </h2>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                aria-disabled="true"
                className="inline-flex items-center justify-center cursor-not-allowed"
                title={i18n.language === 'tr' ? 'Yakında' : 'Coming soon'}
              >
                <img
                  src={i18n.language === 'tr'
                    ? `${badgeAssetBase}/badges/app-store-tr.svg?v=${badgeAssetVersion}`
                    : `${badgeAssetBase}/badges/app-store-en.svg?v=${badgeAssetVersion}`}
                  alt="Download on the App Store"
                  className="h-[3.5rem] md:h-[4.25rem] w-auto object-contain"
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = 'https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg';
                  }}
                />
              </a>
              <a
                href="https://play.google.com/store/apps/details?id=co.plannapp.app"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center"
              >
                <img
                  src={i18n.language === 'tr'
                    ? `${badgeAssetBase}/badges/google-play-tr.svg?v=${badgeAssetVersion}`
                    : `${badgeAssetBase}/badges/google-play-en.svg?v=${badgeAssetVersion}`}
                  alt="Get it on Google Play"
                  className="h-[3.5rem] md:h-[4.25rem] w-auto object-contain"
                />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof Section */}
      <section className="py-16 bg-[#fafafa] border-t border-gray-200">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            {/* İstatistikler */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8 mb-12">
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">500+</div>
                <div className="text-gray-600 font-medium">{t('landing.stats.activeBusinesses')}</div>
              </div>
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">420K+</div>
                <div className="text-gray-600 font-medium">{t('landing.stats.appointments')}</div>
              </div>
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">4.8</div>
                <div className="flex items-center justify-center gap-1 mb-2">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                  ))}
                </div>
                <div className="text-gray-600 font-medium">{t('landing.stats.userRating')}</div>
              </div>
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">%98</div>
                <div className="text-gray-600 font-medium">{t('landing.stats.satisfaction')}</div>
              </div>
            </div>

            {/* Güven Göstergeleri */}
            <div className="flex flex-wrap items-center justify-center gap-6 md:gap-8 pt-8 border-t border-gray-200">
              <div className="flex items-center gap-2">
                <Shield className="w-6 h-6 text-green-500" />
                <span className="text-gray-700 font-medium">{t('landing.trust.sslSecure')}</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-6 h-6 text-green-500" />
                <span className="text-gray-700 font-medium">{t('landing.trust.gdprCompliant')}</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingUp className="w-6 h-6 text-blue-500" />
                <span className="text-gray-700 font-medium">{t('landing.trust.support247')}</span>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="w-6 h-6 text-yellow-500" />
                <span className="text-gray-700 font-medium">{t('landing.trust.uptime')}</span>
              </div>
            </div>

            {/* Müşteri Kategorileri */}
            <div className="mt-12 pt-8 border-t border-gray-200">
              <p className="text-center text-gray-600 mb-6 font-medium">{t('landing.trust.trustedBy')}</p>
              <div className="flex flex-wrap items-center justify-center gap-4 md:gap-6">
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.hairSalons')}</span>
                </Card>
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.beautySalons')}</span>
                </Card>
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.healthCentres')}</span>
                </Card>
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.educationInstitutions')}</span>
                </Card>
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.vetClinics')}</span>
                </Card>
                <Card className="px-6 py-3 bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <span className="text-gray-700 font-semibold text-sm md:text-base">{t('landing.trust.spaWellness')}</span>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-[#fafafa] border-t border-gray-200 scroll-mt-24">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">{t('landing.features.title')}</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <Card key={index} className="p-6 hover:shadow-xl transition-all duration-300 border hover:border-blue-300 bg-white">
                  <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg">
                    <Icon className="w-7 h-7 text-white" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 mb-3">{feature.title}</h3>
                  <p className="text-gray-600 leading-relaxed">{feature.description}</p>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 bg-[#fafafa] scroll-mt-24">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">{t('landing.pricing.title')}</h2>
            
            {/* Aylık / Yıllık Toggle */}
            <div className="flex items-center justify-center gap-3 mb-6">
              <span className={`text-lg font-medium ${billingCycle === 'monthly' ? 'text-gray-900' : 'text-gray-400'}`}>
                {t('landing.pricing.monthly')}
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
                <span className={`text-lg font-medium ${billingCycle === 'yearly' ? 'text-gray-900' : 'text-gray-400'}`}>
                  {t('landing.pricing.yearly')}
                </span>
                {billingCycle === 'yearly' && (
                  <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap">
                    {t('landing.pricing.twoMonthsFree')}
                  </span>
                )}
              </div>
            </div>
            
            {/* Yeni Üye İndirimi Banner - Sadece Aylık için */}
            {billingCycle === 'monthly' && (
              <div className="inline-block mb-6 px-6 py-2 bg-gray-900 text-white text-sm font-medium rounded">
                {t('landing.pricing.newUserDiscount')}
              </div>
            )}
          </div>

          {loadingPlans ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto"></div>
              <p className="mt-4 text-gray-600">{t('common.loading')}</p>
            </div>
          ) : plans.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600">{t('landing.pricing.noPlans') || 'Plans are loading...'}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 max-w-6xl mx-auto">
              {plans.map((plan, index) => {
                const isPopular = plan.id === 'tier_4_business';
                const isYearly = billingCycle === 'yearly';
                
                const roundedMonthly = Math.round(plan.price_monthly);
                const yearlyPrice = plan.price_yearly || (roundedMonthly * 10);
                const monthlyEquivalent = Math.round(yearlyPrice / 12);
                const planKey = plan.name.toLowerCase();
                
                // İndirimli fiyat hesaplama: Önce sabit değerleri kontrol et, sonra backend, son olarak %25 indirim
                let discountedPrice, originalPrice;
                if (plan.price_monthly_discounted && plan.price_monthly_original) {
                  discountedPrice = Math.round(plan.price_monthly_discounted);
                  originalPrice = Math.round(plan.price_monthly_original);
                } else if (tlFirstMonthPricing[planKey]) {
                  // Sabit ilk ay indirimli fiyatları kullan
                  discountedPrice = tlFirstMonthPricing[planKey];
                  originalPrice = roundedMonthly;
                } else {
                  // Backend'den gelmiyorsa frontend'de hesapla: %25 indirim
                  originalPrice = roundedMonthly;
                  discountedPrice = Math.round(roundedMonthly * 0.75); // %25 indirim
                }
                
                // Aylık faturalamada her zaman indirim var (ilk ay için)
                const hasDiscount = !isYearly;
                const displayPrice = isYearly ? monthlyEquivalent : discountedPrice;
                
                return (
                  <div 
                    key={plan.id} 
                    className={`relative group ${isPopular ? 'md:-mt-4 md:mb-4' : ''}`}
                  >
                    {/* Gradient Border Effect */}
                    <div className={`absolute -inset-0.5 rounded-2xl opacity-75 blur-sm transition-all duration-500 group-hover:opacity-100 group-hover:blur-md ${
                      isPopular 
                        ? 'bg-gradient-to-r from-amber-400 via-orange-500 to-red-500' 
                        : 'bg-gradient-to-r from-blue-500 to-indigo-600'
                    }`}></div>
                    
                    <div className={`relative rounded-2xl p-6 md:p-8 flex flex-col h-full transition-all duration-300 ${
                      isPopular 
                        ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white' 
                        : 'bg-white'
                    }`}>
                      
                      {/* Popular Badge */}
                      {isPopular && (
                        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                          <div className="flex items-center gap-1.5 bg-gradient-to-r from-amber-400 to-orange-500 text-gray-900 px-4 py-1.5 rounded-full text-sm font-bold shadow-lg">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M10 2l2.5 5.5L18 8.5l-4 4.5 1 6-5-3-5 3 1-6-4-4.5 5.5-1z"/>
                            </svg>
                            {t('landing.pricing.mostPopular')}
                          </div>
                        </div>
                      )}
                      
                      {/* Plan Name */}
                      <div className="mb-4">
                        <h3 className={`text-2xl font-bold ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                          {t(`landing.pricing.plans.${plan.name.toLowerCase()}.name`, plan.name)}
                        </h3>
                        <p className={`text-sm mt-1 ${isPopular ? 'text-gray-300' : 'text-gray-500'}`}>
                          {t(`landing.pricing.plans.${plan.name.toLowerCase()}.description`, plan.target_audience_tr)}
                        </p>
                      </div>
                      
                      {/* Price Section */}
                      <div className="mb-6">
                        {(() => {
                          const priceInfo = formatPrice(plan, isYearly, hasDiscount);
                          const originalPriceInfo = getOriginalPrice(plan, isYearly);
                          const showStrike = hasDiscount || isYearly;
                          return (
                            <>
                              <div className="flex items-end gap-2">
                                <span className={`text-5xl font-extrabold tracking-tight ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                                  {priceInfo.currency}{priceInfo.price.toLocaleString(priceInfo.locale)}
                                </span>
                                {showStrike && (
                                  <span className={`text-lg line-through mb-1 ${isPopular ? 'text-gray-500' : 'text-gray-400'}`}>
                                    {originalPriceInfo.currency}{originalPriceInfo.price.toLocaleString(originalPriceInfo.locale)}
                                  </span>
                                )}
                              </div>
                              <p className={`text-sm mt-1 ${isPopular ? 'text-gray-400' : 'text-gray-500'}`}>
                                {isYearly ? t('landing.pricing.yearlyBilling') : t('landing.pricing.monthlyBilling')}
                              </p>
                            </>
                          );
                        })()}
                      </div>
                      
                      {/* Divider */}
                      <div className={`h-px mb-6 ${isPopular ? 'bg-gray-700' : 'bg-gray-200'}`}></div>
                      
                      {/* Features */}
                      <div className="flex-grow space-y-3 mb-6">
                        {/* Randevu Limiti - Vurgulu */}
                        <div className={`flex items-center gap-3 p-3 rounded-xl ${
                          isPopular ? 'bg-amber-400/10 border border-amber-400/30' : 'bg-blue-50 border border-blue-100'
                        }`}>
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                            isPopular ? 'bg-amber-400 text-gray-900' : 'bg-blue-500 text-white'
                          }`}>
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                          </div>
                          <div>
                            <div className={`text-lg font-bold ${isPopular ? 'text-white' : 'text-gray-900'}`}>
                              {t('landing.pricing.features.appointments', { count: plan.quota_monthly_appointments.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB') })}
                            </div>
                            <div className={`text-xs ${isPopular ? 'text-gray-400' : 'text-gray-500'}`}>{t('landing.pricing.monthlyLimit')}</div>
                          </div>
                        </div>
                        
                        {/* Diğer Özellikler */}
                        {plan.features
                          .filter(feature => {
                            const quotaStr = plan.quota_monthly_appointments.toLocaleString('tr-TR');
                            return !(feature.includes(quotaStr) && feature.toLowerCase().includes('randevu'));
                          })
                          .map((feature, i) => (
                            <div key={i} className="flex items-center gap-3">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                                isPopular ? 'bg-green-400' : 'bg-green-500'
                              }`}>
                                <Check className="w-3 h-3 text-white" />
                              </div>
                              <span className={`text-sm ${isPopular ? 'text-gray-200' : 'text-gray-700'}`}>{translateFeature(feature)}</span>
                            </div>
                          ))}
                      </div>
                      
                      {/* CTA Button */}
                      <button 
                        onClick={() => navigate("/register")}
                        className={`w-full py-4 rounded-xl font-bold text-base transition-all duration-300 transform hover:scale-[1.02] hover:shadow-xl ${
                          isPopular 
                            ? 'bg-gradient-to-r from-amber-400 to-orange-500 text-gray-900 hover:from-amber-300 hover:to-orange-400' 
                            : 'bg-gradient-to-r from-gray-800 to-gray-900 text-white hover:from-gray-700 hover:to-gray-800'
                        }`}
                      >
                        {t('landing.pricing.tryFree')}
                      </button>
                      
                      {/* Trust Badge */}
                      <div className={`flex items-center justify-center gap-2 mt-4 text-xs ${isPopular ? 'text-gray-400' : 'text-gray-500'}`}>
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        {t('landing.pricing.trustBadge')}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className="py-20 bg-[#fafafa] scroll-mt-24">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">{t('landing.testimonials.title')}</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
            {testimonials.map((testimonial, index) => (
              <Card key={index} className="p-6 hover:shadow-xl transition-all duration-300 bg-gradient-to-br from-white to-gray-50 border-l-4 border-blue-500">
                <div className="flex items-center gap-1 mb-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                  ))}
                </div>
                <p className="text-gray-700 mb-4 italic">"{testimonial.content}"</p>
                <div className="border-t pt-4">
                  <h4 className="font-bold text-gray-900">{testimonial.name}</h4>
                  <p className="text-sm text-gray-600">{testimonial.role}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-20 bg-[#fafafa] border-t border-gray-200 scroll-mt-24">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">{t('landing.faq.title')}</h2>
          </div>

          <div className="max-w-3xl mx-auto space-y-3">
            {faqs.map((faq, index) => (
              <Card key={index} className="overflow-hidden">
                <button
                  onClick={() => setOpenFaqIndex(openFaqIndex === index ? null : index)}
                  className="w-full p-6 text-left flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <h3 className="text-lg font-bold text-gray-900 pr-4">{faq.question}</h3>
                  <ChevronDown 
                    className={`w-5 h-5 text-gray-600 flex-shrink-0 transition-transform duration-300 ${
                      openFaqIndex === index ? 'transform rotate-180' : ''
                    }`}
                  />
                </button>
                {openFaqIndex === index && (
                  <div className="px-6 pb-6 text-gray-600 border-t">
                    <p className="pt-4">{faq.answer}</p>
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-[#fafafa]">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            {t('landing.cta.title')}
          </h2>
          <p className="text-xl text-gray-700 mb-8 max-w-2xl mx-auto">
            {t('landing.cta.subtitle')}
          </p>
          <Button 
            onClick={() => navigate("/register")}
            className="bg-gray-900 text-white hover:bg-gray-800 px-10 py-6 text-lg font-semibold rounded-full shadow-xl"
          >
            {t('landing.cta.button')}
          </Button>
        </div>
      </section>

      {/* Contact Modal */}
      <Dialog open={contactModalOpen} onOpenChange={setContactModalOpen}>
        <DialogContent className="w-[95vw] max-w-[520px] h-[90vh] max-h-[650px] md:h-auto bg-white border-0 p-0 rounded-2xl shadow-2xl overflow-hidden">
          <div className="relative bg-gradient-to-br from-gray-50 to-gray-100 px-6 pt-8 pb-6">
            <button
              onClick={() => setContactModalOpen(false)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-gray-200 transition-colors"
            >
              <X className="w-5 h-5 text-gray-600" />
            </button>
            <DialogHeader>
              <DialogTitle className="text-2xl md:text-3xl font-bold text-gray-900 text-center pr-8" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                {t('landing.contact.title')}
              </DialogTitle>
              <DialogDescription className="text-center text-gray-600 text-sm mt-2">
                {t('landing.contact.subtitle')}
              </DialogDescription>
            </DialogHeader>
          </div>
          
          {contactFormSuccess ? (
            <div className="px-6 py-10 md:py-12 text-center bg-white flex flex-col items-center justify-center min-h-[400px]">
              <div className="w-24 h-24 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
                <Check className="w-12 h-12 text-white" />
              </div>
              <h3 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                {t('landing.contact.success')}
              </h3>
              <p className="text-gray-600 mb-8 text-base max-w-sm">
                {t('landing.contact.successMessage')}
              </p>
              <Button 
                onClick={() => {
                  setContactModalOpen(false);
                  setContactFormSuccess(false);
                  setContactForm({ name: "", phone: "", email: "", message: "" });
                }}
                className="bg-gray-900 text-white hover:bg-gray-800 px-10 py-6 rounded-full font-semibold text-base shadow-lg transition-all hover:scale-105"
              >
                {t('landing.contact.ok')}
              </Button>
            </div>
          ) : (
            <form 
              onSubmit={async (e) => {
                e.preventDefault();
                setContactFormLoading(true);
                
                try {
                  const response = await publicApi.post('/contact', {
                    name: contactForm.name,
                    phone: contactForm.phone,
                    email: contactForm.email || null,
                    message: contactForm.message || null
                  });
                  
                  if (response.data.success) {
                    setContactFormSuccess(true);
                    toast.success("Talebiniz alındı!");
                  } else {
                    toast.error("Bir hata oluştu, lütfen tekrar deneyin");
                  }
                } catch (error) {
                  console.error("Contact form error:", error);
                  toast.error(error.response?.data?.detail || "Bir hata oluştu, lütfen tekrar deneyin");
                } finally {
                  setContactFormLoading(false);
                }
              }}
              className="px-6 py-6 space-y-5 bg-white overflow-y-auto max-h-[calc(90vh-200px)] md:max-h-none"
            >
              <div className="space-y-2">
                <Input
                  id="contact-name"
                  value={contactForm.name}
                  onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                  placeholder={t('landing.contact.namePlaceholder')}
                  required
                  className="h-14 border-2 border-gray-200 rounded-xl focus:border-gray-900 focus:ring-0 bg-gray-50 focus:bg-white transition-all text-base placeholder:text-gray-400"
                />
              </div>

              <div className="space-y-2">
                <Input
                  id="contact-phone"
                  type="tel"
                  value={contactForm.phone}
                  onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
                  placeholder={t('landing.contact.phonePlaceholder')}
                  required
                  className="h-14 border-2 border-gray-200 rounded-xl focus:border-gray-900 focus:ring-0 bg-gray-50 focus:bg-white transition-all text-base placeholder:text-gray-400"
                />
              </div>

              <div className="space-y-2">
                <Input
                  id="contact-email"
                  type="email"
                  value={contactForm.email}
                  onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                  placeholder={t('landing.contact.emailPlaceholder')}
                  className="h-14 border-2 border-gray-200 rounded-xl focus:border-gray-900 focus:ring-0 bg-gray-50 focus:bg-white transition-all text-base placeholder:text-gray-400"
                />
              </div>

              <div className="space-y-2">
                <Textarea
                  id="contact-message"
                  value={contactForm.message}
                  onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                  placeholder={t('landing.contact.messagePlaceholder')}
                  rows={4}
                  className="border-2 border-gray-200 rounded-xl focus:border-gray-900 focus:ring-0 bg-gray-50 focus:bg-white transition-all resize-none text-base placeholder:text-gray-400 min-h-[120px]"
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  disabled={contactFormLoading}
                  className="w-full bg-gray-900 text-white hover:bg-gray-800 px-8 py-6 rounded-full font-semibold text-base shadow-lg transition-all hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {contactFormLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                      {t('landing.contact.sending')}
                    </>
                  ) : (
                    <>
                      <Phone className="w-5 h-5 mr-2" />
                      {t('landing.contact.submit')}
                    </>
                  )}
                </Button>
              </div>

              <div className="flex items-start gap-2 text-xs text-gray-500 pt-2 pb-2">
                <Shield className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400" />
                <span className="leading-relaxed">{t('landing.contact.privacy')}</span>
              </div>

              <div className="text-[11px] text-gray-500 leading-relaxed">
                {(i18n.language || '').toLowerCase().startsWith('en')
                  ? 'PLANNAPP LTD (Company No. 16886895) — Registered Address: 71-75 Shelton Street, Covent Garden, London WC2H 9JQ, United Kingdom.'
                  : 'PLANNAPP LTD (Şirket No: 16886895) — Kayıtlı Adres: 71-75 Shelton Street, Covent Garden, London WC2H 9JQ, United Kingdom.'}
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Footer */}
      <footer className="bg-[#fafafa] text-gray-700 py-12 pb-0 md:pb-12 landing-footer">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="mb-4">
                <span className="text-2xl font-bold text-gray-900">PLANN</span>
              </div>
              <p className="text-sm text-gray-600">{t('landing.footer.description')}</p>
            </div>
            <div>
              <h4 className="font-bold text-gray-900 mb-4">{t('landing.footer.product')}</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#features" className="hover:text-gray-900 text-gray-600">{t('nav.features')}</a></li>
                <li><a href="#pricing" className="hover:text-gray-900 text-gray-600">{t('nav.pricing')}</a></li>
                <li><a href="#testimonials" className="hover:text-gray-900 text-gray-600">{t('nav.testimonials')}</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-gray-900 mb-4">{t('landing.footer.legal')}</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="/privacy" className="hover:text-gray-900 text-gray-600">{t('landing.footer.privacyPolicy')}</a></li>
                <li><a href="/terms" className="hover:text-gray-900 text-gray-600">{t('landing.footer.termsOfService')}</a></li>
                <li><a href="/refund" className="hover:text-gray-900 text-gray-600">{t('landing.footer.refundPolicy')}</a></li>
                <li><a href="#faq" className="hover:text-gray-900 text-gray-600">{t('nav.faq')}</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-gray-900 mb-4">{t('landing.footer.contact')}</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <Phone className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>+44 7474 626900</span>
                </li>
                <li className="flex items-start gap-2">
                  <Mail className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>info@plannapp.co</span>
                </li>
                <li className="flex items-start gap-2">
                  <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>71-75 Shelton Street Covent Garden United Kingdom<br />London WC2H 9JQ</span>
                </li>
                <li className="flex items-start gap-2">
                  <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h10M7 11h4m-4 4h10M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <span>{(i18n.language || '').toLowerCase().startsWith('en') ? 'Company Number: 16886895' : 'Şirket Numarası: 16886895'}</span>
                </li>
              </ul>
            </div>
          </div>

          <SeoLinks />

          <div className="border-t border-gray-300 mt-8 pt-8">
            {/* Ödeme Logoları */}
            <div className="flex flex-wrap items-center justify-center gap-2 mb-6">
              <span className="text-gray-600 text-sm font-medium mr-1">{t('landing.footer.securePayment')}</span>
              {/* Visa */}
              <div className="bg-white px-4 py-2.5 rounded-md shadow-sm border border-gray-200 hover:shadow-md transition-all flex items-center justify-center h-10">
                <span className="text-[#1434CB] font-bold text-lg tracking-wider">VISA</span>
              </div>
              {/* Mastercard */}
              <div className="bg-white px-4 py-2.5 rounded-md shadow-sm border border-gray-200 hover:shadow-md transition-all flex items-center justify-center h-10">
                <div className="flex items-center gap-1">
                  <div className="w-6 h-6 rounded-full bg-[#EB001B]"></div>
                  <div className="w-6 h-6 rounded-full bg-[#F79E1B] -ml-3"></div>
                </div>
              </div>
              {/* Troy */}
              <div className="bg-[#1E1E1E] px-4 py-2.5 rounded-md shadow-sm border border-gray-200 hover:shadow-md transition-all flex items-center justify-center h-10">
                <span className="text-white font-bold text-sm tracking-wider">TROY</span>
              </div>
              {/* American Express */}
              <div className="bg-[#006FCF] px-4 py-2.5 rounded-md shadow-sm border border-gray-200 hover:shadow-md transition-all flex items-center justify-center h-10">
                <span className="text-white font-bold text-xs tracking-wide">AMEX</span>
              </div>
            </div>
            <div className="text-center text-sm text-gray-600 pb-0 mb-0">
              <p className="mb-0 pb-0">{t('landing.footer.copyright')}</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
console.log("BACKEND_URL:", process.env.REACT_APP_BACKEND_URL);
