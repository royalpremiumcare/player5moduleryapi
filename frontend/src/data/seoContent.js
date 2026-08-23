// ============================================================================
// PLANN — Programmatic SEO sayfaları içerik katmanı (Content Enrichment Fazı)
//
// Her kayıt bir landing page'in GÖVDE içeriğidir (head/metadata seoData.js'te).
// Key formatı: "<locale>:<category>:<slug>"
//
// KURAL: Yalnızca GERÇEK PLANN özellikleri anlatılır. Uydurma entegrasyon,
// müşteri sayısı, rating, garanti veya fiyat iddiası YASAK.
//
// Gerçek özellik seti (referans):
// - Randevu takvimi (gün/hafta), çift randevu engelleme
// - WhatsApp otomatik onay + hatırlatma mesajları (WhatsApp Business API)
// - Online randevu sayfası (işletmeye özel link, 7/24)
// - Müşteri yönetimi (randevu geçmişi, harcama takibi, notlar)
// - Personel yönetimi (personel bazlı takvim ve yetkiler)
// - Gelir-gider (kasa) takibi + istatistik raporları
// - Seans paketleri (paket satışı ve kalan seans takibi)
// - Yapay zeka asistanı (yazılı/sesli komutla randevu oluşturma)
// - iOS / Android uygulama + PWA
// - Türkçe/İngilizce arayüz, TRY/GBP desteği
//
// Bu dosya SAF DATA'dır (import yok) — build-time statik shell üreticisi
// (scripts/generate-seo-html.js) tarafından da vm ile okunur.
// ============================================================================

