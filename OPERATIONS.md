# PLANN — Operasyon Sözleşmesi (OPERATIONS.md)

Bu belge, koddan daha hızlı unutulan operasyonel bilgiyi versiyonlanan bir yere sabitler.
Gece yarısı bir deploy sırasında bu dosya tek doğruluk kaynağıdır. Kod kadar ciddiye al.

> Not: Mimari gerekçeler ve yol haritası için `PLANN_MIMARI_YOL_HARITASI.md`'ye bak.

---

## 1. Deploy Prosedürü (KRİTİK)

Backend kaynak kodu Docker image'ına build sırasında `COPY . .` ile gömülür.
`docker-compose.yml`'de backend servisinde **kaynak kod volume mount YOKTUR** (sadece `backend_static`).

Bunun sonucu:

- `docker restart plann_backend` -> ESKİ kodu çalıştırır. Kod değişikliğin YANSIMAZ. (Bu bir kez canlıda bizi yakaladı: "değişiklik neden çalışmıyor?" -> aslında hiç deploy olmamıştı.)

Backend'de Python kodu değiştiğinde ZORUNLU akış:

```bash
cd /var/www/player5moduleryapi
docker compose build backend
docker compose up -d backend
```

Doğrulama (container gerçekten yeni kodu çalıştırıyor mu?):

```bash
docker exec plann_backend grep -c "ARADIGIN_YENI_STRING" /app/server.py   # 1 dönmeli
docker logs plann_backend --tail 20
```

- Frontend (web): prod nginx (`sites-enabled/plannapp`) `location /` -> `http://127.0.0.1:8081`'e proxy'ler; bu port docker `frontend` container'ıdır. Dockerfile multi-stage (`npm run build` -> nginx) ve **volume mount YOKTUR** → JS bundle image'a build anında gömülür. Bu yüzden host'ta `npm run build` almak TEK BAŞINA YETMEZ; container'ı yeniden build edip recreate etmek gerekir:
  ```bash
  cd /var/www/player5moduleryapi
  docker compose build frontend
  docker compose up -d frontend
  ```
