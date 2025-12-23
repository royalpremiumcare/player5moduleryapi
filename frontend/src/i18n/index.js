import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { Capacitor } from '@capacitor/core';

// Import translation files directly
import translationTR from './locales/tr/translation.json';
import translationEN from './locales/en/translation.json';

// Helper function to detect if user should see Turkish
const detectInitialLanguage = () => {
  const stored = localStorage.getItem('i18nextLng');

  // 1) Manual user preference (highest priority)
  if (stored && ['en', 'tr'].includes(stored)) {
    return stored;
  }

  // 2) Native mobile app (Capacitor): use device locale
  //    tr* => Turkish, otherwise default to English
  const deviceLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
  if (Capacitor.isNativePlatform()) {
    if (deviceLang.startsWith('tr')) {
      return 'tr';
    }
    return 'en';
  }
  
  // Domain bazlı dil kontrolü
  const hostname = window.location.hostname;
  if (hostname.includes('plannapp.co.uk')) {
    return 'en';
  } else if (hostname.includes('plannapp.co') || hostname.includes('plannapp.com')) {
    // plannapp.co ve plannapp.com -> Türkçe
    return 'tr';
  }

  // 3) Web: Check browser language
  if (deviceLang.startsWith('tr')) {
    return 'tr';
  } else {
    return 'en';
  }
};

const detectedLang = detectInitialLanguage();

i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Init i18next
  .init({
    lng: detectedLang, // Set initial language explicitly
    supportedLngs: ['en', 'tr'],
    fallbackLng: 'en', // British English as fallback
    debug: false, // Disable debug in production
    
    resources: {
      tr: {
        translation: translationTR
      },
      en: {
        translation: translationEN
      }
    },
    
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
    
    interpolation: {
      escapeValue: false, // React already escapes by default
    },
    
    react: {
      useSuspense: false, // Disable suspense to prevent issues
    },
  });

// Set language after initialization
i18n.changeLanguage(detectedLang);
localStorage.setItem('i18nextLng', detectedLang);

export default i18n;
