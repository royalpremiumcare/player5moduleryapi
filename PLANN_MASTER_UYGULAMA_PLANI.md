---
name: PLANN master uygulama planı
overview: Master plan belgesindeki tüm madde ve geliştirmelerin gerçek kodla doğrulanmış hali; düşükten yükseğe risk sırasına dizilmiş, her fazı tek tek onaylanabilir ve geri alınabilir uygulama planı.
todos:
  - id: faz0-envanter
    content: "Faz 0: Read-only prod envanteri — customers unique index durumu, duplicate raporu, telefon format dağılımı, card_saved:true org kontrolü, geri yüklenebilir yedek doğrulaması. Rapor onaya sunulur."
    status: completed
  - id: faz1-wizard-ux
    content: "Faz 1: AppointmentFormWizard hizmet ve müşteri arama empty state'leri, wizard içinden yeni hizmet oluşturma, akıllı ön-doldurma, müşteri listesi skeleton'ı. i18n metinleri eklenir."
    status: completed
  - id: faz2-katalog
    content: "Faz 2: Kategoriden toplu hizmet atama — additive POST /api/categories/{id}/services endpoint'i ve ServiceManagement.js çoklu seçim akışı."
    status: completed
  - id: faz3-index
    content: "Faz 3: appointments compound index'leri — (org, appointment_date, appointment_time, id) ve (org, staff_member_id, appointment_date). Öncesi/sonrası explain() ölçümü."
    status: completed
  - id: faz4-billing
    content: "Faz 4: Billing durum makinesi — invoice.payment_failed webhook, event.id idempotency, hosted_invoice_url endpoint, trial_expired/past_due_grace/suspended ayrımı, BillingGateModal + dashboard notice, draft state."
    status: pending
  - id: faz5-login-intercept
    content: "Faz 5: Login intercept — email enumeration riski için iki alternatifin karşılaştırmalı sunumu, seçilen yaklaşımın rate limit ve bot koruması ile uygulanması."
    status: pending
  - id: faz6-lock
    content: "Faz 6: Ölü PayTR recurring kodunun temizliği + ortak with_distributed_lock yardımcısı (ownership token, TTL, güvenli release) ve kilitsiz job'lara uygulanması."
    status: pending
  - id: faz7-phone
    content: "Faz 7: Canonical normalize_phone() ve tüm yeni yazma yollarında devreye alınması; wizard/public'teki isim şartının kaldırılması. Geriye dönük veri dönüşümü yok."
    status: pending
  - id: faz8-merge
    content: "Faz 8: Duplicate tespit → rapor → survivor → tüm referansların dry-run merge'ü → onay → kontrollü merge → bütünlük doğrulaması → unique index."
    status: pending
  - id: faz9-capgo
    content: "Faz 9: Capgo autoUpdate:false + manuel download/set + yüzdeli yükleme ekranı. Native build ve mağaza sürümü gerektirir."
    status: pending
  - id: faz10-auth
    content: "Faz 10: Auth v2 programı — identity soyutlaması, lazy migration, Google, Apple, secure credential/Face ID, provider-aware fallback. Her adım feature flag arkasında."
    status: pending
  - id: faz11-appleads
    content: "Faz 11: Apple Ads entegrasyonu — currency_shield deseniyle zamanlanmış sync, idempotent ingestion, superadmin panelinde raporlama."
    status: pending
  - id: faz12-inapp-subscribe
    content: "Faz 12: Mobil içi paket seçimi + Stripe Checkout In-App Browser — feature flag (Apple review), mevcut create_checkout_session, Capacitor Browser, deep link dönüşü. Kod onayı bekliyor."
    status: pending
isProject: false
---

# PLANN Master Plan — Doğrulanmış Uygulama Sırası

Belgedeki her madde gerçek kodla karşılaştırıldı. Aşağıdaki sıra **düşük riskten yükseğe** doğrudur ve her faz ayrı onay noktasıdır. Hiçbir faz, bir öncekinin onayı alınmadan başlamaz.

## Doğrulama Notu — Belge ile Kod Arasındaki Farklar

Uygulamaya geçmeden önce kabul edilmesi gereken düzeltmeler:

- `tenant_id` alanı yok; doğru alan `organization_id`. Belgedeki index komutu bu haliyle uygulanamaz.
- Reminder distributed lock **zaten var** ([backend/server.py](backend/server.py):667) + randevu bazında Mongo atomic claim ([backend/server.py](backend/server.py):724). Kilitsiz olanlar: `recurring_payment_job`, `tuesday_batch_prepare_cron`, `run_expiry_crons`, `run_sla_monitor_cron`, DLQ retry, settlement/wise job'ları.
- `customers_org_phone_unique` index'i kodda **zaten deneniyor**, hata alırsa non-unique fallback'e düşüyor ([backend/server.py](backend/server.py):1201-1241). Prod'daki gerçek durum DB'den okunmalı.
- Randevu-müşteri bağı `customer_id` değil, denormalize `phone` + `customer_name`.
- Wizard'da debounce zaten var (150 ms); eksik olan empty state ve wizard içinden hizmet oluşturma.
- `invoice.payment_failed` webhook'u ve `hosted_invoice_url` endpoint'i yok; Stripe Customer Portal ([backend/server.py](backend/server.py):8301) ve mobil→web SSO ([frontend/src/lib/openWebsiteSubscribe.js](frontend/src/lib/openWebsiteSubscribe.js)) var.

## Faz 0 — Read-Only Envanter (kod değişikliği yok)

Hiçbir yazma işlemi yapılmadan prod'dan rapor çıkarılır ve onaya sunulur:

