import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const TermsOfService = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Geri
          </Button>
          <span className="text-xl font-bold text-gray-900">PLANN</span>
        </div>
      </header>

      {/* Content */}
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Kullanım Koşulları</h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>Son Güncelleme:</strong> 28 Kasım 2025
          </p>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">1. Hizmet Tanımı</h2>
            <p className="text-gray-700 leading-relaxed">
              PLANN, işletmelerin randevu yönetimini kolaylaştıran bir bulut tabanlı yazılım hizmetidir (SaaS). 
              Hizmetlerimiz; randevu takibi, müşteri yönetimi, personel yönetimi, finansal raporlama ve online rezervasyon 
              özelliklerini içerir.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">2. Hesap Oluşturma</h2>
            <p className="text-gray-700 leading-relaxed mb-4">Hizmetlerimizi kullanmak için:</p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>18 yaşından büyük olmalısınız</li>
              <li>Geçerli ve doğru bilgiler sağlamalısınız</li>
              <li>Hesap güvenliğinizden siz sorumlusunuz</li>
              <li>Hesap bilgilerinizi güncel tutmalısınız</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">3. Abonelik ve Ödeme</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              PLANN abonelik tabanlı bir hizmettir:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>Deneme Süresi:</strong> 7 gün ücretsiz deneme veya 50 randevu (hangisi önce dolarsa)</li>
              <li><strong>Aylık Abonelik:</strong> Her ay otomatik olarak yenilenir</li>
              <li><strong>Ödeme:</strong> Tüm ödemeler Stripe güvenli ödeme altyapısı ile işlenir</li>
              <li><strong>Fiyatlar:</strong> KDV dahil Türk Lirası cinsindendir</li>
              <li><strong>Fatura:</strong> Her ödeme sonrası e-posta ile gönderilir</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">4. İptal ve İade</h2>
            <p className="text-gray-700 leading-relaxed">
              Abonelik iptali ve iade koşulları için <a href="/refund" className="text-blue-600 hover:underline">İade Politikası</a> sayfamızı inceleyiniz.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">5. Kabul Edilebilir Kullanım</h2>
            <p className="text-gray-700 leading-relaxed mb-4">Hizmetlerimizi kullanırken şunları yapmamalısınız:</p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>Yasadışı faaliyetler için kullanmak</li>
              <li>Başkalarının haklarını ihlal etmek</li>
              <li>Sisteme zarar verecek eylemler yapmak</li>
              <li>Spam veya istenmeyen içerik göndermek</li>
              <li>Hizmetimizi tersine mühendislik yapmaya çalışmak</li>
              <li>Hesabınızı başkalarıyla paylaşmak</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">6. Fikri Mülkiyet</h2>
            <p className="text-gray-700 leading-relaxed">
              PLANN markası, logosu, yazılımı ve tüm içerikleri şirketimize aittir. 
              Hizmetlerimizi kullanmanız, fikri mülkiyet haklarımızı size devretmez.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">7. Veri Sahipliği</h2>
            <p className="text-gray-700 leading-relaxed">
              Sisteme yüklediğiniz veriler (müşteri bilgileri, randevular vb.) size aittir. 
              Hesabınızı kapattığınızda verilerinizi dışa aktarabilirsiniz.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">8. Hizmet Sürekliliği</h2>
            <p className="text-gray-700 leading-relaxed">
              Hizmetlerimizin kesintisiz çalışması için elimizden geleni yaparız. Ancak teknik bakım, 
              güncelleme veya öngörülemeyen durumlar nedeniyle geçici kesintiler yaşanabilir. 
              Planlı bakımlar önceden bildirilir.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">9. Sorumluluk Sınırlaması</h2>
            <p className="text-gray-700 leading-relaxed">
              PLANN, hizmetin kullanımından doğabilecek dolaylı, arızi veya sonuç olarak ortaya çıkan 
              zararlardan sorumlu tutulamaz. Sorumluluğumuz, son 12 ayda ödediğiniz abonelik bedeli ile sınırlıdır.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">10. Hesap Sonlandırma</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              Aşağıdaki durumlarda hesabınızı askıya alabilir veya sonlandırabiliriz:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>Kullanım koşullarının ihlali</li>
              <li>Ödeme yapılmaması</li>
              <li>Yasadışı faaliyetler</li>
              <li>Uzun süreli hareketsizlik</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">11. Uyuşmazlık Çözümü</h2>
            <p className="text-gray-700 leading-relaxed">
              Bu sözleşmeden doğan uyuşmazlıklarda Türkiye Cumhuriyeti kanunları uygulanır. 
              Uyuşmazlıkların çözümünde Nevşehir Mahkemeleri ve İcra Daireleri yetkilidir.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">12. Değişiklikler</h2>
            <p className="text-gray-700 leading-relaxed">
              Bu kullanım koşullarını zaman zaman güncelleyebiliriz. Önemli değişiklikler yapıldığında 
              e-posta ile bilgilendirileceksiniz. Hizmeti kullanmaya devam etmeniz, değişiklikleri kabul 
              ettiğiniz anlamına gelir.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">13. İletişim</h2>
            <p className="text-gray-700 leading-relaxed">
              Kullanım koşulları hakkında sorularınız için:
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>E-posta:</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>Telefon:</strong> 0543 479 3213</p>
              <p className="text-gray-700"><strong>Adres:</strong> 2000 Evler Mahallesi, Şehit Polis Murat Hamleci Sk. No:12 Kat:3 Daire:32, Nevşehir Merkez</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
