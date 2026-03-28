# Seans (Session Package) Takibi — Final Plan

Randevulara seans paketi desteği ekler: hizmet bazlı seans tanımı, public'ten ilk seans alımı, admin/personel tarafında 2-3 tıkla kalan seansları planlama (akıllı çakışma çözümü ile), takvimde 2/7 badge ve müşteri profilinde seans geçmişi.

---

## Yetki Matrisi

| Eylem | Admin | Personel | Müşteri (Public) |
|-------|-------|----------|------------------|
| Seans hizmeti tanımlama | ✅ | ❌ | ❌ |
| Sıfırdan seans paketi oluşturma | ✅ | ✅ (kendi hizmetleri) | ❌ |
| İlk seansı alma (public) | — | — | ✅ (tek seans) |
| Kalan seansları planlama | ✅ | ✅ (kendi randevuları) | ❌ |
| Seans badge görme (takvim) | ✅ | ✅ | ❌ |
| Seans geçmişi görme (müşteri kartı) | ✅ | ✅ (kendi müşterileri) | ❌ |
| Seans hatırlatma alma (WhatsApp) | — | — | ✅ (her seans) |

---

## Faz 1 — Backend: Model Alanları
**Dosya:** `backend/server.py`

### Service / ServiceCreate / ServiceUpdate
- `session_count: Optional[int] = None` alanı eklenir
- `None` = tekli randevu, `7` = 7 seanslık paket

### Appointment
- `session_group_id: Optional[str] = None` — aynı paketteki tüm seanslarda ortak UUID
- `session_number: Optional[int] = None` — bu seansın sırası (1, 2, 3...)
- `session_total: Optional[int] = None` — paketteki toplam seans sayısı
- `payment_status: Optional[str] = None` — `"paid"` (1. seans, tam fiyat) veya `"package_included"` (kalan seanslar, fiyat 0)

> **Muhasebe Kuralı:** Seans paketlerinde ödeme 1. seansta (tam fiyat) kaydedilir. Kalan seanslar `service_price: 0` + `payment_status: "package_included"` ile oluşturulur. Dashboard ciro hesapları bu sayede doğru kalır.

### AppointmentCreate / AppointmentUpdate
- Aynı 3 alan opsiyonel olarak eklenir

> **Not:** `backend/app/api/schemas/` altındaki modüler şemalar da güncellenir (appointment.py, service.py) tutarlılık için; ancak aktif API `server.py` üzerinden çalışıyor.

---

## Faz 2 — Backend: Endpoint'ler
**Dosya:** `backend/server.py`

### 2a — BulkSessionCreate modeli
```python
class SessionSlot(BaseModel):
    date: str   # "2026-04-01"
    time: str   # "10:00"

class BulkSessionCreate(BaseModel):
    customer_name: str
    phone: str
    service_id: str
    staff_member_id: Optional[str] = None
    notes: str = ""
    session_group_id: Optional[str] = None   # Mevcut gruba ekleme (kalan seanslar)
    starting_session_number: int = 1          # Kalan seanslar için başlangıç numarası
    session_total: Optional[int] = None       # Override: None ise len(sessions) kullanılır
    sessions: list[SessionSlot]
```

### 2b — `POST /api/appointments/bulk-session`
1. Hizmet & personel doğrulama (personel ise kendi hizmet yetki kontrolü)
2. Her seans için mevcut `create_appointment` mantığındaki **çakışma + mola kontrolü**
3. Tüm seanslara aynı `session_group_id` (UUID), `session_number` `starting_session_number`'dan başlar
4. **Fiyatlandırma**: İlk seans (`session_number=1`) → tam fiyat + `payment_status: "paid"`. Kalan seanslar → `service_price: 0` + `payment_status: "package_included"`
5. **Kota**: toplam seans sayısı kadar `quota_usage` artırılır
6. **Atomik**: tek hata tüm işlemi durdurur, oluşturulan randevular ve kota geri alınır
7. **Redis lock**: her seans için ayrı lock key
8. **Müşteri kaydı**: ilk seansta `customers` upsert
9. **WebSocket emit**: tek bir `appointments_bulk_created` event
10. **WhatsApp**: Tüm seanslar başarılı olduktan sonra tek bir onay mesajı (graceful fallback)

