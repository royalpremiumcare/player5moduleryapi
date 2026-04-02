# PLANN GÜVENLİK  
##   
## 🛡️** PLANN Akıllı Savunma ve Doğrulama Modeli**  
**1. Giriş Katmanı: Sessiz Muhafızlar (Spam Koruması)**  
Sistem daha müşteri telefon numarasını girmeden arka planda çalışmaya başlar:  
• **Görünmez Captcha (Cloudflare Turnstile):** Sayfada bot olmadığını, gerçek bir insan olduğunu %99 sessizce (bulmaca çözdürmeden) doğrular.  
• **IP-Tabanlı Rate Limit:** Aynı IP adresinden 12 saat içinde en fazla **2 randevu** alınabilir. Bu, Ahmet’in (veya bir botun) seri şekilde 50 tane sahte randevu basmasını bedavaya engeller.  
**2. Akıllı Filtreleme: "Tanıdık Müşteri" Sorgusu**  
Sistem, maliyeti sıfıra indirmek ve sadık müşteriyi yormamak için veritabanını tarar:  
• **Admin Listesi Kontrolü:** Eğer girilen numara, işletmenin "Müşteriler" listesinde zaten kayıtlıysa veya daha önce sistemden onaylı bir randevu almışsa; **"Bu bizden biri"** denir.  
• **Sonuç:** Bu müşteriye asla WhatsApp doğrulama kodu sorulmaz. Randevu direkt onaylanır. **Maliyet: 0 TL.**  
**3. Coğrafi Zeka: IP ve Numara Uyumu (TR & UK)**  
Uygulamanın global yapısını korumak için en kritik filtre burası:  
• **Ülke Eşleşmesi:** Girilen telefon kodunun (+90 veya +44) IP adresiyle uyumuna bakılır.  
• **Senaryo:** +44 (UK) numara giriliyor ama IP İngiltere dışındaysa veya +90 numara giriliyor ama IP Türkiye dışındaysa; sistem bunu **"Yüksek Risk"** olarak işaretler.  
• **Zorunlu Onay:** Bu eşleşme sağlanamazsa veya numara sistemde ilk kez görülüyorsa; **WhatsApp Doğrulaması** (WhatsApp ile Onayla butonu) zorunlu hale gelir.  
**4. Doğrulama Mekanizması: "WhatsApp Hack" (Girdi Kontrolü)**  
Diyelim ki Ahmet public sayfaya girdi, kendi adı Ahmet ama gıcıklık olsun diye numara kısmına Mehmet'in numarasını (0555 555 55 55) yazdı ve "Randevu Al"a bastı.  
**1. Adım:** Sistem **Mehmet'e mesaj falan atmaz.** Ekranda Ahmet'e şu yazıyı çıkarır:  
*"Randevunuzu onaylamak için aşağıdaki butona tıklayın ve WhatsApp üzerinden bize otomatik onay kodunu gönderin."* [ WhatsApp'ı Aç ve Onayla ]  
**2. Adım:** Ahmet mecburen butona tıklar. Telefonunda (veya bilgisayarında) **kendi orijinal WhatsApp'ı** açılır. Ekranda senin sistemine gönderilmek üzere hazır bekleyen şu mesaj vardır: *"Randevu onayı: RND-8374"* **3. Adım:** Ahmet "Gönder"e basar.  
**İŞTE BÜYÜ BURADA BAŞLIYOR:** Senin sunucuna (Webhook'a) Ahmet'ten mesaj gelir. Sunucun bakar:  
* *"Hmm, RND-8374 kodlu randevu formda 0555'li (Mehmet'in) numarayla doldurulmuş."*  
* *"Ama bana bu kodu gönderen WhatsApp hesabının numarası 0532'li (Ahmet'in gerçek numarası!)."*  
**Sonuç:** Uyuşmazlık var! Sistem Ahmet'in girdiği sahte numarayı (Mehmet'i) çöpe atar, randevuyu **mesajı gönderen gerçek numaraya (Ahmet'e)** günceller ve onaylar.  
* Mehmet hiç rahatsız edilmedi.  
* Senin cebinden boşuna giden bir WhatsApp mesajı parası çıkmadı.  
* Ahmet kendi kazdığı kuyuya düştü ve kendi gerçek numarasını kendi elleriyle sana teslim etmiş oldu.  
  
Numara ilk kez geliyorsa ve güvenli listede değilse:  
• **Müşteri Mesaj Atar:** Müşteri butona tıklar ve kendi WhatsApp'ından işletme hattına hazır bir onay kodu gönderir.  
• **Numara Teyidi:** Sistem, formu dolduran numara ile mesajı atan WhatsApp numarasının aynı olduğunu teyit eder.  
• **Avantajı:** Sahte numara girişini %100 bitirir. Üstelik müşteri ilk mesajı atan taraf olduğu için Meta'nın **aylık 1.000 ücretsiz mesaj** kotasından yararlanırsın.  
**5. İşletme Kontrolü: Esnek / Güvenli Mod Seçeneği**  
Tüm bu sistemi işletme sahibinin tercihine bırakıyoruz (Sorumluluk transferi):  
• **Esnek Mod:** İşletme "Müşterilerim yorulmasın, kim gelirse onaylansın" derse güvenlik duvarlarını gevşetir. Ancak kota suistimalinden sen sorumlu olmazsın.  
• **Güvenli Mod:** Yukarıdaki tüm filtreler (IP eşleşme, yeni numara sorgusu vb.) aktif olur. Sadece gerçek ve doğrulanmış müşteriler randevu alabilir.  
  
  


---

## 🔑 Cloudflare Turnstile Anahtarları
- **Site Key (frontend):** `0x4AAAAAACuhfhSBvGXOLpdW`
- **Secret Key:** `.env` dosyasına `TURNSTILE_SECRET_KEY` olarak eklendi (git'e commit edilmez)
