#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLANN Marketing PDF Generator"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Register Turkish-compatible fonts
pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))

# Colors
PRIMARY = colors.HexColor('#667eea')
PRIMARY_DARK = colors.HexColor('#764ba2')
SUCCESS = colors.HexColor('#27ae60')
DANGER = colors.HexColor('#e74c3c')
DARK = colors.HexColor('#1a1a2e')
LIGHT_BG = colors.HexColor('#f8f9fa')
WHATSAPP_GREEN = colors.HexColor('#25d366')

# Page setup
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2*cm

def create_styles():
    """Create custom paragraph styles"""
    styles = getSampleStyleSheet()
    
    # Title style (for cover)
    styles.add(ParagraphStyle(
        name='CoverTitle',
        fontSize=48,
        leading=56,
        alignment=TA_CENTER,
        textColor=colors.white,
        spaceAfter=20,
        fontName='DejaVu-Bold'
    ))
    
    # Tagline
    styles.add(ParagraphStyle(
        name='Tagline',
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.white,
        spaceAfter=30,
        fontName='DejaVu'
    ))
    
    # Subtitle
    styles.add(ParagraphStyle(
        name='Subtitle',
        fontSize=14,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#cccccc'),
        spaceAfter=40,
        fontName='DejaVu'
    ))
    
    # Section Title
    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontSize=24,
        leading=30,
        alignment=TA_LEFT,
        textColor=DARK,
        spaceBefore=20,
        spaceAfter=20,
        fontName='DejaVu-Bold'
    ))
    
    # Subsection Title
    styles.add(ParagraphStyle(
        name='SubsectionTitle',
        fontSize=16,
        leading=22,
        alignment=TA_LEFT,
        textColor=PRIMARY,
        spaceBefore=15,
        spaceAfter=10,
        fontName='DejaVu-Bold'
    ))
    
    # Problem Title (Red)
    styles.add(ParagraphStyle(
        name='ProblemTitle',
        fontSize=14,
        leading=20,
        alignment=TA_LEFT,
        textColor=DANGER,
        spaceBefore=15,
        spaceAfter=8,
        fontName='DejaVu-Bold'
    ))
    
    # Solution Title (Green)
    styles.add(ParagraphStyle(
        name='SolutionTitle',
        fontSize=14,
        leading=20,
        alignment=TA_LEFT,
        textColor=SUCCESS,
        spaceBefore=5,
        spaceAfter=8,
        fontName='DejaVu-Bold'
    ))
    
    # Body text
    styles.add(ParagraphStyle(
        name='CustomBody',
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        textColor=DARK,
        spaceAfter=12,
        fontName='DejaVu'
    ))
    
    # Feature item
    styles.add(ParagraphStyle(
        name='FeatureItem',
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        textColor=DARK,
        spaceBefore=4,
        spaceAfter=4,
        leftIndent=15,
        fontName='DejaVu'
    ))
    
    # Center text
    styles.add(ParagraphStyle(
        name='CenterText',
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=DARK,
        spaceAfter=10,
        fontName='DejaVu'
    ))
    
    # Big number
    styles.add(ParagraphStyle(
        name='BigNumber',
        fontSize=32,
        leading=40,
        alignment=TA_CENTER,
        textColor=colors.white,
        spaceAfter=10,
        fontName='DejaVu-Bold'
    ))
    
    # Campaign text
    styles.add(ParagraphStyle(
        name='CampaignText',
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.white,
        fontName='DejaVu'
    ))
    
    return styles

