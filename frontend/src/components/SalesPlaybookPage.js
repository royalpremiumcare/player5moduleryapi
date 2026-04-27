import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ClipboardList,
  Copy,
  HandshakeIcon,
  Headphones,
  HelpCircle,
  KeyboardIcon,
  MessageCircle,
  Phone,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
  X,
  Zap,
} from "lucide-react";

/* ============================================================
   PLANN — SATIŞ PLAYBOOK
   Hedef: Pazarlamacı telefonda konuşurken göz ucuyla okur,
   adım adım ilerler, itiraz gelince tek tuşla cevabı bulur.
   Public sayfa — /pazarlama — giriş gerekmez.
   ============================================================ */

// ---------- İÇERİK (ham veri) --------------------------------
const STEPS = [
  {
    id: "hazirlik",
    label: "Hazırlık",
    kicker: "00",
    durationSec: 60,
    icon: ClipboardList,
    accent: "zinc",
    goal: "Aramayı açmadan kafanı netle. Kime, neyi, neden söylediğini bil.",
    insight:
      "Soğuk aramanın %80'i ilk 10 saniyede kazanılır. Hazırlıksız aramada sesin kontrolsüz çıkar, müşteri bunu satıcı paniği olarak okur.",
    successSignal:
      "İşletmeyi araştırdın, sektörün acı noktasını tahmin ettin, nefesin sakin — o zaman aramayı açabilirsin.",
  },
  {
    id: "acilis",
    label: "Açılış",
    kicker: "01",
    durationSec: 30,
    icon: Phone,
    accent: "zinc",
    goal: "İzin al. Kim olduğunu söyle. Neden aradığını 10 saniyede özetle.",
    insight:
      "Müşteri 'bana ne satıyor bu?' diye düşünmeden önce 'güvendeyim' hissi vermelisin. Bunun yolu: açık kimlik + kısa izin sorusu.",
    successSignal:
      "Müşteri 'buyrun / devam edin' dedi ve keşif sorusuna cevap vermeye başladı. Kapandırmadıysa başarmayı beklersin.",
  },
  {
    id: "kesif",
    label: "Keşif",
    kicker: "02",
    durationSec: 120,
    icon: Search,
    accent: "amber",
    goal: "Problemi müşteriye söylet. Sen anlatma — dinle, not al.",
    insight:
      "Müşteri problemi kendi ağzıyla söylerse ikna olmuş olur. Sen 'çözüm' satmazsın; müşteri kendi çözümünü satın alır.",
    successSignal:
      "Müşteri en az bir acıyı kendi ağzıyla söyledi (örn. 'gelmeyen müşteri çok', 'ekip karışıyor'). Bu cümleyi not al — değerde geri kullanacaksın.",
  },
  {
    id: "deger",
    label: "Değer",
    kicker: "03",
    durationSec: 90,
    icon: Zap,
    accent: "emerald",
    goal: "Özellik değil sonuç anlat. Keşifte söylediği acıyı tam olarak adresle.",
    insight:
      "'WhatsApp hatırlatma var' denmez; 'gelmeyen müşteriyi azaltıyor' denir. Müşteri özelliği değil sonucu satın alır.",
    successSignal:
      "Müşteri 'bu iyi olurmuş', 'hmm', 'evet bunu arıyorduk' gibi onay sinyali verdi. En az bir cümle ile tepki kurduysa değeri anladı.",
  },
  {
    id: "fiyat",
    label: "Fiyat",
    kicker: "04",
    durationSec: 45,
    icon: Wallet,
    accent: "zinc",
    goal: "Fiyatı söyledikten sonra SUS. İlk konuşan pazarlık kaybeder.",
    insight:
      "Fiyatı söyledikten sonra kendini tutup 2 saniye bekle. Müşteri reaksiyon verirse gerçek itirazı duyarsın; yoksa işi aldın.",
    successSignal:
      "Müşteri fiyata bir tepki verdi (onay, soru veya itiraz). Sessizliği bozan ilk kişi o olduysa fiyat netleşerek masanın üstüne kondu.",
  },
  {
    id: "itiraz",
    label: "İtirazlar",
    kicker: "05",
    durationSec: 60,
    icon: ShieldAlert,
    accent: "rose",
    goal: "İtirazı savunmaya geçmeden önce onayla. Sonra yeniden çerçevele.",
    insight:
      "İtiraz 'hayır' değil 'hâlâ ikna olmadım' demektir. Savunmaya geçersen kaybedersin. 'Haklısınız' diyip çerçeveyi değiştir.",
    successSignal:
      "Müşteri itirazı bırakıp başka detay sormaya başladı ('kurulum nasıl?', 'ne zaman başlarız?'). İtirazdan detaya geçmek satışın açıldığını gösterir.",
  },
  {
    id: "neden",
    label: "Neden Biz",
    kicker: "06",
    durationSec: 45,
    icon: TrendingUp,
    accent: "violet",
    goal: "Rakibi kötüleme. 'Biz şunu çözüyoruz' diye konuş.",
    insight:
      "Rakip adı geçmeden fark anlat. Kötülediğin an müşterinin gözünde rakiple seni aynı kefeye koyarsın.",
    successSignal:
      "Müşteri 'tamam, makul' tonuna geçti ya da kurulum/süre gibi pratik sorulara yöneldi. Satın alma niyeti olgunlaştı.",
  },
  {
    id: "kapanis",
    label: "Kapanış",
    kicker: "07",
    durationSec: 30,
    icon: HandshakeIcon,
    accent: "emerald",
    goal: "Açık uçlu soru sorma. İkili seçim ver. Bir sonraki adımı sen öner.",
    insight:
      "'Ne düşünüyorsunuz?' satış öldüren sorudur. Yerine: 'Bugün mü, yarın mı kuralım?' Karar kolaylaşır, evet daha hızlı gelir.",
    successSignal:
      "WhatsApp'tan özet + kayıt linki gönderildi ve müşteri 'tamam bakarım' dedi, ya da somut bir takip randevusu kondu. Konuşmayı 'bakarız' ile boşta bırakma.",
  },
];

// ---------- ADIM ÇERİKLERİ -----------------------------------

const HAZIRLIK_CHECKS = [
  {
    t: "İşletme adı ve sektör",
    d: "Aramadan önce işletmenin tam olarak ne yaptığını netleştir. Genel konuşma güven kaybettirir.",
  },
  {
    t: "Muhtemel acı noktası",
    d: "Gelmeyen müşteri, WhatsApp dağınıklığı, manuel hatırlatma, yoğun telefon trafiği — hangisi olabilir tahmin et.",
  },
  {
    t: "Ses tonu kalibrasyonu",
    d: "Bir nefes al. Hızlı değil, güven veren, hafif alçak tonla başla. Sesin 'satıcı' değil 'danışman' duyulsun.",
  },
  {
    t: "Masan temiz mi?",
    d: "Playbook açık, not defteri yanında, telefon full şarj. Görüşme ortasında dağılmak profesyonellik kaybıdır.",
  },
];

const ACILIS_SCRIPTS = [
  {
    role: "Sen",
    text: "İyi çalışmalar, (İşletme Adı) ile mi görüşüyorum?",
    hint: "Kısa, saygılı, izin isteyen giriş. İsmi doğrula — yanlış numara ihtimalini ele.",
  },
  { role: "Müşteri", text: "Evet, buyrun." },
  {
    role: "Sen",
    text: "Merhaba, ben Fatih. Plann ekibinden arıyorum. 30 saniye müsaitseniz neden aradığımı hızlıca söyleyeyim — uygun mu?",
    hint: "30 saniye vaadi savunma refleksini düşürür. İzin alınca engeller çözülür ve konuşma 'satış' değil 'bilgi' çerçevesine geçer.",
  },
  { role: "Müşteri", text: "Buyurun." },
  {
    role: "Sen",
    text: "Teşekkür ederim. Biz Plann olarak kısaca şunu yapıyoruz: randevu, otomatik hatırlatma, iptal ve tahsilat karmaşasını tek bir sistemde topluyoruz. Yani gelmeyen müşteri, karışan takvim, günde yüzlerce WhatsApp mesajı, kapora ve ödeme için kovalamaca — bunların hepsini otomasyonla çözüyoruz. İşletme sahibinin operasyonel yükünü minimuma indirip, müşteri deneyimini profesyonelleştiriyoruz. Türkiye'de farklı sektörlerden binlerce işletme günlük operasyonunu Plann ile yönetiyor.",
    hint: "Açılışın can damarı: NE yaptığımız (tek sistem) + HANGİ ACILARI çözdüğümüz (4 somut sorun) + SONUÇ (operasyon yükü düşer, müşteri deneyimi profesyonelleşir) + sosyal kanıt (binlerce işletme). Bu cümle olmadan müşteri 'ne satıyor bu?' düşüncesinden çıkmaz.",
  },
  {
    role: "Sen",
    text: "Sizin durumunuzu anlamak için sadece kısa bir şey sormak istiyorum: Şu an randevular daha çok WhatsApp üzerinden mi yürüyor, yoksa ayrı bir sisteminiz var mı? Cevabınıza göre size en doğru şekilde nasıl faydalı olabiliriz onu birlikte netleştireceğiz.",
    hint: "Keşife köprü. 'Sadece kısa bir şey' baskıyı düşürür. Cevaba göre konuşacaksın — not almayı unutma, çünkü kapanışta bu cümleyi geri okuyacaksın.",
  },
];

