const fs = require("fs");
const path = require("path");
const vm = require("vm");

const BASE_URL = (process.env.SITEMAP_BASE_URL || "https://plannapp.co").replace(
  /\/+$/,
  ""
);

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
const sitemapPath = path.join(publicDir, "sitemap.xml");
const robotsPath = path.join(publicDir, "robots.txt");

const loadSeoData = () => {
  const raw = fs.readFileSync(seoDataPath, "utf8");

  const transformed =
    raw.replace(/export const /g, "const ") +
    "\nmodule.exports = { seoData, getSeoEntry };\n";

  const context = { module: { exports: {} } };
  vm.createContext(context);
  vm.runInContext(transformed, context);

  if (!context.module.exports || !Array.isArray(context.module.exports.seoData)) {
    throw new Error("Could not load seoData from src/data/seoData.js");
  }

  return context.module.exports.seoData;
};

const xmlEscape = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&apos;");

const buildAbsoluteUrl = (p) => `${BASE_URL}${p}`;

const main = () => {
  const allItems = loadSeoData();

  const trItems = allItems.filter((x) => x.locale === "tr");
  const enItems = allItems.filter((x) => x.locale === "en-GB");

  const dedupe = (items) => {
    const m = new Map();
    for (const item of items) {
      const key = `${item.category}:${item.slug}`;
      if (!m.has(key)) m.set(key, item);
    }
    return Array.from(m.values());
  };

  const urls = [];

  for (const item of dedupe(trItems)) {
    const isVertical = item.category === "vertical";
    const trPath = isVertical
      ? `/cozumler/${item.slug}`
      : `/ozellikler/${item.slug}`;
    urls.push(buildAbsoluteUrl(trPath));
  }

  for (const item of dedupe(enItems)) {
    const isVertical = item.category === "vertical";
    const enPath = isVertical
      ? `/solutions/${item.slug}`
      : `/features/${item.slug}`;
    urls.push(buildAbsoluteUrl(enPath));
  }

  urls.sort((a, b) => a.localeCompare(b));

  const lastMod = new Date().toISOString();

  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls
      .map(
        (loc) =>
          `  <url>\n` +
          `    <loc>${xmlEscape(loc)}</loc>\n` +
          `    <lastmod>${xmlEscape(lastMod)}</lastmod>\n` +
          `  </url>`
      )
      .join("\n") +
    `\n</urlset>\n`;

  fs.mkdirSync(publicDir, { recursive: true });
  fs.writeFileSync(sitemapPath, xml, "utf8");

  const robots =
    `User-agent: *\n` +
    `Allow: /\n` +
    `\n` +
    `Sitemap: ${BASE_URL}/sitemap.xml\n`;

  fs.writeFileSync(robotsPath, robots, "utf8");

  if (fs.existsSync(buildDir)) {
    fs.writeFileSync(path.join(buildDir, "sitemap.xml"), xml, "utf8");
    fs.writeFileSync(path.join(buildDir, "robots.txt"), robots, "utf8");
  }

  process.stdout.write(
    `Generated:\n- ${sitemapPath}\n- ${robotsPath}\nBase URL: ${BASE_URL}\nURLs: ${urls.length}\n`
  );
};

main();