def add_cover_page(story, styles):
    """Add cover page"""
    # Add spacing to center content vertically
    story.append(Spacer(1, 6*cm))
    story.append(Paragraph("PLANN", styles['CoverTitle']))
    story.append(Paragraph("Randevu Yönetim Sistemi", styles['Tagline']))
    story.append(Paragraph(
        "Kuaförler, güzellik merkezleri, psikologlar, diyetisyenler,<br/>"
        "diş klinikleri, spa salonları ve randevu ile çalışan<br/>"
        "tüm işletmeler için yeni nesil çözüm.",
        styles['Subtitle']
    ))
    story.append(Spacer(1, 2*cm))
    
    # Badge
    badge_data = [["Yapay Zeka Destekli  •  WhatsApp Entegrasyonlu"]]
    badge_table = Table(badge_data, colWidths=[12*cm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('PADDING', (0, 0), (-1, -1), 15),
        ('ROUNDEDCORNERS', [10, 10, 10, 10]),
    ]))
    story.append(badge_table)
    story.append(PageBreak())

def add_problems_section(story, styles):
    """Add problems and solutions section"""
    story.append(Paragraph("Yaşadığınız Sorunları Biliyoruz", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    problems = [
        {
            "problem": '"Sürekli Telefon Çalıyor, İşime Odaklanamıyorum"',
            "desc": "Müşteri saç kestirirken telefonunuz çalıyor. Cevap veremeseniz müşteri gidiyor, cevap verseniz elinizdeki müşteriye haksızlık ediyorsunuz.",
            "solution": "Müşterileriniz 7/24 online randevu alır. Siz telefonla uğraşmak yerine işinize odaklanırsınız. Gece 2'de bile randevu alınabilir!"
        },
        {
            "problem": '"Randevular Çakışıyor, Müşteriler Bekliyor"',
            "desc": 'Telefonda "14:00\'a gel" dediniz, defterinize yazmayı unuttunuz. Aynı saate başka biri daha geldi. Profesyonelliğiniz zedeleniyor.',
            "solution": "Akıllı çakışma kontrolü sayesinde aynı personele aynı saate asla iki randevu alınamaz. Hizmet süreleri otomatik hesaplanır."
        },
        {
            "problem": '"Müşteriler Randevuyu Unutuyor, Gelmiyor"',
            "desc": "Randevu aldı, o gün başka işi çıktı, size haber vermeden gelmedi. Siz o saati boş beklediniz. Hem zaman hem para kaybı.",
            "solution": "Randevudan önce otomatik WhatsApp hatırlatması gider. Müşteri ya gelir ya iptal eder. Boş bekleme son bulur."
        },
        {
            "problem": '"Kağıt Defter Karmaşası"',
            "desc": "Defterde silinti, kazıntı, okunmayan yazılar... Hangi müşteri ne zaman gelmiş, kaç kez gelmiş - hiçbir fikriniz yok.",
            "solution": 'Tüm randevular dijital ortamda, aranabilir, filtrelenebilir. "Ahmet Bey" yazın, tüm geçmişi çıksın.'
        },
        {
            "problem": '"Profesyonel Görünmüyorum"',
            "desc": "Rekabette öne çıkmak zor. Büyük markalar uygulama kullanıyor, siz hala telefon ve defter.",
            "solution": "Kendi markanızla online randevu sayfası. Mobil uygulama olarak telefona yüklenebilir. WhatsApp'tan profesyonel bildirimler."
        },
    ]
    
    for p in problems:
        story.append(Paragraph(f"X {p['problem']}", styles['ProblemTitle']))
        story.append(Paragraph(p['desc'], styles['CustomBody']))
        story.append(Paragraph("PLANN Çözümü:", styles['SolutionTitle']))
        story.append(Paragraph(p['solution'], styles['CustomBody']))
        story.append(Spacer(1, 0.5*cm))
    
    story.append(Spacer(1, 1*cm))

def add_benefits_table(story, styles):
    """Add benefits comparison table"""
    story.append(Paragraph("PLANN ile Kazanacaklarınız", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    data = [
        ["Sorun", "PLANN Öncesi", "PLANN Sonrası"],
        ["Telefon Trafiği", "Günde 20+ arama", "Minimuma iner"],
        ["Randevu Çakışması", "Ayda 5-10 kriz", "Sıfır çakışma"],
        ["Unutulan Randevular", "%15-20 gelmeme", "%5'in altına düşer"],
        ["Müşteri Takibi", "Defter karıştırma", "Tek tıkla erişim"],
        ["Personel Takibi", "Manuel hesaplama", "Otomatik raporlama"],
        ["Profesyonellik", "Geleneksel görünüm", "Modern, dijital işletme"],
        ["Çalışma Saati", "Telefonla sınırlı", "7/24 randevu alımı"],
    ]
    
    table = Table(data, colWidths=[5*cm, 5*cm, 5*cm])
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (2, 1), (2, -1), SUCCESS),  # Green for solutions
        ('FONTNAME', (2, 1), (2, -1), 'DejaVu-Bold'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 10),
        # Alternating rows
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BG),
        ('BACKGROUND', (0, 3), (-1, 3), LIGHT_BG),
        ('BACKGROUND', (0, 5), (-1, 5), LIGHT_BG),
        ('BACKGROUND', (0, 7), (-1, 7), LIGHT_BG),
    ]))
    story.append(table)
    story.append(Spacer(1, 1*cm))