const ACILIS_FALLBACKS = [
  {
    case: "\"Şu an çok yoğunum.\"",
    reply:
      "Tabii, sizi hiç yormayayım. Müsait olduğunuzda WhatsApp'tan kısa bir özet göndereyim, size uygun saatte kısaca bakarsınız.",
  },
  {
    case: "\"Zaten sistemimiz var.\"",
    reply:
      "Harika, o zaman karşılaştırma yapmak daha kolay. Bizim farkımız özellikle WhatsApp hatırlatma, kapora ve operasyon tarafında ortaya çıkıyor. 2 dakikada gösterip sizi bırakayım.",
  },
  {
    case: "\"Kiminle görüşüyorum?\"",
    reply:
      "Tabii. Ben Fatih, Plann ekibinden arıyorum. Amacım satış baskısı yapmak değil; işletmenize uygun bir çözüm var mı onu netleştirmek.",
  },
];

const KESIF_QUESTIONS = [
  {
    q: "Gün içinde en çok vakit kaybettiren konu sizde randevu takibi mi, hatırlatma mı, yoksa iptal / gelmeme durumu mu?",
    why: "Acıyı kendi ağzından söyletir. 3 seçenek vererek 'yok bir şeyim' demesini zorlaştırır.",
    replies: [
      {
        customer: "En çok randevu kaçırma yaşıyoruz, gelmeme çok.",
        you: "Tam da en çok fark yarattığımız alan bu. Otomatik WhatsApp hatırlatma, randevudan 1 gün önce ve aynı gün olmak üzere iki kez müşteriye gidiyor — üstelik mesaja işletme konumu da ekleniyor, yani 'nereydi acaba?' diye sorma ihtiyacı kalmıyor. Sadece bu otomasyon sayesinde işletmeler ortalama %30-40 oranında gelmeme oranında düşüş yaşıyor. Birazdan size bunun nasıl çalıştığını canlı göstereceğim, çok şaşıracaksınız.",
      },
      {
        customer: "Aslında çok sorun değil, genel olarak oturmuş.",
        you: "Harika, demek ki operasyonel tarafı oturtmuşsunuz — bu çok önemli, kolay bir şey değil. O zaman size farklı açıdan bakayım: büyüme tarafında, yani daha fazla müşteriye ulaşmak, işletme kapalıyken bile 7/24 online randevu almak ya da kapora ile rezervasyonu sağlama almak konusunda bir ihtiyaç var mı? Genelde fark yarattığımız ikinci alan bu oluyor.",
      },
    ],
  },
  {
    q: "Randevular şu an tek kişi üzerinden mi ilerliyor, yoksa ekip içinde paylaşılıp karışabiliyor mu?",
    why: "Operasyonel kaosu ortaya çıkarır. 'Karışıyor' derse ekip yönetimini satacağını bilirsin.",
    replies: [
      {
        customer: "Evet ekip içinde karışabiliyor, çakışmalar oluyor.",
        you: "Evet, tam burada personel, müşteri ve seans takibini tek ekranda görmek büyük rahatlık sağlıyor. Her personelin kendi takvimi ayrı tutuluyor, siz yönetici olarak üstten hepsini tek ekranda görüyorsunuz. Müşteri 'ben hep Ayşe hanıma geliyorum' dediğinde sistem onu otomatik olarak Ayşe'nin takvimine yönlendiriyor, başka biriyle çakışma ihtimali sıfıra iniyor. Hangi personelin ne kadar dolu, kim boş, kim hangi müşteriyle ilgileniyor — hepsi şeffaf.",
      },
      {
        customer: "Hayır, çoğunlukla ben tek bakıyorum.",
        you: "Anladım, o zaman sizin asıl yükünüz muhtemelen sürekli telefon trafiği ve WhatsApp mesajlaşması oluyor. Plann, müşteri randevu aldıktan sonra otomatik onay mesajı + 1 gün önce ve aynı gün hatırlatma gönderiyor. Yani siz aynı müşteri için 4-5 ayrı mesaj yazmaktan kurtuluyor, sadece gerçek işinize odaklanıyorsunuz. Tek başına çalışan işletmelerde bu otomasyon en çok 'rahatladım' tepkisi alan özelliğimiz.",
      },
    ],
  },
  {
    q: "Müşteri randevu aldığında otomatik onay ve hatırlatma gidiyor mu, yoksa manuel takip mi yapıyorsunuz?",
    why: "Manuel iş yükünü gün yüzüne çıkarır. Maliyet argümanı buradan doğar.",
    replies: [
      {
        customer: "Manuel takip yapıyoruz, genelde kendim yazıyorum.",
        you: "O zaman en büyük kazanımınız, ekibin üzerindeki sürekli mesaj ve hatırlatma yükünü kaldırmak olur. Ortalama bir işletmede günde 30-50 mesaj yazılıyor — hatırlatma, konum, fiyat, uygun saat sorularına cevap… Biz bu yükü %80 oranında otomasyona devrediyoruz. İnsan gücü sadece kişisel iletişim gereken yere odaklanıyor, iş kalitesi artıyor, müşteri 'unutulmuş' hissetmiyor.",
      },
      {
        customer: "Yarı otomatik, WhatsApp Business kullanıyoruz.",
        you: "WhatsApp Business iyi bir ilk adım, doğru yolda yürüyorsunuz. Ama takvim, hatırlatma ve tahsilatı aynı yerde yönetmek o aracın işi değil. Biz WhatsApp'ı kapatmıyoruz — tam tersi, müşteriyle iletişiminiz WhatsApp'tan aynen devam ediyor. Sadece arkasına düzen ekliyoruz: takvim, kapora, seans sayısı, personel yönetimi hepsi Plann'dan yönetiliyor. Onlar konuşuyor, biz düzen tutuyoruz — birbirini tamamlıyor.",
      },
    ],
  },
  {
    q: "Tahsilat tarafında kapora veya online ödeme alma ihtiyacınız oluyor mu?",
    why: "Kapora = gelmeyen müşteri çözümü. Evet derse ciddi ihtiyaç var demektir.",
    replies: [
      {
        customer: "Evet, kapora alıyoruz veya almak istiyoruz.",
        you: "Bu durumda kapora özelliği size çok ciddi fark yaratır. Müşteri randevu alırken ödediği küçük bir ücret bile 'geleceğim' taahhüdünü güçlendiriyor; kapora alan işletmelerde gelmeme oranı yaklaşık %60 düşüyor çünkü insan kendi parasını kaybetmek istemiyor. Üstelik iade kuralı tamamen sizin elinizde — müşteri geldiğinde hizmet bedelinden düşebilir, gelmezse kapora kendinize kalır. Kredi kartı altyapısı tamamen hazır, tek tıkla aktif ediyorsunuz.",
      },
      {
        customer: "Nakit çalışıyoruz, kapora almıyoruz.",
        you: "Anladım, o zaman kapora özelliğini şöyle düşünebilirsiniz: bir sigorta gibi, kullanmazsanız sorun değil ama lazım olduğunda hazır. Özellikle uzun seanslı veya pahalı hizmetlerde, küçük bir kapora alıp gelmezse kendinize bırakmak ciddi gelir kaybını önlüyor. Biz altyapıyı hazır veriyoruz; siz hangi hizmette istiyorsanız o hizmette aktif ediyorsunuz, kullanmadıklarınızda eskiden olduğu gibi nakit devam ediyor.",
      },
    ],
  },
  {
    q: "Şu an sistem değiştirmeyi düşünmeniz için en büyük sebep ne olurdu?",
    why: "Müşterinin kendi 'satın alma motivasyonunu' öğrenirsin. Kapanışta bunu kullanırsın.",
    replies: [
      {
        customer: "Daha düzenli olmak, kaçan randevuyu azaltmak isteriz.",
        you: "Sizi doğru anladıysam, en büyük ihtiyacınız üç şey: randevu takibini sadeleştirmek, hatırlatmayı otomatikleştirmek ve ekip içi karışıklığı azaltmak. Plann tam olarak bu üç noktada işinizi rahatlatıyor — tesadüfen değil, en çok karşılaştığımız ihtiyaç bunlar olduğu için sistemi de bu odakta kurguladık. Size kısaca sistemin bu üç ihtiyaca nasıl cevap verdiğini göstereyim, beklentiyi karşılıyor mu birlikte değerlendirelim.",
      },
      {
        customer: "Açıkçası şu an bir şey aramıyorum.",
        you: "Tabii, zorlamıyorum, sizi anlıyorum. Sadece şunu rica edeyim: 60 saniyede ne yaptığımızı anlatayım, size uygun gelmezse hiç zaman kaybetmeden kapatırız, bir sonraki adım önermiyorum bile. Belki şu an aramıyorsunuz ama 6 ay sonra ihtiyaç doğduğunda 'bunu duymuştum' deyip bize döneceğiniz bir bilgi olsun. Uygun mu?",
      },
    ],
  },
];

