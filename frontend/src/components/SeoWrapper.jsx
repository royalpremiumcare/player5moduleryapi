import React, { useMemo } from "react";
import { Helmet } from "react-helmet-async";
import { SEO_ORIGINS, getSeoUrl, getAlternateEntry } from "../data/seoData";

const normaliseLocale = (locale) => {
  if (!locale) return "en-GB";
  const l = String(locale).toLowerCase();
  if (l.startsWith("tr")) return "tr-TR";
  if (l.startsWith("en")) return "en-GB";
  return "en-GB";
};

export default function SeoWrapper({ seo, faq }) {
  // Canonical her zaman locale'in SABİT domaininden üretilir (window.origin
  // DEĞİL): TR sayfalar → plannapp.co, EN sayfalar → plannapp.co.uk.
  // Böylece .co üzerinden servis edilen /solutions sayfaları cross-domain
  // canonical ile .co.uk'yi gösterir.
  const canonicalUrl = useMemo(() => (seo ? getSeoUrl(seo) : ""), [seo]);
  const alternate = useMemo(() => getAlternateEntry(seo), [seo]);

  const jsonLd = useMemo(() => {
    if (!seo) return null;

    // Sayfa bir yazılımı anlatıyor; işletmenin kendisini değil. Bu yüzden
    // JSON-LD tipi her zaman SoftwareApplication'dır (BarberShop vb. DEĞİL).
    // Uydurma rating/review/price eklenmez.
    const softwareApp = {
      "@type": "SoftwareApplication",
      name: "PLANN",
      headline: seo.h1 || seo.title,
      description: seo.metaDescription,
      url: canonicalUrl,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web, iOS, Android",
      inLanguage: normaliseLocale(seo.locale),
      publisher: {
        "@type": "Organization",
        name: "PLANNAPP LTD",
        url: "https://plannapp.co/",
      },
    };

    // FAQ varsa: görünen FAQ içeriğiyle BİREBİR aynı FAQPage schema eklenir
    // (içerik kaynağı seoContent.js — sayfa ile aynı data).
    if (Array.isArray(faq) && faq.length > 0) {
      return {
        "@context": "https://schema.org",
        "@graph": [
          softwareApp,
          {
            "@type": "FAQPage",
            mainEntity: faq.map((item) => ({
              "@type": "Question",
              name: item.q,
              acceptedAnswer: { "@type": "Answer", text: item.a },
            })),
          },
        ],
      };
    }

    return { "@context": "https://schema.org", ...softwareApp };
  }, [seo, canonicalUrl, faq]);

  if (!seo) return null;

  const htmlLang = seo.locale === "tr" ? "tr" : "en-GB";
  const ogLocale = seo.locale === "tr" ? "tr_TR" : "en_GB";
  const ogImage = `${SEO_ORIGINS[seo.locale]}/plannlogo.png`;

  const trEntry = seo.locale === "tr" ? seo : alternate;
  const enEntry = seo.locale === "en-GB" ? seo : alternate;

  return (
    <Helmet>
      <html lang={htmlLang} />

      <title>{seo.title}</title>
      <meta name="description" content={seo.metaDescription} />
      <meta name="robots" content="index,follow" />

      <link rel="canonical" href={canonicalUrl} />

      {/* Karşılıklı hreflang — yalnızca gerçek eşdeğer sayfa varsa */}
      {trEntry && enEntry && (
        <link rel="alternate" hrefLang="tr-TR" href={getSeoUrl(trEntry)} />
      )}
      {trEntry && enEntry && (
        <link rel="alternate" hrefLang="en-GB" href={getSeoUrl(enEntry)} />
      )}

      <meta property="og:site_name" content="PLANN" />
      <meta property="og:type" content="website" />
      <meta property="og:title" content={seo.title} />
      <meta property="og:description" content={seo.metaDescription} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:locale" content={ogLocale} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:alt" content="PLANN" />

      <meta name="twitter:card" content="summary" />
      <meta name="twitter:title" content={seo.title} />
      <meta name="twitter:description" content={seo.metaDescription} />

      {jsonLd ? (
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      ) : null}
    </Helmet>
  );
}
