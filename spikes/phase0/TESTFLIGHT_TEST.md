# Phase 0 — Mac'siz test (Codemagic → TestFlight → iOS 26 cihaz)

Bu build yalnızca test amaçlıdır. **App Store incelemesine göndermeyin.**
- Sürüm: **6.4.90**, build numarası 1000 + Codemagic build no.
- Production sürüm trenine dokunmaz.

## 1. Build al

1. Codemagic'te depo için **"PLANN iOS SPIKE Phase0 Live Activities (TestFlight only)"** iş akışını seçin.
2. Dal olarak **`spike/phase0-live-activities`** seçin ve **Start new build**'e basın.
3. Başarısız olursa logu bana iletin. Özellikle şu iki adımın çıktısı lazım:
   - "Widget extension profili (yoksa oluştur)": S4 imza sonucu;
   - "IPA içeriği (S4 kanıtı)": appex IPA'da mı.
4. Başarılıysa TestFlight'ta 6.4.90 görünür (işlenmesi 5–15 dk sürebilir).

> TestFlight build'i, telefondaki App Store PLANN uygulamasının **yerine** kurulur. Testten sonra App Store'dan tekrar yükleyebilirsiniz.

## 2. Test ekranını aç

Safari'nin adres çubuğuna `plannapp://la-spike` yazın ve "Aç" deyin. Siyah bir test ekranı açılır.

| Buton | İşi |
|---|---|
| **Tokenları kopyala** | FCM token + push-to-start token panoya gelir → **sohbete yapıştırın**. Push'ları ben gönderirim. |
| **1 LA başlat (2 dk sonra)** | Yerel Live Activity başlatır. Geri sayım çalışmalı; 2 dk sonra kendiliğinden ileri saymaya geçmeli. |
| **12 LA başlat (S3 limit)** | Sistem limitini ölçer. Sonuç "Başlatılan: x/12" olarak görünür. |
| **Tüm LA'ları bitir** | Hepsini kapatır. |
| **Logu paylaş** | Durum + log metnini paylaşır (Notlar / mesaj) → **sohbete yapıştırın**. |

## 3. Test sırası

1. **Hazırlık:** ekranı açın, ardından **Tokenları kopyala** → sohbete yapıştırın. `push_to_start_token` "nil" görünürse uygulamayı tamamen kapatıp yeniden açın ve tekrar kopyalayın.
2. **S1 (uygulama açık):** "hazırım" deyin. Ben sunucudan push-to-start gönderirim. Kilit ekranında ve Dynamic Island'da "Spike K. · Saç Kesimi" görünmeli. Ne zaman göründüğünü yazın.
3. **S2-B (arka plan):** Ana ekrana dönün, uygulamayı kapatmayın, "hazırım" deyin. Ben ikinci push'u gönderirim.
4. **S2-C (zorla kapatma):** uygulamayı uygulama değiştiriciden yukarı kaydırarak kapatın, "hazırım" deyin. Ben üçüncü push'u gönderirim.
5. **Güncelleme/bitirme:** uygulamayı açın, **Logu paylaş** → sohbete yapıştırın. Logdaki aktivite token'larıyla "İşlemde" güncellemesini ve iptal bitirmesini gönderirim. Ekranda karşılıklarını görmelisiniz (`v2`, kırmızı çubuk, kayboluş).
6. **S3 (limit):** **Tüm LA'ları bitir** → **12 LA başlat** → çıkan sayıyı yazın. Ardından Saat uygulamasında bir zamanlayıcı başlatıp tekrarlayın.
7. **Temizlik:** **Tüm LA'ları bitir**, ardından App Store'dan PLANN'ı yeniden yükleyin.

Her adımda gördüğünüzü kısaca yazmanız yeterli: "göründü / görünmedi / x saniye sonra".