const SECTOR_TIPS = [
  {
    sector: "Güzellik / Kuaför",
    angle: "Seans paketleri, gelmeyen müşteri ve kapora en büyük acı. 'Kapora ile randevuyu sağlama alma' ve 'WhatsApp hatırlatma ile gelmeme oranının düşmesi' vurgusunu güçlü tut.",
  },
  {
    sector: "Diş / Sağlık Kliniği",
    angle: "Kontrol ve takip randevuları kritik. 'Müşteri' yerine 'hasta' de. Otomatik 6 ay kontrol hatırlatması özelliğini öne çıkar — tekrar eden gelir vurgusu.",
  },
  {
    sector: "Fizyoterapi / Masaj",
    angle: "10 seanslık paketler standart. 'Kalan seans sayısı hem sizde hem hastada şeffaf görünür' cümlesi vurucu. Ödeme planı + seans takibi birlikte.",
  },
  {
    sector: "Eğitim / Kurs / Koç",
    angle: "Bireysel ve grup ders ayrımı önemli. Her öğrenciye/öğretmene özel takvim, online ödeme ile kayıt, otomatik fatura/makbuz vurgusu.",
  },
  {
    sector: "Otomotiv / Servis",
    angle: "Periyodik bakım hatırlatması altın. 'Müşteriye 6 ay sonra otomatik bakım hatırlatması gider' = tekrar gelen müşteri = tekrar gelen ciro.",
  },
  {
    sector: "Psikolog / Danışman",
    angle: "Gizlilik ve seans öncesi ödeme önemli. 'KVKK uyumlu', 'seans öncesi online ödeme alınır, hatırlatma otomatik gider' netliğinde konuş.",
  },
];

const ROI_BREAKDOWN = {
  title: "Müşteriye söyleyebileceğin sessiz matematik",
  subtitle: "Fiyat itirazı geldiğinde bu sayıları cebinden çıkar.",
  lines: [
    { label: "Bir gelmeyen müşterinin ortalama maliyeti", value: "~250 TL" },
    { label: "Ayda 2 gelmeyen müşteri kaybı", value: "~500 TL" },
    { label: "Manuel WhatsApp takibinde kaybedilen ekip saati (aylık)", value: "~20 saat" },
    { label: "Profesyonel paket ilk ay fırsat fiyatı", value: "1.390 TL" },
    { label: "Sadece 6 gelmeyen müşteri kurtarınca paket kendini ödüyor", value: "6 randevu = paket bedava", highlight: true },
  ],
};

const DEGER_FEATURES = [
  {
    title: "Konumlu WhatsApp hatırlatma",
    outcome: "Gelmeyen müşteri sayısı düşer. Adres sorularıyla ekip vaktini kaybetmez.",
    badge: "EN VURUCU",
    icon: MessageCircle,
  },
  {
    title: "7/24 online randevu linki",
    outcome: "İşletme kapalıyken bile müşteriler kendi saatini seçer. Takvim arka planda dolmaya devam eder.",
    icon: Zap,
  },
  {
    title: "Online ödeme ve kapora",
    outcome: "Randevunun ciddiyeti artar. Gelmeyen müşteri riski, kapora ödenmişse otomatik düşer.",
    icon: Wallet,
  },
  {
    title: "Personel ve seans yönetimi",
    outcome: "Hangi müşteri kaçıncı seansında, hangi personel dolu — hepsi tek ekran. Kargaşa biter.",
    icon: Target,
  },
  {
    title: "Kasa, gelir, gider takibi",
    outcome: "Operasyon ve para aynı yerde. Gün sonu kapatması kolaylaşır.",
    icon: TrendingUp,
  },
  {
    title: "Anlık bildirim ve AI asistan",
    outcome: "Yeni randevu veya iptal anında bildirilir. AI, verileri sade dille yöneticiye aktarır.",
    icon: Sparkles,
  },
];

const DEGER_TRANSITIONS = [
  "Kısacası amaç sadece randevu almak değil; takvimi düzenli yönetmek, gelmeyen müşteriyi azaltmak ve işletme sahibinin üzerindeki manuel yükü hafifletmek.",
  "Yoğun işletmelerde en büyük fark telefon trafiğinin azalması ve takibin tek merkezden ilerlemesi oluyor.",
  "Sizin az önce söylediğiniz (acı noktasını buraya koy) tam olarak Plann'ın çözdüğü problem.",
];

const FIYAT_PACKAGES = [
  {
    name: "STANDART",
    firstMonthPrice: "990",
    normalPrice: "1.090",
    currency: "TL",
    period: "/ay",
    tag: "Başlangıç",
    limit: "Aylık 100 randevuya kadar",
    idealFor: "Küçük işletmeler, tek kişinin yürüttüğü yerler, haftada 20-25 randevulu yapılar.",
  },
  {
    name: "PROFESYONEL",
    firstMonthPrice: "1.390",
    normalPrice: "1.490",
    currency: "TL",
    period: "/ay",
    tag: "En popüler",
    limit: "Aylık 300 randevuya kadar",
    highlight: true,
    idealFor: "Günde 10+ randevusu olan aktif işletmeler. Ekipli veya tek kişi olsun, büyük çoğunluk bu paketle başlıyor.",
  },
  {
    name: "KURUMSAL",
    firstMonthPrice: "2.450",
    normalPrice: "2.850",
    currency: "TL",
    period: "/ay",
    tag: "Sınırsız",
    limit: "Sınırsız randevu hacmi",
    idealFor: "Çoklu şube, aylık 300+ randevulu yapılar, yoğun kurumsal işletmeler. Öncelikli destek hattı dahil.",
  },
];

const FIYAT_SHARED_FEATURES = [
  "Sınırsız personel (kişi başı ücret yok)",
  "Otomatik WhatsApp hatırlatma (konum + tarih)",
  "Online ödeme ve kapora altyapısı",
  "Takvim + seans + paket yönetimi",
  "Kasa, gelir ve gider takibi",
  "7/24 online randevu linki",
  "AI asistan ve canlı bildirimler",
  "KVKK uyumlu, yedekli altyapı",
];

const FIYAT_SCRIPTS = [
  {
    role: "Sen",
    text: "Şimdi fiyat tarafını netleştireyim ki kafanızda soru işareti kalmasın. Plann üç farklı paketle çalışıyor — Standart, Profesyonel ve Kurumsal. Çok önemli bir şeyi en başta söyleyeyim: paketler arasındaki tek fark aylık randevu limiti. Tüm diğer özellikler — WhatsApp hatırlatma, kapora, online ödeme, sınırsız personel, takvim ve seans yönetimi, raporlama — üçünde de tamamen açık. Yani hangi paketi seçerseniz seçin özellik eksiği yaşamayacaksınız.",
    hint: "Üç paketi bir anda tanıt + 'tek fark randevu limiti' vurgusu. 'Diğer özellikler tamamen açık' güveni katlar ve 'ben neden üst paketi alayım' sorusunu önceden iptal eder. Bu çerçeve olmadan müşteri her paket için ayrı karar vermek zorunda hisseder, kararsızlaşır.",
  },
  {
    role: "Sen",
    text: "Ayrıca şu an ilk ayınıza özel bir fırsatımız var: Standart 990 TL (normalde 1.090), Profesyonel 1.390 TL (normalde 1.490), Kurumsal 2.450 TL (normalde 2.850). Yani ilk ayı daha avantajlı fiyatla başlayıp sistemi tam olarak tanımış oluyorsunuz. Sizi risksiz bir girişe koyuyoruz; sistem işe yaramıyorsa zaten bırakıyorsunuz, ama neredeyse her müşterimiz ilk ayda kararını veriyor çünkü sonuç 30 gün içinde rahatça görünüyor.",
    hint: "İlk ay indirimi bir 'giriş eşiği düşürücü' araçtır. Hem bugüne hem sonraya fiyat söylemek dürüstlük sinyali verir. 'Risksiz giriş' cümlesi korkuyu kaldırır. Müşteri fiyat itirazı yerine 'denerim' moduna geçer.",
  },
  {
    role: "Sen",
    text: "Aktif çalışan işletmelerin büyük çoğunluğu Profesyonel paketle başlıyor çünkü aylık 300 randevu çoğu işletme için fazlasıyla yeterli geliyor. İlk ay 1.390 TL — yani günlük 45 TL'den az, bir öğle yemeği kadar bile değil. Sadece bir tek gelmeyen müşteriyi kurtarırsanız paket o gün kendini çıkarıyor. Sürpriz ek ücret yok, tüm özellikler bu pakette de tamamen açık.",
    hint: "Anchor tekniği: aylığı önce söyle, sonra günlüğe böl (45 TL), sonra somut karşılaştırma (öğle yemeği). Profesyonel'i default olarak öner — çünkü çoğu işletme 100 randevuyu geçiyor, küçük paketi satmak zaman sonra yükseltme stresi doğuruyor.",
  },
  {
    role: "Sen",
    text: "Eğer aylık 100 randevuyu geçmeyeceğinizi düşünüyorsanız Standart paketle başlayabilirsiniz — ilk ay 990 TL, günlük 33 TL. Kullanmaya başladıktan sonra ihtiyacınız büyürse Profesyonel veya Kurumsal'a 1 saatte yükseltiriz: veri kaybı olmaz, hesabınız sıfırdan kurulmaz, sadece limitiniz değişir. Yani küçük paketle başlamak ileride sıkıntı yaratmaz.",
    hint: "Düşük hacimli işletmeye Standart'ı öner ama 'yükseltme kolay' güvence cümlesi ile kararsızlığı kaldır. Günlük fiyat anchor'ını tekrar kullan. 'Veri kaybı olmaz' paragrafı göç korkusunu öldürür.",
  },
  {
    role: "Sen",
    text: "Eğer işletmeniz çok yoğunsa, aylık 300 randevuyu geçiyorsa veya birden fazla şubeniz varsa o zaman Kurumsal paketi öneriyoruz — ilk ay 2.450 TL, sonraki aylar 2.850 TL. Sınırsız randevu hacmi, öncelikli destek hattı ve çoklu şube yönetimi ile geliyor. Ama size dürüstçe söyleyeyim: gerekmedikçe Kurumsal'ı önermem, çoğu işletme Profesyonel ile rahatça yürüyor. Ben size gerçekten gereken paketi öneriyorum, gereksiz büyük paket satmak istemiyorum.",
    hint: "Üst pakette de dürüstlük tonu koru. 'Gerçekten gereken' vurgusu satıcı yerine danışman konumunu güçlendirir. Küçük paket öneren satıcıya güvenilir, çünkü ona göre pazarlamacı müşteri yararı düşünüyor.",
  },
  {
    role: "Sen",
    text: "Şunu da belirtmek istiyorum: tüm paketlerde personel sayısı sınırsız, ek lisans ücreti yok, kullanıcı başı para ödemiyorsunuz. 3 kişiyle de 15 kişiyle de fiyat aynı kalıyor. Bu birçok rakipte böyle değil, fark eden ekipli işletmeler genelde bizde kalıyor çünkü kullanıcı başı ücretler hacim büyüdükçe ciddi bir kalem oluyor.",
    hint: "Hidden value: rakip karşılaştırması yapmadan rakip dezavantajını ima et. Büyük ekipler için 'kullanıcı başı ücret yok' ciddi argüman, fiyat itirazını önceden öldürür.",
  },
  {
    role: "Sen",
    text: "Size uygun paketi birlikte netleştirelim. Şu anki aylık randevu hacminiz yaklaşık ne kadar — 100 altında mı, 100-300 arası mı, yoksa 300'ü geçiyor mu? Ona göre size doğru paketi önereyim ki gereksiz büyük veya gereksiz küçük almayın.",
    hint: "Soruyla kapat ve seçimi hacme bağla. 'Satın alır mısınız?' değil 'hangi paket?'. Cialdini commitment prensibi. Müşteri hacmini söylediği an aslında paketi zaten seçmiş olur.",
  },
];