### 2c — `POST /api/availability/bulk-check`
Seans planlama UI'ı için: birden fazla tarih/saat'in müsaitliğini tek seferde kontrol eder. **POST kullanılır** — 20+ seanslık paketlerde URL uzunluk limiti (414 URI Too Long) riski önlenir.
```json
POST /api/availability/bulk-check
{
  "service_id": "X",
  "staff_id": "Y",
  "slots": ["2026-04-01T10:00", "2026-04-08T10:00", ...]
}
```
Response: her slot için `{ date, time, available: true/false, alternatives: ["10:30","11:00"] }`

### 2d — `POST /api/appointments/session-group/{group_id}/cancel-remaining`
Bir seans grubundaki **tarihi henüz gelmemiş** tüm randevuları toplu olarak `status: "İptal Edildi"` yapar.
- Sadece `appointment_date >= today` olanları iptal eder (geçmiş seanslar korunur)
- Kota geri iadesi: iptal edilen seans sayısı kadar `quota_usage` düşürülür
- WebSocket + cache invalidation
- Admin ve personel (kendi randevuları) kullanabilir

### 2e — Seans tarih/saat düzenleme
Mevcut `PUT /api/appointments/{id}` endpoint'i zaten tarih/saat düzenlemeyi destekliyor. Ek olarak:
- Seans randevusu düzenlenirken çakışma kontrolü uygulanır
- `payment_status` ve `session_*` alanları korunur (düzenleme ile değiştirilemez)

### 2f — Public appointment'ta seans desteği
Mevcut `POST /api/public/appointments` endpoint'ine ekleme:
- Eğer seçilen hizmetin `session_count > 1` varsa, oluşturulan randevuya otomatik olarak:
  - `session_group_id` = yeni UUID
  - `session_number` = 1
  - `session_total` = service.session_count
- Güvenlik katmanları **değişmez** (tek randevu akışı)
- Response'a `session_info: { group_id, number: 1, total: 7 }` eklenir

---

## Faz 3 — Frontend: ServiceManagement.js
**Dosya:** `frontend/src/components/ServiceManagement.js`

### Toggle + Şartlı Görünüm (Conditional Rendering)
Doğrudan sayı input'u göstermek yerine **Toggle** kullanılır — sıfır kafa karışıklığı:

**Varsayılan (kapalı):**
```
[ Kapalı ]  Bu hizmet bir seans paketi mi?
```
→ Altında hiçbir kutu yok. Backend'e `session_count: null` gider.

**Aktif (açık):**
```
[  Açık  ]  Bu hizmet bir seans paketi mi?
             Kaç Seans: [ 7 ]    ← fade-in animasyonla açılır, min=2
```
→ Backend'e `session_count: 7` gider.

### Uygulama detayları:
- `formData` state'ine `isSessionPackage: false` + `session_count: 2` eklenir
- Toggle kapalıysa payload'a `session_count: null`, açıksa `session_count: parseInt(value)` gider
- Sayı input'u `min=2`, `max=50` — "0" veya "1" seanslık absürt paketler imkansız
- Düzenleme modunda: mevcut hizmetin `session_count > 1` ise toggle açık + değer dolu gelir
- Hizmet kartında seans sayısı varsa küçük pill badge gösterilir (örn: "7 seans")
- Toggle: shadcn/ui `Switch` bileşeni, glassmorphism stiliyle uyumlu

---

## Faz 4 — Frontend: PublicBookingPage.js (Seans Bilgilendirme)
**Dosya:** `frontend/src/components/PublicBookingPage.js`

**Yaklaşım B — Müşteri sadece ilk seansı alır, güvenlik sistemi değişmez.**

- **Step 1 (Hizmet kartı)**: `session_count` varsa badge → `"7 Seanslık Paket"`
- **Step 4 (Onay özeti)**: Seans hizmeti seçildiyse bilgilendirme kutusu:
  > "Bu hizmet 7 seanslık bir pakettir. İlk seans randevunuz oluşturulacak, kalan seanslar işletme tarafından planlanacaktır."
- **Başarı ekranı**: "İlk seansınız oluşturuldu! Kalan seanslarınız işletme tarafından planlanacaktır."
- `handleSubmit` **değişmez** — backend otomatik olarak `session_group_id/number/total` ekler

---