def add_ai_section(story, styles):
    """Add AI assistant section"""
    story.append(Paragraph("Yapay Zeka Asistanı", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    story.append(Paragraph(
        "PLANN'ın yapay zeka asistanı sayesinde sistemi <b>konuşarak veya yazarak</b> yönetebilirsiniz!",
        styles['CustomBody']
    ))
    
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Yapay Zeka ile Randevu Oluşturma", styles['SubsectionTitle']))
    
    # Chat example 1
    chat_data = [
        ["SİZ:", '"Yarın Ahmet Yılmaz için saat 10:00\'a traş randevusu oluştur"'],
        ["PLANN AI:", '"Tamam! Ahmet Yılmaz için yarın 10:00\'da traş randevusu oluşturdum. Müşteriye WhatsApp bildirimi gönderildi."'],
    ]
    chat_table = Table(chat_data, colWidths=[2.5*cm, 12.5*cm])
    chat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), PRIMARY),
        ('BACKGROUND', (0, 1), (0, 1), DARK),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        ('FONTNAME', (0, 0), (0, -1), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#e8e8ff')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#e8ffe8')),
    ]))
    story.append(chat_table)
    
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Yapay Zeka ile İşletme Analizi", styles['SubsectionTitle']))
    
    # Chat example 2
    chat_data2 = [
        ["SİZ:", '"Bu ay ne kadar kazandık?"'],
        ["PLANN AI:", '"Bu ay toplam 47.250 TL gelir elde ettiniz. Geçen aya göre %12 artış var. En yoğun gününüz Cumartesi oldu."'],
    ]
    chat_table2 = Table(chat_data2, colWidths=[2.5*cm, 12.5*cm])
    chat_table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), PRIMARY),
        ('BACKGROUND', (0, 1), (0, 1), DARK),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        ('FONTNAME', (0, 0), (0, -1), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#e8e8ff')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#e8ffe8')),
    ]))
    story.append(chat_table2)
    
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>Sorabilecekleriniz:</b>", styles['CustomBody']))
    questions = [
        "• En aktif personelim kim?",
        "• En çok hangi hizmeti verdik?",
        "• Hangi müşterim en çok geldi?",
        "• Personel bazında ciroları göster"
    ]
    for q in questions:
        story.append(Paragraph(q, styles['FeatureItem']))
    
    story.append(Spacer(1, 1*cm))

