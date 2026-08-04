"""PLANN Asistan — İçerik Yazarı Brief PDF üretici (Güzellik Salonu / SINCERE_BEAUTY).

DejaVuSans (Türkçe destekli) fontlarıyla, mevcut 120 varyasyonu referans olarak
gömer. Çıktı: PLANN_Asistan_Icerik_Brief_Guzellik_Salonu.pdf
"""
import json
from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
DATA = "/var/www/player5moduleryapi/beauty_variations.json"
OUT = "/var/www/player5moduleryapi/PLANN_Asistan_Icerik_Brief_Guzellik_Salonu.pdf"

# Renkler
INK = (24, 24, 27)        # zinc-900
MUTE = (113, 113, 122)    # zinc-500
ACCENT = (16, 185, 129)   # emerald-600
LINE = (228, 228, 231)    # zinc-200
CARD = (244, 244, 245)    # zinc-100

SCENARIOS = [
    ("morning_busy", "Sabah · Yoğun Gün", "08:30",
     "Bugün doluluk ≥ %75. Salon tıklım tıklım. Enerjik, motive edici, 'hadi bugün para günü' havası.",
     "{isim}, {randevu_sayisi} (bugünkü randevu), {ilk_randevu_saati}"),
    ("morning_normal", "Sabah · Normal Gün", "08:30",
     "Doluluk orta seviyede, belirgin boşluk yok. Sakin ama pozitif; günü selamlayan sıcak bir tona sahip.",
     "{isim}, {randevu_sayisi}, {ilk_randevu_saati}"),
    ("morning_early_gap", "Sabah · Erken Boşluk", "08:30",
     "Günün ERKEN saatlerinde ≥120 dk kesintisiz boşluk var (boşluk 08:30'a yakın başlıyor). "
     "'Sabahı dolduralım' aksiyon çağrısı.",
     "{isim}, {bos_baslangic}, {bos_bitis}"),
    ("morning_late_gap", "Sabah · Öğleden Sonra Boşluk", "08:30",
     "Öğleden sonra ≥120 dk kesintisiz boşluk var (boşluk 08:30'dan ≥180 dk sonra). "
     "Akşam dolu ama gündüz açık; story/kampanya öner.",
     "{isim}, {bos_baslangic}, {bos_bitis}"),
    ("night_growth", "Gece · Büyüme Günü", "22:00",
     "O gün ≥2 YENİ müşteri kazanılmış. Gurur ve kutlama tonu. {randevu_sayisi} = yeni müşteri sayısı.",
     "{isim}, {randevu_sayisi} (yeni müşteri), {ciro}"),
    ("night_loyalty", "Gece · Sadakat Günü", "22:00",
     "Dönen müşteri oranı ≥ %70 (en az 3 benzersiz müşteri). 'Seni seviyorlar, geri geliyorlar' vurgusu.",
     "{isim}, {randevu_sayisi}, {ciro}"),
    ("night_boomerang", "Gece · Geri Kazanım (Bumerang)", "22:00",
     "180+ gündür uğramayan en az 1 müşteri bugün geri dönmüş. 'Kayıp aşkını geri kazandın' tonu. "
     "{randevu_sayisi} = geri kazanılan müşteri sayısı.",
     "{isim}, {randevu_sayisi} (geri gelen), {ciro}"),
    ("night_revenue", "Gece · Ciro Günü", "22:00",
     "Ciro referansa göre +%20 ve üzeri. Para/başarı odaklı, coşkulu kutlama.",
     "{isim}, {ciro}, {randevu_sayisi}"),
    ("night_honest", "Gece · Dürüst/Sakin Gün", "22:00",
     "Sakin/düşük bir gün geçmiş. Suçlamadan, dürüst ama moral veren, yarına umut aşılayan ton.",
     "{isim}, {randevu_sayisi}, {ciro}"),
    ("weekly_record", "Haftalık · Rekor", "Pazar 22:00",
     "Haftalık ciro önceki 4 haftanın ortalamasına göre +%15 ve üzeri. CEO gururu, 'rekor kırdın' tonu.",
     "{isim}, {ciro}, {hizmet_adi}, {oran}"),
    ("weekly_normal", "Haftalık · Normal", "Pazar 22:00",
     "Haftalık ciro dengeli, belirgin sapma yok. İstikrar övgüsü + küçük bir ipucu.",
     "{isim}, {ciro}, {hizmet_adi}"),
    ("weekly_alarm", "Haftalık · Alarm", "Pazar 22:00",
     "Haftalık ciro ortalamaya göre -%15 ve altı. Panik yaratmadan, 'toparlanırız' diyen çözüm odaklı ton.",
     "{isim}, {ciro}, {hizmet_adi}, {oran}"),
]

