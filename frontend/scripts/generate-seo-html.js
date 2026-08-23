// PLANN build-time statik SEO head üretici (Ağustos 2026)
//
// Amaç: Googlebot ve AI crawler'ların İLK HTML yanıtında doğru SEO
// sinyallerini (title, description, canonical, hreflang, lang, OG, JSON-LD)
// görmesi. React SPA body'si aynen korunur; yalnızca <head> route'a göre
// yeniden yazılmış HTML kopyaları üretilir:
//
//   build/cozumler/<slug>/index.html   (TR vertical)
//   build/ozellikler/<slug>/index.html (TR feature)
//   build/solutions/<slug>/index.html  (EN vertical)
//   build/features/<slug>/index.html   (EN feature)
//   build/index-tr.html                (TR ana sayfa)
//   build/index-en.html                (EN ana sayfa)
//
// Nginx (default.conf) `try_files $uri $uri/index.html` ile bunları otomatik
// sunar; ana sayfa varyantı host'a göre map'lenir. Generator hata verirse
// build DÜŞER (sessiz bozulma yok); üretilen dosyalar yoksa SPA fallback
// zaten çalışmaya devam eder.
//
// Docker build: `npm run build && node scripts/generate-seo-html.js`
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const rootDir = path.resolve(__dirname, "..");
const buildDir = path.join(rootDir, "build");
const templatePath = path.join(buildDir, "index.html");
const seoDataPath = path.join(rootDir, "src", "data", "seoData.js");
const seoContentPath = path.join(rootDir, "src", "data", "seoContent.js");
const trTranslationsPath = path.join(rootDir, "src", "i18n", "locales", "tr", "translation.json");
const enTranslationsPath = path.join(rootDir, "src", "i18n", "locales", "en", "translation.json");

const FAQ_COUNT = 11;

const loadSeoModule = () => {
  const raw = fs.readFileSync(seoDataPath, "utf8");
  const transformed =
    raw.replace(/export const /g, "const ") +
    "\nmodule.exports = { seoData, SEO_ORIGINS, CATEGORY_PATHS, HREFLANG_PAIRS, homeSeo };\n";
  const context = { module: { exports: {} } };
  vm.createContext(context);
  vm.runInContext(transformed, context);
  const mod = context.module.exports;
  if (!mod || !Array.isArray(mod.seoData)) {
    throw new Error("seoData.js yüklenemedi");
  }
  return mod;
};

// İçerik katmanı (Content Enrichment fazı): sayfadaki görünür FAQ ile schema'nın
// birebir aynı kaynaktan gelmesi için seoContent.js de yüklenir.
const loadSeoContent = () => {
  const raw = fs.readFileSync(seoContentPath, "utf8");
  const transformed =
    raw.replace(/export const /g, "const ") + "\nmodule.exports = { seoContent };\n";
  const context = { module: { exports: {} } };
  vm.createContext(context);
  vm.runInContext(transformed, context);
  const mod = context.module.exports;
  if (!mod || typeof mod.seoContent !== "object") {
    throw new Error("seoContent.js yüklenemedi");
  }
  return mod.seoContent;
};

const attrEscape = (value) =>
  String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

