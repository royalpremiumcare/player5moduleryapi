import React, { useEffect, useMemo } from "react";
import { Routes, Route, useLocation, useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import SeoWrapper from "./components/SeoWrapper";
import { seoData } from "./data/seoData";
import { getSeoContent } from "./data/seoContent";

const resolveLocale = (lang) => {
  if (!lang) return "en-GB";
  const l = String(lang).toLowerCase();
  if (l.startsWith("tr")) return "tr";
  return "en-GB";
};

// Sayfa şablonu etiketleri (içerik seoContent.js'te; bunlar sadece bölüm başlıkları)
const LABELS = {
  tr: {
    faq: "Sık Sorulan Sorular",
    related: "İlgili sayfalar",
    ctaTop: "Ücretsiz Başla",
    screenshotCaption: "PLANN yönetim paneli — günün randevuları, müşteri kayıtları ve kasa hareketleri",
    screenshotAlt: "PLANN randevu yönetim paneli ekran görüntüsü",
    notFound: "Sayfa bulunamadı",
    home: "Ana sayfa",
  },
  "en-GB": {
    faq: "Frequently Asked Questions",
    related: "Related pages",
    ctaTop: "Start Free",
    screenshotCaption: "The PLANN dashboard — the day's appointments, client records and takings",
    screenshotAlt: "Screenshot of the PLANN appointment dashboard",
    notFound: "Page not found",
    home: "Home",
  },
};

const CheckIcon = () => (
  <svg
    className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

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

  const content = useMemo(
    () => (seo ? getSeoContent(seo.locale, seo.category, seo.slug) : null),
    [seo]
  );

  const isTr = (seo?.locale || locale) === "tr";
  const t = LABELS[isTr ? "tr" : "en-GB"];

  // İlgili sayfalar arası geçişte tarayıcı scroll pozisyonunu koruduğu için
  // yeni sayfa aşağıdan açılıyordu; her rota değişiminde başa alınır.
  useEffect(() => {
    window.scrollTo(0, 0);
    if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
    if (document.documentElement) document.documentElement.scrollTop = 0;
    if (document.body) document.body.scrollTop = 0;
  }, [location.pathname]);

  if (!seo) {
    return (
      <main className="min-h-screen bg-white flex items-center justify-center p-6">
        <h1 className="text-2xl font-bold text-zinc-900">{t.notFound}</h1>
      </main>
    );
  }

  const screenshotSrc = isTr
    ? "/screenshots/landing-dashboard-tr.png"
    : "/screenshots/landing-dashboard-en.png";

  return (
    <div className="min-h-screen bg-white text-zinc-900">
      <SeoWrapper seo={seo} canonicalPath={location.pathname} faq={content?.faq} />

      {/* Üst bar */}
      <header className="border-b border-zinc-100 bg-white/90 sticky top-0 z-40">
        <div className="max-w-4xl mx-auto px-5 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" aria-label="PLANN">
            <img src="/plannlogo.png" alt="PLANN" className="h-8 w-auto" />
          </Link>
          <a
            href="/register"
            className="bg-zinc-900 hover:bg-black text-white text-sm font-bold px-5 h-10 flex items-center rounded-lg shadow-md transition-colors active:scale-[0.98]"
          >
            {t.ctaTop}
          </a>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-5 pb-16">
        {/* Hero */}
        <section className="pt-12 pb-8">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-950 leading-tight">
            {seo.h1}
          </h1>
          {(content?.intro || []).map((p) => (
            <p key={p.slice(0, 40)} className="mt-4 text-base sm:text-lg leading-relaxed text-zinc-600">
              {p}
            </p>
          ))}
        </section>

        {/* Ürün görseli — gerçek PLANN dashboard ekranı */}
        <section className="pb-10">
          <figure className="rounded-xl border border-zinc-200 shadow-lg overflow-hidden bg-zinc-50">
            <img
              src={screenshotSrc}
              alt={t.screenshotAlt}
              className="w-full h-auto block"
              loading="lazy"
            />
            <figcaption className="text-xs text-zinc-500 px-4 py-3 border-t border-zinc-100 bg-white">
              {t.screenshotCaption}
            </figcaption>
          </figure>
        </section>

        {/* İçerik bölümleri */}
        {(content?.sections || []).map((section) => (
          <section key={section.h2} className="pb-10">
            <h2 className="text-2xl font-bold text-zinc-950 mb-4">{section.h2}</h2>
            {(section.body || []).map((p) => (
              <p key={p.slice(0, 40)} className="text-zinc-600 leading-relaxed mb-4">
                {p}
              </p>
            ))}
            {section.items && (
              <div className="space-y-4 mt-2">
                {section.items.map((item) => (
                  <div
                    key={item.h3}
                    className="bg-zinc-50 rounded-xl border border-zinc-100 p-5"
                  >
                    <h3 className="font-bold text-zinc-900 mb-1.5">{item.h3}</h3>
                    <p className="text-sm text-zinc-600 leading-relaxed">{item.text}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        ))}

        {/* Güven / ürün netliği */}
        {content?.trust && (
          <section className="pb-10">
            <h2 className="text-2xl font-bold text-zinc-950 mb-4">{content.trust.title}</h2>
            <ul className="space-y-3">
              {content.trust.items.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <CheckIcon />
                  <span className="text-zinc-700 leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* FAQ — görünen içerik SeoWrapper'daki FAQPage schema ile birebir aynı */}
        {content?.faq?.length > 0 && (
          <section className="pb-10">
            <h2 className="text-2xl font-bold text-zinc-950 mb-4">{t.faq}</h2>
            <div className="space-y-3">
              {content.faq.map((item) => (
                <details
                  key={item.q}
                  className="group bg-white rounded-xl border border-zinc-200 overflow-hidden"
                >
                  <summary className="flex items-center justify-between gap-4 cursor-pointer list-none px-5 py-4 font-semibold text-zinc-900 hover:bg-zinc-50 transition-colors">
                    <span>{item.q}</span>
                    <svg
                      className="w-4 h-4 text-zinc-400 flex-shrink-0 transition-transform group-open:rotate-180"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </summary>
                  <p className="px-5 pb-4 text-sm text-zinc-600 leading-relaxed">{item.a}</p>
                </details>
              ))}
            </div>
          </section>
        )}

        {/* Sektöre özgü CTA */}
        {content?.cta && (
          <section className="pb-10">
            <div className="bg-zinc-950 rounded-xl p-8 sm:p-10 text-center shadow-xl">
              <h2 className="text-2xl font-bold text-white mb-3">{content.cta.title}</h2>
              <p className="text-zinc-400 leading-relaxed max-w-xl mx-auto mb-6">
                {content.cta.text}
              </p>
              <a
                href="/register"
                className="inline-flex items-center justify-center bg-white hover:bg-zinc-100 text-zinc-950 font-bold h-12 px-8 rounded-lg shadow-lg transition-colors active:scale-[0.98]"
              >
                {content.cta.button}
              </a>
            </div>
          </section>
        )}

        {/* Internal linkler */}
        {content?.links?.length > 0 && (
          <section className="pb-4">
            <h2 className="text-lg font-bold text-zinc-950 mb-3">{t.related}</h2>
            <ul className="flex flex-wrap gap-2">
              {content.links.map((link) => (
                <li key={link.to}>
                  <Link
                    to={link.to}
                    className="inline-block text-sm text-zinc-700 bg-white border border-zinc-200 hover:bg-zinc-50 hover:border-zinc-300 rounded-full px-4 py-2 transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>

      <footer className="border-t border-zinc-100">
        <div className="max-w-4xl mx-auto px-5 py-6 flex items-center justify-between text-sm text-zinc-500">
          <Link to="/" className="hover:text-zinc-900 transition-colors">
            {t.home}
          </Link>
          <span>PLANN</span>
        </div>
      </footer>
    </div>
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