def add_whatsapp_section(story, styles):
    """Add WhatsApp section"""
    story.append(Paragraph("WhatsApp Bildirim Sistemi", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=WHATSAPP_GREEN, spaceAfter=20))
    
    story.append(Paragraph(
        "Müşterilerinizle en etkili iletişim kanalı olan WhatsApp üzerinden profesyonel bildirimler!",
        styles['CustomBody']
    ))
    
    # WhatsApp message example
    wa_data = [["""Randevunuz Onaylandı!

Sayın Ayşe Hanım,
Tarih: 15 Aralık 2024, Pazar
Saat: 14:00
Hizmet: Saç Kesimi + Fön
Yer: Güzellik Merkezi XYZ

Görüşmek üzere!"""]]
    
    wa_table = Table(wa_data, colWidths=[14*cm])
    wa_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#dcf8c6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#075e54')),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('PADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('BOX', (0, 0), (-1, -1), 3, WHATSAPP_GREEN),
    ]))
    story.append(wa_table)
    
    story.append(Spacer(1, 1*cm))
    
    # Advantages grid
    adv_data = [
        ["%98 Açılma Oranı", "Güvenilir"],
        ["SMS'in aksine neredeyse\ntüm mesajlar okunur", "Müşteriler WhatsApp'a\ndaha çok güvenir"],
        ["Ekonomik", "Anlık"],
        ["SMS maliyetlerinden\ntasarruf", "Saniyeler içinde ulaşır"],
    ]
    
    adv_table = Table(adv_data, colWidths=[7*cm, 7*cm])
    adv_table.setStyle(TableStyle([
        # All cells font
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        # Headers
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BG),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 2), (-1, 2), PRIMARY),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTNAME', (0, 2), (-1, 2), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 2), (-1, 2), 12),
        # Body
        ('FONTSIZE', (0, 1), (-1, 1), 10),
        ('FONTSIZE', (0, 3), (-1, 3), 10),
        ('TEXTCOLOR', (0, 1), (-1, 1), DARK),
        ('TEXTCOLOR', (0, 3), (-1, 3), DARK),
        # Layout
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee')),
    ]))
    story.append(adv_table)
    story.append(Spacer(1, 1*cm))

def add_sectors_section(story, styles):
    """Add sectors section"""
    story.append(Paragraph("Kimler İçin?", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    story.append(Paragraph(
        "PLANN, randevu sistemiyle çalışan her sektör için uygundur:",
        styles['CustomBody']
    ))
    
    sectors = [
        ["Kuaförler & Berberler", "Güzellik Merkezleri", "SPA & Masaj Salonları"],
        ["Psikologlar & Terapistler", "Diyetisyenler", "Diş Klinikleri"],
        ["Göz Doktorları", "Fizik Tedavi", "Veteriner Klinikleri"],
        ["Fotoğraf Stüdyoları", "Eğitim Merkezleri", "Araç Detailing"],
    ]
    
    sector_table = Table(sectors, colWidths=[5*cm, 5*cm, 5*cm])
    sector_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), PRIMARY),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 2, colors.white),
    ]))
    story.append(sector_table)
    story.append(Spacer(1, 1*cm))

def add_features_section(story, styles):
    """Add features section"""
    story.append(Paragraph("Öne Çıkan Özellikler", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    features = {
        "Randevu Yönetimi": [
            "Günlük, haftalık, aylık takvim görünümü",
            "Akıllı çakışma kontrolü - asla iki randevu çakışmaz",
            "Hizmet süresi otomatik hesaplama",
            "Randevu notları ve müşteri geçmişi",
            "Tek tıkla iptal ve WhatsApp bildirimi",
        ],
        "Personel Yönetimi": [
            "Sınırsız personel ekleme",
            "E-posta ile davet sistemi",
            "Personel bazlı hizmet atama",
            "Maaş veya komisyon hesaplama",
            "Personel mola yönetimi",
            "Performans takibi ve raporlama",
        ],
        "Finans Yönetimi": [
            "Günlük, haftalık, aylık gelir raporları",
            "Hizmet bazında analiz",
            "Gider takibi",
            "Personel bordrosu otomatik hesaplama",
            "Excel'e aktarma",
        ],
        "Müşteri Yönetimi": [
            "Otomatik müşteri kaydı",
            "Randevu geçmişi ve toplam harcama",
            "Müşteri notları (alerjiler, tercihler vb.)",
            "Arama ve filtreleme",
        ],
    }
    
    for title, items in features.items():
        story.append(Paragraph(title, styles['SubsectionTitle']))
        for item in items:
            story.append(Paragraph(f"✓ {item}", styles['FeatureItem']))
        story.append(Spacer(1, 0.3*cm))
    
    story.append(Spacer(1, 1*cm))

def add_howto_section(story, styles):
    """Add how to start section"""
    story.append(Paragraph("Nasıl Başlarım?", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    steps_data = [
        ["1", "2", "3", "4"],
        ["Kayıt Ol", "Hizmetleri Gir", "Personeli Ekle", "Linki Paylaş"],
        ["1 dakikada ücretsiz\nhesap oluştur", "Sunduğun\nhizmetleri tanımla", "Çalışanlarını\ndavet et", "Müşteriler\nrandevu alsın!"],
    ]
    
    steps_table = Table(steps_data, colWidths=[3.75*cm, 3.75*cm, 3.75*cm, 3.75*cm])
    steps_table.setStyle(TableStyle([
        # All cells font
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        # Numbers row
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 24),
        # Titles row
        ('FONTNAME', (0, 1), (-1, 1), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 12),
        ('TEXTCOLOR', (0, 1), (-1, 1), DARK),
        # Description row
        ('FONTSIZE', (0, 2), (-1, 2), 9),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#666666')),
        # Layout
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, 2), LIGHT_BG),
        ('GRID', (0, 0), (-1, -1), 2, colors.white),
    ]))
    story.append(steps_table)
    
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("<b>Kurulum Süresi: Sadece 10 Dakika!</b>", styles['CenterText']))
    story.append(Spacer(1, 1*cm))

