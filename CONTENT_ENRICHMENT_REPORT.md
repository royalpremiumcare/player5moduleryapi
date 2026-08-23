# CONTENT ENRICHMENT REPORT — PLANN Landing Pages

**Tarih:** 17 Ağustos 2026
**Faz:** Content Enrichment (teknik SEO fazından ayrı; teknik altyapıya dokunulmadı)

---

## 1. Özet

| Metrik | Değer |
|---|---|
| Güncellenen sayfa | **40 / 40** (20 TR + 20 EN) |
| Eklenen FAQ | **173 soru-cevap** (sayfa başına 4–5) |
| Eklenen internal link | **200** (sayfa başına 5, tekil hedefler) |
| Yeni H2 bölümü | Sayfa başına 5–6 (problemler, iş akışı, sektör senaryosu, trust, FAQ, ilgili sayfalar) |
| Yeni H3 bölümü | Sayfa başına 3–6 (problem kartları + akış adımları) |
| Kullanılan screenshot | 2 mevcut asset (yeniden kullanım) |
| Build | ✅ Başarılı |
| Production smoke test | ✅ 40/40 sayfa HTTP 200 + FAQPage schema |

---

## 2. Değişen dosyalar (bu fazda dokunulan HER ŞEY)

| Dosya | Değişiklik |
|---|---|
| `frontend/src/data/seoContent.js` | **YENİ** — 40 sayfanın tüm gövde içeriği (intro, H2/H3 bölümleri, FAQ, trust, CTA, internal linkler). Saf data; React ve statik shell üreticisi aynı kaynaktan okur. |
| `frontend/src/AppRoutes.jsx` | `ProgrammaticSeoPage` jenerik şablondan zengin layout'a dönüştürüldü (header, hero, screenshot, H2/H3 bölümleri, FAQ akordiyon, trust listesi, sektöre özgü CTA paneli, ilgili sayfalar, footer). Route yapısı ve slug'lar AYNEN korundu. |
| `frontend/src/components/SeoWrapper.jsx` | Additive: opsiyonel `faq` prop'u. FAQ varsa mevcut SoftwareApplication JSON-LD `@graph` içine alınıp yanına FAQPage eklenir. FAQ yoksa çıktı öncekiyle birebir aynı. |
| `frontend/scripts/generate-seo-html.js` | Additive: `seoContent.js` de yüklenir; sayfanın görünür FAQ'ı statik shell JSON-LD'sine aynı `@graph` yapısıyla eklenir. Mevcut head üretim mekanizması değişmedi. |

