# PLANN — SEO / AI Search Implementasyon Planı

Tarih: 17 Ağustos 2026
Kaynak: `PLANN_SEO_AI_SEARCH_TAM_SOHBET_OZETI_V2_FULL.txt` + `PLANN_SEO_AI_SEARCH_TAM_SOHBET_OZETI_FINAL.txt`
Durum: **UYGULANDI (17 Ağustos 2026)** — Bölüm 1-21 deploy edildi ve doğrulandı. Kalan manuel adımlar: Cloudflare AI bot blokları + cache purge (Bölüm 13) ve Search Console (Bölüm 22).

Onaylanan kararlar (kullanıcı, 17 Ağustos 2026):
1. `.com` ve `.com.tr` kalıcı 301 ile `plannapp.co`'ya yönlendirilecek.
2. Cloudflare'daki AI bot blokları açılacak (plan adımı olarak dahil).

---

## 1. Mevcut Mimari Audit (kod + canlı prod ile doğrulandı)

Rapordaki varsayımlar gerçek codebase ve canlı HTTP testleriyle doğrulandı. Sonuçlar:

| Konu | Rapor varsayımı | Gerçek durum (doğrulanmış) |
|---|---|---|
| www → non-www redirect | "www düz domaine atıyor" | **YANLIŞ — 8 host varyantının tümü 200 dönüyor, hiç 301 yok** |
| .com/.com.tr | duplicate riski | Doğru — aynı frontend'e (8081) proxy'leniyor (`/etc/nginx/sites-enabled/plannapp` #4 blok) |
| canonical yok | tamamen yok | **Kısmen var**: `SeoWrapper.jsx` sadece `/cozumler|/solutions|/ozellikler|/features` sayfalarında canonical basıyor ama `window.location.origin` kullandığı için .com'dan girilirse canonical .com oluyor (hatalı) |
| hreflang yok | yok | Doğru — hiçbir yerde yok |
| index.html | lang=en + TR metadata | Doğru — `frontend/public/index.html`: `lang="en"`, `title=PLANN`, TR description, canonical/hreflang/JSON-LD yok |
| SSR/prerender | bilinmiyor | Yok — saf CSR (react-snap/prerender yok, `craco.config.js` temiz) |
| sitemap içeriği | doğrulanamadı | 40 URL, hepsi `plannapp.co` domaininde (15 TR + 15 EN vertical, 5+5 feature). **Ana sayfa yok, hreflang yok, .co.uk aynı .co sitemap'ini sunuyor.** Üretici: `scripts/generate-sitemap.js` |
| robots.txt | açık | Origin dosyası açık; **AMA Cloudflare canlıda "Managed Content" robots bloğu enjekte ediyor: GPTBot, ClaudeBot, Google-Extended, CCBot, meta-externalagent → `Disallow: /` + `ai-train=no`** |
| Googlebot/OAI-SearchBot erişimi | doğrulanmadı | Canlı test: Googlebot / OAI-SearchBot / GPTBot / Bingbot UA'ları 200 alıyor (HTML seviyesi engel yok; blok sadece robots.txt sinyali) |
| JSON-LD | bilinmiyor | Sadece `SeoWrapper` üretimi var; vertical sayfalar `BarberShop`/`Dentist` gibi **yanlış** tipler kullanıyor (sayfa yazılım tanıtımı, berber dükkanı değil) |

Diğer bulgular:
- Metadata altyapısı hazır: `react-helmet-async` kurulu, `HelmetProvider` `index.js`'te mount edilmiş.
- Landing (`LandingPage.js`) sadece `document.title` set ediyor; Helmet yok. Landing'de 11 maddelik gerçek FAQ var (FAQPage schema fırsatı).
- Dil tespiti `frontend/src/i18n/index.js`'te hostname bazlı (`co.uk` → en, diğerleri → tr) — doğru sırada çalışıyor.
- Frontend container nginx'i (`frontend/default.conf`) `try_files $uri $uri/ /index.html` ile statik build sunuyor; host header geçiyor → host bazlı dosya seçimi mümkün.
- Route kaynağı `AppRouter.js`; `AppRoutes.jsx` sadece `ProgrammaticSeoPage` sağlıyor.

## 2. Domain / Redirect Analizi ve Hedef Mimari

Mevcut: 4 domain x (www + apex) = 8 kopya HTML, Cloudflare proxy arkasında, konsolidasyon yok.

Hedef:
```
plannapp.co          → TR ana site (self-canonical, lang=tr)
plannapp.co.uk       → UK ana site (self-canonical, lang=en-GB)
www.plannapp.co      → 301 → plannapp.co
www.plannapp.co.uk   → 301 → plannapp.co.uk
plannapp.com  (+www) → 301 → plannapp.co
plannapp.com.tr (+www) → 301 → plannapp.co
api.plannapp.co      → değişmez
```

Uygulama yeri: `/etc/nginx/sites-enabled/plannapp` (host nginx) + repo kopyası `system_configs/nginx_plannapp.conf`.

Değişiklikler:
- 443 bloğundan `www.plannapp.co`'yu ayırıp `return 301 https://plannapp.co$request_uri` yapan ayrı server bloğu.
- `.co.uk` bloğundan `www.plannapp.co.uk`'yi ayırıp apex'e 301.
- `.com` ve `.com.tr` 443 blokları: `include snippets/plannapp_proxy.conf` yerine `return 301 https://plannapp.co$request_uri`.
- 80 portu blokları aynı hedeflere tek hop 301 (çift zincir bırakma: `http://www.plannapp.com` → doğrudan `https://plannapp.co`).
- `/appstore`, `/playstore`, AASA location'ları `.co` bloğunda kalır (değişmez).
- Ön kontrol: backend/frontend kodunda ve dış entegrasyonlarda (Stripe/PayTR webhook, e-posta template, WhatsApp) `plannapp.com` veya `plannapp.com.tr` referansı grep ile taranır; varsa önce düzeltilir.
- Loop riski yok: 301'ler host bazlı, proto bazlı değil; Cloudflare SSL mode etkilenmez.

## 3. .co / .co.uk Stratejisi

- `.co` = Türkiye sitesi: `lang="tr"`, TR title/description, self-canonical `https://plannapp.co/...`
- `.co.uk` = UK sitesi: `lang="en-GB"`, EN title/description, self-canonical `https://plannapp.co.uk/...`
- EN sayfalar (`/solutions/*`, `/features/*`): canonical **`plannapp.co.uk`** olur. `.co` üzerinden erişilen `/solutions/*` cross-domain canonical ile `.co.uk`'yi gösterir (route silinmez, 404 olmaz).
- **Bilinen risk:** EN /solutions sayfaları şu an `.co` üzerinde indexli ve gösterim alıyor (barber 77, nail 92 gösterim). Canonical'ın `.co.uk`'ye taşınması sıralamanın haftalar içinde transferi demektir; geçici dalgalanma olabilir. Mitigasyon: slug'lar birebir aynı kalır, karşılıklı hreflang + sitemap + tek seferlik index request ile transfer hızlandırılır, GSC'de izlenir.

## 4. .com / .com.tr Stratejisi

Kullanıcı onayıyla: alternatif/koruma domaini olarak kalırlar, 301 → `plannapp.co`. Ayrı SEO sitesi yapılmaz, sitemap/canonical üretilmez.

## 5. www / non-www

Tek canonical host = apex (non-www). Gerekçe: GSC'de `plannapp.co` apex zaten indexli. Tüm www varyantları 301 → apex.

## 6. Canonical

- `SeoWrapper.jsx`: canonical `window.location.origin` yerine locale'den sabit domain ile üretilir:
  - `locale === "tr"` → `https://plannapp.co` + path
  - `locale === "en-GB"` → `https://plannapp.co.uk` + path
- Ana sayfa: yeni `SiteSeo` bileşeni host'a göre self-canonical basar (`.co.uk` host → `https://plannapp.co.uk/`, diğer → `https://plannapp.co/`).
- Legal sayfalar (`/privacy`, `/terms`, `/refund`): self-canonical (düşük öncelik, aynı mekanizma).
- Login/register/dashboard gibi uygulama sayfalarına canonical eklenmez (index hedefi değil).

## 7. Hreflang

- `frontend/src/data/seoData.js`'e `pairKey` alanı eklenir; yalnızca gerçekten eşdeğer TR↔EN sayfalar eşlenir (ör. `berber-randevu-programi` ↔ `barber-appointment-software`). Eşdeğeri olmayan sayfa hreflang almaz.
- Ana sayfa çifti:
```html
<link rel="alternate" hreflang="tr-TR" href="https://plannapp.co/" />
<link rel="alternate" hreflang="en-GB" href="https://plannapp.co.uk/" />
<link rel="alternate" hreflang="x-default" href="https://plannapp.co/" />
```
- Eşleşen sayfalarda iki tarafta da aynı küme (karşılıklılık şart). Hem Helmet (runtime) hem statik head (build-time) hem sitemap (`xhtml:link`) aynı eşlemeden beslenir.

## 8. HTML lang

- `frontend/public/index.html`: `lang="tr"` (TR varsayılan fallback).
- Runtime: `SiteSeo`/`SeoWrapper` Helmet ile `<html lang>` günceller (`tr` / `en-GB`). `SeoWrapper` bunu zaten yapıyor; ana sayfaya eklenecek.
- Build-time statik shell'lerde route diline göre lang gömülür.

## 9. Route Bazlı Title / Description

- Programmatic sayfalar zaten route bazlı (seoData) — korunur.
- Ana sayfa: `SiteSeo` ile host bazlı:
  - TR: `PLANN | Randevu Sistemi ve Online Randevu Uygulaması` + TR description (WhatsApp onay/hatırlatma vurgusu)
  - UK: `PLANN | Appointment & Booking Software` + EN description
- Final copy implementasyon sırasında i18n dosyalarına eklenir (hardcode yasak kuralına uygun).

## 10. Open Graph

- `SeoWrapper` + `SiteSeo`: `og:url` = canonical, `og:locale` = `tr_TR` / `en_GB`, `og:image` runtime'da da set edilir (şu an sadece statik index.html'de).
- `frontend/public/index.html` fallback OG değerleri TR'ye göre düzeltilir.

