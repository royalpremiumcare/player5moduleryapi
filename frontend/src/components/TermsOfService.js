import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const TermsOfService = () => {
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
          {isEnglish ? 'Terms of Service' : 'Kullanım Koşulları'}
        </h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>{isEnglish ? 'Last Updated:' : 'Son Güncelleme:'}</strong> {isEnglish ? '28 November 2025' : '28 Kasım 2025'}
          </p>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '1. Service Description' : '1. Hizmet Tanımı'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'PLANN is a cloud-based software service (SaaS) that simplifies appointment management for businesses. Our services include appointment tracking, customer management, staff management, financial reporting and online booking features.'
                : 'PLANN, işletmelerin randevu yönetimini kolaylaştıran bir bulut tabanlı yazılım hizmetidir (SaaS). Hizmetlerimiz; randevu takibi, müşteri yönetimi, personel yönetimi, finansal raporlama ve online rezervasyon özelliklerini içerir.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '2. Account Creation' : '2. Hesap Oluşturma'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'To use our services:' : 'Hizmetlerimizi kullanmak için:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'You must be over 18 years of age' : '18 yaşından büyük olmalısınız'}</li>
              <li>{isEnglish ? 'You must provide valid and accurate information' : 'Geçerli ve doğru bilgiler sağlamalısınız'}</li>
              <li>{isEnglish ? 'You are responsible for your account security' : 'Hesap güvenliğinizden siz sorumlusunuz'}</li>
              <li>{isEnglish ? 'You must keep your account information up to date' : 'Hesap bilgilerinizi güncel tutmalısınız'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '3. Subscription and Payment' : '3. Abonelik ve Ödeme'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'PLANN is a subscription-based service:' : 'PLANN abonelik tabanlı bir hizmettir:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li><strong>{isEnglish ? 'Trial Period:' : 'Deneme Süresi:'}</strong> {isEnglish ? '7-day free trial or 50 appointments (whichever comes first)' : '7 gün ücretsiz deneme veya 50 randevu (hangisi önce dolarsa)'}</li>
              <li><strong>{isEnglish ? 'Monthly Subscription:' : 'Aylık Abonelik:'}</strong> {isEnglish ? 'Automatically renews each month' : 'Her ay otomatik olarak yenilenir'}</li>
              <li><strong>{isEnglish ? 'Payment:' : 'Ödeme:'}</strong> {isEnglish ? 'All payments are processed through Stripe secure payment infrastructure' : 'Tüm ödemeler Stripe güvenli ödeme altyapısı ile işlenir'}</li>
              <li><strong>{isEnglish ? 'Prices:' : 'Fiyatlar:'}</strong> {isEnglish ? 'VAT inclusive in GBP' : 'KDV dahil Türk Lirası cinsindendir'}</li>
              <li><strong>{isEnglish ? 'Invoice:' : 'Fatura:'}</strong> {isEnglish ? 'Sent by email after each payment' : 'Her ödeme sonrası e-posta ile gönderilir'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '4. Cancellation and Refund' : '4. İptal ve İade'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'For subscription cancellation and refund conditions, please see our '
                : 'Abonelik iptali ve iade koşulları için '}
              <a href="/refund" className="text-blue-600 hover:underline">
                {isEnglish ? 'Refund Policy' : 'İade Politikası'}
              </a>
              {isEnglish ? ' page.' : ' sayfamızı inceleyiniz.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '5. Acceptable Use' : '5. Kabul Edilebilir Kullanım'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'When using our services, you must not:' : 'Hizmetlerimizi kullanırken şunları yapmamalısınız:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'Use for illegal activities' : 'Yasadışı faaliyetler için kullanmak'}</li>
              <li>{isEnglish ? "Violate others' rights" : 'Başkalarının haklarını ihlal etmek'}</li>
              <li>{isEnglish ? 'Take actions that could harm the system' : 'Sisteme zarar verecek eylemler yapmak'}</li>
              <li>{isEnglish ? 'Send spam or unwanted content' : 'Spam veya istenmeyen içerik göndermek'}</li>
              <li>{isEnglish ? 'Attempt to reverse engineer our service' : 'Hizmetimizi tersine mühendislik yapmaya çalışmak'}</li>
              <li>{isEnglish ? 'Share your account with others' : 'Hesabınızı başkalarıyla paylaşmak'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '6. Intellectual Property' : '6. Fikri Mülkiyet'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'The PLANN brand, logo, software and all content belong to our company. Your use of our services does not transfer our intellectual property rights to you.'
                : 'PLANN markası, logosu, yazılımı ve tüm içerikleri şirketimize aittir. Hizmetlerimizi kullanmanız, fikri mülkiyet haklarımızı size devretmez.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '7. Data Ownership' : '7. Veri Sahipliği'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'Data you upload to the system (customer information, appointments, etc.) belongs to you. You can export your data when you close your account.'
                : 'Sisteme yüklediğiniz veriler (müşteri bilgileri, randevular vb.) size aittir. Hesabınızı kapattığınızda verilerinizi dışa aktarabilirsiniz.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '8. Service Continuity' : '8. Hizmet Sürekliliği'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We do our best to ensure our services run without interruption. However, temporary interruptions may occur due to technical maintenance, updates or unforeseen circumstances. Scheduled maintenance will be notified in advance.'
                : 'Hizmetlerimizin kesintisiz çalışması için elimizden geleni yaparız. Ancak teknik bakım, güncelleme veya öngörülemeyen durumlar nedeniyle geçici kesintiler yaşanabilir. Planlı bakımlar önceden bildirilir.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '9. Limitation of Liability' : '9. Sorumluluk Sınırlaması'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'PLANN cannot be held responsible for indirect, incidental or consequential damages arising from the use of the service. Our liability is limited to the subscription fee you have paid in the last 12 months.'
                : 'PLANN, hizmetin kullanımından doğabilecek dolaylı, arızi veya sonuç olarak ortaya çıkan zararlardan sorumlu tutulamaz. Sorumluluğumuz, son 12 ayda ödediğiniz abonelik bedeli ile sınırlıdır.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '10. Account Termination' : '10. Hesap Sonlandırma'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish 
                ? 'We may suspend or terminate your account in the following circumstances:'
                : 'Aşağıdaki durumlarda hesabınızı askıya alabilir veya sonlandırabiliriz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'Violation of terms of use' : 'Kullanım koşullarının ihlali'}</li>
              <li>{isEnglish ? 'Non-payment' : 'Ödeme yapılmaması'}</li>
              <li>{isEnglish ? 'Illegal activities' : 'Yasadışı faaliyetler'}</li>
              <li>{isEnglish ? 'Extended inactivity' : 'Uzun süreli hareketsizlik'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '11. Dispute Resolution' : '11. Uyuşmazlık Çözümü'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'The laws of the United Kingdom apply to disputes arising from this agreement. UK courts have jurisdiction for the resolution of disputes.'
                : 'Bu sözleşmeden doğan uyuşmazlıklarda Türkiye Cumhuriyeti kanunları uygulanır. Uyuşmazlıkların çözümünde Nevşehir Mahkemeleri ve İcra Daireleri yetkilidir.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '12. Changes' : '12. Değişiklikler'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'We may update these terms of use from time to time. You will be notified by email when significant changes are made. Your continued use of the service means you accept the changes.'
                : 'Bu kullanım koşullarını zaman zaman güncelleyebiliriz. Önemli değişiklikler yapıldığında e-posta ile bilgilendirileceksiniz. Hizmeti kullanmaya devam etmeniz, değişiklikleri kabul ettiğiniz anlamına gelir.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '13. Contact' : '13. İletişim'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish ? 'For questions about terms of use:' : 'Kullanım koşulları hakkında sorularınız için:'}
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>{isEnglish ? 'Email:' : 'E-posta:'}</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Phone:' : 'Telefon:'}</strong> {isEnglish ? '+90 543 479 3213' : '0543 479 3213'}</p>
              {!isEnglish && <p className="text-gray-700"><strong>Adres:</strong> 2000 Evler Mahallesi, Şehit Polis Murat Hamleci Sk. No:12 Kat:3 Daire:32, Nevşehir Merkez</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
