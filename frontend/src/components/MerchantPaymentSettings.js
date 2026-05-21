import { useState, useEffect, useCallback } from "react";
import api from "../api/api";
import { toast } from "sonner";
import { CreditCard, Shield, Clock, CheckCircle, AlertCircle, ChevronRight, Banknote, Building2, ArrowLeft, X, FileText } from "lucide-react";

const TIER_META = {
  fast: {
    title: "Hızlı Çekim",
    desc: "Nakit akışını hızlandırmak isteyenler için düşük çekim limitli esnek plan.",
  },
  standard: {
    title: "Dengeli Plan",
    desc: "Hem işlem ücretinden tasarruf edip hem de düzenli nakit çekebileceğiniz optimum plan.",
  },
  vip: {
    title: "Yüksek Hacim",
    desc: "Büyük cirolu işletmeler için en düşük işlem maliyetine sahip profesyonel plan.",
  },
};

const TC_TEXT = `PLANN Ödeme Hizmet Koşulları

Son Güncelleme: 21 Nisan 2026 (v2)

Bu koşullar, PLANNAPP LTD ("PLANN", "biz") tarafından sunulan ödeme tahsilat ve hesaba aktarım hizmetlerinin kullanımını düzenler. Ödeme ayarlarınızı kaydederek aşağıdaki koşulları kabul etmiş sayılırsınız.

1. Tanımlar
• İşletme (Merchant): PLANN platformuna kayıtlı ve ödeme tahsilat hizmetini kullanan gerçek veya tüzel kişi.
• Müşteri: İşletmenin hizmetleri için online ödeme yapan son kullanıcı.
• Cüzdan: İşletmenin PLANN üzerindeki sanal hesabı; tahsil edilen ödemelerin biriktiği havuz.
• Çekim (Payout): Cüzdandaki bakiyenin işletmenin banka hesabına aktarılması.
• Platform Hizmet Bedeli: Her işlem başına kesilen, online randevu altyapısı, güvenli ödeme işleme ve müşteri destek hizmetlerini kapsayan ücret.
• Ödeme Havuzu (Batch): Haftalık olarak eşik üstü cüzdanlardan toplanan ve toplu işlenen ödeme grubu.

2. Ticari Vekalet ve Ödeme Tahsilat Hizmeti
2.1. PLANN, İngiltere ve Galler'de kayıtlı PLANNAPP LTD (Company No: 16148498) tüzel kişiliği altında faaliyet gösterir.
2.2. PLANN, Stripe altyapısı aracılığıyla müşterilerinizden güvenli kredi/banka kartı ödemesi tahsil eder. Bu tahsilat, PLANNAPP LTD adına ve hesabına gerçekleştirilir.
2.3. Tahsil edilen tutarlar, platform hizmet bedeli ve işlem maliyetleri (Stripe/Wise) düşüldükten sonra işletme cüzdanınıza yansıtılır.
2.4. PLANN, ödeme işlemlerinde ticari vekil (commercial agent) rolü üstlenir ve ödeme akışının operasyonel organizatörüdür; işletme ile müşteri arasındaki hizmet sözleşmesinin doğrudan tarafı değildir.
2.5. İşletme, PLANN'ın müşterilerinden ödeme tahsil etmesine açıkça yetki verir.
2.6. PLANN, teknik risk, dolandırıcılık şüphesi, dispute veya tekrarlayan iade durumlarında ödeme havuzunu askıya alma veya manuel inceleme uygulama hakkını saklı tutar.

3. Platform Hizmet Bedeli ve Ücretler
3.1. Platform hizmet bedeli, seçtiğiniz çekim planına (Hızlı Çekim / Dengeli Plan / Yüksek Hacim) göre yüzdelik oran + sabit ücret olarak belirlenir ve ödeme ayarları ekranında açıkça gösterilir.
3.2. Platform hizmet bedeli; 7/24 online randevu altyapısı, güvenli kredi kartı işleme, sanal POS, kur koruma (TRY pazar için) ve müşteri destek hizmetlerinin tamamını kapsar.
3.3. Cüzdanınızdaki bakiyenin banka hesabınıza aktarımında (çekim/payout) hiçbir havale veya transfer masrafı işletmeden kesilmez; bu masraflar platform hizmet bedeli içindedir.
3.4. Platform hizmet bedeli tercihinize göre sizden (seller_pays) veya müşterinizden (buyer_pays) tahsil edilir. Bu tercih ödeme ayarlarından değiştirilebilir ve randevu bazında özel olarak da uygulanabilir.
3.5. "Müşteri öder" modunda; platform hizmet bedeli, Stripe kesintisi ve Wise havale maliyeti müşteri ödemesine eklenir. Bu sayede işletme, hedeflediği net tutara tam olarak ulaşır.

4. Çekim (Payout) Koşulları
4.1. Çekimler otomatik batch (toplu) mantığıyla işlenir — manuel çekim butonu kaldırılmıştır.
4.2. Her Salı gece eşik üstü cüzdanlar taranır; eşiği aşanlar bir sonraki Çarşamba ödeme havuzuna alınır.
4.3. Ödemeler Wise paneli üzerinden manuel olarak onaylanıp fonlanır; aksi durumlarda bir sonraki haftaya veya retry kuyruğuna ertelenir.
4.4. Çekim yapılabilmesi için cüzdan bakiyenizin seçili planınızın minimum eşiğine ulaşmış olması gerekir.
4.5. İlk çekim talebinizden önce KYC (Kimlik Doğrulama) sürecinin tamamlanmış olması zorunludur.
4.6. Banka bilgilerinizde (IBAN/Sort Code) değişiklik yapmanız halinde güvenlik amacıyla 72 saatlik bekleme süresi uygulanır.
4.7. Çekimler Wise ödeme altyapısı üzerinden işlenir; işlem süreleri banka/ülkeye göre 1-3 iş günü arasında değişebilir.
4.8. Batch'e alınan tutar 7 gün içinde fonlanmazsa otomatik olarak kullanılabilir bakiyeye geri döner.

5. İade ve İhtilaf (Dispute) Politikası
5.1. İade talepleri işletme paneli üzerinden "İade Talebi Oluştur" akışı ile başlatılır; talep gerekçe içermelidir.
5.2. İade talepleri yalnızca PLANN yöneticisinin (SuperAdmin) onayı ile işleme alınır. Onay sonrası Stripe üzerinden iade yapılır ve kaydınıza yansıtılır.
5.3. Öncelik seviyeleri: Normal (12 saat), Yüksek (4 saat), Acil (1 saat). Süresi aşan talepler otomatik olarak eskale edilir.
5.4. İade durumunda yalnızca hizmet bedeli müşteriye iade edilir. Platform hizmet bedeli iade kapsamı dışındadır ve PLANNAPP LTD hesabında kalır.
5.5. Seans paketi kapsamındaki iadeler, kullanılmayan kalan seans sayısına orantılı olarak hesaplanır. Kullanılmış seanslar iade edilmez.
5.6. Müşteri kart ihtilafı (chargeback) durumunda, ilgili tutar cüzdan bakiyenizden dondurulur ve ihtilaf sonucuna göre çözümlenir.
5.7. Kapora ödemeleri, müşterinin iptal etmesi halinde işletmeye ait kalır ve otomatik iade yapılmaz.
5.8. İade veya dispute kaybı cüzdanınızı eksiye düşürürse, "bekleyen borç" oluşur ve ödemeler bu borç kapanana kadar durdurulur. Gelecek tahsilatlar önce bu borcu kapatır.

6. KYC ve Güvenlik
6.1. Ödeme hizmetinden yararlanmak için işletme kimlik doğrulaması (KYC) zorunludur.
6.2. PLANN, şüpheli işlemler tespit ettiğinde cüzdanı geçici olarak dondurma hakkını saklı tutar.
6.3. Aylık işlem hacmi belirli eşikleri aştığında ek doğrulama talep edilebilir (AML — Kara Para Aklama Önleme).

7. Sorumluluk Sınırları
7.1. PLANN, işletme ile müşteri arasındaki hizmet kalitesi, teslimat veya memnuniyet konularında sorumluluk kabul etmez.
7.2. Ödeme altyapısı sağlayıcılarından (Stripe, Wise) kaynaklanan gecikmeler veya kesintiler nedeniyle oluşabilecek dolaylı zararlardan PLANN sorumlu tutulamaz.
7.3. İşletme, platformu yasal olmayan faaliyetler için kullanmamayı taahhüt eder.

8. Değişiklikler
8.1. PLANN, bu koşulları önceden bildirim yaparak güncelleme hakkını saklı tutar.
8.2. Güncellenen koşullar, ödeme ayarları sayfasında ve e-posta ile bildirilir.
8.3. Güncelleme sonrası hizmeti kullanmaya devam etmeniz, yeni koşulları kabul ettiğiniz anlamına gelir.

9. İletişim
Sorularınız için: support@plannapp.co

© 2026 PLANNAPP LTD (Company No: 16148498). Tüm hakları saklıdır.`;

