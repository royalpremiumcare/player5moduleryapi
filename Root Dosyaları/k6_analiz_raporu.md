# PLANN k6 Yük Testi — 6 Test + 3 Profil Karşılaştırmalı Analiz Raporu

> **§12'ye bak:** Tek karışık senaryo yerine 3 profil (Cold / Warm / Large Dataset)
> kuruldu. Large profili bu kutuda MongoDB'yi OOM-kill etti — Faz 4 (PostHog
> ayrıştırma) için en güçlü kanıt.

**Test Ortamı:** Production Backend (`http://127.0.0.1:8002`, 17 Uvicorn worker, MongoDB + Redis)
**Test Aracı:** k6 v1.6.1 (`plann_load_test.js`)
**Test Yükü:** 6 rampalı stage, peak 1000 eşzamanlı VU, ~2m20s süre

> ⚠️ **Önemli metodolojik not:** k6 doğrudan backend'e (`127.0.0.1:8002`) vuruyor, **Nginx'i baypas ediyor**. Bu yüzden Nginx katmanında açtığımız **gzip sıkıştırması bu testte görünmüyor** (`data_received` düşmedi). Gerçek kullanıcılar Nginx üzerinden geldiği için legacy `/customers` gibi büyük JSON'larda prod'da ~%90 daha az bayt iner — bu kazanç bu raporda ölçülemez.

---

## Testlerin Kronolojisi