const OBJECTIONS = [
  {
    q: "Zaten başka bir sistem kullanıyoruz.",
    short: "Sistem var",
    a: "Bunu çok sık duyuyorum, sizi anlıyorum — dijital bir altyapınız olması aslında bizim için avantaj çünkü kıyaslama yapmak çok daha kolay oluyor. Bizim farkımız özellikle üç noktada ortaya çıkıyor: birincisi WhatsApp'tan otomatik konum içeren hatırlatma, ikincisi kapora ile rezervasyon güvenliği, üçüncüsü tek ekrandan personel + tahsilat + seans yönetimi. Mevcut sisteminiz iyi olabilir, ama bu üç tarafa bakınca büyük ihtimalle 'biz şunu yapamıyoruz' diyeceğiniz bir şey çıkıyor. 2 dakika kafanızı meşgul edip karşılaştırma ekranını gösterip kapatayım — uygun bulmazsanız zamanınızı asla almam.",
    tactic: "Empati + 3 somut farklılaştırıcı + minimum risk (2 dakika + zorlamasız çıkış). Mevcut sistemi çürütme, kıyaslama çerçevesine çek.",
  },
  {
    q: "Şu an çok yoğunum.",
    short: "Yoğunum",
    a: "Çok haklısınız, zaten yoğun olmasaydınız muhtemelen Plann gibi bir sisteme de ihtiyacınız olmazdı — yani bu cevap aslında doğru yerde olduğumu gösteriyor. Sizi şu an bölmeyeyim. Müsait olduğunuzda bakmanız için WhatsApp'tan size 3 dakikalık bir özet linki ileteyim — paketler, özellikler ve sık sorulan sorular tek ekranda. Sakin bir çay molanızda 30 saniye bakar, ihtiyacınıza uygun bulursanız sonra konuşuruz. Şu an WhatsApp numaranız bu mu, oraya göndereyim?",
    tactic: "Yoğunluğu silah olarak çevir ('zaten yoğun olduğunuz için ihtiyacınız var'). Direnmeden geri çekil + WhatsApp takip kapısı aç + küçük evet (numara onayı) ile döngüyü açık bırak.",
  },
  {
    q: "Fiyat yüksek görünüyor.",
    short: "Fiyat yüksek",
    a: "Haklısınız, ilk duyulduğunda öyle algılanabiliyor — bu yüzden hep önce maliyet değil değer üzerinden bakalım diyorum. Hesabı somut yapayım: aylık paket 1.490 TL, yani günlük 50 TL'den az. Sadece ayda 2-3 gelmeyen müşteriyi kurtarırsanız paket kendini tamamen amorti ediyor. Bunun üzerine ekleyin: ekibinizin günde 30-50 mesaj yazmaktan kurtulduğu zaman, takvim karışıklığından gelen iş kayıpları, tahsilat kovalamadan kaybedilen saatler… Çoğu işletmede bu toplam kayıp paket ücretinin 5-6 katı oluyor. Yani aslında mesele 'yüksek mi düşük mü' değil, mesele 'şu an bu kayıpları yaşıyor musunuz' — siz bana onu söylerseniz birlikte hesabı yaparız, kararı sonra verin.",
    tactic: "Onayla + günlüğe böl (anchor) + somut ROI hesabı + 'kararı siz verin' (baskıyı kaldır). Fiyat tartışmasını değer hesabına çevir.",
  },
  {
    q: "Bakarız sonra.",
    short: "Sonra",
    a: "Tabii ki, zorlamıyorum, sizin için doğru zaman değilse ben de ısrarcı olmayacağım. Sadece şunu rica edeyim: size 1 sayfalık bir özet bırakayım, içinde paketler, özellikler ve sık sorulan soruların cevapları olsun. İhtiyacınız yoksa zaten bakmazsınız — ama 3 ay sonra 'şu sorun büyüdü' dediğinizde 'aaa, bunu duymuştum' deyip hızlıca dönersiniz. Size bu özeti WhatsApp'tan mı göndereyim, e-postadan mı daha rahat bakarsınız?",
    tactic: "Baskıdan tamamen kaç + 'gelecek hatırlama' tohumu ek + kanal seçimi ile küçük karar aldır. Hayır demek zorlaşır.",
  },
  {
    q: "Personelimiz zorlanır.",
    short: "Personel",
    a: "Bu en çok duyduğumuz endişelerden biri ve tam olarak bu yüzden kurulumu biz yapıyoruz, ekibinize bir şey öğrenme yükü çıkmıyor. Toplam 15-20 dakikalık bir tanıtımla sistem oturuyor; teknik bilgi gerekmiyor, telefondan bile rahatça kullanılıyor. Hatta açık konuşayım: en çok memnun kalan müşterilerimizin bir kısmı 'biz teknolojiye yabancıyız' diyerek başlayanlar. İlk haftadan sonra genelde 'keşke daha önce kullansaydık' tepkisi alıyoruz. Kurulum sonrası ilk 2 hafta destek ekibimiz size özel olarak ayrılır, takıldığınız her noktada ulaşabilirsiniz.",
    tactic: "Empati + kurulum sorumluluğunu üstlen + sosyal kanıt (benzer profil müşteri tepkisi) + 2 haftalık özel destek vaadi. Yalnız bırakmayacaksın hissi ver.",
  },
  {
    q: "WhatsApp yeterli.",
    short: "WhatsApp yeter",
    a: "Tamamen haklısınız, WhatsApp iletişim için gerçekten güçlü bir araç — zaten biz de WhatsApp'ı kapatmıyoruz, tam tersi destekliyoruz. Plann ile WhatsApp'ı kullanmaya aynen devam edersiniz, müşteriniz farkı bile etmez. Biz sadece arkasına düzen ekliyoruz: takvim, otomatik hatırlatma, kapora, seans sayısı, personel yönetimi… Düşünün şu an: bir müşteri 'pazartesi 14:00 müsait misiniz?' diye yazdığında, takvimi açıp uygunluğu kontrol etmek, yazıp onaylamak, hatırlatma kurmak birkaç dakika alıyor. Bizde bu 10 saniyede oluyor — üstelik müşteri bekleme yapmadan, siz hiç dahil olmadan. Yani WhatsApp kalır, kaos gider.",
    tactic: "Onay + 'rakip yerine tamamlayıcıyız' çerçevesi + somut senaryo (pazartesi 14:00) + sonuç cümlesi ('WhatsApp kalır, kaos gider'). Müşterinin alışkanlığını koruduğunu hisset.",
  },
  {
    q: "Eşim / ortağım ile konuşayım.",
    short: "Ortakla konuşayım",
    a: "Çok doğru yaklaşım, bu tür kararlar beraber alınmalı, saygı duyuyorum. Size hemen WhatsApp'tan düzgün bir özet göndereyim — paketler, özellikler ve sık sorulan sorular tek ekranda olsun, ortağınızla aynı bilgiye baktığınızdan emin olalım. Böylece eksik bilgiyle değil, tam tablo üzerinden konuşursunuz. Yarın aynı saatte sizi arayayım, beraber değerlendirmiş olursunuz; öğleden önce mi daha müsait olursunuz, öğleden sonra mı sizi rahatsız etmeyeyim?",
    tactic: "Saygı + bilgi paketi (eksik bilgi engelini kaldır) + randevulu tekrar arama (zaman alternatifi sun). Kararı askıda bırakma.",
  },
  {
    q: "İnternet / sistem kullanmıyorum.",
    short: "Teknoloji yabancı",
    a: "Hiç sorun değil, bunu çok duyuyoruz ve tam olarak bu yüzden sistemi olabildiğince sade kurguladık. Amacımız zaten işi kolaylaştırmak, karmaşıklaştırmak değil. Sisteme sadece ekibinizden bir kişi (örneğin resepsiyon sorumlunuz) bakacak, size hiç bulaşmayabilir bile — siz sadece raporları telefondan görmek isterseniz tek tıkla görüyorsunuz. Telefondan yönetiliyor, 10 dakikada öğreniliyor. Şunu da söyleyeyim: en çok memnun kalan müşterilerimizin bir kısmı 'ben teknolojiye yabancıyım' diyerek başlayanlar oldu. Kurulumdan sonraki ilk hafta destek ekibimiz hep yanınızda, hiç merak etmeyin.",
    tactic: "Endişeyi ortadan kaldır + 'siz kullanmak zorunda değilsiniz' delegasyon + sosyal kanıt + sürekli destek vaadi. Teknoloji korkusunu çürüt.",
  },
];

