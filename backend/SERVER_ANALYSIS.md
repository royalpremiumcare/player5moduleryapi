# PLANN Backend — Kapsamlı Sistem Analiz Dokümantasyonu

## 📋 İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Mimari ve Teknoloji Yığını](#mimari-ve-teknoloji-yığını)
3. [Başlangıç ve Yaşam Döngüsü](#başlangıç-ve-yaşam-döngüsü)
4. [Güvenlik ve Kimlik Doğrulama](#güvenlik-ve-kimlik-doğrulama)
5. [Veri Modelleri](#veri-modelleri)
6. [Randevu Durumları ve Yaşam Döngüsü](#randevu-durumları-ve-yaşam-döngüsü)
7. [Seans Paketi Sistemi](#seans-paketi-sistemi)
8. [Online Ödeme Sistemi (Stripe Merchant Checkout)](#online-ödeme-sistemi)
9. [Ödeme Bekleniyor Akışı](#ödeme-bekleniyor-akışı)
10. [Cüzdan (Wallet) Sistemi](#cüzdan-wallet-sistemi)
11. [İade (Refund) Sistemi](#iade-refund-sistemi)
12. [WhatsApp Bildirim Sistemi](#whatsapp-bildirim-sistemi)
13. [API Endpoint'leri](#api-endpointleri)
14. [WebSocket ve Real-Time İletişim](#websocket-ve-real-time-iletişim)
15. [Push Notification Sistemi](#push-notification-sistemi)
16. [E-posta Entegrasyonu](#e-posta-entegrasyonu)
17. [Kota ve Abonelik Yönetimi](#kota-ve-abonelik-yönetimi)
18. [SaaS Abonelik Ödeme (Stripe Subscription)](#saas-abonelik-ödeme)
19. [Müsaitlik Hesaplama](#müsaitlik-hesaplama)
20. [Finans ve Kasa Yönetimi](#finans-ve-kasa-yönetimi)
21. [Personel Yönetimi](#personel-yönetimi)
22. [Müşteri Yönetimi](#müşteri-yönetimi)
23. [AI Entegrasyonu](#ai-entegrasyonu)
24. [Zamanlanmış Görevler (Cron Jobs)](#zamanlanmış-görevler)
25. [Yardımcı Fonksiyonlar](#yardımcı-fonksiyonlar)

---

## 🎯 Genel Bakış

PLANN, multi-tenant (çok kiracılı) randevu, müşteri yönetimi ve ödeme altyapısı sunan SaaS platformudur. Backend, FastAPI tabanlı monolitik bir uygulama (`server.py`, ~12.500+ satır) ve modüler `financial/` paketiyle çalışır. Sistem Türkiye (TRY) ve İngiltere (GBP) pazarlarına çift para birimi desteğiyle hizmet verir.

**Temel Özellikler:**
- Multi-tenant SaaS mimarisi (`organization_id` izolasyonu)
- JWT tabanlı kimlik doğrulama (admin, staff, superadmin, marketing rolleri)
- Real-time güncellemeler (Socket.IO + Redis pub/sub)
- WhatsApp bildirim sistemi (Meta Cloud API, çoklu template)
- **Seans paketi sistemi** (toplu randevu oluşturma ve yönetimi)
- **Online ödeme sistemi** (Stripe Merchant Checkout, merchant cüzdanı, payout)
- **"Ödeme Bekleniyor" akışı** (ödeme tamamlanana kadar randevu görünmez)
- **İade sistemi** (tekil ve orantılı seans grubu iadesi)
- Dinamik müsaitlik hesaplama (15dk aralıklı slot sistemi)
- AI asistan (Gemini) ve Voice AI desteği
- Push notification (Web Push VAPID + Firebase Cloud Messaging)
- Stripe SaaS abonelik + PayTR (TR) abonelik ödeme
- Finans modülü (gelir/gider/personel hakediş)
- CSV/Excel export

---

## 🏗️ Mimari ve Teknoloji Yığını

### Kullanılan Teknolojiler

| Teknoloji | Kütüphane / Araç | Kullanım Amacı |
|-----------|-------------------|----------------|
| **FastAPI** | 0.110.x | RESTful API framework |
| **Motor** | AsyncIOMotorClient | MongoDB async driver |
| **Socket.IO** | python-socketio (AsyncServer + AsyncRedisManager) | Real-time WebSocket iletişimi |
| **JWT** | python-jose | Token tabanlı kimlik doğrulama |
| **Passlib** | bcrypt | Şifre hashleme |
| **APScheduler** | AsyncIOScheduler | Zamanlanmış görevler |
| **Stripe** | stripe-python | SaaS abonelik + merchant ödeme |
| **Brevo** | sib_api_v3_sdk | Transactional e-posta gönderimi |
| **Meta WhatsApp Cloud API** | whatsapp_service.py | WhatsApp bildirim (CONFIRMATION, REMINDER, SESSION_PACKAGE) |
| **Redis** | redis-py async | Cache, rate limiting, Socket.IO scaling, distributed lock |
| **Pydantic** | BaseModel / ConfigDict | Veri validasyonu |
| **Google Gemini** | google-generativeai / google-genai | AI asistan + Voice AI |
| **Sentry** | sentry-sdk | Hata izleme ve performance tracing |
| **Web Push** | pywebpush (VAPID) | Web push notification |
| **Firebase** | firebase-admin | Android/iOS push notification (FCM) |
| **Wise API** | requests | Uluslararası payout |
| **Pillow** | PIL | Resim işleme (logo upload) |
| **slowapi** | limits | Rate limiting |

### Veritabanı Yapısı (MongoDB Collections)

| Collection | Açıklama |
|-----------|----------|
| `users` | Kullanıcılar (admin, staff, superadmin, marketing) |
| `appointments` | Randevular (seans bilgileri, ödeme durumu dahil) |
| `services` | Hizmetler (session_count, payment_rule dahil) |
| `customers` | Müşteriler |
| `transactions` | İşletme iç finansal işlemler (gelir/gider) |
| `expenses` | Giderler |
| `settings` | İşletme ayarları (slug, base_currency, location, business_hours) |
| `organization_plans` | Abonelik planları ve kota bilgileri |
| `audit_logs` | Denetim günlükleri |
| `customer_notes` | Müşteri notları |
| `password_reset_tokens` | Şifre sıfırlama token'ları |
| `push_subscriptions` | Web Push ve FCM abonelikleri |
| `merchant_transactions` | **Merchant ödeme işlemleri** (Stripe, state machine ile yönetilen) |
| `merchant_wallets` | **Merchant cüzdan bakiyeleri** |
| `webhook_events` | **Webhook idempotency kayıtları** |
| `payout_batches` | **Payout batch kayıtları** (Wise) |
| `exchange_rates` | **Döviz kuru geçmişi** (GBP/TRY) |
| `payment_logs` | SaaS abonelik ödeme logları |

---

## 🔄 Başlangıç ve Yaşam Döngüsü

### `lifespan()` Fonksiyonu

Uygulama başlangıcında ve kapanışında çalışan async context manager.

**Başlangıç Adımları:**

1. **MongoDB Bağlantısı** — `MONGO_URL` env ile `AsyncIOMotorClient` bağlantısı; başarısız olursa lazy initialization
2. **Redis Bağlantısı** — Cache, rate limiting ve Socket.IO scaling için; başarısız olursa dummy limiter
3. **Rate Limiter** — Redis varsa gerçek, yoksa dummy limiter
4. **Firebase Initialization** — FCM push notification için `firebase-admin` başlatma
5. **SMS/WhatsApp Reminder Scheduler** — `AsyncIOScheduler`, her 5 dakikada `check_and_send_reminders()`
6. **Database Indexes:**
   - `appointments`: `organization_id`, `appointment_date`, `staff_member_id`, `phone`, `status`
   - `users`: `organization_id`, `role`, `slug` (unique)
   - `settings`: `organization_id` (unique), `slug` (unique)

**Kapanış:** Scheduler durdurulur, MongoDB ve Redis bağlantıları kapatılır.

---

## 🔐 Güvenlik ve Kimlik Doğrulama

### JWT Token Yönetimi

- **Token oluşturma:** `create_access_token(data, expires_delta)` — varsayılan süre: 24 saat
- **Token doğrulama:** `get_current_user(request, token)` — JWT decode → DB'den kullanıcı çekme
- **Token payload:** `sub` (username), `role`, `org_id`, `can_view_all_appointments`
- **Roller:** `superadmin`, `admin`, `staff`, `marketing`

### Şifre Yönetimi

- `get_password_hash()` — Bcrypt
- `verify_password()` — Bcrypt doğrulama

### Rate Limiting

- `slowapi` + `limits` async storage (Redis)
- Endpoint bazlı limit tanımları: `register`, `login`, `forgot-password`
- `RATE_LIMIT_ENABLED` env flag ile açılır/kapanır

### Multi-Tenant İzolasyonu

- **HER sorgu** `organization_id` filtresi içerir (superadmin hariç)
- Staff kullanıcılar `can_view_all_appointments` yetkisine sahip değilse sadece kendi randevularını görür

### Audit Logging

- `create_audit_log()` ile tüm önemli işlemler (CREATE, UPDATE, DELETE) loglanır
- Kullanıcı bilgileri, IP adresi, eski/yeni değerler saklanır
- `AUDIT_LOGS_ENABLED` env flag ile kontrol edilir

---

## 📊 Veri Modelleri

### Service Modeli

```python
class Service(BaseModel):
    organization_id: str
    id: str
    name: str
    price: float
    duration: int = 30
    order: Optional[int] = None
    session_count: Optional[int] = None       # Seans sayısı (>1 ise seans paketi)
    payment_rule: Optional[str] = None         # "online" | "deposit" | None (on_site)
    deposit_percentage: Optional[int] = None   # Kapora yüzdesi (deposit için)
```

### Appointment Modeli

```python
class Appointment(BaseModel):
    organization_id: str
    id: str
    customer_name: str
    phone: str
    service_id: str
    service_name: str
    service_price: float
    appointment_date: str         # "YYYY-MM-DD"
    appointment_time: str         # "HH:MM"
    notes: str = ""
    status: str = "Bekliyor"     # "Bekliyor" | "Tamamlandı" | "İptal" | "İptal Edildi" | "Ödeme Bekleniyor"
    staff_member_id: Optional[str] = None
    service_duration: Optional[int] = None
    source: Optional[str] = None  # "admin_bulk", "public_booking", vb.
    # Seans paketi alanları
    session_group_id: Optional[str] = None
    session_number: Optional[int] = None
    session_total: Optional[int] = None
    # Ödeme durumu
    payment_status: Optional[str] = None  # "paid" | "pending_payment" | "package_included" | "refunded" | "no_payment_required"
```

### User Modeli

```python
class User(BaseModel):
    username: str                    # E-posta (unique)
    full_name: str
    organization_id: str
    role: str                        # "admin" | "staff" | "superadmin" | "marketing"
    slug: str                        # URL-friendly kullanıcı adı
    permitted_service_ids: list      # Personelin verebileceği hizmetler
    payment_type: str                # "salary" | "commission"
    payment_amount: float
    status: str                      # "active" | "pending"
    invitation_token: Optional[str]
    days_off: list                   # ["sunday", "monday"]
    can_view_all_appointments: bool  # Tüm randevuları görebilir mi?
```

### Settings Modeli

```python
class Settings(BaseModel):
    organization_id: str
    company_name: str
    support_phone: str
    slug: str                            # URL-friendly işletme adı (unique)
    logo_url: Optional[str]
    sms_reminder_hours: int
    admin_provides_service: bool
    customer_can_choose_staff: bool
    business_hours: dict                 # Her gün: {is_open, open_time, close_time}
    base_currency: str                   # "GBP" | "TRY"
    fee_preference: str                  # "seller_pays" | "buyer_pays"
    payout_tier: str                     # "standard" | "fast" | "vip"
    kyc_verified: bool
    wise_recipient_verified: bool
    location: dict                       # {coordinates: {lat, lng}, address}
```

---

## 🔄 Randevu Durumları ve Yaşam Döngüsü

### Tüm Durumlar

| Durum | Kod | Açıklama |
|-------|-----|----------|
| **Bekliyor** | `status: "Bekliyor"` | Aktif randevu, henüz gerçekleşmedi |
| **Tamamlandı** | `status: "Tamamlandı"` | Bitiş saati geçmiş (otomatik) veya manuel |
| **İptal** | `status: "İptal"` | İptal edilmiş |
| **İptal Edildi** | `status: "İptal Edildi"` | İptal edilmiş (alternatif format) |
| **Ödeme Bekleniyor** | `status: "Ödeme Bekleniyor"` | Online/deposit ödeme bekleyen — **görünmez** |

### "Ödeme Bekleniyor" Özel Davranışları

Bu status'teki randevular **sistemin her yerinde filtrelenir:**
- ❌ `GET /api/appointments` listesinde görünmez
- ❌ `GET /api/stats/dashboard` istatistiklerine dahil edilmez
- ❌ Müsaitlik hesaplamada slot bloklamaz
- ❌ `GET /api/customers/{phone}/history` müşteri geçmişinde görünmez
- ❌ WhatsApp, Push, WebSocket bildirimi gönderilmez
- ❌ `_check_slot_conflict` çakışma kontrolünde sayılmaz
- ❌ `_find_alternative_slots` alternatif slot aramada sayılmaz

### Otomatik Tamamlanma

Her `GET /api/appointments` ve `GET /api/stats/dashboard` çağrısında:
1. "Bekliyor" randevuları kontrol edilir
2. Bitiş saati hesaplanır: `appointment_time + service_duration`
3. Şu an ≥ bitiş saati ise → "Tamamlandı" + `Transaction` kaydı + `completed_at`

---

## 📦 Seans Paketi Sistemi

### Genel Bakış

Hizmetler seans tabanlı olabilir (`session_count > 1`). İlk seans public booking veya admin panelinden oluşturulur, kalan seanslar toplu olarak planlanır.

### Veri Modelleri

```python
class SessionSlot(BaseModel):
    date: str      # "YYYY-MM-DD"
    time: str      # "HH:MM"

class BulkSessionCreate(BaseModel):
    customer_name: str
    phone: str
    service_id: str
    staff_member_id: Optional[str] = None
    notes: str = ""
    session_group_id: Optional[str] = None      # Yeniden planlama için
    starting_session_number: int = 1
    session_total: Optional[int] = None
    sessions: list[SessionSlot]
```

### `POST /api/appointments/bulk-session`

**Akış:**

```
1. Hizmet doğrulama (service_id, organization_id)
   ↓
2. Personel doğrulama (staff yetkisi, permitted_service_ids)
   ↓
3. Kota kontrolü (her seans için ayrı ayrı artırılır)
   ↓
4. Yeniden planlama kontrolü:
   - session_group_id varsa → aynı grubun starting_session_number'dan itibaren
     "Tamamlandı" ve "İptal Edildi" olmayan seansları otomatik iptal et
   ↓
5. Her slot için çakışma kontrolü:
   - Redis distributed lock (aynı anda çift randevu engeli)
   - _check_slot_conflict → çakışma varsa alternatif personel ara
   - check_break_conflict → mola saatleri kontrolü
   - Personelsiz mod: çakışma var ama warning ile devam
   ↓
6. Atomik insert_many ile tüm randevular oluşturulur
   ↓
7. Müşteri kaydı (upsert)
   ↓
8. Cache invalidation + WebSocket emit (appointments_bulk_created)
   ↓
9. WhatsApp SESSION_PACKAGE bildirimi (arka planda)
```

### Seans Özellikleri

- **session_group_id:** Aynı gruba ait tüm seansları birleştirir (UUID)
- **session_number:** 1'den başlayan seans numarası
- **session_total:** Toplam seans sayısı
- **payment_status:** İlk seans = `"paid"`, diğerleri = `"package_included"`
- **service_price:** İlk seans = hizmet fiyatı, diğerleri = 0
- **source:** `"admin_bulk"`

### Yardımcı Fonksiyonlar

```python
async def _check_slot_conflict(db, organization_id, staff_id, date, time, service_duration) -> bool:
    # "İptal", "İptal Edildi", "Ödeme Bekleniyor" hariç mevcut randevularla overlap kontrolü
    # True = çakışma var

async def _find_available_staff_for_slot(db, organization_id, service_id, date, time, service_duration, exclude_staff_id) -> str | None:
    # Hizmeti verebilen (permitted_service_ids) tüm personeller arasında
    # çakışma ve mola kontrolü yaparak müsait birini bulur
```

---

## 💳 Online Ödeme Sistemi

### Genel Bakış

Hizmetlerin `payment_rule` alanına göre online ödeme alınır. Financial modülü `backend/financial/` altında modüler yapıdadır.

### Hizmet Ödeme Kuralları

| `payment_rule` | Davranış |
|----------------|----------|
| `None` / `"on_site"` | Ödeme işletmede, online ödeme yok |
| `"online"` | Tam tutar online ödeme zorunlu |
| `"deposit"` | Kapora (sabit veya yüzde) online, kalan işletmede |

### Financial Modülü Dosya Yapısı

```
backend/financial/
├── __init__.py
├── merchant_checkout.py    # Stripe Checkout oluşturma, webhook handling
├── fee_calculator.py       # Platform komisyon hesaplama (buyer_pays / seller_pays)
├── financial_endpoints.py  # FastAPI router: cüzdan, payout, ayarlar, superadmin
├── state_machine.py        # Transaction state machine (SINGLE SOURCE OF TRUTH)
├── payout_service.py       # Wise payout batch oluşturma ve işleme
├── wise_service.py         # Wise API entegrasyonu
├── compliance.py           # KYC, IBAN cooldown, AML kontrolleri
├── currency_shield.py      # GBP/TRY kur takibi, buffer oranları
├── cron_jobs.py            # Finansal zamanlanmış görevler
├── schemas.py              # Pydantic modeller (merchant_transactions, wallets, vb.)
├── money.py                # Para birimi yardımcıları, tier konfigürasyonu
├── email_notifications.py  # Finansal e-posta bildirimleri
└── migration.py            # Veri migrasyon araçları
```

### `POST /api/public/checkout`

Müşteri tarafı checkout session oluşturma (auth gerektirmez).

**Akış:**

```
1. Merchant settings + service yükle
   ↓
2. base_currency (GBP/TRY), tier, fee_preference belirle
   ↓
3. Fee hesapla (fee_calculator.py):
   - seller_pays → komisyon merchant'tan kesilir
   - buyer_pays → komisyon müşteriye yansıtılır
   ↓
4. Deposit kuralı uygula (full_online / deposit / on_site)
   ↓
5. Stripe Checkout Session oluştur
   ↓
6. Pending transaction oluştur (state_machine)
   ↓
7. Checkout URL döndür
```

### Fee Calculator

```python
@dataclass(frozen=True)
class FeeResult:
    gross_minor: int              # Müşterinin ödediği toplam (minor unit)
    net_minor: int                # Merchant'ın aldığı net tutar
    fee_minor: int                # Platform komisyonu
    fee_rate_bps: int             # Komisyon oranı (basis points)
    stripe_currency: str          # Stripe'a gönderilen para birimi
    base_currency: str
    deposit_applied: bool         # Kapora uygulandı mı?
    deposit_minor: int            # Kapora tutarı
    full_service_price_minor: int # Hizmetin tam fiyatı
```

### Stripe Merchant Webhook

Webhook handler (`handle_stripe_merchant_webhook`), Stripe'dan gelen `checkout.session.completed` ve diğer event'leri işler:

1. **Webhook idempotency:** `webhook_events` collection'ında `event_id` kontrolü
2. Ödeme onaylandığında:
   - Transaction state: `pending` → `captured`
   - Randevu: `status` → `"Bekliyor"`, `payment_status` → `"paid"`
   - WhatsApp CONFIRMATION + Push notification gönderimi
   - WebSocket `appointment_created` event

---

## ⏳ Ödeme Bekleniyor Akışı

### Randevu Oluşturma (Online/Deposit Hizmet)

Public booking'den online/deposit `payment_rule`'lu bir hizmet için randevu oluşturulduğunda:

```
POST /api/public/appointments
   ↓
Hizmetin payment_rule kontrol edilir
   ↓
payment_rule == "online" veya "deposit" ise:
   appointment_data['payment_status'] = 'pending_payment'
   appointment_data['status'] = 'Ödeme Bekleniyor'
   ↓
Randevu DB'ye kaydedilir — AMA:
   ❌ WhatsApp bildirimi GÖNDERİLMEZ
   ❌ Push notification GÖNDERİLMEZ
   ❌ WebSocket event GÖNDERİLMEZ
   ↓
Frontend müşteriyi Stripe Checkout'a yönlendirir
```

### Ödeme Sonrası Aktivasyon

```
Stripe webhook → checkout.session.completed
   ↓
Randevu güncellenir:
   status: "Ödeme Bekleniyor" → "Bekliyor"
   payment_status: "pending_payment" → "paid"
   ↓
Bildirimler gönderilir:
   ✅ WhatsApp CONFIRMATION template
   ✅ Push notification
   ✅ WebSocket appointment_created event
   ↓
Randevu artık her yerde GÖRÜNÜR
```

### Checkout İptali

Müşteri Stripe Checkout sayfasını kapatırsa:
- Randevu `"Ödeme Bekleniyor"` olarak kalır
- Sistemde **görünmez** (hayalet randevu)
- Slot'u bloklamaz, istatistiklere dahil değildir

### Filtrelenen Tüm Noktalar

```python
# Her yerde status filter olarak kullanılır:
{"status": {"$nin": ["İptal", "İptal Edildi", "Ödeme Bekleniyor"]}}

# Filtreleme uygulanan fonksiyonlar:
- get_appointments()
- get_dashboard_stats()
- get_availability() (public + internal)
- get_customer_history()
- _check_slot_conflict()
- _find_available_staff_for_slot()
- _find_alternative_slots()
- Tüm conflict check noktaları
```

---

## 💰 Cüzdan (Wallet) Sistemi

### Endpoint'ler

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/merchant/wallet` | Cüzdan özeti (bakiyeler, bekleyen, donmuş) |
| `POST /api/merchant/payout/request` | Payout talebi oluştur |
| `GET /api/merchant/transactions` | Transaction listesi (filtrelenebilir) |
| `GET /api/merchant/payout/eligibility` | Payout uygunluk kontrolü |
| `GET /api/merchant/payout/history` | Payout geçmişi |

### Transaction State Machine

**SINGLE SOURCE OF TRUTH — `state_machine.py`**

Tüm geçerli state geçişleri:

```
pending → authorized → captured → settled → available → reserved → paid_out
pending → canceled
pending → async_failed
captured → refunded
available → refunded
available → frozen → disputed → resolved_won (→ fonlar available'a döner)
available → frozen → disputed → resolved_lost (→ kalıcı kayıp)
reserved → paid_out
reserved → failed (→ available rollback)
```

### Settlement Süreci

- **T+2 gün:** `captured` → `settled` → `available` (settlement_check_job, her 2 saatte)
- Settlement sonrası fonlar merchant cüzdanında kullanılabilir hale gelir

### Payout Uygunluk Koşulları

1. ✅ KYC doğrulanmış (`kyc_verified: true`)
2. ✅ Wise recipient doğrulanmış
3. ✅ IBAN cooldown geçmiş (48 saat — banka bilgileri değişikliği sonrası)
4. ✅ Donmuş bakiye yok
5. ✅ Minimum eşik (₺12.000 standard tier)
6. ✅ AML limitlerine uygun

### Payout Marketleri

| Pazar | Yöntem | Maliyet |
|-------|--------|---------|
| **GBP** | Wise BACS local transfer | £0.20–0.40 |
| **TRY** | Wise GBP→TRY cross-border | ~£5–6 |

---

## 🔄 İade (Refund) Sistemi

### Tekil Randevu İadesi

**`POST /api/appointments/{appointment_id}/refund`**

1. Randevu ve ilişkili `merchant_transactions` bulunur
2. `stripe_payment_intent_id` ile Stripe refund başlatılır
3. Seans paketi parçası ise → orantılı iade (`amount / session_total`)
4. Seans paketi parçası ise → ayrı `"refund"` type transaction oluşturulur
5. Değilse → StateMachine ile `captured/available` → `refunded` geçişi
6. Wallet güncellenir: `available_balance -= refund_amount`, `total_refunded += refund_amount`
7. Randevu: `payment_status` → `"refunded"`, `status` → `"İptal Edildi"`

### Seans Grubu Toplu İptal

**`POST /api/appointments/session-group/{group_id}/cancel-remaining?from_session_number=N`**

- Belirtilen seans numarasından itibaren bekleyen seansları iptal eder
- Kota geri verilir (iptal edilen seans sayısı kadar)
- İade **yapmaz** (sadece iptal)

### Seans Grubu Toplu İptal + İade

**`POST /api/appointments/session-group/{group_id}/cancel-and-refund?from_session_number=N`**

- Seansları iptal eder
- **Orantılı iade hesaplar:** `refund_amount = total_amount * (cancel_count / total_in_group)`
- Tam grup iptali → full refund, kısmi → partial refund
- Partial refund: ayrı `"refund"` type transaction oluşturulur
- Full refund: StateMachine ile `refunded` state'e geçiş
- Stripe refund başlatılır + wallet güncellenir

### Dashboard İptal Dialogu

- **"Sadece İptal Et"** — Sadece randevuyu iptal eder, iade yok
- **"İptal Et ve İade Yap"** — İptal + Stripe iade başlatır
- İade butonu SADECE `payment_status` = `"paid"` veya `"deposit_paid"` olan randevularda gösterilir
- `"package_included"` randevularda iade butonu **gösterilmez**

---

## 📱 WhatsApp Bildirim Sistemi

### Template Yapısı

`whatsapp_service.py` içinde 3 ana template tipi:

| Template | Kullanım |
|----------|----------|
| **CONFIRMATION** | Randevu onayı (oluşturma sonrası) |
| **REMINDER** | Randevu hatırlatması (scheduler, X saat önce) |
| **SESSION_PACKAGE** | Seans paketi bilgisi (toplu planlama sonrası) |

### Dil ve Konum Matrisi

Her template için 4 varyant:

| | TR + Konum | TR + Metin | EN + Konum | EN + Metin |
|---|---|---|---|---|
| CONFIRMATION | `randevu_onay_konumlu_v2` | `randevu_onay_metin` | `randevu_onay_konumlu_eng_v2` | `randevu_onay_metin_eng_v2` |
| REMINDER | `randevu_hatirlatma_konumlu` | `randevu_hatirlatma_metin_v2` | `randevu_hatirlatma_konumlu_eng` | `randevu_hatirlatma_metin_v2_eng` |
| SESSION_PACKAGE | `seans_paketi_onay_konumlu` | `seans_paketi_onay_metin` | (EN varyantlar) | (EN varyantlar) |

### Dil Tespiti

`detect_language_from_phone(phone)` — Telefon numarasına göre:
- `+90...` → `TR`
- `+44...` → `EN`
- Diğer → `EN` (fallback)

### SESSION_PACKAGE Template Parametreleri

5 parametre:
1. `{{1}}` — Müşteri adı
2. `{{2}}` — Hizmet adı
3. `{{3}}` — Toplam seans sayısı
4. `{{4}}` — Seans tarihleri listesi
5. `{{5}}` — İletişim numarası

**Önemli:** Meta WhatsApp API template parametrelerinde `\n` (newline) desteklenmez. Seans tarihleri `|` (pipe) ayracı ile formatlanır:
```
15 Oca 2026 10:00 | 22 Oca 2026 10:00 | 29 Oca 2026 10:00
```

### Konum Senaryoları

- **Senaryo A (koordinat VAR):** Header = location (lat/lng), body = 5-6 parametre
- **Senaryo B (koordinat YOK):** Header = text (işletme adı), body = 7 parametre (adres metin olarak eklenir)

---

## 🌐 API Endpoint'leri

### 🔑 Kimlik Doğrulama

| Endpoint | Açıklama |
|----------|----------|
| `POST /api/register` | Yeni işletme sahibi (admin) kaydı + trial plan + slug |
| `POST /api/token` | OAuth2 giriş → JWT token |
| `POST /api/forgot-password` | Şifre sıfırlama e-postası (Brevo) |
| `POST /api/reset-password` | Token ile şifre sıfırlama |
| `POST /api/auth/setup-password` | Personel davet token'ı ile şifre belirleme |

### 📅 Randevu İşlemleri

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/appointments` | Randevuları listele (role-based, "Ödeme Bekleniyor" hariç) |
| `POST /api/appointments` | Admin/staff panelinden randevu oluştur |
| `PUT /api/appointments/{id}` | Randevu güncelle |
| `DELETE /api/appointments/{id}` | Randevu sil |
| `GET /api/appointments/{id}` | Tek randevu detayı |
| `POST /api/appointments/bulk-session` | **Seans paketi toplu oluşturma** |
| `POST /api/appointments/session-group/{group_id}/cancel-remaining` | **Seans grubu toplu iptal** |
| `POST /api/appointments/session-group/{group_id}/cancel-and-refund` | **Seans grubu iptal + orantılı iade** |
| `POST /api/appointments/{id}/refund` | **Tekil randevu Stripe iadesi** |

### 🌍 Public Endpoint'ler

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/public/info/{org_id}` | İşletme bilgileri (müşteri booking sayfası) |
| `GET /api/public/availability/{org_id}` | Müsait saatler (slot hesaplama) |
| `POST /api/public/appointments` | Müşteri sayfasından randevu oluştur |
| `POST /api/public/checkout` | **Stripe Checkout Session oluştur** (merchant ödeme) |

### 🛠️ Hizmet Yönetimi

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/services` | Hizmetleri listele |
| `POST /api/services` | Yeni hizmet ekle (session_count, payment_rule dahil) |
| `PUT /api/services/{id}` | Hizmet güncelle |
| `DELETE /api/services/{id}` | Hizmet sil |

### 👥 Personel Yönetimi

| Endpoint | Açıklama |
|----------|----------|
| `POST /api/staff/add` | Personel davet et (e-posta ile) |
| `PUT /api/staff/{id}/payment` | Ödeme ayarları (salary/commission) |
| `PUT /api/staff/{id}/days-off` | Tatil günleri |
| `PUT /api/staff/{id}/services` | Hizmet yetkileri |
| `DELETE /api/staff/{id}` | Personel sil |

### 💰 İşletme Finans

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/finance/summary` | Gelir/gider özeti (period bazlı) |
| `GET /api/expenses` | Giderleri listele |
| `POST /api/expenses` | Gider ekle |
| `GET /api/finance/payroll` | Personel hakedişleri |
| `POST /api/finance/payroll/payment` | Personel ödemesi yap |

### 💳 Merchant Ödeme (Financial Modülü)

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/merchant/wallet` | Cüzdan bakiye özeti |
| `GET /api/merchant/transactions` | Merchant transaction listesi |
| `GET /api/merchant/payment-settings` | Ödeme ayarları |
| `PUT /api/merchant/payment-settings` | Ödeme ayarları güncelle (fee_preference, bank details) |
| `GET /api/merchant/payout/eligibility` | Payout uygunluk kontrolü |
| `POST /api/merchant/payout/request` | Payout talebi |
| `GET /api/merchant/payout/history` | Payout geçmişi |
| `GET /api/merchant/fee-preview` | Komisyon önizleme |

### 📊 İstatistikler

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/stats/dashboard` | Admin dashboard ("Ödeme Bekleniyor" hariç) |
| `GET /api/stats/personnel` | Personel dashboard |

### 👤 Müşteri Yönetimi

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/customers` | Müşteri listesi |
| `POST /api/customers` | Yeni müşteri ekle |
| `DELETE /api/customers/{phone}` | Müşteri sil |
| `GET /api/customers/{phone}/history` | Müşteri geçmişi ("Ödeme Bekleniyor" hariç) |
| `PUT /api/customers/{phone}/notes` | Müşteri notu güncelle |

### ⚙️ Ayarlar ve Diğer

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/settings` | İşletme ayarları |
| `PUT /api/settings` | Ayarları güncelle |
| `POST /api/settings/logo` | Logo yükle |
| `GET /api/plans` | Tüm SaaS planları |
| `GET /api/plan/current` | Mevcut plan + kota bilgisi |
| `GET /api/audit-logs` | Denetim günlükleri |
| `GET /api/export/appointments` | Randevuları CSV export |
| `GET /api/export/customers` | Müşterileri CSV export |
| `POST /api/ai/chat` | AI asistan sohbet |

### 🔗 Webhook Endpoint'leri

| Endpoint | Açıklama |
|----------|----------|
| `POST /api/webhook/stripe` | SaaS Stripe webhook |
| `POST /webhook/stripe` | SaaS Stripe webhook (uyumluluk) |
| `POST /payments/webhook/stripe` | SaaS Stripe webhook (uyumluluk) |
| `POST /api/merchant/webhook/stripe` | Merchant Stripe webhook (financial modülü) |
| `POST /api/merchant/webhook/wise` | Wise payout webhook |
| `POST /webhook` | WhatsApp webhook |
| `POST /api/webhook` | WhatsApp webhook (uyumluluk) |

---

## 🔌 WebSocket ve Real-Time İletişim

### Socket.IO Yapılandırması

```python
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=socketio_cors_origins
)
# Redis manager ile cross-worker event broadcasting
socket_app = socketio.ASGIApp(sio, socketio_path='/api/socket.io', other_asgi_app=app)
```

### Event Handler'lar

| Event | Yön | Açıklama |
|-------|-----|----------|
| `connect` | Server | Client bağlandı → `connection_established` emit |
| `disconnect` | Server | Client bağlantısı kesildi |
| `join_organization` | Client→Server | Room'a katıl: `org_{organization_id}` |
| `leave_organization` | Client→Server | Room'dan ayrıl |

### Gönderilen Event'ler

| Event | Tetikleyici |
|-------|-------------|
| `appointment_created` | Randevu oluşturulduğunda (ödeme tamamlandıysa) |
| `appointment_updated` | Randevu güncellendiğinde |
| `appointment_deleted` | Randevu silindiğinde |
| `appointments_bulk_created` | Seans paketi oluşturulduğunda |
| `customer_added` | Yeni müşteri eklendiğinde |
| `customer_deleted` | Müşteri silindiğinde |

### `emit_to_organization(organization_id, event, data)`

Belirli bir organization'ın tüm bağlı client'larına `org_{organization_id}` room'u üzerinden event gönderir.

**Önemli:** `"Ödeme Bekleniyor"` randevuları için WebSocket event gönderilmez.

---

## 🔔 Push Notification Sistemi

### Desteklenen Platformlar

| Platform | Teknoloji |
|----------|-----------|
| **Web** | VAPID Web Push (pywebpush) |
| **Android** | Firebase Cloud Messaging (FCM) |
| **iOS** | Firebase Cloud Messaging (FCM) |

### `send_push_notification(db, organization_id, title, body, data, user_id)`

1. `push_subscriptions` collection'ından ilgili org'un aboneliklerini çeker
2. Platform kontrolü:
   - `android`/`ios` → Firebase `messaging.send()` ile FCM
   - Web → `webpush()` ile VAPID push
3. Geçersiz abonelikler otomatik temizlenir (410/404 response)

---

## 📧 E-posta Entegrasyonu

### Brevo (Sendinblue) Transactional E-posta

| Fonksiyon | Kullanım |
|-----------|----------|
| `send_email()` | Genel e-posta gönderimi |
| `send_personnel_invitation_email()` | Personel davet e-postası |
| `send_password_reset_email()` | Şifre sıfırlama e-postası |
| `_build_subscription_email()` | Abonelik aktivasyon e-postası (TR/EN) |

---

## 🎫 Kota ve Abonelik Yönetimi

### Plan Yapısı

| Plan | Randevu/Ay | AI Mesaj Limiti | Aylık Fiyat (TL) | Yıllık Fiyat (TL) |
|------|-----------|-----------------|-------------------|-------------------|
| Trial | 50 | 100 | 0 | — |
| Standart | 100 | 500 | 710 | 7.100 |
| Profesyonel | 300 | 3.000 | 1.020 | 10.200 |
| Premium | 600 | 10.000 | 1.530 | 15.300 |
| Business | 900 | Sınırsız | 1.940 | 19.400 |
| Enterprise | 1.200 | Sınırsız | 2.350 | 23.500 |
| Kurumsal | Sınırsız | Sınırsız | 3.580 | 35.800 |

### Kota Kontrolü

```python
check_quota_and_increment(db, organization_id) -> (bool, str)
```

1. Organization plan getirilir (yoksa trial oluşturulur)
2. Trial süresi dolmuş mu kontrolü
3. Kota reset: reset tarihi geçmişse kullanım sıfırlanır (30 günlük döngü)
4. Kullanım >= limit ise hata döner
5. Kullanım +1 artırılır

### Stripe Yıllık Abonelik Kota Reset

Stripe yearly subscription'lar aylık webhook göndermediği için, her ay başında `quota_last_reset_date` kontrolü ile kota otomatik sıfırlanır.

---

## 💳 SaaS Abonelik Ödeme

### Stripe Subscription

**`POST /api/payments/create-checkout-session`**

1. Plan ve billing cycle (monthly/yearly) alınır
2. Kullanıcının dil ve para birimi belirlenir
3. **Lookup key** oluşturulur: `{plan}_{cycle}_{currency}` (ör: `standard_monthly_gbp`, `professional_monthly_try`)
4. Stripe'da lookup key ile fiyat aranır
5. Stripe Checkout Session (subscription mode) oluşturulur
6. Frontend checkout URL'e yönlendirilir

### Stripe SaaS Webhook

**`POST /api/webhook/stripe`** (+ uyumluluk path'leri)

1. `stripe.Webhook.construct_event()` ile signature doğrulaması
2. `checkout.session.completed` event'i işlenir:
   - Plan aktivasyonu (kota güncelleme)
   - Abonelik e-postası gönderimi
   - Payment log kaydı

### PayTR (Türkiye)

**`POST /api/subscription/paytr/initiate`** — PayTR iframe token oluşturma
**`POST /api/subscription/paytr/callback`** — PayTR webhook (hash doğrulama + plan aktivasyonu)

---

## 🕐 Müsaitlik Hesaplama

### Algoritma

**`GET /api/public/availability/{organization_id}`**

```
1. İşletme ayarları (business_hours) yükle
   ↓
2. Gün kontrolü: İşletme o gün açık mı?
   ↓
3. Personel kontrolü:
   A) Belirli personel → days_off kontrolü
   B) Otomatik atama → hizmeti verebilen tüm personeller
   ↓
4. Slot oluşturma: STEP_INTERVAL = 15 dakika
   Açılış → kapanış arası 15dk aralıklarla slotlar
   ↓
5. Her slot için filtreleme:
   - Geçmiş saatler (bugün için)
   - Kapanış saati kontrolü (slot + hizmet süresi ≤ kapanış)
   - Çakışma kontrolü: "İptal", "İptal Edildi", "Ödeme Bekleniyor" hariç randevular
   - Overlap: (new_start < existing_end) AND (new_end > existing_start)
   ↓
6. Otomatik atama mantığı:
   - Tüm personeller kontrol edilir
   - En az bir personel müsaitse → slot available
   - Tüm personeller doluysa → slot busy
```

**Response:**
```json
{
  "available_slots": ["09:00", "09:15", "10:30"],
  "all_slots": ["09:00", "09:15", "09:30"],
  "busy_slots": ["10:00", "11:00"]
}
```

---

## 💰 Finans ve Kasa Yönetimi

### İşletme İç Finansı (server.py)

- **Gelir:** "Tamamlandı" randevuların `service_price` toplamı
- **Gider:** `expenses` collection'ından
- **Net Kâr:** Gelir – Gider
- **Personel Hakedişleri:**
  - `salary` → sabit maaş
  - `commission` → randevu tutarı × yüzde

### Merchant Ödeme Finansı (financial/ modülü)

Ayrı bir para akışı; müşterilerden Stripe ile alınan ödemeler:
- `merchant_transactions` collection'ında takip edilir
- State machine ile durum yönetimi
- `merchant_wallets` ile bakiye takibi
- Wise üzerinden payout

---

## 👥 Personel Yönetimi

### Ekleme Akışı

```
1. Admin personel bilgilerini girer (şifre YOK)
   ↓
2. invitation_token oluşturulur
   ↓
3. Personel "pending" status ile kaydedilir
   ↓
4. Brevo ile davet e-postası gönderilir
   ↓
5. Personel e-postadaki linke tıklar
   ↓
6. POST /api/auth/setup-password ile şifre belirler
   ↓
7. status → "active", invitation_token silinir
```

### Özellikler

- **days_off:** Haftalık tatil günleri (müsaitlik hesaplamada kullanılır)
- **permitted_service_ids:** Verebileceği hizmetler (randevu + seans oluştururken kontrol edilir)
- **payment_type/amount:** `salary` (sabit) veya `commission` (yüzde bazlı)
- **can_view_all_appointments:** Tüm randevuları görebilme yetkisi

---

## 👤 Müşteri Yönetimi

### Kaynaklar

1. **Randevu oluşturma:** Admin/staff veya public booking'den otomatik eklenir
2. **Manuel ekleme:** Admin tarafından isim + telefon ile

### Duplicate Kontrolü

Telefon numarası + isim (case-insensitive) kombinasyonuyla çift kayıt engellenir.

### Müşteri Notları

- `customer_notes` collection'ında saklanır
- Admin ve yetkili staff erişebilir

---

## 🤖 AI Entegrasyonu

### Gemini AI Asistan

- **`POST /api/ai/chat`** — Metin tabanlı AI sohbet
- `ai_service.py` → `chat_with_ai()` fonksiyonu
- Plan bazlı mesaj limiti (trial: 100, standart: 500, premium: 10.000, business+: sınırsız)

### Voice AI

- `voice_ai_service.py` → Gemini Live Audio entegrasyonu
- Socket.IO üzerinden real-time ses akışı
- `voice_start`, `voice_audio`, `voice_stop` event'leri

---

## ⏰ Zamanlanmış Görevler (Cron Jobs)

### Hatırlatma Scheduler (server.py)

- **Her 5 dakika:** `check_and_send_reminders()` — WhatsApp hatırlatma gönderimi
- Redis distributed lock: `reminder_lock:{YYYYMMDDHHMM}` (çakışma engeli)
- Tolerance: ±6 dakika penceresi

### Financial Cron Jobs (financial/cron_jobs.py)

| Job | Zamanlama | Açıklama |
|-----|-----------|----------|
| `currency_shield_job` | 01:00 UTC (gece) | GBP/TRY kur güncelleme, spike tespiti |
| `settlement_check_job` | Her 2 saat | T+2 settlement: captured → settled → available |
| `refund_reserve_release_job` | Her saat | Refund reserve window süresi dolmuş işlemler |
| `auto_payout_job` | 03:00 UTC (gece) | Otomatik payout batch oluşturma |
| `wise_status_check_job` | Her 30 dk | Wise transfer durumu kontrolü |
| `quote_cleanup_job` | Her saat | Süresi dolmuş quote temizliği |
| `failed_webhook_retry_job` | Her 15 dk | Başarısız webhook'ları yeniden deneme |
| `daily_reconciliation_job` | 23:30 UTC (gece) | Günlük mutabakat raporu |

---

## 🛠️ Yardımcı Fonksiyonlar

| Fonksiyon | Açıklama |
|-----------|----------|
| `slugify(text)` | Türkçe karakterleri Latin'e çevirir, URL-friendly slug |
| `make_json_serializable(obj)` | ObjectId → string, datetime → ISO format |
| `clean_dict_for_audit(data)` | Audit log için `_id` temizleme |
| `create_audit_log(...)` | Denetim günlüğü kaydı oluşturma |
| `emit_to_organization(org_id, event, data)` | WebSocket event gönderimi |
| `check_quota_and_increment(db, org_id)` | Kota kontrolü ve artırma |
| `_check_slot_conflict(...)` | Randevu çakışma kontrolü |
| `_find_available_staff_for_slot(...)` | Müsait personel bulma |
| `format_phone_number(phone)` | Telefon numarası formatlama (WhatsApp) |
| `detect_language_from_phone(phone)` | Telefon numarasından dil tespiti |

---

## 🔒 Güvenlik Notları

1. **JWT Secret Key:** `JWT_SECRET_KEY` env'den alınır, default kullanılmamalı
2. **Bcrypt Hashleme:** Her hash benzersiz (otomatik salt)
3. **Rate Limiting:** Redis ile brute force koruması
4. **Multi-Tenant İzolasyon:** Her sorgu `organization_id` filtresi içerir
5. **Stripe Webhook Doğrulama:** `stripe.Webhook.construct_event()` ile signature kontrolü
6. **Webhook Idempotency:** `webhook_events` collection'ında event_id ile çift işleme engeli
7. **Cloudflare Turnstile:** Public sayfalarda bot koruması
8. **CORS:** Production'da spesifik domain'ler (`CORS_ORIGINS` env)
9. **Audit Logging:** Tüm kritik işlemler loglanır (IP, kullanıcı, eski/yeni değer)
10. **Sentry:** Unhandled exception izleme + performance tracing
11. **IBAN Cooldown:** Banka bilgisi değişikliğinden sonra 48 saat payout engeli
12. **AML Limitleri:** Aylık payout eşik kontrolleri

---

## 📝 Bilinen Mimari Notlar

1. **İki paralel FastAPI uygulaması:** `server.py` (production) ve `app/main.py` (refaktör). **Production'da `server.py` çalışır.**
2. **server.py monolitik:** ~12.500+ satır. Yeni endpoint eklerken mevcut pattern'e uyum sağlanmalı.
3. **Financial modülü ayrı router:** `financial_endpoints.py` içinde `APIRouter`, `server.py`'dan `app.include_router()` ile mount edilir.
4. **Webhook path duplikasyonları:** Uyumluluk için aynı handler birden fazla path'e mount (`/api/webhook/stripe`, `/webhook/stripe`, `/payments/webhook/stripe`)
5. **Para birimleri minor unit:** TRY ve GBP tutarları kuruş/pence olarak saklanır (merchant_transactions). İşletme iç finansta float kullanılır.
6. **Redis multi-purpose:** Cache + Rate Limiting + Socket.IO Manager + Distributed Lock + WhatsApp doğrulama

---

**Dokümantasyon Tarihi:** 2026-04-14
**Dosya:** `/var/www/player5moduleryapi/backend/SERVER_ANALYSIS.md`