## Faz 5 — Frontend: Seans Planlama UI (Admin + Personel)
**Dosyalar:** `AppointmentFormWizard.js`, `AppointmentForm.js` + yeni `SessionPlannerDialog.js`

### 5a — Yeni seans oluşturma (sıfırdan, AppointmentFormWizard'dan)
Hizmet seçildiğinde `service.session_count > 1` ise form **"Seans Paketi Oluştur"** moduna geçer:

#### İki Sekme (Tab):
| Otomatik | Manuel |
|----------|--------|
| Başlangıç tarihi + saat | N adet tarih/saat satırı (tek tek) |
| Aralık: Haftada 1 / 2 Haftada 1 / X gün | Her satırda tarih seçici + saat seçici |
| Sistem tarihleri öneri olarak üretir | Kullanıcı serbestçe düzenler |

Önizleme tablosunun üstünde **aynı sabit bilgi kutusu** (inline alert) gösterilir — bkz. 5b.

Kaydet → `POST /api/appointments/bulk-session`

### 5b — "Kalan Seansları Planla" (`SessionPlannerDialog.js`)
Ortak bileşen — Calendar ve Customers'dan açılır.

#### Giriş noktaları:
1. **Calendar.js** → Randevu detay dialog'unda **"Kalan Seansları Planla"** butonu
2. **Customers.js** → Seans geçmişinde **"Paketi Tamamla"** butonu

#### Sabit Bilgi Kutusu (Inline Alert):
Önizleme tablosunun **üstünde** sabit, her zaman görünür bir bilgi kutusu. Tooltip değil — salon ortamında dokunmatik tabletlerle kullanılacağı için sabit olmalı.

```
┌─ ℹ️ ──────────────────────────────────────────────────────┐
│ Sistem seans tarihlerinizi otomatik planladı.              │
│ Eğer ⚠️ sarı uyarı görüyorsanız, o günkü saatiniz        │
│ doludur. Yandaki alternatif saatlere tıklayarak hızlıca   │
│ düzeltebilir ve tüm seansları tek tuşla kaydedebilirsiniz.│
└───────────────────────────────────────────────────────────┘
```

Tasarım: `bg-blue-50 border border-blue-200 rounded-xl p-4` — mevcut app stiliyle uyumlu, bilgi ikonu ile.

#### Akıllı Çakışma Çözümü:
Dialog açıldığında sistem ilk seansın tarih/saatinden haftalık aralıkla kalan seansları üretir ve her biri için müsaitlik kontrol eder (`GET /api/availability/bulk-check`):

```
Seans 2:  8 Nisan  10:00  ✅ Müsait
Seans 3: 15 Nisan  10:00  ⚠️ Dolu → Öneri: 10:30, 11:00
Seans 4: 22 Nisan  10:00  ✅ Müsait
Seans 5: 29 Nisan  10:00  ⚠️ Dolu → Öneri: 09:30, 14:00
Seans 6:  6 Mayıs  10:00  ✅ Müsait
Seans 7: 13 Mayıs  10:00  ✅ Müsait
```

- **✅ Müsait**: Yeşil tik, dokunmaya gerek yok
- **⚠️ Dolu**: Sarı uyarı + aynı günden **en yakın müsait saatler** otomatik önerilir (pill butonlar, dokunmatik uyumlu)
- Admin/personel çakışan satırdaki alternatif saate **tek dokunuş** → slot güncellenir
- **Tümü müsait olana kadar "Hepsini Oluştur" butonu devre dışı** kalır

#### Otomatik doldurulmuş bilgiler:
- Müşteri adı, telefon, hizmet, personel → ilk seanstan kopyalanır (değiştirilemez)

#### Admin/Personel akışı (2-3 tık):
1. **1 tık**: "Kalan Seansları Planla" butonuna basar
2. **Bilgi kutusu okunur** — ne yapması gerektiğini anlar
3. **Göz gezdirme**: Çoğu yeşil ✅ — çakışanlar varsa önerilen saate dokunur
4. **1 tık**: "Hepsini Oluştur" → bitti ✅

---

## Faz 6 — Frontend: Calendar.js (Badge + Buton)
**Dosya:** `frontend/src/components/Calendar.js`

- Randevu kartlarında `session_number` ve `session_total` varsa küçük pill badge: **2/7** (mavi)
- Tüm view modlarda (day, week, list) eklenir
- Randevu detay dialog'unda:
  - Seans bilgisi gösterilir ("Seans 2/7")
  - Grupta eksik seans varsa **"Kalan Seansları Planla"** butonu → `SessionPlannerDialog` açar