PLACEHOLDERS = [
    ("{isim}", "Salon sahibinin adı (Güzellik Salonu profilinde İLK İSİM, ör. 'Gamze'). Boş olabilir; cümle onsuz da akmalı."),
    ("{randevu_sayisi}", "Senaryoya göre değişir: genelde günün toplam randevusu; night_growth'ta yeni müşteri; night_boomerang'ta geri kazanılan müşteri sayısı."),
    ("{ilk_randevu_saati}", "Günün ilk randevu saati, ör. '10:00'. Sabah senaryolarında kullanılır."),
    ("{ciro}", "Tutar (TL, binlik ayraçlı ör. '12.000'). Gece ve haftalık senaryolarda."),
    ("{hizmet_adi}", "Öne çıkan hizmet adı, ör. 'kalıcı oje'. Haftalık senaryolarda."),
    ("{oran}", "Yüzde değeri (ör. 22). Rekor/alarm senaryolarında kıyas için."),
    ("{bos_baslangic}", "Boşluğun başlangıç saati, ör. '12:20'. Gap senaryolarında."),
    ("{bos_bitis}", "Boşluğun bitiş saati, ör. '18:00'. Gap senaryolarında."),
]


class PDF(FPDF):
    def multi_cell(self, *args, **kwargs):
        kwargs.setdefault("new_x", XPos.LMARGIN)
        kwargs.setdefault("new_y", YPos.NEXT)
        return super().multi_cell(*args, **kwargs)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*MUTE)
        self.cell(0, 8, "PLANN Asistan · İçerik Yazarı Brief · Güzellik Salonu", align="L")
        self.cell(0, 8, f"Sayfa {self.page_no()}", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*MUTE)
        self.cell(0, 8, "PLANNAPP LTD · Gizli · Yalnızca içerik üretimi için", align="C")


def H1(pdf, text):
    pdf.set_font("DejaVu", "B", 17)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, text)
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, y, pdf.l_margin + 40, y)
    pdf.ln(4)


def H2(pdf, text):
    if pdf.get_y() > 245:
        pdf.add_page()
    pdf.set_font("DejaVu", "B", 12.5)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)


def body(pdf, text, size=10.5, color=INK, gap=5.5):
    pdf.set_font("DejaVu", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, gap, text)
    pdf.ln(1.5)


def bullet(pdf, label, text):
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 5.4, f"•  {label}")
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*MUTE)
    pdf.set_x(pdf.l_margin + 5)
    pdf.multi_cell(0, 5.2, text)
    pdf.ln(1)


def chip(pdf, text):
    pdf.set_font("DejaVu", "B", 9)
    w = pdf.get_string_width(text) + 8
    x, y = pdf.get_x(), pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_text_color(*INK)
    pdf.rect(x, y, w, 7, style="F")
    pdf.cell(w, 7, text, align="C")
    pdf.ln(9)


