import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter, BrowserRouter } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { HelmetProvider } from 'react-helmet-async';
import './index.css';
import './i18n'; // i18n configuration
import AppRouter from './AppRouter';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';

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