def add_comparison_section(story, styles):
    """Add why PLANN section"""
    story.append(Paragraph("Neden PLANN?", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    data = [
        ["Özellik", "PLANN", "Diğerleri"],
        ["Yapay Zeka Asistanı", "VAR", "YOK"],
        ["WhatsApp Bildirimi", "VAR", "Çoğunda yok"],
        ["Türkçe Arayüz & Destek", "%100 Türkçe", "Çeviri hataları"],
        ["Mobil Uygulama", "Ücretsiz", "Ek ücret"],
        ["Personel Sayısı", "Sınırsız", "Kişi başı ücret"],
        ["Fiyat", "Uygun", "Pahalı"],
    ]
    
    table = Table(data, colWidths=[5*cm, 5*cm, 5*cm])
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        # PLANN column (green)
        ('TEXTCOLOR', (1, 1), (1, -1), SUCCESS),
        ('FONTNAME', (1, 1), (1, -1), 'DejaVu-Bold'),
        # Others column (gray/red)
        ('TEXTCOLOR', (2, 1), (2, -1), colors.HexColor('#888888')),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 10),
        # Alternating rows
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BG),
        ('BACKGROUND', (0, 4), (-1, 4), LIGHT_BG),
        ('BACKGROUND', (0, 6), (-1, 6), LIGHT_BG),
    ]))
    story.append(table)
    story.append(Spacer(1, 1*cm))