const NEDEN_BIZ = [
  {
    q: "Neden siz, başka firma değil?",
    a: "Çünkü sadece takvim tutmuyoruz. WhatsApp hatırlatma, kapora, operasyon ve tahsilat aynı yerde. İşletme sahibinin kafasındaki 5 ayrı aracı teke düşürüyoruz.",
  },
  {
    q: "Kurulum ne kadar sürer?",
    a: "Aynı gün. Ekibinize 10-15 dakikada sistemi gösteriyoruz. Teknik bilgi gerekmez; telefondan bile yönetilir.",
  },
  {
    q: "Verilerim güvende mi?",
    a: "Evet. KVKK uyumlu, yedekli ve şifreli altyapı. Sadece sizin ekibiniz kendi verisini görür.",
  },
  {
    q: "Eğer beğenmezsem?",
    a: "İlk dönemde destek ekibi yanınızda olur; adaptasyon zor gelirse birlikte çözeriz. Amacımız sizi bir aracın içinde bırakmak değil.",
  },
];

const KAPANIS_SCRIPTS = [
  {
    role: "Sen",
    text: "Ben kayıt notunu oluşturayım. En uygun akışı WhatsApp'tan gönderelim mi, yoksa kurulum uzmanımız kısa bir tanıtımla sizi arasın mı? Öğleden önce mi daha rahatsınız, öğleden sonra mı?",
    hint: "İkili seçim kapanışı. 'Evet / hayır' sorma — 'bu mu, şu mu' sor.",
  },
];

const KAPANIS_WHATSAPP =
  "Merhaba, az önce görüştüğümüz Plann ekibinden Fatih ben. İşletmenize özel randevu sistemi linkimiz: https://plannapp.co. Uygun olduğunuzda inceleyebilirsiniz, size özel demo için müsait olduğunuz saati yazarsanız kurulum uzmanımız arar. İyi çalışmalar!";

// ---------- YARDIMCI RENK HARİTASI ---------------------------
const accentMap = {
  zinc: {
    text: "text-zinc-900",
    bg: "bg-zinc-900",
    bgSoft: "bg-zinc-100",
    ring: "ring-zinc-900",
    border: "border-zinc-900",
    chip: "bg-zinc-900 text-white",
  },
  emerald: {
    text: "text-emerald-700",
    bg: "bg-emerald-600",
    bgSoft: "bg-emerald-50",
    ring: "ring-emerald-600",
    border: "border-emerald-600",
    chip: "bg-emerald-600 text-white",
  },
  amber: {
    text: "text-amber-700",
    bg: "bg-amber-600",
    bgSoft: "bg-amber-50",
    ring: "ring-amber-600",
    border: "border-amber-600",
    chip: "bg-amber-600 text-white",
  },
  rose: {
    text: "text-rose-700",
    bg: "bg-rose-600",
    bgSoft: "bg-rose-50",
    ring: "ring-rose-600",
    border: "border-rose-600",
    chip: "bg-rose-600 text-white",
  },
  violet: {
    text: "text-violet-700",
    bg: "bg-violet-600",
    bgSoft: "bg-violet-50",
    ring: "ring-violet-600",
    border: "border-violet-600",
    chip: "bg-violet-600 text-white",
  },
};

// ---------- KOPYA YARDIMCISI ---------------------------------
const useCopy = () => {
  const [copiedId, setCopiedId] = useState(null);
  const timerRef = useRef(null);

  const copy = useCallback(async (text, id) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopiedId(id || text);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopiedId(null), 1600);
    } catch (e) {
      setCopiedId("__err");
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopiedId(null), 1800);
    }
  }, []);

  return { copiedId, copy };
};

// ---------- UI PARÇALARI -------------------------------------

const ScriptBubble = ({ item, id, onCopy, copied }) => {
  const isMe = item.role === "Sen";
  return (
    <div className={`flex ${isMe ? "justify-end" : "justify-start"} group`}>
      <div className={`max-w-[92%] ${isMe ? "text-right" : "text-left"}`}>
        <div className="flex items-center gap-2 mb-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-zinc-400">
          {isMe ? <Headphones size={11} /> : <MessageCircle size={11} />}
          <span>{isMe ? "Sen oku" : "Müşteri"}</span>
        </div>
        <div
          className={`relative rounded-2xl px-5 py-4 shadow-sm leading-relaxed text-[15px] md:text-base ${
            isMe
              ? "bg-zinc-900 text-white rounded-br-sm"
              : "bg-white text-zinc-800 border border-zinc-200 rounded-bl-sm"
          }`}
        >
          <p className="font-medium">{item.text}</p>
          {isMe && (
            <button
              onClick={() => onCopy(item.text, id)}
              className="absolute -left-11 top-1/2 -translate-y-1/2 hidden md:flex items-center justify-center h-9 w-9 rounded-full bg-white text-zinc-700 border border-zinc-200 shadow-sm hover:bg-zinc-900 hover:text-white hover:border-zinc-900 transition-colors"
              title="Metni kopyala"
            >
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </button>
          )}
          {isMe && (
            <button
              onClick={() => onCopy(item.text, id)}
              className="md:hidden mt-3 inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-300 hover:text-white"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? "Kopyalandı" : "Kopyala"}
            </button>
          )}
        </div>
        {item.hint && (
          <p className="mt-2 text-[12px] text-zinc-500 italic leading-snug px-1">
            <span className="font-semibold not-italic text-zinc-600">İpucu — </span>
            {item.hint}
          </p>
        )}
      </div>
    </div>
  );
};

