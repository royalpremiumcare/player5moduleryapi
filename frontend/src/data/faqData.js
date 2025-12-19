export const faqData = {
  tr: {
    // ===================================================================
    // 👑 ADMIN (İŞLETME SAHİBİ) İÇİN SIK SORULAN SORULAR (SIRALAMA GÜNCELLENDİ)
    // ===================================================================
    admin: [
      {
        id: "admin-1",
        question: "❓ PLANN'ı kullanmaya nasıl başlarım?",
        answer: "Panelinize ilk giriş yaptığınızda karşınıza çıkan <strong>Kurulum Sihirbazı</strong> (Setup Wizard) en hızlı yoludur. Orada hizmetlerinizi, fiyatlarınızı ve genel çalışma saatlerinizi 2 dakikada ayarlayabilirsiniz."
      },
      {
        id: "admin-7",
        question: "🔗 Müşterilerim benden nasıl online randevu alabilir?",
        answer: "<strong>Ayarlar > İşletme Bilgileri</strong> sayfasına gidin. Orada size özel <strong>'Randevu Linkiniz'</strong> (örn: plannapp.co/isletme-adi) bulunmaktadır. Bu linki kopyalayıp Instagram profilinize veya müşterilerinize gönderebilirsiniz."
      },
      {
        id: "admin-2",
        question: "💳 Deneme sürem bitiyor, nasıl abone olabilirim?",
        answer: "Panelinizde <strong>Ayarlar > Abonelik & Faturalandırma</strong> bölümüne gidin. İşletmenize en uygun olan 6 paketimizden (Standart, Pro vb.) birini seçerek aboneliğinizi başlatabilirsiniz."
      },
      {
        id: "admin-3",
        question: "✂️ Yeni bir hizmeti (örn: Manikür) sisteme nasıl eklerim?",
        answer: "<strong>Ayarlar > Hizmet Yönetimi</strong> sayfasına gidin. Sağ üstteki <strong>[ + Yeni Hizmet Ekle ]</strong> butonuna basın. Hizmetin adını, fiyatını ve en önemlisi <strong>Hizmet Süresini (Dakika)</strong> girin. Bu süre, takviminizin doğru çalışması için kritiktir."
      },
      {
        id: "admin-4",
        question: "👥 Yeni bir personeli sisteme nasıl davet ederim?",
        answer: "<strong>Ayarlar > Personel Yönetimi</strong> sayfasına gidin. <strong>[ + Personel Davet Et ]</strong> butonuna basın. Personelinizin adını ve e-posta adresini girin. Sistem, personelinize kendi şifresini belirlemesi için bir <strong>davet e-postası</strong> gönderecektir."
      },
      {
        id: "admin-5",
        question: "💰 Kasa (Finans) modülü nasıl çalışır?",
        answer: "Kasa, sizin için geliri <strong>otomatik</strong> toplar. Bir randevu 'Tamamlandı' olarak işaretlendiğinde, o hizmetin bedeli kasanıza 'Gelir' olarak işlenir. Sizin tek yapmanız gereken <strong>Giderler</strong> sekmesinden kira, fatura, malzeme gibi manuel harcamalarınızı girmektir."
      },
      {
        id: "admin-6",
        question: "💸 Personelime avans/maaş ödemesi yaptım, bunu nasıl işlerim?",
        answer: "<strong>Ayarlar > Kasa > Personel Hakedişleri</strong> sekmesine gidin. İlgili personelin kartındaki <strong>[ Ödeme Yap ]</strong> butonuna basın ve verdiğiniz tutarı (örn: 5000 TL) girin. Bu tutar hem personelin bakiyesinden düşer hem de kasanızdan 'Gider' olarak çıkar."
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
        answer: "<strong>[Anasayfa] (Dashboard)</strong> ekranındaki <strong>'Bugünün Akışı'</strong> kartında güncel programınızı görebilirsiniz. Tüm programınızı (geçmiş ve gelecek) görmek için ise alttaki <strong>[Takvim]</strong> ikonuna tıklayın. Takvim, sadece SİZE ait randevuları gösterecektir."
      },
      {
        id: "personnel-3",
        question: "➕ Yeni bir randevuyu nasıl eklerim?",
        answer: "Panelin altındaki büyük, mavi <strong>[ + ]</strong> butonuna basın. Açılan 3 adımlı sihirbazda 'Hizmet', 'Müşteri' ve 'Saat' seçmeniz yeterlidir. Personel alanı otomatik olarak size (adınıza) kilitlenmiştir."
      },
      {
        id: "personnel-4",
        question: "📊 Bugün ne kadar kazandırdığımı (ciro) görebilir miyim?",
        answer: "Evet. <strong>[Anasayfa] (Dashboard)</strong> ekranınızdaki <strong>'Hızlı Bakış'</strong> kartı, o gün tamamladığınız randevuların toplam tutarını (Toplam Hizmet Tutarı) size gösterir."
      },
      {
        id: "personnel-5",
        question: "🔒 Şifremi nasıl değiştirebilirim?",
        answer: "Panelin altındaki <strong>[Ayarlar]</strong> ikonuna tıklayın. Açılan menüden <strong>[Profilim]</strong> seçeneğine girerek şifrenizi güncelleyebilirsiniz."
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
        answer: "The <strong>Setup Wizard</strong> that appears when you first log in to your panel is the quickest way. There you can set up your services, prices, and general business hours in 2 minutes."
      },
      {
        id: "admin-7",
        question: "🔗 How can my customers book appointments online?",
        answer: "Go to <strong>Settings > Business Information</strong>. There you'll find your <strong>'Booking Link'</strong> (e.g., plannapp.co.uk/business-name). You can copy this link and share it on your Instagram profile or send it to your customers."
      },
      {
        id: "admin-2",
        question: "💳 My trial is ending, how can I subscribe?",
        answer: "Go to <strong>Settings > Subscription & Billing</strong> in your panel. Select one of our 6 packages (Standard, Professional, etc.) that best suits your business to start your subscription."
      },
      {
        id: "admin-3",
        question: "✂️ How do I add a new service (e.g., Manicure) to the system?",
        answer: "Go to <strong>Settings > Service Management</strong>. Click the <strong>[ + Add New Service ]</strong> button in the top right. Enter the service name, price, and most importantly, the <strong>Service Duration (Minutes)</strong>. This duration is critical for your calendar to work correctly."
      },
      {
        id: "admin-4",
        question: "👥 How do I invite a new staff member to the system?",
        answer: "Go to <strong>Settings > Staff Management</strong>. Click the <strong>[ + Invite Staff ]</strong> button. Enter your staff member's name and email address. The system will send an <strong>invitation email</strong> to your staff member to set their password."
      },
      {
        id: "admin-5",
        question: "💰 How does the Finance (Cash) module work?",
        answer: "The Finance module <strong>automatically</strong> collects revenue for you. When an appointment is marked as 'Completed', the service fee is processed as 'Revenue' in your finance. All you need to do is enter manual expenses such as rent, bills, and materials from the <strong>Expenses</strong> tab."
      },
      {
        id: "admin-6",
        question: "💸 I made an advance/salary payment to my staff, how do I record it?",
        answer: "Go to <strong>Settings > Finance > Staff Payroll</strong>. Click the <strong>[ Make Payment ]</strong> button on the relevant staff member's card and enter the amount you paid (e.g., £500). This amount will be deducted from the staff member's balance and recorded as an 'Expense' in your finance."
      }
    ],

    // ===================================================================
    // 👤 STAFF FAQ
    // ===================================================================
    personnel: [
      {
        id: "personnel-1",
        question: "✉️ I received an invitation email, what should I do now?",
        answer: "Your business owner has invited you to the PLANN system. Please click the <strong>[ Set My Password ]</strong> link in the email. Once you set a secure password, your account will be activated and you can log in to the panel."
      },
      {
        id: "personnel-2",
        question: "🗓️ Where can I see today's or tomorrow's schedule?",
        answer: "You can see your current schedule in the <strong>'Today's Flow'</strong> card on the <strong>[Dashboard]</strong> screen. To see your entire schedule (past and future), click the <strong>[Calendar]</strong> icon at the bottom. The calendar will only show appointments assigned to YOU."
      },
      {
        id: "personnel-3",
        question: "➕ How do I add a new appointment?",
        answer: "Click the large blue <strong>[ + ]</strong> button at the bottom of the panel. In the 3-step wizard that opens, you just need to select 'Service', 'Customer', and 'Time'. The staff field is automatically locked to you (your name)."
      },
      {
        id: "personnel-4",
        question: "📊 Can I see how much I've earned (revenue) today?",
        answer: "Yes. The <strong>'Quick View'</strong> card on your <strong>[Dashboard]</strong> screen shows you the total amount of appointments you completed that day (Total Service Amount)."
      },
      {
        id: "personnel-5",
        question: "🔒 How can I change my password?",
        answer: "Click the <strong>[Settings]</strong> icon at the bottom of the panel. From the menu that opens, go to <strong>[My Profile]</strong> to update your password."
      }
    ]
  }
};