- `customers` üzerinde `customers_org_phone_unique` index'i gerçekten var mı, yoksa fallback mi kurulmuş?
- `(organization_id, phone)` bazında duplicate sayısı, kaç org etkilenmiş, duplicate'lerin telefon format dağılımı.
- Aynı telefon + farklı isim varyantı sayısı (wizard/public kaynaklı duplicate'ler).
- `organization_plans` içinde `card_saved: true` olan org var mı (PayTR recurring job'un patlayıp patlamayacağını belirler).
- Geri yüklenebilirliği doğrulanmış MongoDB yedeği.

Çıktı: rapor + onay. Bu faz olmadan hiçbir DB fazına geçilmez.

## Faz 1 — Frontend UX (çok düşük risk, OTA ile gider)

1. **Wizard hizmet arama empty state** ([frontend/src/components/AppointmentFormWizard.js](frontend/src/components/AppointmentFormWizard.js):887-938): sonuç yoksa boş grid yerine "sonuç bulunamadı" + `[+ Yeni Hizmet Ekle]` + `[Aramayı Temizle]`. Yeni hizmet modalı arama metniyle ön-doldurulur, kaydedince wizard kaldığı yerden devam eder.
2. **Wizard müşteri arama empty state** ([frontend/src/components/AppointmentFormWizard.js](frontend/src/components/AppointmentFormWizard.js):1036-1064): aynı desen; girilen metin telefon formatındaysa isim yerine telefon alanına doldurulur.
3. **Müşteri listesi ilk yükleme skeleton'ı** (şu an boş liste görünüyor).

Backend'e dokunmaz. Tüm metinler i18n dosyalarına eklenir.

## Faz 2 — Katalog Toplu Atama (düşük risk, additive endpoint)

- Yeni endpoint: `POST /api/categories/{category_id}/services` — gövde `{ service_ids: [...] }`, yalnızca admin, `organization_id` filtreli, `update_many` ile `category_id` set eder. Mevcut hiçbir response şekli değişmez (contract güvenli).
- [frontend/src/components/ServiceManagement.js](frontend/src/components/ServiceManagement.js) kategori kartına "Hizmet Ata" akışı: çoklu seçim listesi ile tek seferde atama.

## Faz 3 — Appointments Compound Index (düşük risk, geri alınabilir)

Sorgu şekilleriyle uyuşmayan index'ler tespit edildi. `background` index olarak eklenecekler:

- `(organization_id, appointment_date, appointment_time, id)` — `GET /api/appointments` cursor sıralaması ([backend/server.py](backend/server.py):7643).
- `(organization_id, staff_member_id, appointment_date)` — Calendar haftalık/aylık görünüm.

Önce `explain()` çıktısı alınır, index sonrası tekrar ölçülür. Index eklemek geri alınabilir (`dropIndex`), veri değiştirmez.

## Faz 4 — Billing Durum Makinesi ve Paywall (orta risk)

Belgenin istediği üç durum backend'de gerçekten ayrıştırılır:

- `trial_expired` — hiç abonelik başlatılmamış, trial bitmiş.
- `past_due_grace` — ödeme başarısız, `SUBSCRIPTION_GRACE_DAYS = 3` içinde ([backend/server.py](backend/server.py):15356).
- `suspended` — grace bitmiş.

Adımlar:

1. `invoice.payment_failed` event'ini webhook handler'a ekle ([backend/server.py](backend/server.py):9168) ve `organization_plans` üzerine ödeme durumu yaz. Stripe `event.id` bazlı idempotency guard ekle (şu an yalnızca kısmi dup kontrolü var).
2. `GET /api/subscription/payment-link` — açık faturanın `hosted_invoice_url`'ini döndürür; yoksa Customer Portal'a düşer.
3. `check_quota_and_increment` ([backend/server.py](backend/server.py):2243) çıktısını durum koduyla zenginleştir; 403 gövdesine makine-okunur `state` alanı **ekle** (mevcut `detail` string'i aynen korunur — sahadaki donmuş mobil build'ler bozulmaz).
4. Frontend: tek bir `BillingGateModal` bileşeni, duruma göre metin/CTA değişir. Dashboard bildirimi için mevcut soft banner tasarımı yeniden kullanılır ([frontend/src/components/ForceUpdateModal.js](frontend/src/components/ForceUpdateModal.js):66-99).
5. Draft state: paywall açıldığında wizard formu saklanır, ödeme sonrası kaldığı yerden devam eder.
6. Ödeme sonrası state tazeleme: webhook + uygulama foreground'a gelince refresh + kritik aksiyon öncesi backend doğrulaması.

## Faz 5 — Login Intercept (orta risk, güvenlik kararı gerektirir)

`POST /api/auth/check-email` yok. Eklenecekse email enumeration riski nedeniyle: sıkı rate limit, Turnstile koruması ve yanıtın hesap varlığını doğrudan ifşa etmeyecek şekilde tasarlanması gerekir. Bu fazda önce iki alternatif (açık yanıt vs. koruma katmanlı yanıt) karşılaştırmalı sunulur, sonra uygulanır.

## Faz 6 — Zamanlanmış Görev Kilitleri (yüksek risk)

1. **Ölü PayTR kodunun temizliği:** `check_and_process_recurring_payments` içindeki tanımsız `PAYTR_*` sabitlerine giden yol kaldırılır veya job güvenli şekilde devre dışı bırakılır ([backend/server.py](backend/server.py):795-969). Faz 0'da `card_saved: true` org bulunursa önce bu ele alınır.
2. Ortak bir `with_distributed_lock` yardımcı fonksiyonu: ownership token + TTL + Lua compare-and-delete ile güvenli release.
3. Kilitsiz job'lara uygulanır: `tuesday_batch_prepare_cron`, `run_expiry_crons`, `run_sla_monitor_cron`, DLQ retry, settlement ve Wise job'ları.
4. **Fail-open kararı:** Redis erişilemezse şu an job'lar 17 worker'da birden çalışıyor. Para veya mesaj gönderen job'lar için fail-closed'a çevrilmesi ayrıca onaya sunulur.
5. Test: TTL dolması, worker restart, crash sonrası release, overlapping execution.

## Faz 7 — Telefon Normalizasyonu (yüksek risk)

- Tek bir canonical `normalize_phone()` yardımcı fonksiyonu (E.164, TR ve UK).
- **Yalnızca yeni yazma yollarında** devreye alınır: `POST /api/customers`, `POST /api/appointments`, public booking, bulk-session, AI aracı, `_apply_customer_delta`.
- Geriye dönük veri dönüşümü bu fazda **yapılmaz**; Faz 8'in parçasıdır.
- Wizard/public'teki "aynı telefon + farklı isim = yeni müşteri" davranışı gözden geçirilir: eşleşme telefona dayanır, isim farkı kayıt açmaz (isteğe bağlı olarak mevcut isim güncellenir).

## Faz 8 — Duplicate Merge ve Unique Index (en yüksek risk)

Belgedeki zorunlu sıra aynen uygulanır, otomatik silme yoktur:

```mermaid
flowchart LR
  A[Duplicate tespiti] --> B[Rapor]
  B --> C[Survivor kaydı belirle]
  C --> D[Tüm referansları bul]
  D --> E[Dry-run merge]
  E --> F[Fatih onayı]
  F --> G[Kontrollü merge]
  G --> H[Bütünlük doğrulaması]
  H --> I[Unique index]
```

Referans güncellenecek alanlar (denormalize telefon/isim taşıyanlar): `appointments`, `customer_notes`, `transactions`, `merchant_transactions`, `session_credits`, `stripe_customers`, `marketing_autopilot` görevleri, `refund_reconciliation_pending`. Sayaç alanları (`total_appointments`, `completed_appointments`, `first/last_appointment_at`) merge sonrası yeniden hesaplanır.

Walk-in/paylaşılan telefon senaryosu (`phone: "0"`) unique index'i engelleyebilir; index kurulmadan önce bu kayıtlar için ayrı strateji kararlaştırılır.

## Faz 9 — Capgo OTA Kontrolü (çok yüksek risk, native build gerektirir)

- `capacitor.config.json` içinde `autoUpdate: false` + uygulama içinde `download`/`set` + yüzdeli yükleme ekranı.
- Bu değişiklik OTA ile gönderilemez; mağaza sürümü gerektirir ve mevcut kullanıcılar mağazadan güncellemeden yeni akışa geçmez.
- Ön koşul olarak iOS `Podfile`'da Capgo pod'unun `cap sync` ile geldiği doğrulanmalı.

## Faz 10 — Auth v2 (çok yüksek risk, ayrı program)

Sıra: identity soyutlaması → mevcut e-posta kullanıcılarının lazy migration'ı → Google → Apple → secure credential/Face ID → provider-aware fallback. Her adım ayrı feature flag arkasında, eski `email + password` login'i hiç kapatılmadan. Detaylı migration kuralları belgede zaten tanımlı ve kodla uyumlu bulundu (tek `users` collection, `username` birincil kimlik, bcrypt hash korunur).

## Faz 11 — Apple Ads Entegrasyonu (ayrı program)

Mevcut `currency_shield` deseni (zamanlanmış sync + koleksiyon + on-demand tazeleme) bu iş için hazır bir şablon. Credential'lar `backend/.env` üzerinden, frontend'e hiç verilmeden. Gerçek API response şekli doğrulanmadan alan adı veya idempotency anahtarı varsayılmaz.

## Faz 12 — Mobil içi paket seçimi + Stripe Checkout (In-App Browser)

Faz 3'ten bağımsız, Faz 4'ten önce alınabilir. Native'de paket seçimini siteye atmak yerine uygulama içinde göstermek; kartı Stripe Checkout'ta `@capacitor/browser` (SFSafariViewController / Chrome Custom Tabs) ile almak. Apple review için feature flag varsayılan kapalı. Detay ve kod planı: aşağıda "Faz 12 — uygulama planı". Kod yazılmadan Fatih onayı bekleniyor.

## Her Faz İçin Ortak Kurallar

- Faz başlar: mevcut durum → değişiklik → test → Fatih manuel testi → onay → Capgo Internal OTA → sonraki faz.
- Backend'e dokunan her fazda contract testleri çalıştırılır (`tests/integration/`), response modelinden alan silinmez/yeniden adlandırılmaz, POST gövdelerine zorunlu alan eklenmez.
- DB'ye dokunan fazlarda önce dry-run raporu ve geri yüklenebilir yedek.
- Prod kanalına geçiş yalnızca tüm fazlar bitip son onay verildikten sonra.

---

# FAZ NOTLARI

Her faz sonunda bulgular, yapılanlar ve sonraki faza etkisi buraya eklenir.

## Faz 0 — Read-Only Prod Envanteri (tamamlandı, 22 Ağustos 2026)

Prod veritabanına hiçbir yazma yapılmadı. Envanter scripti: `/tmp/faz0_inventory.py` (yalnızca okuma).

### Veritabanı büyüklüğü

| Koleksiyon | Kayıt |
| --- | --- |
| customers | 3.004 |
| appointments | 629 |
| transactions | 2.502 |
| organization_plans | 75 |
| users | 81 |
| leads | 37.955 |
| Toplam (42 koleksiyon) | 61.355 doküman / 29 MB |

Müşteri sayısının randevu sayısının ~5 katı olması dikkat çekici: kayıtların büyük kısmı rehber/Excel içe aktarmasından gelmiş, gerçek randevu geçmişi olan müşteri azınlıkta.

### Bulgu 1 — Unique index kurulamamış (doğrulandı)

`customers` üzerindeki index'in adı **`customers_org_phone_nonunique`**. Yani `backend/server.py:1201`'deki unique deneme başarısız olmuş ve sessizce fallback'e düşülmüş. Duplicate koruması şu anda veritabanı seviyesinde **yok**.

### Bulgu 2 — Duplicate tablosu (beklenenden çok daha küçük)

| Ölçüm | Sonuç |
| --- | --- |
| Birebir aynı `(organization_id, phone)` grup | 9 grup / 17 fazla kayıt / 4 org |
| Normalize edilince duplicate olacak grup | 34 grup / 44 fazla kayıt / 9 org |
| Bunlardan format farkından gelen | 25 grup |
| Aynı telefon + farklı isim | 24 grup |
| Aynı telefon + aynı isim (güvenli birleştirme adayı) | 10 grup |
| Duplicate gruplara bağlı randevu | 27 grupta toplam 52 randevu |

Toplam temizlenecek kayıt 44 civarında. Bu, Faz 8'in riskini planlandığından belirgin şekilde düşürüyor: 3.000 kayıtlık bir veri setinde elle gözden geçirilebilir bir hacim.

### Bulgu 3 — Duplicate'lerin kaynağı bulundu: telefon rehberi içe aktarması

Etkilenen kayıtların büyük bölümü tek bir organizasyonda ve hepsi aynı imzayı taşıyor: aynı numara bir kayıtta `05...`, diğerinde `905...` formatında ve ikinci kaydın ismi **" Müşteri" son ekiyle** bitiyor (`Canan Çelik` / `Canan Çelik Müşteri`).

Kaynak, kod ve veri birlikte okunarak kesinleştirildi:

- `Customers.js` içindeki telefon rehberi içe aktarma özelliği (`@capacitor-community/contacts`, `saveContactsBatch`). İşletme sahibi kişileri telefonuna "Canan Çelik Müşteri" diye kaydetmiş; son ek rehberden aynen gelmiş, PLANN üretmemiş.
- `saveContactsBatch` telefonu **`90...` formatına normalize edip** tek tek `POST /api/customers`'a gönderiyor. Manuel/sihirbaz kayıtları ise kullanıcı ne yazdıysa (`05...`, `5...`) o şekilde saklıyor. Format ayrışması buradan doğuyor.
- 314 " Müşteri" son ekli kaydın 308'i tek organizasyonda, **291'i 26 Şubat 2026 15:21'de saniyeler içinde** oluşmuş — tek seferlik toplu içe aktarma. Hepsinin `total_appointments: 0`, hiçbirinin randevusu yok.
- O tarihte `POST /api/customers` yalnızca birebir telefon eşitliğine bakıyordu. Aynı günün akşamı, **19:45'te** `a2ced696` ("phone normalization for duplicate check") commit'i ile telefon varyantı kontrolü eklenmiş. Yani mevcut 44 mükerrer kayıt, bu düzeltmeden 4,5 saat önce yapılan tek bir içe aktarmanın kalıntısı.

Sonuç: **artık kitlesel mükerrer üretimi yok**, tek seferlik tarihsel bir artık temizlenecek. Faz 8 bu yönüyle güvenli.

### Bulgu 3b — Buna rağmen iki canlı mükerrer üretme yolu duruyor

Kod okumasında iki açık kaldığı görüldü; Faz 7 bunları kapatmalı:

1. `POST /api/customers` varyant üretimi asimetrik. Girdi `90...` (12 hane) veya prefixsiz 10 hane ise varyantlar üretiliyor; ancak girdi **`0...` (11 hane) ise hiç varyant üretilmiyor** (`server.py:11952-11959`). Yani `905052592138` kayıtlıyken kullanıcı `05052592138` yazarsa mükerrer oluşur. Bugün 2.649 kayıt `90...`, 191 kayıt `0...` formatında olduğu için bu senaryo gerçekçi.
2. `_apply_customer_delta` (`server.py:4610`) müşteriyi **birebir `{organization_id, phone}` ile upsert ediyor** — ne varyant kontrolü ne isim koşulu var. Randevudaki telefon hangi formatta yazıldıysa, o formatta yeni bir müşteri dokümanı doğuyor. Randevu oluşturan her yol bu fonksiyondan geçtiği için asıl kalıcı çözüm burada: tek bir kanonik `normalize_phone()`.

### Bulgu 4 — Telefon format dağılımı

`90...` (12 hane) %88,2 ile baskın; `0...` (11 hane) %6,4; `+90...` %3,1. Geri kalan %2 kırık veriye giriyor: 2 haneli 4 kayıt, 21 haneli 1 kayıt, 14-15 haneli kayıtlar. Faz 7'deki `normalize_phone()` bu kırık kayıtları normalize edemez; onlar için "dokunma, raporla" davranışı gerekiyor.

### Bulgu 4b — "Aynı numara, farklı isim" gruplarının sınıflandırması

34 duplicate grubu tek tek okundu (`/tmp/faz0_name_conflict.py`, salt okuma):

| Sınıf | Grup | Karar |
| --- | --- | --- |
| A — Yalnız " Müşteri" soneki veya birebir aynı isim | 19 | Güvenle birleştirilir |
| B — Yazım farkı / ek soyad (`Ceylin Küçük`–`Ceylin küçül`, `Melek Hilal Kaplan`–`Melek Hilal Ölmez Kaplan`) | 7 | Güvenle birleştirilir |
| C — **Aynı numarayı paylaşan farklı kişiler** | 4–5 | **Birleştirilmez** |
| D — Anlamsız isim (`müşteribelirsi`, `Ben`) | 2 | Elle karar |
| Ayrı tutulan | `phone: "0"` walk-in grubu (10 kayıt) | Birleştirilmez |

C sınıfının tamamı:

```
905313881212  Nazmiye Çelik (1 randevu)  /  Oğuz Çelik Müşteri (0)
905397200882  Orhan Durmaz  (1 randevu)  /  Mariye Hanım       (0)
905524875344  Makbule       (3 randevu)  /  Kadir Burak gökdere (1 randevu)
905435241758  İlayda        (1 randevu)  /  İrem               (0)
905301437705  Türkan Aksu   (1 randevu)  /  Türkan Türkeli     (0)
```

Bunlar mükerrer değil: aynı soyadlı iki kişi, anne–kız, karı–koca. Kuaför/güzellik işinde bir kadının kendi numarasıyla hem kendine hem kızına randevu alması olağan. `905524875344` grubunda **iki kaydın da gerçek randevusu var**, yani ikisi de aktif müşteri.

### Bulgu 4c — Unique index kararı yeniden değerlendirilmeli

Belge `(organization_id, phone)` üzerine unique index öngörüyor. Bulgu 4b ve Bulgu 5 birlikte okunduğunda bu enstrüman bu iş için yanlış:

- Bugünkü 4–5 meşru kaydı imkânsız kılar (silmek ya da birleştirmek zorunda kalırız — veri kaybı).
- **Gelecekteki meşru kayıtları da engeller:** anne kızı için randevu almak istediğinde "bu numara zaten kayıtlı" hatası alır.
- Telefonu alınmamış 10 walk-in kaydı (`phone: "0"`) engeller.

Index'in dayandığı "bir telefon = bir müşteri" varsayımı bu sektörde doğru değil. Gerçek hedef "aynı kişinin iki kez kaydedilmemesi" ve bu, veritabanı kısıtıyla değil yazma yolundaki davranışla çözülür:

1. Faz 7 — tüm yazma yollarında kanonik `normalize_phone()`. 34 grubun 25'i zaten yalnızca format farkından doğduğu için bu tek başına kaynağı kurutur.
2. Kayıt anında — normalize edilmiş numara zaten varsa sessizce yeni kayıt açma; mevcut kişiyi göster ve "bu kişi mi, yoksa aynı numarayı kullanan başka biri mi?" diye sor. Hem mükerreri keser hem aile senaryosunu yaşatır.

Veritabanı seviyesinde bir kısıt yine de istenirse tek uyumlu seçenek, placeholder ve bilinçli çoklu kayıtları dışarıda bırakan partial unique index'tir; ancak yukarıdaki iki adım uygulandıktan sonra pratik faydası sınırlı kalır.

**Karar (Fatih onayı):** unique index kurulmayacak; çözüm Faz 7 normalizasyonu + kayıt anında kimlik sorusu üzerinden yürüyecek. Faz 8'de yalnızca A + B sınıfları (26 grup) birleştirilecek, C ve D ile walk-in grubuna dokunulmayacak.

### Bulgu 4d — Public randevu akışının bu karara etkisi

`POST /public/appointments` (`server.py:14710-14745`) bugün şunu yapıyor:

1. `_phone_match_variants` ile numaranın tüm saklama formatlarını tarıyor. **Bu fonksiyon eksiksiz** (`0...`, `90...`, `+90...`, 10 hane) — Bulgu 3b'deki asimetrik varyant hatası burada yok.
2. Eşleşenler arasında **birebir isim eşitliği** (case-insensitive) arıyor; tutmazsa yeni müşteri açıyor.
3. İsim tuttuysa `resolved_customer_phone` mevcut kaydın telefonunu alıyor, böylece `_apply_customer_delta` doğru dokümana yazıyor.

Belge bu isim şartını "kaldırılacak hata" sayıyor; **kaldırılmamalı**. Aile senaryosunu ayakta tutan tam olarak bu şart: kaldırılırsa annesinin numarasıyla randevu alan kız çocuğu sessizce annenin kaydına yazılır. Şart doğru, fazla katı olması yanlış (`Canan` ↛ `Canan Çelik`, `Andac` ↛ `Andaç`).

Public'te yönetici olmadığı için "bu kişi mi?" sorusu ziyaretçiye sorulamaz. Faz 7 sonrası üç kademeli davranış:

1. Telefon kanonik saklanır — format kaynaklı mükerrer public'te de biter.
2. İsim karşılaştırması normalize edilir (büyük-küçük harf, Türkçe karakter ç/c ş/s ı/i ğ/g ö/o ü/u, fazla boşluk). Bir isim diğerinin token alt kümesiyse (`Alara` ⊂ `Alara kaya`) aynı kişi sayılır — **yalnızca o numarada tek müşteri varsa**; numarayı iki kişi paylaşıyorsa tam eşleşme aranır.
3. Kalan belirsizlikte (harf hatası: `Küçük`/`küçül`) public tahmin yürütmez. Otomatik birleştirme, benzer isimli iki kardeşi (`Elif` / `Elif Naz`) tek kişiye indirme riski taşır. Kayıt normal açılır, işletme sahibine uygulama içinde "bu numarada zaten X kayıtlı — aynı kişi mi?" önerisi gösterilir ve tek dokunuşla birleştirilir.

**Kapsam kararı (Fatih onayı):** 3. maddedeki müşteri listesinde birleştirme önerisi arayüzü **Faz 8'in kuyruğuna eklendi**. Birleştirme motoru zaten o fazda yazılacağı için arayüz onun üstüne binecek; ayrı bir faz açılmayacak. Bu, belgede olmayan yeni bir iştir ve Faz 8'in kapsamını genişletir.

### Bulgu 5 — Walk-in placeholder sorunu

Tek bir organizasyonda `phone: "0"` olan **10 kayıt** (9 farklı isim) ve `phone: "00"` olan 1 kayıt var. Bunlar gerçek duplicate değil, telefonu alınmamış müşteriler. Düz bir unique index bu kayıtları engeller. Çözüm Faz 8'de: ya partial index (placeholder değerleri hariç tutan), ya da bu kayıtlara benzersiz bir iç anahtar verilmesi. Karar verilmeden index kurulmamalı.

### Bulgu 6 — PayTR mayını uyuyor

`organization_plans` içinde `card_saved: true` olan **0 kayıt**, `payment_utoken` dolu **0 kayıt**. Yani recurring payment job'u bugün PayTR koduna hiç girmiyor ve patlamıyor. Aciliyet yok, ancak kod kaldırılmadığı sürece ileride biri kart kaydettiğinde job `NameError` ile düşer. Faz 6'da temizlenecek.

### Bulgu 7 — Yedek sistemi var ve çalışıyor (fiilen doğrulandı)

Kurulu yedek mekanizması: `/var/backups/plann_mongodb/backup.sh`, root crontab'ında **saatlik** (`0 * * * *`). `mongodump --archive --gzip` ile tam sunucu yedeği alıyor, 10 günden eski dosyaları siliyor. Yanında `restore_latest.sh` geri yükleme scripti de mevcut.

Sağlık kontrolü:

- 241 yedek dosyası, en yenisi bugün 20:00. Beklenen ~240 dosyaya karşılık **hiç atlanmış saat yok**.
- 0 baytlık veya yarım kalmış dosya yok; en küçük yedek 3,66 MB (normal aralıkta). Toplam 864 MB.

Geri yüklenebilirlik ilk kez fiilen kanıtlandı — cron'un ürettiği **en son yedek** (`backup_2026-08-22_20-00.gz`) izole bir `plann_restore_test` veritabanına gerçekten geri yüklendi:

- **61.355/61.355 doküman, 0 hata**, 42/42 koleksiyon, sayılar prod ile birebir eşleşti.
- Index tanımları da yedekten geldi (`customers_org_phone_nonunique` dahil).
- Test veritabanı çift güvenlik kontrolüyle silindi; prod veritabanına hiç dokunulmadı.

Ayrıca fazlar boyunca dönmeyecek sabit bir referans noktası olarak `/var/backups/plann/plann_20260822_204309.archive.gz` alındı (saatlik yedekler 10 günde döngüye girdiği, faz programı ise daha uzun süreceği için).

İyileştirme önerileri (bloklayıcı değil):

- Yedekler **veritabanıyla aynı diskte**. Sunucu/disk kaybı senaryosunda yedek de gider. Haftalık bir kopyanın sunucu dışına alınması tek gerçek açık.
- `restore_latest.sh` `--drop` ile çalışıyor ve en yeni dosyayı sorgusuz seçiyor. Yedek bozuksa önce prod'u siler, sonra geri yükleyemez. Başına basit bir bütünlük kontrolü (dosya boyutu ve `--dryRun`) eklenmesi ucuz bir sigorta.
- Her iki script'te MongoDB parolası düz metin. Dizin `drwx------` (yalnız root) olduğu için acil değil, ancak `.env`'den okunması daha temiz olur.

### Bulgu 8 — Abonelik tablosu

75 organizasyonun 72'si `tier_trial`, 2'si `tier_6_kurumsal`, 1'i `tier_1_standard`. `stripe_subscription_id` dolu olan **1 organizasyon** var. Faz 4'teki billing durum makinesi bugün neredeyse tamamen trial ve trial bitişi senaryosu üzerinden test edilecek; `past_due_grace` ve `suspended` yollarını gerçek veriyle doğrulamak mümkün değil, Stripe test modu gerekecek.

### Faz 0'ın sonraki fazlara etkisi

- **Faz 8 küçüldü ve güvenli hale geldi:** 44 fazla kayıt, 52 randevu bağı, kaynağı bilinen tek seferlik bir artık. Geriye tek karar kaldı: Bulgu 5'teki `phone: "0"` walk-in kayıtları için partial index mi, iç anahtar mı.
- **Faz 7 netleşti ve öncelik kazandı:** asıl iş `_apply_customer_delta` ile `POST /api/customers`'ı tek bir kanonik `normalize_phone()` üzerinde birleştirmek (Bulgu 3b). Normalizasyon `0...` ve `+90...` kayıtlarını hedefleyecek; kırık kayıtlar (2, 14, 15, 21 hane) dönüştürülmeyip raporlanacak. Faz 8'den önce gelmesi mantıklı — önce musluk kapatılır, sonra yer silinir.
- **Faz 6'nın aciliyeti düştü:** PayTR mayını şu an tetiklenmiyor (`card_saved: true` sıfır org).
- **Yedek kalemi kapandı:** ayrı bir cron kurulmasına gerek yok, mevcut saatlik yedek çalışıyor ve geri yüklenebilirliği kanıtlandı. Sunucu dışına kopya alınması ayrı ve düşük öncelikli bir iyileştirme olarak duruyor.

### Faz 0 çıktıları

- `/tmp/faz0_inventory.py` — yalnızca okuma yapan envanter scripti, tekrar çalıştırılabilir.
- `/var/backups/plann/plann_20260822_204309.archive.gz` — fazlar boyunca dönmeyecek sabit referans yedeği.
- Prod veritabanına yapılan yazma işlemi: **yok**.

## Faz 1 — Sihirbaz UX (kod yazıldı, deploy edilmedi — 23 Ağustos 2026)

Yalnızca frontend. Backend'e, veritabanına, endpoint'lere, response şekillerine **dokunulmadı**.

### Yapılanlar

**1. Hizmet arama boş sonuç ekranı** (`AppointmentFormWizard.js`, `renderStep1`)

Sonuç yokken boş grid yerine iki ayrı durum gösteriliyor:

- Arama yapılmışsa: "Bu aramaya uyan hizmet yok" + aranan terim + `[Yeni Hizmet Ekle]` + `[Aramayı Temizle]`.
- Hiç hizmet yoksa: "Henüz hizmet eklenmemiş" + `[Yeni Hizmet Ekle]`.
- Kullanıcı **admin değilse** hizmet ekleme butonu gösterilmiyor; yerine "yöneticinizden hizmet ataması isteyin" notu çıkıyor. Sebep: `POST /api/services` admin dışına 403 dönüyor (`server.py:7872`), butonu göstermek kullanıcıyı hataya sürüklerdi.

**2. Sihirbaz içinden hizmet oluşturma**

Yeni bir modal: ad, fiyat, süre. Ad alanı **arama metniyle ön-doldurulur**. Kaydedince `POST /api/services` çağrılır, dönen hizmet seçilir ve akış kaldığı yerden devam eder (tek hizmet modunda otomatik adım 2'ye geçer, çoklu hizmet modunda sepete eklenir).

Teknik ayrıntı: `services` bir prop ve parent yeniden yükleyene kadar yeni kaydı içermiyor. Bu boşluğu kapatmak için `createdServices` yerel listesi ve `allServices` birleşik memo'su eklendi; sihirbazdaki 7 `services.find/filter` kullanımı `allServices`'e taşındı. Böylece yeni hizmetin fiyatı, süresi ve paket kontrolü ilk saniyeden itibaren doğru çalışıyor. Ayrıca `App.js`'ten opsiyonel `onServiceCreated` (= `loadServices`) prop'u geçirildi, parent listesi de tazeleniyor.

**3. Müşteri arama boş sonuç ekranı** (`renderStep2`)

Aynı desen, artı **akıllı ön-doldurma**: aranan metin telefon formatındaysa (yalnız rakam/`+`/boşluk/parantez/tire ve 6–11 hane) yeni müşteri kartında **telefon** alanına, değilse **isim** alanına yazılıyor. Açıklama metni de buna göre değişiyor ("… adında müşteri bulunamadı" / "… numarasına kayıtlı müşteri bulunamadı").

Boş sonuç ekranı kendi "Yeni Müşteri" butonunu taşıdığı için, listenin üstündeki kesikli "Yeni Müşteri" butonu bu durumda gizleniyor — iki aynı buton yan yana çıkmıyor.

**4. Yükleme iskeletleri**

- Müşteri listesi: `loadCustomers` artık `customersLoading` tutuyor; liste gelene kadar 5 satırlık iskelet gösteriliyor (eskiden boş liste görünüyordu).
- Hizmet listesi: `App.js`'e `servicesLoading` eklendi ve prop olarak geçildi. **Sebep:** boş sonuç ekranı eklenince, hizmetler daha yüklenmemişken ilk açılışta "Henüz hizmet eklenmemiş" yanıp sönüyordu. Artık yükleme sürerken 4 satırlık iskelet çıkıyor, boş sonuç ekranı yalnızca yükleme bittikten sonra gösteriliyor.

### Dokunulan dosyalar

| Dosya | Değişiklik |
| --- | --- |
| `frontend/src/components/AppointmentFormWizard.js` | Boş sonuç ekranları, yeni hizmet modalı, iskeletler, `allServices` birleşik listesi |
| `frontend/src/App.js` | `servicesLoading` state'i, `loadServices` finally bloğu, iki yeni prop |
| `frontend/src/i18n/locales/tr/translation.json` | 25 yeni anahtar (`appointments.form.wizard.*`) |
| `frontend/src/i18n/locales/en/translation.json` | Aynı 25 anahtarın İngilizcesi |

Hardcode metin yok; TR/EN anahtar sayıları eşit (38/38) ve iki tarafta da eksik anahtar bulunmuyor.

### Build

`npx craco build` → **Compiled with warnings** (yalnızca mevcut `fb-pixel.js` source map uyarısı ve browserslist tazelik uyarısı; ikisi de bu değişiklikten önce de vardı). Bundle artışı canlıdaki sürüme göre **11 KB ham** (~2-3 KB gzip).

Yerel `frontend/build/` klasörü derleme doğrulaması için üzerine yazıldı; bu klasör `.gitignore`'da ve **hiçbir nginx konfigürasyonu tarafından servis edilmiyor** (canlı frontend, imaja gömülü kopyayı servis ediyor). Yani prod etkilenmedi.

### Deploy ve smoke test (23 Ağustos 2026, canlıda)

`docker compose build frontend && docker compose up -d frontend` çalıştırıldı. İmaj build'i `generate-seo-html.js`'i de çalıştırdı: **42 SEO shell dosyası** yeniden üretildi.

| Kontrol | Sonuç |
| --- | --- |
| `plann_frontend` container | Up, **healthy** |
| Canlı bundle | `main.1f10e6a5.js` (yeni build) |
| `plannapp.co` | 200 |
| `plannapp.co.uk` | 200 |
| `/cozumler/kuafor-randevu-sistemi` | 200 |
| `/features/whatsapp-reminders` | 200 |
| `POST /api/token` | 422 (backend ayakta, beklenen doğrulama hatası) |
| Yeni i18n anahtarları canlı bundle'da | 5/5 doğrulandı |

SEO shell'leri, canonical/hreflang yapısı ve backend etkilenmedi.

### Durum

**Canlıda (web).** Capgo Internal OTA, Fatih'in manuel testi ve onayından sonra.

### Fatih'in manuel test edeceği noktalar

1. Yeni randevu → hizmet aramasına olmayan bir şey yaz → boş ekran çıkıyor mu, `[Yeni Hizmet Ekle]` ad alanını aradığın metinle dolduruyor mu.
2. Modaldan hizmet oluştur → toast geliyor mu, hizmet seçili olarak adım 2'ye geçiyor mu, fiyat/süre doğru görünüyor mu.
3. Hizmetler sayfasına git → yeni hizmet listede duruyor mu (parent tazelemesi).
4. Müşteri aramasına önce bir isim, sonra bir telefon numarası yaz → "Yeni Müşteri" hangi alanı dolduruyor.
5. Uygulamayı yeni açıp hemen randevu ekranına gir → "henüz hizmet yok" yanıp sönüyor mu (sönmemeli, iskelet çıkmalı).
6. Personel (staff) hesabıyla gir → hizmet ekleme butonu görünmemeli.

### Faz 1 düzeltmesi — hizmet modalı alan eşitliği (23 Ağustos 2026)

**Geri bildirim:** modalda Hizmet Yönetimi'ndeki alanların hepsi yoktu; ödeme kuralı ve seans bölümleri eksikti.

Modal artık `ServiceManagement.js`'teki formla birebir aynı alanları taşıyor: kategori seçimi, seans paketi anahtarı + seans sayısı, ödeme kuralı (yerinde / tamamı online / sadece kapora) ve kapora tutarı. Bölüm başlıkları da aynı — Temel Bilgiler / Paket Tipi / Ödeme. Uzayan form için modal `max-h-[88vh]` ile kaydırılabilir yapıldı, başlık ve buton çubuğu sabit kaldı.

`POST /api/services` gövdesine `session_count`, `payment_rule`, `deposit_amount`, `category_id` eklendi. Dördü de `ServiceCreate` içinde zaten Optional; **yeni zorunlu alan eklenmedi, response şekli değişmedi** — API sözleşmesi korunuyor.

Kategoriler her sihirbaz açılışında değil, **modal ilk kez açıldığında** bir kez çekiliyor (`GET /api/categories`); kategori yoksa alan hiç görünmüyor.

Doğrulama eşikleri backend'den (`server.py:7801 _validate_service_payment_limits`) alındı: online/kapora için minimum fiyat 300, minimum kapora 200 ve kapora ≤ fiyat. Bunlar sabit olarak tanımlandı, son söz yine backend'de.

> **Not — mevcut bir tutarsızlık (bu fazda dokunulmadı):** `ServiceManagement.js` İngilizce arayüzde bu limitleri "£5" ve "£3" olarak yazıyor, oysa backend para birimi ne olursa olsun 300 ve 200 uyguluyor. Sihirbaz modalı gerçek eşiği gösteriyor. Hizmet Yönetimi'ndeki metnin düzeltilmesi ayrı ve küçük bir iş; onay verirseniz ayrıca yapılır.

TR/EN anahtar sayısı 58/58, iki tarafta da eksik yok. Build **Compiled with warnings** (yalnızca eski `fb-pixel.js` source map uyarısı), bundle `main.78fadc20.js`, +1.14 KB gzip. Deploy sonrası `plann_frontend` **healthy**, `plannapp.co` ve `plannapp.co.uk` 200, `generate-seo-html.js` yine 42 shell üretti. Yeni anahtarlar ve görünen metinler canlı bundle içinde tek tek doğrulandı.

Ek test noktası: modalda ödeme kuralını **Sadece Kapora** yap → kapora alanı açılıyor mu, 200'ün altında veya fiyatın üstünde bir tutarda uyarı veriyor mu; seans anahtarını aç → seans sayısı alanı çıkıyor mu; oluşturduğun hizmeti Hizmetler sayfasında aç → seans ve kapora rozetleri doğru görünüyor mu.

### Faz 1 düzeltmesi #2 — uyarı yeri, kategori ve safe-area (23 Ağustos 2026)

**1. Uyarılar modalın içine alındı.** Minimum fiyat ve kapora uyarıları `toast` ile veriliyordu; toast modalın arkasında kaldığı için kullanıcı hiçbir şey görmeden "kaydet"e basıyordu. Sihirbaz modalında artık `newServiceErrors` ile alan bazlı hata gösteriliyor: ad, fiyat, süre, seans sayısı, ödeme kuralı ve kapora tutarı kendi alanının altında kırmızı uyarı ve kırmızı kenarlık alıyor. Backend'den dönen hata da (ör. contract doğrulaması) artık toast yerine formun altındaki kırmızı kutuda çıkıyor — modal açık kaldığı için tek görünür yer orası.

`ServiceManagement.js` bu uyarıları zaten inline gösteriyordu, ama iki sorunu vardı: uyarı **fiyat alanının** altında çıkıyordu (kullanıcı ödeme bölümündeyken ekranın dışında kalıyor) ve ödeme kuralı seçimi **sessizce geri alınıyordu**. İkisi de düzeltildi: seçim artık geri alınmıyor, uyarı seçimin hemen altında görünüyor.

Ayrıca İngilizce metinlerdeki yanlış eşikler düzeltildi: arayüz "£5" ve "£3" yazıyordu, backend ise para biriminden bağımsız 300 ve 200 uyguluyor. Metinler gerçek eşiği söyleyecek şekilde güncellendi.

**2. Kategori alanı iki formdan da kaldırıldı.** Hem sihirbaz modalından hem `ServiceManagement.js` hizmet formundan. Sihirbazda `GET /api/categories` çağrısı ve ilgili state tamamen silindi.

> **Dikkat — geçici boşluk:** kategori atamasının tek yolu buydu. Şu an kategori oluşturulabiliyor, adı değiştirilebiliyor, sıralanabiliyor ve müşteri sayfasında gruplama çalışmaya devam ediyor; ama **yeni bir hizmete kategori atanamıyor**. Yeni yol Faz 2'de geliyor (kategori kartından çoklu hizmet atama). Faz 2'yi sıradaki iş olarak öneriyorum.

> **Veri koruması:** `formData.categoryId` görünmese de formda taşınmaya devam ediyor. Sebebi `update_service` ([backend/server.py](backend/server.py):7837): `category_id` payload'da `None` gelirse alanı `$unset` ediyor. Alanı tamamen çıkarsaydım, kategorili bir hizmeti düzenleyen herkes o hizmetin kategorisini farkında olmadan silecekti. Mevcut atamalar olduğu gibi duruyor.

**3. Safe-area düzeltmesi.** Modal açıkken ekranın en altında beyaz bir şerit kalıyor ve modalın üstü durum çubuğuna (saat/bildirim) taşıyordu.

Beyaz şeridin sebebi `index.css`'te zaten belgelenmiş: bu WebView kurulumunda `fixed inset-0` safe-area'yı kapsamıyor ve o şeritte `html`'in arka planı görünüyor. Proje bunu tema rengiyle (light'ta beyaz) maskelemiş — sihirbazın kendi tam ekran sayfası da beyaz olduğu için fark edilmiyordu, koyu overlay açılınca ortaya çıktı. `dialog.jsx` ve `alert-dialog.jsx` overlay'lerine negatif `env(safe-area-inset-*)` inset'i eklendi; overlay şeritlerin üstüne taşıyor. Safe-area'nın 0 olduğu platformlarda ekran dışına taşar, görünür etkisi yok.

Durum çubuğu taşması ise modalın `max-h-[88vh]` olmasından: 844 px'lik bir ekranda 743 px'lik modal ortalanınca üstte 50 px kalıyor, durum çubuğu ~47 px. `max-h-[78dvh]` yapıldı, üstte ~93 px boşluk kalıyor. İçerik zaten kaydırılabilir.

Bu iki değişiklik `ui/dialog.jsx` ve `ui/alert-dialog.jsx` üzerinden **uygulamadaki tüm modalleri** etkiliyor, ama ikisi de yalnızca kaplama alanını genişletiyor; hiçbir modalin davranışı veya içeriği değişmiyor.

**Build ve deploy:** `main.920d8c3f.js`, +118 B. `plann_frontend` healthy, `plannapp.co` / `plannapp.co.uk` / örnek SEO sayfası 200, 42 SEO shell yeniden üretildi. TR/EN anahtar sayısı 56/56.

**Doğrulanamayan nokta:** safe-area davranışı masaüstü tarayıcıda üretilemiyor. Beyaz şerit ve durum çubuğu taşması gerçek cihazda kontrol edilmeli.

### Faz 1 düzeltmesi #3 — ödeme eşikleri para birimine bağlandı (23 Ağustos 2026)

Bir önceki maddede "arayüz £5 diyor, backend 300 uyguluyor, metin yanlış" demiştim. **Yanlış olan metin değil, backend'di.**

`financial/money.py` zaten doğru eşikleri tutuyor ve checkout tarafı (`merchant_checkout.py`) bunları kullanıyor:

| Para birimi | Min. online fiyat | Min. kapora |
| --- | --- | --- |
| TRY | ₺300 | ₺200 |
| GBP | £5 | £3 |

`server.py`'deki `_validate_service_payment_limits` ise TRY değerlerini sabit kodluyordu. Sonuç: **GBP işletmelerde £300 altındaki hiçbir hizmete online ödeme veya kapora açılamıyordu.** Bir İngiliz kuaförün £45'lik boya hizmeti için kapora alması mümkün değildi — arayüz doğru limiti (£5) söylüyor, backend reddediyordu.

Düzeltme: yeni `_get_org_base_currency()` yardımcısı organizasyonun `base_currency` ayarını okuyor, `_validate_service_payment_limits` eşikleri `financial/money.py`'den alıyor. Artık checkout ile hizmet kaydı aynı kaynağı kullanıyor, ikinci bir sabit liste yok. Hata mesajları da `format_display_short` ile doğru sembolü basıyor. Bilinmeyen bir para birimi gelirse TRY'ye düşülüyor.

Frontend'de her iki formdaki sabit 300/200 değerleri de para birimine bağlandı (`paymentMinimums`). Bir önceki adımda "300" diye değiştirdiğim İngilizce metinler `£5`/`£3`'e geri alındı.

**Sözleşme etkisi yok:** response şekli değişmedi, yeni zorunlu alan eklenmedi. Değişiklik yalnızca GBP işletmeler için doğrulamayı **gevşetiyor** — donmuş mobil sürümler için güvenli yön.

**Bilinen zayıflık (bu fazda dokunulmadı):** frontend para birimini `support_phone`'un `+44` ile başlayıp başlamamasına bakarak tahmin ediyor; `GET /api/settings` `base_currency` alanını döndürmüyor (`Settings` modelinde yok, `extra="ignore"` ile eleniyor). Yani TR telefonlu bir GBP işletmede arayüz yanlış eşiği gösterebilir. Backend artık doğru davrandığı için bu yalnızca görsel bir tutarsızlık. Kalıcı çözüm `Settings` modeline `base_currency` eklemek (response'a alan eklemek sözleşme açısından güvenli); ayrı madde olarak duruyor.

**Doğrulama:** contract testleri `13 passed`. Backend healthy, `POST /api/token` → 422. Frontend `main.199541ba.js`, iki alan adı da 200. Sabit `30_000` karşılaştırması canlı `server.py`'de kalmadı, GBP ve TRY eşikleri canlı bundle'da doğrulandı.

---

## Faz 2 — Kategoriden Toplu Hizmet Atama (tamamlandı, canlıda — 23 Ağustos 2026)

Faz 1'de hizmet formundan kategori seçimini kaldırmıştık; bu faz o boşluğu dolduruyor ve atamayı kategori tarafına taşıyor.

### Backend — yeni endpoint (additive)

`POST /api/categories/{category_id}/services`, gövde `{ "service_ids": [...] }`.

Semantik **tam üyelik listesi**: gönderilen liste kategorinin yeni içeriğidir. Listedekilere `category_id` atanır, kategoride olup listede olmayanların ataması `$unset` ile kaldırılır. Boş liste kategoriyi boşaltır. Bu, arayüzdeki çoklu seçim kutusunun "kaydet" davranışıyla birebir örtüşüyor — ayrı bir "çıkar" endpoint'ine gerek kalmıyor.

Korumalar: yalnızca `admin` (aksi 403), kategori `organization_id` ile doğrulanıyor (yoksa 404), gönderilen her `service_id` aynı organizasyonda mı diye kontrol ediliyor (değilse 400). Böylece başka bir organizasyonun hizmeti bu kategoriye çekilemiyor. İşlem sonunda `invalidate_service_caches` çağrılıyor.

Dönen gövde: `{category_id, assigned_count, removed_count, total_in_category}`.

**Sözleşme etkisi yok:** yeni bir yol eklendi, mevcut hiçbir response şekli veya request gövdesi değişmedi. Contract testleri `13 passed`.

### Frontend — kategori kartından çoklu seçim

`ServiceManagement.js` kategori satırı artık kaç hizmet içerdiğini gösteriyor ("3 hizmet" / "Hizmet atanmamış") ve yeni bir **Hizmetler** butonu taşıyor. Buton, işletmenin tüm hizmetlerini listeleyen bir seçim modalı açıyor; kategoride hâlihazırda olanlar işaretli geliyor. Başka bir kategoriye ait bir hizmetin altında "şu an X içinde" notu çıkıyor, böylece kullanıcı taşıma yaptığını bilerek yapıyor. Hizmet sayısı 8'i geçtiğinde arama kutusu beliriyor. Kaydet butonu seçili sayıyı gösteriyor.

Modal Faz 1'deki `max-h-[78dvh]` desenini kullanıyor, yani safe-area düzeltmesinden faydalanıyor.

### i18n

`services.categories.*` altındaki metinler **kod içinde `t(key, 'Türkçe varsayılan')` biçiminde gömülüydü** — yani İngilizce arayüzde "Kategoriler", "Örn: Saç Hizmetleri", "Kategoriyi Sil" gibi Türkçe metinler görünüyordu. Bu faz kapsamında tüm blok iki dile de gerçek anahtar olarak yazıldı (32/32, çoğul biçimler dahil). Varsayılanlar kodda duruyor ama artık devreye girmiyor.

Çeviri dosyaları yeniden biçimlendirildi; anlamsal karşılaştırmayla **hiçbir anahtarın silinmediği veya değerinin değişmediği** doğrulandı (1478/1478, silinen 0).

### Doğrulama

| Kontrol | Sonuç |
| --- | --- |
| Contract testleri | 13 passed |
| Token'sız `POST /api/categories/{id}/services` | 401 |
| `plann_backend` / `plann_frontend` | healthy |
| `plannapp.co`, `plannapp.co.uk`, örnek SEO sayfası | 200 |
| SEO shell'leri | 42 dosya yeniden üretildi |
| Canlı bundle | `main.7d76e235.js`, yeni metinler TR ve EN doğrulandı |

### Fatih'in manuel test edeceği noktalar

1. Hizmetler → Kategoriler bölümünde bir kategorinin **Hizmetler** butonuna bas → mevcut hizmetleri işaretli geliyor mu.
2. Birkaç hizmet işaretle, birkaçının işaretini kaldır, kaydet → kategori satırındaki sayı güncelleniyor mu, hizmet kartlarındaki kategori rozeti doğru mu.
3. Başka kategoriye ait bir hizmeti işaretle → "şu an X içinde" notu görünüyor mu, kaydettikten sonra gerçekten taşınıyor mu.
4. Müşteri rezervasyon sayfasını aç → hizmetler doğru kategori altında gruplanıyor mu.
5. Bir kategorideki tüm işaretleri kaldır → kategori boşalıyor ama hizmetler silinmiyor, değil mi.
6. Personel hesabıyla gir → Hizmetler yönetimi zaten admin'e özel; erişim davranışı değişmemeli.

### Faz 2 düzeltmesi — atama modalı (23 Ağustos 2026)

Dört sorun bildirildi, dördü de düzeltildi ve canlıya alındı (`main.e76df631.js`).

**1. Ham çeviri anahtarı görünüyordu.** `services.categories.currentlyIn` anahtarını çeviri dosyalarına eklemeyi atlamışım; başka bir kategoriye ait hizmetlerin altında ham anahtar yazıyordu. İki dile de eklendi. Ayrıca kodda kullanılan tüm `services.categories.*` anahtarları taranıp iki dosyayla karşılaştırıldı — başka eksik yok.

**2. Modal açılınca klavye fırlıyordu.** Radix modalı açarken ilk odaklanabilir öğeye odaklanıyor, o da arama kutusuydu. Atama modalinde `onOpenAutoFocus` engellendi; odak modalin kendisine gidiyor, klavye kullanıcı arama kutusuna dokununca açılıyor. (Sihirbazdaki yeni hizmet modalinde otomatik odak **bilinçli** duruyor: ad alanı arama metniyle dolu geliyor ve kullanıcı çoğunlukla oraya yazmaya devam ediyor.)

**3. Kapatma butonu küçüktü.** `ui/dialog.jsx`'te ikon 16 px ve dokunma alanı yoktu. İkon 20 px'e çıkarıldı, çevresine dolgu ve hover zemini eklendi; dokunma hedefi ~32 px oldu. Uygulamadaki tüm modalleri etkiliyor, yalnızca hedef büyüyor.

**4. Uzun kategori adında çarpı başlığın üstüne biniyordu.** Kapatma butonu mutlak konumlu; atama modalinin başlığına `pr-10` verildi. Genel `DialogHeader`'a dokunulmadı — mobilde başlıklar ortalı olduğu için global sağ dolgu metni sola kaydırırdı.

Ardından başlık düzeni bir tur daha değişti: "Kategori Adı — Hizmet Seç" biçimi hem uzun adlarda taşıyor hem de ortalamayı bozuyordu. Başlık sade "Hizmet Seç" oldu, kategori adı altına küçük punto ve etiket ikonuyla taşındı. Kısa başlık artık çarpıyla çakışmadığı için `pr-10` da kaldırıldı ve başlık gerçekten ortalandı.

---

## Faz 3 — Appointments Compound Index (tamamlandı, canlıda — 23 Ağustos 2026)

Planda iki index öngörülmüştü. Ölçüm, **birinin gereksiz, diğerinin sanılandan daha değerli** olduğunu gösterdi.

### Ölçümden önce: mevcut durum

`appointments` koleksiyonunda zaten sekiz index vardı. Planın ikinci maddesi olan `(organization_id, staff_member_id, appointment_date)` fiilen **zaten mevcut**, üstelik daha geniş hâliyle:

```
organization_id_1_staff_member_id_1_appointment_date_1_status_1
```

Bu index'in ilk üç alanı planda istenen index'in birebir aynısı; MongoDB bir index'in ön ekini bağımsız index gibi kullanabildiği için ayrıca oluşturmak yalnızca yazma maliyeti eklerdi. **Bu maddeyi uygulamadım.** Doğrulama olarak personel + tek gün çakışma sorgusu ölçüldü: bu index'i seçiyor ve 0 doküman tarıyor.

### Asıl sorun: `GET /api/appointments` her seferinde bellekte sıralıyordu

Endpoint `sort([appointment_date:1, appointment_time:1, id:1])` ile çalışıyor. Mevcut `(organization_id, appointment_date: -1)` index'i **azalan** olduğu ve üç alanlı sıralamayı karşılamadığı için planlayıcı şunu yapıyordu: organizasyonun tüm randevularını index'ten oku, hepsini belleğe al, orada sırala, sonra ilk 50'sini ver.

Yani `limit=50` göndermenin hiçbir faydası yoktu — sayfalama için yazılan cursor mekanizması, sıralama yüzünden her istekte tüm koleksiyonu okuyordu.

En büyük organizasyonda (399 randevu) ölçüm:

| Sorgu | Öncesi | Sonrası |
|---|---|---|
| Cursor sayfalama (limit 51) | 400 key / 399 doc okundu, bellekte SORT, 25 ms | **51 key / 51 doc**, sort yok, 4 ms |
| Legacy (limitsiz) | 400 key / 399 doc, bellekte SORT, 17 ms | 399 key / 399 doc, **sort yok**, 4 ms |
| Tarih aralığı + sıralama | (aynı SORT sorunu) | 51 key / 51 doc, sort yok, 2 ms |

Kritik olan milisaniyeler değil — 399 dokümanlık bir koleksiyonda zaten hiçbir şey yavaş değil. Kritik olan **okunan doküman sayısının artık dönen sayıya eşit olması**. Önceki davranışta maliyet organizasyonun toplam randevu sayısıyla büyüyordu; 10.000 randevulu bir işletmede aynı istek 10.000 doküman okuyup belleğe alacaktı. Artık 50 okuyor. Bu, bugünü hızlandıran değil, gelecekteki bir duvarı kaldıran bir değişiklik.

### Eklenen index

```
appointments_org_date_time_id
(organization_id: 1, appointment_date: 1, appointment_time: 1, id: 1)
```

Hem canlı veritabanına doğrudan oluşturuldu hem de `server.py` başlangıç adımına eklendi (Step 5), böylece yeni ortamlar ve temiz kurulumlar da alıyor. Oluşturma `try/except` içinde ve hata durumu DEBUG seviyesinde loglanıyor — diğer index'lerdeki desenin aynısı.

### Gerileme kontrolü

Index eklemenin sinsi riski, planlayıcının başka sorgularda yanlışlıkla yeni index'e kayması. Altı yaygın sorgu şekli index sonrası tekrar ölçüldü:

| Sorgu | Seçilen index | Sonuç |
|---|---|---|
| Dashboard: bugün + Bekliyor | `org_status_date` | değişmedi |
| Dashboard: status + tarih aralığı | `org_status_date` | 75 doc, tam isabet |
| İstatistik: tarih aralığı | `org_date_-1` | değişmedi |
| Hatırlatıcı job | `org_status` | değişmedi |
| Müşteri geçmişi (telefon) | `org_phone` | değişmedi |
| CSV export (tarihe azalan) | `org_date_-1` | değişmedi |

Hiçbirinde COLLSCAN, yeni bellekte sıralama veya index değişimi yok. **Not:** eski azalan index `(org, appointment_date: -1)` hâlâ gerekli — CSV export ve müşteri geçmişi gibi *azalan* sıralamalar onu kullanıyor, yeni artan index bunları karşılayamaz. Bu yüzden silinmedi.

### Yan gözlem (aksiyon alınmadı)

`organization_id_1_staff_member_id_1` index'i, dört alanlı `organization_id_1_staff_member_id_1_appointment_date_1_status_1` index'inin ön ekidir; teknik olarak gereksiz. 634 dokümanlık koleksiyonda yazma maliyeti ölçülemeyecek kadar küçük olduğu için dokunmadım. Index silmek geri alınabilir ama üretimde ölçülebilir bir fayda vermeden risk almanın anlamı yok. Koleksiyon büyürse tekrar bakılabilir.

### Dokunulan dosyalar

| Dosya | Değişiklik |
|---|---|
| `backend/server.py` | Step 5'e tek index oluşturma bloğu (13 satır) |

Endpoint, response modeli, sorgu mantığı veya iş kuralı **hiç değişmedi**. Bu faz tamamen veritabanı seviyesinde.

### Doğrulama

| Kontrol | Sonuç |
|---|---|
| Sözdizimi (`ast.parse`) | geçti |
| Contract testleri | 13 passed |
| Backend build + deploy | başarılı |
| Container | `Up (healthy)` |
| Startup index logu | `Step 5 SUCCESS` (17 worker) |
| `/api/health` | HTTP 200 |
| `/api/appointments?limit=50` | HTTP 401 (tokensiz — beklenen) |

### Geri alma

Tek komut, veri kaybı yok:

```js
db.appointments.dropIndex("appointments_org_date_time_id")
```

Ayrıca `server.py`'deki bloğun kaldırılması gerekir, aksi hâlde bir sonraki restart index'i yeniden kurar.

### Fatih'in manuel test edeceği noktalar

1. Randevular listesini aç, aşağı kaydırarak birkaç sayfa yükle → sıralama bozulmamalı, tekrar eden veya atlanan randevu olmamalı.
2. Tarih aralığı filtresi uygula → sonuçlar doğru ve tarihe göre sıralı gelmeli.
3. Personel filtresi + "atanmamış" seçeneği → liste doğru gelmeli.
4. Randevularda arama yap (isim/telefon) → sonuçlar dönmeli.
5. Takvim haftalık ve aylık görünüm → randevular yerli yerinde olmalı.

### Faz 3 ölçek doğrulaması — k6 large profili (23 Ağustos 2026, 23:39)

Index canlıdayken 10.000 müşteri / 100.000 randevuluk izole sentetik organizasyona 100 eşzamanlı
kullanıcıyla yük bindirildi. Tam analiz: `Root Dosyaları/k6_faz3_analiz_raporu.md`.

**Sonuç: 3.568 istek, sıfır hata, ortanca 164 ms.** Sayfalanmış uçlar ölçekte sağlam:

| Uç | p95 |
|---|---|
| `/appointments?limit=30` | 418 ms |
| `/customers?limit=30` | 387 ms |
| `/stats/dashboard` | 374 ms |
| `/services` | 314 ms |
| `/appointments` (legacy, limitsiz) | **6,42 sn** |
| `/customers` (legacy, limitsiz) | **12,78 sn** |

Aynı uç, aynı veri; tek fark `limit` parametresi → randevularda 15 kat, müşterilerde 33 kat.
Genel `p(95)<2000` eşiği kaldı, ama bunun tamamı iki legacy uçtan geliyor; onlar dışlandığında
en kötü p95 897 ms.

**Dürüstlük notu:** Bu, index öncesi/sonrası kontrollü karşılaştırma değil. 7 Ağustos'taki large
koşusu geçerli bir taban değil, çünkü o koşuda 31.078 isteğin **tamamı hata döndü** (MongoDB OOM
ile ölmüştü). Oradaki "42 ms" hızlı yanıt değil, hızlı hata. İki koşuyu yan yana koyup hızlanma
oranı iddia etmedim. Kesin kanıt isteniyorsa sentetik veri tekrar seed edilip aynı sorgu bir kez
normal, bir kez eski index'e `hint` verilerek `explain()` edilebilir — birkaç dakikalık iş.

**Testin ortaya çıkardığı asıl konu (Faz 3 kapsamı dışı):** `server.py`'deki legacy `/customers`
bloğunun yorumu "yeni web zaten sayfalı yolu kullanıyor" diyor, ama bu artık doğru değil. Web
arayüzü dört yerde hâlâ limitsiz çağırıyor:

- `App.js:630` — açılıştaki ana randevu yüklemesi, k6'nın ölçtüğü 6,42 sn'lik çağrının aynısı
- `AppointmentFormWizard.js:411`, `AppointmentForm.js:134`, `PaymentRequestDrawer.js:87` — tüm müşteri listesi (12,78 sn)

Uçların kendisi donmuş sözleşme (mağazadaki build'ler limitsiz çağırıyor), o yüzden **ucu değil
çağıranı** düzeltmek gerekiyor. Frontend-only, sözleşmeye dokunmayan ayrı bir faz olarak
değerlendirilmeli.

**Altyapı:** MongoDB testi atlattı (4 gün uptime, 0 restart) — 7 Ağustos'taki OOM tekrarlamadı.
Sentetik veri teardown edilmiş, prod dokunulmamış (639 randevu). Tek uyarı: test sonrası swap
tamamen dolu; `run_profiles.sh`'deki `ALLOW_LARGE=1` kilidi yerinde kalmalı.

### Faz 3 takibi — legacy çağıranların temizliği (23 Ağustos 2026, canlıda)

Yük testinin işaret ettiği legacy çağıranlar düzeltildi. Bu iş sırasında **latent bir doğruluk
hatası** çıktı; asıl önemli kısım o.

**Bulunan hata:** `/appointments` limitsiz çağrıldığında backend tarihe ARTAN sıralayıp ilk 1000
kaydı döndürüyor — yani **en eski 1000 randevu**. Dashboard ise yalnızca bugün ve sonrasını
okuyor. Yani **randevu sayısı 1000'i geçen ilk işletmede panelin "Bugün" listesi boşalacaktı.**
Yavaşlık değil, veri kaybı. Bugün görünmüyor çünkü en büyük org'da 399 randevu var; ama zamanla
kendiliğinden tetiklenecekti. Yük testi olmasa fark edilmezdi.

**Yapılanlar:**

| Yer | Önce | Sonra |
|---|---|---|
| `App.js` açılış | `/appointments` (en eski 1000, ölçekte 6,4 sn) | `?start_date=<bugün-7g>` + `?session_only=true`, paralel + id ile tekilleştirme |
| `AppointmentFormWizard` | tüm müşteri listesi (12,8 sn) | `?limit=30&search=` + cursor ile sonsuz kaydırma |
| `PaymentRequestDrawer` | tüm müşteri listesi (12,8 sn) | `?limit=50&search=`, 200 ms debounce |
| `AppointmentForm` import | ölü kod (hiç render edilmiyordu) | kaldırıldı, paket 1,7 kB küçüldü |

**Backend:** `GET /appointments`'a opsiyonel `session_only` parametresi eklendi. Seans ekranının
"Tamamlanan" sekmesi geçmişe bakmak zorunda olduğu için tarih penceresine sığmıyordu; bu filtre
o küçük kümeyi ayrıca çekmeyi sağlıyor. Parametre gönderilmezse davranış **birebir eskisi** —
sözleşme kuralı §5'e uygun additive değişiklik. Legacy uçların kendisine dokunulmadı.

Dashboard, bildirimler, `SessionsHub` ve "aktif seans var mı" kontrolü aynı `appointments`
prop'unu görmeye devam ediyor; tüketici bileşenlerde değişiklik gerekmedi.

**Doğrulama:** `session_only` filtresi izole geçici bir organizasyonla test edildi (2 randevudan
seans paketi olan 1'i döndü — geçti, geçici veri hemen silindi). Contract testleri 13/13,
frontend build temiz, backend + frontend deploy healthy, canlı bundle `main.776fe023.js` içinde
yeni çağrılar doğrulandı. Prod verisine dokunulmadı.

**Açık kalanlar:** legacy uçlara client telemetrisi (hangi sürüm parametresiz çağırıyor) ve
k6'da uç bazlı eşikler. İkisi de acil değil.

### Not — `session_only` açılış maliyeti (24 Ağustos 2026, henüz işlenmedi)

Panel profili k6'da (legacy uçlar çıkarılmış, 100k randevu / 100 VU) asıl pencere çağrısı p95
**623 ms** oldu. Genel `p(95)<2000` yine kaldı (**7,55 sn**); suçlu `/appointments?session_only=true`
(**p95 10,8 sn**).

Neden: tarih filtresi yok, `session_group_id` index'i yok. Seed'de hiç seans paketi yoktu; her istek
yine org'un 100k kaydını tarıyor. `App.js` bunu açılışta `start_date` penceresiyle **paralel** atıyor
— Seanslar sekmesi ve "aktif paket var mı" kontrolü için geçmiş paketler tarih penceresine sığmıyor.

Konuşulacak seçenekler (yapılmadı):
1. `(organization_id, session_group_id)` sparse index — tarama biter, çağrı durur.
2. Paketsiz org'da isteği atlamak — frontend'in bunu bilebilmesi lazım (flag veya hafif count ucu).
3. `session_only`'yi dashboard açılışından çıkarıp Seanslar ekranına ertelemek — nav rozeti gecikebilir.

Karar verilmeden kod yok. OTA **6.3.4** production'da (internal da aynı).

## Faz 12 — Mobil içi paket seçimi + Stripe Checkout (In-App Browser)

**Durum:** kod yazıldı, Internal OTA bekleniyor (24 Ağustos 2026). Production / Apple review kapalı.

Kod:
- Flag `SHOW_IN_APP_SUBSCRIBE = true` + native'de Capgo kanalı `internal` zorunlu (`production` fail-closed).
- `PlanPicker.js`, `lib/inAppSubscribe.js` (Browser + browserFinished + confirm/plan poll).
- Native success_url `plannapp://payment-success?session_id={CHECKOUT_SESSION_ID}`, cancel `plannapp://subscribe`.
- Production OTA **6.3.4** değişmedi; internal test bundle ayrı yüklenecek (promote yok).

### Neden

Native'de abonelik satın alma siteye (`plannapp.co` / SSO) atılıyor. Kullanıcı uygulamadan çıkıyor, menülerde kayboluyor, şifre sıfırlama döngüsüne giriyor. Strateji: paket seçimi uygulama içinde, kart yalnızca Stripe'ın hosted Checkout'unda.

### Mevcut durum (kodla doğrulandı)

Backend — yeni endpoint gerekmez:

- `POST /api/payments/create-checkout-session` ([backend/server.py](backend/server.py):8506) JWT + `admin`, `PlanUpdateRequest`: `plan_id` zorunlu; `billing_cycle`, `platform`, `currency` opsiyonel. Stripe `mode=subscription`, lookup key (`{plan}_{cycle}_{currency}`), ilk-ay kuponu, `payment_logs` pending. Yanıt: `{ checkout_url, session_id }` — frozen contract, şekil değişmez.
- `platform` `ios`/`android` ise `success_url = plannapp://payment-success` (session_id yok), `cancel_url = plannapp://dashboard`.
- `POST /api/payments/confirm-checkout-session` webhook gecikmesine karşı yedek; native başarı URL'inde session_id olmadığı için bugün native bu ucu çağırmıyor — aktivasyon `checkout.session.completed` webhook'una bağlı.
- Merchant checkout (`financial/merchant_checkout.py`) müşteri ödemesi; bu fazın konusu değil (SaaS abonelik).

Frontend — native'de paket seçici bilinçli kapalı:

- [Subscribe.js](frontend/src/components/Subscribe.js): `Capacitor.isNativePlatform()` → "siteye git" kartı (`openWebsiteSubscribe` + SSO). Web yolu zaten `create-checkout-session` + plan kartları.
- [SettingsSubscription.js](frontend/src/components/SettingsSubscription.js): native'de "plan değiştir" yok, aynı siteye git CTA.
- Native checkout bugün `openExternalUrl` → **sistem tarayıcısı** (Safari/Chrome). `Subscribe.js` içinde `Browser.addListener` var ama `Browser` import edilmemiş ve native early-return yüzünden ölü kod.

Altyapı hazır:

- `@capacitor/browser` 7.0.2 `package.json`'da, iOS `Podfile` `CapacitorBrowser`, Android `capacitor.plugins.json` kayıtlı. JS OTA yeter (native 6.3 binary'sinde plugin yoksa `Browser.open` patlar — cihazda bir kez doğrulanır).
- URL scheme `plannapp://` Info.plist + Android intent-filter'da. Associated domains (`applinks:plannapp.co`) entitlements'ta; mağaza binary'sine henüz girmemiş olabilir (önceki not).
- [App.js](frontend/src/App.js): `appUrlOpen` `payment-success` → toast + dashboard; `confirm-checkout-session` yalnızca web hash yolunda.

### Hedef akış

```mermaid
sequenceDiagram
  participant User
  participant App as PlanPicker (native)
  participant API as FastAPI
  participant Stripe
  participant Browser as Capacitor Browser

  User->>App: Paket seç (aylık/yıllık)
  App->>API: POST /payments/create-checkout-session
  API->>Stripe: Session.create (subscription)
  Stripe-->>API: session.url
  API-->>App: checkout_url, session_id
  App->>Browser: Browser.open(checkout_url)
  User->>Stripe: Kartı Checkout formunda gir
  Stripe->>App: plannapp://payment-success?session_id=...
  App->>Browser: Browser.close()
  App->>API: POST /payments/confirm-checkout-session
  Note over API,Stripe: webhook checkout.session.completed zaten planı yazar
```

Kart asla Capacitor WebView içinde alınmaz (PCI + Apple). In-App Browser = iOS SFSafariViewController / Android Chrome Custom Tabs.

### Kod planı (onay sonrası, bu sırayla)

1. **Feature flag** — [frontend/src/constants/uiFlags.js](frontend/src/constants/uiFlags.js) içine `SHOW_IN_APP_SUBSCRIBE = false`. Apple reviewer production bundle'da eski "siteye git" görür. Internal Capgo kanalında `true` ile test. Production OTA'da flag açmak ayrı onay (review riski). Backend env/DB flag yok: UI JS bundle'da, Apple'ın gördüğü şey kanal + OTA.

2. **`PlanPicker` bileşeni** — [Subscribe.js](frontend/src/components/Subscribe.js) içindeki web plan kartları (aylık/yıllık toggle, `GET /plans` + `GET /plan/current`, `PRICING_DISPLAY`, i18n) yeni `frontend/src/components/PlanPicker.js`'e çıkarılır. Web `Subscribe.js` aynı UI'ı kullanır (davranış değişmez). Native: flag kapalı → mevcut compliance kartı; flag açık → `PlanPicker`. Ayrı kopya fiyat UI'ı yok.

3. **Checkout tetikleme** — `handleStartSubscription` mevcut body'yi korur: `{ plan_id, billing_cycle, platform: ios|android, currency }`. Native + flag: `import { Browser } from '@capacitor/browser'` → `Browser.open({ url: checkout_url, presentationStyle: 'fullscreen' })`. `openExternalUrl` / `openWebsiteSubscribe` bu yolda kullanılmaz. Web: `window.location.href` aynı kalır.

4. **Settings girişi** — [SettingsSubscription.js](frontend/src/components/SettingsSubscription.js): flag açıkken "Plan değiştir" → `onNavigate('subscribe')`. Stripe Customer Portal (`POST /subscription/portal`) native'de de `Browser.open(portal_url)` — aynı sürtünme. Flag kapalıyken siteye git durur.

5. **Dönüş (üç katman, SFSafariViewController custom scheme'i yutabilir)**
   - Backend (küçük, contract dışı URL string): native `success_url` → `plannapp://payment-success?session_id={CHECKOUT_SESSION_ID}`; native `cancel_url` → `plannapp://subscribe` (dashboard yerine paket ekranı). Response JSON değişmez.
   - [App.js](frontend/src/App.js) `appUrlOpen`: `payment-success` → `Browser.close()`, session_id varsa `confirm-checkout-session` (org uyumu zaten backend'de), `loadStats`, subscribe/dashboard, toast. Cancel → `Browser.close()`, subscribe'da kal.
   - `browserFinished` + kısa `GET /plan/current` poll (ör. 3×1.5 sn): kullanıcı Done ile kapatırsa veya scheme açılmazsa webhook yine planı yazar, UI yakalar.

6. **i18n** — yeni metin yoksa mevcut `settings.subscribePage` / `landing.pricing` yeterli. Native'de "Güvenli ödeme — Stripe" zaten var. Gerekirse tek satır: tarayıcı kapandıktan sonra "Abonelik güncelleniyor…".

7. **Kapsam dışı (bilinçli)**
   - Yeni FastAPI endpoint yok; IAP / StoreKit yok; PayTR native yok; Faz 4 billing state machine yok.
   - Stripe.js Capacitor WebView'e gömülmez.
   - `create-checkout-session` response şekli değişmez (alan silme/rename yok).
   - Mağaza versionCode bump yok — plugin native 6.3'te yoksa o zaman store; associated-domain HTTPS dönüşü sonraki store'a bırakılabilir (scheme yeterli varsayımı, cihazda doğrulanır).

### Test planı (onay + kod sonrası)

- Flag `false`: native hâlâ siteye gider (Apple reviewer yolu).
- Flag `true` / Capgo internal: paket seç → In-App Browser Stripe test kartı → uygulama içine dönüş → plan `GET /plan/current` ile güncel.
- İptal / Browser Done: subscribe'da kalır, şifre sıfırlama yok, login kaybolmaz.
- Web subscribe + checkout birebir aynı (regresyon).
- Contract: `python -m pytest tests/integration/ -q` (request'e zorunlu alan eklenmez).
- Cihaz: iOS + Android'de `Browser.open` unimplemented değil.

### Risk notu — Apple 3.1.1

Mevcut gizleme App Store yorumunun savunmacı hali. Yeni akış Guideline 3.1.3(b) multiplatform (web'de de satılan SaaS) + ödeme Safari/Custom Tabs'ta. Flag kapalı default bu riski review'dan ayırır. Flag production'da açılmadan legal/review kararı ayrıca.