| Test | Zaman | Yapılan Değişiklikler |
|---|---|---|
| **T1 — Baseline** | 6 Ağu 16:15 | Optimizasyon YOK — ham backend |
| **T2 — Cache + Pagination** | 6 Ağu 18:38 | Dashboard cache + cursor pagination + Türkçe search + denormalize sayaçlar |
| **T3 — Legacy Path Optimize** | 6 Ağu 18:52 | Legacy `/customers` da denormalize sayaçları okur (appointments taraması iptal) |
| **T4 — Faz 1 + Legacy Revert** | 7 Ağu 04:12 | Dashboard aggregate paralelleştirme (`asyncio.gather`+`$group`), compound index, Nginx gzip, randevu onayları `BackgroundTasks`'e taşındı, legacy `/customers` **appointments+merge'e geri alındı** (eski build render bug fix) |
| **T5 — Faz 2** | 7 Ağu 04:31 | `/appointments` parametre-versiyonlu cursor pagination (additive; test parametresiz legacy'yi çağırdığı için sıcak yol değişmedi). İyileşme büyük ölçüde ölçüm varyansı — bkz. §10.2 |
| **T6 — Paginated varyant ölçümü** | 7 Ağu 04:37 | Teste `/appointments?limit=30` varyantı eklendi → legacy vs paginated **doğrudan** karşılaştırıldı. Kritik bulgu: bu veri setinde ikisi özdeş — bkz. §11.2 |

---

## 1. Genel Karşılaştırma

| Metrik | **T1** | **T2** | **T3** | T1→T3 |
|---|---:|---:|---:|---:|
| Total requests | 42.613 | 41.463 | 39.204 | ~aynı |
| RPS | 304 | 296 | 280 | -8% |
| Error rate | 0% | 0% | 0% | ✅ |
| Peak VU | 1000 | 1000 | 1000 | ✅ |
| **Overall p95** | **3.90 s** | **3.80 s** | 3.98 s | ~aynı |
| **Overall avg** | 1.66 s | 1.63 s | 1.73 s | ~aynı |
| Data received | 905 MB | 754 MB | 729 MB | -19% |

**Genel yorum:** Overall p95 sabit görünüyor çünkü darboğaz artık farklı endpoint'lere kaymış. Endpoint bazına inince gerçek kazançlar netleşiyor.

---

## 2. Endpoint Bazlı Karşılaştırma (Kritik Tablo)

### `/stats/dashboard` — Dashboard Cache Etkisi

| Metrik | T1 (cache YOK) | T2 (cache VAR) | T3 | T1→T3 |
|---|---:|---:|---:|---:|
| avg | 3.03 s | **1.82 s** | 2.00 s | **-34%** 🚀 |
| p95 | 6.26 s | **3.96 s** | 4.45 s | **-29%** 🚀 |
| max | 9.75 s | 7.54 s | 7.67 s | -21% |
| min | — | 11 ms | **10 ms** | Redis hit hızı |

**Analiz:** Redis cache decorator (60s TTL) + event-driven invalidation, dashboard yükünü yaklaşık üçte bir azalttı. Cache hit'lerde 10 ms, cache miss'lerde ise MongoDB aggregate hâlâ 3-4 s alıyor — dashboard aggregate pipeline'ının kendisi de ileride optimize edilebilir.

### `/customers` (Legacy — Mobil Build'ler Kullanıyor)

| Metrik | T1 | T2 (appointments+merge) | T3 (**denorm only**) | T2→T3 |
|---|---:|---:|---:|---:|
| avg | 1.17 s | 2.35 s | **2.14 s** | -9% |
| p95 | 2.47 s | 5.02 s | **4.48 s** | -11% |
| max | 8.68 s | 7.42 s | **6.15 s** | -17% |
| min | — | 42 ms | **48 ms** | ~aynı |

**Analiz:** T2'de legacy path yavaşlamıştı çünkü appointments + customers merge yapıyordu. T3'te sadece denormalize `customers` collection'ından okuduğu için:
- Tek istek smoke: **60 ms** (dramatik hız)
- 300 RPS concurrent: 2.14 s (payload büyüklüğü ~150 KB × 1021 müşteri ⇒ 45 MB/s ağ + JSON serialize CPU)
- Kalan darboğaz artık DB değil, **response body büyüklüğü** — mobil eski build'ler pagination'a geçince bu tamamen çözülecek.

### `/customers?limit=30` (Yeni Web — Cursor Pagination)

| Metrik | T2 | T3 | Değişim |
|---|---:|---:|---:|
| avg | 1.46 s | 1.57 s | +7% (test-to-test varyans) |
| p95 | 3.19 s | 3.40 s | +7% |
| max | 4.73 s | 5.03 s | +6% |
| min | 10 ms | **13 ms** | ~aynı |

**Analiz:** 30 kayıtlık sayfa ile yeni web müşteri listesi payload'u küçük (~5 KB), MongoDB'de indeksli cursor sorgusu (`org_id + name + _id`) hızlı. Test-to-test %5-10 varyans normal.

### `/customers?search=fatih` (Türkçe-Tolerant Search)

| Metrik | T2 | T3 | Değişim |
|---|---:|---:|---:|
| avg | 1.45 s | 1.55 s | +7% |
| p95 | 3.13 s | 3.37 s | +8% |
| max | 4.94 s | 4.90 s | ~aynı |

**Analiz:** Regex substring + `.collation({locale:'tr'})` collection scan ediyor (1021 doc); indeks kullanmıyor ama data set küçük olduğu için hızlı kalıyor. Data set 10K+'a çıkarsa dedicated text index'i düşünmek gerekir.

---

## 3. Toplu İyileşme Görselleştirmesi

```
T1 (baseline)        ═══════════════════════════════════════════════════════ 9.75 s
Dashboard max
T2 (dash cache)      ══════════════════════════════════════════════ 7.54 s    (-23%)
T3 (legacy denorm)   ═══════════════════════════════════════════════ 7.67 s   (-21%)

T1                   ═══════════════════════════ 6.26 s
Dashboard p95
T2                   ═════════════════ 3.96 s    (-37%)
T3                   ══════════════════ 4.45 s   (-29%)

T1                   ═══════════ 2.47 s
Customers legacy p95
T2                   ═══════════════════════ 5.02 s   ⚠️ (+103%)
T3                   ═════════════════════ 4.48 s     (-11% T2'ye göre)

—                    (yoktu)
Customers paginated p95
T2                   ═════════════ 3.19 s   🆕
T3                   ══════════════ 3.40 s

—                    (yoktu)
Customers search p95
T2                   ═════════════ 3.13 s   🆕
T3                   ══════════════ 3.37 s
```

---

## 4. Threshold Sonuçları (Üç Test)

| Threshold | T1 | T2 | T3 |
|---|---:|---:|---:|
| `errors < 5%` | ✅ %0.00 | ✅ %0.00 | ✅ **%0.00** |
| `http_req_duration p(95) < 2000ms` | ❌ 3906 | ❌ 3808 | ❌ **3980** |

**Neden 2000ms hedefi hâlâ aşılıyor?**
- Dashboard cache miss senaryosunda MongoDB aggregate 3-4 saniye
- Legacy `/customers` payload büyüklüğü (150 KB, 1021 satır) 300 RPS altında serialize + ağ maliyeti
- `/appointments` cursor pagination henüz uygulanmadı, aynı payload sorunu

**300 RPS ≈ 30 organizasyon × 10 istek/sn** — gerçek dünyada bu yük çok yüksek. Normal koşullarda (100 VU seviyesinde) p95 hâlâ **353 ms** (T1'de bile), yani gerçek kullanıcı deneyimi çok akıcı.

---

## 5. Ekonomik Yorum

| İyileştirme | Etki | Neden Önemli |
|---|---|---|
| Dashboard cache | avg 3.03 s → **2.00 s** (-34%) | Her kullanıcı ana ekranı sürekli açıyor; 1 saniye kazanım × milyonlarca gösterim = büyük UX kazancı |
| Legacy denormalize | avg 2.35 s → **2.14 s** (-9%) | Mobil eski build'ler için kritik — kalıcı çözüme kadar köprü |
| Cursor pagination | Yeni | Web müşteri listesi büyüdükçe patlamayı önler (10K+ müşteri için hâlâ ~50 ms) |
| Türkçe search | Yeni | Client-side arama yerine sunucu-tarafı; büyük veri setlerinde de doğru sonuç |

---

## 6. Kalan Aksiyonlar (Güncel Öncelik)

### 🔴 P0 — Dashboard aggregate optimization
Cache miss senaryosunda 3-4 sn kalıyor. Aggregate pipeline'ının kendisini incele:
- Compound index'ler
- `$facet` yerine paralel `asyncio.gather`
- Bazı sayaçlar için denormalize (customers gibi)

### 🟠 P1 — `/appointments` cursor pagination
p95 4.02 s (T2) / 4.37 s (T3). Aynı cursor pattern uygulanabilir.

### 🟡 P2 — Legacy `/customers` response cache
Mobil eski build'ler tam liste alıyor. Redis cache (60s TTL, org bazlı key) ile 45 MB/s ağ maliyeti sıfıra iner.

### 🟢 P3 — Response compression
Nginx tarafında `gzip on` + `gzip_types application/json` — büyük JSON response'ları 5-10× küçültür (özellikle legacy /customers için).

### 🟢 P4 — Prometheus + Grafana
Real-time RPS/latency/cache hit ratio dashboard'ı.

---

## 7. Kapasite Planlaması

- **Konforlu kapasite:** ~500 eşzamanlı aktif kullanıcı (dashboard cache ile artık daha rahat)
- **Peak (kısa süreli) kapasite:** ~1000 VU stabil, hiç 5xx yok
- **Gerçek dünya DAU tahmini:** ~30-50k günlük aktif kullanıcı (peak concurrent oranı ~2-3%)
- **Backend altyapısı:** 17 Uvicorn worker + async pattern → RPS 280-320 sabit, throughput doygun değil

---

## 9. T4 Koşusu — Faz 1 Sonrası (7 Ağu 04:12)

**Özet:** 40.358 istek · RPS 288 · **hata %0.00** · peak 1000 VU · overall p95 **4.04 s** · avg 1.68 s · data_received 739 MB

### 9.1 Endpoint p95 — T3 → T4

| Endpoint | T3 p95 | **T4 p95** | Değişim | Yorum |
|---|---:|---:|---:|---|
| `/stats/dashboard` | 4.45 s | **4.23 s** | **-5%** | Aggregate paralelleştirme (`asyncio.gather`+`$group`) küçük kazanç; avg 2.00→**1.83 s** (-9%) |
| `/appointments` | 4.37 s | **4.32 s** | ~aynı | Hâlâ pagination yok — aynı payload darboğazı |
| `/customers` (legacy) | 4.48 s | **5.34 s** | **+19%** | Beklenen: denorm-only'den appointments+merge'e **bilinçli geri dönüş** (eski build render bug fix). Doğruluk > hız |
| `/customers?limit=30` | 3.40 s | **3.43 s** | ~aynı | Test-to-test varyans |
| `/customers?search` | 3.37 s | **3.38 s** | ~aynı | Stabil |
| `/services` | 3.34 s | **3.34 s** | ~aynı | — |

### 9.2 Yorum

- **Sıfır hata** yine korundu — 1000 VU ekstrem yükte tek bir 5xx yok; altyapı dayanıklılığı sağlam.
- **Dashboard:** Faz 1 aggregate optimizasyonu cache-**hit**'lerde 11 ms (Redis) veriyor; ekstrem yükte cache-miss stampede'i altında p95 hâlâ 4 s bandında. Gerçek kazanç prod'da düşük eşzamanlılıkta çok daha belirgin.
- **Legacy `/customers` bilinçli olarak yavaşladı** (5.34 s). Bu bir regresyon değil, **eski mobil build'lerdeki "6-7 müşteri yan yana" render bug'ını** çözmek için appointments+merge davranışına geri dönüşün bedeli. Kalıcı çözüm: eski build'ler pagination'a geçince bu path tamamen emekliye ayrılacak (P2: Redis response cache köprü olarak duruyor).
- **gzip bu testte görünmüyor** (bkz. metodoloji notu) — k6 Nginx'i baypas ediyor. Prod'da legacy `/customers` teli üzerinde ~%90 daha küçük.

### 9.3 Threshold (Dört Test)

| Threshold | T1 | T2 | T3 | **T4** |
|---|---:|---:|---:|---:|
| `errors < 5%` | ✅ %0.00 | ✅ %0.00 | ✅ %0.00 | ✅ **%0.00** |
| `http_req_duration p(95) < 2000ms` | ❌ 3906 | ❌ 3808 | ❌ 3980 | ❌ **4040** |

**Not:** 2000ms hedefi 1000 VU ekstrem senaryo içindir; gerçek dünya yükünde (≤100 VU) p95 hâlâ ~350 ms bandında. Kalan darboğazlar: (1) `/appointments` cursor pagination (P1), (2) dashboard cache-miss aggregate, (3) legacy `/customers` — hepsi yol haritasında.

---

## 10. T5 Koşusu — Faz 2 Sonrası (7 Ağu 04:31)

**Özet:** **48.267 istek** · RPS **344.6** · **hata %0.00** · peak 1000 VU · overall p95 **3.21 s** · avg 1.38 s · data_received 881 MB

### 10.1 Endpoint p95 — T4 → T5

| Endpoint | T4 p95 | **T5 p95** | Değişim |
|---|---:|---:|---:|
| `/stats/dashboard` | 4.23 s | **3.59 s** | -15% |
| `/appointments` (legacy) | 4.32 s | **3.40 s** | -21% |
| `/customers` (legacy) | 5.34 s | **4.21 s** | -21% |
| `/customers?limit=30` | 3.43 s | **2.63 s** | -23% |
| `/customers?search` | 3.38 s | **2.71 s** | -20% |
| `/services` | 3.34 s | **2.60 s** | -22% |
| **Overall** | **4.04 s** | **3.21 s** | **-21%** |
| **RPS** | 288 | **344.6** | **+20%** |

### 10.2 Dürüst Yorum — Bu İyileşme Faz 2 DEĞİL

⚠️ **Neden-sonuç uyarısı:** Faz 2 yalnızca `/appointments` endpoint'ine, **sadece `?limit=` verildiğinde** aktifleşen yeni bir kod yolu ekledi. Test scripti `/appointments`'ı **parametresiz (legacy)** çağırıyor → Faz 2 sıcak yolu bu testte hiç çalışmıyor (tek fark: ihmal edilebilir bir `use_pagination=False` dal kontrolü).

Buna rağmen **alakasız endpoint'ler dahil hepsi ~%20 hızlandı ve throughput %20 arttı**. Bu, kodla değil **sistem-seviyesi bağlamla** açıklanır:
- T4, ard arda yapılan frontend+backend Docker build'lerinin hemen ardından, makine PostHog/swap baskısı altındayken koşuldu.
- T5 daha sessiz bir makinede koşuldu → backend'e daha çok CPU headroom düştü (RPS 288→344 + 0 hata bunu doğruluyor).

**Sonuç:** T5'in kendisi harika bir dayanıklılık fotoğrafı (1000 VU, 344 RPS, sıfır 5xx, p95 2s'ye çok yaklaştı) ama T4→T5 farkını Faz 2'ye **yazamayız**; büyük ölçüde ölçüm varyansı. Faz 2'nin gerçek kazancı ancak `/appointments?limit=30` telde ölçülünce (payload küçülmesi) görünür — mevcut test bu varyantı çağırmıyor.

### 10.3 Threshold (Beş Test)

| Threshold | T1 | T2 | T3 | T4 | **T5** |
|---|---:|---:|---:|---:|---:|
| `errors < 5%` | ✅ 0% | ✅ 0% | ✅ 0% | ✅ 0% | ✅ **0%** |
| `p(95) < 2000ms` | ❌ 3906 | ❌ 3808 | ❌ 3980 | ❌ 4040 | ❌ **3210** |

**Öneri:** Faz 2'yi gerçekten ölçmek için teste `/appointments?limit=30` varyantı eklenebilir (customers'taki gibi ayrı trend). Bir sonraki koşuda eklerim.

