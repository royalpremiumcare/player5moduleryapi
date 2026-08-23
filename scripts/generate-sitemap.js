// PLANN sitemap/robots üretici — SEO domain mimarisi (Ağustos 2026)
//
// İki localized sitemap üretir:
//   sitemap-tr.xml → https://plannapp.co    (ana sayfa + /cozumler + /ozellikler)
//   sitemap-uk.xml → https://plannapp.co.uk (ana sayfa + /solutions + /features)
//
// Kurallar:
// - Yalnızca self-canonical URL'ler sitemap'e girer (EN sayfalar TR sitemap'e GİRMEZ).
// - Gerçek eşdeğer TR↔EN çiftlerinde xhtml:link hreflang alternates eklenir.
// - robots-tr.txt / robots-uk.txt kendi domainlerinin sitemap'ini işaret eder.
// - sitemap.xml / robots.txt TR kopyası olarak da yazılır (nginx host map'i
//   co.uk isteklerini -uk varyantına yönlendirir; TR default'tur).
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const seoDataPath = path.resolve(
  __dirname,
  "..",
  "frontend",
  "src",
  "data",
  "seoData.js"
);

const publicDir = path.resolve(__dirname, "..", "frontend", "public");
const buildDir = path.resolve(__dirname, "..", "frontend", "build");

const loadSeoModule = () => {
  const raw = fs.readFileSync(seoDataPath, "utf8");

  const transformed =
    raw.replace(/export const /g, "const ") +
    "\nmodule.exports = { seoData, SEO_ORIGINS, CATEGORY_PATHS, HREFLANG_PAIRS };\n";

  const context = { module: { exports: {} } };
  vm.createContext(context);
  vm.runInContext(transformed, context);

  const mod = context.module.exports;
  if (!mod || !Array.isArray(mod.seoData) || !mod.SEO_ORIGINS || !mod.CATEGORY_PATHS) {
    throw new Error("Could not load seoData module from src/data/seoData.js");
  }
  return mod;
};

const xmlEscape = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&apos;");

const main = () => {
  const { seoData, SEO_ORIGINS, CATEGORY_PATHS, HREFLANG_PAIRS } = loadSeoModule();

  const getPath = (entry) =>
    `/${CATEGORY_PATHS[entry.category][entry.locale]}/${entry.slug}`;
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

  const lastMod = new Date().toISOString();

  const urlBlock = (loc, alternates) => {
    let block = `  <url>\n    <loc>${xmlEscape(loc)}</loc>\n    <lastmod>${xmlEscape(lastMod)}</lastmod>\n`;
    for (const alt of alternates) {
      block += `    <xhtml:link rel="alternate" hreflang="${alt.hreflang}" href="${xmlEscape(alt.href)}"/>\n`;
    }
    block += `  </url>`;
    return block;
  };

  const homeAlternates = [
    { hreflang: "tr-TR", href: "https://plannapp.co/" },
    { hreflang: "en-GB", href: "https://plannapp.co.uk/" },
    { hreflang: "x-default", href: "https://plannapp.co/" },
  ];

  const buildSitemap = (locale) => {
    const origin = SEO_ORIGINS[locale];
    const blocks = [urlBlock(`${origin}/`, homeAlternates)];

    const items = seoData
      .filter((i) => i.locale === locale)
      .sort((a, b) => getUrl(a).localeCompare(getUrl(b)));

    for (const item of items) {
      const alt = getAlternate(item);
      const alternates = alt
        ? [
            {
              hreflang: "tr-TR",
              href: getUrl(item.locale === "tr" ? item : alt),
            },
            {
              hreflang: "en-GB",
              href: getUrl(item.locale === "en-GB" ? item : alt),
            },
          ]
        : [];
      blocks.push(urlBlock(getUrl(item), alternates));
    }

    return (
      `<?xml version="1.0" encoding="UTF-8"?>\n` +
      `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n` +
      blocks.join("\n") +
      `\n</urlset>\n`
    );
  };

  const buildRobots = (locale) =>
    `User-agent: *\n` +
    `Allow: /\n` +
    `\n` +
    `Sitemap: ${SEO_ORIGINS[locale]}/sitemap.xml\n`;

  const outputs = {
    "sitemap-tr.xml": buildSitemap("tr"),
    "sitemap-uk.xml": buildSitemap("en-GB"),
    "robots-tr.txt": buildRobots("tr"),
    "robots-uk.txt": buildRobots("en-GB"),
  };
  // Varsayılan dosyalar = TR (nginx map co.uk isteklerini -uk varyantına çevirir)
  outputs["sitemap.xml"] = outputs["sitemap-tr.xml"];
  outputs["robots.txt"] = outputs["robots-tr.txt"];

  fs.mkdirSync(publicDir, { recursive: true });
  const dirs = [publicDir];
  if (fs.existsSync(buildDir)) dirs.push(buildDir);

  for (const dir of dirs) {
    for (const [name, content] of Object.entries(outputs)) {
      fs.writeFileSync(path.join(dir, name), content, "utf8");
    }
  }

  const trCount = (outputs["sitemap-tr.xml"].match(/<loc>/g) || []).length;
  const ukCount = (outputs["sitemap-uk.xml"].match(/<loc>/g) || []).length;
  process.stdout.write(
    `Generated sitemaps/robots in: ${dirs.join(", ")}\n` +
      `TR URLs: ${trCount}, UK URLs: ${ukCount}\n`
  );
};

main();