const StepHeader = ({ step, index, total, nextStep }) => {
  const Icon = step.icon;
  const a = accentMap[step.accent] || accentMap.zinc;
  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-400 mb-3">
        <span>Adım {step.kicker} / {String(total - 1).padStart(2, "0")}</span>
        <span className="h-1 w-1 rounded-full bg-zinc-300" />
        <span>~{step.durationSec}sn</span>
      </div>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-2xl ${a.bgSoft} ${a.text} shrink-0`}>
          <Icon size={22} strokeWidth={2.2} />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl md:text-[32px] font-black tracking-tight text-zinc-900 leading-tight">
            {step.label}
          </h2>
          <p className="text-sm md:text-[15px] text-zinc-600 mt-1.5 leading-relaxed">
            {step.goal}
          </p>
        </div>
      </div>
      <div className={`mt-5 rounded-2xl border border-zinc-200 bg-white px-4 py-3 flex gap-3`}>
        <Sparkles size={16} className={`${a.text} shrink-0 mt-0.5`} />
        <p className="text-[13px] text-zinc-700 leading-relaxed">
          <span className="font-semibold text-zinc-900">Neden işe yarar: </span>
          {step.insight}
        </p>
      </div>
      {(step.successSignal || nextStep) && (
        <div className="mt-2 rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3 flex gap-3">
          <Check size={16} className="text-emerald-700 shrink-0 mt-0.5" strokeWidth={3} />
          <div className="text-[13px] text-zinc-800 leading-relaxed">
            {step.successSignal && (
              <p>
                <span className="font-bold text-emerald-800">Bu adımı ne zaman bitirirsin: </span>
                {step.successSignal}
              </p>
            )}
            {nextStep && (
              <p className="mt-1 text-zinc-700">
                <span className="font-bold text-zinc-900">Sonra → </span>
                {nextStep.label}: <span className="text-zinc-600">{nextStep.goal}</span>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const SectionTitle = ({ children, icon: Icon }) => (
  <div className="flex items-center gap-2 mb-3 mt-6">
    {Icon && <Icon size={15} className="text-zinc-500" />}
    <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-500">
      {children}
    </h3>
  </div>
);

// ---------- ADIM İÇERİKLERİ ----------------------------------

const HazirlikStep = () => (
  <div>
    <SectionTitle icon={ClipboardList}>Çağrı akışı — telefonda sırayla böyle git</SectionTitle>
    <div className="bg-zinc-900 text-white rounded-3xl p-5 md:p-6">
      <p className="text-[12.5px] text-zinc-300 mb-5 leading-relaxed">
        Ortalama bir çağrı 8-12 dakika sürer. Her adımı sırayla yap — bir adımın <span className="text-emerald-400 font-bold">başarı sinyalini</span> almadan sonrakine geçersen müşteriyi kaybedersin. Üst menuden her an istediğin adıma atlayabilirsin.
      </p>
      <ol className="space-y-3">
        {STEPS.map((s, i) => {
          const isLast = i === STEPS.length - 1;
          return (
            <li key={s.id} className="flex items-start gap-3">
              <div className="flex flex-col items-center shrink-0">
                <span className="h-8 w-8 rounded-xl bg-white/10 text-white text-[11px] font-black flex items-center justify-center tabular-nums">
                  {String(i).padStart(2, "0")}
                </span>
                {!isLast && <span className="w-px flex-1 bg-white/10 my-1 min-h-[16px]" />}
              </div>
              <div className="flex-1 min-w-0 pb-2">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-[14.5px] font-black text-white">{s.label}</span>
                  <span className="text-[10.5px] text-zinc-400 font-semibold tabular-nums">~{s.durationSec}sn</span>
                </div>
                <p className="text-[12.5px] text-zinc-300 mt-0.5 leading-relaxed">{s.goal}</p>
                {s.successSignal && (
                  <p className="text-[11.5px] text-emerald-300/90 mt-1 leading-relaxed">
                    <span className="font-bold">Bitirme sinyali: </span>
                    {s.successSignal}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>

    <SectionTitle icon={ClipboardList}>Aramadan önce bunlar masanda hazır olsun</SectionTitle>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {HAZIRLIK_CHECKS.map((c, i) => (
        <div
          key={i}
          className="bg-white border border-zinc-200 rounded-2xl p-4 flex gap-3 hover:border-zinc-300 transition-colors"
        >
          <div className="h-9 w-9 rounded-xl bg-zinc-900 text-white flex items-center justify-center shrink-0 font-black text-sm">
            {String(i + 1).padStart(2, "0")}
          </div>
          <div>
            <h4 className="font-bold text-[14px] text-zinc-900 leading-snug">{c.t}</h4>
            <p className="text-[13px] text-zinc-600 mt-0.5 leading-relaxed">{c.d}</p>
          </div>
        </div>
      ))}
    </div>

    <SectionTitle icon={Target}>Aradığın işletmenin sektörüne göre konuş</SectionTitle>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      {SECTOR_TIPS.map((s, i) => (
        <div
          key={i}
          className="bg-white border border-zinc-200 rounded-2xl p-4 hover:border-zinc-900 transition-colors"
        >
          <p className="text-[12px] font-black uppercase tracking-widest text-zinc-900 mb-1.5">
            {s.sector}
          </p>
          <p className="text-[13px] text-zinc-600 leading-relaxed">{s.angle}</p>
        </div>
      ))}
    </div>
  </div>
);

const AcilisStep = ({ copy, copiedId }) => (
  <div>
    <div className="bg-white border border-zinc-200 rounded-3xl p-5 md:p-6 space-y-5">
      {ACILIS_SCRIPTS.map((s, i) => (
        <ScriptBubble
          key={i}
          item={s}
          id={`ac-${i}`}
          onCopy={copy}
          copied={copiedId === `ac-${i}`}
        />
      ))}
    </div>

    <SectionTitle icon={ShieldAlert}>Açılışta direnç gelirse</SectionTitle>
    <div className="space-y-2">
      {ACILIS_FALLBACKS.map((f, i) => (
        <div
          key={i}
          className="bg-white border border-zinc-200 rounded-2xl p-4 hover:border-zinc-300 transition-colors"
        >
          <p className="text-[12px] font-bold text-rose-600 mb-1.5">{f.case}</p>
          <p className="text-[14px] text-zinc-800 leading-relaxed">{f.reply}</p>
          <button
            onClick={() => copy(f.reply, `af-${i}`)}
            className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-500 hover:text-zinc-900 transition-colors"
          >
            {copiedId === `af-${i}` ? <Check size={12} /> : <Copy size={12} />}
            {copiedId === `af-${i}` ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
      ))}
    </div>
  </div>
);

const KesifQuestionCard = ({ k, idx, copy, copiedId }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl p-5 group hover:border-zinc-900 transition-colors">
      <div className="flex items-start gap-4">
        <span className="font-black text-zinc-300 text-2xl leading-none tabular-nums">
          {String(idx + 1).padStart(2, "0")}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[15px] md:text-base text-zinc-900 font-semibold leading-relaxed">
            {k.q}
          </p>
          <p className="text-[12px] text-zinc-500 mt-2 italic leading-relaxed">
            <span className="font-bold not-italic text-zinc-600">Neden bu soru: </span>
            {k.why}
          </p>
        </div>
        <button
          onClick={() => copy(k.q, `kq-${idx}`)}
          className="shrink-0 h-9 w-9 rounded-xl border border-zinc-200 text-zinc-500 hover:bg-zinc-900 hover:text-white hover:border-zinc-900 flex items-center justify-center transition-colors"
          title="Soruyu kopyala"
        >
          {copiedId === `kq-${idx}` ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>

      <button
        onClick={() => setOpen((v) => !v)}
        className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-bold text-zinc-700 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200 px-3 py-1.5 rounded-lg transition-colors"
      >
        <MessageCircle size={13} />
        {open ? "Olası cevapları gizle" : `Olası cevaplar ve karşılıkların (${k.replies?.length || 0})`}
      </button>

      {open && (
        <div className="mt-4 space-y-4 pl-2 border-l-2 border-amber-300">
          {k.replies?.map((r, ri) => (
            <div key={ri} className="pl-3">
              <div className="text-[10px] font-black uppercase tracking-widest text-amber-700 mb-2">
                Senaryo {String.fromCharCode(65 + ri)}
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-2">
                <p className="text-[10px] font-bold uppercase tracking-widest text-amber-700 mb-1">
                  Müşteri
                </p>
                <p className="text-[13px] text-zinc-800 leading-relaxed">"{r.customer}"</p>
              </div>
              <div className="bg-zinc-900 text-white rounded-xl px-4 py-3 relative group/reply">
                <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-400 mb-1">
                  Sen oku
                </p>
                <p className="text-[13px] md:text-[14px] leading-relaxed">{r.you}</p>
                <button
                  onClick={() => copy(r.you, `kr-${idx}-${ri}`)}
                  className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-300 hover:text-white"
                >
                  {copiedId === `kr-${idx}-${ri}` ? <Check size={12} /> : <Copy size={12} />}
                  {copiedId === `kr-${idx}-${ri}` ? "Kopyalandı" : "Cevabı kopyala"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const KesifStep = ({ copy, copiedId }) => (
  <div>
    <SectionTitle icon={Search}>Sırayla sor — her sorunun altında olası cevaplar var</SectionTitle>
    <div className="space-y-3">
      {KESIF_QUESTIONS.map((k, i) => (
        <KesifQuestionCard key={i} k={k} idx={i} copy={copy} copiedId={copiedId} />
      ))}
    </div>

    <div className="mt-6 rounded-2xl border-2 border-dashed border-amber-300 bg-amber-50 p-4 flex gap-3">
      <Sparkles size={18} className="text-amber-600 shrink-0 mt-0.5" />
      <p className="text-[13px] text-zinc-700 leading-relaxed">
        <span className="font-bold text-zinc-900">Keşif altın kuralı: </span>
        Sen ne kadar az konuşursan, satış o kadar büyür. Müşteri kendi acısını söylediğinde çözümü satmaya gerek kalmaz — kendiliğinden satılır.
      </p>
    </div>
  </div>
);

const DegerStep = ({ copy, copiedId }) => (
  <div>
    <SectionTitle icon={Zap}>Özellik değil sonuç anlat</SectionTitle>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {DEGER_FEATURES.map((f, i) => {
        const Icon = f.icon;
        return (
          <div
            key={i}
            className="bg-white border border-zinc-200 rounded-2xl p-4 flex gap-3 hover:border-emerald-600 hover:shadow-sm transition-all"
          >
            <div className="h-10 w-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
              <Icon size={18} strokeWidth={2.2} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                <h4 className="font-bold text-[14px] text-zinc-900 leading-snug">{f.title}</h4>
                {f.badge && (
                  <span className="bg-emerald-600 text-white text-[9px] px-2 py-0.5 rounded-full font-black uppercase tracking-wider">
                    {f.badge}
                  </span>
                )}
              </div>
              <p className="text-[13px] text-zinc-600 leading-relaxed">{f.outcome}</p>
            </div>
          </div>
        );
      })}
    </div>

    <SectionTitle icon={HandshakeIcon}>Değerden fiyata köprü cümleleri</SectionTitle>
    <div className="space-y-2">
      {DEGER_TRANSITIONS.map((t, i) => (
        <div
          key={i}
          className="bg-white border border-zinc-200 rounded-2xl p-4 flex items-start gap-3"
        >
          <span className="font-black text-emerald-600 tabular-nums text-sm mt-0.5">
            {String(i + 1).padStart(2, "0")}
          </span>
          <p className="flex-1 text-[14px] text-zinc-800 leading-relaxed">{t}</p>
          <button
            onClick={() => copy(t, `dt-${i}`)}
            className="shrink-0 text-zinc-400 hover:text-zinc-900 transition-colors"
            title="Kopyala"
          >
            {copiedId === `dt-${i}` ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      ))}
    </div>
  </div>
);

const FiyatStep = ({ copy, copiedId }) => (
  <div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {FIYAT_PACKAGES.map((p, i) => (
        <div
          key={i}
          className={`rounded-3xl p-5 md:p-6 flex flex-col ${
            p.highlight
              ? "bg-zinc-900 text-white border-2 border-zinc-900 md:-my-1 shadow-xl shadow-zinc-900/10"
              : "bg-white text-zinc-900 border border-zinc-200"
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <span
              className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-widest ${
                p.highlight ? "bg-emerald-500 text-white" : "bg-zinc-100 text-zinc-600"
              }`}
            >
              {p.tag}
            </span>
            <span className={`text-[11px] font-bold ${p.highlight ? "text-zinc-400" : "text-zinc-400"}`}>
              {p.name}
            </span>
          </div>

          <div className="flex items-baseline gap-1.5">
            <span className="text-4xl font-black tracking-tight">{p.firstMonthPrice}</span>
            <span className={`text-sm font-bold ${p.highlight ? "text-zinc-400" : "text-zinc-500"}`}>
              {p.currency}
            </span>
            <span className={`text-sm ${p.highlight ? "text-zinc-400" : "text-zinc-500"}`}>
              {p.period}
            </span>
          </div>
          <p className={`text-[10.5px] font-black uppercase tracking-[0.14em] mt-1 ${p.highlight ? "text-emerald-400" : "text-emerald-700"}`}>
            İlk ay fırsat fiyatı
          </p>
          <p className={`text-[12px] mt-1 ${p.highlight ? "text-zinc-400" : "text-zinc-500"}`}>
            Sonraki aylar:{" "}
            <span className={`font-bold ${p.highlight ? "text-zinc-200" : "text-zinc-700"}`}>
              {p.normalPrice} {p.currency}
            </span>
          </p>

          <div className={`mt-5 rounded-xl px-3 py-2.5 ${p.highlight ? "bg-white/10" : "bg-zinc-50"}`}>
            <p className={`text-[9.5px] font-black uppercase tracking-[0.14em] mb-0.5 ${p.highlight ? "text-zinc-400" : "text-zinc-500"}`}>
              Randevu limiti
            </p>
            <p className="text-[13px] font-bold">{p.limit}</p>
          </div>

          <div className="mt-3">
            <p className={`text-[9.5px] font-black uppercase tracking-[0.14em] mb-1 ${p.highlight ? "text-zinc-400" : "text-zinc-500"}`}>
              Kim için uygun
            </p>
            <p className={`text-[12px] leading-relaxed ${p.highlight ? "text-zinc-300" : "text-zinc-600"}`}>
              {p.idealFor}
            </p>
          </div>
        </div>
      ))}
    </div>

    <div className="mt-4 rounded-3xl border-2 border-emerald-200 bg-emerald-50/60 p-5">
      <div className="flex items-start gap-3 mb-3">
        <div className="h-9 w-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0">
          <Check size={17} strokeWidth={3} />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-black uppercase tracking-widest text-emerald-700">
            Üç pakette de tamamen açık
          </p>
          <p className="text-[13px] text-zinc-800 mt-0.5 leading-relaxed">
            Paketler arasındaki <span className="font-bold">tek fark randevu limiti</span>. Diğer tüm özellikler her pakette aynı — küçük paket aldınız diye bir özelliği kaybetmiyorsunuz.
          </p>
        </div>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pl-12">
        {FIYAT_SHARED_FEATURES.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-[12.5px] text-zinc-700">
            <Check size={13} className="text-emerald-600 mt-0.5 shrink-0" strokeWidth={2.5} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </div>

    <SectionTitle icon={Headphones}>Fiyatı söylerken oku</SectionTitle>
    <div className="bg-white border border-zinc-200 rounded-3xl p-5 space-y-5">
      {FIYAT_SCRIPTS.map((s, i) => (
        <ScriptBubble
          key={i}
          item={s}
          id={`fs-${i}`}
          onCopy={copy}
          copied={copiedId === `fs-${i}`}
        />
      ))}
    </div>

    <SectionTitle icon={TrendingUp}>{ROI_BREAKDOWN.title}</SectionTitle>
    <div className="bg-white border border-zinc-200 rounded-2xl p-5">
      <p className="text-[12px] text-zinc-500 mb-4">{ROI_BREAKDOWN.subtitle}</p>
      <div className="space-y-2">
        {ROI_BREAKDOWN.lines.map((line, i) => (
          <div
            key={i}
            className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl ${
              line.highlight
                ? "bg-emerald-600 text-white"
                : "bg-zinc-50 text-zinc-800"
            }`}
          >
            <span className={`text-[13px] ${line.highlight ? "font-bold" : ""}`}>
              {line.label}
            </span>
            <span
              className={`text-[14px] font-black tabular-nums shrink-0 ${
                line.highlight ? "text-white" : "text-zinc-900"
              }`}
            >
              {line.value}
            </span>
          </div>
        ))}
      </div>
    </div>

    <div className="mt-4 rounded-2xl border-2 border-dashed border-zinc-300 bg-zinc-50 p-4 flex gap-3">
      <div className="text-zinc-900 font-black text-xl leading-none pt-0.5">!</div>
      <p className="text-[13px] text-zinc-700 leading-relaxed">
        <span className="font-bold text-zinc-900">Altın kural: </span>
        Fiyatı söyledikten sonra cümle kurma. 2 saniye sessiz kal. İlk konuşan pazarlık kaybeder.
      </p>
    </div>
  </div>
);