export default function MerchantPaymentSettings({ onNavigate }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});
  const [tcAccepted, setTcAccepted] = useState(false);
  const [showTcModal, setShowTcModal] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      const res = await api.get("/merchant/payment-settings");
      setSettings(res.data);
      setForm({
        payout_mode: "auto", // Weekly auto batch is the only supported mode
        payout_tier: res.data.payout_tier,
        fee_preference: res.data.fee_preference,
        iban: res.data.iban || "",
        account_holder_name: res.data.account_holder_name || "",
        sort_code: res.data.sort_code || "",
        account_number: res.data.account_number || "",
      });
      if (res.data.tc_accepted) setTcAccepted(true);
    } catch (err) {
      console.error("Settings load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const handleSave = async () => {
    if (!tcAccepted) {
      toast.error("Lütfen Ödeme Hizmet Koşullarını kabul edin");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, tc_accepted: true };
      if (settings.base_currency === "GBP") {
        delete payload.iban;
      } else {
        delete payload.sort_code;
        delete payload.account_number;
      }
      await api.put("/merchant/payment-settings", payload);
      toast.success("Ayarlar kaydedildi");
      await loadSettings();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Kaydetme hatası");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
      </div>
    );
  }

  if (!settings) return (
    <div className="p-4 pb-24 max-w-lg mx-auto space-y-4">
      <button onClick={() => onNavigate && onNavigate("settings")} className="flex items-center gap-2 text-gray-600 hover:text-gray-900">
        <ArrowLeft className="h-5 w-5" /> <span className="text-sm">Geri</span>
      </button>
      <div className="text-center text-gray-500 py-12">Ödeme ayarları yüklenemedi.</div>
    </div>
  );

  const bc = settings.base_currency;
  const isGBP = bc === "GBP";
  const tiers = settings.tiers || {};
  const currencySymbol = isGBP ? "£" : "₺";

  return (
    <div className="p-4 pb-24 max-w-lg mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate && onNavigate("settings")}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <CreditCard className="h-5 w-5" /> Ödeme Ayarları
          </h1>
        </div>
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-600">
          {bc}
        </span>
      </div>

      {/* KYC Status */}
      <div className={`rounded-xl p-4 border flex items-center gap-3 ${
        settings.kyc_verified
          ? "bg-green-50 border-green-200"
          : "bg-amber-50 border-amber-200"
      }`}>
        {settings.kyc_verified ? (
          <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
        ) : (
          <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0" />
        )}
        <div>
          <p className={`text-sm font-medium ${settings.kyc_verified ? "text-green-700" : "text-amber-700"}`}>
            {settings.kyc_verified ? "KYC Doğrulandı" : "KYC Doğrulanmadı"}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {settings.kyc_verified ? "Ödeme almaya hazırsınız" : "Ödeme alabilmek için doğrulama gerekli"}
          </p>
        </div>
      </div>

      {/* Bank Details */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
        <div className="flex items-center gap-2 text-gray-900 font-medium">
          <Building2 className="h-4 w-4" />
          Banka Bilgileri
        </div>

        {settings.cooldown?.cooldown_active && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700 flex items-center gap-2">
            <Clock className="h-4 w-4 flex-shrink-0" />
            IBAN değişikliği bekleme süresi aktif ({settings.cooldown.remaining_hours} saat kaldı)
          </div>
        )}

        <div>
          <label className="block text-xs text-gray-500 mb-1">Hesap Sahibi</label>
          <input
            type="text"
            value={form.account_holder_name}
            onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })}
            placeholder="Ad Soyad"
            className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-sm focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
          />
        </div>

        {isGBP ? (
          <>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Sort Code</label>
              <input
                type="text"
                value={form.sort_code}
                onChange={(e) => setForm({ ...form, sort_code: e.target.value })}
                placeholder="12-34-56"
                maxLength={8}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-sm focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Account Number</label>
              <input
                type="text"
                value={form.account_number}
                onChange={(e) => setForm({ ...form, account_number: e.target.value })}
                placeholder="12345678"
                maxLength={8}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-sm focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-xs text-gray-500 mb-1">IBAN</label>
            <input
              type="text"
              value={form.iban}
              onChange={(e) => setForm({ ...form, iban: e.target.value.replace(/\s/g, '').toUpperCase() })}
              placeholder="TR000000000000000000000000"
              maxLength={34}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-sm font-mono focus:ring-2 focus:ring-zinc-900 focus:border-transparent outline-none"
            />
          </div>
        )}

        {settings.wise_recipient_verified ? (
          <div className="flex items-center gap-1.5 text-green-600 text-xs">
            <Shield className="h-3.5 w-3.5" /> Banka hesabınız doğrulandı
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-gray-400 text-xs">
            <Shield className="h-3.5 w-3.5" /> Banka bilgileri kaydedildiğinde doğrulanacak
          </div>
        )}
      </div>

      {/* Tier Selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2 text-gray-900 font-medium">
          <Banknote className="h-4 w-4" />
          Çekim Planı
        </div>

        {Object.entries(tiers).map(([name, tier]) => {
          const meta = TIER_META[name] || { title: name, desc: "", fee: tier.fee_rate_pct, example: "" };
          const isSelected = form.payout_tier === name;
          return (
            <button
              key={name}
              onClick={() => setForm({ ...form, payout_tier: name })}
              className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                isSelected
                  ? "border-zinc-900 bg-white"
                  : "border-gray-200 hover:border-gray-300 bg-white"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-bold text-gray-900">{meta.title}</p>
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  isSelected ? "border-zinc-900" : "border-gray-300"
                }`}>
                  {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-zinc-900" />}
                </div>
              </div>
              <p className="text-sm text-gray-500 mb-3">{meta.desc}</p>
              <div className="flex items-center gap-4 text-sm flex-wrap">
                <span className="bg-gray-100 text-gray-700 px-2 py-1 rounded font-medium">
                  Platform Hizmet Bedeli: {tier.fee_rate_pct}
                </span>
                <span className="text-gray-500">
                  Hesaba Yatacak Net Tutar: Min. {tier.limit_display}
                </span>
              </div>
            </button>
          );
        })}

        <p className="text-sm text-gray-500 leading-relaxed mt-3">
          💡 Bilgilendirme: Platform hizmet bedeli; 7/24 online randevu altyapısı, güvenli kredi kartı işleme, sanal POS ve müşteri destek hizmetlerinin tamamını kapsar.
        </p>
      </div>

      {/* Fee Preference */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
        <p className="text-sm font-medium text-gray-900">Platform Hizmet Bedeli Tercihi</p>
        {[
          { 
            value: "seller_pays", 
            label: "Platform Hizmet Bedeli Benden Kesilsin", 
            desc: "Müşteriniz ödeme ekranında sadece hizmetin net fiyatını görür. Platform hizmet bedeli kasanıza yansıtılacak tutardan düşülür." 
          },
          { 
            value: "buyer_pays", 
            label: "Platform Hizmet Bedelini Müşteri Karşılasın", 
            desc: "Müşteriniz ödeme adımında hizmet bedeline ek olarak platform hizmet bedelini de öder. Sizin hak edişinizden hiçbir kesinti yapılmaz." 
          },
        ].map((opt) => {
          const isSelected = form.fee_preference === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setForm({ ...form, fee_preference: opt.value })}
              className={`w-full p-3 rounded-xl border-2 text-left transition-all ${
                isSelected
                  ? "border-zinc-900 bg-white"
                  : "border-gray-200 hover:border-gray-300 bg-white"
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-900">{opt.label}</p>
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  isSelected ? "border-zinc-900" : "border-gray-300"
                }`}>
                  {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-zinc-900" />}
                </div>
              </div>
              <p className="text-sm text-gray-500 mt-1">{opt.desc}</p>
            </button>
          );
        })}
      </div>

      {/* Payout Mode selector removed — all orgs use weekly auto batch */}

      {/* T&C Checkbox */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="tc-accept"
            checked={tcAccepted}
            onChange={(e) => setTcAccepted(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-zinc-900 focus:ring-zinc-900"
          />
          <label htmlFor="tc-accept" className="text-sm text-gray-700 leading-relaxed cursor-pointer">
            <button 
              type="button"
              onClick={(e) => { e.preventDefault(); setShowTcModal(true); }}
              className="text-zinc-900 font-semibold underline hover:text-zinc-700"
            >
              Ödeme Hizmet Koşulları
            </button>'nı okudum ve kabul ediyorum.
          </label>
        </div>
      </div>

      {/* Save Button */}
      <button
        onClick={handleSave}
        disabled={saving || !tcAccepted}
        className="w-full py-3 rounded-xl bg-zinc-900 text-white font-medium text-sm hover:bg-black active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {saving ? (
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
        ) : (
          "Kaydet"
        )}
      </button>

      {/* T&C Modal */}
      {showTcModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setShowTcModal(false)}>
          <div 
            className="bg-white rounded-2xl max-w-lg w-full max-h-[80vh] flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-zinc-900" />
                <h2 className="text-lg font-bold text-zinc-900">Ödeme Hizmet Koşulları</h2>
              </div>
              <button 
                onClick={() => setShowTcModal(false)}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">{TC_TEXT}</pre>
            </div>
            <div className="p-4 border-t border-gray-200">
              <button
                onClick={() => { setTcAccepted(true); setShowTcModal(false); }}
                className="w-full py-2.5 rounded-xl bg-zinc-900 text-white text-sm font-medium hover:bg-black transition-colors"
              >
                Okudum ve Kabul Ediyorum
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
