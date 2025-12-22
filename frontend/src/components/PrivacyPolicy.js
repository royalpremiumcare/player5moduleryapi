import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const PrivacyPolicy = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('common.back')}
          </Button>
          <span className="text-xl font-bold text-gray-900">PLANN</span>
        </div>
      </header>

      {/* Content */}
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          {isEnglish ? 'Privacy Policy' : 'Gizlilik Politikası'}
        </h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>{isEnglish ? 'Last Updated:' : 'Son Güncelleme:'}</strong> {isEnglish ? '28 November 2025' : '28 Kasım 2025'}
          </p>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '1. Introduction' : '1. Giriş'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'This website is operated by PLANNAPP LTD, a company registered in England and Wales. At PLANN ("we", "our" or "Company"), we respect your privacy and are committed to protecting your personal data. This Privacy Policy explains what information we collect when you use our services, how we use it and how we protect it.'
                : 'Bu web sitesi, İngiltere ve Galler’de kayıtlı PLANNAPP LTD tarafından işletilmektedir. PLANN ("biz", "bizim" veya "Şirket") olarak, gizliliğinize saygı duyuyor ve kişisel verilerinizi korumayı taahhüt ediyoruz. Bu Gizlilik Politikası, hizmetlerimizi kullandığınızda hangi bilgileri topladığımızı, nasıl kullandığımızı ve koruduğumuzu açıklar.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '2. Information We Collect' : '2. Topladığımız Bilgiler'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'We may collect the following information:' : 'Aşağıdaki bilgileri toplayabiliriz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>{isEnglish ? 'Identity Information:' : 'Kimlik Bilgileri:'}</strong> {isEnglish ? 'Name, email address, phone number' : 'Ad, soyad, e-posta adresi, telefon numarası'}</li>
              <li><strong>{isEnglish ? 'Business Information:' : 'İşletme Bilgileri:'}</strong> {isEnglish ? 'Business name, address, sector information' : 'İşletme adı, adresi, sektör bilgisi'}</li>
              <li><strong>{isEnglish ? 'Payment Information:' : 'Ödeme Bilgileri:'}</strong> {isEnglish ? 'Payment transactions are processed securely by Stripe. Your credit card details are not stored on our servers.' : 'Ödeme işlemleri Stripe tarafından güvenli şekilde işlenir. Kredi kartı bilgileriniz sunucularımızda saklanmaz.'}</li>
              <li><strong>{isEnglish ? 'Usage Data:' : 'Kullanım Verileri:'}</strong> {isEnglish ? 'Information about how you use our services' : 'Hizmetlerimizi nasıl kullandığınıza dair bilgiler'}</li>
              <li><strong>{isEnglish ? 'Appointment Data:' : 'Randevu Verileri:'}</strong> {isEnglish ? 'Customer appointment information, service records' : 'Müşteri randevu bilgileri, hizmet kayıtları'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '3. Use of Information' : '3. Bilgilerin Kullanımı'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'We use the information we collect for the following purposes:' : 'Topladığımız bilgileri şu amaçlarla kullanırız:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'To provide and improve our services' : 'Hizmetlerimizi sağlamak ve geliştirmek'}</li>
              <li>{isEnglish ? 'To manage your account and provide customer support' : 'Hesabınızı yönetmek ve müşteri desteği sunmak'}</li>
              <li>{isEnglish ? 'To process payment transactions' : 'Ödeme işlemlerini gerçekleştirmek'}</li>
              <li>{isEnglish ? 'To send SMS and email notifications' : 'SMS ve e-posta bildirimleri göndermek'}</li>
              <li>{isEnglish ? 'To fulfil our legal obligations' : 'Yasal yükümlülüklerimizi yerine getirmek'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '4. Information Sharing' : '4. Bilgi Paylaşımı'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish 
                ? 'We do not sell your personal information to third parties. We may only share your information in the following circumstances:'
                : 'Kişisel bilgilerinizi üçüncü taraflarla satmıyoruz. Bilgilerinizi yalnızca şu durumlarda paylaşabiliriz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>{isEnglish ? 'Service Providers:' : 'Hizmet Sağlayıcılar:'}</strong> {isEnglish ? 'For payment processing (Stripe), email delivery (Brevo), SMS delivery' : 'Ödeme işlemleri (Stripe), e-posta gönderimi (Brevo), SMS gönderimi için'}</li>
              <li><strong>{isEnglish ? 'Legal Requirements:' : 'Yasal Gereklilikler:'}</strong> {isEnglish ? 'Where required by law' : 'Kanunların gerektirdiği durumlarda'}</li>
              <li><strong>{isEnglish ? 'Business Transfers:' : 'İş Transferleri:'}</strong> {isEnglish ? 'In the event of a company merger or sale' : 'Şirket birleşmesi veya satışı durumunda'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '5. Data Security' : '5. Veri Güvenliği'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We use industry-standard security measures to protect your data:'
                : 'Verilerinizi korumak için endüstri standardı güvenlik önlemleri kullanıyoruz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li>{isEnglish ? 'SSL/TLS encryption' : 'SSL/TLS şifreleme'}</li>
              <li>{isEnglish ? 'Secure server infrastructure' : 'Güvenli sunucu altyapısı'}</li>
              <li>{isEnglish ? 'Regular security updates' : 'Düzenli güvenlik güncellemeleri'}</li>
              <li>{isEnglish ? 'Access control and authorisation' : 'Erişim kontrolü ve yetkilendirme'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '6. Cookies' : '6. Çerezler'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We use cookies to improve our services. Cookies are used for session management and to enhance the user experience. You can disable cookies from your browser settings.'
                : 'Hizmetlerimizi iyileştirmek için çerezler kullanıyoruz. Çerezler, oturum yönetimi ve kullanıcı deneyimini geliştirmek için kullanılır. Tarayıcı ayarlarınızdan çerezleri devre dışı bırakabilirsiniz.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '7. Your Rights' : '7. Haklarınız'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'Under GDPR, you have the following rights:' : 'KVKK kapsamında aşağıdaki haklara sahipsiniz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'To find out whether your personal data is being processed' : 'Kişisel verilerinizin işlenip işlenmediğini öğrenme'}</li>
              <li>{isEnglish ? 'To request access to your personal data' : 'Kişisel verilerinize erişim talep etme'}</li>
              <li>{isEnglish ? 'To request correction of inaccurate data' : 'Yanlış verilerin düzeltilmesini isteme'}</li>
              <li>{isEnglish ? 'To request deletion of your data' : 'Verilerinizin silinmesini talep etme'}</li>
              <li>{isEnglish ? 'To object to data processing' : 'Veri işlemeye itiraz etme'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '8. Data Retention' : '8. Veri Saklama'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We retain your personal data for as long as we provide services and for as long as necessary to fulfil our legal obligations. When you close your account, your data will be deleted at the end of the legal retention period.'
                : 'Kişisel verilerinizi, hizmet sağladığımız süre boyunca ve yasal yükümlülüklerimizi yerine getirmek için gerekli olan süre kadar saklarız. Hesabınızı kapattığınızda, verileriniz yasal saklama süreleri sonunda silinir.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '9. Contact' : '9. İletişim'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'If you have any questions about our privacy policy, please contact us:'
                : 'Gizlilik politikamız hakkında sorularınız için bizimle iletişime geçebilirsiniz:'}
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>{isEnglish ? 'Email:' : 'E-posta:'}</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Phone:' : 'Telefon:'}</strong> +44 7474 626900</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Company Name:' : 'Şirket Ünvanı:'}</strong> PLANNAPP LTD</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Company Number:' : 'Şirket Numarası:'}</strong> 16886895</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Registered Address:' : 'Kayıtlı Adres:'}</strong> 71-75 Shelton Street Covent Garden United Kingdom, London WC2H 9JQ</p>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '10. Changes' : '10. Değişiklikler'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We may update this Privacy Policy from time to time. We will notify you when significant changes are made.'
                : 'Bu Gizlilik Politikasını zaman zaman güncelleyebiliriz. Önemli değişiklikler yapıldığında sizi bilgilendireceğiz.'}
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
