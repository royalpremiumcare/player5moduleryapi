import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter, BrowserRouter } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { HelmetProvider } from 'react-helmet-async';
import * as Sentry from '@sentry/react';
import './index.css';
import './i18n'; // i18n configuration
import AppRouter from './AppRouter';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import posthog from './lib/posthog';
import metaPixel from './lib/metaPixel';

// === POSTHOG ANALYTICS ===
// REACT_APP_POSTHOG_KEY yoksa otomatik olarak no-op'a düşer; ledger POST'ları yine çalışır.
posthog.init().catch((err) => console.warn('PostHog init failed:', err));

// === META PIXEL + CAPI HİBRİT TAKİP ===
// REACT_APP_META_PIXEL_ID yoksa Pixel disabled, ama track() çağrıları backend
// `/api/meta/event` üzerinden CAPI'a yine de gider (server-side fallback).
// Capacitor (native) içinde Pixel anlamsız → web ortamında init et.
if (!Capacitor.isNativePlatform()) {
  metaPixel.init().catch((err) => console.warn('Meta Pixel init failed:', err));
}

// === SENTRY ERROR TRACKING ===
Sentry.init({
  dsn: "https://de29a57c7caa511eaad0db256c48d28e@o4510971460845568.ingest.de.sentry.io/4510971496890448",
  sendDefaultPii: true,
  tracesSampleRate: 0.2,
  replaysSessionSampleRate: 0.0,
  replaysOnErrorSampleRate: 1.0,
  environment: process.env.NODE_ENV || 'production',
  enabled: process.env.NODE_ENV === 'production' || Capacitor.isNativePlatform(),
});

// Suppress ResizeObserver errors (known React 19 + Radix UI issue)
const originalError = console.error;
console.error = (...args) => {
  if (
    typeof args[0] === 'string' &&
    args[0].includes('ResizeObserver loop')
  ) {
    return;
  }
  originalError.call(console, ...args);
};

// Suppress window error for ResizeObserver
window.addEventListener('error', (e) => {
  if (e.message.includes('ResizeObserver loop')) {
    e.stopImmediatePropagation();
  }
});

// Android WebView performance: backdrop-blur'u CSS override ile kapat
if (Capacitor.getPlatform() === 'android') {
  document.body.classList.add('android-platform');
}

// Native için HashRouter, Web için BrowserRouter
const Router = Capacitor.isNativePlatform() ? HashRouter : BrowserRouter;

// Loading component for i18n
const LoadingFallback = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh',
    fontSize: '1.2rem',
    color: '#666'
  }}>
    Yükleniyor...
  </div>
);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Suspense fallback={<LoadingFallback />}>
      <HelmetProvider>
        <Router>
          <ThemeProvider>
            <AuthProvider>
              <AppRouter />
            </AuthProvider>
          </ThemeProvider>
        </Router>
      </HelmetProvider>
    </Suspense>
  </React.StrictMode>
);