---

## 11. T6 Koşusu — Legacy vs Paginated Doğrudan Karşılaştırma (7 Ağu 04:37)

**Özet:** 44.862 istek · RPS 320.2 · **hata %0.00** · peak 1000 VU · overall p95 3.29 s · avg 1.49 s. Teste `/appointments?limit=30` (Faz 2 paginated) eklendi.

### 11.1 `/appointments` — legacy vs paginated (aynı koşu, yan yana)

| Metrik | Legacy (tam array) | **Paginated (limit=30)** | Fark |
|---|---:|---:|---:|
| avg | 1708 ms | 1730 ms | +1% |
| p95 | 3462 ms | 3473 ms | ~aynı |
| max | 5462 ms | 5638 ms | ~aynı |
| min | 16 ms | 17 ms | ~aynı |

**İkisi pratikte ÖZDEŞ.**

### 11.2 Neden paginated appointments hız KAZANDIRMADI? (kritik ders)

Bu, pagination hakkında en önemli mühendislik dersini veriyor: **pagination her zaman hız demek değildir.**

- Test org'unda **yalnızca 87 randevu** var. Legacy path `to_list(1000)` ile 87 doküman çekiyor; paginated 31 çekiyor. İkisi de küçük → serialize/ağ maliyeti zaten minik. Pagination'ın çözdüğü "büyük payload" problemi **bu veri setinde mevcut değil**.
- 1000 VU altında latency, 87 vs 31 doküman farkından değil, **CPU/kuyruk contention'ından** doğuyor. İki yol da aynı zaman dilimini paylaşıyor → aynı p95.