const jsonLdSerialize = (obj) => JSON.stringify(obj).replace(/<\//g, "<\\/");

// Şablonda pattern bulunamazsa build'i düşür (CRA minify formatı değişirse
// sessizce yanlış head üretmek yerine hata ver).
const mustReplace = (html, pattern, replacement, label) => {
  if (!pattern.test(html)) {
    throw new Error(`Şablonda bulunamadı: ${label} (${pattern})`);
  }
  return html.replace(pattern, () => replacement);
};

// CRA `homepage: "./"` ile derlendiği için (Capacitor native build göreli yol
// ister) asset'ler `./static/...` olarak referanslanır. Alt dizinde servis
// edilen shell'lerde bu yol `/cozumler/<slug>/static/...` olarak çözülür ve
// nginx SPA fallback'i JS yerine HTML döndürür → sayfa boş açılır. Bu yüzden
// yalnızca alt dizin shell'lerinde asset yolları köke sabitlenir.
const absolutiseAssetPaths = (html) => {
  const out = html.replace(/(\b(?:src|href)=)"\.\//g, '$1"/');
  if (/(?:src|href)="\.\//.test(out)) {
    throw new Error("Göreli asset yolu kaldırılamadı");
  }
  if (!/(?:src|href)="\/static\//.test(out)) {
    throw new Error("Kök asset referansı bulunamadı (build çıktısı değişmiş olabilir)");
  }
  return out;
};

const buildHeadHtml = ({ lang, title, description, canonical, alternates, ogLocale, ogImage, jsonLd }) => {
  let extra = `<link rel="canonical" href="${attrEscape(canonical)}"/>`;
  for (const alt of alternates) {
    extra += `<link rel="alternate" hreflang="${alt.hreflang}" href="${attrEscape(alt.href)}"/>`;
  }
  extra += `<meta property="og:url" content="${attrEscape(canonical)}"/>`;
  extra += `<meta property="og:locale" content="${ogLocale}"/>`;
  extra += `<meta name="robots" content="index,follow"/>`;
  if (ogImage) {
    extra += `<meta property="og:image" content="${attrEscape(ogImage)}"/>`;
  }
  if (jsonLd) {
    extra += `<script type="application/ld+json">${jsonLdSerialize(jsonLd)}</script>`;
  }
  return { extra };
};

const renderPage = (template, opts) => {
  const { lang, title, description } = opts;
  let html = template;

  html = mustReplace(html, /<html lang="[^"]*"/, `<html lang="${lang}"`, "html lang");
  html = mustReplace(html, /<title>[^<]*<\/title>/, `<title>${attrEscape(title)}</title>`, "title");
  html = mustReplace(
    html,
    /<meta name="description" content="[^"]*"\s*\/?>/,
    `<meta name="description" content="${attrEscape(description)}"/>`,
    "meta description"
  );
  html = mustReplace(
    html,
    /<meta property="og:title" content="[^"]*"\s*\/?>/,
    `<meta property="og:title" content="${attrEscape(title)}"/>`,
    "og:title"
  );
  html = mustReplace(
    html,
    /<meta property="og:description" content="[^"]*"\s*\/?>/,
    `<meta property="og:description" content="${attrEscape(description)}"/>`,
    "og:description"
  );
  // Statik şablondaki sabit og:image'ı locale domain'li versiyonla değiştir
  html = mustReplace(
    html,
    /<meta property="og:image" content="[^"]*"\s*\/?>/,
    `<meta property="og:image" content="${attrEscape(opts.ogImage)}"/>`,
    "og:image"
  );

  const { extra } = buildHeadHtml(opts);
  html = mustReplace(html, /<\/head>/, `${extra}</head>`, "</head>");
  return html;
};

