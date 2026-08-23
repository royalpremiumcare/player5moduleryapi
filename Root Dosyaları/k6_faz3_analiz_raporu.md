# PLANN k6 — Faz 3 Ölçek Testi Analizi (100k randevu / 10k müşteri)

**Tarih:** 23 Ağustos 2026, 20:39 UTC (23:39 TR)
**Profil:** `large` — izole sentetik organizasyon (`k6-loadtest-synthetic-org`)
**Veri:** 10.000 müşteri / 100.000 randevu
**Yük:** 4 kademede 100 VU'ya kadar, toplam 1 dk 50 sn
**Harness:** `k6_profiles.js` (PROFILE=large), `run_profiles.sh large`
**Bağlam:** Faz 3'te eklenen `appointments_org_date_time_id` index'i canlıdayken koşuldu.

> **Metodoloji notu (önceki rapordan devam):** k6 doğrudan backend'e (`127.0.0.1:8002`) vuruyor,
> **Nginx'i baypas ediyor.** Bu yüzden Nginx'teki gzip bu ölçümde görünmüyor. Aşağıdaki
> "906 MB indi" rakamı gerçek kullanıcılarda ~%90 daha düşüktür. Süreler etkilenmez, baytlar etkilenir.

---

## 1. Tek cümlelik sonuç

**Sayfalanmış uçlar 100.000 randevuda bile sorunsuz (p95 < 420 ms, sıfır hata); tüm gecikme
sayfalama parametresi göndermeyen iki "legacy düz liste" ucunda toplanıyor** — ve web arayüzü
bu uçları hâlâ üç yerde çağırıyor.

---

## 2. Genel sonuçlar

| Metrik | Değer |
|---|---|
| Toplam istek | 3.568 |
| Hata | **0** (%0,00) |
| Throughput | 32,4 istek/sn |
| Ortanca (median) süre | **164,5 ms** |
| p90 | 5,75 sn |
| p95 | 8,67 sn |
| Maksimum | 14,24 sn |
| İnen veri | 906 MB (8,2 MB/sn) |
| Zirve eşzamanlı kullanıcı | 99 VU |

**Eşikler:**

| Eşik | Sonuç |
|---|---|
| `errors rate < 0.05` | ✅ geçti (%0,00) |
| `http_req_duration p(95) < 2000ms` | ❌ kaldı (8,67 sn) |

Ortanca 164 ms ama p95 8,67 sn. Bu uçurum tek başına şunu söylüyor: **sorun genel bir
yavaşlık değil, belirli uçların uç noktada patlaması.**

---

## 3. Uç bazında dağılım — asıl tablo

Yük 7 uca eşit dağıtıldı (her biri ~510 istek).

| Uç | Ortanca | p90 | p95 | Maks |
|---|---|---|---|---|
| `/services` | 50 ms | 212 ms | **314 ms** | 1,05 sn |
| `/stats/dashboard` | 60 ms | 245 ms | **374 ms** | 1,16 sn |
| `/customers?limit=30` | 62 ms | 264 ms | **387 ms** | 1,38 sn |
| `/appointments?limit=30` | 88 ms | 299 ms | **418 ms** | 1,52 sn |
| `/customers?limit=30&search=` | 398 ms | 775 ms | **897 ms** | 1,47 sn |
| `/appointments` (legacy düz) | 3,43 sn | 6,02 sn | **6,42 sn** | 7,50 sn |
| `/customers` (legacy düz) | 7,17 sn | 12,19 sn | **12,78 sn** | 14,24 sn |

Beş uç 900 ms'nin altında. İki uç 6–13 saniye. Aradaki fark 15–30 kat.

**Aynı veri, aynı uç, tek fark `limit` parametresi:**

| | p95 | Fark |
|---|---|---|
| `/appointments?limit=30` | 418 ms | — |
| `/appointments` | 6.417 ms | **15,3×** |
| `/customers?limit=30` | 387 ms | — |
| `/customers` | 12.784 ms | **33,1×** |

### p95 eşiğinin neden kaldığı (matematik tutuyor)

İki legacy uç trafiğin %28,6'sı. En yavaş %5'lik dilim tamamen legacy `/customers`
popülasyonunun içine düşüyor — o ucun kendi ortancası 7,17 sn, p90'ı 12,19 sn; genel p95'in
8,67 sn çıkması bu dağılımın ~%65'inci yüzdeliğine denk geliyor. Yani **genel p95 eşiği
tek bir ucun ağırlığıyla kalmış durumda.** Legacy uçlar dışlandığında en kötü p95 897 ms
— eşiğin yarısından az.

---

## 4. Faz 3 index'i ne kanıtladı, ne kanıtlamadı