def add_faq_section(story, styles):
    """Add FAQ section"""
    story.append(Paragraph("Sıkça Sorulan Sorular", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    faqs = [
        {
            "q": '"Teknik bilgim yok, kullanabilir miyim?"',
            "a": "Evet! PLANN, teknik bilgi gerektirmeyecek şekilde tasarlandı. Telefon kullanabiliyorsanız PLANN'ı da kullanabilirsiniz. Üstelik yapay zeka asistanı ile konuşarak bile işlem yapabilirsiniz."
        },
        {
            "q": '"Müşteri bilgilerim güvende mi?"',
            "a": "Kesinlikle! SSL şifreleme ile tüm veriler korunur. KVKK uyumlu altyapı. Verileriniz sadece size aittir."
        },
        {
            "q": '"Kaç personel ekleyebilirim?"',
            "a": "Sınırsız! Tüm planlarda sınırsız personel ekleme hakkınız var."
        },
        {
            "q": '"İstediğim zaman iptal edebilir miyim?"',
            "a": "Evet! Taahhüt yok, istediğiniz zaman iptal edebilirsiniz."
        },
    ]
    
    for faq in faqs:
        story.append(Paragraph(faq['q'], styles['SubsectionTitle']))
        story.append(Paragraph(faq['a'], styles['CustomBody']))
        story.append(Spacer(1, 0.3*cm))
    
    story.append(Spacer(1, 1*cm))

def add_campaigns_section(story, styles):
    """Add campaigns section"""
    story.append(Paragraph("Özel Kampanyalar", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    # Campaign 1 - Welcome
    camp1_content = """<b>HOŞGELDİN KAMPANYASI</b><br/><br/>
<font size="24"><b>İLK AY %25 İNDİRİM!</b></font><br/><br/>
Yeni üyelere özel, ilk ay tüm planlarda geçerli"""
    camp1_data = [[Paragraph(camp1_content, ParagraphStyle('camp1', parent=styles['CenterText'], textColor=colors.white, fontSize=11))]]
    camp1_table = Table(camp1_data, colWidths=[14*cm], rowHeights=[3.5*cm])
    camp1_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ff6b6b')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(camp1_table)
    story.append(Spacer(1, 0.5*cm))
    
    # Campaign 2 - Annual
    camp2_content = """<b>YILLIK PLAN AVANTAJI</b><br/><br/>
<font size="24"><b>2 AY BEDAVA!</b></font><br/><br/>
12 ay yerine 10 ay öde, 12 ay kullan • %17 tasarruf"""
    camp2_data = [[Paragraph(camp2_content, ParagraphStyle('camp2', parent=styles['CenterText'], textColor=colors.white, fontSize=11))]]
    camp2_table = Table(camp2_data, colWidths=[14*cm], rowHeights=[3.5*cm])
    camp2_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SUCCESS),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(camp2_table)
    story.append(Spacer(1, 0.5*cm))
    
    # Campaign 3 - Trial
    camp3_content = """<b>RİSKSİZ DENEME</b><br/><br/>
<font size="24"><b>7 GÜN ÜCRETSİZ</b></font><br/><br/>
Kredi kartı gerekmez • Tüm özellikler açık • Beğenmezsen taahhüt yok"""
    camp3_data = [[Paragraph(camp3_content, ParagraphStyle('camp3', parent=styles['CenterText'], textColor=colors.white, fontSize=11))]]
    camp3_table = Table(camp3_data, colWidths=[14*cm], rowHeights=[3.5*cm])
    camp3_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(camp3_table)
    story.append(Spacer(1, 1*cm))

def add_cta_section(story, styles):
    """Add call to action and contact"""
    story.append(Spacer(1, 1*cm))
    
    # CTA Box
    cta_content = """<font size="24"><b>Hemen Başla!</b></font><br/><br/>
7 Gün Ücretsiz Dene + İlk Ay %25 İndirim!<br/><br/>
<font size="16"><b>plannapp.co</b></font>"""
    cta_data = [[Paragraph(cta_content, ParagraphStyle('cta', parent=styles['CenterText'], textColor=colors.white, fontSize=12))]]
    cta_table = Table(cta_data, colWidths=[14*cm], rowHeights=[4*cm])
    cta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(cta_table)
    
    story.append(Spacer(1, 1*cm))
    
    # Contact info
    story.append(Paragraph("İletişim", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=20))
    
    contact_data = [
        ["Web", "E-posta", "Telefon"],
        ["plannapp.co", "info@plannapp.co", "0XXX XXX XX XX"],
    ]
    contact_table = Table(contact_data, colWidths=[5*cm, 5*cm, 5*cm])
    contact_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('TEXTCOLOR', (0, 0), (-1, 0), PRIMARY),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(contact_table)
    
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        '<i>"İşinize odaklanın, randevuları PLANN yönetsin."</i>',
        styles['CenterText']
    ))

def on_first_page(canvas, doc):
    """Draw black background on cover page with decorative elements"""
    canvas.saveState()
    
    # Black background
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True)
    
    # Gradient-like decorative bars at top
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_HEIGHT - 0.8*cm, PAGE_WIDTH, 0.8*cm, fill=True, stroke=False)
    canvas.setFillColor(PRIMARY_DARK)
    canvas.rect(0, PAGE_HEIGHT - 1.2*cm, PAGE_WIDTH, 0.4*cm, fill=True, stroke=False)
    
    # Bottom decorative element
    canvas.setFillColor(colors.HexColor('#1a1a2e'))
    canvas.rect(0, 0, PAGE_WIDTH, 2*cm, fill=True, stroke=False)
    
    # Website at bottom
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.setFont('DejaVu', 10)
    canvas.drawCentredString(PAGE_WIDTH/2, 0.8*cm, "plannapp.co")
    
    # Corner accents
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(3)
    # Top left corner
    canvas.line(1*cm, PAGE_HEIGHT - 2*cm, 1*cm, PAGE_HEIGHT - 4*cm)
    canvas.line(1*cm, PAGE_HEIGHT - 2*cm, 3*cm, PAGE_HEIGHT - 2*cm)
    # Bottom right corner
    canvas.line(PAGE_WIDTH - 1*cm, 3*cm, PAGE_WIDTH - 1*cm, 5*cm)
    canvas.line(PAGE_WIDTH - 1*cm, 3*cm, PAGE_WIDTH - 3*cm, 3*cm)
    
    canvas.restoreState()

