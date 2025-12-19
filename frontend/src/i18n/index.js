import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpApi from 'i18next-http-backend';

i18n
  // Load translations using http backend
  .use(HttpApi)
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Init i18next
  .init({
    supportedLngs: ['en', 'tr'],
    fallbackLng: 'en', // British English as fallback
    debug: true, // Enable debug temporarily to see what's happening
    
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
    
    backend: {
      // Use path relative to public folder (works with both HashRouter and BrowserRouter)
      loadPath: process.env.PUBLIC_URL ? `${process.env.PUBLIC_URL}/locales/{{lng}}/translation.json` : '/locales/{{lng}}/translation.json',
    },
    
    interpolation: {
      escapeValue: false, // React already escapes by default
    },
    
    react: {
      useSuspense: true,
    },
  });

// Helper function to detect if user should see Turkish
const detectInitialLanguage = () => {
  const stored = localStorage.getItem('i18nextLng');
  
  // Domain bazlı dil kontrolü
  const hostname = window.location.hostname;
  if (hostname.includes('plannapp.co.uk')) {
    i18n.changeLanguage('en');
    localStorage.setItem('i18nextLng', 'en');
    return;
  } else if (hostname.includes('plannapp.co') || hostname.includes('plannapp.com')) {
    // plannapp.co ve plannapp.com -> Türkçe
    i18n.changeLanguage('tr');
    localStorage.setItem('i18nextLng', 'tr');
    return;
  }
  
  if (stored && ['en', 'tr'].includes(stored)) {
    return; // Use stored preference
  }
  
  // Check browser language
  const browserLang = navigator.language || navigator.userLanguage || '';
  if (browserLang.startsWith('tr')) {
    i18n.changeLanguage('tr');
  } else {
    i18n.changeLanguage('en');
  }
};

// Run detection after i18n is initialized
i18n.on('initialized', detectInitialLanguage);

export default i18n;