**Kanıtladığı:** `/appointments?limit=30` 100.000 randevuluk bir organizasyonda, 100 eşzamanlı
kullanıcı altında p95 418 ms ile yanıt veriyor ve hiç hata vermiyor. Faz 3'teki `explain()`
ölçümü bu yolun artık okuduğu doküman sayısının döndürdüğüne eşit olduğunu göstermişti
(51 istek → 51 doküman); bu test o davranışın ölçekte de bozulmadığını doğruluyor.

**Kanıtlamadığı — dürüst olmak gerekirse:** Bu, index öncesi/sonrası kontrollü bir karşılaştırma
**değil.** 7 Ağustos'taki `large` koşusu geçerli bir "önce" ölçümü sayılamaz, çünkü o koşuda
**31.078 isteğin tamamı hata döndü** (`http_req_failed: %100`). O koşu MongoDB'yi OOM ile
öldürmüştü (bkz. `k6_analiz_raporu.md` §12); oradaki "42 ms ortanca" rakamı hızlı yanıt değil,
hızlı **hata** yanıtıdır. İki koşuyu yan yana koyup "şu kadar hızlandı" demek yanlış olur.

Index'in ölçekteki katkısına dair güçlü ama dolaylı gerekçe şudur: index olmadan planlayıcı,
sıralamayı karşılayamadığı için organizasyonun **tüm** randevularını belleğe alıp orada
sıralıyordu. 100.000 dokümanda bu, MongoDB'nin bloklayan sıralama için ayırdığı bellek
sınırına dayanma riski taşır — yani muhtemelen sadece yavaşlamaz, hata verirdi.

**Kesin kanıt isterseniz** ucuz bir deney var: sentetik veriyi tekrar seed edip aynı sorguyu
bir kez normal, bir kez `hint("organization_id_1_appointment_date_-1")` ile `explain()`
etmek yeterli. k6 gerektirmez, birkaç dakika sürer. Onay verirseniz yaparım.

---

## 5. Asıl bulgu: yavaş uçları hâlâ web arayüzü çağırıyor

`server.py` içindeki legacy `/customers` bloğunun yorum satırı şöyle diyor:

> *"performans (yeni web zaten limit=30 paginated path'i kullanıyor) ikincil"*

**Bu varsayım artık doğru değil.** Frontend'i taradım — sayfalanmış yolu yalnızca müşteri
listesi ekranı kullanıyor. Üç yer hâlâ tüm listeyi çekiyor:

| Dosya | Satır | Çağrı | Ölçekteki p95 |
|---|---|---|---|
| `frontend/src/App.js` | 630 | `api.get("/appointments")` | **6,42 sn** |
| `frontend/src/components/AppointmentFormWizard.js` | 411 | `api.get("/customers")` | **12,78 sn** |
| `frontend/src/components/AppointmentForm.js` | 134 | `api.get("/customers")` | **12,78 sn** |
| `frontend/src/components/PaymentRequestDrawer.js` | 87 | `api.get("/customers")` | **12,78 sn** |
| `frontend/src/components/Customers.js` | 208 | `params` ile sayfalı | 387 ms ✅ |
| `frontend/src/components/Calendar.js` | 222 | tarih aralığı, `limit` yok | legacy yol (aralıkla sınırlı) |

En kritiği `App.js:630`: uygulama açılışındaki ana randevu yüklemesi, k6'nın ölçtüğü
**parametresiz** `/appointments` çağrısının birebir aynısı. Bugün 639 randevuda sorun yok;
tek bir işletme 100 bin randevuya çıktığında açılış ekranı 6 saniyeye dayanır.

`AppointmentFormWizard.js:411` ise Faz 1'de dokunduğumuz sihirbaz — randevu oluşturmak için
tüm müşteri listesini indiriyor.

### Neden legacy uçlar bu kadar pahalı

Legacy `/customers`, sayfalama olmadığında iki tam sorgu çekip Python tarafında birleştiriyor
(`server.py:11900-11944`): 10.000 randevu + 50.000'e kadar müşteri okunuyor, bellekte bir
sözlükte harmanlanıyor, sonra Python'da sıralanıyor. Bu iş index'le çözülemez — mimari.

### Neden "legacy ucu kaldıralım" bir çözüm değil

`.cursor/rules/api-contract.mdc` gereği bu uçlar **donmuş sözleşme**. Mağazadaki mobil
build'ler `/customers` ve `/appointments` uçlarını `limit` göndermeden çağırıyor ve tam
diziyi bekliyor. Ucu değiştirmek sahadaki uygulamaları bozar.

