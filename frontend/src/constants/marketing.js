/**
 * Plann — Marketing / Tele-Sales Constants
 *
 * Single source of truth for follow-up messages used by the marketing panel
 * after a cold call disposition. Pazarlamacı butona basınca açılan WhatsApp
 * deep link'inde bu metin prefilled olarak gelir.
 */

/**
 * Cold-call sonrası tüm dispositionlarda (İlgisiz dahil) müşteriye
 * gönderilen takip mesajı. Pazarlamacı isterse PDF'i kendi telefonundan
 * 📎 ekler. Web sitesi linki dahil — PDF link'i mesajın içinde verilmez,
 * çünkü pazarlamacı dosyayı WhatsApp Business üzerinden eklemeyi tercih
 * ediyor.
 */
export const MARKETING_FOLLOWUP_MESSAGE = `Merhaba,
PLANN Randevu Uygulamasından Yazıyorum. Az önce telefonda görüşmüştük.

Konuştuğumuz gibi, randevu defteri karmaşasını bitirip müşterilerinize otomatik hatırlatma ve kapora imkanı sunan sistemimizin detaylarını aşağıda paylaşıyorum.
📄 Sistemin tüm özelliklerini ekteki kısa tanıtım dosyasından inceleyebilirsiniz.
🌐 Nasıl çalıştığını görmek ve detaylı bilgi almak için web sitemizi ziyaret edebilirsiniz: https://plannapp.co

Sistemi salonunuzda ücretsiz test etmek isterseniz veya aklınıza takılan bir şey olursa bana direkt bu numaradan yazabilirsiniz. Bereketli işler dilerim.`;

/**
 * Verilen telefon numarasını WhatsApp deep link formatına çevirir.
 * E.g. "+90 543 511 3250" → "905435113250".
 * Tek + ya da harfler/parantezler temizlenir, sadece rakamlar bırakılır.
 */
export function normalizePhoneForWhatsApp(rawPhone) {
  if (!rawPhone) return "";
  return String(rawPhone).replace(/\D/g, "");
}

/**
 * Pazarlamacı follow-up için WhatsApp deep link'i açar.
 * Native cihazda kişinin WhatsApp Business app'i, web'de wa.me sayfası
 * üzerinden ilgili sohbet kutusu açılır; metin prefilled gelir.
 *
 * PWA standalone modda (özellikle iOS) `window.open(_blank)` Safari
 * tarafından bloklanabilir — bu yüzden user-initiated anchor click
 * yöntemini kullanıyoruz; PWA, browser ve native (Capacitor WKWebView)
 * tüm ortamlarda dış uygulamayı (WhatsApp / WhatsApp Business) açar.
 *
 * Returns false if the phone is missing/invalid (caller may toast).
 */
export function openMarketingFollowUp(phone, message = MARKETING_FOLLOWUP_MESSAGE) {
  if (typeof window === "undefined") return false;
  const digits = normalizePhoneForWhatsApp(phone);
  if (!digits) return false;
  const url = `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;

  // 1) PWA-safe yöntem: gerçek <a target=_blank> click — Safari standalone
  //    modda window.open()'ı blokluyor ama anchor click'i geçiriyor.
  try {
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    // Bazı tarayıcılar görünmeyen anchor'ı click etmiyor — minimal style.
    a.style.position = "fixed";
    a.style.left = "-9999px";
    document.body.appendChild(a);
    a.click();
    // setTimeout ile remove — bazı tarayıcılar sync remove'u tıklamadan
    // önce işliyor ve navigation iptal oluyor.
    setTimeout(() => {
      try { document.body.removeChild(a); } catch (_) {}
    }, 100);
    return true;
  } catch (_) {
    // 2) Son çare: aynı tab'da yönlendir. PWA'da bile WhatsApp universal
    //    link tarayıcı/app'a otomatik yönlendirir.
    try {
      window.location.href = url;
      return true;
    } catch (_) {
      return false;
    }
  }
}
