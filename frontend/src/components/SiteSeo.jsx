import React, { useMemo } from "react";
import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { SEO_ORIGINS, homeSeo } from "../data/seoData";

// Ana sayfa (landing) SEO head'i.
// Site locale HOST'a göre belirlenir (kullanıcının dil toggle'ına göre DEĞİL):
// plannapp.co.uk → en-GB, diğer her şey → tr. Canonical/hreflang sinyalleri
// böylece domain başına sabit kalır.
const resolveSiteLocale = () => {
  if (typeof window === "undefined") return "tr";
  return window.location.hostname.includes("plannapp.co.uk") ? "en-GB" : "tr";
};

const FAQ_COUNT = 11;

export default function SiteSeo() {
  const { i18n } = useTranslation();
  const siteLocale = resolveSiteLocale();
  const seo = homeSeo[siteLocale];

  const canonicalUrl = `${SEO_ORIGINS[siteLocale]}/`;
  const htmlLang = siteLocale === "tr" ? "tr" : "en-GB";
  const ogLocale = siteLocale === "tr" ? "tr_TR" : "en_GB";
  const ogImage = `${SEO_ORIGINS[siteLocale]}/plannlogo.png`;

  const jsonLd = useMemo(() => {
    // FAQ içerikleri site locale'inin çevirisinden sabitlenir (görünür dil
    // toggle'ından bağımsız) — JSON-LD canonical dil ile tutarlı olmalı.
    const fixedT = i18n.getFixedT(siteLocale === "tr" ? "tr" : "en");
    const faqItems = [];
    for (let idx = 1; idx <= FAQ_COUNT; idx++) {
      const q = fixedT(`landing.faq.q${idx}`);
      const a = fixedT(`landing.faq.a${idx}`);
      if (q && a && !q.startsWith("landing.faq")) {
        faqItems.push({
          "@type": "Question",
          name: q,
          acceptedAnswer: { "@type": "Answer", text: a },
        });
      }
    }

    const graph = [
      {
        "@type": "Organization",
        "@id": "https://plannapp.co/#organization",
        name: "PLANNAPP LTD",
        url: "https://plannapp.co/",
        logo: "https://plannapp.co/plannlogo.png",
        sameAs: [
          "https://play.google.com/store/apps/details?id=co.plannapp.app",
          "https://apps.apple.com/app/id6759719891",
        ],
      },
      {
        "@type": "WebSite",
        "@id": `${canonicalUrl}#website`,
        name: "PLANN",
        url: canonicalUrl,
        inLanguage: htmlLang,
        publisher: { "@id": "https://plannapp.co/#organization" },
      },
      {
        "@type": "SoftwareApplication",
        name: "PLANN",
        description: seo.metaDescription,
        url: canonicalUrl,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web, iOS, Android",
        inLanguage: htmlLang,
        publisher: { "@id": "https://plannapp.co/#organization" },
      },
    ];

    if (faqItems.length > 0) {
      graph.push({ "@type": "FAQPage", mainEntity: faqItems });
    }

    return { "@context": "https://schema.org", "@graph": graph };
  }, [i18n, siteLocale, canonicalUrl, htmlLang, seo.metaDescription]);

  return (
    <Helmet>
      <html lang={htmlLang} />

      <title>{seo.title}</title>
      <meta name="description" content={seo.metaDescription} />
      <meta name="robots" content="index,follow" />

      <link rel="canonical" href={canonicalUrl} />
      <link rel="alternate" hrefLang="tr-TR" href="https://plannapp.co/" />
      <link rel="alternate" hrefLang="en-GB" href="https://plannapp.co.uk/" />
      <link rel="alternate" hrefLang="x-default" href="https://plannapp.co/" />

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

      <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
    </Helmet>
  );
}