**Doğru müdahale:** ucu değil, **çağıranı** düzeltmek. Web frontend güncellenebilir olduğu için
yukarıdaki dört çağrıyı sayfalı yola taşımak, sözleşmeyi hiç ellemeden yükün büyük kısmını
ortadan kaldırır.

---

## 6. Bant genişliği

906 MB / 110 sn, sadece 32 istek/sn'de. Kaba dağılım: inen baytın **~%85'i tek başına legacy
`/customers`** ucundan geliyor (10.000 müşterilik dizi, istek başına ~1,5 MB).

Prod'da Nginx gzip bunu ~%90 kısıyor (bu testte görünmüyor — §metodoloji). Yine de asıl mesele
bayt değil: 1,5 MB'lık JSON'u üretmek için harcanan serileştirme ve bellek, 17 worker'ı
doyuran şey.

---

## 7. Altyapı davranışı

| Kontrol | Sonuç |
|---|---|
| MongoDB | **Ayakta** — 4 gün uptime, 0 restart |
| Backend | Ayakta, healthy, 0 restart |
| Kesintiye uğrayan iterasyon | 0 |
| Sentetik veri temizliği | ✅ yapılmış (sorgulandı: sentetik org'da 0 randevu / 0 müşteri) |
| Prod veri bütünlüğü | ✅ 639 randevu — dokunulmamış |

Bu, 7 Ağustos'a göre en belirgin iyileşme: o koşuda MongoDB OOM ile ölmüş ve veritabanı
kurtarma gerektirmişti. Bu sefer kutu yükü sorunsuz kaldırdı.

**Tek uyarı:** test sonrası swap tamamen dolu (2,0 GB / 2,0 GB, 21 MB boş), RAM 15 GB'ın
11 GB'ı kullanımda. Kutu testi atlattı ama rahat değil. `run_profiles.sh` içindeki
`ALLOW_LARGE=1` güvenlik kilidi yerinde kalmalı.

---

## 8. Öneriler ve uygulanma durumu

| # | Öneri | Durum |
|---|---|---|
| 1 | `App.js` açılış çağrısını pencerele | ✅ uygulandı (23 Ağustos) |
| 2 | Müşteri seçicilerini sunucu taraflı aramaya taşı | ✅ uygulandı (23 Ağustos) |
| 3 | `Calendar.js`'e `limit` ekle | ⏭️ atlandı — tarih aralığı zaten sınırlıyor |
| 4 | Legacy uçlara client telemetrisi | ⏳ açık |
| 5 | Uç bazlı k6 eşikleri (`p(95)<2000` tek eşik olarak anlamsız) | ⏳ açık |

Uygulama detayı §10'da.

---

## 9. Beklenmedik bulgu: bu sadece performans sorunu değildi

Raporu yazarken `App.js`'in parametresiz `/appointments` çağrısını incelerken **latent bir
doğruluk hatası** çıktı.

Backend, `limit` gönderilmediğinde şunu yapıyor (`server.py`):

```python
.sort([("appointment_date", 1), ("appointment_time", 1)]).to_list(1000)
```

Tarihe **artan** sıralayıp ilk 1000 kaydı alıyor — yani **en eski 1000 randevu**. Dashboard ise
yalnızca bugün ve sonrasını okuyor (`Dashboard.js:494` açıkça `date < today` olanı eliyor).

Sonuç: **toplam randevu sayısı 1000'i geçen bir işletmede panele en eski 1000 randevu gelir,
"Bugün" listesi boş görünür.** Yavaşlık değil, veri kaybı.

Bugün canlıda bu hata görünmüyor çünkü en büyük organizasyonun 399 randevusu var — eşiğin
altında. Ama bu, zamanla kendiliğinden tetiklenecek bir hata; yük testi olmasa fark edilmeyecekti.

---

## 10. Uygulanan düzeltmeler (23 Ağustos 2026)

### 10.1 Backend — additive parametre

`GET /appointments` uçuna opsiyonel `session_only` parametresi eklendi. Gönderilmediğinde
davranış **birebir eskisi**; gönderildiğinde yalnızca seans paketine ait randevular döner.
Sözleşme kuralı §5'e uygun (yeni davranış yeni query parametresi arkasında).

Gerekçe: seans ekranının "Tamamlanan" sekmesi geçmiş seansları göstermek zorunda, yani tarih
penceresine sığmıyor. Bu filtre sayesinde küçük ve sınırlı bir küme ayrıca çekilebiliyor.

### 10.2 `App.js` — tek ağır çağrı, iki hafif çağrıya bölündü

```
ÖNCE : /appointments                       → en eski 1000 kayıt, ölçekte 6,4 sn
SONRA: /appointments?start_date=<bugün-7g>  → panel + bildirimler
     + /appointments?session_only=true      → seans ekranı
```

İkisi `Promise.all` ile paralel çekilip `id` üzerinden tekilleştiriliyor. Dashboard, bildirimler,
`SessionsHub` ve "aktif seans var mı" kontrolü aynı `appointments` prop'unu görmeye devam ediyor —
tüketici bileşenlerde hiçbir değişiklik gerekmedi.

7 günlük geriye bakış, bildirim listesindeki yakın geçmişteki bekleyen public randevuların
kaybolmaması için.

### 10.3 Müşteri seçicileri — sunucu taraflı arama

| Dosya | Değişiklik |
|---|---|
| `AppointmentFormWizard.js` | `?limit=30&search=` + cursor tabanlı **sonsuz kaydırma** (Virtuoso `endReached`) |
| `PaymentRequestDrawer.js` | `?limit=50&search=`, 200 ms debounce |

Sihirbazda sonsuz kaydırma şart oldu: kullanıcı arama yapmadan da listeyi gezebiliyor, sadece
ilk 30'u göstermek gerileme olurdu. Backend zaten Türkçe collation ile sıralayıp arıyor
(`build_turkish_case_insensitive_pattern`), bu yüzden istemci tarafındaki sıralama/süzme
kaldırıldı; yalnızca kullanıcı yazarken debounce dolana kadar liste sıçramasın diye anlık
yerel süzme bırakıldı.

### 10.4 Ölü kod

`AppointmentForm.js` `App.js`'te import ediliyordu ama **hiçbir yerde render edilmiyordu** —
yani oradaki `/customers` çağrısı zaten hiç çalışmıyordu. Import kaldırıldı; paket 1,7 kB küçüldü.

### 10.5 Doğrulama

| Kontrol | Sonuç |
|---|---|
| `session_only` filtresi | izole geçici org ile test edildi: 2 randevudan seans paketi olan 1'i döndü — **geçti**, geçici veri silindi |
| Contract testleri | 13 passed |
| Frontend build | başarılı, yalnızca önceden var olan source-map uyarısı |
| Backend + frontend deploy | healthy |
| Canlı bundle | `main.776fe023.js` — `session_only`, `next_cursor`, `endReached` içinde doğrulandı |
| Prod veri | dokunulmadı |

---

## 11. Üretilen dosyalar

---

## 9. Üretilen dosyalar

| Dosya | İçerik |
|---|---|
| `k6_large_faz3.log` | Ham k6 çıktısı (16,8 KB) |
| `k6_large_faz3_summary.json` | Metrik özeti (7,5 KB) |
| `k6_faz3_analiz_raporu.md` | Bu rapor |

Karşılaştırma tabanı: `k6_analiz_raporu.md` (7 Ağustos, 6 test + 3 profil).

---

## 12. Panel profili — legacy uçlar çıkarıldı (24 Ağustos 2026, 01:30 TR)

Aynı 10k müşteri / 100k randevu, aynı 100 VU. Script artık panelin gerçek çağrılarını vuruyor:
pencere (`start_date=bugün−7`), `limit=30`, `session_only`, müşteri sayfalama/arama. Limitsiz
`/appointments` ve `/customers` yok.

**5.264 istek, sıfır hata, ortanca 100 ms.** MongoDB ayakta kaldı. Seed sonrası sentetik org silindi (prod 635 randevu).

| Uç | p95 önce (legacy script) | p95 şimdi |
|---|---|---|
| `/appointments?limit=30` | 418 ms | **166 ms** |
| `/customers?limit=30` | 387 ms | **131 ms** |
| `/stats/dashboard` | 374 ms | **182 ms** |
| `/services` | 314 ms | **119 ms** |
| `/customers?limit=30&search=` | 897 ms | **664 ms** |
| `/appointments?start_date=` (panel) | *(ölçülmemiş; eski limitsiz 6,42 sn)* | **623 ms** |
| `/appointments?session_only=true` | *(ölçülmemiş)* | **10,8 sn** |

Panelin asıl randevu çağrısı 6,4 sn → **0,62 sn**. Sayfalı uçlar da hızlandı (muhtemelen limitsiz uçların worker'ı boğmaması).

Genel `p(95)<2000` yine kaldı (**7,55 sn**). Bu kez suçlu `session_only`: tarih filtresi yok, `session_group_id` index'i yok, 100k dokümanda tarama. Seed'de hiç paket yoktu; yine de her istek org'u tarıyor. `App.js` bu çağrıyı açılışta paralel atıyor. Paketsiz işletmede de bedeli var.

Ham çıktı: `k6_large_panel.log` / `k6_large_panel_summary.json`.