def on_later_pages(canvas, doc):
    """Header/footer for other pages"""
    canvas.saveState()
    
    # Top header line
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(2)
    canvas.line(MARGIN, PAGE_HEIGHT - 1.5*cm, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 1.5*cm)
    
    # Header text
    canvas.setFillColor(PRIMARY)
    canvas.setFont('DejaVu-Bold', 11)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 1.2*cm, "PLANN")
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.setFont('DejaVu', 9)
    canvas.drawString(MARGIN + 1.5*cm, PAGE_HEIGHT - 1.2*cm, "Randevu Yönetim Sistemi")
    
    # Bottom footer line
    canvas.setStrokeColor(colors.HexColor('#dddddd'))
    canvas.setLineWidth(1)
    canvas.line(MARGIN, 1.8*cm, PAGE_WIDTH - MARGIN, 1.8*cm)
    
    # Footer left - website
    canvas.setFillColor(PRIMARY)
    canvas.setFont('DejaVu', 9)
    canvas.drawString(MARGIN, 1*cm, "plannapp.co")
    
    # Footer center - tagline
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.setFont('DejaVu', 8)
    canvas.drawCentredString(PAGE_WIDTH/2, 1*cm, "İşinize odaklanın, randevuları PLANN yönetsin.")
    
    # Footer right - page number
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.setFont('DejaVu', 9)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 1*cm, f"Sayfa {doc.page}")
    
    # Decorative corner accent (bottom right)
    canvas.setFillColor(colors.HexColor('#f0f0ff'))
    canvas.rect(PAGE_WIDTH - 3*cm, 0, 3*cm, 0.5*cm, fill=True, stroke=False)
    canvas.setFillColor(PRIMARY)
    canvas.rect(PAGE_WIDTH - 3*cm, 0.5*cm, 3*cm, 0.1*cm, fill=True, stroke=False)
    
    canvas.restoreState()

def generate_pdf():
    """Main function to generate PDF"""
    output_file = "/var/www/royalpremiumcare_dev/PLANN_OZELLIKLER.pdf"
    
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    styles = create_styles()
    story = []
    
    # Build document
    add_cover_page(story, styles)
    add_problems_section(story, styles)
    add_benefits_table(story, styles)
    add_ai_section(story, styles)
    add_whatsapp_section(story, styles)
    add_sectors_section(story, styles)
    add_features_section(story, styles)
    add_howto_section(story, styles)
    add_comparison_section(story, styles)
    add_faq_section(story, styles)
    add_campaigns_section(story, styles)
    add_cta_section(story, styles)
    
    # Generate PDF
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    print(f"PDF olusturuldu: {output_file}")

if __name__ == "__main__":
    generate_pdf()