- Badge kodu:
  ```jsx
  {apt.session_number && apt.session_total && (
    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full font-bold">
      {apt.session_number}/{apt.session_total}
    </span>
  )}
  ```

---

## Faz 7 — Frontend: Customers.js (Seans Geçmişi)
**Dosya:** `frontend/src/components/Customers.js`

Müşteri detay sayfasında mevcut randevu listesinin **üstüne** "Seans Paketleri" bölümü:

- `session_group_id`'ye göre gruplanmış kartlar
- Her kart: **Hizmet adı** + **3/7 tamamlandı** ilerleme çubuğu (progress bar)
- Mini timeline: Tamamlanan → yeşil ✓ / Bekleyen → gri ○ / İptal → kırmızı ✗
- Sadece müşteriye ait `session_group_id` olan randevular varsa gösterilir
- Eksik seansları olan paketlerde **"Paketi Tamamla"** butonu → `SessionPlannerDialog` açar
- Kalan bekleyen seanslar varsa **"Kalan Seansları İptal Et"** kırmızı buton → toplu iptal dialog'u (`POST /api/appointments/session-group/{group_id}/cancel-remaining`)
- Her seans satırında tarih/saat **düzenlenebilir** (kalem ikonu → mevcut `PUT /appointments/{id}` kullanılır, sadece gelecek tarihli seanslar)

---

## Faz 8 — Frontend: Aktif Randevu Göstergesi (Live Pulse)
**Dosya:** `frontend/src/components/Calendar.js`

Randevu saati geldiğinde, mevcut durum Badge'i (sağ üst köşe) otomatik olarak **"İşlemde"** durumuna geçer. Yeni UI elemanı eklenmez — var olan Badge dönüşür.

### Mantık:
- `appointment_time` + `service_duration` ile randevunun aktif olup olmadığı hesaplanır
- `getStatusCode()` fonksiyonuna `"active"` durumu eklenir
- Aktif randevu: `now >= start && now < end` (1 dakikalık `setInterval` ile güncellenir)

### Görünüm:
```
Bekliyor:   [Bekliyor]        ← turuncu badge (mevcut)
Aktif:      🟢 İşlemde        ← yeşil pulse nokta + metin (aynı Badge alanında)
Tamamlandı: [Tamamlandı]      ← yeşil badge (mevcut)
```

### Pulse animasyonu (CSS-only, Tailwind):
```jsx
<Badge className="text-xs flex-shrink-0 text-green-700 bg-green-50 border-green-200">
  <span className="relative flex h-2 w-2 mr-1.5">
    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
  </span>
  İşlemde
</Badge>
```

### Uygulama detayları:
- `useEffect` + `setInterval(60000)` ile her dakika aktif randevular kontrol edilir
- `service_duration` yoksa (eski randevular) → varsayılan 30dk
- Sadece **bugünün** randevuları kontrol edilir (performans)
- Tüm view modlarda (day, week, list, month) çalışır
- i18n: `appointments.status.active` → TR: "İşlemde", EN: "In Progress"

---

## Faz 9 — Müşteri İyileştirmeleri (Bug Fix + Yeni Özellikler)
**Dosyalar:** `backend/server.py`, `frontend/src/components/Customers.js`

### 9a — Cache Race Condition Fix (Bug)
**Sorun:** `create_appointment` ve `create_public_appointment` içinde `invalidate_cache("customers_list")` müşteri DB'ye eklenmeden ÖNCE çağrılıyor. Başka bir istek arada cache'i yeniden doldurursa, yeni müşteri 5dk (TTL=300) boyunca görünmüyor.

**Çözüm:** `invalidate_cache("customers_list")` çağrısını müşteri `insert_one()` satırının **SONRASINA** taşı. Her iki endpoint'te de:
- `server.py` satır ~4058 → satır ~4100 sonrasına
- `server.py` satır ~9792 → satır ~9826 sonrasına

### 9b — Müşteri Düzenleme (Yeni Özellik)
**Backend:**
- `PUT /api/customers/{phone}` endpoint'i eklenir
- Body: `{ name: str, phone: str }` (telefon değişirse eski telefondaki randevular da güncellenir)
- Cache invalidation dahil