## 11. Sitemap

`scripts/generate-sitemap.js` yeniden yazılır — iki sitemap üretir:
- `sitemap-tr.xml`: `https://plannapp.co/` + `/cozumler/*` + `/ozellikler/*` (+ eşleşen sayfalarda `xhtml:link` hreflang)
- `sitemap-uk.xml`: `https://plannapp.co.uk/` + `/solutions/*` + `/features/*` (+ hreflang)
- Kurallar: yalnızca self-canonical URL'ler; `.co` üzerindeki EN URL'ler TR sitemap'e girmez; 301 hedefi URL yok.
- Servis: `frontend/default.conf`'ta `map $host` ile `sitemap.xml` isteği host'a göre doğru dosyaya rewrite edilir.

## 12. Robots.txt

- `robots-tr.txt` → `Sitemap: https://plannapp.co/sitemap.xml`
- `robots-uk.txt` → `Sitemap: https://plannapp.co.uk/sitemap.xml`
- `frontend/default.conf`'ta host bazlı seçim (sitemap ile aynı map).
- İçerik: `User-agent: * / Allow: /` korunur.

## 13. Googlebot / OAI-SearchBot / Cloudflare (MANUEL ADIM)

Canlı bulgu: Cloudflare "Managed robots.txt / Content Signals" özelliği GPTBot, ClaudeBot, Google-Extended, CCBot, Bytespider, meta-externalagent'ı `Disallow: /` ile blokluyor ve `ai-train=no` sinyali basıyor. **Bu, AI görünürlük hedefiyle doğrudan çelişiyor.**

