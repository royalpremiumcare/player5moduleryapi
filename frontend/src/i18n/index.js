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
      // Use relative path for production compatibility
      loadPath: './locales/{{lng}}/translation.json',
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
