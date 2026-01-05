import React, { useMemo } from "react";
import { Helmet } from "react-helmet-async";

const normaliseLocale = (locale) => {
  if (!locale) return "en-GB";
  const l = String(locale).toLowerCase();
  if (l.startsWith("tr")) return "tr-TR";
  if (l.startsWith("en")) return "en-GB";
  return "en-GB";
};

const buildCanonicalUrl = (canonicalPath) => {
  if (typeof window === "undefined") return canonicalPath || "";

  const origin = window.location.origin;
  const path = canonicalPath || window.location.pathname;
  return `${origin}${path}`;
};

export default function SeoWrapper({ seo, canonicalPath }) {
  const canonicalUrl = useMemo(
    () => buildCanonicalUrl(canonicalPath),
    [canonicalPath]
  );

  const jsonLd = useMemo(() => {
    if (!seo) return null;

    const type = seo.schemaType || "WebPage";

    const base = {
      "@context": "https://schema.org",
      "@type": type,
      name: seo.h1 || seo.title || "PLANN",
      description: seo.metaDescription,
      url: canonicalUrl,
      publisher: {
        "@type": "Organization",
        name: "PLANN",
      },
    };

    if (
      type === "SoftwareApplication" ||
      type === "WebApplication" ||
      type === "MobileApplication"
    ) {
      return {
        ...base,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
      };
    }

    return base;
  }, [seo, canonicalUrl]);

  if (!seo) return null;

  const htmlLang = normaliseLocale(seo.locale);

  return (
    <Helmet>
      <html lang={htmlLang} />

      <title>{seo.title}</title>
      <meta name="description" content={seo.metaDescription} />
      <meta name="robots" content="index,follow" />

      <link rel="canonical" href={canonicalUrl} />

      <meta property="og:site_name" content="PLANN" />
      <meta property="og:type" content="website" />
      <meta property="og:title" content={seo.title} />
      <meta property="og:description" content={seo.metaDescription} />
      <meta property="og:url" content={canonicalUrl} />

      <meta name="twitter:card" content="summary" />
      <meta name="twitter:title" content={seo.title} />
      <meta name="twitter:description" content={seo.metaDescription} />

      {jsonLd ? (
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      ) : null}
    </Helmet>
  );
}