**Başka hiçbir dosyaya dokunulmadı.** (git'te görünen diğer değişiklikler önceki teknik SEO fazına ve önceki işlere aittir.)

---

## 3. Sayfa bazında eklenen içerik

Tüm sayfalar aynı iskelete oturur ama içerik %100 sayfaya özgüdür (kopya paragraf yok):
**intro (2 paragraf) → sektörün 3 problemi (H2+H3 kartlar) → PLANN'de iş akışı (H2) → sektöre özgü ek senaryo (H2) → trust listesi (H2) → FAQ (H2, 4–5 soru) → sektöre özgü CTA → ilgili sayfalar.**

### TR sektör sayfaları (/cozumler/*)

| Sayfa | Sektöre özgü açı | FAQ | Örnek CTA |
|---|---|---|---|
| berber-randevu-programi | Tıraş sırasında telefon, no-show, çift randevu; usta bazlı prim | 5 | "Makası bırakmadan randevu almaya başlayın" |
| kuafor-randevu-programi | Boya/kesim süre farkı, Instagram DM kaybı, boya formülü notu, seans paketi | 5 | "Salonunuzun takvimi kendi kendini doldursun" |
| guzellik-merkezi-randevu-programi | Lazer seans paketi takibi, uzman/oda çakışması, cihaz saati kaybı | 5 | "Merkezi tek panelden yönetmeye başlayın" |
| protez-tirnak-randevu-programi | Uygulama/dolgu süresi, dolgu hatırlatma, Instagram bio linki, renk notu | 4 | "Takviminizi tasarıma ayırın" |
| dis-klinigi-randevu-programi | No-show koltuk kaybı, sekreter yükü, hekim bazlı takvim, kontrol randevusu | 5 | "Kliniğinizin randevu düzenini bugün kurun" |
| psikolog-randevu-programi | Danışan gizliliği, seans arası mesaj trafiği, hatırlatmada içerik mahremiyeti | 4 | "Takviminizi sessiz bir asistana bırakın" |
| diyetisyen-randevu-programi | Kontrol randevusu düzeni, ilk görüşme/kontrol süre farkı, online danışmanlık | 4 | "Danışan takibinizi düzene sokun" |
| fizyoterapi-randevu-programi | Seans serisi takibi, atlanan seans = tedavi gecikmesi, terapist takvimi | 4 | "Seans düzeninizi sisteme bağlayın" |
| spor-salonu-randevu-programi | PT paket hakkı, antrenör takvimi, deneme antrenmanından üyeliğe | 4 | "Salon programınızı tek panele taşıyın" |
| pilates-studyo-randevu-programi | Reformer kapasitesi, ders paketi, eğitmen doluluk raporu | 4 | "Reformerlarınız boş kalmasın" |
| ozel-ders-randevu-programi | Son dakika iptali, veli mesaj trafiği, ders/ödeme hesabı, online ders | 4 | "Saatinizi derse ayırın" |
| hali-yikama-randevu-programi | Alım-teslim iki ayrı randevu, "halım nerede?" aramaları, ekip ataması, sezon | 4 | "Sahadaki operasyonu tek ekrana toplayın" |
| oto-kuafor-randevu-programi | Yıkama/seramik süre farkı, lift doluluğu, teslim hatırlatma, detailing imajı | 4 | "Liftleriniz planlı dolsun" |
| oto-ekspertiz-randevu-programi | Alıcı-satıcı aynı anda, hat kapasitesi, cumartesi yoğunluğu, galeri müşterisi | 4 | "İstasyonunuzda düzenli akışı kurun" |
| veteriner-randevu-programi | Aşı tekrarı takibi, acil vaka esnekliği, hasta sahibi kartı | 4 | "Aşı takibini sisteme emanet edin" |

### TR özellik sayfaları (/ozellikler/*)

| Sayfa | İçerik odağı | FAQ |
|---|---|---|
| yapay-zeka-randevu-asistani | Yazılı/sesli komut, gerçek veriyle çalışma, "uydurmayan AI", tek kişilik/ekipli senaryo | 4 |
| whatsapp-randevu-hatirlatma | Neden WhatsApp, 3 adımlı akış (onay→hatırlatma→boşalan saat), kurulumsuz başlangıç | 4 |
| online-randevu-sayfasi | Hizmet/personel seçimi, gerçek boş saat mantığı, link yerleşimi (Instagram/Google/QR) | 4 |
| gelir-gider-personel-takibi | Kasa + hizmet bazlı gelir + personel performansı, yetkilendirme, dönem raporları | 4 |
| mobil-randevu-uygulamasi | iOS/Android + web senkron, anlık bildirim, personelin cebinde program | 4 |

### EN sayfaları (/solutions/*, /features/*)

20 EN sayfası TR karşılıklarıyla **aynı konuyu** işler (hreflang pairKey yapısı korunmuştur) ancak **kelime kelime çeviri değildir** — doğal İngiliz İngilizcesiyle yeniden yazılmıştır. UK terminolojisi kullanıldı: *diary* (takvim), *till/takings* (kasa/ciro), *DNA* (diş kliniğinde no-show karşılığı), *practice/practise*, *rota*, *organised/utilisation* (İngiliz yazımı), *rent-a-chair* (berber), *Google Business Profile*. Her EN sayfası TR'dekiyle aynı yapıda kendi FAQ, trust, CTA ve internal link setine sahiptir.

---

## 4. FAQ ve FAQ Schema

- Toplam **173 soru-cevap** eklendi (TR 86, EN 87). Sorular gerçek kullanıcı sorularıdır ("Müşterilerim uygulama indirmeli mi?", "Seans paketini takip ediyor mu?", "Mesajı kim gönderiyor?" vb.); cevaplar yalnızca gerçek ürün özelliklerine dayanır.
- **Schema:** Mevcut JSON-LD mekanizması kullanıldı (yeniden yazılmadı). SoftwareApplication şeması korunarak `@graph` içine `FAQPage` eklendi — ana sayfadaki mevcut `@graph` pattern'inin aynısı.
- **Birebir uyum garantisi:** Görünen FAQ, runtime schema (SeoWrapper) ve statik shell schema'sı (generate-seo-html.js) **üçü de aynı `seoContent.js` kaydından** okur; içerik farkı yapısal olarak imkansızdır.

## 5. Internal linking

Her sayfada "İlgili sayfalar / Related pages" bloğu + 5 doğal etiketli link:
- Sektör sayfaları → 2-3 ilişkili sektör + 2-3 ilişkili özellik (örn. berber → kuaför, güzellik merkezi, WhatsApp hatırlatma, online randevu sayfası, gelir-gider)
- Özellik sayfaları → 2-3 diğer özellik + 2-3 o özelliğin en çok fayda sağladığı sektör
- TR sayfaları yalnızca TR sayfalarına, EN sayfaları yalnızca EN sayfalarına link verir (hreflang/canonical hijyeni)
- Ek olarak her sayfada header + CTA panelinde `/register` aksiyonu, footer'da ana sayfa linki
- Keyword-spam anchor yok; etiketler doğal cümle formatında ("Kuaförler için randevu programı" gibi)

## 6. Screenshot / asset kullanımı

**Kullanılan mevcut asset'ler (gerçek ürün görselleri):**
- `/screenshots/landing-dashboard-tr.png` → tüm TR sayfalarında (dashboard paneli, TR arayüz)
- `/screenshots/landing-dashboard-en.png` → tüm EN sayfalarında
- Görsel; dürüst alt text ("PLANN randevu yönetim paneli ekran görüntüsü") ve caption ile, hero'nun hemen altında çerçeveli figure olarak kullanıldı. `loading="lazy"` ile performans korundu.

**Yeni asset ihtiyacı (üretilmedi — fake görsel yasak):**
| Önerilen asset | Kullanılacağı sayfalar |
|---|---|
| WhatsApp onay/hatırlatma mesajı ekran görüntüsü (telefon mockup değil, gerçek mesaj) | whatsapp-randevu-hatirlatma + tüm sektör sayfaları |
| Online randevu sayfası (public booking) müşteri görünümü | online-randevu-sayfasi + sektör sayfaları |
| Yapay zeka asistanı sohbet ekranı | yapay-zeka-randevu-asistani |
| İstatistik/kasa ekranı | gelir-gider-personel-takibi |
| Seans paketi / müşteri kartı ekranı | güzellik merkezi, fizyoterapi, spor salonu, pilates |

Bu asset'ler hazır olduğunda `seoContent.js`'e sayfa bazlı `screenshot` alanı eklemek 5 dakikalık iştir.

## 7. Bilerek değiştirilmeyen içerikler

| İçerik | Neden |
|---|---|
| `seoData.js`'teki title / metaDescription / H1'ler | Teknik SEO fazında optimize edildi; H1'ler arama niyetiyle zaten eşleşiyor. Değiştirmek donmuş metadata'yı bozardı. |
| Ana sayfa (LandingPage) gövdesi | Zaten zengin: 11 soruluk FAQ (+FAQPage schema), gerçek screenshotlar, özellik ve fiyat bölümleri mevcut. Bu fazda dokunmak risk/fayda dengesinde gereksizdi. |
| Ana sayfa FAQ schema'sı | Teknik fazda kuruldu, translation.json ile birebir uyumlu çalışıyor. |
| URL slug'ları, route yapısı | Katı sınır — hiçbiri değişmedi. |

## 8. Teknik SEO doğrulaması (dokunulmadı)

Bu fazda **değiştirilmeyen** teknik bileşenler:
- ❌ canonical mantığı (SeoWrapper'daki `getSeoUrl` aynen duruyor)
- ❌ hreflang mantığı (`HREFLANG_PAIRS` + alternate üretimi aynen)
- ❌ sitemap üreticisi (`scripts/generate-sitemap.js`)
- ❌ robots.txt / sitemap.xml dosyaları
- ❌ nginx konfigürasyonları (`system_configs/nginx_plannapp.conf`, `frontend/default.conf`)
- ❌ Cloudflare ayarları
- ❌ Statik SEO shell sisteminin head üretim mekanizması (yalnızca JSON-LD'ye additive FAQPage eklendi)
- ❌ URL slug'ları, route'lar, API, booking/login/dashboard fonksiyonları

Production doğrulaması: canonical'lar, hreflang çiftleri (tr-TR + en-GB), sitemap.xml (200), robots.txt (200) smoke testte birebir önceki davranışla eşleşti.

## 9. Build ve deploy

```
docker compose build frontend   → ✅ başarılı (CRA build + generate-seo-html.js: 42 shell dosyası)
docker compose up -d frontend   → ✅ plann_frontend recreate edildi
```

## 10. Production smoke test

```
40/40 sayfa: HTTP 200 ✅
40/40 sayfa: İlk HTML'de FAQPage schema mevcut ✅
Canonical'lar doğru (TR→plannapp.co, EN→plannapp.co.uk) ✅
Hreflang çiftleri (tr-TR + en-GB) tüm sayfalarda ✅
sitemap.xml: 200 ✅ | robots.txt: 200 ✅ | ana sayfalar (.co / .co.uk): 200 ✅
JS bundle doğrulaması: TR ve EN içerik + screenshot referansları + /register CTA bundle'da mevcut ✅
```

## 11. En önemli kural — uygunluk beyanı

İçerikte yalnızca gerçek PLANN özellikleri anlatıldı: randevu takvimi, WhatsApp Business API onay/hatırlatma, online randevu sayfası, müşteri kartı (geçmiş/harcama/not), personel yetkilendirme ve takvimleri, kasa + istatistikler, seans paketleri, yapay zeka asistanı (yazılı/sesli), iOS/Android/PWA.
**Eklenmeyen şeyler:** uydurma entegrasyon, müşteri sayısı, rating/review, performans iddiası, fiyat/garanti vaadi, var olmayan screenshot. "Muhasebe programı yerine geçer mi?" FAQ'ında sınır dürüstçe belirtildi ("resmi muhasebe aracı değildir").
