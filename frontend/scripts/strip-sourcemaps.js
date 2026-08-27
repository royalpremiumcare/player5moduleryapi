// PLANN mobil paket küçültücü — source map temizliği (Ağustos 2026)
//
// Neden: `build/` klasörünün ~%68'i source map dosyasıdır (19 MB'ın 13 MB'ı).
// Bu klasör iki yere gidiyor:
//   1. Capgo OTA bundle'ı  → her kullanıcı her güncellemede indiriyor
//   2. Native store build'i → `cap sync` ile uygulamanın içine gömülüyor
//
// Capgo `autoUpdate: "atInstall"` modunda güncelleme SPLASH EKRANI BEKLETİLİRKEN
// indiriliyor (bkz. capacitor.config.json + ForceUpdateGate emniyet supabı).
// Yani indirilen her fazladan megabayt doğrudan ilk açılış süresine biniyor.
// Native tarafta map'lerin hiçbir faydası da yok: Sentry `capacitor://localhost`
// adresinden map çekemez, dolayısıyla bu 13 MB telefonda tamamen ölü ağırlık.
//
// WEB deploy'u ETKİLEMEZ: web imajı kendi içinde `npm run build` çalıştırıyor ve
// map'ler orada duruyor; Sentry web tarafında stack trace'leri HTTP üzerinden
// map çekerek çözmeye devam ediyor.
//
// Kullanım: `npm run build:app` (craco build + bu script). Codemagic iOS/Android
// workflow'ları bu script'i çağırır.
const fs = require("fs");
const path = require("path");

const buildDir = path.resolve(__dirname, "..", "build");

if (!fs.existsSync(buildDir)) {
  console.error("strip-sourcemaps: build/ bulunamadı — önce `npm run build` çalıştır.");
  process.exit(1);
}

// `.js` ve `.css` dosyalarının sonundaki sourceMappingURL yorumu, map dosyası
// silindikten sonra WebView'de 404 üretir. Yorumu da kaldırıyoruz.
const SOURCE_MAPPING_COMMENT = /\n?\/[/*]#\s*sourceMappingURL=[^\s*]+\s*\*?\/?\s*$/;

let removedFiles = 0;
let removedBytes = 0;
let cleanedRefs = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
      continue;
    }
    if (entry.name.endsWith(".map")) {
      removedBytes += fs.statSync(full).size;
      fs.unlinkSync(full);
      removedFiles += 1;
      continue;
    }
    if (entry.name.endsWith(".js") || entry.name.endsWith(".css")) {
      const original = fs.readFileSync(full, "utf8");
      const stripped = original.replace(SOURCE_MAPPING_COMMENT, "");
      if (stripped !== original) {
        fs.writeFileSync(full, stripped);
        cleanedRefs += 1;
      }
    }
  }
}

walk(buildDir);

const mb = (bytes) => (bytes / 1024 / 1024).toFixed(2);
console.log(
  `strip-sourcemaps: ${removedFiles} map dosyası silindi (${mb(removedBytes)} MB), ` +
    `${cleanedRefs} dosyadan sourceMappingURL referansı kaldırıldı.`
);