Kullanıcı onaylı adım (Cloudflare panelinden, tüm zone'larda: .co, .co.uk, .com, .com.tr):
1. Security → Bots (veya Settings → Content Signals / managed robots.txt) → AI crawler bloklarını ve managed robots içeriğini kapat.
2. Super Bot Fight Mode / AI Scrapers and Crawlers ayarını "block" ise kaldır.
3. Doğrulama: `curl https://plannapp.co/robots.txt` çıktısında "BEGIN Cloudflare Managed content" bloğunun kaybolduğunu gör.

Not: HTML seviyesinde engel yok (Googlebot/OAI-SearchBot/GPTBot UA testleri 200 aldı); sorun yalnızca robots sinyali.

## 14. React SEO Rendering (SSR yerine güvenli yaklaşım)

Tam SSR/react-snap YAPILMAZ (monolit SPA'da kırılganlık riski, "çalışan uygulamayı bozma" kuralı). Bunun yerine **build-time statik head enjeksiyonu**:

- Yeni `scripts/generate-seo-html.js` (post-build): `build/index.html`'i şablon alıp seoData'daki her route için `build/cozumler/<slug>/index.html`, `build/solutions/<slug>/index.html` vb. dosyaları, `<head>` içi tamamen doğru (title, description, canonical, hreflang, lang, OG, JSON-LD) olacak şekilde üretir. Nginx `try_files $uri $uri/ ...` bunları otomatik yakalar.
- Ana sayfa: `build/index-tr.html` ve `build/index-en.html` iki varyant; `frontend/default.conf`'ta `map $host` ile `location = /` doğru varyantı sunar. Diğer SPA route'ları `/index.html` (TR fallback) ile çalışmaya devam eder.
- Build entegrasyonu: `frontend/Dockerfile` build aşamasına (veya package.json `build` scriptine) generator eklenir. Generator hata verirse build düşer (sessiz bozulma yok).
- Kazanç: Googlebot/AI crawler ilk HTML'de doğru sinyalleri görür; JS render'a bağımlılık kalkar. Body içeriği CSR kalır (ana sayfa zaten indexli olduğu için kabul edilebilir; ileride H1+intro'nun statik shell'e gömülmesi opsiyonel iyileştirme).

## 15. JSON-LD / Structured Data

- Ana sayfa (`SiteSeo` + statik shell): `Organization` (PLANNAPP LTD), `WebSite`, `SoftwareApplication` (gerçek bilgilerle; uydurma rating/review/price YOK), landing'deki 11 gerçek FAQ'dan `FAQPage`.
- Vertical sayfalar: `schemaType: "BarberShop"` gibi yanlış tipler `SoftwareApplication` + `audience` alanına çevrilir (sayfa yazılımı anlatıyor, işletmenin kendisini değil).

## 16. Solutions / Çözümler Sayfaları

- Bu fazda: doğru canonical (sabit domain), hreflang çiftleri, lang, OG, düzeltilmiş JSON-LD, statik head shell.
- İçerik zenginleştirme (sektöre özel body, FAQ, screenshot, internal cross-link) **ayrı bir içerik fazı** olarak plan dışında bırakıldı — önce teknik sinyaller temizlenir, GSC'de traction izlenir, sonra en çok gösterim alan sayfalardan başlanarak içerik büyütülür.

## 17. Internal Linking

- Mevcut `SeoLinks` (landing footer) korunur; sitemap + ana sayfa hreflang eklendikten sonra yeterli. Ek internal linking içerik fazına ertelendi.

## 18. Riskler

| Risk | Etki | Mitigasyon |
|---|---|---|
| EN /solutions traction'ının .co → .co.uk canonical transferi | Geçici sıralama dalgalanması | Slug'lar aynı, hreflang + sitemap + tek index request; GSC takip |
| Nginx redirect hatası (loop / yanlış host) | Site erişilemez | Host bazlı 301 (proto bazlı değil), `nginx -t` + canlı curl matrisi, tek satır rollback |
| .com/.com.tr'ye bağlı dış referans (webhook, e-posta linki) | Kırık link | Uygulamadan önce codebase + entegrasyon grep taraması |
| Statik shell generator build'i bozar | Deploy düşer | Generator build pipeline'da fail-fast; üretilen dosyalar yoksa SPA fallback zaten çalışır |
| Yanlış hreflang eşleşmesi | Index karışıklığı | Sadece elle doğrulanmış `pairKey` çiftleri; sahte eşleşme yok |
| Cloudflare cache eski HTML sunar | Sinyaller geç görünür | Deploy sonrası CF cache purge |

Mobil uygulama etkisi: **YOK.** Hiçbir API endpoint'ine/response modeline dokunulmuyor (api-contract kuralı ihlali yok). Head/meta değişiklikleri Capacitor WebView'i etkilemez; `.co` API host'u değişmiyor.

## 19. Etkilenecek Dosyalar

| Dosya | Değişiklik |
|---|---|
| `/etc/nginx/sites-enabled/plannapp` + `system_configs/nginx_plannapp.conf` | www + .com/.com.tr 301 blokları |
| `frontend/default.conf` | `map $host` → homepage varyantı, sitemap/robots seçimi |
| `frontend/public/index.html` | lang=tr, TR fallback title/description/OG |
| `frontend/src/components/SeoWrapper.jsx` | Sabit domain canonical, hreflang, og:url/og:locale/og:image, SoftwareApplication JSON-LD |
| `frontend/src/components/SiteSeo.jsx` (YENİ) | Ana sayfa host-bazlı head + JSON-LD |
| `frontend/src/components/LandingPage.js` | `SiteSeo` mount (document.title hack'i kalkar) |
| `frontend/src/data/seoData.js` | `pairKey` hreflang eşleme alanı |
| `scripts/generate-sitemap.js` | İki sitemap + hreflang + robots varyantları |
| `scripts/generate-seo-html.js` (YENİ) | Build-time statik head shell üretici |
| `frontend/Dockerfile` / `frontend/package.json` | Build'e generator entegrasyonu |
| `frontend/src/i18n/locales/{tr,en}/translation.json` | Yeni meta metinleri |

## 20. Implementasyon Sırası

1. Ön tarama: codebase'de `.com`/`.com.tr` referans grep'i.
2. Nginx 301 konsolidasyonu (host nginx + repo kopyası) → `nginx -t` → reload → curl matrisi.
3. Cloudflare AI bot bloklarını kapat (manuel, kullanıcı paneli — ajan yönlendirir) + cache purge.
4. Frontend runtime SEO: SeoWrapper düzeltme, SiteSeo, seoData pairKey, index.html fallback.
5. Sitemap/robots üretici + frontend nginx host map.
6. Statik head shell generator + build entegrasyonu.
7. `docker compose build frontend && docker compose up -d frontend` → validasyon.
8. Search Console adımları.

## 21. Validasyon Planı (deploy sonrası)

HTTP matrisi (curl, her biri için status + Location + hop sayısı):
```
https://plannapp.co/            → 200
https://www.plannapp.co/        → 301 → https://plannapp.co/ (tek hop)
https://plannapp.co.uk/         → 200
https://www.plannapp.co.uk/     → 301 → https://plannapp.co.uk/ (tek hop)
https://plannapp.com/ (+www)    → 301 → https://plannapp.co/ (tek hop)
https://plannapp.com.tr/ (+www) → 301 → https://plannapp.co/ (tek hop)
```
Raw HTML kontrolü (curl, JS render'sız):
- `plannapp.co/` → lang=tr, TR title/description, canonical `.co`, hreflang çifti, JSON-LD
- `plannapp.co.uk/` → lang=en-GB, EN title/description, canonical `.co.uk`, hreflang çifti
- `plannapp.co/cozumler/berber-randevu-programi` → route'a özel head
- `plannapp.co.uk/solutions/barber-appointment-software` → route'a özel head + canonical `.co.uk`
- `plannapp.co/solutions/barber-appointment-software` → canonical `.co.uk` (cross-domain)
- Her iki domainde `sitemap.xml` ve `robots.txt` doğru varyant
- Googlebot/OAI-SearchBot/GPTBot UA → 200 + robots.txt'te Cloudflare blok yok
- Redirect loop yok, canonical ↔ redirect çelişkisi yok
- Booking/admin smoke test: `/:slug` public booking + login + dashboard açılıyor

## 22. Search Console Planı

1. Tüm teknik doğrulamalar geçtikten SONRA (öncesinde index request YAPMA):
2. `.co` property: `sitemap.xml` (TR) yeniden gönder.
3. `.co.uk` property: `sitemap.xml` (UK) gönder; `https://plannapp.co.uk/` için TEK seferlik "Dizine eklenmesini iste".
4. 1–2 hafta izleme: `.co.uk` user-declared vs Google-selected canonical; `/solutions/*` gösterimlerinin `.co`'dan `.co.uk`'ye geçişi; TR sorgu gösterimleri.
5. Sonraki faz kararı (içerik zenginleştirme) bu verilerle verilir.
