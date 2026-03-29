import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, X } from "lucide-react";

const sections = [
  {
    title: "Vurucu Giriş Cümleleri",
    content: (
      <>
        <p className="text-xs text-gray-400 mb-3 italic">İlk 10 saniye kritik. Karşı tarafın derdinden bahset.</p>

        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-blue-600 mb-1">A — "Gelmeyen Müşteri"</p>
            <p className="text-sm text-gray-700">"Merhaba, ben <span className="text-blue-600">[İsim]</span>, PLANN'dan arıyorum. Çok kısa bir sorum var: Randevu alıp da gelmeyen müşterileriniz yüzünden boş kalan saatleriniz oluyor mu? Biz tam olarak bu sorunu çözen bir sistem geliştirdik — 30 saniyenizi alabilir miyim?"</p>
          </div>

          <div className="bg-purple-50 border border-purple-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-purple-600 mb-1">B — "Randevu Karmaşası"</p>
            <p className="text-sm text-gray-700">"Merhaba, ben <span className="text-purple-600">[İsim]</span>. <span className="text-purple-600">[İşletme adı]</span>'nı aradım çünkü sizin gibi randevulu çalışan işletmelere özel bir dijital asistan geliştirdik. Defterde karışan randevular, çakışmalar, müşteri takibi... Bunlarla uğraşıyor musunuz? 30 saniye verirseniz hayatınızı kolaylaştıracak bir şey anlatacağım."</p>
          </div>

          <div className="bg-green-50 border border-green-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-green-600 mb-1">C — "Ciro Kaybı"</p>
            <p className="text-sm text-gray-700">"Merhaba, ben <span className="text-green-600">[İsim]</span>, PLANN Randevu Sistemi'nden. Size bir rakam söyleyeyim: Randevulu işletmeler, gelmeyen müşteriler yüzünden ayda ortalama %15-20 ciro kaybediyor. Biz bunu neredeyse sıfıra indiren bir sistem geliştirdik. İlginizi çeker mi?"</p>
          </div>
        </div>
      </>
    ),
  },
  {
    title: "Sorun → Çözüm",
    content: (
      <div className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-gray-800 mb-1">1. "Randevular defterde karışıyor, çakışmalar oluyor"</p>
          <p className="text-sm text-gray-600">"PLANN'da her şey dijital takvimde. Günlük, haftalık, aylık görünüm var. Sistem otomatik olarak çakışmaları engelliyor — aynı saate aynı personele iki kişi yazamazsınız. Üstelik yeni bir randevu geldiğinde telefonunuza anlık bildirim düşüyor."</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-800 mb-1">2. "Müşteriler randevuyu unutuyor, gelmiyor"</p>
          <p className="text-sm text-gray-600">"PLANN, randevudan önce müşterinize otomatik SMS veya WhatsApp hatırlatması gönderiyor. Siz hiçbir şey yapmıyorsunuz — sistem kendisi hallediyor. Kullanıcılarımız randevu kaçırma oranını %5'in altına düşürdü."</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-800 mb-1">3. "Telefonda sürekli randevu almak zorundayız"</p>
          <p className="text-sm text-gray-600">"PLANN size özel bir online randevu sayfası oluşturuyor. Müşterileriniz 7/24 kendi telefonlarından randevu alabiliyor. Instagram'a, WhatsApp'a, kartvizitinize QR kod olarak koyabilirsiniz."</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-800 mb-1">4. "Müşteri geçmişini takip edemiyoruz"</p>
          <p className="text-sm text-gray-600">"PLANN'da her müşterinin kartı var. Tüm geçmiş randevuları, aldığı hizmetler, özel notlar... Hepsi tek ekranda. Telefon rehberinizden tek tıkla tüm müşterilerinizi aktarabilirsiniz."</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-800 mb-1">5. "Gelir-gider takibimiz yok"</p>
          <p className="text-sm text-gray-600">"PLANN'ın içinde tam bir finansal yönetim modülü var. Randevulardan gelen gelir otomatik hesaplanıyor. Giderlerinizi giriyorsunuz — ay sonunda tek ekranda ne kazandığınızı görüyorsunuz."</p>
        </div>
        <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
          <p className="text-sm font-semibold text-amber-700 mb-1">Bonus: Yapay Zeka Asistan</p>
          <p className="text-sm text-gray-600">"PLANN'ın içinde yapay zeka asistanı var. 'Yarın kaç randevum var?' diye sorabiliyorsunuz. Teknolojiden anlamak gerekmiyor — sohbet eder gibi kullanıyorsunuz."</p>
        </div>
      </div>
    ),
  },
  {
    title: "Paket Sunumu",
    content: (
      <div className="space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left p-2 font-semibold text-gray-700 border-b">Paket</th>
                <th className="text-center p-2 font-semibold text-gray-700 border-b">Randevu/Ay</th>
                <th className="text-center p-2 font-semibold text-gray-700 border-b">Fiyat</th>
                <th className="text-center p-2 font-semibold text-gray-700 border-b">İlk Ay</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="p-2 border-b font-medium">Standart</td>
                <td className="p-2 border-b text-center">100</td>
                <td className="p-2 border-b text-center">1.090₺</td>
                <td className="p-2 border-b text-center font-semibold text-green-600">990₺</td>
              </tr>
              <tr className="bg-indigo-50/50">
                <td className="p-2 border-b font-medium">Profesyonel</td>
                <td className="p-2 border-b text-center">300</td>
                <td className="p-2 border-b text-center">1.490₺</td>
                <td className="p-2 border-b text-center font-semibold text-green-600">1.390₺</td>
              </tr>
              <tr>
                <td className="p-2 border-b font-medium">Kurumsal</td>
                <td className="p-2 border-b text-center">2.000</td>
                <td className="p-2 border-b text-center">2.850₺</td>
                <td className="p-2 border-b text-center font-semibold text-green-600">2.490₺</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500">Tüm paketlerde: Sınırsız personel, sınırsız müşteri, online randevu, hatırlatma, yapay zeka asistan. Yıllık ödemede 2 ay ücretsiz. 7 gün ücretsiz deneme.</p>

        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Nasıl Konumlandır?</p>
          <div className="bg-blue-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-blue-700">Günde 3-4 müşteri → Standart</p>
            <p className="text-xs text-gray-600">"Ayda 100 randevu. Günlük 33₺'ye tüm özellikler — bir kahve parası bile değil."</p>
          </div>
          <div className="bg-indigo-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-indigo-700">Günde 8-10 müşteri → Profesyonel</p>
            <p className="text-xs text-gray-600">"Ayda 300 randevu. Yapay zeka asistan gelişmiş kullanımla geliyor."</p>
          </div>
          <div className="bg-purple-50 rounded-lg p-2.5">
            <p className="text-xs font-semibold text-purple-700">Günde 15+ / Klinik → Kurumsal</p>
            <p className="text-xs text-gray-600">"Ayda 2.000 randevu. Sınırsız yapay zeka, sınırsız personel."</p>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "İtiraz Cevapları",
    content: (
      <div className="space-y-4">
        <div className="border border-red-100 rounded-lg overflow-hidden">
          <div className="bg-red-50 px-3 py-2">
            <p className="text-sm font-semibold text-red-700">"Biz defter/ajanda ile memnunuz"</p>
          </div>
          <div className="p-3">
            <p className="text-sm text-gray-700">"Anlıyorum, defter de bir yöntem. Ama şunu sorayım: Deftere yazılmış bir randevuyu son anda iptal eden müşteriye otomatik hatırlatma gönderebiliyor musunuz? Ya da aynı saate iki kişi yazıldığında defter sizi uyarıyor mu?"</p>
            <p className="text-xs text-gray-500 mt-2 italic">"7 gün ücretsiz deneyin. Defteri bırakmayın, yanında deneyin. Farkı hemen göreceksiniz."</p>
          </div>
        </div>

        <div className="border border-orange-100 rounded-lg overflow-hidden">
          <div className="bg-orange-50 px-3 py-2">
            <p className="text-sm font-semibold text-orange-700">"Şu an meşgulüm / Vaktim yok"</p>
          </div>
          <div className="p-3">
            <p className="text-sm text-gray-700">"Tamamen anlıyorum. Zaten PLANN'ın amacı da bu yoğunluğu azaltmak. Size 2 dakikalık bir WhatsApp mesajı atayım, müsait olduğunuzda bakarsınız."</p>
            <p className="text-xs text-gray-500 mt-2 italic">Alternatif: "Sizi en az meşgul olduğunuz saatte tekrar arayabilir miyim?"</p>
          </div>
        </div>

        <div className="border border-yellow-100 rounded-lg overflow-hidden">
          <div className="bg-yellow-50 px-3 py-2">
            <p className="text-sm font-semibold text-yellow-700">"Fiyatı yüksek / Bütçemiz yok"</p>
          </div>
          <div className="p-3">
            <p className="text-sm text-gray-700">"Haftada sadece 1 müşteriniz randevuya gelmese, o boş saatin maliyeti ne? 200-300₺? PLANN'ın Standart paketi günlük 33₺. Bir haftada kendini geri ödüyor."</p>
            <p className="text-xs text-gray-500 mt-2 italic">"İlk ay indirimli 990₺. 7 gün ücretsiz, beğenmezseniz 1 kuruş ödemezsiniz."</p>
          </div>
        </div>

        <div className="border border-blue-100 rounded-lg overflow-hidden">
          <div className="bg-blue-50 px-3 py-2">
            <p className="text-sm font-semibold text-blue-700">"Personelim teknolojiden anlamıyor"</p>
          </div>
          <div className="p-3">
            <p className="text-sm text-gray-700">"PLANN'ı WhatsApp kullanabilen herkes kullanabilir. O kadar basit. İçinde adım adım rehber var, yapay zeka asistana yazarak soru sorabilirsiniz. Birçok müşterimiz 50-60 yaş üstü ve gayet rahat kullanıyor."</p>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "WhatsApp Takip Mesajları",
    content: (
      <div className="space-y-4">
        <div>
          <p className="text-xs font-semibold text-green-600 mb-1">İlgilenen Müşteri İçin</p>
          <div className="bg-green-50 border border-green-100 rounded-lg p-3 text-sm text-gray-700 whitespace-pre-line">
{`Merhaba [İşletme Adı] 👋

Ben [İsim], az önce PLANN hakkında konuştuk.

Size 7 günlük ücretsiz deneme hesabı açabilirim. Kredi kartı gerekmez, beğenmezseniz hiçbir ücret yok.

PLANN ile neler yapabilirsiniz:
✅ Otomatik SMS/WhatsApp hatırlatma
✅ Online randevu sayfası (7/24)
✅ Akıllı takvim + çakışma engeli
✅ Yapay zeka asistan

Deneme hesabınızı açmamı ister misiniz? 🚀

PLANN — plannapp.co`}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-500 mb-1">"Düşüneceğim" Diyen Müşteri İçin</p>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-700 whitespace-pre-line">
{`Merhaba [İşletme Adı] 👋

Ben [İsim], az önce telefonla görüştük. Vakit ayırdığınız için teşekkür ederim.

PLANN hakkında kısa bilgi:
📱 3 dakikada kurulum
📅 Randevular karışmaz, çakışmaz
📩 Müşteriye otomatik hatırlatma
🌐 Online randevu sayfası (7/24)
🤖 Yapay zeka asistan

7 gün ücretsiz, bağlayıcılığı yok.

Sorunuz olursa yazabilirsiniz ✌️`}
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "Rakiplerden Farkımız",
    content: (
      <div className="space-y-3">
        <div className="flex gap-2">
          <span className="text-lg">🇹🇷</span>
          <div>
            <p className="text-sm font-semibold text-gray-800">Türkiye'ye Özel</p>
            <p className="text-xs text-gray-600">Arayüz, SMS, WhatsApp hatırlatma, TL fiyatlandırma — her şey Türk işletmeleri için tasarlandı.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="text-lg">🤖</span>
          <div>
            <p className="text-sm font-semibold text-gray-800">Yapay Zeka Dahil</p>
            <p className="text-xs text-gray-600">Çoğu rakipte yok veya ekstra ücretli. PLANN'da her pakette dahil.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="text-lg">🌐</span>
          <div>
            <p className="text-sm font-semibold text-gray-800">Online Randevu + QR Kod</p>
            <p className="text-xs text-gray-600">Birçok rakip sadece takvim verir. PLANN müşteriye açık randevu sayfası da verir.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="text-lg">📱</span>
          <div>
            <p className="text-sm font-semibold text-gray-800">Web + Mobil Anlık Senkron</p>
            <p className="text-xs text-gray-600">Ofiste bilgisayardan, dışarıda telefondan — hiçbir şey kaçırmaz.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="text-lg">🔒</span>
          <div>
            <p className="text-sm font-semibold text-gray-800">5 Katmanlı Güvenlik</p>
            <p className="text-xs text-gray-600">Spam, bot, sahte randevu engeli. Rakiplerde bu seviyede güvenlik yok.</p>
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "Tüm Özellikler (55 Madde)",
    content: (
      <div className="space-y-3 text-xs text-gray-700">
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Randevu Yönetimi</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Akıllı Takvim (gün/hafta/ay görünümü)</li>
            <li>Çakışma engeli</li>
            <li>Sürükle-bırak ile randevu taşıma</li>
            <li>3 adımda hızlı randevu oluşturma</li>
            <li>Çok seanslı otomatik planlayıcı</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Online Randevu Sayfası</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>İşletmeye özel link (plannapp.co/salon-adi)</li>
            <li>Hizmet ve personel seçimi</li>
            <li>Sadece müsait saatler gösterilir</li>
            <li>Google Maps konum</li>
            <li>İşletme galeri fotoğrafları</li>
            <li>QR kod paylaşım</li>
            <li>5 katmanlı güvenlik (spam engeli)</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Hatırlatma & Bildirim</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Otomatik SMS hatırlatma</li>
            <li>WhatsApp hatırlatma</li>
            <li>Ayarlanabilir zamanlama</li>
            <li>Yeni randevu push bildirimi</li>
            <li>Değişiklik/iptal bildirimi</li>
            <li>Android + iOS bildirim desteği</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Müşteri Yönetimi</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Müşteri kartları (isim, telefon, geçmiş)</li>
            <li>Özel notlar ("alerjisi var" gibi)</li>
            <li>Randevu geçmişi</li>
            <li>Tek tıkla arama/mesaj</li>
            <li>Rehberden toplu aktarım</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Personel Yönetimi</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Kişiye özel hesap ve takvim</li>
            <li>Hizmet atama</li>
            <li>İzin günleri ve mola saatleri</li>
            <li>Maaş/prim takibi</li>
            <li>Yetki kontrolü (personel vs yönetici)</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Hizmet Yönetimi</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Hizmet listesi (isim, fiyat, süre)</li>
            <li>Sürükle-bırak sıralama</li>
            <li>Geçici açma/kapama</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Finans</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Otomatik gelir takibi</li>
            <li>Gider girişi (kira, fatura, malzeme)</li>
            <li>Özet raporlar (günlük/haftalık/aylık)</li>
            <li>Kasa modülü</li>
            <li>Personel maaş hesaplama</li>
          </ul>
        </div>
        <div>
          <p className="font-semibold text-gray-800 text-sm mb-1">Diğer</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li>Yapay zeka sohbet asistanı + sesli kullanım</li>
            <li>Web + Android + iOS</li>
            <li>Anlık senkronizasyon</li>
            <li>3 dakikada kurulum sihirbazı</li>
            <li>Uygulama içi tur rehberi</li>
            <li>Yardım merkezi</li>
            <li>Excel veri aktarımı</li>
            <li>Çift dil (TR/EN)</li>
          </ul>
        </div>
      </div>
    ),
  },
];

function AccordionItem({ title, content, isOpen, onToggle }) {
  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 transition-colors text-left"
      >
        <span className="text-sm font-semibold text-gray-800">{title}</span>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-1 bg-white border-t border-gray-50">
          {content}
        </div>
      )}
    </div>
  );
}

export default function SalesGuide() {
  const [isOpen, setIsOpen] = useState(false);
  const [openSections, setOpenSections] = useState({});

  const toggleSection = (idx) => {
    setOpenSections((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-xl text-sm font-medium text-indigo-700 transition-colors"
      >
        <BookOpen className="w-4 h-4" />
        Satış Rehberi
      </button>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-indigo-100 overflow-hidden">
      <div className="bg-indigo-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-white" />
          <span className="text-white text-sm font-semibold">Satış Rehberi</span>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 hover:bg-white/20 rounded-lg transition-colors"
        >
          <X className="w-4 h-4 text-white" />
        </button>
      </div>
      <div className="p-3 space-y-2 max-h-[60vh] overflow-y-auto">
        {sections.map((section, idx) => (
          <AccordionItem
            key={idx}
            title={section.title}
            content={section.content}
            isOpen={!!openSections[idx]}
            onToggle={() => toggleSection(idx)}
          />
        ))}
      </div>
    </div>
  );
}