- Frontend (mobil): JS bundle build anında uygulamaya gömülür (`capacitor.config.json`'da `server.url` YOK). Eski App Store build'leri DONMUŞ kabul edilir; git push -> Codemagic/Android build -> store gerekir.

### Nginx gzip (GİT DIŞI — global config)

API JSON sıkıştırması `/etc/nginx/nginx.conf` http bloğunda açık: `gzip_proxied any`,
`gzip_types ... application/json`, `gzip_comp_level 5`, `gzip_min_length 1024`. **Proxied**
yanıtlar için `gzip_proxied any` şart (yoksa `/api/` proxy'si sıkışmaz). Bu dosya repo'da
değil; değişiklik yedeği `/etc/nginx/nginx.conf.bak.*`. Doğrulama:

```bash
curl -s -k -D - -o /dev/null -H "Host: plannapp.co" -H "Authorization: Bearer <token>" \
  -H "Accept-Encoding: gzip" https://127.0.0.1/api/appointments | grep -i content-encoding
# beklenen: content-encoding: gzip  (ölçülen: 261 KB -> 26 KB, ~%90)
```

---

## 2. Legacy Contract Listesi (DONDURULDU — şeklini değiştirme)

Aşağıdaki endpoint'lerin PARAMETRESİZ çağrıldığındaki response ŞEKLİ, App Store'daki
donmuş mobil build'ler tarafından parse edilir. Alan ekleme/çıkarma/yeniden adlandırma
YASAKTIR. Yeni davranış yalnızca YENİ query parametreleri arkasında olmalı.

- `GET /api/customers` (limit YOK) -> flat array. Randevulu müşteri `is_pending` içermez; randevusuz müşteri `is_pending:true` içerir. Kaynak: `backend/server.py` ~11265. `?limit=&cursor=` verilince -> `{items, next_cursor, has_more}` (yeni web).
- `GET /api/appointments` (parametresiz / date / status ...) -> `List[Appointment]`. Kaynak: `backend/server.py` class Appointment ~2338. **Faz 2 (additive):** `?limit=&cursor=` verilince -> `{items, next_cursor, has_more}`; `items[]` her elemanı yine birebir `Appointment` şekli (JSONResponse ile response_model baypas). Cursor: base64(`appointment_date|appointment_time|id`). Legacy array'e DOKUNULMADI.

Bu contract'lar golden dosyalarla test altında:

- `backend/tests/contracts/customers_legacy_v1.json`
- `backend/tests/contracts/appointments_legacy_v1.json`
- Test: `backend/tests/integration/test_legacy_contracts.py`

Çalıştırma:

```bash
docker exec -w /app plann_backend python -m pytest tests/integration/test_legacy_contracts.py -q
```

Bir refactor bu şekli bozarsa test patlar. Test patlıyorsa: alanı geri koy VEYA yeni davranışı
yeni parametre arkasına al; golden'ı "düzeltmek" için DEĞİŞTİRME (donmuş build hâlâ eski şekli bekliyor).

Legacy contract'ı bir gün silebilmenin tek yolu: force-update ile eski build popülasyonunu
emekliye ayırmak (bkz. Bölüm 4).

### 2.1. API Sözleşmesi Güvenlik Ağı (3 katman)

Sorun: 169 endpoint var, hepsine elle golden yazılamaz. Korunması gereken de aslında endpoint
değil **response modelidir** (aynı model N endpoint'te kullanılır; bir alan silinince hepsi kırılır).
Bu yüzden 3 katmanlı ağ:

1. **Golden JSON (davranış) — kritik legacy endpoint'ler.** `customers_legacy_v1.json`,
   `appointments_legacy_v1.json`. Şekil + `is_pending` invariant gibi DAVRANIŞ kilitlenir.
2. **response_model alan-seti snapshot (RESPONSE şeması) — TÜM modeller otomatik.**
   `models_fieldset_v1.json` + `test_model_fieldset_contract.py`. Response modeli olarak
   kullanılan (ve iç içe geçen) her Pydantic modelin alan seti kilitli. Alan **silme/rename**
   → patlar. Alan **ekleme** → güvenli. Bilinçli silmede: `UPDATE_CONTRACTS=1 pytest ...`.
3. **request required-field snapshot (REQUEST şeması) — TÜM body modelleri otomatik.**
   `request_required_v1.json` + `test_request_contract.py`. Her POST/PUT body modelinin ZORUNLU
   alan seti kilitli. Bir alan **zorunlu hale gelirse** (eski client göndermez → 400) → patlar.
   Opsiyonel ekleme / zorunlu kaldırma → güvenli. Yeni zorunlu alan gerekiyorsa: Optional+default
   yap VEYA yeni endpoint/sürüm aç. (Response değişmese bile request kırılması gerçek bir risktir.)
4. **Mobil API Surface (envanter) — hangi endpoint kritik?**
   `mobile_api_surface.md` (donmuş build'in çağırdığı endpoint listesi, `frontend/src`'ten
   otomatik). Yenile: `bash backend/tests/contracts/gen_mobile_surface.sh`.
5. **Contract version işaretleri (kod içi).** Donmuş endpoint'lerin dekoratörü üstünde
   `# ═══ CONTRACT: v1 (FROZEN / RESPONSE|REQUEST) ═══` marker'ı var (ör. `GET/POST /appointments`,
   `GET /customers`, `POST /public/appointments`). Amaç: 2 yıl sonra biri "bu neden böyle yazılmış?"
   deyip refactor etmesin — tarihsel/sözleşmesel sebebi kodda görsün. Yeni bir endpoint dondurulunca
   aynı marker'ı ekle.

**Sınır:** Şema testleri DAVRANIŞ testi değildir. Alan adı/tipi aynı kalıp ANLAMI değişirse
(`price` TL→kuruş, `status` değer seti) yakalanmaz → bu tür değişikliklerde ekstra dikkat + golden JSON.

Tüm ağı çalıştır:

```bash
docker exec -w /app plann_backend python -m pytest tests/integration/ -q
```

AI için kalıcı talimat: `.cursor/rules/api-contract.mdc` (alwaysApply). Her oturumda okunur.

---

## 3. Cache Invalidation Matrisi

Redis cache decorator: `backend/cache.py` (`@cache_result(prefix=..., ttl=...)`), key pattern
`plann:org_{org_id}:{prefix}`. Bir mutation olduğunda ilgili prefix invalidate EDİLMELİ.

Eksik invalidation = performans değil, **VERİ TUTARLILIĞI** hatası (kullanıcı TTL boyunca bayat veri görür).

Mevcut cache'ler ve onları bozması gereken olaylar:

- `dashboard_stats` (ttl 60s):
  - randevu create / update / delete / bulk / cancel / public booking / auto-complete
  - ödeme başarılı (merchant checkout payment-success)
- `customers_list` (varsa):
  - randevu create/delete (yeni telefon -> yeni müşteri), müşteri update
- (Gelecek) legacy `/customers` Redis cache eklenirse: yukarıdaki TÜM olaylar + onboarding test müşterisi + customer merge.

Kural: Yeni bir cache eklerken, onu bozan olayların tam listesini BURAYA ekle. Yeni bir mutation
endpoint'i eklerken, hangi cache prefix'lerini invalidate etmesi gerektiğini BURADAN kontrol et.

---

## 4. Sürüm Politikası (Force-Update)

- `min_supported_version` ve `latest_version` DB'de (`app_config` koleksiyonu, `_id="global"`) tutulur;
  **platform bazlı**: `{ "ios": "x.y.z", "android": "x.y.z" }`. Deploy'suz bumplanabilir.
- Backend sadece SİNYAL verir (`GET /api/app/config`, PUBLIC/auth'suz). İsteği HARD-REJECT ETME
  (yoksa korumaya çalıştığımız eski build'i kırarsın). Kilidi UX katmanı (frontend modal) uygular.
- Frontend: `CapacitorApp.getInfo()` + `appStateChange` ile açılışta + öne gelince kontrol
  (`frontend/src/App.js` `checkAppVersion`, util `frontend/src/lib/versionCheck.js`, UI
  `components/ForceUpdateModal.js`). `min_supported` altı -> kapatılamayan modal + store linki;
  `latest` altı -> kapatılabilir uyarı (oturum içi 1 kez). Yalnız native'de çalışır (web hep günceldir).
  **Fail-open**: config/getInfo/parse başarısızsa kullanıcıyı ASLA kilitleme (kapı açılmaz).

### Force-update endpoint'i (`GET /api/app/config`) — DONMUŞ (v1)

```bash
# Oku (public):
curl -s https://plannapp.co/api/app/config
# → {"min_supported_version":{"ios","android"},"latest_version":{...},"store_urls":{...}}
```

Doküman yoksa güvenli defaults döner (`min_supported=0.0.0` → kimseyi kilitleme). Contract v1:
alan SİLME/RENAME yasak, EKLEME güvenli. Kaynak: `backend/server.py` (`get_app_config`).

**Deploy'suz sürüm bump — birincil yöntem: Süper Admin paneli.**
`Süper Admin → Sürüm Yönetimi` (`components/superadmin/SAAppVersion.js`) sekmesinden iOS/Android için
`min_supported` + `latest` + store linki görünür şekilde düzenlenir, "Kaydet" ile anında geçerli olur.
Kritik uyarı kartı panelde de var (min_supported'ı yükseltmenin sahadaki eski kullanıcıları kilitlediği).
Bu, "curl'de unutulan komut" riskini ortadan kaldırır. Alternatif (curl):

```bash
curl -X PUT https://plannapp.co/api/superadmin/app-config \
  -H "Authorization: Bearer <SUPERADMIN_TOKEN>" -H "Content-Type: application/json" \
  -d '{"min_supported_version":{"ios":"6.0"},"latest_version":{"ios":"6.1"}}'
```

Kısmi güncelleme: yalnız gönderilen platform alanları yazılır (dot-path `$set`, upsert). Store URL'leri
de aynı endpoint'ten `store_urls:{ios,android}` ile güncellenebilir. **"Sıfırıncı build" uyarısı:**
sahadaki mevcut build'lerde version-check kodu YOK → force-update yalnız bundan SONRAKİ (v6.1+) build'leri
etkiler; `min_supported`'ı bu build'lerden ÖNCEKİ bir sürüme set etme (kimse güncelleyemez, ama modal da
göremez → etkisiz). Doğru kullanım: v6.1 popülasyona yayıldıktan sonra `min_supported.ios` yavaşça yükselt.

### Her mobil release'de sürüm bump ZORUNLU

- iOS: `frontend/ios/App/App.xcodeproj/project.pbxproj` -> `MARKETING_VERSION` + `CURRENT_PROJECT_VERSION`.
- Android: `frontend/android/app/build.gradle` -> `versionName` + `versionCode`.
- **Android bump GİT'te yapılır** (PC'de değil). Aksi halde git'teki sürüm ile Play Store'daki
  sürüm drift eder ve force-update politikası yanlış kullanıcıyı kilitler.
  - **SSOT senkronu yapıldı (Ağu 2026):** PC'deki canlı Android projesi git'e alındı. Git artık
    gerçekle uyumlu — canlı Play Store sürümü `3.1/31`, git bir sonraki release için `3.2/32`.
    Ayrıca senkronda git'e taşınanlar: `variables.gradle` compile/target SDK `35→36`,
    `build.gradle` AGP `8.2.1→8.13.2`, gradle wrapper `8.2.1→8.13`, `AndroidManifest.xml`
    izinleri (READ/WRITE_CONTACTS, VIBRATE, RECORD_AUDIO), ve capacitor plugin include'ları
    (contacts, speech-recognition, text-to-speech, haptics, status-bar).
  - Bundan sonra her Android release'inde `versionCode`/`versionName` git'te bir artırılır;
    PC yalnızca `git pull` + AAB alır (build.gradle'a PC'de DOKUNULMAZ).

---

## 5. Release Pipeline

### iOS (otomatik — Codemagic)

`codemagic.yaml` -> workflow `ios-capacitor-workflow`:
1. Burada düzenle -> git push.
2. Codemagic: `npm install` -> `npm run build` -> `npx cap sync ios` -> `pod install` -> `build-ipa`.
3. `submit_to_testflight: true`, `submit_to_app_store: false` -> TestFlight'a düşer.
4. App Store'a terfi MANUEL. Review ~2 gün + kullanıcı adoption'ı haftalar sürer.

### Android (Codemagic — Ağu 2026'da otomatikleşti)

`codemagic.yaml` -> workflow `android-capacitor-workflow` (`mac_mini_m2`):
1. Burada düzenle (versionCode/Name git'te bump) -> git push.
2. Codemagic'te workflow'u MANUEL başlat (otomatik trigger YOK — her commit AAB üretmesin diye).
3. Adımlar: `npm install --legacy-peer-deps` -> `npm run build` -> `npx cap sync android` ->
   **JDK 21 seç** (`/usr/libexec/java_home -v 21`; Capacitor 7 `@capacitor/android` v7 modülü Java 21
   ZORUNLU kılar — PC'de Android Studio JBR 21 kullandığı için görünmüyordu) -> keystore'u
   `local.properties`'e yaz -> `./gradlew bundleRelease -Dorg.gradle.java.home=... --no-daemon`.
4. İmza: keystore Codemagic env'de base64 (`CM_KEYSTORE` + `CM_KEYSTORE_PASSWORD`/`CM_KEY_ALIAS`/
   `CM_KEY_PASSWORD`, grup `android_secrets`). `app/build.gradle`'da KOŞULLU `signingConfig`
   (local.properties varsa uygular; PC'de yoksa Android Studio sihirbazı bozulmaz).
5. Şu an sonuç **email ile AAB** olarak gelir; Play'e MANUEL yüklenir.

- **YAPILACAK (android-play-publish):** `publishing.email` yerine `publishing.google_play`
  (`credentials: $GCLOUD_SERVICE_ACCOUNT_CREDENTIALS`, `track: internal|production`,
  `submit_as_draft`) ile DOĞRUDAN Play Store'a publish. Google Play service account JSON'u
  Codemagic env'e eklemek gerekir. Bitince manuel yükleme adımı da kalkar.
- Eski manuel yol (yedek): PC'de temiz `git pull` -> Android Studio -> AAB -> Play Store.

### OTA (Capgo — manuel entegrasyon, `@capgo/capacitor-updater@7`)

Web (JS/CSS/HTML) değişikliklerini App Store/Play review beklemeden telefonlara push etmek için.
**SADECE web bundle güncellenir** — native kod (plugin ekleme, izin, native ayar) değişirse OTA YETMEZ,
yeni store build'i şart.

- **Kurulum (yapıldı):** `@capgo/capacitor-updater` kuruldu; `capacitor.config.json` -> `plugins.CapacitorUpdater`
  (`autoUpdate: true`, `appReadyTimeout: 10000`); `App.js` mount'ta `CapacitorUpdater.notifyAppReady()`
  (native). Android native bağlandı (`cap update android`), iOS Codemagic'te `cap sync ios` ile bağlanır.
- **notifyAppReady KRİTİK:** çağrılmazsa Capgo bundle'ı bozuk sayıp `appReadyTimeout` (10s) sonrası son
  sağlam sürüme geri döner (otomatik rollback). App.js'teki useEffect'i SİLME.
- **Kanal politikası:** önce `internal` (sadece test cihazları). Doğrulanınca `production`'a promote.
- **Yayın komutları** (API key gizli, Codemagic/lokal env'den; repoya YAZMA):
  ```bash
  cd frontend
  npm run build                                             # build/ üret
  npx @capgo/cli@latest bundle upload -a "$CAPGO_TOKEN" \
      -c internal --path ./build                            # internal kanala yükle
  # Test cihazını internal kanala bağla (bir kez): dashboard'dan cihaz -> internal
  # Doğrulandıktan sonra production'a taşı:
  npx @capgo/cli@latest bundle upload -a "$CAPGO_TOKEN" -c production --path ./build
  ```
- **Sürüm uyumu:** OTA bundle'ın native uyumu package.json version'a göre eşleşir; native değişiklik olan
  release'lerde OTA push etme, store build bekle.

### "Sıfırıncı build" gerçeği

Sahadaki mevcut build'lerde force-update / OTA kodu YOK. Bu yüzden force-update yayınlandığında bile
yalnızca ONDAN SONRAKİ build'leri kontrol eder. Legacy contract freeze, mevcut popülasyon güncelleyene
kadar kalmak zorunda.

---

## 6. Rollback Prosedürü

- Backend: hatalı deploy'da önceki image'a dön. `docker compose build` yerine bilinen iyi git commit'e
  checkout -> yeniden build -> up. (Öneri: her deploy öncesi `git rev-parse HEAD` not al.)
- OTA (Capgo — kuruldu): bozuk bundle -> `notifyAppReady` çağrılmazsa `appReadyTimeout` (10s) sonrası son
  sağlam sürüme otomatik fallback. Prod'a açmadan önce `internal` kanalda rollback davranışı test EDİLMELİ.

---

## 7. Bilinen Durumlar / Tuzaklar

- İki paralel FastAPI app var: `server.py` (production) ve `app/main.py` (refaktör). Production `server.py`.
- `server.py` monolitik (~14k satır). Yeni endpoint eklerken mevcut pattern'e uy.
- Para birimleri minor unit (kuruş/pence). Gösterimde `formatMoney`.
- Backend `docker restart` != deploy (Bölüm 1).
- Yeni test dosyaları container'a otomatik girmez (volume mount yok); ya rebuild ya `docker cp` ile geçici kopyala.