const ItirazStep = ({ copy, copiedId, query, onQuery }) => {
  const filtered = OBJECTIONS.filter(
    (o) =>
      !query ||
      o.q.toLowerCase().includes(query.toLowerCase()) ||
      o.a.toLowerCase().includes(query.toLowerCase()) ||
      o.short.toLowerCase().includes(query.toLowerCase())
  );
  return (
    <div>
      <div className="sticky top-[148px] z-10 mb-4">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="İtirazda geçen kelimeyi yaz (örn. fiyat, yoğun, WhatsApp)…"
            className="w-full h-12 pl-11 pr-4 rounded-2xl border border-zinc-200 bg-white text-[14px] focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900 shadow-sm"
          />
        </div>
      </div>

      <div className="space-y-3">
        {filtered.map((o, i) => (
          <div
            key={i}
            className="bg-white border border-zinc-200 rounded-2xl p-5 hover:border-rose-300 transition-colors"
          >
            <div className="flex items-start gap-3">
              <span className="shrink-0 h-7 px-2 rounded-lg bg-rose-50 text-rose-700 text-[11px] font-black uppercase tracking-wider flex items-center">
                {o.short}
              </span>
            </div>
            <p className="mt-2 text-[13px] text-zinc-500 italic">Müşteri: “{o.q}”</p>
            <div className="mt-3 rounded-xl bg-zinc-900 text-white px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-400 mb-1.5">
                Sen oku
              </p>
              <p className="text-[14px] md:text-[15px] leading-relaxed">{o.a}</p>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-[12px] text-zinc-500 leading-snug">
                <span className="font-bold text-zinc-700">Taktik: </span>
                {o.tactic}
              </p>
              <button
                onClick={() => copy(o.a, `ob-${i}`)}
                className="shrink-0 inline-flex items-center gap-1.5 text-[12px] font-bold text-zinc-700 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200 px-3 py-1.5 rounded-lg transition-colors"
              >
                {copiedId === `ob-${i}` ? <Check size={13} /> : <Copy size={13} />}
                {copiedId === `ob-${i}` ? "Kopyalandı" : "Cevabı kopyala"}
              </button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-zinc-500 text-sm">
            Bu kelimeye denk gelen bir itiraz şablonu yok. Ana listeye dön.
          </div>
        )}
      </div>
    </div>
  );
};

const NedenStep = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    {NEDEN_BIZ.map((n, i) => (
      <div
        key={i}
        className="bg-white border border-zinc-200 rounded-2xl p-5 hover:border-violet-300 transition-colors"
      >
        <div className="flex items-center gap-2 mb-2">
          <HelpCircle size={14} className="text-violet-600" />
          <p className="text-[11px] font-bold uppercase tracking-widest text-violet-700">
            Soru {i + 1}
          </p>
        </div>
        <p className="text-[15px] font-bold text-zinc-900 mb-2 leading-snug">{n.q}</p>
        <p className="text-[14px] text-zinc-700 leading-relaxed">{n.a}</p>
      </div>
    ))}
  </div>
);

const KapanisStep = ({ copy, copiedId }) => (
  <div>
    <div className="bg-white border border-zinc-200 rounded-3xl p-5 md:p-6 space-y-5">
      {KAPANIS_SCRIPTS.map((s, i) => (
        <ScriptBubble
          key={i}
          item={s}
          id={`ks-${i}`}
          onCopy={copy}
          copied={copiedId === `ks-${i}`}
        />
      ))}
    </div>

    <SectionTitle icon={MessageCircle}>WhatsApp takip mesajı</SectionTitle>
    <div className="bg-zinc-900 rounded-3xl p-6 relative overflow-hidden">
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessageCircle size={16} className="text-emerald-400" />
            <span className="text-[11px] font-bold uppercase tracking-widest text-zinc-400">
              Görüşme sonrası 10 dk içinde gönder
            </span>
          </div>
          <button
            onClick={() => copy(KAPANIS_WHATSAPP, "wa-msg")}
            className="inline-flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 text-white text-[12px] font-black px-3 py-2 rounded-xl transition-colors"
          >
            {copiedId === "wa-msg" ? <Check size={13} /> : <Copy size={13} />}
            {copiedId === "wa-msg" ? "Kopyalandı" : "Mesajı kopyala"}
          </button>
        </div>
        <p className="text-[14px] md:text-[15px] text-zinc-100 leading-relaxed whitespace-pre-line">
          {KAPANIS_WHATSAPP}
        </p>
      </div>
    </div>

    <div className="mt-4 rounded-2xl border border-zinc-200 bg-white p-4 flex gap-3">
      <TrendingUp size={18} className="text-emerald-600 shrink-0 mt-0.5" />
      <div className="text-[13px] text-zinc-700 leading-relaxed">
        <span className="font-bold text-zinc-900">Kapanış kuralı: </span>
        Bir sonraki adımı sen öner. "Sizi geri arayayım mı?" deme — "Yarın 14:00 uyar mı?" de. Tarih ver, saat ver, seçim daralt.
      </div>
    </div>
  </div>
);

// ---------- OBJECTION DRAWER (her yerden erişim) -------------

