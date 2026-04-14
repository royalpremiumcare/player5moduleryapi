export const faqData = {
  tr: {
    // ===================================================================
    // 👑 ADMIN (İŞLETME SAHİBİ) İÇİN SIK SORULAN SORULAR
    // ===================================================================
    admin: [
      // --- BAŞLANGIÇ ---
      {
        id: "admin-1",
        question: "❓ PLANN'ı kullanmaya nasıl başlarım?",
        answer: "Panelinize ilk giriş yaptığınızda karşınıza çıkan <strong>Kurulum Sihirbazı</strong> (Setup Wizard) en hızlı yoludur. Orada hizmetlerinizi, fiyatlarınızı ve genel çalışma saatlerinizi 2 dakikada ayarlayabilirsiniz."
      },
      {
        id: "admin-2",
        question: "🔗 Müşterilerim benden nasıl online randevu alabilir?",
        answer: "<strong>Ayarlar > İşletme Bilgileri</strong> sayfasına gidin. Orada size özel <strong>'Randevu Linkiniz'</strong> (örn: plannapp.co/isletme-adi) bulunmaktadır. Bu linki kopyalayıp Instagram profilinize, Google My Business sayfanıza veya müşterilerinize gönderebilirsiniz. Müşteriler bu link üzerinden hizmet, tarih ve saat seçerek randevu oluşturabilir."
      },

      // --- ABONELİK & FATURALANDIRMA ---
      {
        id: "admin-3",
        question: "💳 Deneme sürem bitiyor, nasıl abone olabilirim?",
        answer: "<strong>Ayarlar > Abonelik & Faturalandırma</strong> bölümüne gidin. İşletmenize en uygun paketi (Başlangıç, Standart, Profesyonel, Premium, İşletme, Kurumsal) seçerek aboneliğinizi başlatabilirsiniz. Ödeme Stripe altyapısı ile güvenle işlenir."
      },

      // --- HİZMET YÖNETİMİ ---
      {
        id: "admin-4",
        question: "✂️ Yeni bir hizmet nasıl eklerim?",
        answer: "<strong>Ayarlar > Hizmet Yönetimi</strong> sayfasına gidin. <strong>[ + Yeni Hizmet Ekle ]</strong> butonuna basın. Hizmetin adını, fiyatını ve <strong>Hizmet Süresini (Dakika)</strong> girin. Ayrıca ödeme kuralı belirleyebilirsiniz: <strong>Mağazada Ödeme</strong>, <strong>Tamamı Online</strong> (min. 300₺) veya <strong>Kapora</strong> (min. 200₺ sabit tutar). Bu sayede müşterilerinizden online ön ödeme alabilirsiniz."
      },
      {
        id: "admin-5",
        question: "💡 Online ödeme ve kapora sistemi nasıl çalışır?",
        answer: "Hizmet eklerken veya düzenlerken ödeme kuralını ayarlarsınız:<br/><br/>• <strong>Mağazada Ödeme:</strong> Müşteri mağazada öder, online ödeme yoktur.<br/>• <strong>Tamamı Online:</strong> Müşteri randevu alırken tutarın tamamını online öder (hizmet tutarı min. 300₺ olmalıdır).<br/>• <strong>Kapora:</strong> Müşteri sabit bir kapora tutarı öder (min. 200₺), kalan mağazada ödenir.<br/><br/>Online ödemeler <strong>Stripe</strong> üzerinden güvenle işlenir ve bakiyeniz <strong>Cüzdan</strong> bölümünde görünür."
      },

      // --- PERSONEL YÖNETİMİ ---
      {
        id: "admin-6",
        question: "👥 Yeni bir personeli sisteme nasıl davet ederim?",
        answer: "<strong>Ayarlar > Personel Yönetimi</strong> sayfasına gidin. <strong>[ + Personel Davet Et ]</strong> butonuna basın. Personelinizin adını ve e-posta adresini girin. Sistem, personelinize kendi şifresini belirlemesi için bir <strong>davet e-postası</strong> gönderecektir. Her personelin kendi paneli olur ve sadece kendi randevularını görebilir."
      },

      // --- TAKVİM & RANDEVU ---
      {
        id: "admin-7",
        question: "📅 Takvim nasıl çalışır?",
        answer: "Takvim haftalık görünümdedir ve tüm personelin randevularını renkli bloklarla gösterir. <strong>Geçen Hafta / Bu Hafta / Gelecek Hafta</strong> butonlarıyla hızlıca gezebilirsiniz. Her randevu bloğuna tıklayarak detayları görebilir, düzenleyebilir veya iptal edebilirsiniz. Mobilde de tam uyumlu çalışır."
      },
      {
        id: "admin-8",
        question: "➕ Yeni bir randevu nasıl oluştururum?",
        answer: "<strong>[ + Randevu Ekle ]</strong> butonuna veya alttaki büyük <strong>[ + ]</strong> butonuna basın. 3 adımlı sihirbazda sırasıyla hizmet, müşteri ve tarih/saat seçersiniz. Mevcut müşteri yoksa anında yeni müşteri oluşturabilirsiniz. Randevu oluşturulduğunda müşteriye otomatik <strong>WhatsApp hatırlatma mesajı</strong> gönderilir."
      },

      // --- MÜŞTERİ YÖNETİMİ ---
      {
        id: "admin-9",
        question: "👤 Müşteri listemi nasıl yönetirim?",
        answer: "<strong>Müşteriler</strong> sekmesinden tüm müşterilerinizi görebilirsiniz. Her müşterinin geçmiş randevularını, toplam harcamasını ve notlarını görüntüleyebilirsiniz. Müşteri arama ile hızlıca istediğiniz kişiyi bulabilirsiniz. Ayrıca müşteri profilinden <strong>not ekleyebilir</strong> ve geçmiş randevuları inceleyebilirsiniz."
      },

      // --- SEANS PLANLAMA ---
      {
        id: "admin-10",
        question: "📋 Seans planlama özelliği ne işe yarar?",
        answer: "Seans planlama, birden fazla seans gerektiren hizmetler (örn: lazer epilasyon, diş tedavisi serisi) için tasarlanmıştır. Müşteriye toplam seans sayısını belirleyerek <strong>seans paketi</strong> oluşturursunuz. Her randevu tamamlandığında kalan seans sayısı otomatik güncellenir. Böylece müşterinizin kaçıncı seansında olduğunu takip edebilirsiniz."
      },

      // --- CÜZDAN & FİNANS ---
      {
        id: "admin-11",
        question: "💰 Cüzdan (Merchant Wallet) nasıl çalışır?",
        answer: "Online ödemeler (Stripe üzerinden gelen) otomatik olarak cüzdanınıza eklenir. <strong>~2 iş günü</strong> sonra kullanılabilir bakiyeye geçer. Bakiyeniz yeterli olduğunda <strong>Ödeme Çek</strong> butonu ile paranızı banka hesabınıza çekebilirsiniz. Ödemeler <strong>Wise</strong> üzerinden 1-2 iş günü içinde hesabınıza ulaşır."
      },
      {
        id: "admin-12",
        question: "🏦 IBAN bilgilerimi nasıl girerim?",
        answer: "<strong>Cüzdan</strong> sayfasında banka bilgileri bölümünde IBAN'ınızı girebilirsiniz. Güvenlik amacıyla, IBAN değişikliği sonrası <strong>48 saatlik bekleme süresi</strong> uygulanır. İlk IBAN girişinde bekleme süresi yoktur. IBAN doğrulandıktan sonra otomatik ve manuel ödeme çekimleri yapabilirsiniz."
      },
      {
        id: "admin-13",
        question: "💸 Kasa (Finans) modülü nasıl çalışır?",
        answer: "Kasa, gelirinizi <strong>otomatik</strong> toplar. Bir randevu 'Tamamlandı' olarak işaretlendiğinde, hizmet bedeli kasanıza 'Gelir' olarak işlenir. <strong>Giderler</strong> sekmesinden kira, fatura, malzeme gibi harcamalarınızı girebilirsiniz. <strong>Personel Hakedişleri</strong> sekmesinden personele avans/maaş ödemesi yapabilirsiniz — ödeme hem personelin bakiyesinden düşer hem de kasadan 'Gider' olarak çıkar."
      },

      // --- ÖDEME AYARLARI ---
      {
        id: "admin-14",
        question: "⚙️ Ödeme ayarlarını nasıl yapılandırırım?",
        answer: "<strong>Ayarlar > Ödeme Ayarları</strong> bölümünde:<br/><br/>• <strong>Otomatik Ödeme:</strong> Bakiyeniz belirlediğiniz limite ulaştığında otomatik olarak banka hesabınıza gönderilir.<br/>• <strong>Manuel Ödeme:</strong> Cüzdandan dilediğiniz zaman 'Ödeme Çek' butonu ile çekim yaparsınız.<br/><br/>İade penceresi ilk <strong>12 saat</strong> içinde aktiftir. Bu süre içinde müşteriye iade yapılabilir."
      },

      // --- DASHBOARD & İSTATİSTİK ---
      {
        id: "admin-15",
        question: "📊 Dashboard'da ne görürüm?",
        answer: "Dashboard'da günlük özet bilgilerinizi görürsünüz:<br/><br/>• <strong>Bugünün Akışı:</strong> Günün tüm randevuları saat sırasıyla<br/>• <strong>Hızlı İstatistikler:</strong> Bugünkü/haftalık/aylık toplam randevu ve ciro<br/>• <strong>Yaklaşan Randevular:</strong> Sonraki randevularınız<br/>• <strong>Müşteri İstatistikleri:</strong> Toplam müşteri sayısı ve yeni müşteriler"
      },

      // --- BİLDİRİMLER ---
      {
        id: "admin-16",
        question: "🔔 Bildirimler nasıl çalışır?",
        answer: "PLANN iki tür bildirim gönderir:<br/><br/>• <strong>Push Bildirimleri:</strong> Yeni randevu, iptal veya değişiklik olduğunda anlık bildirim alırsınız.<br/>• <strong>WhatsApp Hatırlatma:</strong> Müşterilere randevu saatinden önce otomatik WhatsApp mesajı gönderilir.<br/><br/>Bildirimler çalışmıyorsa <strong>Ayarlar > Bildirimler > Sorun Giderici</strong> butonunu kullanın."
      },

      // --- AI CHATBOT ---
      {
        id: "admin-17",
        question: "🤖 AI Asistan (Chatbot) ne işe yarar?",
        answer: "Panel içindeki <strong>AI Asistan</strong> size işletmeniz hakkında sorulara yanıt verir. Günlük ciro, en popüler hizmet, müşteri istatistikleri gibi konularda anında bilgi alabilirsiniz. Asistan, işletmenizin verilerine göre kişiselleştirilmiş yanıtlar üretir."
      },

      // --- ONLINE RANDEVU SAYFASI ---
      {
        id: "admin-18",
        question: "🌐 Müşterilerimin gördüğü online randevu sayfasını özelleştirebilir miyim?",
        answer: "<strong>Ayarlar > Online Randevu Ayarları</strong> bölümünden randevu sayfanızın görünümünü özelleştirebilirsiniz. İşletme logosu, çalışma saatleri ve hizmet listesi otomatik olarak sayfanızda gösterilir. Müşteriler hizmet, personel, tarih ve saat seçerek kolayca randevu alabilir."
      },

      // --- GÜVENLİK ---
      {
        id: "admin-19",
        question: "🔒 Verilerim güvende mi?",
        answer: "Evet, PLANN en yüksek güvenlik standartlarını kullanır:<br/><br/>• <strong>SSL/HTTPS</strong> şifreli bağlantı<br/>• <strong>Stripe PCI-DSS</strong> uyumlu ödeme altyapısı<br/>• <strong>Wise</strong> ile güvenli uluslararası para transferi<br/>• <strong>JWT</strong> tabanlı kimlik doğrulama<br/>• <strong>Sentry</strong> ile hata takibi<br/>• Tüm veriler şifrelenmiş MongoDB veritabanında saklanır"
      },

      // --- İLETİŞİM ---
      {
        id: "admin-20",
        question: "📞 Destek ekibine nasıl ulaşabilirim?",
        answer: "Bize iki yoldan ulaşabilirsiniz:<br/><br/>• <strong>Telefon:</strong> +90 540 595 3250<br/>• <strong>WhatsApp:</strong> +90 540 595 3250 numarasından bize yazabilirsiniz.<br/><br/>Ayrıca <strong>Ayarlar > Diğer > İletişim</strong> veya <strong>WhatsApp Destek</strong> butonlarını kullanarak doğrudan bize ulaşabilirsiniz."
      }
    ],

    // ===================================================================
    // 👤 PERSONEL İÇİN SIK SORULAN SORULAR
    // ===================================================================
    personnel: [
      {
        id: "personnel-1",
        question: "✉️ Bana bir davet e-postası geldi, şimdi ne yapmalıyım?",
        answer: "İşletme sahibiniz sizi PLANN sistemine davet etti. Lütfen e-postadaki <strong>[ Şifremi Belirle ]</strong> linkine tıklayın. Güvenli bir şifre belirlediğiniz an hesabınız aktif olacak ve panele giriş yapabileceksiniz."
      },
      {
        id: "personnel-2",
        question: "🗓️ Bugünkü veya yarınki programımı nerede görebilirim?",
        answer: "<strong>Anasayfa (Dashboard)</strong> ekranındaki <strong>'Bugünün Akışı'</strong> kartında güncel programınızı görebilirsiniz. Tüm programınızı (geçmiş ve gelecek) görmek için <strong>Takvim</strong> sekmesine tıklayın. Takvim, sadece <strong>size atanmış</strong> randevuları gösterir."
      },
      {
        id: "personnel-3",
        question: "➕ Yeni bir randevuyu nasıl eklerim?",
        answer: "Panelin altındaki büyük <strong>[ + ]</strong> butonuna basın. 3 adımlı sihirbazda 'Hizmet', 'Müşteri' ve 'Saat' seçmeniz yeterlidir. Personel alanı otomatik olarak size kilitlenmiştir. Mevcut müşteri yoksa anında yeni müşteri oluşturabilirsiniz."
      },
      {
        id: "personnel-4",
        question: "📊 Bugün ne kadar kazandırdığımı görebilir miyim?",
        answer: "Evet. <strong>Anasayfa (Dashboard)</strong> ekranınızdaki <strong>'Hızlı Bakış'</strong> kartı, o gün tamamladığınız randevuların toplam tutarını gösterir. Ayrıca haftalık ve aylık istatistiklerinizi de takip edebilirsiniz."
      },
      {
        id: "personnel-5",
        question: "✅ Randevuyu nasıl tamamlarım veya iptal ederim?",
        answer: "Takvimde veya Dashboard'daki listede ilgili randevuya tıklayın. Açılan detay ekranında <strong>'Tamamlandı'</strong> veya <strong>'İptal Et'</strong> butonlarını kullanabilirsiniz. Tamamlanan randevular otomatik olarak kasaya gelir olarak eklenir."
      },
      {
        id: "personnel-6",
        question: "👤 Müşteri bilgilerine erişebilir miyim?",
        answer: "Evet, <strong>Müşteriler</strong> sekmesinden kendi müşterilerinizin bilgilerini görebilirsiniz. Müşteri profilinde geçmiş randevuları, notları ve iletişim bilgilerini görüntüleyebilirsiniz."
      },
      {
        id: "personnel-7",
        question: "🔔 Bildirim almıyorum, ne yapmalıyım?",
        answer: "<strong>Ayarlar > Bildirimler</strong> bölümünden bildirimlerin açık olduğundan emin olun. Sorun devam ediyorsa <strong>Sorun Giderici</strong> butonuna tıklayarak bildirim izinlerini onarabilirsiniz. Tarayıcınızın bildirim izinlerinin de açık olduğundan emin olun."
      },
      {
        id: "personnel-8",
        question: "🔒 Şifremi nasıl değiştirebilirim?",
        answer: "<strong>Ayarlar > Profilim</strong> bölümünden şifrenizi güncelleyebilirsiniz."
      },
      {
        id: "personnel-9",
        question: "📞 Sorun yaşıyorum, destek ekibine nasıl ulaşırım?",
        answer: "<strong>Ayarlar > Diğer</strong> bölümündeki <strong>İletişim</strong> veya <strong>WhatsApp Destek</strong> butonlarını kullanarak bize ulaşabilirsiniz. Telefon: <strong>+90 540 595 3250</strong>"
      }
    ]
  },
  en: {
    // ===================================================================
    // 👑 ADMIN (BUSINESS OWNER) FAQ
    // ===================================================================
    admin: [
      {
        id: "admin-1",
        question: "❓ How do I get started with PLANN?",
        answer: "The <strong>Setup Wizard</strong> that appears when you first log in is the quickest way. There you can set up your services, prices, and general business hours in 2 minutes."
      },
      {
        id: "admin-2",
        question: "🔗 How can my customers book appointments online?",
        answer: "Go to <strong>Settings > Business Information</strong>. There you'll find your unique <strong>'Booking Link'</strong> (e.g., plannapp.co.uk/business-name). Share this link on your Instagram profile, Google My Business page, or send it directly to your customers. They can select a service, date, and time to book an appointment."
      },
      {
        id: "admin-3",
        question: "💳 My trial is ending, how can I subscribe?",
        answer: "Go to <strong>Settings > Subscription & Billing</strong>. Select the package that best suits your business (Starter, Standard, Professional, Premium, Business, Enterprise) to start your subscription. Payments are securely processed via Stripe."
      },
      {
        id: "admin-4",
        question: "✂️ How do I add a new service?",
        answer: "Go to <strong>Settings > Service Management</strong> and click <strong>[ + Add New Service ]</strong>. Enter the service name, price, and <strong>Service Duration (Minutes)</strong>. You can also set a payment rule: <strong>Pay at Venue</strong>, <strong>Full Online Payment</strong> (min. £15), or <strong>Deposit</strong> (min. £10 fixed amount). This allows you to collect online payments from customers."
      },
      {
        id: "admin-5",
        question: "💡 How does the online payment and deposit system work?",
        answer: "When adding or editing a service, you set the payment rule:<br/><br/>• <strong>Pay at Venue:</strong> Customer pays at the shop, no online payment.<br/>• <strong>Full Online:</strong> Customer pays the full amount when booking (min. service price applies).<br/>• <strong>Deposit:</strong> Customer pays a fixed deposit amount (min. £10), the rest is paid at the venue.<br/><br/>Online payments are securely processed via <strong>Stripe</strong> and your balance appears in the <strong>Wallet</strong> section."
      },
      {
        id: "admin-6",
        question: "👥 How do I invite a new staff member?",
        answer: "Go to <strong>Settings > Staff Management</strong> and click <strong>[ + Invite Staff ]</strong>. Enter their name and email address. The system will send an <strong>invitation email</strong> for them to set their password. Each staff member gets their own panel and can only see their own appointments."
      },
      {
        id: "admin-7",
        question: "📅 How does the calendar work?",
        answer: "The calendar shows a weekly view with all staff appointments as colour-coded blocks. Navigate quickly with <strong>Previous Week / This Week / Next Week</strong> buttons. Click any appointment block to view details, edit, or cancel. Fully responsive on mobile."
      },
      {
        id: "admin-8",
        question: "➕ How do I create a new appointment?",
        answer: "Click <strong>[ + Add Appointment ]</strong> or the large <strong>[ + ]</strong> button at the bottom. In the 3-step wizard, select a service, customer, and date/time. You can create a new customer on the fly. When an appointment is created, the customer automatically receives a <strong>WhatsApp reminder</strong>."
      },
      {
        id: "admin-9",
        question: "👤 How do I manage my customer list?",
        answer: "The <strong>Customers</strong> tab shows all your clients. View each customer's appointment history, total spend, and notes. Use the search bar to quickly find anyone. You can <strong>add notes</strong> to customer profiles and review their past appointments."
      },
      {
        id: "admin-10",
        question: "📋 What is the session planning feature?",
        answer: "Session planning is designed for services requiring multiple sessions (e.g., laser hair removal, dental treatment courses). You create a <strong>session package</strong> with a total session count. Each completed appointment automatically updates the remaining count, so you always know which session the customer is on."
      },
      {
        id: "admin-11",
        question: "💰 How does the Merchant Wallet work?",
        answer: "Online payments (via Stripe) are automatically added to your wallet. After <strong>~2 business days</strong>, they become available balance. When your balance is sufficient, use the <strong>Request Payout</strong> button to withdraw to your bank account. Payouts are sent via <strong>Wise</strong> and typically arrive within 1-2 business days."
      },
      {
        id: "admin-12",
        question: "🏦 How do I enter my bank details?",
        answer: "In the <strong>Wallet</strong> page, enter your bank details in the banking section. For security, a <strong>48-hour cooldown</strong> applies after changing bank details. There is no cooldown for your first entry. Once verified, you can make both automatic and manual payout requests."
      },
      {
        id: "admin-13",
        question: "💸 How does the Finance (Cash Register) module work?",
        answer: "The Finance module <strong>automatically</strong> tracks your revenue. When an appointment is marked 'Completed', the service fee becomes 'Revenue'. Enter manual expenses (rent, bills, supplies) in the <strong>Expenses</strong> tab. Use <strong>Staff Payroll</strong> to record advance/salary payments — the amount is deducted from the staff member's balance and recorded as an expense."
      },
      {
        id: "admin-14",
        question: "⚙️ How do I configure payment settings?",
        answer: "In <strong>Settings > Payment Settings</strong>:<br/><br/>• <strong>Automatic Payout:</strong> When your balance reaches the threshold you set, it's automatically sent to your bank.<br/>• <strong>Manual Payout:</strong> Withdraw anytime using the 'Request Payout' button in your Wallet.<br/><br/>The refund window is active for the first <strong>12 hours</strong>. Within this period, you can issue refunds to customers."
      },
      {
        id: "admin-15",
        question: "📊 What do I see on the Dashboard?",
        answer: "Your Dashboard shows daily summary information:<br/><br/>• <strong>Today's Flow:</strong> All of today's appointments in chronological order<br/>• <strong>Quick Stats:</strong> Daily/weekly/monthly appointment and revenue totals<br/>• <strong>Upcoming Appointments:</strong> Your next scheduled appointments<br/>• <strong>Customer Stats:</strong> Total customers and new customer count"
      },
      {
        id: "admin-16",
        question: "🔔 How do notifications work?",
        answer: "PLANN sends two types of notifications:<br/><br/>• <strong>Push Notifications:</strong> Instant alerts for new bookings, cancellations, or changes.<br/>• <strong>WhatsApp Reminders:</strong> Automatic messages sent to customers before their appointment time.<br/><br/>If notifications aren't working, use the <strong>Settings > Notifications > Troubleshooter</strong> button."
      },
      {
        id: "admin-17",
        question: "🤖 What does the AI Assistant do?",
        answer: "The in-panel <strong>AI Assistant</strong> answers questions about your business. Get instant insights on daily revenue, most popular services, customer statistics, and more. The assistant produces personalised responses based on your business data."
      },
      {
        id: "admin-18",
        question: "🌐 Can I customise my online booking page?",
        answer: "In <strong>Settings > Online Booking Settings</strong>, you can customise your booking page appearance. Your business logo, working hours, and service list are automatically displayed. Customers can easily select a service, staff member, date, and time to book."
      },
      {
        id: "admin-19",
        question: "🔒 Is my data secure?",
        answer: "Yes, PLANN uses the highest security standards:<br/><br/>• <strong>SSL/HTTPS</strong> encrypted connections<br/>• <strong>Stripe PCI-DSS</strong> compliant payment infrastructure<br/>• <strong>Wise</strong> for secure international money transfers<br/>• <strong>JWT</strong> based authentication<br/>• <strong>Sentry</strong> for error monitoring<br/>• All data stored in encrypted MongoDB database"
      },
      {
        id: "admin-20",
        question: "📞 How can I contact the support team?",
        answer: "You can reach us in two ways:<br/><br/>• <strong>Phone:</strong> +90 540 595 3250<br/>• <strong>WhatsApp:</strong> Message us at +90 540 595 3250<br/><br/>You can also use the <strong>Contact</strong> or <strong>WhatsApp Support</strong> buttons in <strong>Settings > Other</strong>."
      }
    ],

    // ===================================================================
    // 👤 STAFF FAQ
    // ===================================================================
    personnel: [
      {
        id: "personnel-1",
        question: "✉️ I received an invitation email, what should I do?",
        answer: "Your business owner has invited you to the PLANN system. Click the <strong>[ Set My Password ]</strong> link in the email. Once you set a secure password, your account will be activated and you can log in."
      },
      {
        id: "personnel-2",
        question: "🗓️ Where can I see my schedule?",
        answer: "The <strong>'Today's Flow'</strong> card on your <strong>Dashboard</strong> shows your current schedule. To see your full schedule (past and future), go to the <strong>Calendar</strong> tab. The calendar only shows appointments <strong>assigned to you</strong>."
      },
      {
        id: "personnel-3",
        question: "➕ How do I add a new appointment?",
        answer: "Click the large <strong>[ + ]</strong> button at the bottom. In the 3-step wizard, select 'Service', 'Customer', and 'Time'. The staff field is automatically locked to you. You can create a new customer on the fly if needed."
      },
      {
        id: "personnel-4",
        question: "📊 Can I see how much I've earned today?",
        answer: "Yes. The <strong>'Quick View'</strong> card on your <strong>Dashboard</strong> shows the total amount of appointments you completed that day. You can also track weekly and monthly statistics."
      },
      {
        id: "personnel-5",
        question: "✅ How do I complete or cancel an appointment?",
        answer: "Click the appointment in the calendar or Dashboard list. In the detail screen, use the <strong>'Completed'</strong> or <strong>'Cancel'</strong> buttons. Completed appointments are automatically recorded as revenue."
      },
      {
        id: "personnel-6",
        question: "👤 Can I access customer information?",
        answer: "Yes, the <strong>Customers</strong> tab lets you view your clients' details. You can see their appointment history, notes, and contact information."
      },
      {
        id: "personnel-7",
        question: "🔔 I'm not receiving notifications, what should I do?",
        answer: "Go to <strong>Settings > Notifications</strong> and make sure they're enabled. If the issue persists, click the <strong>Troubleshooter</strong> button to repair notification permissions. Also check that your browser's notification permissions are enabled."
      },
      {
        id: "personnel-8",
        question: "🔒 How can I change my password?",
        answer: "Go to <strong>Settings > My Profile</strong> to update your password."
      },
      {
        id: "personnel-9",
        question: "📞 I'm having issues, how do I contact support?",
        answer: "Use the <strong>Contact</strong> or <strong>WhatsApp Support</strong> buttons in <strong>Settings > Other</strong>. Phone: <strong>+90 540 595 3250</strong>"
      }
    ]
  }
};
