import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const PrivacyPolicy = () => {
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
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Gizlilik Politikası</h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>Son Güncelleme:</strong> 28 Kasım 2025
          </p>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">1. Giriş</h2>
            <p className="text-gray-700 leading-relaxed">
              PLANN ("biz", "bizim" veya "Şirket") olarak, gizliliğinize saygı duyuyor ve kişisel verilerinizi korumayı taahhüt ediyoruz. 
              Bu Gizlilik Politikası, hizmetlerimizi kullandığınızda hangi bilgileri topladığımızı, nasıl kullandığımızı ve koruduğumuzu açıklar.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">2. Topladığımız Bilgiler</h2>
            <p className="text-gray-700 leading-relaxed mb-4">Aşağıdaki bilgileri toplayabiliriz:</p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>Kimlik Bilgileri:</strong> Ad, soyad, e-posta adresi, telefon numarası</li>
              <li><strong>İşletme Bilgileri:</strong> İşletme adı, adresi, sektör bilgisi</li>
              <li><strong>Ödeme Bilgileri:</strong> Ödeme işlemleri Stripe tarafından güvenli şekilde işlenir. Kredi kartı bilgileriniz sunucularımızda saklanmaz.</li>
              <li><strong>Kullanım Verileri:</strong> Hizmetlerimizi nasıl kullandığınıza dair bilgiler</li>
              <li><strong>Randevu Verileri:</strong> Müşteri randevu bilgileri, hizmet kayıtları</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">3. Bilgilerin Kullanımı</h2>
            <p className="text-gray-700 leading-relaxed mb-4">Topladığımız bilgileri şu amaçlarla kullanırız:</p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>Hizmetlerimizi sağlamak ve geliştirmek</li>
              <li>Hesabınızı yönetmek ve müşteri desteği sunmak</li>
              <li>Ödeme işlemlerini gerçekleştirmek</li>
              <li>SMS ve e-posta bildirimleri göndermek</li>
              <li>Yasal yükümlülüklerimizi yerine getirmek</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">4. Bilgi Paylaşımı</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              Kişisel bilgilerinizi üçüncü taraflarla satmıyoruz. Bilgilerinizi yalnızca şu durumlarda paylaşabiliriz:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>Hizmet Sağlayıcılar:</strong> Ödeme işlemleri (Stripe), e-posta gönderimi (Brevo), SMS gönderimi için</li>
              <li><strong>Yasal Gereklilikler:</strong> Kanunların gerektirdiği durumlarda</li>
              <li><strong>İş Transferleri:</strong> Şirket birleşmesi veya satışı durumunda</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">5. Veri Güvenliği</h2>
            <p className="text-gray-700 leading-relaxed">
              Verilerinizi korumak için endüstri standardı güvenlik önlemleri kullanıyoruz:
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li>SSL/TLS şifreleme</li>
              <li>Güvenli sunucu altyapısı</li>
              <li>Düzenli güvenlik güncellemeleri</li>
              <li>Erişim kontrolü ve yetkilendirme</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">6. Çerezler</h2>
            <p className="text-gray-700 leading-relaxed">
              Hizmetlerimizi iyileştirmek için çerezler kullanıyoruz. Çerezler, oturum yönetimi ve kullanıcı deneyimini 
              geliştirmek için kullanılır. Tarayıcı ayarlarınızdan çerezleri devre dışı bırakabilirsiniz.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">7. Haklarınız</h2>
            <p className="text-gray-700 leading-relaxed mb-4">KVKK kapsamında aşağıdaki haklara sahipsiniz:</p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>Kişisel verilerinizin işlenip işlenmediğini öğrenme</li>
              <li>Kişisel verilerinize erişim talep etme</li>
              <li>Yanlış verilerin düzeltilmesini isteme</li>
              <li>Verilerinizin silinmesini talep etme</li>
              <li>Veri işlemeye itiraz etme</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">8. Veri Saklama</h2>
            <p className="text-gray-700 leading-relaxed">
              Kişisel verilerinizi, hizmet sağladığımız süre boyunca ve yasal yükümlülüklerimizi yerine getirmek için 
              gerekli olan süre kadar saklarız. Hesabınızı kapattığınızda, verileriniz yasal saklama süreleri sonunda silinir.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">9. İletişim</h2>
            <p className="text-gray-700 leading-relaxed">
              Gizlilik politikamız hakkında sorularınız için bizimle iletişime geçebilirsiniz:
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>E-posta:</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>Telefon:</strong> 0543 479 3213</p>
              <p className="text-gray-700"><strong>Adres:</strong> 2000 Evler Mahallesi, Şehit Polis Murat Hamleci Sk. No:12 Kat:3 Daire:32, Nevşehir Merkez</p>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">10. Değişiklikler</h2>
            <p className="text-gray-700 leading-relaxed">
              Bu Gizlilik Politikasını zaman zaman güncelleyebiliriz. Önemli değişiklikler yapıldığında sizi bilgilendireceğiz.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
