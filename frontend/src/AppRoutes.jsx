import React, { useMemo } from "react";
import { Routes, Route, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import SeoWrapper from "./components/SeoWrapper";
import { seoData } from "./data/seoData";

const resolveLocale = (lang) => {
  if (!lang) return "en-GB";
  const l = String(lang).toLowerCase();
  if (l.startsWith("tr")) return "tr";
  return "en-GB";
};

export const ProgrammaticSeoPage = ({ category, forcedLocaleKey }) => {
  const { slug } = useParams();
  const location = useLocation();
  const { i18n } = useTranslation();

  const locale = forcedLocaleKey || resolveLocale(i18n.language);

  const seo = useMemo(() => {
    const exact = seoData.find(
      (item) =>
        item.category === category && item.slug === slug && item.locale === locale
    );

    if (exact) return exact;

    const trFallback = seoData.find(
      (item) => item.category === category && item.slug === slug && item.locale === "tr"
    );
    if (trFallback) return trFallback;

    return seoData.find(
      (item) => item.category === category && item.slug === slug && item.locale === "en-GB"
    );
  }, [category, slug, locale]);

  const isTr = locale === "tr";

  const intro = isTr
    ? "PLANN; telefon trafiği, no-show/ghosting ve defter karmaşasını bitirmek için tasarlanmış modern bir randevu yazılımıdır. Yapay zeka asistanıyla randevu oluşturun, WhatsApp bildirimleriyle müşteriyi otomatik bilgilendirin, PWA ile her yerden yönetin ve Stripe abonelik & gelir takibiyle işin finansını netleştirin."
    : "PLANN is a modern appointment system built to end constant phone calls, no-shows/ghosting and paper-notebook chaos. Create bookings using an AI assistant, keep customers informed with automated WhatsApp notifications, manage everything on the go with PWA, and track subscriptions and revenue with Stripe.";

  const bullets = isTr
    ? [
        "Yapay zeka ile sesli/yazılı komutla randevu oluşturma",
        "WhatsApp otomatik onay ve hatırlatma mesajları",
        "Online randevu sayfası ile 7/24 rezervasyon",
        "Gelir-gider ve personel takibi ile net raporlama",
        "PWA mobil uygulama: işletmeniz cebinizde",
      ]
    : [
        "Create appointments by voice or text with AI",
        "Automatic WhatsApp confirmations and reminders",
        "24/7 online booking page to capture demand",
        "Revenue and staff tracking in one dashboard",
        "PWA mobile app: manage from anywhere",
      ];

  if (!seo) {
    return (
      <main style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
        <h1>{isTr ? "Sayfa bulunamadı" : "Page not found"}</h1>
      </main>
    );
  }

  return (
    <main style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <SeoWrapper seo={seo} canonicalPath={location.pathname} />

      <h1 style={{ fontSize: 32, marginBottom: 12 }}>{seo.h1}</h1>
      <p style={{ fontSize: 16, lineHeight: 1.6, marginBottom: 16 }}>{intro}</p>

      <div style={{ marginBottom: 20 }}>
        <ul style={{ paddingLeft: 18, margin: 0 }}>
          {bullets.map((b) => (
            <li key={b} style={{ marginBottom: 8 }}>
              {b}
            </li>
          ))}
        </ul>
      </div>

      <a
        href="/register"
        style={{
          display: "inline-block",
          padding: "10px 14px",
          borderRadius: 10,
          textDecoration: "none",
          background: "#111827",
          color: "#ffffff",
          fontWeight: 600,
        }}
      >
        {isTr ? "PLANN’i Ücretsiz Deneyin" : "Try PLANN Free"}
      </a>
    </main>
  );
};

export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/cozumler/:slug"
        element={<ProgrammaticSeoPage category="vertical" forcedLocaleKey="tr" />}
      />
      <Route
        path="/ozellikler/:slug"
        element={<ProgrammaticSeoPage category="feature" forcedLocaleKey="tr" />}
      />
      <Route
        path="/solutions/:slug"
        element={<ProgrammaticSeoPage category="vertical" forcedLocaleKey="en-GB" />}
      />
      <Route
        path="/features/:slug"
        element={<ProgrammaticSeoPage category="feature" forcedLocaleKey="en-GB" />}
      />
    </Routes>
  );
}