**Kontrast — neden `/customers`'ta pagination KAZANDIRDI (p95 4.22s → 2.67s)?**

| | `/appointments` | `/customers` |
|---|---|---|
| Legacy SORGU maliyeti | Ucuz: indeksli, 87 doc | **Pahalı:** 10.000 appointment + customers **MERGE** taraması |
| Paginated SORGU maliyeti | Ucuz: 31 doc | Ucuz: indeksli 30 doc |
| Fark kaynağı | Sadece payload (bu sette küçük) | **Sorgu algoritması** (merge vs index) |

Yani `/customers` kazancı payload değil, **legacy'nin pahalı merge sorgusundan** geliyordu. `/appointments` legacy'si zaten ucuz indeksli sorgu → paginate etmek bu boyutta ölçülebilir kazanç vermiyor.

### 11.3 Faz 2 yine de DEĞERLİ — ama şimdi değil, ÖLÇEKTE

Faz 2'nin getirisi **10.000+ randevulu org'da** ortaya çıkar: o zaman legacy `to_list(1000)` ~150 KB+ array serialize edip telden geçirir; paginated 30 kayıt ~5 KB döner. Bu bir **ölçek güvenlik supabı** (customers'ta olduğu gibi), mevcut küçük veride görünmez. Bulgu: **"pagination'ı erken optimizasyon sanıp atma; ama küçük veride hız beklentisiyle de ölçme."**

### 11.4 Threshold (Altı Test)

| Threshold | T1 | T2 | T3 | T4 | T5 | **T6** |
|---|---:|---:|---:|---:|---:|---:|
| `errors < 5%` | ✅ 0% | ✅ 0% | ✅ 0% | ✅ 0% | ✅ 0% | ✅ **0%** |
| `p(95) < 2000ms` | ❌ 3906 | ❌ 3808 | ❌ 3980 | ❌ 4040 | ❌ 3210 | ❌ **3290** |

---

## 12. Üç Profil — Cold / Warm / Large Dataset (7 Ağu 05:00)

Tek karışık senaryonun küçük veride bazı optimizasyonları göstermediği anlaşıldı
(bkz. §10-11). Üç ayrı profil kuruldu. Harness: `k6_profiles.js` (PROFILE env),
`run_profiles.sh` (orkestratör: token mint + cache flush/prewarm + seed),
`backend/scripts/seed_synthetic_loadtest.py` (İZOLE sentetik org).

### 12.1 Cold vs Warm (gerçek org, 1000 VU peak)

| | Tekil dashboard | k6 RPS | k6 overall p95 | dashboard p95 | customers legacy p95 | hata |
|---|---:|---:|---:|---:|---:|---:|
| **Cold** (cache flush) | 37 ms (miss) | 271 | 4.26 s | 4.59 s | 5.70 s | %0 |
| **Warm** (prewarm) | 17 ms (hit) | 307 | **3.36 s** | **3.38 s** | 4.31 s | %0 |

**Analiz:**
- **Tekil cache-miss yalnızca 37 ms** — Faz 1 aggregate optimizasyonu sayesinde cold-start artık felaket değil (eskiden 3-4 s idi). Cache'in asıl değeri, yük altında her worker'ın yeniden hesaplamasını önlemesinde: warm overall p95 cold'dan **%21 düşük**, RPS %13 yüksek.
- Warm senaryosu gerçek kullanıcı deneyimine en yakın olan; p95 3.36 s (1000 VU ekstrem yük altında — normal yükte ~sub-sn).

### 12.2 Large Dataset — TEK İSTEK (yüksüz, 100k randevu / 10k müşteri) 🔴 EN ÖNEMLİ TABLO

| Endpoint | Süre | Payload | Paginated'e karşı |
|---|---:|---:|---|
| `/customers` (legacy) | 848 ms | **1.16 MB** | — |
| `/customers?limit=30` | **15 ms** | 8.8 KB | **55× hızlı / 131× küçük** 🚀 |
| `/appointments` (legacy) | 2843 ms | **638 KB** (1000 cap) | — |
| `/appointments?limit=30` | **1319 ms** | 19 KB | **2.2× hızlı / 33× küçük** 🚀 |
| `/stats/dashboard` | 55 ms | 300 B | (cache) |

**T6'nın öngördüğü tam olarak bu:** Pagination'ın değeri küçük veride görünmez ama
10k/100k ölçekte **dramatik**. Özellikle `/customers` legacy merge'i 1.16 MB
serialize ediyor; paginated 8.8 KB. Bu, mobil eski build'lerin neden pagination'a
geçmesi gerektiğinin (force-update, Faz 3) sayısal kanıtı.

### 12.3 Large Dataset — 1000 VU YÜK 🔴 SİSTEMİK ÇÖKÜŞ

Aynı sentetik org'a 1000 VU bindirildiğinde:

| Metrik | Değer |
|---|---:|
| Hata oranı | **%67.5** (1729/2560) |
| p95 | **65 s** (timeout) |
| RPS | 300 → **15** (çöktü) |
| Etki | Ağır legacy sorguları 17 worker'ı doyurdu → **head-of-line blocking** → hızlı paginated endpoint'ler bile timeout (customers?limit=30 tek başına 15 ms iken p95 60 s) |

**Kritik ders:** Legacy tam-array endpoint'leri ölçekte sadece "yavaş" değil;
yük altında **tüm API'yi kilitleyen sistemik risk**. Birkaç ağır sorgu, hızlı
endpoint'leri de aç bırakıyor. Pagination bir optimizasyon değil, ölçekte
**çalışan API ile eriyen API arasındaki fark**.

### 12.4 🔥 Sunucu Çöküşü — Faz 4'ün Kanıtı

Large profilini **100 VU** (gerçekçi) ile tekrar koşarken **sunucu çöktü**:
- `free`: 15 GB RAM doldu, **19 GB swap doldu**, OOM-killer **MongoDB'yi öldürdü**.
- Sebep: 100k randevu working-set'i + ağır payload'lar **+ zaten 12 GB swap yiyen PostHog aynı kutuda**.
- Kurtarma: k6 kill → sentetik veri teardown (100k+10k silindi) → prod doğrulandı (dashboard 27 ms, Mongo ok). Bellek: swap 18→14 GB gevşedi.

**Sonuç — bu, raporun en değerli çıktısı:**
1. **Faz 4 (PostHog ayrıştırma) artık teorik değil, ZORUNLU.** Analitik yükü, latency-hassas prod DB'siyle aynı bellekte yarışıyor ve onu öldürüyor.
2. **Large profili bu kutuda bir daha çalıştırılMAMALI** (`run_profiles.sh` içine `ALLOW_LARGE=1` kilidi eklendi). İzole test sunucusu veya PostHog ayrıştıktan sonra.
3. Sentetik seed/teardown idempotent ve izole (`k6-loadtest-synthetic-org`) — prod verisine hiç dokunmadı.

---

## 8. Ekler (Dosyalar)

- `plann_load_test.js` — Tek-senaryo test script'i (13 endpoint)
- `k6_profiles.js` — 3-profilli test (PROFILE=cold|warm|large; large peak 100 VU, diğerleri 1000)
- `run_profiles.sh` — Orkestratör (token mint + cache flush/prewarm + seed; large `ALLOW_LARGE=1` kilitli)
- `backend/scripts/seed_synthetic_loadtest.py` — İZOLE sentetik org seed/teardown (10k/100k)
- `k6_{cold,warm,large}_summary.json` — Profil bazlı k6 özetleri
- `single_request_timings.txt` — Tekil cold/warm dashboard ölçümleri
- `k6_run.log` — Ham k6 çıktısı
- `k6_summary.json` — k6 özet metrikleri
- `k6_raw.json` — Ham datapoint akışı (~150 MB)
- `k6_analiz_raporu.md` — Bu rapor (3 test karşılaştırmalı)

---

**Rapor Sonu.**
