import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const RefundPolicy = () => {
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
          {isEnglish ? 'Refund Policy' : 'İade Politikası'}
        </h1>
        
        <div className="prose prose-gray max-w-none space-y-6">
          <p className="text-gray-600">
            <strong>{isEnglish ? 'Last Updated:' : 'Son Güncelleme:'}</strong> {isEnglish ? '28 November 2025' : '28 Kasım 2025'}
          </p>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
            <p className="text-blue-800 font-medium">
              {isEnglish 
                ? 'At PLANN, we prioritise customer satisfaction. Below you can find our refund and cancellation policy in detail.'
                : 'PLANN olarak müşteri memnuniyetini ön planda tutuyoruz. Aşağıda iade ve iptal politikamızı detaylı olarak bulabilirsiniz.'}
            </p>
          </div>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '1. Free Trial Period' : '1. Ücretsiz Deneme Süresi'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'All new users are entitled to a 7-day free trial or 50 appointments (whichever comes first). No payment is taken during the trial period and there is no commitment.'
                : 'Tüm yeni kullanıcılar 7 gün ücretsiz deneme veya 50 randevu (hangisi önce dolarsa) hakkına sahiptir. Deneme süresi boyunca herhangi bir ödeme alınmaz ve taahhüt yoktur.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '2. Subscription Cancellation' : '2. Abonelik İptali'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'You can cancel your subscription at any time:' : 'Aboneliğinizi istediğiniz zaman iptal edebilirsiniz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'You can cancel from "Settings → Subscription" in the panel' : 'Panel içinden "Ayarlar → Abonelik" bölümünden iptal edebilirsiniz'}</li>
              <li>{isEnglish ? 'Cancellation takes effect immediately' : 'İptal işlemi anında gerçekleşir'}</li>
              <li>{isEnglish ? 'After cancellation, you can continue to use the service until the end of the current billing period' : 'İptal sonrası mevcut ödeme döneminin sonuna kadar hizmeti kullanmaya devam edebilirsiniz'}</li>
              <li>{isEnglish ? 'Automatic renewal for the next period will be stopped' : 'Sonraki dönem için otomatik yenileme durdurulur'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '3. Refund Conditions' : '3. İade Koşulları'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'You may request a refund in the following circumstances:' : 'Aşağıdaki durumlarda iade talebinde bulunabilirsiniz:'}
            </p>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-green-800 mb-2">
                {isEnglish ? '✓ Refund Available' : '✓ İade Yapılabilir'}
              </h3>
              <ul className="list-disc pl-6 text-green-700 space-y-1">
                <li>{isEnglish ? 'Cancellation requests within 14 days of payment' : 'Ödeme yapıldıktan sonraki 14 gün içinde iptal talepleri'}</li>
                <li>{isEnglish ? 'Inability to use the service due to a technical issue' : 'Teknik bir sorun nedeniyle hizmetin kullanılamaması'}</li>
                <li>{isEnglish ? 'Accidental double payment' : 'Yanlışlıkla yapılan çift ödeme'}</li>
                <li>{isEnglish ? 'Service outage (longer than 24 hours)' : 'Hizmet kesintisi yaşanması (24 saatten uzun)'}</li>
              </ul>
            </div>

            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="font-semibold text-red-800 mb-2">
                {isEnglish ? '✗ No Refund' : '✗ İade Yapılamaz'}
              </h3>
              <ul className="list-disc pl-6 text-red-700 space-y-1">
                <li>{isEnglish ? 'Payment periods exceeding 14 days' : '14 günü geçen ödeme dönemleri'}</li>
                <li>{isEnglish ? 'Accounts closed due to violation of terms of use' : 'Kullanım koşulları ihlali nedeniyle kapatılan hesaplar'}</li>
                <li>{isEnglish ? 'Used service period (if actively used)' : 'Kullanılmış hizmet dönemi (aktif kullanım yapılmışsa)'}</li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '4. Refund Process' : '4. İade Süreci'}
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {isEnglish ? 'To request a refund:' : 'İade talebinde bulunmak için:'}
            </p>
            <ol className="list-decimal pl-6 text-gray-700 space-y-2">
              <li>{isEnglish ? 'Send your refund request by email to info@plannapp.co' : 'E-posta ile info@plannapp.co adresine iade talebinizi gönderin'}</li>
              <li>{isEnglish ? 'Specify your account email address and reason for refund in your email' : 'E-postanızda hesap e-posta adresinizi ve iade nedeninizi belirtin'}</li>
              <li>{isEnglish ? 'Your request will be reviewed within 3 business days' : 'Talebiniz 3 iş günü içinde incelenir'}</li>
              <li>{isEnglish ? 'Approved refunds will be returned to your payment method within 5-10 business days' : 'Onaylanan iadeler 5-10 iş günü içinde ödeme yönteminize geri yatırılır'}</li>
            </ol>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '5. Plan Change' : '5. Plan Değişikliği'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish ? 'You can upgrade or downgrade your plan at any time:' : 'İstediğiniz zaman planınızı yükseltebilir veya düşürebilirsiniz:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li><strong>{isEnglish ? 'Plan Upgrade:' : 'Plan Yükseltme:'}</strong> {isEnglish ? 'Difference charged immediately, new features activated instantly' : 'Fark ücreti anında alınır, yeni özellikler hemen aktif olur'}</li>
              <li><strong>{isEnglish ? 'Plan Downgrade:' : 'Plan Düşürme:'}</strong> {isEnglish ? 'Takes effect at end of current period, no refund for remaining time' : 'Mevcut dönem sonunda geçerli olur, kalan süre için iade yapılmaz'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '6. Payment Methods' : '6. Ödeme Yöntemleri'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'All our payments are processed through Stripe secure payment infrastructure. Accepted payment methods:'
                : 'Tüm ödemelerimiz Stripe güvenli ödeme altyapısı üzerinden işlenir. Kabul edilen ödeme yöntemleri:'}
            </p>
            <ul className="list-disc pl-6 text-gray-700 space-y-2 mt-4">
              <li>Visa</li>
              <li>Mastercard</li>
              <li>American Express</li>
              {!isEnglish && <li>Troy</li>}
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '7. Price Changes' : '7. Fiyat Değişiklikleri'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish 
                ? 'Price changes do not affect existing subscribers. New prices only apply to new subscriptions or renewal periods. You will be notified at least 30 days in advance of any price increases.'
                : 'Fiyat değişiklikleri mevcut aboneleri etkilemez. Yeni fiyatlar yalnızca yeni aboneliklere veya yenileme dönemlerine uygulanır. Fiyat artışı durumunda en az 30 gün önceden bilgilendirilirsiniz.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">
              {isEnglish ? '8. Contact' : '8. İletişim'}
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {isEnglish ? 'For refund and cancellation transactions, please contact us:' : 'İade ve iptal işlemleri için bizimle iletişime geçebilirsiniz:'}
            </p>
            <div className="bg-gray-100 p-4 rounded-lg mt-4">
              <p className="text-gray-700"><strong>{isEnglish ? 'Email:' : 'E-posta:'}</strong> info@plannapp.co</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Phone:' : 'Telefon:'}</strong> +44 7474 626900</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Company Name:' : 'Şirket Ünvanı:'}</strong> PLANNAPP LTD</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Company Number:' : 'Şirket Numarası:'}</strong> 16886895</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Registered Address:' : 'Kayıtlı Adres:'}</strong> 71-75 Shelton Street Covent Garden United Kingdom, London WC2H 9JQ</p>
              <p className="text-gray-700"><strong>{isEnglish ? 'Working Hours:' : 'Çalışma Saatleri:'}</strong> {isEnglish ? 'Monday - Friday, 09:00 - 18:00' : 'Pazartesi - Cuma, 09:00 - 18:00'}</p>
            </div>
          </section>

          <section className="mt-8 p-4 bg-gray-100 rounded-lg">
            <p className="text-gray-600 text-sm">
              {isEnglish 
                ? 'This refund policy has been prepared in accordance with UK consumer protection regulations. The right of withdrawal for digital services applies before the service has been used.'
                : 'Bu iade politikası, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve ilgili mevzuat çerçevesinde hazırlanmıştır. Dijital hizmetlerde cayma hakkı, hizmetin kullanılmaya başlanmasından önce geçerlidir.'}
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default RefundPolicy;
