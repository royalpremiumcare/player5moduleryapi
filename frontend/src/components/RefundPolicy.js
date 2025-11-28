import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const RefundPolicy = () => {
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
        <h1 className="text-3xl font-bold text-gray-900 mb-8">İade Politikası</h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>Son Güncelleme:</strong> 28 Kasım 2025
          </p>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
            <p className="text-blue-800 font-medium">
              PLANN olarak müşteri memnuniyetini ön planda tutuyoruz. Aşağıda iade ve iptal politikamızı 
              detaylı olarak bulabilirsiniz.
            </p>
          </div>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">1. Ücretsiz Deneme Süresi</h2>
            <p className="text-gray-700 leading-relaxed">
              Tüm yeni kullanıcılar <strong>7 gün ücretsiz deneme</strong> veya <strong>50 randevu</strong> (hangisi önce dolarsa) 
              hakkına sahiptir. Deneme süresi boyunca herhangi bir ödeme alınmaz ve taahhüt yoktur.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">2. Abonelik İptali</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              Aboneliğinizi istediğiniz zaman iptal edebilirsiniz:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>Panel içinden "Ayarlar → Abonelik" bölümünden iptal edebilirsiniz</li>
              <li>İptal işlemi anında gerçekleşir</li>
              <li>İptal sonrası mevcut ödeme döneminin sonuna kadar hizmeti kullanmaya devam edebilirsiniz</li>
              <li>Sonraki dönem için otomatik yenileme durdurulur</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">3. İade Koşulları</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              Aşağıdaki durumlarda iade talebinde bulunabilirsiniz:
            </p>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-green-800 mb-2">✓ İade Yapılabilir</h3>
              <ul className="list-disc pl-6 text-green-700 space-y-1">
                <li>Ödeme yapıldıktan sonraki <strong>14 gün içinde</strong> iptal talepleri</li>
                <li>Teknik bir sorun nedeniyle hizmetin kullanılamaması</li>
                <li>Yanlışlıkla yapılan çift ödeme</li>
                <li>Hizmet kesintisi yaşanması (24 saatten uzun)</li>
              </ul>
            </div>

            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="font-semibold text-red-800 mb-2">✗ İade Yapılamaz</h3>
              <ul className="list-disc pl-6 text-red-700 space-y-1">
                <li>14 günü geçen ödeme dönemleri</li>
                <li>Kullanım koşulları ihlali nedeniyle kapatılan hesaplar</li>
                <li>Kullanılmış hizmet dönemi (aktif kullanım yapılmışsa)</li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">4. İade Süreci</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              İade talebinde bulunmak için:
            </p>
            <ol className="list-decimal pl-6 text-gray-700 space-y-2">
              <li>E-posta ile <strong>info@plannapp.co</strong> adresine iade talebinizi gönderin</li>
              <li>E-postanızda hesap e-posta adresinizi ve iade nedeninizi belirtin</li>
              <li>Talebiniz 3 iş günü içinde incelenir</li>
              <li>Onaylanan iadeler 5-10 iş günü içinde ödeme yönteminize geri yatırılır</li>
            </ol>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">5. Plan Değişikliği</h2>
            <p className="text-gray-700 leading-relaxed">
              İstediğiniz zaman planınızı yükseltebilir veya düşürebilirsiniz:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li><strong>Plan Yükseltme:</strong> Fark ücreti anında alınır, yeni özellikler hemen aktif olur</li>
              <li><strong>Plan Düşürme:</strong> Mevcut dönem sonunda geçerli olur, kalan süre için iade yapılmaz</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">6. Ödeme Yöntemleri</h2>
            <p className="text-gray-700 leading-relaxed">
              Tüm ödemelerimiz <strong>Stripe</strong> güvenli ödeme altyapısı üzerinden işlenir. 
              Kabul edilen ödeme yöntemleri:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li>Visa</li>
              <li>Mastercard</li>
              <li>American Express</li>
              <li>Troy</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">7. Fiyat Değişiklikleri</h2>
            <p className="text-gray-700 leading-relaxed">
              Fiyat değişiklikleri mevcut aboneleri etkilemez. Yeni fiyatlar yalnızca yeni aboneliklere 
              veya yenileme dönemlerine uygulanır. Fiyat artışı durumunda en az 30 gün önceden bilgilendirilirsiniz.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">8. İletişim</h2>
            <p className="text-gray-700 leading-relaxed">
              İade ve iptal işlemleri için bizimle iletişime geçebilirsiniz:
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>E-posta:</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>Telefon:</strong> 0543 479 3213</p>
              <p className="text-gray-700"><strong>Çalışma Saatleri:</strong> Pazartesi - Cuma, 09:00 - 18:00</p>
            </div>
          </section>

          <section className="mt-8 p-4 bg-gray-100 rounded-lg">
            <p className="text-gray-600 text-sm">
              Bu iade politikası, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve ilgili mevzuat 
              çerçevesinde hazırlanmıştır. Dijital hizmetlerde cayma hakkı, hizmetin kullanılmaya 
              başlanmasından önce geçerlidir.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default RefundPolicy;