const main = () => {
  if (!fs.existsSync(templatePath)) {
    throw new Error(`build/index.html yok — önce 'npm run build' çalıştırılmalı: ${templatePath}`);
  }

  const template = fs.readFileSync(templatePath, "utf8");
  const { seoData, SEO_ORIGINS, CATEGORY_PATHS, HREFLANG_PAIRS, homeSeo } = loadSeoModule();
  const seoContent = loadSeoContent();

  const getPath = (entry) => `/${CATEGORY_PATHS[entry.category][entry.locale]}/${entry.slug}`;
  const getUrl = (entry) => `${SEO_ORIGINS[entry.locale]}${getPath(entry)}`;
  const getAlternate = (entry) => {
    const pair = HREFLANG_PAIRS.find(([tr, en]) =>
      entry.locale === "tr" ? tr === entry.slug : en === entry.slug
    );
    if (!pair) return null;
    const altSlug = entry.locale === "tr" ? pair[1] : pair[0];
    const altLocale = entry.locale === "tr" ? "en-GB" : "tr";
    return seoData.find(
      (i) => i.category === entry.category && i.slug === altSlug && i.locale === altLocale
    );
  };

  let written = 0;

  // --- 1) Programmatic SEO sayfaları ---
  for (const entry of seoData) {
    const lang = entry.locale === "tr" ? "tr" : "en-GB";
    const ogLocale = entry.locale === "tr" ? "tr_TR" : "en_GB";
    const canonical = getUrl(entry);
    const alt = getAlternate(entry);
    const alternates = alt
      ? [
          { hreflang: "tr-TR", href: getUrl(entry.locale === "tr" ? entry : alt) },
          { hreflang: "en-GB", href: getUrl(entry.locale === "en-GB" ? entry : alt) },
        ]
      : [];

    const softwareApp = {
      "@type": "SoftwareApplication",
      name: "PLANN",
      headline: entry.h1 || entry.title,
      description: entry.metaDescription,
      url: canonical,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web, iOS, Android",
      inLanguage: lang === "tr" ? "tr-TR" : "en-GB",
      publisher: { "@type": "Organization", name: "PLANNAPP LTD", url: "https://plannapp.co/" },
    };

    // Sayfanın görünür FAQ'ı varsa (seoContent.js) statik shell'e de aynı
    // FAQPage schema'sı eklenir — runtime (SeoWrapper) ile birebir aynı yapı.
    const pageContent = seoContent[`${entry.locale}:${entry.category}:${entry.slug}`];
    const jsonLd =
      pageContent && Array.isArray(pageContent.faq) && pageContent.faq.length > 0
        ? {
            "@context": "https://schema.org",
            "@graph": [
              softwareApp,
              {
                "@type": "FAQPage",
                mainEntity: pageContent.faq.map((item) => ({
                  "@type": "Question",
                  name: item.q,
                  acceptedAnswer: { "@type": "Answer", text: item.a },
                })),
              },
            ],
          }
        : { "@context": "https://schema.org", ...softwareApp };

    const html = renderPage(template, {
      lang,
      title: entry.title,
      description: entry.metaDescription,
      canonical,
      alternates,
      ogLocale,
      ogImage: `${SEO_ORIGINS[entry.locale]}/plannlogo.png`,
      jsonLd,
    });

    const outDir = path.join(buildDir, CATEGORY_PATHS[entry.category][entry.locale], entry.slug);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "index.html"), absolutiseAssetPaths(html), "utf8");
    written++;
  }

  // --- 2) Ana sayfa varyantları (host bazlı: nginx map seçer) ---
  const trT = JSON.parse(fs.readFileSync(trTranslationsPath, "utf8"));
  const enT = JSON.parse(fs.readFileSync(enTranslationsPath, "utf8"));

  const faqFrom = (translations) => {
    const faq = translations?.landing?.faq || {};
    const items = [];
    for (let i = 1; i <= FAQ_COUNT; i++) {
      const q = faq[`q${i}`];
      const a = faq[`a${i}`];
      if (q && a) {
        items.push({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } });
      }
    }
    return items;
  };

  const homeAlternates = [
    { hreflang: "tr-TR", href: "https://plannapp.co/" },
    { hreflang: "en-GB", href: "https://plannapp.co.uk/" },
    { hreflang: "x-default", href: "https://plannapp.co/" },
  ];

  const homeJsonLd = (locale, canonical, lang, description, faqItems) => {
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
        "@id": `${canonical}#website`,
        name: "PLANN",
        url: canonical,
        inLanguage: lang,
        publisher: { "@id": "https://plannapp.co/#organization" },
      },
      {
        "@type": "SoftwareApplication",
        name: "PLANN",
        description,
        url: canonical,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web, iOS, Android",
        inLanguage: lang,
        publisher: { "@id": "https://plannapp.co/#organization" },
      },
    ];
    if (faqItems.length > 0) graph.push({ "@type": "FAQPage", mainEntity: faqItems });
    return { "@context": "https://schema.org", "@graph": graph };
  };

  const homeVariants = [
    { file: "index-tr.html", locale: "tr", lang: "tr", ogLocale: "tr_TR", faq: faqFrom(trT) },
    { file: "index-en.html", locale: "en-GB", lang: "en-GB", ogLocale: "en_GB", faq: faqFrom(enT) },
  ];

  for (const v of homeVariants) {
    const seo = homeSeo[v.locale];
    const canonical = `${SEO_ORIGINS[v.locale]}/`;
    const html = renderPage(template, {
      lang: v.lang,
      title: seo.title,
      description: seo.metaDescription,
      canonical,
      alternates: homeAlternates,
      ogLocale: v.ogLocale,
      ogImage: `${SEO_ORIGINS[v.locale]}/plannlogo.png`,
      jsonLd: homeJsonLd(v.locale, canonical, v.lang, seo.metaDescription, v.faq),
    });
    fs.writeFileSync(path.join(buildDir, v.file), html, "utf8");
    written++;
  }

  process.stdout.write(`SEO HTML shells generated: ${written} dosya (build/)\n`);
};

main();