def main():
    variations = json.load(open(DATA))
    by_scn = {}
    for r in variations:
        by_scn.setdefault(r["scenario"], []).append(r)
    for k in by_scn:
        by_scn[k].sort(key=lambda r: r.get("variation_index", 0))

    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(18, 16, 18)
    pdf.add_font("DejaVu", "", f"{FONT_DIR}/DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", f"{FONT_DIR}/DejaVuSans-Bold.ttf")
    # Emoji fallback (monokrom) — DejaVu'da olmayan emoji glifleri için
    try:
        pdf.add_font("Symbola", "", "/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf")
        pdf.set_fallback_fonts(["Symbola"])
    except Exception as e:
        print("Emoji fallback yuklenemedi:", e)

    # ---------- KAPAK ----------
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("DejaVu", "B", 30)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 13, "PLANN Asistan")
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 9, "İçerik Yazarı Brief'i")
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 13)
    pdf.set_text_color(*MUTE)
    pdf.multi_cell(0, 7, "Güzellik Salonu profili (SINCERE_BEAUTY)\nDuolingo tarzı bildirim metinleri")
    pdf.ln(14)
    pdf.set_draw_color(*LINE); pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
    pdf.ln(6)
    body(pdf,
         "Bu doküman, PLANN uygulamasının 'Akıllı Asistan' bildirimlerini yazacak içerik yazarı "
         "için hazırlanmıştır. Amaç: Güzellik Salonu işletmelerine giden 12 senaryonun her biri için "
         "Duolingo tarzı (kısa, samimi, oyunbaz, motive edici) metin varyasyonları üretmek. "
         "Dokümanın sonunda hâlihazırda sistemde bulunan tüm mevcut varyasyonlar referans olarak yer alır.",
         size=11, gap=6)
    pdf.ln(2)
    body(pdf, "Hazırlayan: PLANN Ürün Ekibi    ·    Kapsam: 12 senaryo × hedef 10-15 varyasyon    ·    Dil: Türkçe",
         size=9.5, color=MUTE, gap=5.5)

    # ---------- 1. PROJE ----------
    pdf.add_page()
    H1(pdf, "1. Proje Nedir?")
    body(pdf,
         "PLANN; kuaför, güzellik salonu, klinik gibi işletmeler için randevu, müşteri yönetimi ve online "
         "ödeme sunan bir SaaS platformudur. 'PLANN Asistan' ise işletme sahibinin telefonuna, doğru zamanda "
         "kısa ve akıllı push bildirimleri gönderen dijital sağ koldur.")
    body(pdf,
         "Asistan, işletmenin randevu ve ciro verisini arka planda analiz eder; günün/haftanın durumuna göre "
         "bir 'senaryo' seçer ve o senaryoya uygun, kişiselleştirilmiş bir mesaj gönderir. Bildirime dokunulduğunda "
         "işletme sahibi doğrudan uygulama panosuna (Dashboard) gider.")

    H2(pdf, "Üç zaman dilimi (katman)")
    bullet(pdf, "Sabah Brifingi — 08:30",
           "Günü kapasiteye göre selamlar: yoğun mu, boşluk mu var? Sahibi güne hazırlar, aksiyona yönlendirir.")
    bullet(pdf, "Gece Kapanışı — 22:00 (Pzt-Cmt)",
           "Günün 'hikâyesini' anlatır: büyüme, sadakat, geri kazanım, ciro veya dürüst/sakin gün.")
    bullet(pdf, "Haftalık CEO Özeti — Pazar 22:00",
           "Haftanın trendini yorumlar: rekor, normal veya alarm. 'Neden' odaklı, stratejik bir üst bakış.")

    # ---------- 2. TON ----------
    pdf.add_page()
    H1(pdf, "2. Ton & Stil: 'Duolingo Tarzı'")
    body(pdf,
         "Metinler bir bildirimden çok, işletmeyi çok iyi tanıyan esprili bir arkadaşın attığı mesaj gibi olmalı. "
         "Duolingo'nun o meşhur push dilini hedefliyoruz: cesur, oyunbaz, hafif iğneleyici ama her zaman sevecen ve motive edici.")
    bullet(pdf, "Kısa ve vurucu", "Tek nefeste okunmalı. İdeal olarak 160 karakterin altında. Uzun paragraf YOK.")
    bullet(pdf, "Samimi ve kişisel", "Sahibe ismiyle ('Gamze', 'canım', 'kraliçe') hitap et. Sen dili kullan.")
    bullet(pdf, "Oyunbaz ve esprili", "Küçük bir şaka, abartı ya da tatlı bir sitem serbest. Sıkıcı/kurumsal DEĞİL.")
    bullet(pdf, "Motive edici", "Her mesaj bir enerji veya aksiyon bırakmalı: 'hadi', 'kalk', 'patlat', 'kutla'.")
    bullet(pdf, "Tek emoji, sonda", "Cümlenin sonunda 1 adet uygun emoji. Emoji yağmuru YOK.")
    bullet(pdf, "Güzellik sektörü dili", "Salon dünyasından kelimeler: koltuk, fön, oje, makas, story, kampanya, siftah.")

    H2(pdf, "Güzellik Salonu profili (SINCERE_BEAUTY) — özel not")
    body(pdf,
         "Bu profil kadın ağırlıklı, sıcak ve içten bir tona sahiptir. 'canım, tatlım, kraliçe, şekerim' gibi "
         "sevecen hitaplar bu profilin imzasıdır. Aynı metin havuzu Masaj/SPA için de kullanılır. "
         "Kuaför profilinden farkı: daha kadınsı, daha 'kız kıza' bir sohbet havası.")

    # ---------- 3. TEKNİK KURALLAR ----------
    pdf.add_page()
    H1(pdf, "3. Teknik Kurallar (ÇOK ÖNEMLİ)")
    bullet(pdf, "Değişkenler (placeholder)",
           "Metinlerde süslü parantezli değişkenler kullanılır; sistem bunları gerçek veriyle doldurur. "
           "Değişken adını AYNEN yaz: {isim} doğru, {İsim} veya {ad} YANLIŞ.")
    bullet(pdf, "Değişken olmadan da akmalı",
           "{isim} boş gelebilir. Cümle, isim gelmese de dilbilgisel olarak bozulmamalı.")
    bullet(pdf, "5 gün tekrar yok",
           "Sistem son 5 günde kullanılan metni tekrar seçmez. Bu yüzden her senaryo için BOL varyasyon şart "
           "(mevcut 10; hedef 10-15). Varyasyonlar birbirinin kopyası değil, gerçekten farklı olmalı.")
    bullet(pdf, "Başlık sabit", "Bildirim başlığı her zaman 'PLANN Asistan'. Sen sadece GÖVDE metnini yazıyorsun.")
    bullet(pdf, "Yasaklar",
           "Marka/rakip adı yok, yanıltıcı vaat yok, aşırı uzunluk yok, yanlış/uydurma placeholder yok, tıbbi iddia yok.")

    H2(pdf, "Kullanılabilir değişkenler")
    for name, desc in PLACEHOLDERS:
        bullet(pdf, name, desc)

    H2(pdf, "Teslim formatı")
    body(pdf,
         "Her senaryo için, senaryo kodunun altına numaralı liste halinde varyasyonları yaz. Örnek:")
    body(pdf,
         "morning_busy\n"
         "1) Günaydın kraliçe! Bugün {randevu_sayisi} randevun var, ilk misafir {ilk_randevu_saati}'de. Fönleri ısıt! 🔥\n"
         "2) ...",
         size=10, color=MUTE, gap=5.2)

    # ---------- 4. SENARYOLAR + MEVCUT VARYASYONLAR ----------
    pdf.add_page()
    H1(pdf, "4. Senaryolar ve Mevcut Varyasyonlar")
    body(pdf,
         "Aşağıda 12 senaryonun her biri için: ne zaman tetiklendiği, hangi değişkenlerin kullanılabileceği ve "
         "sistemde HÂLİHAZIRDA bulunan tüm mevcut varyasyonlar (referans) yer alır. Görevin: her senaryo için "
         "aynı ruhu koruyan, ama daha taze ve çeşitli yeni varyasyonlar üretmek (mevcutları iyileştirebilir/çoğaltabilirsin).",
         gap=5.8)
    pdf.ln(1)

    for idx, (code, title, when, trig, ph) in enumerate(SCENARIOS, 1):
        if pdf.get_y() > 235:
            pdf.add_page()
        # başlık kartı
        pdf.set_fill_color(*INK)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 12)
        pdf.multi_cell(0, 8, f"  {idx}. {title}", fill=True)
        pdf.ln(1)
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.set_text_color(*ACCENT)
        pdf.cell(0, 5.5, f"kod: {code}   ·   zaman: {when}")
        pdf.ln(6.5)
        pdf.set_font("DejaVu", "B", 9.5); pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5, "Ne zaman tetiklenir?")
        pdf.set_font("DejaVu", "", 9.5); pdf.set_text_color(*MUTE)
        pdf.multi_cell(0, 5, trig)
        pdf.ln(0.5)
        pdf.set_font("DejaVu", "B", 9.5); pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5, "Kullanılabilir değişkenler:")
        pdf.set_font("DejaVu", "", 9.5); pdf.set_text_color(*MUTE)
        pdf.multi_cell(0, 5, ph)
        pdf.ln(1)
        pdf.set_font("DejaVu", "B", 9.5); pdf.set_text_color(*INK)
        rows = by_scn.get(code, [])
        pdf.multi_cell(0, 5, f"Mevcut varyasyonlar ({len(rows)} adet):")
        pdf.ln(0.5)
        for i, r in enumerate(rows, 1):
            if pdf.get_y() > 262:
                pdf.add_page()
            pdf.set_font("DejaVu", "", 9.3)
            pdf.set_text_color(*INK)
            pdf.set_x(pdf.l_margin + 2)
            pdf.multi_cell(0, 4.8, f"{i}. {r.get('text','')}")
            pdf.ln(0.4)
        pdf.ln(4)

    # ---------- 5. ÖZET GÖREV ----------
    pdf.add_page()
    H1(pdf, "5. Özet: Senden İstenen")
    bullet(pdf, "12 senaryonun her biri için", "Güzellik Salonu (SINCERE_BEAUTY) tonunda, Duolingo tarzı 10-15 varyasyon yaz.")
    bullet(pdf, "Toplam hedef", "Yaklaşık 120-180 metin (12 senaryo × 10-15).")
    bullet(pdf, "Kurallara sadık kal", "Değişken adları aynen, tek emoji, kısa metin, 5 gün tekrar etmeyecek çeşitlilik.")
    bullet(pdf, "Dil", "Türkçe. (İngilizce sürüm ayrıca istenirse belirtilecek.)")
    bullet(pdf, "Teslim", "Senaryo kodu başlık, altında numaralı liste. Düz metin (.txt / .docx / Google Docs) yeterli.")
    pdf.ln(2)
    body(pdf,
         "Not: Yukarıdaki mevcut varyasyonlar sana ton ve uzunluk için pusuladır. Onları taklit et ama tekrarlama; "
         "amacımız daha zengin, daha taze ve daha 'Duolingo' bir havuz oluşturmak. İyi eğlenceler! ",
         gap=6)

    pdf.output(OUT)
    print("PDF olusturuldu:", OUT)
    print("Sayfa sayisi:", pdf.page_no())


if __name__ == "__main__":
    main()