**Frontend (Customers.js):**
- Müşteri detay sayfasında ad ve telefon alanları **düzenlenebilir** olur
- "Düzenle" butonu → inline edit mode veya edit dialog
- Kaydet → `PUT /api/customers/{phone}`
- Başarı sonrası müşteri listesi yenilenir

### 9c — A-Z Alfabetik Sıralama
**Backend (`server.py` satır ~7481):**
- Mevcut: `customers.sort(key=lambda x: x['total_appointments'], reverse=True)`
- Değişiklik: `customers.sort(key=lambda x: x['name'].lower())`

**Frontend (Customers.js):**
- `loadCustomers` sonrası sıralama garantisi (backend'den zaten sıralı gelecek)
- Opsiyonel: sıralama dropdown (A-Z / Randevu sayısı) — basit tutmak için varsayılan A-Z yeterli

---

## WhatsApp Mesajlaşma Kuralları

| Durum | Davranış |
|-------|----------|
| Public ilk seans | Mevcut `randevu_onay` şablonu (değişmez) |
| Admin/personel bulk-session | Tek bir onay mesajı (tüm seanslar listelenir) |
| Her seans hatırlatması | Mevcut scheduler aynen korunur (seans başına hatırlatma) |
| Tekli randevular | Değişiklik yok, mevcut şablonlar korunur |

Yeni şablon: `seans_paketi_onay` (Meta onayı gerekir). Şablon hazır olana kadar **graceful fallback** — gönderim başarısız olursa sadece log yazılır.

---

## Uygulama Sırası

| # | Adım | Dosya(lar) |
|---|------|-----------|
| 1 | Model alanları (`payment_status` dahil) | `server.py` + `app/api/schemas/*.py` |
| 2 | bulk-session + bulk-check (POST) + cancel-remaining + public endpoint | `server.py` |
| 3 | Müşteri cache fix + düzenleme endpoint + A-Z sıralama | `server.py` |
| 4 | ServiceManagement: session_count | `ServiceManagement.js` |
| 5 | PublicBookingPage: seans bilgilendirme | `PublicBookingPage.js` |
| 6 | SessionPlannerDialog: akıllı çakışma çözümlü seans planlama | yeni `SessionPlannerDialog.js` |
| 7 | AppointmentFormWizard: seans modu (sıfırdan paket) | `AppointmentFormWizard.js` + `AppointmentForm.js` |
| 8 | Calendar: seans badge + kalan seanslar butonu + aktif randevu pulse | `Calendar.js` |
| 9 | Customers: seans geçmişi + paketi tamamla + toplu iptal + seans düzenleme + müşteri düzenleme + A-Z | `Customers.js` |
| 10 | i18n çevirileri (TR/EN) | `locales/*.json` |
| 11 | Docker rebuild + test | — |

---

## Dikkat Edilecekler

- **Glassmorphism UI**: Tüm frontend değişiklikleri mevcut tasarım diline uygun olacak: `backdrop-blur-xl`, `bg-white/40`, `border border-white/20`, `rounded-2xl`, `shadow-lg`, gradient arkaplanlar. Yeni dialog/bileşenler bu stili takip eder.
- **Geriye uyumluluk**: Mevcut tekli randevular etkilenmez (tüm yeni alanlar `Optional`)
- **Public güvenlik**: 5 katman güvenlik sistemi **değişmez** — public'te sadece tek randevu akışı
- **Admin/Personel UX**: "Kalan Seansları Planla" **2-3 tıkla** tamamlanır (akıllı çakışma çözümü)
- **Personel yetkisi**: Personel kendi hizmetleri kapsamında seans paketi oluşturabilir, kendi randevularının kalan seanslarını planlayabilir
- **Çakışma çözümü**: Dolu slotlara sarı uyarı + aynı günden en yakın müsait saat alternatifleri. Tümü müsait olana kadar kayıt butonu devre dışı
- **Kota yönetimi**: Bulk endpoint'te atomik kota artırımı/geri alma
- **Redis lock**: Her seans slotu için ayrı lock
- **i18n**: Tüm yeni UI metinleri TR/EN çeviri dosyalarına eklenir
- **server.py satır yoğunluğu**: ~11K satır, değişiklikler mevcut stil ile uyumlu olacak (tek satır model tanımları vb.)