const ObjectionDrawer = ({ open, onClose, copy, copiedId }) => {
  const [q, setQ] = useState("");
  const filtered = OBJECTIONS.filter(
    (o) =>
      !q ||
      o.q.toLowerCase().includes(q.toLowerCase()) ||
      o.a.toLowerCase().includes(q.toLowerCase()) ||
      o.short.toLowerCase().includes(q.toLowerCase())
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        className={`fixed inset-0 z-[60] bg-zinc-900/30 backdrop-blur-[2px] transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed z-[70] top-0 right-0 h-full w-full md:w-[480px] bg-white shadow-2xl transform transition-transform duration-300 flex flex-col ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="px-5 py-4 border-b border-zinc-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-xl bg-rose-50 text-rose-700 flex items-center justify-center">
              <ShieldAlert size={17} />
            </div>
            <div>
              <h3 className="font-black text-zinc-900 leading-tight">Hızlı İtiraz Kartı</h3>
              <p className="text-[11px] text-zinc-500">Konuşurken aç, cevabı bul, kopyala.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="h-9 w-9 rounded-xl bg-zinc-100 hover:bg-zinc-200 text-zinc-700 flex items-center justify-center transition-colors"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-3 border-b border-zinc-100">
          <div className="relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Ara: fiyat, yoğun, sistem…"
              className="w-full h-10 pl-10 pr-3 rounded-xl border border-zinc-200 bg-zinc-50 text-[13px] focus:bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:border-zinc-900"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
          {filtered.map((o, i) => (
            <div key={i} className="border border-zinc-200 rounded-xl p-3 hover:border-rose-300 transition-colors">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] font-black uppercase tracking-wider text-rose-700 bg-rose-50 px-2 py-0.5 rounded-md">
                  {o.short}
                </span>
              </div>
              <p className="text-[12px] text-zinc-500 italic mb-2">“{o.q}”</p>
              <p className="text-[13px] text-zinc-900 leading-relaxed">{o.a}</p>
              <button
                onClick={() => copy(o.a, `dr-${i}`)}
                className="mt-2.5 w-full inline-flex items-center justify-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-white text-[12px] font-bold px-3 py-2 rounded-lg transition-colors"
              >
                {copiedId === `dr-${i}` ? <Check size={12} /> : <Copy size={12} />}
                {copiedId === `dr-${i}` ? "Kopyalandı" : "Cevabı kopyala"}
              </button>
            </div>
          ))}
          {filtered.length === 0 && (
            <p className="text-center text-sm text-zinc-500 py-8">Sonuç yok.</p>
          )}
        </div>
      </aside>
    </>
  );
};

// ---------- ANA SAYFA ----------------------------------------

const SalesPlaybookPage = () => {
  const [activeIdx, setActiveIdx] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [objectionQuery, setObjectionQuery] = useState("");
  const [toastKey, setToastKey] = useState(0);
  const { copiedId, copy: rawCopy } = useCopy();
  const mainRef = useRef(null);

  const copy = useCallback(
    async (text, id) => {
      await rawCopy(text, id);
      setToastKey((k) => k + 1);
    },
    [rawCopy]
  );

  const step = STEPS[activeIdx];
  const total = STEPS.length;

  const progress = ((activeIdx + 1) / total) * 100;

  const goTo = useCallback(
    (idx) => {
      const clamped = Math.max(0, Math.min(total - 1, idx));
      setActiveIdx(clamped);
      if (mainRef.current) {
        mainRef.current.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    },
    [total]
  );

  // Klavye kısayolları
  useEffect(() => {
    const onKey = (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
        return;
      }
      if (e.key === "ArrowRight") goTo(activeIdx + 1);
      else if (e.key === "ArrowLeft") goTo(activeIdx - 1);
      else if (e.key.toLowerCase() === "o") setDrawerOpen((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeIdx, goTo]);

  useEffect(() => {
    document.title = "Plann | Satış Playbook";
  }, []);

  const renderStep = () => {
    switch (step.id) {
      case "hazirlik":
        return <HazirlikStep />;
      case "acilis":
        return <AcilisStep copy={copy} copiedId={copiedId} />;
      case "kesif":
        return <KesifStep copy={copy} copiedId={copiedId} />;
      case "deger":
        return <DegerStep copy={copy} copiedId={copiedId} />;
      case "fiyat":
        return <FiyatStep copy={copy} copiedId={copiedId} />;
      case "itiraz":
        return (
          <ItirazStep
            copy={copy}
            copiedId={copiedId}
            query={objectionQuery}
            onQuery={setObjectionQuery}
          />
        );
      case "neden":
        return <NedenStep />;
      case "kapanis":
        return <KapanisStep copy={copy} copiedId={copiedId} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#fafafa_0%,#f4f4f5_100%)] text-zinc-900 pb-28 md:pb-12">
      {/* Toast */}
      {copiedId && (
        <div
          key={toastKey}
          className="fixed top-[88px] md:top-[92px] left-1/2 -translate-x-1/2 z-[80] bg-zinc-900 text-white text-[12px] font-bold px-4 py-2 rounded-full shadow-2xl animate-in fade-in slide-in-from-top-2 duration-200"
        >
          {copiedId === "__err" ? "Kopyalanamadı" : "Panoya kopyalandı"}
        </div>
      )}

      {/* ============ HEADER ============ */}
      <header className="sticky top-0 z-50 bg-white/85 backdrop-blur-xl border-b border-zinc-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-9 w-9 rounded-xl bg-zinc-900 text-white flex items-center justify-center shrink-0">
              <Sparkles size={17} strokeWidth={2.5} />
            </div>
            <div className="min-w-0">
              <h1 className="text-[15px] md:text-base font-black tracking-tight leading-tight truncate">
                Plann · Satış Playbook
              </h1>
              <p className="text-[10.5px] text-zinc-500 -mt-0.5 hidden sm:block">
                Telefonda canlı kullanım için · v2
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center gap-1.5 text-[11px] text-zinc-500 mr-1">
              <KeyboardIcon size={12} />
              <kbd className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-200 rounded text-[10px] font-bold">←</kbd>
              <kbd className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-200 rounded text-[10px] font-bold">→</kbd>
              <span className="text-zinc-400">gezin</span>
            </div>
            <button
              onClick={() => setDrawerOpen(true)}
              className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-500 text-white text-[12px] font-black px-3 py-2 rounded-xl transition-colors shadow-sm shadow-rose-200"
              title="İtiraz kartı (O tuşu)"
            >
              <ShieldAlert size={14} />
              <span className="hidden sm:inline">İtirazlar</span>
              <kbd className="hidden md:inline px-1.5 py-0.5 bg-rose-700/40 rounded text-[9px] font-bold">
                O
              </kbd>
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="h-0.5 bg-zinc-100">
          <div
            className="h-full bg-zinc-900 transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Step chips */}
        <div className="max-w-5xl mx-auto px-2 md:px-4 py-2 overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-1.5 min-w-max">
            {STEPS.map((s, i) => {
              const active = i === activeIdx;
              const done = i < activeIdx;
              const Icon = s.icon;
              return (
                <button
                  key={s.id}
                  onClick={() => goTo(i)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11.5px] font-bold transition-all whitespace-nowrap ${
                    active
                      ? "bg-zinc-900 text-white shadow-sm"
                      : done
                      ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                      : "bg-white text-zinc-500 border border-zinc-200 hover:border-zinc-900 hover:text-zinc-900"
                  }`}
                >
                  {done ? <Check size={12} /> : <Icon size={12} />}
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {/* ============ MAIN ============ */}
      <main ref={mainRef} className="max-w-3xl mx-auto px-4 md:px-6 pt-7 md:pt-9">
        <StepHeader
          step={step}
          index={activeIdx}
          total={total}
          nextStep={activeIdx < total - 1 ? STEPS[activeIdx + 1] : null}
        />
        <div className="pb-24">{renderStep()}</div>
      </main>

      {/* ============ NAV FOOTER ============ */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/90 backdrop-blur-xl border-t border-zinc-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <button
            onClick={() => goTo(activeIdx - 1)}
            disabled={activeIdx === 0}
            className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-[13px] font-bold text-zinc-700 hover:bg-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeft size={15} />
            <span className="hidden sm:inline">Önceki</span>
          </button>

          <div className="flex items-center gap-2 text-[11px] text-zinc-500 font-semibold">
            <span className="tabular-nums">
              {String(activeIdx + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
            </span>
            <span className="h-1 w-1 rounded-full bg-zinc-300" />
            <span className="truncate max-w-[100px]">{step.label}</span>
          </div>

          {activeIdx < total - 1 ? (
            <button
              onClick={() => goTo(activeIdx + 1)}
              className="inline-flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-white px-4 py-2.5 rounded-xl text-[13px] font-bold transition-colors shadow-sm"
            >
              <span>Sonraki: {STEPS[activeIdx + 1].label}</span>
              <ArrowRight size={15} />
            </button>
          ) : (
            <button
              onClick={() => goTo(0)}
              className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-xl text-[13px] font-bold transition-colors shadow-sm"
            >
              <Check size={15} />
              Başa dön
            </button>
          )}
        </div>
      </div>

      {/* ============ OBJECTION DRAWER ============ */}
      <ObjectionDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        copy={copy}
        copiedId={copiedId}
      />

      {/* Floating objection button (mobile) */}
      <button
        onClick={() => setDrawerOpen(true)}
        className="md:hidden fixed bottom-[84px] right-4 z-30 h-14 w-14 rounded-full bg-rose-600 text-white shadow-xl shadow-rose-300/50 flex items-center justify-center active:scale-95 transition-transform"
        title="İtiraz kartını aç"
      >
        <ShieldAlert size={22} />
      </button>
    </div>
  );
};

export default SalesPlaybookPage;