export const seoContent = {
  // ==========================================================================
  // TR — SEKTÖR SAYFALARI (/cozumler/*)
  // ==========================================================================
  "tr:vertical:berber-randevu-programi": {
    intro: [
      "Berber dükkânında takvim, günün temposunu belirler. Saç kesimi sürerken gelen aramalar, kapıdan sorulan müsaitlikler ve ustalar arasında paylaştırılan işler aynı yerde tutulmadığında boşluklar kadar üst üste yazılan saatler de sorun olur.",
      "PLANN, randevuları gün veya hafta görünümünde toplar. Müşteri işletmenize ait bağlantıdan boş saati seçebilir; WhatsApp Business API randevu onayını ve zamanı yaklaşan randevunun hatırlatmasını iletir.",
    ],
    sections: [
      {
        h2: "Tezgâh başındaki işi aksatan randevu sorunları",
        items: [
          {
            h3: "Müsaitlik soruları tıraşı bölüyor",
            text: "Telefon her çaldığında elinizdeki işi bırakıp deftere dönmek gerekmez. Paylaştığınız randevu bağlantısı o anda uygun olan saatleri gösterir; müşteri hizmetini ve saatini seçerken siz koltuktaki işinize devam edersiniz.",
          },
          {
            h3: "Dolu saat yeniden verilebiliyor",
            text: "Sözlü alınan randevular farklı ustalara aktarılırken aynı saate iki müşteri yazılabilir. PLANN dolu aralığa ikinci kayıt açılmasını önler ve günlük programı usta bazında görünür tutar.",
          },
          {
            h3: "Günün hesabı hafızaya kalıyor",
            text: "Hangi ustanın kaç randevu tamamladığını ve kasaya hangi hizmetlerden gelir girdiğini ayrı ayrı toplamak yerine, randevu istatistikleriyle gelir-gider kayıtlarını birlikte değerlendirirsiniz.",
          },
        ],
      },
      {
        h2: "Açılıştan kapanışa berberin günlük düzeni",
        body: [
          "Saç kesimi, sakal tıraşı ve bakım gibi hizmetleri süreleriyle tanımlayıp işletme bağlantınızı Instagram profilinde, Google işletme sayfasında veya WhatsApp üzerinden paylaşabilirsiniz. Müşteri yalnızca takvimde uygun görünen saatlerden birini alır.",
          "Telefonla veya dükkâna gelerek saat isteyen müşterinin kaydını uygulamadan eklersiniz. Müşteri, hizmet ve usta seçildiğinde randevu diğer kayıtlarla birlikte günlük programa yerleşir.",
          "Kapanışta günlük gelir-gider hareketlerine ve hizmet ya da personel bazlı istatistiklere bakarak dükkânın işleyişini rakamlarla değerlendirirsiniz.",
        ],
      },
      {
        h2: "Her ustaya kendi programı, yöneticiye tam görünüm",
        body: [
          "Ekipteki her usta için ayrı takvim ve uygun yetki tanımlanabilir. Personel kendi programını takip ederken yönetici haftalık yoğunluğu, ekip randevularını ve işletme istatistiklerini birlikte görür.",
        ],
      },
    ],
    faq: [
      {
        q: "Müşteri randevu almak için uygulama kurmak zorunda mı?",
        a: "Hayır. İşletmenize ait herkese açık randevu bağlantısını telefondaki tarayıcıdan açıp uygun saati seçmesi yeterlidir. Siz ise takvimi iOS, Android veya PWA üzerinden yönetebilirsiniz.",
      },
      {
        q: "Teyit ve hatırlatma mesajlarını yine tek tek ben mi göndereceğim?",
        a: "Göndermeniz gerekmez. WhatsApp Business API, kayıt sırasında onay mesajını; randevu yaklaşırken de hatırlatmayı iletir.",
      },
      {
        q: "Kapıdan ya da telefondan aldığım randevu ne olacak?",
        a: "Onu da gün veya hafta takvimine siz eklersiniz. Müşteriyi, hizmeti, ustayı ve saati seçtiğinizde kayıt dükkân programında görünür.",
      },
      {
        q: "Üç usta aynı anda çalışıyor; takvimler birbirine karışır mı?",
        a: "Her ustanın ayrı takvimi vardır. Yetkileri personelin hangi ekranları görebileceğini belirler; yönetici hesabı ise ekibin tamamını birlikte takip eder.",
      },
      {
        q: "Müşterinin önceki gelişlerini görebilir miyim?",
        a: "Evet. Müşteri kartında yalnızca randevu geçmişi, toplam harcama ve eklediğiniz genel notlar bulunur; önceki ziyaretin idari bilgilerine buradan bakabilirsiniz.",
      },
    ],
    trust: {
      title: "Berber dükkânında PLANN ile kontrol edilenler",
      items: [
        "Günlük ve haftalık görünümde usta bazlı randevu planı",
        "Dolu saatlere ikinci kayıt açılmasını önleyen takvim",
        "WhatsApp Business API ile zamanında onay ve hatırlatma",
        "Randevu geçmişi, toplam harcama ve genel not alanı",
        "iOS, Android ve PWA üzerinden dükkân dışından erişim",
      ],
    },
    cta: {
      title: "Koltuklar arasında çakışan saat bırakmayın",
      text: "Kesim ve bakım sürelerini ustalarınızla eşleştirin; müsait saat bağlantısını WhatsApp, Instagram veya Google profilinizde paylaşın.",
      button: "Usta programlarını düzenleyin",
    },
    links: [
      { label: "Kuaför salonu takvimini düzenleyin", to: "/cozumler/kuafor-randevu-programi" },
      { label: "Güzellik merkezi randevularını yönetin", to: "/cozumler/guzellik-merkezi-randevu-programi" },
      { label: "WhatsApp teyit ve hatırlatmalarını inceleyin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "İşletmenize özel randevu bağlantısını görün", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Kasa ve ekip istatistiklerini keşfedin", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:kuafor-randevu-programi": {
    intro: [
      "Kuaför salonunda bir kesimin arasına fön sığabilir; boya, bakım veya gelin saçı ise takvimde uzun bir blok ister. Hizmet süreleri hesaba katılmadan verilen tek bir saat, müşteriyi bekletip ekibin bütün gününü geriye atabilir.",
      "PLANN her hizmetin süresini, çalışanların takvimini ve müşteri randevularını birlikte yönetir. Salon bağlantısından alınan randevular uygun çalışanın programına yazılır; WhatsApp onayı kayıt anında, hatırlatma ise randevu yaklaşırken gider.",
    ],
    sections: [
      {
        h2: "Salon programında en çok zaman alan ayrıntılar",
        items: [
          {
            h3: "Kesimle boya aynı süreye sığmıyor",
            text: "Her hizmet için ayrı süre tanımlandığında takvim seçilen işleme göre yer ayırır. Böylece uzun bir boya randevusunun üzerine yanlışlıkla başka müşteri yazılmaz.",
          },
          {
            h3: "DM kutusu gerçek takvimi göstermiyor",
            text: "Instagram mesajındaki talep henüz kesin bir randevu değildir ve yoğunlukta gözden kaçabilir. Profildeki herkese açık bağlantı, müşteriye güncel boşlukları gösterir ve seçilen saati doğrudan takvime işler.",
          },
          {
            h3: "Müşterinin tercihi her ziyarette yeniden soruluyor",
            text: "Müşteri kartındaki geçmiş randevulara, toplam harcamaya ve genel notlara bakabilirsiniz. Son ziyaretin idari ayrıntıları, yeni randevu öncesinde elinizin altında olur.",
          },
        ],
      },
      {
        h2: "Cumartesi yoğunluğunu çalışanlara dağıtın",
        body: [
          "Gün görünümünde çalışanların randevularını yan yana, hafta görünümünde yaklaşan yoğunluğu görürsünüz. Online bağlantıdan gelen kayıtlar boş saatleri kullanır ve takvim aynı personele çakışan randevu verilmesini engeller.",
          "Telefonla arayan müşteriyi hizmet, çalışan ve saat seçerek uygulamadan eklersiniz. Yeni kayıt için WhatsApp onayı gönderilir; randevu zamanı yaklaşınca müşteri ayrıca hatırlatılır.",
          "Dönem sonunda hizmet ve personel istatistikleri ile gelir-gider kayıtları; hangi işlerin salon trafiğini ve kasayı oluşturduğunu değerlendirmenize yardım eder.",
        ],
      },
      {
        h2: "Bakım paketlerinin kullanımını içeride izleyin",
        body: [
          "Birden çok ziyaret içeren bakım paketlerinde kullanılan ve kalan seansları işletme içi paket kayıtlarından takip edebilirsiniz. Bu bilgi müşteriye açık randevu sayfasında gösterilmez ve müşteri kartının içeriğiyle karıştırılmaz.",
        ],
      },
    ],
    faq: [
      {
        q: "Boya için üç saat, fön için daha kısa süre ayırabilir miyim?",
        a: "Evet. Her hizmetin süresi ayrı tanımlanır. Randevu sayfası ve salon takvimi, müşterinin seçtiği hizmet için gereken aralığa göre uygun saatleri gösterir.",
      },
      {
        q: "Cumartesi randevularının teyidini nasıl yetiştireceğiz?",
        a: "WhatsApp Business API, randevu oluştuğunda onayı ve zamanı yaklaşınca hatırlatmayı gönderir; ekibin her müşteri için ayrı mesaj yazması gerekmez.",
      },
      {
        q: "Müşterinin kullandığı renk bilgisini nerede tutarım?",
        a: "Müşteri kartındaki genel not alanını kullanabilirsiniz. Kartta geçmiş randevular ve toplam harcama da görüldüğü için sonraki ziyarete hazırlanmak kolaylaşır.",
      },
      {
        q: "Çalışanlar yalnızca kendi müşterilerini görebilir mi?",
        a: "Personel için ayrı takvim ve yetkiler tanımlanabilir. Yönetici bütün salon programını görürken çalışanların erişimi görevlerine göre sınırlandırılabilir.",
      },
      {
        q: "Instagram'daki müşteriye hangi bağlantıyı vereceğim?",
        a: "İşletmenize ait herkese açık randevu bağlantısını profilinize ekleyebilirsiniz. Müşteri buradan hizmeti ve uygun saati seçer; kayıt salon takvimine düşer.",
      },
    ],
    trust: {
      title: "Boya, kesim ve fönü ayıran salon düzeni",
      items: [
        "Hizmet süresine göre açılan gerçek müsaitlikler",
        "Çalışan bazlı takvimler ve erişim yetkileri",
        "Kayıt ve yaklaşan saat için WhatsApp mesajları",
        "Geçmiş, harcama ve genel notları gösteren müşteri kartı",
        "Hizmet ve ekip performansını gösteren gelir istatistikleri",
      ],
    },
    cta: {
      title: "Salon yoğunluğunu görünür bir programa dönüştürün",
      text: "Kesim, boya ve bakım sürelerini ekibin çalışma saatleriyle eşleştirin; güncel müsaitlik bağlantısını salon kanallarında paylaşın.",
      button: "Salon programınızı düzenleyin",
    },
    links: [
      { label: "Berber dükkânı için randevu akışına bakın", to: "/cozumler/berber-randevu-programi" },
      { label: "Güzellik merkezinde seansları planlayın", to: "/cozumler/guzellik-merkezi-randevu-programi" },
      { label: "Protez tırnak stüdyosu takvimini inceleyin", to: "/cozumler/protez-tirnak-randevu-programi" },
      { label: "WhatsApp onay ve hatırlatma akışını inceleyin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Müşteriye açık randevu sayfasını keşfedin", to: "/ozellikler/online-randevu-sayfasi" },
    ],
  },

  "tr:vertical:guzellik-merkezi-randevu-programi": {
    intro: [
      "Güzellik merkezinde lazer seansları, cilt bakımları ve kalıcı makyaj randevuları farklı uzmanların gününe dağılır. Paket hakları ayrı listede, tahsilatlar başka yerde, randevular mesajlarda kalınca resepsiyon sürekli kontrol yapmak zorunda kalır.",
      "PLANN uzman programlarını, müşteri kayıtlarını, seans paketlerini ve kasa hareketlerini birlikte izlemeyi sağlar. Dolu saat yeniden seçilemez; WhatsApp Business API onayı kayıt sırasında, hatırlatmayı randevu yaklaşırken iletir.",
    ],
    sections: [
      {
        h2: "Resepsiyonda çapraz kontrol gerektiren işler",
        items: [
          {
            h3: "Paket kullanımı ayrı çizelgede kalıyor",
            text: "Kullanılan ve kalan seanslar işletmenin paket kayıtlarında izlenir. Resepsiyon randevu verirken bu iç kaydı kontrol eder; paket bilgisi müşteriye açık sayfada veya müşteri kartında gösterilmez.",
          },
          {
            h3: "Uzmanın dolu saati yeniden açılıyor",
            text: "Her uzmanın kendi gün ve hafta takvimi bulunur. Dolu zaman aralığına çakışan ikinci randevu eklenemez; yönetici merkezin programını toplu olarak izler.",
          },
          {
            h3: "Teyit aramaları resepsiyon kuyruğu oluşturuyor",
            text: "Randevu kaydıyla birlikte WhatsApp onayı, yaklaşan randevu için de planlanan hatırlatma gönderilir. Ekip gün boyu teyit araması yapmak yerine gelen müşteriye odaklanır.",
          },
        ],
      },
      {
        h2: "Hizmetten tahsilata kadar düzenli kayıt",
        body: [
          "Merkezde sunulan işlemleri süre ve fiyat bilgileriyle tanımlarsınız. Müşteri açık randevu bağlantısından hizmeti, uzmanı ve uygun saati seçebilir; resepsiyon da telefon taleplerini aynı takvime ekler.",
          "Müşteri kartı yalnızca geçmiş randevuları, harcama toplamını ve ekibin genel notlarını gösterir. Paket kullanımı bu karttan ayrı, işletme içi paket kayıtlarında tutulur.",
          "Gelir-gider ekranı kasa hareketlerini, istatistikler ise dönem, hizmet ve uzman bazındaki sonuçları gösterir. Yönetim kararları dağınık dosyalar yerine güncel işletme verisine dayanır.",
        ],
      },
      {
        h2: "Ön masanın elini hızlandıran kayıt yolları",
        body: [
          "Yoğun telefonda müşteri, hizmet, uzman ve saat alanlarını sırayla seçerek kaydı doğrudan takvime eklersiniz. Randevu onayı bu kayıt üzerinden gönderildiği için resepsiyon aynı bilgileri mesaj listesine yeniden yazmaz.",
        ],
      },
    ],
    faq: [
      {
        q: "On seanslık paketin kullanımını ekip nereden izler?",
        a: "Kullanılan ve kalan seanslar yalnızca işletmenin iç paket kayıtlarında takip edilir. Bu sayı müşterinin randevu sayfasında veya müşteri kartında gösterilen bir bakiye değildir.",
      },
      {
        q: "Aynı uzmana iki randevu yazılması nasıl önleniyor?",
        a: "Uzmanın dolu aralığı yeniden kullanılamaz. Hem herkese açık randevu sayfası hem içeriden kayıt işlemi mevcut takvim müsaitliğine göre çalışır.",
      },
      {
        q: "Hatırlatmalar için resepsiyonun WhatsApp açması gerekiyor mu?",
        a: "Hayır. WhatsApp Business API, onay mesajını kayıt sırasında; hatırlatmayı ise randevu öncesinde gönderir.",
      },
      {
        q: "Hangi hizmetin daha çok gelir getirdiğini görebilir miyiz?",
        a: "Gelir-gider kayıtlarının yanında hizmet ve uzman bazlı istatistikleri dönemsel olarak inceleyebilirsiniz. Böylece merkezdeki randevu hacmi ile gelir görünümünü birlikte değerlendirirsiniz.",
      },
      {
        q: "Uzmanların yönetim ekranlarına erişmesini istemiyoruz; mümkün mü?",
        a: "Evet. Personel hesaplarına görevlerine uygun yetkiler verilebilir. Yönetici merkez genelini izlerken uzmanların erişimi kendi çalışma alanlarıyla sınırlandırılabilir.",
      },
    ],
    trust: {
      title: "Uzman, seans ve kasa için net kayıtlar",
      items: [
        "Kullanılan ve kalan hakları gösteren seans paketi takibi",
        "Uzman bazlı gün ve hafta takvimleriyle çakışma önleme",
        "WhatsApp Business API üzerinden onay ve hatırlatma mesajları",
        "Harcama, randevu geçmişi ve genel notları içeren müşteri kartları",
        "Hizmet ve uzman bazında gelir ile randevu istatistikleri",
      ],
    },
    cta: {
      title: "Resepsiyonda paket ve takvim kontrolünü kısaltın",
      text: "Uzman saatlerini, işlem sürelerini ve işletme içi paket kayıtlarını düzenleyin; müşterilere yalnızca güncel müsaitlik bağlantısını verin.",
      button: "Merkez programınızı hazırlayın",
    },
    links: [
      { label: "Kuaför ekip takvimini nasıl yönetir?", to: "/cozumler/kuafor-randevu-programi" },
      { label: "Protez tırnak randevularını planlayın", to: "/cozumler/protez-tirnak-randevu-programi" },
      { label: "Diyetisyen danışan takibini inceleyin", to: "/cozumler/diyetisyen-randevu-programi" },
      { label: "WhatsApp randevu mesajlarını inceleyin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Gelir-gider ve personel ekranlarını keşfedin", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:protez-tirnak-randevu-programi": {
    intro: [
      "Yeni set, dolgu, kalıcı oje ve nail art aynı uzunlukta işler değildir. Stüdyonun takvimi hizmet süresini doğru ayırmadığında birkaç dakikalık plan hatası, günün ilerleyen saatlerinde bekleyen müşterilere dönüşür.",
      "PLANN hizmet sürelerine göre müsaitlik açar, dolu saate ikinci kayıt alınmasını önler ve stüdyo programını güncel tutar. Müşteri bio bağlantınızdan saat seçtiğinde WhatsApp onayı gönderilir; randevu yaklaşınca hatırlatma iletilir.",
    ],
    sections: [
      {
        h2: "Tırnak stüdyosunda takvimi bozan ayrıntılar",
        items: [
          {
            h3: "Yeni set için dolgu kadar süre ayrılıyor",
            text: "Her işlem kendi süresiyle tanımlanır. Müşteri yeni set seçtiğinde uzun, dolgu seçtiğinde daha kısa bir aralık ayrılır; arkadaki randevular yanlış süre hesabıyla kaymaz.",
          },
          {
            h3: "Uzun randevu unutulunca büyük boşluk kalıyor",
            text: "Yaklaşan randevu için WhatsApp hatırlatması planlanan zamanda gönderilir. Özellikle iki-üç saatlik uygulamalarda ekibin ayrıca teyit listesi hazırlamasına gerek kalmaz.",
          },
          {
            h3: "Mesaj kutusundaki talepler kesinleşmiyor",
            text: "Instagram bio bağlantısı müşteriyi doğrudan güncel müsaitliklere götürür. Seçilen saat takvimde kayıt altına alınır; DM konuşmalarını ayrıca randevu listesine çevirmek gerekmez.",
          },
        ],
      },
      {
        h2: "Randevudan müşteri notuna stüdyo akışı",
        body: [
          "Yeni uygulama, dolgu, manikür ve kalıcı oje gibi seçenekleri süre ve fiyatlarıyla eklersiniz. Herkese açık sayfa, seçilen işleme yetecek boşlukları gösterir ve çakışan saatleri kapalı tutar.",
          "Kayıt tamamlandığında WhatsApp onayı gider; saat yaklaşınca hatırlatma iletilir. Müşteri kartında yalnızca önceki randevular, toplam harcama ve genel notlar kalır.",
          "Günlük kasa hareketlerini gelir-gider ekranından; hizmet yoğunluğunu ve ekip sonuçlarını istatistiklerden takip edebilirsiniz.",
        ],
      },
      {
        h2: "Bağımsız artistten büyüyen stüdyoya",
        body: [
          "Bağımsız çalışırken randevuları mobil uygulamadan yönetebilir, ekip büyüdüğünde her artist için ayrı takvim ve yetki açabilirsiniz. Yönetici stüdyonun programını görür; çalışanlar kendilerine tanımlanan erişimle ilerler.",
        ],
      },
    ],
    faq: [
      {
        q: "Nail art ile sade dolguya ayrı süre girebilir miyim?",
        a: "Evet. Her hizmet için farklı süre ve fiyat tanımlanabilir. Randevu sayfasındaki müsaitlik seçilen işlemin süresine göre hesaplanır.",
      },
      {
        q: "Üç hafta sonraki dolgu randevusunu unutmaması için ne yapacağım?",
        a: "Çıkışta sonraki randevuyu takvime eklediğinizde WhatsApp hatırlatması zamanı gelince iletilir. Kayıt anında da onay mesajı gönderilir.",
      },
      {
        q: "Bio bağlantısından gelen kişi doğrudan takvime mi düşer?",
        a: "Evet. Müşteri herkese açık bağlantıda hizmeti ve uygun saati seçer; tamamlanan randevu stüdyo takviminde görünür.",
      },
      {
        q: "Bir müşterinin geçen sefer seçtiği rengi bulabilir miyim?",
        a: "Müşteri kartındaki genel not alanını kullanabilirsiniz. Geçmiş randevular ve toplam harcama da aynı kartta bulunur.",
      },
    ],
    trust: {
      title: "Yeni set ve dolgu süresini koruyan kayıtlar",
      items: [
        "Yeni set, dolgu ve tasarım için ayrı hizmet süreleri",
        "Uzun uygulamalar için planlanan WhatsApp hatırlatmaları",
        "Instagram bio'sunda paylaşılabilen açık randevu bağlantısı",
        "Randevu geçmişi, toplam harcama ve genel notlar",
        "Mobil erişim, kasa hareketleri ve hizmet istatistikleri",
      ],
    },
    cta: {
      title: "Her tasarıma doğru süreyi ayırın",
      text: "İşlemlerinizi süreleriyle ekleyin, uygun çalışma saatlerini açın ve stüdyo bağlantınızı profilinizde paylaşın.",
      button: "Stüdyo randevu takvimini hazırlayın",
    },
    links: [
      { label: "Güzellik merkezi seans düzenine göz atın", to: "/cozumler/guzellik-merkezi-randevu-programi" },
      { label: "Kuaför salonu ekip takvimini keşfedin", to: "/cozumler/kuafor-randevu-programi" },
      { label: "WhatsApp onay ve hatırlatmalarını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Açık randevu bağlantısı nasıl çalışır?", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "iOS ve Android'de randevuları yönetin", to: "/ozellikler/mobil-randevu-uygulamasi" },
    ],
  },

  "tr:vertical:dis-klinigi-randevu-programi": {
    intro: [
      "Diş kliniğinde kısa kontroller ile daha uzun işlemler aynı hekim programında art arda yürür. Sekreter bir yandan yeni saat verirken diğer yandan teyit mesajı yazıyor, hekimlerin takvimlerini ayrı ayrı kontrol ediyorsa küçük bir kayıt hatası bekleme süresini büyütür.",
      "PLANN hekim bazlı gün ve hafta takvimlerini birlikte gösterir. Hasta klinik bağlantısından uygun saati seçebilir; WhatsApp Business API randevu onayını ve zamanı yaklaşan kontrolün hatırlatmasını iletir.",
    ],
    sections: [
      {
        h2: "Sekreter masasındaki randevu yükü nerede birikiyor?",
        items: [
          {
            h3: "Hatırlatma listesi her gün yeniden hazırlanıyor",
            text: "Ekip ertesi günün randevularını ayırıp her hastaya ayrı mesaj yazmak zorunda kalmaz. Onay ve hatırlatma gönderimleri takvimdeki randevu saatine göre planlanır.",
          },
          {
            h3: "Telefonda uygun hekim aramak vakit alıyor",
            text: "Hekim takvimleri gün veya hafta görünümünde birlikte incelenebilir. Klinik bağlantısını kullanan hasta yalnızca uygun saatleri görür; sekreter telefon taleplerini ilgili hekimin programına ekler.",
          },
          {
            h3: "Aynı hekime çakışan kayıt açılıyor",
            text: "Dolu zaman aralığına ikinci bir randevu yazılması engellenir. Yönetici klinik genelini izlerken her hekim için ayrı program korunur.",
          },
        ],
      },
      {
        h2: "Klinik randevusu baştan sona nasıl ilerler?",
        body: [
          "Muayene, kontrol ve klinikte sunulan diğer randevu türlerini süre ve ücretleriyle tanımlarsınız. Hasta açık bağlantıdan hizmeti, hekimi ve müsait saati seçebilir; telefonla gelen kayıtları sekreter ekleyebilir.",
          "Randevu takvime girdiğinde WhatsApp onayı gönderilir, zamanı yaklaşınca hatırlatma iletilir. Müşteri kartında yalnızca randevu geçmişi, toplam harcama ve genel notlar bulunur.",
          "Gelir-gider ekranı kasa kayıtlarını; istatistikler hekim, randevu türü ve dönem bazındaki sayısal görünümü sunar.",
        ],
      },
      {
        h2: "İleri tarihli kontrolleri ajandadan çıkarın",
        body: [
          "Hasta ayrılmadan bir sonraki kontrol saatini takvime ekleyebilirsiniz. Kayıt günler veya aylar sonra olsa da zamanı geldiğinde hatırlatma gönderilir; sekreter ayrıca kişisel bir liste tutmaz.",
        ],
      },
    ],
    faq: [
      {
        q: "Hekimler bütün klinik takvimini görmek zorunda mı?",
        a: "Hayır. Personel bazında takvim ve erişim yetkileri tanımlanabilir. Yönetici genel programı görürken kullanıcıların erişimi görev alanlarına göre düzenlenir.",
      },
      {
        q: "İki hekim için ayrı çalışma saatleri açabilir miyiz?",
        a: "Evet. Her hekimin kendi takvimi bulunur; randevular ilgili hekimin uygunluğuna göre yerleşir ve yönetici klinik genelindeki programı birlikte izleyebilir.",
      },
      {
        q: "WhatsApp teyitleri hangi yöntemle gönderiliyor?",
        a: "Randevu onayı ve hatırlatması WhatsApp Business API üzerinden iletilir. Sekreterin kişisel hesabından her hastaya ayrı mesaj göndermesi gerekmez.",
      },
      {
        q: "Kontrol ve muayene için farklı zaman blokları açılır mı?",
        a: "Her randevu türüne ayrı süre ve ücret tanımlanabilir. Takvim, seçilen türün süresine göre müsaitlik gösterir ve dolu aralığa çakışan kayıt almaz.",
      },
      {
        q: "Ay sonunda hekim bazında randevu sayısını görebilir miyiz?",
        a: "Evet. İstatistiklerde hekim ve randevu türü bazındaki sayıları, gelir-gider bölümünde ise dönemsel kasa hareketlerini inceleyebilirsiniz.",
      },
    ],
    trust: {
      title: "Sekreter ve hekim programını eşleştiren yapı",
      items: [
        "Hekim bazlı gün ve hafta takvimlerinde çakışma kontrolü",
        "WhatsApp Business API ile planlanan onay ve hatırlatma",
        "Telefon trafiğini azaltan kliniğe özel randevu bağlantısı",
        "Göreve göre düzenlenebilen personel erişim yetkileri",
        "Hekim ve randevu türü bazında işletme istatistikleri",
      ],
    },
    cta: {
      title: "Sekreterin hekim arama süresini kısaltın",
      text: "Kontrol ve muayene sürelerini hekim çalışma saatleriyle eşleştirin; yalnızca müsait aralıkları gösteren klinik bağlantısını paylaşın.",
      button: "Hekim takvimlerini düzenleyin",
    },
    links: [
      { label: "Fizyoterapi seans takvimini inceleyin", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "Psikologlar için danışan randevu akışı", to: "/cozumler/psikolog-randevu-programi" },
      { label: "Veteriner kliniği randevularını yönetin", to: "/cozumler/veteriner-randevu-programi" },
      { label: "WhatsApp randevu mesajları nasıl işler?", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Kasa ve personel istatistiklerine bakın", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:psikolog-randevu-programi": {
    intro: [
      "Bir seans biterken sıradaki danışan gelir; aradaki kısa sürede yeni saat taleplerine dönmek ve haftalık programı güncellemek kolay değildir. Düzenli görüşmeler mesajlarda, tek seferlik randevular ajandada kalınca çalışma günü gereksiz bir idari yüke dönüşür.",
      "PLANN danışan randevularını gün ve hafta görünümünde düzenler. Paylaştığınız bağlantı uygun saatleri açar; WhatsApp onayı kayıt sırasında, hatırlatma seans yaklaşırken gider. Programınızı iOS, Android veya PWA'dan takip edersiniz.",
    ],
    sections: [
      {
        h2: "Seans aralarında büyüyen küçük idari işler",
        items: [
          {
            h3: "Yeni saat bulmak uzun bir yazışmaya dönüşüyor",
            text: "Danışan herkese açık randevu bağlantısından o anda uygun olan saatleri görebilir. Seçim doğrudan takvime işlendiği için karşılıklı gün ve saat mesajları azalır.",
          },
          {
            h3: "Teyit mesajı gün içinde unutulabiliyor",
            text: "Randevu oluştuğunda WhatsApp onayı gönderilir; seans yaklaşırken planlanan hatırlatma iletilir. Bu iş seans aralarındaki yapılacaklar listesine kalmaz.",
          },
          {
            h3: "İdari danışan bilgileri farklı yerlerde duruyor",
            text: "Müşteri kartında geçmiş randevular, toplam harcama ve sizin eklediğiniz genel notlar birlikte görünür. Böylece program ve ödeme takibi için ayrı listeler arasında dolaşmazsınız.",
          },
        ],
      },
      {
        h2: "Çalışma haftasını kendi ritminize göre kurun",
        body: [
          "Bireysel görüşme, çift görüşmesi veya online seans gibi seçenekleri farklı sürelerle tanımlayabilirsiniz. Danışan açık saatlerden birini alır; siz de telefonla kesinleşen randevuyu takvime eklersiniz.",
          "Telefonla kesinleşen kaydı danışan, görüşme türü ve saat seçerek takvime eklersiniz. Dolu aralık yeniden seçilemez; yaklaşan görüşmelerin WhatsApp mesajları randevu saatine göre gönderilir.",
          "Aylık seans sayısı, gelir görünümü ve yoğun dönemler istatistiklerde; günlük işletme hareketleri gelir-gider ekranında takip edilir.",
        ],
      },
      {
        h2: "Erişimi çalışma biçiminize göre sınırlayın",
        body: [
          "Tek başınıza çalışıyorsanız hesabınızı yalnızca siz kullanırsınız. Bir merkez içinde çalışıyorsanız personel takvimleri ve yetkileri ayrılabilir; kullanıcılar kendilerine tanımlanan ekranlara erişir.",
        ],
      },
    ],
    faq: [
      {
        q: "Merkezdeki diğer çalışanlar benim takvimimi görür mü?",
        a: "Erişim, tanımlanan personel yetkilerine bağlıdır. Her kullanıcı için takvim ve ekran izinleri düzenlenebilir; yönetici ise ihtiyaç duyduğu genel görünümü korur.",
      },
      {
        q: "Danışana giden mesajları ben mi hazırlıyorum?",
        a: "Randevu onayı ve yaklaşan seans hatırlatması WhatsApp Business API üzerinden gönderilir. Gönderim zamanı takvimdeki randevu bilgisine bağlıdır.",
      },
      {
        q: "Online ve yüz yüze görüşmeye farklı süre verebilir miyim?",
        a: "Evet. İkisini ayrı hizmet olarak tanımlayıp her birine farklı süre ve fiyat ekleyebilirsiniz; uygun saatler seçilen hizmete göre açılır.",
      },
      {
        q: "Beş seanslık paketin kullanımını nasıl izlerim?",
        a: "Kullanılan ve kalan seansları işletme içi paket kayıtlarında takip edebilirsiniz. Müşteri kartı bundan ayrı olarak yalnızca randevu geçmişini, toplam harcamayı ve genel notları gösterir.",
      },
    ],
    trust: {
      title: "Seans aralarında idari yükü azaltan kayıtlar",
      items: [
        "Gün ve hafta görünümünde çakışmasız seans takvimi",
        "WhatsApp üzerinden randevu onayı ve seans hatırlatması",
        "Randevu geçmişi, harcama ve genel not görünümü",
        "Paketli çalışmalarda kullanılan ve kalan seans takibi",
        "Personel takvimleri için ayrı erişim yetkileri",
      ],
    },
    cta: {
      title: "Seans aralarını takvim işleriyle doldurmayın",
      text: "Bireysel, çift veya online görüşmeler için ayrı süreler açın; yalnızca boş saatleri gösteren bağlantıyı danışanlarınızla paylaşın.",
      button: "Seans saatlerinizi düzenleyin",
    },
    links: [
      { label: "Diyetisyenlerin kontrol randevusu akışı", to: "/cozumler/diyetisyen-randevu-programi" },
      { label: "Fizyoterapi paket ve seans takibi", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "Özel ders programını haftalık görünümde yönetin", to: "/cozumler/ozel-ders-randevu-programi" },
      { label: "Herkese açık randevu bağlantısını inceleyin", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "WhatsApp seans hatırlatmalarını keşfedin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
    ],
  },

  "tr:vertical:diyetisyen-randevu-programi": {
    intro: [
      "İlk görüşme, kısa kontrol ve online danışmanlık aynı takvimde farklı süreler ister. Bir danışanın sonraki kontrolü çıkışta kaydedilmediğinde ya da teyit mesajı yoğunlukta atlanınca takip planı kolayca dağılır.",
      "PLANN görüşme türlerine göre müsaitlik oluşturur ve kontrol randevularını gün ile hafta görünümünde gösterir. WhatsApp onayı kayıt sırasında, hatırlatma kontrol yaklaşırken gider; müşteri kartında randevu geçmişi, toplam harcama ve genel notlar kalır.",
    ],
    sections: [
      {
        h2: "Danışan takibinde aksayan üç operasyon",
        items: [
          {
            h3: "Sonraki kontrol farklı bir listede unutuluyor",
            text: "Görüşme bitiminde ilerideki kontrolü takvime ekleyebilir veya danışana açık randevu bağlantısını kullanabilirsiniz. Takvimdeki saat yaklaştığında WhatsApp hatırlatması gönderilir.",
          },
          {
            h3: "İlk görüşmeye kontrol kadar süre ayrılıyor",
            text: "İlk görüşme ve kontrol ayrı hizmetler olarak farklı sürelerle tanımlanır. Takvim seçilen görüşmeye göre uygun aralığı açar ve dolu saate ikinci kayıt alınmasını engeller.",
          },
          {
            h3: "Kaç kez geldiği ödeme kayıtlarıyla eşleşmiyor",
            text: "Danışan kartında randevu geçmişini ve harcama toplamını birlikte görebilirsiniz. Genel notlarınızı da aynı karta ekleyerek bir sonraki kontrolün idari ayrıntılarını hızla hatırlarsınız.",
          },
        ],
      },
      {
        h2: "Kontrol programını birkaç adımda yürütün",
        body: [
          "İlk görüşme, kontrol ve online danışmanlığı süre ve fiyatlarıyla eklersiniz. Danışan bağlantınızdan boş saati seçebilir; yüz yüze veya telefonla kesinleşen kontrolü siz kaydedebilirsiniz.",
          "Yoğun bir anda yeni randevuyu danışan, görüşme türü ve saat alanlarını seçerek kaydedebilirsiniz. WhatsApp Business API onayı kayıt sonrasında, hatırlatmayı ise kontrol öncesinde iletir.",
          "İstatistikler dönem içindeki görüşme sayılarını ve gelir görünümünü, gelir-gider bölümü ise işletme hareketlerini takip etmenizi sağlar.",
        ],
      },
      {
        h2: "Online görüşmeleri aynı takvimde ayırın",
        body: [
          "Online danışmanlığı ayrı bir hizmet olarak açabilirsiniz. Danışan uygun saati aynı randevu sayfasından seçer; görüşmenin hangi platformda yapılacağını siz ayrıca paylaşırsınız. PLANN takvim, onay ve hatırlatma kısmını yönetir.",
        ],
      },
    ],
    faq: [
      {
        q: "Kontrolü çıkışta ben mi yazmalıyım, danışan sonra alabilir mi?",
        a: "İki yöntem de kullanılabilir. Siz ileri tarihli kontrolü hemen ekleyebilir veya danışanın herkese açık bağlantıdan uygun saati seçmesini sağlayabilirsiniz; her iki kayıt da aynı takvimde görünür.",
      },
      {
        q: "Danışanın kaç görüşmeye geldiğini hızlıca bulabilir miyim?",
        a: "Evet. Müşteri kartı randevu geçmişini, toplam harcamayı ve eklediğiniz genel notları bir arada gösterir.",
      },
      {
        q: "Online görüşmeler yüz yüze randevularla çakışır mı?",
        a: "Online danışmanlığı ayrı süreli bir hizmet olarak tanımlarsınız. Takvim dolu zaman aralığına ikinci randevu alınmasını önlediği için iki görüşme üst üste yazılmaz.",
      },
      {
        q: "Kontrol teyitlerini kişisel WhatsApp hesabımdan mı göndereceğim?",
        a: "Hayır. WhatsApp Business API, onay mesajını kayıt sonrasında; hatırlatmayı ise kontrol öncesinde gönderir.",
      },
    ],
    trust: {
      title: "İlk görüşme ve kontrole ayrı zaman blokları",
      items: [
        "İlk görüşme ve kontrole özel sürelerle çakışmasız takvim",
        "İleri tarihli kontroller için WhatsApp hatırlatmaları",
        "Danışan geçmişi, harcaması ve genel notları",
        "Yüz yüze ve online görüşmeler için ortak program",
        "Görüşme sayılarıyla gelir-gider görünümünü birleştiren raporlar",
      ],
    },
    cta: {
      title: "İlk görüşmeyle kontrol süresini ayırın",
      text: "İlk görüşme, kısa kontrol ve online danışmanlık için ayrı süreler belirleyin; danışanlara güncel boşlukları gösterin.",
      button: "Kontrol programınızı hazırlayın",
    },
    links: [
      { label: "Psikologlar için seans planını inceleyin", to: "/cozumler/psikolog-randevu-programi" },
      { label: "Fizyoterapide kalan seans takibine bakın", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "Spor salonu seans programını keşfedin", to: "/cozumler/spor-salonu-randevu-programi" },
      { label: "WhatsApp onay ve hatırlatma akışını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Danışana açık randevu sayfasını inceleyin", to: "/ozellikler/online-randevu-sayfasi" },
    ],
  },

  "tr:vertical:fizyoterapi-randevu-programi": {
    intro: [
      "Fizyoterapi merkezinde tek randevudan çok, haftalara yayılan seans dizileri yönetilir. Bir yanda terapistlerin günlük programı, diğer yanda paketlerden kullanılan haklar ve her seans öncesi yapılacak hatırlatmalar vardır.",
      "PLANN terapist takvimlerinde çakışmayı önler, kullanılan ve kalan paket seanslarını işletme içi kayıtlarda izletir. WhatsApp onayı kayıt sırasında, hatırlatma seans yaklaşırken gider; yönetici haftayı, terapist ise yetkisi kapsamındaki programı görür.",
    ],
    sections: [
      {
        h2: "Seri seanslarda ekibi yoran takip noktaları",
        items: [
          {
            h3: "Kalan seans sayısı farklı kayıtlarda tutuluyor",
            text: "Kullanılan ve kalan seanslar işletmenin iç paket kayıtlarında takip edilir. Randevu verirken kâğıt liste açmanız gerekmez; bu bilgi hastaya açık sayfada veya müşteri kartında gösterilmez.",
          },
          {
            h3: "Haftalık seans yoğunlukta gözden kaçıyor",
            text: "Takvime girilen seans için WhatsApp onayı gönderilir, saat yaklaşınca hatırlatma iletilir. Sekreter veya terapist ayrıca günlük teyit listesi hazırlamaz.",
          },
          {
            h3: "İki hasta aynı terapiste yazılabiliyor",
            text: "Terapist bazlı takvim dolu zaman aralığını yeniden kullandırmaz. Klinik yöneticisi gün veya hafta görünümünde tüm terapistlerin programını birlikte kontrol eder.",
          },
        ],
      },
      {
        h2: "Değerlendirme süresiyle paket kullanımını ayırın",
        body: [
          "Değerlendirme, bireysel seans ve merkezde sunduğunuz diğer randevu türlerini ayrı süre ve fiyatlarla tanımlarsınız. Hasta açık bağlantıdan uygun saati seçebilir; ekip de telefonla gelen kaydı takvime ekleyebilir.",
          "Birden fazla seans içeren paketlerin kullanımı işletme içi paket kayıtlarında izlenir. Müşteri kartı bundan ayrı tutulur ve yalnızca randevu geçmişini, toplam harcamayı ve genel notları içerir.",
          "İstatistik ekranında terapist ve seans türü bazındaki adetler ile gelir görünümünü; kasa bölümünde gelir-gider hareketlerini dönemsel olarak incelersiniz.",
        ],
      },
      {
        h2: "Düzenli seans planını ekipçe görün",
        body: [
          "İleri tarihli seansları takvime yerleştirerek hastanın haftalık programını görünür hâle getirebilirsiniz. Zamanlanan hatırlatma yaklaşan randevuyu bildirir; personel yetkileri de her terapistin kendi programına erişmesini sağlar.",
        ],
      },
    ],
    faq: [
      {
        q: "On seanslık paketin kullanımını ekip görebilir mi?",
        a: "Evet. Kullanılan ve kalan seanslar işletme içi paket kayıtlarında takip edilir. Bu bilgi müşteri kartında veya hastaya açık randevu sayfasında gösterilmez.",
      },
      {
        q: "Her terapistin haftalık programını ayrı açabilir miyiz?",
        a: "Evet. Personel bazlı takvim ve yetki tanımlanır. Yönetici bütün merkezin programını izlerken terapistler kendilerine verilen erişimle çalışır.",
      },
      {
        q: "Seans teyitleri için her akşam mesaj yazmak gerekiyor mu?",
        a: "Gerekmiyor. WhatsApp Business API randevu onayını kayıt sırasında, yaklaşan seansın hatırlatmasını planlanan zamanda gönderir.",
      },
      {
        q: "Müşteri kartında hangi bilgiler bulunuyor?",
        a: "Müşteri kartında yalnızca randevu geçmişi, toplam harcama ve genel notlar bulunur. Paket kullanımı bundan ayrı bir işletme içi kayıtta izlenir.",
      },
    ],
    trust: {
      title: "Terapist programı ve paket kullanımı ayrımı",
      items: [
        "Paketlerde kullanılan ve kalan seansların iç takibi",
        "Terapist bazlı gün ve hafta takvimlerinde çakışma önleme",
        "WhatsApp Business API ile seans onayı ve hatırlatması",
        "Randevu geçmişi ve harcamayı gösteren müşteri kartı",
        "Terapist ve seans türüne göre işletme istatistikleri",
      ],
    },
    cta: {
      title: "Haftalara yayılan seansları sıraya koyun",
      text: "Değerlendirme ve seans sürelerini terapist takvimleriyle eşleştirin; paket kullanımını işletme içinde, randevuları takvimde izleyin.",
      button: "Terapist programlarını düzenleyin",
    },
    links: [
      { label: "Diş kliniği hekim takvimini inceleyin", to: "/cozumler/dis-klinigi-randevu-programi" },
      { label: "Psikolog danışan programına göz atın", to: "/cozumler/psikolog-randevu-programi" },
      { label: "Spor salonu paket ve seans akışını görün", to: "/cozumler/spor-salonu-randevu-programi" },
      { label: "WhatsApp seans hatırlatmalarını keşfedin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Gelir-gider ile personel görünümüne bakın", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:spor-salonu-randevu-programi": {
    intro: [
      "Sabah deneme antrenmanı, öğlen birebir çalışma, akşam üst üste grup dersleri… Spor salonunda gün, antrenörlerin takvimiyle üyelerin paket haklarını aynı anda takip etmeyi gerektirir.",
      "PLANN, PT ve ders randevularını gün ve hafta takviminde gösterir. Üyeler paylaştığınız bağlantıdan saat seçer; WhatsApp onay ve hatırlatmaları otomatik gider, tamamlanan seanslar paketlerden düşer.",
    ],
    sections: [
      {
        h2: "Resepsiyonda günü zorlaştıran noktalar",
        items: [
          {
            h3: "Antrenörün saati iki kişiye veriliyor",
            text: "Mesajlar ve telefon notları ayrı yerlerde kalınca aynı saat yeniden verilebilir. Antrenör takvimleri dolu zamanı gösterir ve yeni randevunun mevcut seansla çakışmasını önler.",
          },
          {
            h3: "Kalan PT hakkı konuşma konusu oluyor",
            text: "Üyenin kaç seansı kaldığını eski mesajlardan aramak gerekmez. Paket tanımlandığında tamamlanan seanslar düşer; güncel hak bilgisi müşteri kartında görülür.",
          },
          {
            h3: "Hatırlatma işi antrenöre kalıyor",
            text: "Ders aralarında tek tek mesaj yazmak yerine randevu onayı ve seans öncesi hatırlatma WhatsApp üzerinden otomatik gönderilir.",
          },
        ],
      },
      {
        h2: "PT, deneme ve grup dersleri aynı düzende",
        body: [
          "PT, deneme antrenmanı ve grup derslerini ayrı hizmetler olarak tanımlayabilirsiniz. Üye, herkese açık randevu bağlantınızdan uygun antrenörü ve saati seçebilir.",
          "Resepsiyon da gelen telefonu takvime ekleyebilir; yazılı veya sesli yapay zekâ asistanıyla randevu oluşturabilir. Dolu saatler görünür olduğu için program net kalır.",
          "Gelir-gider ekranı günlük hareketi, istatistikler ise hizmet ve personel bazındaki sonuçları gösterir. Böylece ay sonu değerlendirmesi dağınık notlara dayanmaz.",
        ],
      },
      {
        h2: "Üyenin gelişini tek karttan görün",
        body: [
          "Müşteri kartında geçmiş seanslar, toplam harcama ve ekip notları birlikte durur. Yeni paket konuşurken üyenin önceki devamlılığını ve aldığı hizmetleri hızlıca görebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "PT paketinde kaç seans kaldığını görebilir miyim?",
        a: "Evet. Üyeye paket tanımlanır ve tamamlanan seanslar kalan haktan düşer. Güncel sayı müşteri kartında görünür.",
      },
      {
        q: "Antrenörlerin programları birbirinden ayrılıyor mu?",
        a: "Evet. Her antrenörün takvimi ayrı izlenebilir. Personel yetkileriyle ekip üyelerinin görebileceği alanları sınırlayabilirsiniz.",
      },
      {
        q: "Seans mesajlarını kim gönderiyor?",
        a: "Randevu onayı ve yaklaşan seans hatırlatması WhatsApp üzerinden otomatik gönderilir. Ekibin her üyeyi tek tek araması gerekmez.",
      },
      {
        q: "Deneme antrenmanı için bağlantı paylaşabilir miyim?",
        a: "Evet. Deneme antrenmanını hizmet olarak açıp herkese açık randevu bağlantınızı paylaşabilirsiniz. İlgilenen kişi uygun saati kendisi seçer.",
      },
    ],
    trust: {
      title: "Salonun günlük düzeninde ne değişir?",
      items: [
        "PT ve ders saatleri gün ve hafta görünümünde izlenir",
        "Paket hakları tamamlanan seanslarla güncellenir",
        "WhatsApp onay ve hatırlatmaları otomatik gönderilir",
        "Antrenör takvimleri ve erişim yetkileri ayrı yönetilir",
        "Seans, gelir ve gider istatistikleri birlikte izlenir",
      ],
    },
    cta: {
      title: "Antrenör takvimlerini bir araya getirin",
      text: "Hizmetlerinizi, ekibinizi ve paketlerinizi tanımlayın; randevu bağlantınızı üyelerinizle paylaşın.",
      button: "Spor salonu hesabı oluşturun",
    },
    links: [
      { label: "Pilates stüdyosu takvimini inceleyin", to: "/cozumler/pilates-studyo-randevu-programi" },
      { label: "Fizyoterapi randevularını düzenleyin", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "Özel ders programına göz atın", to: "/cozumler/ozel-ders-randevu-programi" },
      { label: "WhatsApp onay ve hatırlatmalarını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Gelir, gider ve personel takibini keşfedin", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:pilates-studyo-randevu-programi": {
    intro: [
      "Pilates stüdyosunda ilk ders değerlendirmeleri, birebir seanslar ve grup dersleri gün boyunca farklı ritimlerde ilerler. Eğitmen değişikliği ve paket bakiyesi de eklenince mesajlardan tutulan program çabuk dağılır.",
      "PLANN, stüdyonun ders takvimini eğitmenlerle birlikte görünür kılar. Üyeler bağlantıdan randevu alır, WhatsApp mesajları otomatik gider ve ders paketleri tamamlanan seanslarla güncellenir.",
    ],
    sections: [
      {
        h2: "Ders aralarında büyüyen küçük işler",
        items: [
          {
            h3: "Uygun saat soruları gün boyu sürüyor",
            text: "Her üyeye ayrı ayrı boş saat yazmak yerine açık randevu sayfasını paylaşabilirsiniz. Üye, tanımladığınız dersler arasından uygun eğitmen ve zamanı seçer.",
          },
          {
            h3: "Paket bakiyesi defterde kalıyor",
            text: "Sekiz ya da on iki derslik paketler sistemde takip edilir. Tamamlanan ders paketten düşer; kalan hak müşteri kartında güncel kalır.",
          },
          {
            h3: "Eğitmen değişikliği takvime geç yansıyor",
            text: "Eğitmenlerin dersleri gün ve hafta takviminde birlikte görüldüğünde değişiklik doğrudan ilgili randevuya işlenir. Personel yetkileri, her eğitmenin erişimini düzenler.",
          },
        ],
      },
      {
        h2: "Stüdyonun ders akışı nasıl kurulur?",
        body: [
          "Birebir, düet ve grup derslerini süre ve fiyatlarıyla ayrı ayrı tanımlarsınız. Randevuyu üye bağlantıdan alabilir, ekip panelden ekleyebilir.",
          "Rezervasyon yapıldığında WhatsApp onayı, ders yaklaşınca hatırlatma otomatik gider. Takvim, aynı eğitmene çakışan iki seans yazılmasını önler.",
          "Eğitmen bazlı ders sayıları ve gelir istatistikleri görülebilir; günlük gelir ve giderler de kasa ekranında takip edilir.",
        ],
      },
      {
        h2: "Ders öncesi bilgi elinizin altında",
        body: [
          "Üyenin önceki dersleri, harcaması, kalan paketi ve ekibin aldığı notlar müşteri kartında bulunur. Eğitmen, güne telefondan veya PWA üzerinden bakıp seans sırasını görebilir.",
        ],
      },
    ],
    faq: [
      {
        q: "Farklı ders paketleri tanımlanabilir mi?",
        a: "Evet. Üyeye uygun sayıda ders içeren paket tanımlayabilirsiniz. Tamamlanan dersler paketten düşer ve kalan hak kartta görünür.",
      },
      {
        q: "Birebir ve grup derslerini aynı takvimde tutabilir miyim?",
        a: "Evet. Ders türleri ayrı hizmetler olarak tanımlanır; süreleri ve fiyatları farklı olabilir. Hepsi ilgili eğitmenin takviminde görünür.",
      },
      {
        q: "Ders onayı ve hatırlatması otomatik mi?",
        a: "Evet. Randevu sonrasında WhatsApp onayı, ders öncesinde de otomatik hatırlatma gönderilir.",
      },
      {
        q: "Stüdyo sahibi eğitmenlerin sonuçlarını görebilir mi?",
        a: "Evet. Yetkili kullanıcılar her eğitmenin takvimini açabilir; ders sayılarını ve gelir istatistiklerini personel bazında karşılaştırabilir.",
      },
    ],
    trust: {
      title: "Stüdyo ekibine kalan net bir program",
      items: [
        "Birebir, düet ve grup dersleri ayrı tanımlanır",
        "Kalan paket hakları müşteri kartında izlenir",
        "WhatsApp mesajları ekip adına otomatik gönderilir",
        "Eğitmenler kendi takvimlerini mobilde görebilir",
        "Ders ve gelir sonuçları personel bazında incelenir",
      ],
    },
    cta: {
      title: "Ders programınızı düzene koyun",
      text: "Ders türlerini ve eğitmenleri ekleyin; üyelerin kullanacağı randevu bağlantısını hazır edin.",
      button: "Pilates stüdyosu hesabı açın",
    },
    links: [
      { label: "Spor salonu seans düzenini görün", to: "/cozumler/spor-salonu-randevu-programi" },
      { label: "Fizyoterapi takvimine göz atın", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "Diyetisyen randevu akışını inceleyin", to: "/cozumler/diyetisyen-randevu-programi" },
      { label: "Herkese açık randevu sayfasını keşfedin", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Otomatik WhatsApp mesajlarını inceleyin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
    ],
  },

  "tr:vertical:ozel-ders-randevu-programi": {
    intro: [
      "Özel ders programı yalnızca saatlerden oluşmaz. Velinin istediği değişiklik, öğrencinin kalan paketi, yüz yüze ve çevrim içi dersler aynı hafta içinde sürekli güncellenir.",
      "PLANN, dersleri gün ve hafta görünümünde sıralar. Öğrenci veya veli bağlantıdan uygun saati seçebilir; WhatsApp onayı ve hatırlatması otomatik gider, ders geçmişi ve paket hakları kayıtlı kalır.",
    ],
    sections: [
      {
        h2: "Ders vermeden önce yapılan görünmez mesai",
        items: [
          {
            h3: "Saat değişiklikleri mesajlarda kayboluyor",
            text: "Takvimdeki tüm dersler gün ve hafta görünümünde yer alır. Bir saate başka ders yazılmışsa yeni randevuda çakışma önlenir.",
          },
          {
            h3: "Veliye hatırlatmak ayrı bir iş oluyor",
            text: "Kayıtlı numaraya randevu onayı ve ders öncesi hatırlatma WhatsApp üzerinden otomatik gider. Böylece ders araları mesaj listesine ayrılmaz.",
          },
          {
            h3: "Ay sonunda ders sayısı yeniden hesaplanıyor",
            text: "Öğrencinin geçmiş dersleri, toplam harcaması ve paket bakiyesi kartında birlikte görünür. Gelir-gider kayıtları da aynı dönem için incelenebilir.",
          },
        ],
      },
      {
        h2: "Haftalık programı kurmanın kısa yolu",
        body: [
          "Yüz yüze, çevrim içi ve deneme derslerini farklı süre ve fiyatlarla tanımlayabilirsiniz. Randevular herkese açık bağlantıdan veya doğrudan takvimden eklenir.",
          "Yoğunken yazılı ya da sesli yapay zekâ asistanıyla yeni ders oluşturabilirsiniz. Randevu, mevcut programla çakışmadan ilgili saate yerleşir.",
          "İstatistiklerden verilen ders sayısını ve geliri, müşteri kartından ise öğrenciye ait ders geçmişi ile notları görebilirsiniz.",
        ],
      },
      {
        h2: "Sınıfta, evde ya da çevrim içi",
        body: [
          "Dersin nerede yapılacağından bağımsız olarak takvim ve hatırlatma akışı aynı kalır. Mobil/PWA görünümünden günün programına bakabilir, değişiklikleri telefondan işleyebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "Hatırlatma için velinin numarasını kullanabilir miyim?",
        a: "Evet. Randevuda velinin telefonunu kullanırsanız WhatsApp onayı ve hatırlatması o numaraya gönderilir.",
      },
      {
        q: "Öğrencinin kalan ders hakkı nerede görünür?",
        a: "Tanımlanan paketin kalan hakkı öğrenci kartında görünür. Tamamlanan her ders bu bakiyeden düşer.",
      },
      {
        q: "İleri tarihli dersleri topluca planlayabilir miyim?",
        a: "Dersleri takvimde ileri tarihlere ayrı ayrı yerleştirebilirsiniz. Her randevu için ilgili zamana göre otomatik hatırlatma gönderilir.",
      },
      {
        q: "Çevrim içi dersler de aynı programda yer alır mı?",
        a: "Evet. Çevrim içi dersi ayrı bir hizmet olarak tanımlayabilir, diğer derslerle birlikte aynı takvimde yönetebilirsiniz.",
      },
    ],
    trust: {
      title: "Ders takibinde düzenli bir görünüm",
      items: [
        "Dolu saatlere çakışan ders eklenmesi önlenir",
        "Veli veya öğrenciye WhatsApp mesajları otomatik gider",
        "Paket bakiyesi ve ders geçmişi birlikte tutulur",
        "Yazılı ya da sesli asistanla randevu eklenebilir",
        "Program mobil ve PWA üzerinden açılabilir",
      ],
    },
    cta: {
      title: "Haftalık ders programınızı görün",
      text: "Ders türlerinizi tanımlayın, öğrencileriniz için randevu bağlantısını paylaşın.",
      button: "Özel ders hesabı oluşturun",
    },
    links: [
      { label: "Psikolog randevu düzenini inceleyin", to: "/cozumler/psikolog-randevu-programi" },
      { label: "Spor salonu seanslarına göz atın", to: "/cozumler/spor-salonu-randevu-programi" },
      { label: "Pilates ders takvimini keşfedin", to: "/cozumler/pilates-studyo-randevu-programi" },
      { label: "WhatsApp ders hatırlatmalarını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Mobil randevu kullanımını inceleyin", to: "/ozellikler/mobil-randevu-uygulamasi" },
    ],
  },

  "tr:vertical:hali-yikama-randevu-programi": {
    intro: [
      "Halı yıkama işinde telefon sabah erken çalmaya başlar: yeni alım talebi, teslim zamanı sorusu, koltuk yıkama için uygun gün… Bu görüşmeler takvime eksik geçince ekip programı ile müşteri beklentisi birbirinden kopar.",
      "PLANN, alım görüşmelerini ve teslim için ayırdığınız saatleri aynı randevu takviminde tutar. Müşteriye WhatsApp onay ve hatırlatmaları gider; geçmiş işler, harcama ve operasyon notları kartında kalır.",
    ],
    sections: [
      {
        h2: "Telefon kapandıktan sonra unutulan ayrıntılar",
        items: [
          {
            h3: "Alım sözü takvime geçmiyor",
            text: "Görüşme sırasında randevuyu doğrudan takvime eklediğinizde saat ekipçe görünür. Aynı personele aynı zamanda başka iş yazılması önlenir.",
          },
          {
            h3: "Teslim zamanı için tekrar tekrar aranılıyor",
            text: "Teslim için oluşturduğunuz randevunun onayı ve yaklaşan saat hatırlatması WhatsApp üzerinden otomatik gönderilebilir.",
          },
          {
            h3: "Eski müşterinin işi baştan soruluyor",
            text: "Müşteri kartında önceki randevular, toplam harcama ve ekibin yazdığı genel notlar yer alır. Tekrar arayan müşterinin geçmişini hızlıca görürsünüz.",
          },
        ],
      },
      {
        h2: "Alımdan teslim saatine kadar görünür akış",
        body: [
          "Halı, koltuk ve perde yıkama gibi hizmetleri farklı süre ve fiyatlarla tanımlarsınız. Randevuyu telefonda siz açabilir veya alım talebi için herkese açık bağlantınızı paylaşabilirsiniz.",
          "Personel takvimleri gün içindeki işleri ayırır; yetkiler, ekip üyelerinin görebileceği alanları belirler. Takvimde dolu olan saate çakışan kayıt eklenmez.",
          "Gün sonunda gelir ve giderleri kasa ekranında, tamamlanan iş ve hizmet sonuçlarını istatistiklerde inceleyebilirsiniz.",
        ],
      },
      {
        h2: "Yoğun haftaya telefondan bakın",
        body: [
          "Bayram öncesi gibi yoğun dönemlerde gün ve hafta görünümü alınmış randevuları netleştirir. Mobil/PWA üzerinden takvimi açıp yeni talebi uygun personele ekleyebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "Alım ve teslim için iki ayrı randevu açabilir miyim?",
        a: "Evet. Alım ve teslimi ayrı hizmet veya randevu olarak takvime ekleyebilirsiniz. Her biri için kendi saatine göre WhatsApp hatırlatması gönderilir.",
      },
      {
        q: "Müşteriyle ilgili özel ayrıntıları nerede tutarım?",
        a: "Genel müşteri notlarını kartına ekleyebilirsiniz. Aynı kartta geçmiş randevular ve toplam harcama da görünür.",
      },
      {
        q: "Sahadaki çalışanların takvimleri ayrılabilir mi?",
        a: "Evet. Personel için ayrı takvimler ve erişim yetkileri tanımlanabilir. Yönetici tüm programı birlikte görebilir.",
      },
      {
        q: "İş tutarını ve günlük masrafları takip edebilir miyim?",
        a: "Evet. Randevu ve hizmet gelirleriyle işletme giderlerini kaydedebilir, seçtiğiniz dönemin sonuçlarını kasa ve istatistik ekranlarından görebilirsiniz.",
      },
    ],
    trust: {
      title: "Atölye ve saha arasında ortak görünüm",
      items: [
        "Alım ve teslim saatleri randevu takviminde tutulur",
        "Müşteriye WhatsApp onayı ve hatırlatması gider",
        "Personelin işleri ayrı takvimlerde görülebilir",
        "Geçmiş işler ve genel notlar müşteri kartında kalır",
        "Günlük gelir, gider ve iş sayıları izlenir",
      ],
    },
    cta: {
      title: "Günün alım ve teslimlerini netleştirin",
      text: "Hizmetlerinizi ve çalışanlarınızı ekleyin; yeni talepleri gün ve hafta takvimine kaydetmeye başlayın.",
      button: "Halı yıkama hesabı açın",
    },
    links: [
      { label: "Oto kuaför randevu akışını görün", to: "/cozumler/oto-kuafor-randevu-programi" },
      { label: "Oto ekspertiz takvimini inceleyin", to: "/cozumler/oto-ekspertiz-randevu-programi" },
      { label: "WhatsApp müşteri mesajlarını keşfedin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Gelir, gider ve ekip takibine bakın", to: "/ozellikler/gelir-gider-personel-takibi" },
      { label: "Mobil randevu ekranını inceleyin", to: "/ozellikler/mobil-randevu-uygulamasi" },
    ],
  },

  "tr:vertical:oto-kuafor-randevu-programi": {
    intro: [
      "Sabah hızlı yıkamalar peş peşe gelirken detaylı temizlik öğleden sonrayı kaplayabilir. Oto kuaförde hizmet süreleri farklı olduğu için telefonda verilen tek bir yanlış saat günün kalanını geciktirir.",
      "PLANN, her hizmeti kendi süresiyle takvime yerleştirir ve aynı personele çakışan randevuyu önler. Müşteri bağlantıdan saat seçer; WhatsApp onayı ve hatırlatması otomatik gider.",
    ],
    sections: [
      {
        h2: "Anahtar teslimleri arasında aksayan işler",
        items: [
          {
            h3: "Kısa ve uzun işlemler üst üste geliyor",
            text: "Dış yıkama ile detaylı bakım aynı süreyi almaz. Hizmet süreleri ayrı tanımlandığında takvim, personele ayrılan zamanı doğru gösterir.",
          },
          {
            h3: "Müşteri randevu saatini karıştırıyor",
            text: "Rezervasyon sonrasında WhatsApp onayı, işlem öncesinde hatırlatma otomatik gönderilir. Ekip gün içinde tekrar tekrar mesaj yazmaz.",
          },
          {
            h3: "Aracın önceki işlemleri hatırlanmıyor",
            text: "Müşteri kartında geçmiş randevular, toplam harcama ve araçla ilgili yazdığınız genel notlar bulunur. Düzenli müşteri geldiğinde önceki işlemler görülebilir.",
          },
        ],
      },
      {
        h2: "Hizmet süresine göre çalışan takvim",
        body: [
          "İç-dış yıkama, pasta-cila, detaylı temizlik ve seramik uygulamasını farklı süre ve fiyatlarla eklersiniz. Müşteri açık bağlantıdan hizmeti ve uygun saati seçebilir.",
          "Telefonla gelen randevuyu ekip panelden, yazılı veya sesli yapay zekâ asistanıyla ekleyebilir. Takvim dolu saati gösterir ve personel çakışmasını önler.",
          "Hizmet bazlı gelirleri, personel sonuçlarını ve günlük gelir-gider hareketlerini rapor ekranlarından izleyebilirsiniz.",
        ],
      },
      {
        h2: "Önceki işlemleri yeni randevuda görün",
        body: [
          "Kartta görünen geçmiş işler ve notlar, müşterinin son ziyaretini hatırlamayı kolaylaştırır. Mobil/PWA ekranından günün programına bakıp ekip içindeki iş dağılımını görebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "Tam gün süren bir işlemi takvime ekleyebilir miyim?",
        a: "Evet. Hizmet için uygun süreyi tanımlarsınız; randevu takvimde bu süre boyunca yer alır ve aynı personele çakışan kayıt eklenmez.",
      },
      {
        q: "İşlem öncesinde müşteriye otomatik mesaj gider mi?",
        a: "Evet. Randevu oluşturulduğunda WhatsApp onayı, belirlenen zamanda da hatırlatma otomatik gönderilir.",
      },
      {
        q: "Kapıdan gelen aracı takvime yazabilir miyim?",
        a: "Evet. Randevuyu doğrudan panelden ekleyebilirsiniz. Müşteri kaydı oluşur ve işlem geçmişi sonraki ziyaretlerde görünür.",
      },
      {
        q: "Hangi hizmetten ne kadar gelir geldiğini görebilir miyim?",
        a: "Evet. Seçtiğiniz dönemde hizmet bazlı gelir ve randevu istatistiklerini inceleyebilir, giderleri kasa ekranından takip edebilirsiniz.",
      },
    ],
    trust: {
      title: "Oto kuaförde daha düzenli bir gün",
      items: [
        "Her işlem takvimde kendi süresi kadar yer alır",
        "Personel saatlerinde randevu çakışması önlenir",
        "WhatsApp onay ve hatırlatmaları otomatik gider",
        "Müşteri geçmişi, harcaması ve notları saklanır",
        "Hizmet gelirleri ve günlük giderler izlenir",
      ],
    },
    cta: {
      title: "İşlem sürelerini takvime doğru yansıtın",
      text: "Hizmetleri ve çalışanları ekleyin; müşterilerin kullanacağı randevu bağlantısını paylaşın.",
      button: "Oto kuaför hesabı oluşturun",
    },
    links: [
      { label: "Oto ekspertiz randevularını inceleyin", to: "/cozumler/oto-ekspertiz-randevu-programi" },
      { label: "Halı yıkama iş takvimine bakın", to: "/cozumler/hali-yikama-randevu-programi" },
      { label: "WhatsApp randevu mesajlarını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Açık randevu bağlantısını keşfedin", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Gelir, gider ve personel ekranını inceleyin", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:oto-ekspertiz-randevu-programi": {
    intro: [
      "Oto ekspertizde alıcı, satıcı ve istasyon aynı saatte buluşur. Bir randevu geciktiğinde sıradaki araç da bekler; özellikle cumartesi sabahı telefondaki programı takip etmek zorlaşır.",
      "PLANN, ekspertiz paketlerini süreleriyle takvime yerleştirir. Müşteri açık bağlantıdan saat seçer, WhatsApp onayı ve hatırlatması alır; ekip hangi aracın ne zaman geleceğini gün takviminde görür.",
    ],
    sections: [
      {
        h2: "İstasyonda beklemeye dönüşen aksaklıklar",
        items: [
          {
            h3: "Telefonda aynı saate iki söz veriliyor",
            text: "Takvimde dolu zaman görünür ve aynı personele çakışan ikinci randevu eklenmez. Ekip, gelen aracı hangi saatte beklediğini birlikte görür.",
          },
          {
            h3: "Alıcı saat bilgisini sonradan arıyor",
            text: "Randevu kaydedildiğinde WhatsApp onayı, işlem yaklaşınca hatırlatma otomatik gider. Kayıtlı numaradaki kişi saat bilgisini mesajında görür.",
          },
          {
            h3: "Paket seçimi telefonda uzuyor",
            text: "Ekspertiz seçeneklerini süre ve fiyatlarıyla açık randevu sayfasında gösterebilirsiniz. Müşteri uygun hizmeti ve saati kendisi seçer.",
          },
        ],
      },
      {
        h2: "Araç kabulünü takvimden başlatın",
        body: [
          "Tam ekspertiz, motor kontrolü veya kaporta-boya kontrolü gibi hizmetleri ayrı ayrı tanımlarsınız. Her biri takvimde belirlediğiniz süre kadar yer tutar.",
          "Telefon görüşmesi sürerken randevuyu panelden ya da yazılı/sesli yapay zekâ asistanıyla ekleyebilirsiniz. Personel takvimleri ve yetkileri ekip içindeki görünümü düzenler.",
          "Günlük araç sayısı, hizmet bazlı gelirler ve işletme giderleri istatistik ile kasa ekranlarında izlenebilir.",
        ],
      },
      {
        h2: "Düzenli iş gönderen firmaları ayırın",
        body: [
          "Galeri veya kurumsal müşteri kartında geçmiş randevular, toplam harcama ve ekip notları birikir. Yeni araç için görüşürken önceki çalışma hacmini aynı karttan görebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "Ekspertiz seçeneklerinin süreleri farklı olabilir mi?",
        a: "Evet. Her hizmeti kendi süresi ve fiyatıyla tanımlayabilirsiniz. Seçilen paket, takvimde belirlenen süre kadar yer alır.",
      },
      {
        q: "Onay mesajı alıcıya mı satıcıya mı ulaşır?",
        a: "WhatsApp onayı ve hatırlatması randevuda kayıtlı telefon numarasına gönderilir. Hangi tarafın numarası kaydedildiyse mesajı o kişi alır.",
      },
      {
        q: "Hafta sonu telefon yoğunluğunu azaltabilir miyim?",
        a: "Herkese açık randevu bağlantısını paylaşabilirsiniz. Müşteri, tanımladığınız müsait saatlerden birini seçerek telefon görüşmesi olmadan randevu oluşturur.",
      },
      {
        q: "Günlük araç adedi ve gelir görünür mü?",
        a: "Evet. Randevu ve hizmet istatistikleri araç sayısını ve geliri gösterir; günlük giderleri de kasa ekranında takip edebilirsiniz.",
      },
    ],
    trust: {
      title: "Araç kabulü için ortak bir plan",
      items: [
        "Paketler kendi süre ve fiyatlarıyla tanımlanır",
        "Personel takvimlerinde çakışan saatler önlenir",
        "Müşteri açık bağlantıdan randevu oluşturabilir",
        "WhatsApp onayı ve hatırlatması otomatik gider",
        "Araç adedi, gelir ve gider sonuçları izlenir",
      ],
    },
    cta: {
      title: "Günün araçlarını sıraya koyun",
      text: "Ekspertiz hizmetlerinizi ve ekibinizi tanımlayın; randevu bağlantısını müşterilerinizle paylaşın.",
      button: "Ekspertiz hesabı oluşturun",
    },
    links: [
      { label: "Oto kuaför iş takvimini inceleyin", to: "/cozumler/oto-kuafor-randevu-programi" },
      { label: "Halı yıkama randevu akışına bakın", to: "/cozumler/hali-yikama-randevu-programi" },
      { label: "Otomatik WhatsApp mesajlarını keşfedin", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Herkese açık randevu sayfasını görün", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Gelir, gider ve ekip takibini inceleyin", to: "/ozellikler/gelir-gider-personel-takibi" },
    ],
  },

  "tr:vertical:veteriner-randevu-programi": {
    intro: [
      "Veteriner kliniğinde rutin muayeneler sürerken acil bir telefon gelebilir, kontrol uzayabilir, resepsiyon aynı anda birkaç kişiye saat vermeye çalışabilir. Gün içindeki değişiklikler ayrı notlarda kalınca bekleme artar.",
      "PLANN, her hekimin randevularını personel takviminde gösterir. Hayvan sahibi bağlantıdan uygun saati seçebilir; WhatsApp onayı ve hatırlatması otomatik gider, ziyaret geçmişi ile genel müşteri notları kartta görünür.",
    ],
    sections: [
      {
        h2: "Muayene akışını bölen günlük işler",
        items: [
          {
            h3: "Rutin randevular için telefon sürekli çalıyor",
            text: "Muayene ve kontrol gibi hizmetleri açık randevu sayfasında sunabilirsiniz. Hayvan sahibi, tanımlanan uygun saatlerden birini kendi seçer.",
          },
          {
            h3: "Kontrol tarihi yalnızca not kâğıdında kalıyor",
            text: "Bir sonraki kontrolü ileri tarihli randevu olarak oluşturduğunuzda, zamanı yaklaşınca kayıtlı numaraya WhatsApp hatırlatması otomatik gönderilir.",
          },
          {
            h3: "Hekimlerin programları resepsiyonda birleşmiyor",
            text: "Her hekimin takvimi ayrı görünür; yönetici tüm randevuları birlikte izleyebilir. Yetkiler, ekip üyelerinin erişebileceği alanları sınırlar.",
          },
        ],
      },
      {
        h2: "Resepsiyondan hekime ortak takvim",
        body: [
          "Muayene, kontrol, tırnak kesimi ve bakım gibi hizmetleri süre ve fiyatlarıyla tanımlarsınız. Randevuyu hayvan sahibi bağlantıdan, resepsiyon ise panelden ekleyebilir.",
          "Yoğun bir telefon görüşmesinde yazılı veya sesli yapay zekâ asistanıyla randevu oluşturabilirsiniz. Takvim, ilgili hekimin dolu saatine çakışan kayıt eklenmesini önler.",
          "Hizmet ve hekim bazlı randevu ile gelir istatistiklerini görebilir; kliniğin gelir-gider hareketlerini kasa ekranında takip edebilirsiniz.",
        ],
      },
      {
        h2: "Önceki ziyaret bilgilerini kolayca bulun",
        body: [
          "Müşteri kartında önceki randevular, toplam harcama ve ekibin eklediği genel notlar yer alır. Aynı kişinin birden fazla hayvanı varsa hangi hayvan için geldiğini randevu notunda belirtebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "İleri tarihli kontrol için hatırlatma gönderilir mi?",
        a: "Evet. Kontrolü randevu olarak takvime eklediğinizde, belirlenen zamanda kayıtlı numaraya otomatik WhatsApp hatırlatması gider.",
      },
      {
        q: "Aynı kişinin farklı hayvanlarını nasıl ayırırım?",
        a: "Müşteri kartındaki genel notları ve her randevunun not alanını kullanabilirsiniz. Randevuda hangi hayvan için gelindiğini belirterek geçmiş görüşmeleri ayırt edebilirsiniz.",
      },
      {
        q: "Acil durum geldiğinde program değiştirilebilir mi?",
        a: "Evet. Randevuları takvimde farklı saatlere taşıyabilir veya yeni saat oluşturabilirsiniz. Güncel program, yetkili ekip üyelerinin ekranında görünür.",
      },
      {
        q: "Her hekim yalnızca kendi takvimini görebilir mi?",
        a: "Personel takvimleri ayrıdır ve erişim yetkileri düzenlenebilir. Yönetici, gün ve hafta görünümünde hekimlerin programlarını birlikte izleyebilir.",
      },
    ],
    trust: {
      title: "Klinik gününü bir arada tutan ayrıntılar",
      items: [
        "Hekim takvimleri ayrı, yönetici görünümü ortaktır",
        "Dolu saate çakışan randevu eklenmesi önlenir",
        "WhatsApp onay ve hatırlatmaları otomatik gönderilir",
        "Ziyaret geçmişi ve genel notlar müşteri kartında kalır",
        "Hizmet, personel, gelir ve gider sonuçları izlenir",
      ],
    },
    cta: {
      title: "Klinik takvimini ekipçe görün",
      text: "Hizmetleri ve hekimleri ekleyin; hayvan sahipleri için randevu bağlantınızı paylaşın.",
      button: "Veteriner kliniği hesabı açın",
    },
    links: [
      { label: "Diş kliniği randevu düzenini inceleyin", to: "/cozumler/dis-klinigi-randevu-programi" },
      { label: "Fizyoterapi takvimine göz atın", to: "/cozumler/fizyoterapi-randevu-programi" },
      { label: "WhatsApp onay ve hatırlatmalarını görün", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Açık randevu sayfasını keşfedin", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Yapay zekâ randevu asistanını inceleyin", to: "/ozellikler/yapay-zeka-randevu-asistani" },
    ],
  },

  // ==========================================================================
  // TR — ÖZELLİK SAYFALARI (/ozellikler/*)
  // ==========================================================================
  "tr:feature:yapay-zeka-randevu-asistani": {
    intro: [
      "Telefonda bir müşteriyle konuşurken takvimde doğru günü bulmak, hizmeti seçmek ve kaydı tamamlamak işi gereksiz yere bölebilir. PLANN'in yapay zeka asistanına müşteri, hizmet ve zaman bilgisini doğal bir cümleyle yazabilir; randevuyu bu komuttan oluşturabilirsiniz.",
      "Aynı işlem sesli komutla da yapılabilir. Asistanın rolü işletme kararlarını sizin yerinize vermek değil, verdiğiniz randevu bilgisini PLANN takvimine daha kısa yoldan aktarmaktır.",
    ],
    sections: [
      {
        h2: "Komuttan takvim kaydına",
        items: [
          {
            h3: "Kısa bir cümleyle randevu girin",
            text: "\"Salı 10.30, Deniz, cilt bakımı\" gibi müşteri, zaman ve hizmet içeren bir komut verirsiniz. Asistan bu bilgileri kullanarak randevuyu oluşturur; ardından kayıt, elle girilen diğer randevularla aynı takvimde yer alır.",
          },
          {
            h3: "Yazmak uygun değilse konuşun",
            text: "Telefonunuzdan sesli komut vererek de randevu oluşturabilirsiniz. Bu seçenek özellikle elleriniz doluyken veya masa başında olmadığınızda form alanları arasında dolaşma ihtiyacını azaltır.",
          },
          {
            h3: "Takvim kuralları korunur",
            text: "Asistan ayrı bir ajanda kullanmaz. Randevuyu PLANN'in gün ve hafta görünümlerinde kullanılan takvime ekler; sistemin çakışma önleme kontrolü bu kayıtlar için de geçerlidir.",
          },
        ],
      },
      {
        h2: "Oluşturulan randevu nerede görünür?",
        body: [
          "Yapay zekayla eklenen kayıt, mevcut müşteri ve hizmet yapınızın içinde çalışır. Takvimde personel, saat ve hizmet bilgileriyle görünür; daha sonra aynı ekrandan incelenebilir veya gerektiğinde düzenlenebilir.",
          "Geçerli telefon numarası bulunan randevular, PLANN'deki standart iletişim akışını izler. Otomatik WhatsApp onayı ve zamanı geldiğinde hatırlatma, WhatsApp'ın resmi mesajlaşma kanalı üzerinden gönderilir.",
        ],
      },
      {
        h2: "Asistanın kapsamı nedir?",
        body: [
          "Asistan, yazılı veya sesli olarak verdiğiniz randevu bilgilerini takvime aktarır. Kayıt oluşturulduktan sonra tarih, saat, müşteri ve hizmet ayrıntılarını takvimde görebilir, gerektiğinde düzenleyebilirsiniz.",
        ],
      },
    ],
    faq: [
      {
        q: "Yapay zeka asistanıyla hangi işlemi yapabilirim?",
        a: "Müşteri, hizmet, tarih ve saat bilgisi vererek yazılı veya sesli komuttan randevu oluşturabilirsiniz. Özellik, randevu girişini kısaltmak için tasarlanmıştır.",
      },
      {
        q: "Sesli kullanım için ayrı bir ekipman gerekir mi?",
        a: "Hayır. PLANN'i kullandığınız telefonun mikrofonuyla komut verebilirsiniz; ayrıca özel bir mikrofon satın almanız gerekmez.",
      },
      {
        q: "Bu randevular normal takvimden ayrı mı tutulur?",
        a: "Hayır. Asistanın oluşturduğu kayıtlar, elle veya online randevu sayfasından eklenen kayıtlarla aynı PLANN takviminde görünür ve aynı çakışma kontrollerine tabidir.",
      },
      {
        q: "Komutta bir bilgiyi yanlış söylersem ne yapmalıyım?",
        a: "Oluşan randevuyu takvimden açarak müşteri, hizmet, personel ve zaman bilgilerini kontrol edebilir; yanlış olan alanı düzenleyebilirsiniz.",
      },
    ],
    trust: {
      title: "Randevu girişini hızlandıran seçenekler",
      items: [
        "Doğal Türkçe metinden randevu oluşturma",
        "Telefon mikrofonuyla sesli randevu girişi",
        "Gün ve hafta takvimiyle ortak kayıt yapısı",
        "Yeni kayıtlarda mevcut çakışma kontrolünün korunması",
        "Uygun kayıtlarda standart WhatsApp mesaj akışının sürmesi",
      ],
    },
    cta: {
      title: "Bir sonraki randevuyu tek cümleyle ekleyin",
      text: "PLANN hesabınızı oluşturun; hizmetlerinizi ekledikten sonra randevuları yazarak veya söyleyerek kaydedin.",
      button: "PLANN hesabı oluşturun",
    },
    links: [
      { label: "Otomatik WhatsApp onay ve hatırlatmaları", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "İşletmenize ait online rezervasyon linki", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "PLANN'i telefondan kullanma seçenekleri", to: "/ozellikler/mobil-randevu-uygulamasi" },
      { label: "Berber takvimini dijital yönetme", to: "/cozumler/berber-randevu-programi" },
      { label: "Kuaför randevularını gün ve hafta görünümünde izleme", to: "/cozumler/kuafor-randevu-programi" },
    ],
  },

  "tr:feature:whatsapp-randevu-hatirlatma": {
    intro: [
      "Randevu bilgilerini tek tek WhatsApp'tan yazmak, her yeni kayıtta aynı tarih ve saat metnini yeniden hazırlamak demektir. Hatırlatma zamanı geldiğinde ise yoğunluk yüzünden bazı müşteriler gözden kaçabilir.",
      "PLANN, randevu oluşturulduğunda otomatik onay ve randevu öncesinde otomatik hatırlatma gönderir. İletim resmi WhatsApp API üzerinden yapılır; kişisel telefonunuzdan elle mesaj göndermeniz gerekmez.",
    ],
    sections: [
      {
        h2: "İki mesaj, tek randevu akışı",
        body: [
          "Onay mesajı, müşteriye kaydın tarih ve saatini randevu oluşturulduktan sonra iletir. Böylece telefon görüşmesinde veya yüz yüze konuşmada verilen bilginin yazılı bir karşılığı müşterinin WhatsApp'ında bulunur.",
          "Hatırlatma mesajı ise randevu yaklaşırken otomatik olarak gönderilir. Müşteri, tarih ve saat bilgisini WhatsApp konuşmasında yeniden görebilir.",
        ],
      },
      {
        h2: "Mesajlar hangi kayıtlarda çalışır?",
        items: [
          {
            h3: "Online alınan randevular",
            text: "Müşteri işletmenize özel linkten uygun bir saat seçtiğinde randevu PLANN'e kaydolur. Telefon bilgisi uygun olduğunda onay ve hatırlatma akışı bu kayıt için uygulanır.",
          },
          {
            h3: "Ekip tarafından girilen randevular",
            text: "Telefonla ya da işletmede alınan randevuyu takvime siz eklediğinizde de otomatik mesaj akışı kullanılabilir. Mesajın gönderilebilmesi için müşteri telefon bilgisinin doğru kaydedilmesi gerekir.",
          },
          {
            h3: "Asistanla oluşturulan randevular",
            text: "Yazılı veya sesli yapay zeka komutuyla oluşturulan kayıtlar aynı takvime girer. Gerekli müşteri bilgisi bulunduğunda WhatsApp iletişimi diğer randevularla aynı şekilde yürür.",
          },
        ],
      },
      {
        h2: "Resmi API kullanımı ne sağlar?",
        body: [
          "Gönderimler WhatsApp'ın resmi mesajlaşma kanalıyla PLANN tarafından yapılır. İşletme telefonunu veya bir tarayıcı oturumunu açık tutmanız gerekmez.",
        ],
      },
    ],
    faq: [
      {
        q: "Onay ve hatırlatma mesajlarını kim gönderiyor?",
        a: "Gönderim PLANN tarafından resmi WhatsApp API üzerinden otomatik yürütülür. Her randevu için kişisel WhatsApp hesabınızdan elle işlem yapmazsınız.",
      },
      {
        q: "Müşteri numarası olmadan mesaj iletilebilir mi?",
        a: "Hayır. WhatsApp mesajının hedefe ulaşabilmesi için randevuya bağlı müşterinin geçerli telefon numarasının sistemde bulunması gerekir.",
      },
      {
        q: "Telefonda aldığım randevuya da hatırlatma gider mi?",
        a: "Randevuyu PLANN takvimine kaydedip müşteri telefonunu eklediğinizde, kayıt otomatik onay ve hatırlatma akışına dahil olabilir.",
      },
      {
        q: "Hatırlatma mesajı ne zaman gönderilir?",
        a: "PLANN, kayıtlı randevu yaklaşırken müşterinin telefon numarasına otomatik WhatsApp hatırlatması gönderir.",
      },
    ],
    trust: {
      title: "Randevu mesajlarında düzenli bir akış",
      items: [
        "Randevu kaydından sonra otomatik onay mesajı",
        "Randevu öncesinde planlı otomatik hatırlatma",
        "WhatsApp'ın resmi API kanalı üzerinden gönderim",
        "Online, elle ve asistanla eklenen kayıtlarda ortak akış",
        "Gönderim için doğru müşteri telefonu gereksinimi",
      ],
    },
    cta: {
      title: "Tekrarlanan randevu mesajlarını otomatikleştirin",
      text: "PLANN hesabınızı oluşturun; randevu onaylarını ve yaklaşan randevu hatırlatmalarını otomatik gönderin.",
      button: "PLANN hesabı oluşturun",
    },
    links: [
      { label: "Müşterinin saat seçebildiği randevu sayfası", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Yazılı ve sesli komutla randevu ekleme", to: "/ozellikler/yapay-zeka-randevu-asistani" },
      { label: "Berberler için düzenli randevu takibi", to: "/cozumler/berber-randevu-programi" },
      { label: "Güzellik merkezlerinde müşteri planlaması", to: "/cozumler/guzellik-merkezi-randevu-programi" },
      { label: "Diş klinikleri için randevu düzeni", to: "/cozumler/dis-klinigi-randevu-programi" },
    ],
  },

  "tr:feature:online-randevu-sayfasi": {
    intro: [
      "Müşteri yalnızca boş saatleri öğrenmek için aradığında hem onun hem ekibin zamanı harcanır. Mesai dışında gelen talep ise yanıt beklerken başka bir işletmeye yönelebilir.",
      "PLANN, işletmenize paylaşabileceğiniz bir online randevu linki verir. Müşteri uygulama indirmeden hizmeti, uygun personeli ve takvimde açık olan saati seçer; oluşturulan kayıt işletmenin kullandığı aynı PLANN takvimine eklenir.",
    ],
    sections: [
      {
        h2: "Müşteri linki açtığında ne yapar?",
        items: [
          {
            h3: "Sunulan hizmeti seçer",
            text: "İşletmede tanımladığınız hizmetler randevu sayfasında listelenir. Müşteri ihtiyacına uygun hizmeti seçerek bu hizmet için müsaitlik adımına ilerler.",
          },
          {
            h3: "Uygun personel ve saati belirler",
            text: "Ekipli işletmelerde personel seçimi yapılabilir. Sayfa mevcut takvim kayıtlarını dikkate alır ve dolu saatlerin yeniden alınmasını engelleyen PLANN kurallarıyla çalışır.",
          },
          {
            h3: "Bilgilerini girip kaydı tamamlar",
            text: "Müşteri iletişim bilgilerini vererek randevuyu oluşturur. Kayıt doğrudan işletmenizin PLANN takvimine eklenir; uygun telefon bilgisi varsa otomatik WhatsApp onayı gönderilir.",
          },
        ],
      },
      {
        h2: "Tek linki farklı kanallarda paylaşın",
        body: [
          "İşletmenize ait randevu bağlantısını Instagram profilinde, Google işletme bilgilerinde, web sitenizde veya WhatsApp konuşmalarında paylaşabilirsiniz. Bağlantıyı gören müşteri doğrudan seçim ekranına gider.",
          "Link 24 saat erişilebilir olsa da müşteriye gösterilen seçenekler işletmenizin tanımladığı çalışma düzeni ve mevcut randevularla sınırlıdır. Böylece mesai dışında talep alınabilirken takvim kuralları korunur.",
        ],
      },
      {
        h2: "Online ve işletme içi kayıtlar birleşir",
        body: [
          "Müşterinin linkten aldığı randevu ile ekibin telefon görüşmesi sonrası girdiği randevu ayrı listelerde tutulmaz. Her ikisi de gün ve hafta görünümünde aynı takvimi kullanır; bu ortak yapı çakışan saatlerin yeniden seçilmesini önlemeye yardımcı olur.",
        ],
      },
    ],
    faq: [
      {
        q: "Randevu alan kişinin PLANN hesabı açması gerekir mi?",
        a: "Hayır. Müşteri, işletmenin paylaştığı bağlantıyı telefon veya bilgisayar tarayıcısında açarak randevu adımlarını tamamlar.",
      },
      {
        q: "Link, takvimde dolu olan bir saati gösterebilir mi?",
        a: "Randevu sayfası işletmenin aynı PLANN takvimini kullanır ve mevcut kayıtlarla çakışan seçimleri önleyecek şekilde çalışır. Takvimin doğru tutulması bu nedenle önemlidir.",
      },
      {
        q: "Randevu sayfasını nerelerde kullanabilirim?",
        a: "Bağlantıyı sosyal medya profillerinde, işletme sayfanızda, kendi web sitenizde ve müşterilerle yaptığınız dijital yazışmalarda paylaşabilirsiniz.",
      },
      {
        q: "Müşteri online randevu alınca ekip nereden görür?",
        a: "Kayıt, işletmenin PLANN gün ve hafta takvimine eklenir. Yetkili ekip üyeleri kendi erişim kapsamlarına göre randevuyu panelden veya mobil uygulamadan görebilir.",
      },
    ],
    trust: {
      title: "Online randevu sayfasının çalışma biçimi",
      items: [
        "İşletmeye özel, tarayıcıdan açılan paylaşılabilir link",
        "Hizmet, personel ve uygun saat seçimi",
        "Mevcut takvime dayalı çakışma önleme",
        "Online ve ekip tarafından girilen kayıtların aynı gün ve hafta görünümünde yer alması",
        "Uygun müşteri bilgisinde otomatik WhatsApp onayı",
      ],
    },
    cta: {
      title: "Müşteriye saat sormak yerine seçim alanı verin",
      text: "PLANN hesabınızı oluşturun, hizmetlerinizi ve ekibinizi tanımlayın; ardından randevu bağlantınızı paylaşın.",
      button: "PLANN hesabı oluşturun",
    },
    links: [
      { label: "Randevu sonrası WhatsApp iletişimi", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Komut vererek takvime kayıt ekleme", to: "/ozellikler/yapay-zeka-randevu-asistani" },
      { label: "Kuaförler için online takvim düzeni", to: "/cozumler/kuafor-randevu-programi" },
      { label: "Protez tırnak stüdyolarında saat planlama", to: "/cozumler/protez-tirnak-randevu-programi" },
      { label: "Oto ekspertiz randevularını planlama", to: "/cozumler/oto-ekspertiz-randevu-programi" },
    ],
  },

  "tr:feature:gelir-gider-personel-takibi": {
    intro: [
      "Randevu takvimi günün kiminle dolu olduğunu gösterir; işletmeyi yönetmek için bunun yanında tahsilatı, gideri, personel iş yükünü ve müşteri geçmişini de görmek gerekir. Bilgiler farklı defterlerde kaldığında bütün resmi çıkarmak zorlaşır.",
      "PLANN, operasyonel gelir-gider kayıtlarını ve istatistikleri randevu düzeniyle aynı panelde toplar. Personel takvimleri ile erişim yetkileri ayrı ayrı yönetilebilir; müşteri kartlarında geçmiş, harcama ve notlar izlenebilir.",
    ],
    sections: [
      {
        h2: "İşletme verisini üç açıdan izleyin",
        items: [
          {
            h3: "Gelir ve gider hareketleri",
            text: "Randevuya bağlı gelirleri ve işletme giderlerini kaydederek para hareketlerini seçtiğiniz tarih aralığına göre inceleyebilirsiniz.",
          },
          {
            h3: "Personel takvimi ve erişimi",
            text: "Her ekip üyesinin randevuları personel bazlı takvimde izlenir. Yönetici, kullanıcıların hangi alanlara erişebileceğini yetkilerle sınırlar; herkesin tüm işletme verisini görmesi gerekmez.",
          },
          {
            h3: "Müşteri geçmişi ve seanslar",
            text: "Müşteri kartında önceki randevular, harcama bilgileri ve ekip notları tutulabilir. Seans paketi kullanan işletmeler paket satışını ve kalan seans sayısını işletme panelinden takip edebilir.",
          },
        ],
      },
      {
        h2: "İstatistikler ne anlatır?",
        body: [
          "PLANN'in istatistik ekranları randevu, gelir ve personel verilerini toplu biçimde incelemeyi sağlar. Böylece hangi dönemde kaç randevu olduğunu ve işletme hareketlerinin nasıl dağıldığını kayıtlar üzerinden değerlendirebilirsiniz.",
          "Gelir, gider ve tamamlanan randevuları düzenli kaydettiğinizde dönem sonuçlarını karşılaştırmak ve iş yoğunluğunu değerlendirmek kolaylaşır.",
        ],
      },
      {
        h2: "Yetki, görünürlüğü belirler",
        body: [
          "Yönetici ekip üyelerine görevlerine uygun erişim tanımlar. Personel kendi takvimine odaklanabilirken yönetim, işletme genelindeki takvimleri ve erişime açılan finansal göstergeleri inceleyebilir.",
        ],
      },
    ],
    faq: [
      {
        q: "Gelir ve giderleri hangi dönem için inceleyebilirim?",
        a: "Kaydettiğiniz gelir ve giderleri seçtiğiniz tarih aralığında görüntüleyebilir, aynı döneme ait işletme istatistikleriyle birlikte değerlendirebilirsiniz.",
      },
      {
        q: "Her personel aynı bilgileri mi görür?",
        a: "Hayır. Kullanıcı erişimleri işletmenin belirlediği yetkilere göre sınırlandırılabilir. Personel bazlı takvim ve izin yapısı, görev dışındaki verilere erişimi azaltır.",
      },
      {
        q: "Bir müşterinin geçmişini nereden izlerim?",
        a: "Müşteri kartında randevu geçmişini, kayıtlı harcama bilgisini ve ekip tarafından eklenen notları bir arada inceleyebilirsiniz.",
      },
      {
        q: "Seans paketleri bu bölümde takip edilebilir mi?",
        a: "Evet. Paket satışını, kullanılan seansları ve kalan seans sayısını işletme panelindeki müşteri kaydından izleyebilirsiniz.",
      },
    ],
    trust: {
      title: "Operasyon takibinde elinizde olanlar",
      items: [
        "İşletme içi gelir ve gider kayıtları",
        "Randevu ve finans hareketlerinden üretilen istatistikler",
        "Personel bazlı takvimler ve erişim yetkileri",
        "Müşteri geçmişi, harcama bilgisi ve ekip notları",
        "Paket satışı ile kalan seansların işletme panelinden takibi",
      ],
    },
    cta: {
      title: "Takvimden işletme görünümüne geçin",
      text: "PLANN hesabınızı oluşturun; randevuları, gelir-gider hareketlerini, ekip erişimlerini ve müşteri kayıtlarını birlikte yönetin.",
      button: "PLANN hesabı oluşturun",
    },
    links: [
      { label: "İşletmeye özel randevu bağlantısı", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "Otomatik WhatsApp randevu mesajları", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Spor salonları için üye ve randevu düzeni", to: "/cozumler/spor-salonu-randevu-programi" },
      { label: "Güzellik merkezlerinde ekip ve müşteri takibi", to: "/cozumler/guzellik-merkezi-randevu-programi" },
      { label: "Diş kliniklerinde personel takvimi yönetimi", to: "/cozumler/dis-klinigi-randevu-programi" },
    ],
  },

  "tr:feature:mobil-randevu-uygulamasi": {
    intro: [
      "Randevular yalnızca bilgisayar başındayken gelmez. İşletme içinde hareket ederken, dışarıdayken veya günün programına hızlıca bakmanız gerektiğinde takvime telefondan ulaşabilmek işleri kolaylaştırır.",
      "PLANN; iOS, Android ve kurulabilir PWA seçenekleriyle mobil kullanım sunar. Takvim, müşteri kayıtları ve yetkinizin izin verdiği işletme alanları telefonda ve bilgisayarda aynı hesap üzerinden açılır.",
    ],
    sections: [
      {
        h2: "Mobilde hangi işler yapılır?",
        items: [
          {
            h3: "Gün ve hafta planını kontrol edin",
            text: "Randevuları günlük veya haftalık görünümde inceleyebilir, müsaitliğe bakabilir ve yeni kayıt ekleyebilirsiniz. Çakışma önleme kuralları mobilde girilen randevular için de aynı takvim üzerinde çalışır.",
          },
          {
            h3: "Müşteri kaydına işin başında ulaşın",
            text: "Müşterinin önceki randevularını, kayıtlı harcama bilgisini ve ekip notlarını telefondan görebilirsiniz. Görünen alanlar kullanıcının rolüne ve işletmenin verdiği yetkilere bağlıdır.",
          },
          {
            h3: "Randevuyu konuşarak ekleyin",
            text: "Mobil cihazın mikrofonunu kullanarak yapay zeka asistanına müşteri, hizmet ve zaman bilgisini söyleyebilirsiniz. Oluşturulan kayıt, diğer giriş yöntemleriyle aynı PLANN takvimine yazılır.",
          },
        ],
      },
      {
        h2: "Ekip üyeleri kendi erişimleriyle çalışır",
        body: [
          "Personel kendi kullanıcı hesabıyla mobil uygulamaya girer ve yetkisi kapsamındaki takvimi kullanır. Yönetici, ekip üyelerinin erişebileceği alanları belirleyerek müşteri, takvim ve işletme bilgilerinin görünürlüğünü sınırlar.",
          "Personel bazlı takvim sayesinde ekip üyesi kendisine atanmış randevulara odaklanırken yönetici gün ve hafta planını ekip genelinde değerlendirebilir.",
        ],
      },
      {
        h2: "Uygulama, PWA ve web aynı hesabı kullanır",
        body: [
          "iPhone, Android telefon, kurulabilir web uygulaması ve masaüstü tarayıcı aynı PLANN hesabındaki güncel kayıtları gösterir. Gördüğünüz içerik, oturum açtığınız hesap ve kullanıcı yetkileriyle belirlenir.",
        ],
      },
    ],
    faq: [
      {
        q: "PLANN'i hangi mobil platformlarda kullanabilirim?",
        a: "PLANN'in iOS ve Android uygulamaları vardır. Desteklenen tarayıcılarda PWA olarak kurulabilir ve normal web arayüzünden de açılabilir.",
      },
      {
        q: "Online randevu alan müşterinin uygulama kurması gerekir mi?",
        a: "Hayır. Mobil uygulamalar işletme ve ekip kullanımı içindir; müşteri kendisine paylaşılan online randevu bağlantısını tarayıcıda açar.",
      },
      {
        q: "Personel mobil uygulamada finansal verileri görür mü?",
        a: "Bu, işletmenin tanımladığı kullanıcı yetkilerine bağlıdır. Yönetici erişimi sınırlandırabilir; mobil uygulama masaüstündeki yetkileri aşan ayrı bir görünürlük vermez.",
      },
      {
        q: "Telefon ve bilgisayar farklı kayıtlar mı tutar?",
        a: "Hayır. Telefon ve bilgisayarda aynı işletme hesabıyla oturum açtığınızda güncel randevu ve müşteri kayıtlarına ulaşırsınız.",
      },
    ],
    trust: {
      title: "Mobil erişimin kapsadığı alanlar",
      items: [
        "iOS, Android ve kurulabilir PWA desteği",
        "Telefondan gün ve hafta randevu görünümü",
        "Yetkiye bağlı müşteri geçmişi, harcama ve not erişimi",
        "Personel bazlı takvim ve rol kontrollü görünürlük",
        "Mobil ve web kullanımında aynı güncel kayıtların gösterilmesi",
      ],
    },
    cta: {
      title: "Günün programını yanınızda taşıyın",
      text: "PLANN hesabınızı oluşturun; randevu ve müşteri bilgilerine telefondan veya bilgisayardan ulaşın.",
      button: "PLANN hesabı oluşturun",
    },
    links: [
      { label: "Telefondan sesli randevu oluşturma", to: "/ozellikler/yapay-zeka-randevu-asistani" },
      { label: "Müşteriler için uygulamasız randevu alma", to: "/ozellikler/online-randevu-sayfasi" },
      { label: "WhatsApp üzerinden otomatik bilgilendirme", to: "/ozellikler/whatsapp-randevu-hatirlatma" },
      { label: "Halı yıkama ekiplerinde mobil planlama", to: "/cozumler/hali-yikama-randevu-programi" },
      { label: "Özel ders programını telefondan izleme", to: "/cozumler/ozel-ders-randevu-programi" },
    ],
  },

  // ==========================================================================
  // EN-GB — SECTOR PAGES (/solutions/*)
  // ==========================================================================
  "en-GB:vertical:barber-appointment-software": {
    intro: [
      "A walk-in arrives while one client is in the chair and another is asking for Saturday by phone. If bookings live in a paper diary or several message threads, a straightforward morning can quickly become difficult to read.",
      "PLANN gives the shop a clear day or week diary, blocks conflicting appointments and lets clients choose an available time on your public booking page. WhatsApp confirmations and reminders are sent automatically, leaving you to deal with the person in the chair.",
    ],
    sections: [
      {
        h2: "Keep a working barber shop diary",
        items: [
          {
            h3: "See the next gap without stopping the cut",
            text: "The day and week views show each barber's appointments and the gaps between them. When someone rings, you can give a definite answer without checking a notebook and several message threads.",
          },
          {
            h3: "Protect slots from booking conflicts",
            text: "Once a barber has an appointment, that time cannot be booked again in the same diary. Online requests and appointments entered by the team follow the same availability.",
          },
          {
            h3: "Let regulars book after closing",
            text: "Your public booking page gives clients a direct route to your available services and times. Add the link to Instagram, your website or a message, and bookings can arrive without a live phone conversation.",
          },
        ],
      },
      {
        h2: "From first booking to the daily totals",
        body: [
          "Set up cuts, beard trims and combined appointments with the time each service needs. A client chooses an available slot on your booking page; PLANN adds it to the relevant barber's diary and sends the WhatsApp confirmation.",
          "Counter bookings can be entered normally or with the typed or voice AI assistant. A request such as \"Lewis, beard trim, Friday at four\" creates the appointment without working through several screens.",
          "Client cards show previous visits, spend and practical notes, while income, expenses and statistics give the owner a view of the shop beyond today's chair list.",
        ],
      },
      {
        h2: "Give each barber the access they need",
        body: [
          "Separate staff diaries keep a multi-chair shop legible. Permissions can limit what each barber sees, while the owner can review the wider schedule and staff-level figures from the web, PWA or iOS and Android apps.",
        ],
      },
    ],
    faq: [
      {
        q: "Can clients book without installing anything?",
        a: "Yes. The public booking page opens in their browser. They choose a service and an available time there, then receive the confirmation and reminder through WhatsApp.",
      },
      {
        q: "What happens when somebody books at the counter?",
        a: "Add the appointment to the same diary used for online bookings. The conflict check still applies, and the client can receive the same automated WhatsApp messages.",
      },
      {
        q: "Can I add an appointment while my hands are occupied?",
        a: "Yes. The AI assistant accepts typed or voice instructions, so you can state the client, service and time instead of completing the appointment form field by field.",
      },
      {
        q: "Will every barber have access to the full shop figures?",
        a: "Not unless you choose that arrangement. Staff have individual diaries and permissions, allowing you to control access while retaining an owner-level view.",
      },
      {
        q: "Can I check the diary away from the premises?",
        a: "Yes. PLANN is available on iOS, Android and as a PWA, with the same current diary available when you are away from the shop.",
      },
    ],
    trust: {
      title: "Practical tools for the chair and counter",
      items: [
        "Day and week views for a quick check between clients",
        "Conflict prevention across online and staff-entered bookings",
        "Automatic WhatsApp confirmation and reminder messages",
        "Separate barber diaries with controlled permissions",
        "Visit, spend and note history on each client card",
      ],
    },
    cta: {
      title: "Set out the week before the first cut",
      text: "Create your PLANN account, add your services and barbers, then share your booking page.",
      button: "Create a barber shop account",
    },
    links: [
      { label: "Hair salon diary and booking tools", to: "/solutions/hair-salon-appointment-software" },
      { label: "Beauty salon appointment management", to: "/solutions/beauty-salon-appointment-software" },
      { label: "Automated WhatsApp booking messages", to: "/features/whatsapp-appointment-reminders" },
      { label: "A public page for online bookings", to: "/features/online-booking-page" },
      { label: "Staff, income and expense reporting", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:hair-salon-appointment-software": {
    intro: [
      "A fringe trim, full-head colour and bridal styling should not occupy identical blocks in the book. Add several stylists and a late-running colour service, and the shape of the salon day matters as much as the number of bookings.",
      "PLANN builds the diary around service durations and each stylist's availability. Clients use your public page to select a genuine opening, while automated WhatsApp confirmations and reminders handle the routine messages.",
    ],
    sections: [
      {
        h2: "Plan around the work, not uniform slots",
        items: [
          {
            h3: "Reserve enough time for colour",
            text: "Give each service its real duration, from a quick finish to a longer colour booking. The diary only offers times that fit, helping the team avoid an overlap hidden behind a short appointment label.",
          },
          {
            h3: "Keep stylist columns separate",
            text: "Each stylist works from their own diary, and conflicting appointments are prevented. The salon view still lets a manager scan the whole day when allocating a telephone enquiry.",
          },
          {
            h3: "Keep useful details with the client",
            text: "Previous appointments, total spend and free-text notes sit on the client card. Record a colour reference or preferred finish as a working salon note for the next visit.",
          },
        ],
      },
      {
        h2: "What the team sees through the day",
        body: [
          "The morning view shows each stylist's sequence and the time allowed for every service. Appointments made overnight through the public booking page are already in place, with their WhatsApp confirmations sent.",
          "A receptionist can add a telephone booking directly, or use the typed or voice AI assistant for a concise instruction such as \"Priya, roots with Hannah, Thursday at half two\". The same conflict check protects the stylist's existing work.",
          "Income and expense records sit alongside statistics for services and staff, so reviewing the month does not require rebuilding figures from the appointment book.",
        ],
      },
      {
        h2: "Manage repeat services as a package",
        body: [
          "Where the salon sells a defined course of treatments, assign a session package to the client. Completed appointments update the remaining session count, giving reception a clear answer without a separate card or spreadsheet.",
        ],
      },
    ],
    faq: [
      {
        q: "Can a cut and a colour have different booking lengths?",
        a: "Yes. Set a duration for every service. The public page and internal diary use that duration when checking which start times are available.",
      },
      {
        q: "Are confirmations left to the receptionist?",
        a: "No. PLANN automatically sends a WhatsApp confirmation when an appointment is created and a reminder before it begins.",
      },
      {
        q: "Where can a stylist keep a client's colour reference?",
        a: "Use the free-text notes on the client card. The same card also shows visit history and total spend, so practical salon context is available together.",
      },
      {
        q: "Can junior staff have more limited access?",
        a: "Yes. Staff diaries and permissions let the salon decide what each login can view, while managers retain the broader operational picture.",
      },
      {
        q: "Does the booking page work from a social profile?",
        a: "Yes. Share its link in a profile or message. Clients open it in a browser and choose from the services, stylists and times you make available.",
      },
    ],
    trust: {
      title: "A diary shaped for varied salon work",
      items: [
        "Service durations that reflect cuts, colours and styling",
        "Individual stylist diaries with booking conflict checks",
        "Client visit, spend and preference notes together",
        "Session package balances for defined treatment courses",
        "Web, PWA, iOS and Android access for the team",
      ],
    },
    cta: {
      title: "Build a salon day that fits",
      text: "Create your PLANN account, set the length of each service and add your stylists.",
      button: "Create a hair salon account",
    },
    links: [
      { label: "Appointment diaries for barber shops", to: "/solutions/barber-appointment-software" },
      { label: "Booking management for beauty salons", to: "/solutions/beauty-salon-appointment-software" },
      { label: "Scheduling for nail studios", to: "/solutions/nail-studio-appointment-software" },
      { label: "WhatsApp confirmations and reminders", to: "/features/whatsapp-appointment-reminders" },
      { label: "Your browser-based booking page", to: "/features/online-booking-page" },
    ],
  },

  "en-GB:vertical:beauty-salon-appointment-software": {
    intro: [
      "A beauty salon may have a facial beginning as a laser appointment ends, a treatment course to update and two therapists changing shifts. Reception needs one dependable view of people, time and payments.",
      "PLANN brings therapist diaries, client histories, session packages and business figures together. The public booking page follows live availability, and WhatsApp confirmations and reminders are sent without a manual round of messages.",
    ],
    sections: [
      {
        h2: "Give reception clear answers",
        items: [
          {
            h3: "Know which therapist is available",
            text: "Day and week views separate each therapist's appointments. Once their time is taken, PLANN prevents another appointment being placed over it, whether the request comes online or through reception.",
          },
          {
            h3: "Answer package-balance questions",
            text: "Attach a session package to a client and record completed appointments against it. Staff can check the remaining number on the client card instead of counting marks on paper.",
          },
          {
            h3: "Keep commercial context nearby",
            text: "Client cards show appointment history, spend and notes. The team can see the practical relationship with the salon before taking the next booking or discussing a course.",
          },
        ],
      },
      {
        h2: "From client booking to the salon diary",
        body: [
          "List treatments with their prices and durations, then assign staff diaries and permissions. A client booking through your public page sees an available therapist and time rather than an unverified enquiry slot.",
          "PLANN confirms the appointment over WhatsApp and sends the scheduled reminder automatically. Reception can also create a booking from typed or spoken instructions when dealing with a caller at the desk.",
          "Daily income and expenses feed the salon's statistics, making it possible to review treatment and staff activity without copying totals out of the diary.",
        ],
      },
      {
        h2: "Separate responsibilities without separating the information",
        body: [
          "Therapists can work from their own diaries under the permissions you set. Reception and management can have the broader access their roles require, with the current schedule available through the PWA and iOS or Android apps.",
        ],
      },
    ],
    faq: [
      {
        q: "Can PLANN keep count of a prepaid treatment course?",
        a: "Yes. Create a session package for the client and use it as appointments are completed. The client card shows how many sessions remain.",
      },
      {
        q: "How does it stop two clients being put with one therapist?",
        a: "PLANN checks the therapist's current diary for both public and staff-entered bookings. A time already occupied by an appointment cannot be booked again for that therapist.",
      },
      {
        q: "What WhatsApp admin is automated?",
        a: "A confirmation is sent when the appointment is made, followed by an automatic reminder before the booked time. Staff do not need to send those messages one by one.",
      },
      {
        q: "Can management compare treatments and therapists?",
        a: "The income, expense and statistics views provide business reporting across services and staff, alongside the underlying appointment activity.",
      },
      {
        q: "Can therapists be restricted to their own diaries?",
        a: "Yes. Staff permissions can be set around the access each role needs, so a therapist can work from an individual diary while management retains oversight.",
      },
    ],
    trust: {
      title: "Built for the salon's front-desk reality",
      items: [
        "Live therapist diaries with appointment conflict prevention",
        "Remaining package sessions visible to authorised staff",
        "Automated WhatsApp messages for booked appointments",
        "Income, expense and staff activity statistics",
        "Client history, spend and team notes in one card",
      ],
    },
    cta: {
      title: "Give reception one reliable view",
      text: "Create your PLANN account, add therapists, treatments and packages, then bring bookings into one diary.",
      button: "Create a beauty salon account",
    },
    links: [
      { label: "Hair salon scheduling and client history", to: "/solutions/hair-salon-appointment-software" },
      { label: "Nail studio diary software", to: "/solutions/nail-studio-appointment-software" },
      { label: "Client scheduling for dietitians", to: "/solutions/dietitian-appointment-software" },
      { label: "Automatic appointment messages on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Track staff activity, income and expenses", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:nail-studio-appointment-software": {
    intro: [
      "The difference between an infill and detailed new extensions can be hours. When both appear as a name and time in a message thread, the next client's arrival exposes the missing detail.",
      "PLANN reserves time according to the service selected, prevents another booking crossing that appointment and gives clients a public page for choosing an opening. WhatsApp confirmation and reminder messages then follow the booking automatically.",
    ],
    sections: [
      {
        h2: "Protect the long blocks in your day",
        items: [
          {
            h3: "Make the service decide the duration",
            text: "Create separate entries for gel polish, infills, removals and new sets, each with its own length. Available start times are calculated from the chosen service rather than a standard slot.",
          },
          {
            h3: "Replace screenshot scheduling",
            text: "Share the public booking page from your social profile and let clients select an available appointment. The result enters the same diary you use for direct and telephone bookings.",
          },
          {
            h3: "Bring the previous visit into view",
            text: "A client's appointment history, spend and free-text notes are kept together. Shade references, shape preferences or the last service can be checked before the next appointment starts.",
          },
        ],
      },
      {
        h2: "A studio day without diary guesswork",
        body: [
          "Open the day view to see the order of services and the time reserved for each. PLANN prevents overlapping appointments, so a longer set cannot silently run across another confirmed booking.",
          "New appointments receive a WhatsApp confirmation and a reminder before the scheduled time. If a client arranges the next infill at the desk, create that future appointment now and its reminder will follow in due course.",
          "Record takings and expenses as the studio works, then use the statistics to review service income and busy periods rather than estimating from social messages.",
        ],
      },
      {
        h2: "Keep working when the studio grows",
        body: [
          "A solo technician can manage the diary from the PWA or iOS and Android apps. With additional technicians, give each person a diary and suitable permissions while retaining a studio-wide management view.",
        ],
      },
    ],
    faq: [
      {
        q: "Can I allow more time for nail art or a new set?",
        a: "Yes. Services can have different durations, so create the options you actually sell and PLANN will only offer openings long enough for the selection.",
      },
      {
        q: "Can I book a client's next infill before they leave?",
        a: "Yes. Add the future appointment to the diary and PLANN will send its WhatsApp confirmation and reminder at the usual points.",
      },
      {
        q: "Can clients use my booking link from Instagram?",
        a: "Yes. The page opens in a browser, where clients can select an available service and time without installing an app.",
      },
      {
        q: "Can I save a shade or shape preference?",
        a: "Yes. Add it as a free-text note on the client card, alongside their visit history and total spend.",
      },
    ],
    trust: {
      title: "A precise diary for detailed work",
      items: [
        "Different durations for infills, new sets and other services",
        "Conflict checks that protect confirmed appointment time",
        "Future appointments with automatic WhatsApp messaging",
        "Client notes for shades, shapes and practical preferences",
        "Mobile access for solo technicians and studio teams",
      ],
    },
    cta: {
      title: "Reserve the time your work deserves",
      text: "Create your PLANN account, define each service duration and publish your available appointment times.",
      button: "Create a nail studio account",
    },
    links: [
      { label: "Beauty salon bookings and packages", to: "/solutions/beauty-salon-appointment-software" },
      { label: "Hair salon staff diaries", to: "/solutions/hair-salon-appointment-software" },
      { label: "WhatsApp messages for confirmed appointments", to: "/features/whatsapp-appointment-reminders" },
      { label: "Shareable online appointment page", to: "/features/online-booking-page" },
      { label: "Diary access on mobile and web", to: "/features/mobile-appointment-app-pwa" },
    ],
  },

  "en-GB:vertical:dental-clinic-appointment-software": {
    intro: [
      "The diary at a dental practice must distinguish a short examination from a longer procedure and show which clinician is free without keeping a patient on hold. Reception needs that picture to stay current throughout the day.",
      "PLANN provides day and week diaries for the team, blocks conflicting appointments and offers a public booking page for the services you choose to expose. Automated WhatsApp confirmations and reminders cover the routine appointment messages.",
    ],
    sections: [
      {
        h2: "Make the appointment book clear at reception",
        items: [
          {
            h3: "Use realistic appointment lengths",
            text: "Set the duration for each bookable appointment type. Reception and the public page then work from openings that can accommodate that amount of time.",
          },
          {
            h3: "See clinicians independently",
            text: "Each dentist can have a separate diary, while authorised reception or management users can view the wider practice schedule. PLANN prevents two appointments occupying the same clinician's time.",
          },
          {
            h3: "Send the expected booking messages",
            text: "Patients receive a WhatsApp confirmation when the appointment is entered and an automated reminder before it. The front desk does not have to reproduce those messages manually.",
          },
        ],
      },
      {
        h2: "An administrative flow for the practice",
        body: [
          "Create bookable appointment types with durations and prices, then add clinician diaries and permissions. Patients can use the public page for available options, while reception can enter calls directly into the same schedule.",
          "For a fast internal entry, staff can use typed or voice instructions with the AI appointment assistant. The conflict check still applies before the appointment is placed.",
          "Client cards provide appointment history, spend and general administrative notes. Income, expenses and statistics give the practice a separate view of its business activity.",
        ],
      },
      {
        h2: "Handle the next check-up as an appointment",
        body: [
          "If the practice agrees a future check-up before the patient leaves, add it to the diary there and then. PLANN sends the WhatsApp confirmation and reminder for that booked appointment.",
        ],
      },
    ],
    faq: [
      {
        q: "Can the team check appointments away from reception?",
        a: "Yes. Authorised staff can use the web, PWA, iOS or Android versions, with access governed by the permissions set for their role.",
      },
      {
        q: "Can every dentist have an individual diary?",
        a: "Yes. Staff diaries separate clinician availability, and permissions determine which users can see an individual or wider practice view.",
      },
      {
        q: "What messages are sent to patients?",
        a: "PLANN automatically sends a WhatsApp confirmation for the booking and a reminder before the appointment.",
      },
      {
        q: "Can examination and treatment bookings use different lengths?",
        a: "Yes. Set a duration for each appointment type, and available times are checked against the appropriate clinician diary.",
      },
      {
        q: "Does it include practice income and expense figures?",
        a: "Yes. The business views cover income, expenses and statistics, including activity associated with staff and services.",
      },
    ],
    trust: {
      title: "Straightforward appointment operations for a practice",
      items: [
        "Separate clinician diaries with role-based permissions",
        "Durations matched to each bookable appointment type",
        "Automatic WhatsApp confirmations and reminders",
        "A public page for the appointments you offer online",
        "Business income, expense and activity statistics",
      ],
    },
    cta: {
      title: "Put reception on one current diary",
      text: "Create your PLANN account, add clinicians and appointment types, then manage online and telephone bookings together.",
      button: "Create a dental practice account",
    },
    links: [
      { label: "Physiotherapy clinic scheduling", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Appointment tools for psychologists", to: "/solutions/psychologist-appointment-software" },
      { label: "Veterinary practice booking software", to: "/solutions/vet-appointment-software" },
      { label: "WhatsApp booking confirmations and reminders", to: "/features/whatsapp-appointment-reminders" },
      { label: "Practice staff and financial reporting", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:psychologist-appointment-software": {
    intro: [
      "Ten minutes between sessions is better used for resetting than comparing messages with a paper diary. A clear appointment list keeps the next client, session time and working day easy to check.",
      "PLANN keeps day and week appointments together, prevents conflicting times and lets clients use a public booking page. WhatsApp confirmation and reminder messages are automatic, while access permissions support solo and group practices.",
    ],
    sections: [
      {
        h2: "Reduce the diary work between sessions",
        items: [
          {
            h3: "Offer only time that is genuinely open",
            text: "The public page works from your current availability. Once a session occupies a time, PLANN prevents another appointment being placed over it.",
          },
          {
            h3: "Give different formats enough space",
            text: "Set separate durations for individual, couple or online appointments. The diary checks the full length selected rather than assuming every conversation takes the same time.",
          },
          {
            h3: "Keep appointment context together",
            text: "The client card shows session dates, recorded spend and free-text administrative notes for the booking history you need to check.",
          },
        ],
      },
      {
        h2: "A quieter booking routine",
        body: [
          "Choose which session types appear publicly and set the times you work. Clients can book an available appointment in their browser, or you can add the next session directly before the current one ends.",
          "A WhatsApp confirmation follows the booking and an automated reminder is sent before the appointment. For an appointment arranged by phone, a typed or voice instruction to the AI assistant can create the same diary entry.",
          "The income, expense and statistics views provide a practical picture of sessions and day-to-day business activity.",
        ],
      },
      {
        h2: "Set access for the way you practise",
        body: [
          "A sole practitioner can keep a single diary, while a group practice can allocate staff diaries and permissions. Each person works with the access their role requires across the web, PWA, iOS or Android app.",
        ],
      },
    ],
    faq: [
      {
        q: "Can clients see what is in my diary?",
        a: "The public booking page shows the appointment options and availability you offer for booking. Staff access to the working diaries is governed by the permissions you set.",
      },
      {
        q: "Will I still need to message each client before a session?",
        a: "Not for the standard booking messages. PLANN sends the WhatsApp confirmation and pre-appointment reminder automatically for the session in the diary.",
      },
      {
        q: "Can I offer online and in-person sessions?",
        a: "Yes. Define them as separate appointment types with their own durations. PLANN manages their booking and reminder timing; it does not provide the video consultation itself.",
      },
      {
        q: "Can I account for a block of sessions?",
        a: "Yes. Session packages record a defined number of appointments and show the remaining balance as completed sessions are counted against the package.",
      },
    ],
    trust: {
      title: "A practical diary for client sessions",
      items: [
        "Current availability shared through a browser booking page",
        "Conflict prevention across different session lengths",
        "WhatsApp confirmation and reminder messages handled automatically",
        "Staff diaries and permissions for group practices",
        "Client appointment history, spend and general notes together",
      ],
    },
    cta: {
      title: "Create more space between sessions",
      text: "Create your PLANN account, set your working times and let clients book from the availability you publish.",
      button: "Create a practice account",
    },
    links: [
      { label: "Dietitian appointment management", to: "/solutions/dietitian-appointment-software" },
      { label: "Physiotherapy session scheduling", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Booking tools for private tutors", to: "/solutions/private-tutor-booking-software" },
      { label: "Public booking page for clients", to: "/features/online-booking-page" },
      { label: "Automated appointment messages on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
    ],
  },

  "en-GB:vertical:dietitian-appointment-software": {
    intro: [
      "An initial consultation may need a generous block; a routine review may not. When both are labelled simply as an appointment, the diary cannot show how much of the working day is actually available.",
      "PLANN schedules each consultation type at its proper length, prevents conflicts and gives clients a public page for booking. Confirmations and reminders go through WhatsApp automatically, and future reviews can be entered before the client leaves.",
    ],
    sections: [
      {
        h2: "Make follow-up administration manageable",
        items: [
          {
            h3: "Distinguish first consultations from reviews",
            text: "Create separate services with the duration and price appropriate to each. A client booking a review sees openings that fit a review, while a first consultation reserves its longer block.",
          },
          {
            h3: "Book the next agreed review immediately",
            text: "If you and the client agree a future date during the consultation, add that appointment there and then. PLANN sends the normal confirmation and later reminder for the booking.",
          },
          {
            h3: "See the client's administrative history",
            text: "Appointment dates, total spend and free-text administrative notes are available on the client card, giving you useful context when arranging the next consultation.",
          },
        ],
      },
      {
        h2: "Run in-person and online diaries together",
        body: [
          "Set in-person and online consultations as distinct bookable options if their durations differ. The public page shows your available times; you continue to use your chosen platform for any video call.",
          "PLANN sends an automated WhatsApp confirmation and reminder for either format. A telephone booking can also be added through the usual form or by giving the AI assistant a typed or spoken appointment instruction.",
          "Use the income, expense and statistics views to review consultation activity and the commercial side of the practice from the same system.",
        ],
      },
      {
        h2: "Offer defined blocks where they suit your service",
        body: [
          "If you sell a fixed package of consultations, assign the session package to the client. Completed appointments update the remaining count, so both the diary and package balance can be checked without a separate worksheet.",
        ],
      },
    ],
    faq: [
      {
        q: "How do I arrange a future review?",
        a: "Add the agreed date and time to the diary, or let the client choose an available slot from your booking page. PLANN then sends the usual confirmation and reminder.",
      },
      {
        q: "What can I see on a client's card?",
        a: "It shows appointment history, total spend and general free-text notes, so the administrative details of previous and future consultations are easy to check.",
      },
      {
        q: "Can online consultations use the same calendar?",
        a: "Yes. Add online consultation as a service and it appears alongside in-person appointments. PLANN manages the booking while you continue to host the call with your chosen video service.",
      },
      {
        q: "Can a client book through a link on my website?",
        a: "Yes. Share the public booking page wherever clients find you. It opens in a browser and presents the consultation options and availability you have configured.",
      },
    ],
    trust: {
      title: "A practical timetable for varied consultations",
      items: [
        "Appropriate durations for initial and review appointments",
        "One diary for online and in-person consultation times",
        "Specific future bookings with automatic WhatsApp reminders",
        "Session package counts for fixed consultation blocks",
        "Income, expense and appointment statistics for the practice",
      ],
    },
    cta: {
      title: "Give each consultation the right space",
      text: "Create your PLANN account, define your appointment formats and publish the times clients can book.",
      button: "Create a dietitian account",
    },
    links: [
      { label: "Scheduling for psychology practices", to: "/solutions/psychologist-appointment-software" },
      { label: "Physiotherapy appointments and packages", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Gym diary and booking tools", to: "/solutions/gym-booking-software" },
      { label: "WhatsApp messages for appointments", to: "/features/whatsapp-appointment-reminders" },
      { label: "Browser-based client booking page", to: "/features/online-booking-page" },
    ],
  },

  "en-GB:vertical:physiotherapy-appointment-software": {
    intro: [
      "A physiotherapy clinic often books a sequence rather than a single visit. Reception may need to place several appointments around work, school and different therapists while keeping an accurate count of a purchased session package.",
      "PLANN shows package counts alongside therapist diaries and prevents conflicting appointments. Patients can use a public booking page, and each confirmed appointment receives automated WhatsApp confirmation and reminder messages.",
    ],
    sections: [
      {
        h2: "Coordinate a series without a side spreadsheet",
        items: [
          {
            h3: "Keep the package count visible",
            text: "Assign a defined session package to the patient and count completed appointments against it. The remaining balance is available on the client card when reception is arranging the next date.",
          },
          {
            h3: "Separate assessment and session lengths",
            text: "An initial assessment and a routine appointment can have different durations. PLANN checks the selected length against the therapist's live diary before offering or accepting the time.",
          },
          {
            h3: "Coordinate several therapists",
            text: "Each therapist has an individual diary and permissions. Managers and authorised reception staff can view the broader week, while conflicting appointments are blocked within each therapist's schedule.",
          },
        ],
      },
      {
        h2: "How appointments enter the clinic diary",
        body: [
          "Configure bookable appointment types, staff and availability. Patients can select an opening on the public page, and reception can enter telephone or desk bookings into the same day and week diaries.",
          "Every appointment receives a WhatsApp confirmation and an automatic reminder before its time. Staff can also use a typed or voice AI instruction to add an agreed appointment while speaking with the patient.",
          "Client cards hold appointment history, spend and general notes. Staff and service statistics, together with income and expenses, help management review the clinic's activity.",
        ],
      },
      {
        h2: "Plan the next visit while dates are clear",
        body: [
          "When a further session is agreed, book the date before the patient leaves. It appears in the therapist's current diary and receives the standard WhatsApp confirmation and reminder.",
        ],
      },
    ],
    faq: [
      {
        q: "Can it show how many package sessions remain?",
        a: "Yes. Assign the session package and count completed appointments against it. Authorised staff can see the remaining number on the client card.",
      },
      {
        q: "Can reception see all therapist diaries?",
        a: "Permissions determine that access. Therapists can work from individual diaries, while authorised reception or management users can be given the wider clinic view.",
      },
      {
        q: "Are reminders sent for every booked session?",
        a: "PLANN sends a WhatsApp confirmation when the appointment is made and an automated reminder before that appointment.",
      },
      {
        q: "What information is available when booking the next session?",
        a: "The client card shows previous appointments, total spend, general notes and any remaining session-package balance alongside the diary.",
      },
    ],
    trust: {
      title: "Operational control for a session-based clinic",
      items: [
        "Session package balances updated from completed appointments",
        "Different durations for assessments and routine sessions",
        "Individual therapist diaries with access permissions",
        "Automatic WhatsApp confirmations and reminders",
        "Clinic activity and financial statistics in one system",
      ],
    },
    cta: {
      title: "Lay out each agreed session clearly",
      text: "Create your PLANN account, add therapists, appointment types and packages, then coordinate the clinic from one diary.",
      button: "Create a physiotherapy account",
    },
    links: [
      { label: "Dental practice appointment diaries", to: "/solutions/dental-clinic-appointment-software" },
      { label: "Psychology practice scheduling", to: "/solutions/psychologist-appointment-software" },
      { label: "Gym diaries and PT bookings", to: "/solutions/gym-booking-software" },
      { label: "Automated WhatsApp appointment messages", to: "/features/whatsapp-appointment-reminders" },
      { label: "Staff activity and financial tracking", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:gym-booking-software": {
    intro: [
      "PT sessions, inductions and trial appointments all compete for the same working week. When trainers keep separate notes, reception cannot see the true diary and members are left checking how many sessions remain.",
      "PLANN gives the gym a shared booking record. Each trainer has a controlled diary, package use stays visible, and members receive an automatic WhatsApp confirmation and reminder for every appointment.",
    ],
    sections: [
      {
        h2: "Keep the training floor organised",
        items: [
          {
            h3: "Separate trainer notes create clashes",
            text: "A booking agreed in a private message is easily missed at reception. Put every PT appointment in the relevant trainer's diary and PLANN prevents another booking from taking the occupied time.",
          },
          {
            h3: "Session balances need a clear record",
            text: "PLANN records each member's package and reduces the remaining sessions as appointments are completed. Authorised staff can check the count on the client record instead of relying on memory.",
          },
          {
            h3: "Forgotten appointments cost a trainer's hour",
            text: "Members receive a WhatsApp confirmation when the appointment is made, followed by an automatic reminder beforehand. Trainers do not have to run their own message list.",
          },
        ],
      },
      {
        h2: "A practical routine for PT bookings",
        body: [
          "Set up personal training, inductions and trial sessions with their usual durations and prices. Members can use your public booking link, while reception can enter telephone bookings in the same diary.",
          "Allocate the appointment to the right trainer and attach a package where relevant. The member's completed sessions, spending and notes remain together in their client history.",
          "Owners can review income, expenses and appointment statistics; trainers can be limited by permission to the diaries and information they need.",
        ],
      },
      {
        h2: "Take the diary onto the gym floor",
        body: [
          "The mobile app and PWA let trainers check the day, add a booking and review a member note without returning to reception. Typed or spoken AI booking is useful when the next client is already waiting.",
        ],
      },
    ],
    faq: [
      {
        q: "Will PLANN keep count of a member's PT sessions?",
        a: "Yes. Add the package to the member and completed appointments reduce its remaining session count. Authorised staff can check the latest count on the member record.",
      },
      {
        q: "Can trainers be restricted to their own schedules?",
        a: "Yes. Each trainer can have a separate login and diary, with permissions set by the owner. Management can still review the team from the main account.",
      },
      {
        q: "What messages does a member receive?",
        a: "PLANN sends an automated WhatsApp confirmation after booking and a reminder before the session, provided the booking has the member's telephone number.",
      },
      {
        q: "May prospective members arrange an induction online?",
        a: "Yes. Create the induction or trial as a service and include it on your public booking page. Visitors choose from the available appointment times.",
      },
    ],
    trust: {
      title: "Built for the daily PT desk",
      items: [
        "Individual trainer diaries with owner-set permissions",
        "Package sessions recorded against each member",
        "Automated WhatsApp confirmations and reminders",
        "A public link for trials, inductions and PT appointments",
        "Income, expenses and training statistics by selected period",
      ],
    },
    cta: {
      title: "Give every trainer a clearer week",
      text: "Create your PLANN account, add your PT services and team, then share your booking link.",
      button: "Create a gym account",
    },
    links: [
      { label: "Pilates studio diary and bookings", to: "/solutions/pilates-studio-booking-software" },
      { label: "Physiotherapy appointment management", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Private tuition scheduling", to: "/solutions/private-tutor-booking-software" },
      { label: "Automated appointment messages on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Track takings, costs and team activity", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:private-tutor-booking-software": {
    intro: [
      "A teaching week can unravel through small changes: a parent asks for Thursday, a pupil forgets Tuesday, and a prepaid lesson is marked on the wrong note. The administration often spills into evenings.",
      "PLANN keeps lessons in one diary, sends each booking its own WhatsApp confirmation and reminder, and records lesson packages against the pupil. Your public link handles new bookings without another message thread.",
    ],
    sections: [
      {
        h2: "Protect the hours you teach",
        items: [
          {
            h3: "Timetable changes disappear in chat",
            text: "Move the agreed lesson in PLANN and everyone with access sees the updated time. An occupied slot cannot be booked again, so a rearrangement does not create a second commitment.",
          },
          {
            h3: "Parents need a timely prompt",
            text: "The telephone number attached to the booking receives an automatic WhatsApp confirmation and a reminder before the lesson. That may be the pupil's number or a parent's.",
          },
          {
            h3: "Keep prepaid lesson counts up to date",
            text: "Assign a lesson package to the pupil and completed appointments reduce the remaining count. Their lesson history, spending and your tutoring notes remain on the client record.",
          },
        ],
      },
      {
        h2: "Plan a week without the spreadsheet",
        body: [
          "Create services for one-to-one tuition, online lessons and initial assessments, each with its normal length and fee. Pupils or parents can choose an available time through your public booking page.",
          "Telephone bookings go into the same diary. For quicker entry, tell the AI assistant the pupil, lesson, date and time by typing or voice.",
          "Use the income and expense screens to review takings, then check appointment statistics when deciding which teaching hours to offer.",
        ],
      },
      {
        h2: "Equally useful away from a desk",
        body: [
          "The mobile app and PWA keep the next lesson, pupil history and notes to hand between sessions. Online teaching still happens on your chosen video service; PLANN looks after the appointment record and reminders.",
        ],
      },
    ],
    faq: [
      {
        q: "Can the reminder be sent to a parent?",
        a: "Yes. Use the parent's telephone number on the booking and that number receives the automated WhatsApp confirmation and reminder.",
      },
      {
        q: "How are blocks of prepaid lessons recorded?",
        a: "Add a package to the pupil's record. Each completed lesson reduces the remaining number, giving you a consistent balance to check.",
      },
      {
        q: "Can I put a term's lessons in the diary in advance?",
        a: "Yes. Add the appointments for their agreed dates and times. PLANN treats each one separately and sends its reminder before that lesson.",
      },
      {
        q: "Is the system suitable for remote tuition?",
        a: "Yes. Set online tuition up as a service and manage its bookings like any other lesson. You continue to share and host the video call through your preferred service.",
      },
    ],
    trust: {
      title: "Quiet administration for independent tutors",
      items: [
        "One conflict-checked diary for every lesson",
        "WhatsApp prompts sent to the saved pupil or parent number",
        "Package balances linked to completed appointments",
        "Pupil lesson history, spend and notes kept together",
        "Phone-friendly access through the app or PWA",
      ],
    },
    cta: {
      title: "Keep your evenings for preparation",
      text: "Create your PLANN account, set your lesson types, add pupils and share a link for new bookings.",
      button: "Create a tutor account",
    },
    links: [
      { label: "Appointment tools for psychologists", to: "/solutions/psychologist-appointment-software" },
      { label: "PT and gym scheduling", to: "/solutions/gym-booking-software" },
      { label: "Pilates session management", to: "/solutions/pilates-studio-booking-software" },
      { label: "WhatsApp confirmations and reminders", to: "/features/whatsapp-appointment-reminders" },
      { label: "Use PLANN on mobile and the web", to: "/features/mobile-appointment-app-pwa" },
    ],
  },

  "en-GB:vertical:pilates-studio-booking-software": {
    intro: [
      "A studio timetable mixes private sessions, duets and group teaching, often across several instructors. When bookings arrive through calls and direct messages, the first problem is not the exercise plan but knowing which instructor is actually free.",
      "PLANN keeps those appointments in instructor diaries, blocks conflicting times and records class packages against each member. It sends WhatsApp confirmations and reminders automatically.",
    ],
    sections: [
      {
        h2: "A calmer front desk between sessions",
        items: [
          {
            h3: "Messages obscure the real timetable",
            text: "Members can choose an available appointment through your public booking link. Online and staff-entered bookings appear in the same diary, so instructors are not working from separate conversations.",
          },
          {
            h3: "Class packs need consistent counting",
            text: "Record the member's package once and completed sessions reduce its balance. The remaining number is available on the member record alongside appointment history and spending.",
          },
          {
            h3: "Manual reminders interrupt teaching",
            text: "PLANN sends a WhatsApp confirmation when a session is booked and an automated reminder before it begins. The instructor can focus on the class rather than tomorrow's message list.",
          },
        ],
      },
      {
        h2: "Run private and group work together",
        body: [
          "List private reformer, duet and group sessions as separate services with their own duration and price. Members select the service, instructor and an available time from the booking page.",
          "Every instructor can work from a personal diary and login. Permissions decide what each person can see, while the studio account keeps the complete team timetable available to management.",
          "Income, expenses and statistics show how appointment types and instructors contribute across the chosen period.",
        ],
      },
      {
        h2: "Check the next class anywhere",
        body: [
          "Instructors can open the mobile app or PWA for their daily schedule and member notes. Reception can also add a booking quickly with a typed or spoken instruction to the AI assistant.",
        ],
      },
    ],
    faq: [
      {
        q: "Does PLANN reduce a member's class-pack balance?",
        a: "Yes. Once the package is assigned, each completed appointment reduces the remaining sessions shown on the member record.",
      },
      {
        q: "Can private, duet and group sessions have different settings?",
        a: "Yes. Create each as a separate service with its own duration and price. They then appear as distinct choices on the booking page.",
      },
      {
        q: "Are members reminded without staff sending messages?",
        a: "Yes. The booking triggers an automated WhatsApp confirmation, and PLANN sends another reminder before the appointment.",
      },
      {
        q: "Can the owner compare instructors' activity?",
        a: "Yes. Appointment and income statistics can be reviewed by instructor, while individual logins and permissions keep day-to-day access appropriate.",
      },
    ],
    trust: {
      title: "A studio diary instructors can rely on",
      items: [
        "Conflict prevention across instructor schedules",
        "Separate services for each style of session",
        "Member packages reduced as appointments are completed",
        "Automatic WhatsApp messages before class",
        "Instructor-level diaries, permissions and statistics",
      ],
    },
    cta: {
      title: "Give every instructor a current timetable",
      text: "Create your PLANN account, add session types and instructors, then share your public booking link.",
      button: "Create a Pilates studio account",
    },
    links: [
      { label: "Gym and personal-training bookings", to: "/solutions/gym-booking-software" },
      { label: "Scheduling for physiotherapy practices", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Diary tools for dietitians", to: "/solutions/dietitian-appointment-software" },
      { label: "Give clients a public booking link", to: "/features/online-booking-page" },
      { label: "Send appointment prompts through WhatsApp", to: "/features/whatsapp-appointment-reminders" },
    ],
  },

  "en-GB:vertical:carpet-cleaning-scheduling-software": {
    intro: [
      "Carpet and upholstery work is easily interrupted by ringing telephones, changing job lengths and handwritten appointments. The immediate need is simple: know who is expected, when the work is booked and whether the time is already taken.",
      "PLANN provides a shared diary for customer appointments, prevents clashes and sends automatic WhatsApp confirmations and reminders. Client history and notes help the team recognise repeat work and prepare for the next booking.",
    ],
    sections: [
      {
        h2: "Keep bookings tidy before work begins",
        items: [
          {
            h3: "Telephone notes leave uncertain times",
            text: "Enter each appointment in the diary as it is agreed. PLANN checks the chosen staff member's schedule and will not place another booking over occupied time.",
          },
          {
            h3: "Customers ring to confirm the arrangement",
            text: "An automated WhatsApp confirmation records the booking details for the customer. A further reminder goes out beforehand, reducing the need for manual follow-up calls.",
          },
          {
            h3: "Repeat work lacks context",
            text: "The client record shows previous appointments, spend and your general service notes. Staff can understand the relationship before answering the next enquiry.",
          },
        ],
      },
      {
        h2: "A clear routine for taking cleaning bookings",
        body: [
          "Set up carpet, rug and upholstery services with sensible durations and prices. Take bookings by telephone or let customers choose an available appointment through your public link.",
          "If more than one person handles appointments, give each staff member a diary and appropriate permissions. Everyone works from the same current schedule.",
          "Record income and expenses as the week progresses, then use the statistics to review appointment volume, staff activity and service takings.",
        ],
      },
      {
        h2: "Useful between customer jobs",
        body: [
          "The mobile app and PWA put the diary and client history on your phone. A spoken or typed AI instruction can add an appointment when using several screens would be inconvenient.",
        ],
      },
    ],
    faq: [
      {
        q: "Can I book different stages as separate appointments?",
        a: "Yes. You can add separate diary appointments where that matches your process. PLANN records their times and sends the standard confirmation and reminder flow for each booking.",
      },
      {
        q: "What can the team see in a customer's history?",
        a: "The client record brings together past appointments, recorded spending and the general service notes your team has added.",
      },
      {
        q: "Can several cleaners use individual diaries?",
        a: "Yes. Staff members can have their own schedules and logins, with access controlled through permissions set by the business owner.",
      },
      {
        q: "Can I vary the price for a particular job?",
        a: "You can define service prices and record the relevant appointment amount. The income, expense and statistics screens then show the figures for the period you choose.",
      },
    ],
    trust: {
      title: "Solid scheduling for a hands-on trade",
      items: [
        "Shared appointments without overlapping staff times",
        "WhatsApp confirmation and reminder automation",
        "Public booking for the services you choose to offer",
        "Client appointment history, spend and practical notes",
        "Mobile access to the diary between jobs",
      ],
    },
    cta: {
      title: "Make the next week's diary clear",
      text: "Create your PLANN account, list your cleaning services, add the team and share your booking page.",
      button: "Create a cleaning business account",
    },
    links: [
      { label: "Appointment planning for car detailers", to: "/solutions/car-detailing-appointment-software" },
      { label: "Vehicle inspection scheduling", to: "/solutions/vehicle-inspection-booking-software" },
      { label: "Automatic customer reminders on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Review business income, costs and staff", to: "/features/revenue-expenses-staff-tracking" },
      { label: "Carry your appointment book on mobile", to: "/features/mobile-appointment-app-pwa" },
    ],
  },

  "en-GB:vertical:car-detailing-appointment-software": {
    intro: [
      "A maintenance wash and a full detail do not occupy the same amount of time. If both are pencilled in without a dependable duration, the workshop starts late and the rest of the diary follows.",
      "PLANN schedules each detailing service for its defined length, prevents staff clashes and lets customers take an available appointment from your public page. WhatsApp handles the booking confirmation and advance reminder.",
    ],
    sections: [
      {
        h2: "Start each job at the agreed time",
        items: [
          {
            h3: "Different services distort a paper diary",
            text: "Give every service its real duration, from a wash to paint correction. PLANN uses that duration when showing free appointment times and protects occupied staff diaries from overlap.",
          },
          {
            h3: "A missed booking leaves paid time unused",
            text: "The customer receives a WhatsApp confirmation at booking and an automatic reminder before arrival. No one on the team needs to send those messages by hand.",
          },
          {
            h3: "Past work is hard to recall",
            text: "Open the client's history to see earlier appointments, recorded spend and general notes. The team can check the last service before arranging the next visit.",
          },
        ],
      },
      {
        h2: "Set up the workshop appointment book",
        body: [
          "Create services such as maintenance wash, interior detail, machine polish and ceramic coating, each with its usual duration and price. Customers book from the public link or staff add the appointment directly.",
          "Separate staff diaries show who is booked and when. Permissions can keep each detailer's view focused while management retains oversight.",
          "Income, expenses and statistics help you review completed appointments and service takings for the selected period.",
        ],
      },
      {
        h2: "Handle enquiries with wet hands",
        body: [
          "Use the mobile app or PWA to check the next client from the workshop. When tapping through a form is awkward, the AI assistant can create a booking from a typed or spoken instruction.",
        ],
      },
    ],
    faq: [
      {
        q: "How do I reserve enough time for a long detail?",
        a: "Set the service's normal duration. PLANN places the appointment for that period and prevents another booking from overlapping the assigned staff diary.",
      },
      {
        q: "Which WhatsApp messages are sent for an appointment?",
        a: "PLANN sends a confirmation when the appointment is created and an automatic reminder before the booked time.",
      },
      {
        q: "Can reception enter an appointment for a walk-in?",
        a: "Yes. Staff can add the customer and appointment directly to the diary, where it joins the same history and reporting as online bookings.",
      },
      {
        q: "Will the figures separate one detailing service from another?",
        a: "Yes. Statistics and income records help you compare appointments and takings by service over the period you select.",
      },
    ],
    trust: {
      title: "A precise diary for detailing work",
      items: [
        "Service durations respected when appointments are offered",
        "Occupied staff times protected from another booking",
        "Automated WhatsApp confirmation and advance reminder",
        "Client history, spending and notes available to the team",
        "Service and financial statistics for workshop review",
      ],
    },
    cta: {
      title: "Give every detail the time it needs",
      text: "Create your PLANN account, add services with accurate durations and organise your staff diaries.",
      button: "Create a detailing business account",
    },
    links: [
      { label: "Booking tools for inspection businesses", to: "/solutions/vehicle-inspection-booking-software" },
      { label: "Scheduling for carpet cleaners", to: "/solutions/carpet-cleaning-scheduling-software" },
      { label: "WhatsApp booking confirmations and prompts", to: "/features/whatsapp-appointment-reminders" },
      { label: "Let customers choose an available appointment", to: "/features/online-booking-page" },
      { label: "See takings, outgoings and team statistics", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:vehicle-inspection-booking-software": {
    intro: [
      "Inspection work depends on punctual appointments. A time agreed on the telephone but not entered properly can leave two customers arriving together, while a forgotten booking leaves an inspector unexpectedly idle.",
      "PLANN keeps each inspector's diary current, rejects conflicting appointments and lets customers choose an available time online. Automated WhatsApp messages confirm the booking and remind them before arrival.",
    ],
    sections: [
      {
        h2: "Keep the inspection day in sequence",
        items: [
          {
            h3: "Verbal bookings collide",
            text: "Add every appointment to the assigned staff diary. Once a period is occupied, PLANN prevents another booking from being placed over it.",
          },
          {
            h3: "Changes are easy to overlook",
            text: "One shared schedule is clearer than desk notes and private messages. Staff can see the latest appointment time on web or mobile before speaking to the next customer.",
          },
          {
            h3: "Routine calls absorb inspection time",
            text: "Your public booking link shows available appointments without a call. PLANN then sends a WhatsApp confirmation and an automated reminder using the number on the booking.",
          },
        ],
      },
      {
        h2: "Configure appointments around the work",
        body: [
          "Create inspection services with the durations and prices you use. Customers choose a service and time online, while staff can enter bookings received by telephone.",
          "Where several inspectors work, provide individual diaries and set permissions for each login. Management can review the team's appointments from the broader schedule.",
          "Use income, expense and appointment statistics to review daily trading and compare services over longer periods.",
        ],
      },
      {
        h2: "Keep regular trade customers in view",
        body: [
          "A customer's record brings together appointment history, recorded spend and general notes. The team can use that commercial context when a regular customer books another inspection.",
        ],
      },
    ],
    faq: [
      {
        q: "Can inspection types have different appointment lengths?",
        a: "Yes. Configure each inspection as a service with its own duration and price. The booking page uses that information when presenting available times.",
      },
      {
        q: "Which telephone number gets the WhatsApp message?",
        a: "The confirmation and reminder go to the customer number attached to that booking. Staff choose the appropriate contact when entering the appointment.",
      },
      {
        q: "How does PLANN prevent a busy Saturday clash?",
        a: "It checks the assigned staff diary and refuses an appointment that overlaps an occupied time. Online customers are shown the remaining available appointment times.",
      },
      {
        q: "Can management review appointments and takings?",
        a: "Yes. PLANN includes income and expense tracking plus statistics for appointment counts, services and staff activity.",
      },
    ],
    trust: {
      title: "Orderly booking for inspection teams",
      items: [
        "Conflict checks against each inspector's diary",
        "Service durations reflected in available times",
        "Public booking without the telephone queue",
        "WhatsApp confirmation followed by a timed reminder",
        "Appointment and financial statistics for management",
      ],
    },
    cta: {
      title: "Begin the day with an accurate diary",
      text: "Create your PLANN account, define the inspection services and arrange access for your team.",
      button: "Create an inspection business account",
    },
    links: [
      { label: "Car-detailing appointment software", to: "/solutions/car-detailing-appointment-software" },
      { label: "Carpet-cleaning diary software", to: "/solutions/carpet-cleaning-scheduling-software" },
      { label: "Confirm and remind through WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Offer online appointment times", to: "/features/online-booking-page" },
      { label: "Monitor income, expenses and staff", to: "/features/revenue-expenses-staff-tracking" },
    ],
  },

  "en-GB:vertical:vet-appointment-software": {
    intro: [
      "Reception at a veterinary practice must balance routine consultations with an unpredictable working day. Calls for vaccinations and follow-ups still need a definite time, even when the diary is changing around them.",
      "PLANN gives the practice separate staff diaries, conflict checks, a public link for suitable appointment types and automated WhatsApp confirmations and reminders.",
    ],
    sections: [
      {
        h2: "Give reception a dependable appointment view",
        items: [
          {
            h3: "Routine bookings crowd the telephone",
            text: "Offer selected services, such as vaccinations or nail clips, through your public booking page. Owners choose an available appointment while reception remains free for calls that need discussion.",
          },
          {
            h3: "Follow-up dates need a firm place",
            text: "When the practice agrees a further visit, enter the date before the owner leaves. PLANN sends its WhatsApp confirmation and an automatic reminder before the appointment.",
          },
          {
            h3: "Several vets need separate diaries",
            text: "Allocate each appointment to the relevant member of staff. Their occupied time is protected from overlap, and owner-set permissions control access to schedules and business information.",
          },
        ],
      },
      {
        h2: "Keep booking details easy to find",
        body: [
          "Set up the appointment services, durations and prices you want to offer. Owners may book through the public link, and reception can enter telephone or in-person requests.",
          "The client record contains appointment history, recorded spend and general notes, giving reception useful context when an owner books again.",
          "Income, expenses and statistics help the practice review appointment patterns, services and staff activity.",
        ],
      },
      {
        h2: "Adjust when the day changes",
        body: [
          "Staff can update and check the diary through the mobile app or PWA. Typed and spoken AI booking also helps reception enter a clear appointment quickly when the telephone is busy.",
        ],
      },
    ],
    faq: [
      {
        q: "Can PLANN remind an owner about a booked booster visit?",
        a: "Yes. Add the agreed future appointment to the diary and PLANN sends the usual WhatsApp confirmation and reminder.",
      },
      {
        q: "What can reception see when an owner books again?",
        a: "The client record shows previous appointments, recorded spend and general notes added by the team.",
      },
      {
        q: "What happens when an urgent case changes the diary?",
        a: "Staff can move the affected appointments in the shared diary, and authorised team members will see the updated times.",
      },
      {
        q: "May each vet have a private schedule?",
        a: "Yes. Vets can have individual diaries and logins, with permissions chosen by the practice owner. Management can retain oversight of all appointments.",
      },
    ],
    trust: {
      title: "A shared appointment view for the practice",
      items: [
        "Separate, conflict-checked diaries for practice staff",
        "Online access for appointment types chosen by the clinic",
        "Automatic WhatsApp confirmation and reminder messages",
        "Client booking history, spend and administrative notes",
        "Income, expense and appointment statistics for management",
      ],
    },
    cta: {
      title: "Make routine bookings easier to place",
      text: "Create your PLANN account, add bookable services, set staff permissions and share the appointment link.",
      button: "Create a veterinary practice account",
    },
    links: [
      { label: "Appointment scheduling for dental practices", to: "/solutions/dental-clinic-appointment-software" },
      { label: "Physiotherapy practice bookings", to: "/solutions/physiotherapy-appointment-software" },
      { label: "Automate confirmations and reminders", to: "/features/whatsapp-appointment-reminders" },
      { label: "Publish a simple booking page", to: "/features/online-booking-page" },
      { label: "Add appointments by typing or speaking", to: "/features/ai-appointment-assistant" },
    ],
  },

  // ==========================================================================
  // EN-GB — FEATURE PAGES (/features/*)
  // ==========================================================================
  "en-GB:feature:ai-appointment-assistant": {
    intro: [
      "A booking can arrive while you are with a client, between jobs or away from the desk. PLANN lets you enter it in plain English instead of working through each diary field.",
      "Type or say the client, service and time, and the AI appointment assistant creates the entry in your diary. It is a practical shortcut for day-to-day booking, with the same conflict checks used elsewhere in PLANN.",
    ],
    sections: [
      {
        h2: "Two quicker ways to add an appointment",
        items: [
          {
            h3: "Write the booking in one line",
            text: "Enter a request such as \"Helen, colour appointment, Thursday at 3pm\". PLANN uses those details to create the appointment without making you fill in each field separately.",
          },
          {
            h3: "Use your voice when typing is awkward",
            text: "Say the appointment details when your hands are occupied or you are moving between clients. Voice entry gives you another direct route into the same diary.",
          },
          {
            h3: "Keep occupied times protected",
            text: "AI-created appointments follow your existing diary availability. PLANN checks for a conflict before placing the booking, so the shortcut does not bypass your schedule.",
          },
        ],
      },
      {
        h2: "Made for real working days",
        body: [
          "A sole practitioner can record a telephone booking without breaking the conversation to navigate several screens. In a larger business, reception can enter straightforward requests quickly while the desk is busy.",
          "Appointments created by the assistant sit alongside every other appointment. They appear in the day and week diary and use the usual automatic WhatsApp confirmation and reminder flow.",
        ],
      },
      {
        h2: "A shortcut, not a separate diary",
        body: [
          "The assistant creates appointments from the details you provide and the services, staff and availability already held in PLANN. You continue to manage the resulting entry from the normal diary.",
        ],
      },
    ],
    faq: [
      {
        q: "What should I include in a typed request?",
        a: "Give the client name, service, date and time in an ordinary sentence. For example, \"Sam, haircut, next Tuesday at 10am\" contains the details needed to create the appointment.",
      },
      {
        q: "Can I create an appointment by speaking?",
        a: "Yes. PLANN supports voice as well as typed appointment creation, so you can say the booking details instead of entering them field by field.",
      },
      {
        q: "Will the assistant place two appointments in the same slot?",
        a: "PLANN applies its diary conflict check before creating the appointment. A time that is already occupied is not treated as available.",
      },
      {
        q: "Where does an AI-created appointment appear?",
        a: "It goes into the standard PLANN diary, where you can see it in day or week view and manage it in the same way as an appointment entered manually.",
      },
    ],
    trust: {
      title: "Useful facts about AI appointment entry",
      items: [
        "Create appointments from typed instructions",
        "Use voice entry when typing is inconvenient",
        "Apply the diary's existing conflict protection",
        "See every created appointment in day and week views",
        "Keep automatic WhatsApp messages in the usual booking flow",
      ],
    },
    cta: {
      title: "Enter the next booking in one sentence",
      text: "Set up your services and diary, then use typed or voice entry when a new appointment comes in.",
      button: "Create an account",
    },
    links: [
      { label: "Send confirmations and reminders on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Give clients a public booking link", to: "/features/online-booking-page" },
      { label: "Use PLANN on mobile and web", to: "/features/mobile-appointment-app-pwa" },
      { label: "Manage appointments in a barbershop", to: "/solutions/barber-appointment-software" },
      { label: "Organise a hair salon diary", to: "/solutions/hair-salon-appointment-software" },
    ],
  },

  "en-GB:feature:whatsapp-appointment-reminders": {
    intro: [
      "Confirming each appointment and remembering when to send a reminder adds a repetitive task to an already full diary. Missing one can leave a client unsure of the time.",
      "PLANN sends an automatic WhatsApp confirmation when the appointment is created and an automatic reminder before it starts. Delivery uses the WhatsApp Business API, so staff do not have to send each message themselves.",
    ],
    sections: [
      {
        h2: "Why put appointment messages on WhatsApp?",
        body: [
          "The confirmation arrives in a channel many clients already use, leaving the appointment details available in their WhatsApp conversation.",
          "For the business, automation removes a routine round of individual messages. The diary remains the source of the appointment, while PLANN handles the scheduled communication.",
        ],
      },
      {
        h2: "From booking to reminder",
        items: [
          {
            h3: "1. Create the appointment",
            text: "The appointment may come from your public booking page or be entered by a member of staff. In either case, it is recorded in the PLANN diary.",
          },
          {
            h3: "2. Send the confirmation",
            text: "PLANN automatically sends the client a WhatsApp confirmation after the booking is made, using the phone number recorded for that appointment.",
          },
          {
            h3: "3. Send the reminder",
            text: "Before the scheduled time, PLANN sends the appointment reminder automatically. There is no separate reminder list for staff to work through.",
          },
        ],
      },
      {
        h2: "One process for every booking source",
        body: [
          "Online bookings and appointments entered by your team follow the same confirmation and reminder process. That keeps communication consistent without changing how you prefer to take bookings.",
        ],
      },
    ],
    faq: [
      {
        q: "How are the WhatsApp messages delivered?",
        a: "They are sent automatically through the WhatsApp Business API. Staff do not need to use a personal WhatsApp account to send each confirmation or reminder.",
      },
      {
        q: "Which messages does PLANN send?",
        a: "PLANN sends a confirmation when an appointment is created and a reminder before the appointment time.",
      },
      {
        q: "Are telephone and in-person bookings included?",
        a: "Yes. Once the appointment and client phone number are entered in PLANN, a manually added booking can use the same automatic message flow.",
      },
      {
        q: "Do online bookings follow a different process?",
        a: "No. An appointment made through your public booking link enters the diary and receives the same automatic confirmation and reminder treatment.",
      },
    ],
    trust: {
      title: "A clear WhatsApp message routine",
      items: [
        "Messages delivered through the WhatsApp Business API",
        "Automatic confirmation when the booking is created",
        "Automatic reminder before the appointment",
        "The same process for online and staff-entered bookings",
        "No manual message list for the team to maintain",
      ],
    },
    cta: {
      title: "Take confirmation messages off the task list",
      text: "Create your PLANN account and send confirmations and reminders automatically from each appointment.",
      button: "Create a PLANN account",
    },
    links: [
      { label: "Share a public page for bookings", to: "/features/online-booking-page" },
      { label: "Add appointments with typed or voice AI", to: "/features/ai-appointment-assistant" },
      { label: "Run a barbershop appointment diary", to: "/solutions/barber-appointment-software" },
      { label: "Plan appointments for a beauty salon", to: "/solutions/beauty-salon-appointment-software" },
      { label: "Coordinate a dental clinic diary", to: "/solutions/dental-clinic-appointment-software" },
    ],
  },

  "en-GB:feature:online-booking-page": {
    intro: [
      "Clients often know the service they want and simply need a suitable time. A telephone call or message thread makes that straightforward choice slower for both sides.",
      "Your PLANN public booking link shows the services and available times you have set. Clients use it in their browser, choose a suitable slot and place the appointment directly into your diary.",
    ],
    sections: [
      {
        h2: "What clients can book from the page",
        items: [
          {
            h3: "The service they need",
            text: "Clients choose from the services you have configured. Where staff selection is relevant, they can also choose the appropriate team member.",
          },
          {
            h3: "A time that fits the diary",
            text: "Availability reflects the appointments already in PLANN. Occupied times are protected, helping prevent two bookings being placed in the same slot.",
          },
          {
            h3: "A booking with a clear confirmation",
            text: "The new appointment appears in your diary and PLANN sends the client an automatic WhatsApp confirmation using the booking details.",
          },
        ],
      },
      {
        h2: "Put one link where clients look for you",
        body: [
          "Share the public booking link in places you already use to communicate with clients, such as your website, social profile, Google Business Profile or WhatsApp conversation.",
          "The page remains available outside your opening hours. Clients can check the offered times without waiting for somebody to answer a call or reply to a message.",
        ],
      },
      {
        h2: "Your diary rules still apply",
        body: [
          "You decide which services and staff are available. Appointments from the public page and those entered by your team meet in the same PLANN diary, with conflict prevention applied to the schedule.",
        ],
      },
    ],
    faq: [
      {
        q: "Must clients install PLANN to make a booking?",
        a: "No. Clients open your public booking link in a browser. The iOS, Android and PWA options are for businesses and their staff using PLANN.",
      },
      {
        q: "Can the page offer a time that is already booked?",
        a: "PLANN checks the diary's existing appointments when presenting availability, helping prevent a second appointment being placed in an occupied slot.",
      },
      {
        q: "Where can I publish the booking link?",
        a: "You can add the link to your website, social profile or Google Business Profile, or send it directly to clients in a message.",
      },
      {
        q: "What happens after a client chooses a slot?",
        a: "The appointment is added to your PLANN diary. The client then receives the automatic WhatsApp confirmation, followed by a reminder before the appointment.",
      },
    ],
    trust: {
      title: "What your public booking link covers",
      items: [
        "Browser-based booking with no client app required",
        "Services and staff presented from your PLANN setup",
        "Availability checked against the current diary",
        "New appointments added to the same day and week views",
        "Automatic WhatsApp confirmation after booking",
      ],
    },
    cta: {
      title: "Give clients a direct route to your diary",
      text: "Create your PLANN account, add your services and share a booking link with your clients.",
      button: "Create a PLANN account",
    },
    links: [
      { label: "Automate WhatsApp appointment messages", to: "/features/whatsapp-appointment-reminders" },
      { label: "Create appointments with the AI assistant", to: "/features/ai-appointment-assistant" },
      { label: "Set up online booking for a hair salon", to: "/solutions/hair-salon-appointment-software" },
      { label: "Manage bookings for a nail studio", to: "/solutions/nail-studio-appointment-software" },
      { label: "Offer vehicle inspection appointments online", to: "/solutions/vehicle-inspection-booking-software" },
    ],
  },

  "en-GB:feature:revenue-expenses-staff-tracking": {
    intro: [
      "A busy diary does not by itself show where the business stands. Owners still need a readable record of income and expenses, useful appointment statistics and a clear view of each staff diary.",
      "PLANN keeps those day-to-day records beside your appointments. Review income, enter expenses, inspect statistics and control staff access from one business workspace.",
    ],
    sections: [
      {
        h2: "Review figures for the period you choose",
        items: [
          {
            h3: "Income and expense records",
            text: "Keep track of business income and enter day-to-day expenses in PLANN, then review the figures for the period you choose.",
          },
          {
            h3: "Appointment and business statistics",
            text: "Use the statistics to review activity across your services, clients and diary. The information helps you understand the work recorded in PLANN without maintaining a parallel booking spreadsheet.",
          },
          {
            h3: "Separate staff diaries",
            text: "Give each staff member a diary for their own appointments while retaining an overview of the team's schedule. Conflict prevention keeps occupied times from being reused.",
          },
        ],
      },
      {
        h2: "Access that follows each role",
        body: [
          "Staff sign in with their own account and use the diary access you grant. Permissions let you decide which parts of the business they can see and manage.",
          "Managers can work across staff diaries, while individual team members can be kept focused on the appointments relevant to them. Client history, spend and notes remain available according to those permissions.",
        ],
      },
      {
        h2: "Connect the diary with client value",
        body: [
          "Client records bring together visit history, recorded spend and notes. Alongside income, expenses and statistics, this gives you an operational view of the business while packages help you track services sold as a series.",
        ],
      },
    ],
    faq: [
      {
        q: "Can I review income and expenses for a chosen period?",
        a: "Yes. Record day-to-day income and expenses, then use PLANN's business views to review activity across the dates you select.",
      },
      {
        q: "What can I keep on a client record?",
        a: "A client record can hold appointment history, recorded spend and notes, giving authorised users useful context before the next visit.",
      },
      {
        q: "Can every staff member have a separate diary?",
        a: "Yes. Staff diaries separate each person's appointments, while authorised managers can oversee the wider schedule and PLANN prevents clashes with occupied times.",
      },
      {
        q: "Can I limit what staff are allowed to see?",
        a: "Yes. Staff permissions control access, so you can give each person the parts of PLANN needed for their role rather than opening the entire business account.",
      },
    ],
    trust: {
      title: "A practical view of business activity",
      items: [
        "Operational income and expense recording",
        "Statistics drawn from activity held in PLANN",
        "Individual staff diaries with conflict prevention",
        "Permissions set to suit different team roles",
        "Client history, spend, notes and package tracking",
      ],
    },
    cta: {
      title: "See the work behind the diary",
      text: "Create your PLANN account to review appointments, staff access and everyday business figures from the dates you select.",
      button: "Create a PLANN account",
    },
    links: [
      { label: "Let clients book from a public link", to: "/features/online-booking-page" },
      { label: "Send WhatsApp confirmations and reminders", to: "/features/whatsapp-appointment-reminders" },
      { label: "Track appointments and staff in a gym", to: "/solutions/gym-booking-software" },
      { label: "Manage a beauty salon team", to: "/solutions/beauty-salon-appointment-software" },
      { label: "Oversee staff diaries in a dental clinic", to: "/solutions/dental-clinic-appointment-software" },
    ],
  },

  "en-GB:feature:mobile-appointment-app-pwa": {
    intro: [
      "Appointments are rarely managed from one desk all day. Owners and staff need to check the diary between clients, in another room or while working away from the premises.",
      "PLANN is available for iOS and Android, as well as a PWA. Use the same business account to reach your diary, client records and everyday management tools from the device that suits the work.",
    ],
    sections: [
      {
        h2: "The essentials on a smaller screen",
        items: [
          {
            h3: "Day and week diary views",
            text: "Check today's running order or look across the week from your phone. Existing appointments remain protected by PLANN's conflict prevention when the diary changes.",
          },
          {
            h3: "Typed and voice appointment entry",
            text: "Use the AI assistant to type or say a new appointment when opening and completing several diary fields would be inconvenient.",
          },
          {
            h3: "Client context away from the desk",
            text: "Open client history, recorded spend and notes when you need context for a visit, without returning to a separate office computer.",
          },
        ],
      },
      {
        h2: "Useful for owners and staff",
        body: [
          "Each staff member can use their own login to reach the diary permitted for their role. Managers decide access through staff permissions rather than sharing one account across the team.",
          "Packages, income and expense records, statistics and client information remain part of the same PLANN workspace, subject to the access granted to that user.",
        ],
      },
      {
        h2: "Choose app or PWA access",
        body: [
          "Use PLANN on iOS or Android, or open the PWA where that better suits your setup. Whichever route you choose, you are working with the same business account and appointment records.",
        ],
      },
    ],
    faq: [
      {
        q: "Which mobile options does PLANN support?",
        a: "PLANN is available on iOS and Android and can also be used as a PWA.",
      },
      {
        q: "Do clients need to install anything?",
        a: "No. Clients use your public booking link in their browser. The iOS, Android and PWA access is for the business and its authorised staff.",
      },
      {
        q: "Can staff use separate accounts on their phones?",
        a: "Yes. Staff can sign in individually, and the permissions you set determine the diaries and business information available to each person.",
      },
      {
        q: "Can I use the AI assistant on mobile?",
        a: "Yes. Typed and voice AI appointment creation are available when you need a quicker way to put a booking into the PLANN diary.",
      },
    ],
    trust: {
      title: "PLANN access that fits the working day",
      items: [
        "Available for iOS, Android and as a PWA",
        "Day and week diary views on mobile",
        "Typed and voice AI appointment creation",
        "Client history, spend and notes within reach",
        "Separate staff logins governed by permissions",
      ],
    },
    cta: {
      title: "Keep the diary close to the work",
      text: "Create your PLANN account and choose iOS, Android or PWA access for you and your team.",
      button: "Create a PLANN account",
    },
    links: [
      { label: "Use AI to enter an appointment", to: "/features/ai-appointment-assistant" },
      { label: "Share your public booking link", to: "/features/online-booking-page" },
      { label: "Automate appointment messages on WhatsApp", to: "/features/whatsapp-appointment-reminders" },
      { label: "Schedule carpet cleaning work", to: "/solutions/carpet-cleaning-scheduling-software" },
      { label: "Manage a private teaching diary", to: "/solutions/private-tutor-booking-software" },
    ],
  },
};

// Lookup: seoData kaydındaki locale ("tr" | "en-GB"), category, slug ile içerik döner.
export const getSeoContent = (locale, category, slug) =>
  seoContent[`${locale}:${category}:${slug}`] || null;
