import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpApi from 'i18next-http-backend';

// Helper function to detect if user should see Turkish
const detectInitialLanguage = () => {
  const stored = localStorage.getItem('i18nextLng');
  
  // Domain bazlı dil kontrolü
  const hostname = window.location.hostname;
  if (hostname.includes('plannapp.co.uk')) {
    return 'en';
  } else if (hostname.includes('plannapp.co') || hostname.includes('plannapp.com')) {
    // plannapp.co ve plannapp.com -> Türkçe
    return 'tr';
  }
  
  if (stored && ['en', 'tr'].includes(stored)) {
    return stored; // Use stored preference
  }
  
  // Check browser language
  const browserLang = navigator.language || navigator.userLanguage || '';
  if (browserLang.startsWith('tr')) {
    return 'tr';
  } else {
    return 'en';
  }
};

const detectedLang = detectInitialLanguage();

i18n
  // Load translations using http backend
  .use(HttpApi)
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
    
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
    
    backend: {
      // Use absolute path from root - works with both HashRouter and BrowserRouter
      loadPath: window.location.origin + '/locales/{{lng}}/translation.json',
      // Add cache busting query parameter
      queryStringParams: { v: Date.now() },
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
