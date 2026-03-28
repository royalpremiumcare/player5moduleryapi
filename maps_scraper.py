from serpapi import GoogleSearch
import pandas as pd
import time
import re
import urllib.parse 

# --- AYARLAR ---
API_KEY = "84c9c70b01568faeb3fc1e9e75cb3a5d6f2c9cfe581b8b8259e9e6e322ba72e0" 

KEYWORDS = [
    "Güzellik Salonu", 
    "Bayan Kuaförü", 
    "Berber", 
    "Erkek Kuaförü", 
    "Lazer Epilasyon", 
    "Protez Tırnak", 
    "Gelin Başı", 
    "Cilt Bakımı",
    "Hair",
    "Saç Tasarım",
    "Nail",
    "Beauty",
]

# --- İZMİR GRID (IZGARA) AYARLARI ---
LAT_START = 37.632 # Güney
LAT_END = 39.641   # Kuzey
LNG_START = 25.956 # Batı
LNG_END = 28.796   # Doğu
STEP = 0.15        # Izgara adım büyüklüğü

# --- WHATSAPP MESAJI ---
WA_MESSAGE = (
    "Merhaba, iyi çalışmalar. Sayfanızı ve yaptığınız işlemleri bir süredir inceliyorum, gerçekten bölgenizde çok profesyonel bir iş çıkarıyorsunuz, tebrik ederim.\n\n"
    "Sizin gibi yoğun çalışan salonların tek bir düşmanı vardır: Randevu takibinin yarattığı karmaşa ve gelmeyen müşterilerin yarattığı ciro kaybı. PLANN olarak geliştirdiğimiz sistem, otomatik Whatsapp hatırlatmalarıyla randevu firelerinizi sıfıra indiriyor.\n\n"
    "Sizin kalibrenizdeki bir salonun bu operasyonu defterle veya karmaşık sistemlerle yürütmesi yerine, 7 günlük ücretsiz bir test ile bizim sistemimizin hızını denemesini çok isteriz. Gelmeyen 2 müşteriyi dükkana soktuğunda sistem zaten kendini amorti ediyor. İlgilenirseniz detaylı bilgi paylaşabilirim."
)
ENCODED_MESSAGE = urllib.parse.quote(WA_MESSAGE)

NEGATIVE_KEYWORDS = ["Avukat", "Hukuk", "Eczane", "Hastane", "Market", "Diyaliz", "Sağlık", "Veteriner"]

def clean_phone_for_display(phone_raw):
    if not phone_raw: return None
    clean = re.sub(r'\D', '', str(phone_raw))
    if clean.startswith('90'): clean = clean[2:]
    if clean.startswith('0'): clean = clean[1:]
    return clean

def format_phone_for_wa(phone_clean):
    if not phone_clean: return None
    return f"90{phone_clean}"

def classify_lead(phone_clean, website):
    if not phone_clean: return "İletişim Yok", "4_YOK"
    
    if phone_clean.startswith('5'): status_score = "1_CEP"
    elif phone_clean.startswith('444'): status_score = "3_KURUMSAL"
    else: status_score = "2_SABIT"

    if pd.isna(website) or website == "": 
        web_score = "FIRSAT"
    else: 
        web_score = "Sitesi Var"
        
    display_text = f"{status_score.split('_')[1]} - {web_score}"
    return display_text, status_score

def fetch_izmir_leads_unlimited(api_key, query, coords):
    leads = []
    start = 0 
    print(f"\n🔎 {coords} koordinatında '{query}' tüm sonuçlar taranıyor...")

    while True: # Sınırsız döngü (Sonuç bitene kadar)
        params = {
            "engine": "google_maps", "q": query, "ll": coords, 
            "type": "search", "start": start, "api_key": api_key, "hl": "tr"
        }

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            local_results = results.get("local_results", [])
            
            # Google daha fazla sonuç vermiyorsa bu harita karesinden çık
            if not local_results: 
                break

            for result in local_results:
                title = result.get("title", "")
                if any(neg_word.lower() in title.lower() for neg_word in NEGATIVE_KEYWORDS): continue

                phone_raw = result.get("phone")
                phone_display = clean_phone_for_display(phone_raw)
                website = result.get("website")
                
                if phone_display:
                    wa_number = format_phone_for_wa(phone_display)
                    if phone_display.startswith('5'):
                        full_url = f"https://wa.me/{wa_number}?text={ENCODED_MESSAGE}"
                    else:
                        full_url = ""

                    display_status, sort_score = classify_lead(phone_display, website)

                    place_data = {
                        "Siralama_Kategorisi": query,
                        "Isletme_Adi": title,
                        "Lead_Durumu": display_status,
                        "Lead_Puani": sort_score,
                        "Telefon": phone_display,
                        "WhatsApp_URL": full_url,
                        "Web_Sitesi": website,
                        "Adres": result.get("address")
                    }
                    leads.append(place_data)
            
            print(f"   ⏳ {start} - {start+20} arası tarandı. Toplam toplanan: {len(leads)}")
            start += 20 
            time.sleep(1)
            
        except Exception as e:
            print(f"Hata: {e}")
            break
    return leads

# --- ANA İŞLEM (GRID DÖNGÜSÜ) ---
all_leads = []
print("🚀 İzmir PLANN Sınırsız Grid Operasyonu Başlıyor...")

for keyword in KEYWORDS:
    print(f"\n=====================================")
    print(f"🚀 SEKTÖR BAŞLIYOR: {keyword}")
    print(f"=====================================")
    
    lat = LAT_START
    while lat <= LAT_END:
        lng = LNG_START
        while lng <= LNG_END:
            current_coords = f"@{lat:.4f},{lng:.4f},14z"
            
            data = fetch_izmir_leads_unlimited(API_KEY, keyword, current_coords)
            all_leads.extend(data)
            time.sleep(1) 
            
            lng += STEP
        lat += STEP

# --- KAYDETME VE TEMİZLİK ---
if all_leads:
    df = pd.DataFrame(all_leads)
    
    baslangic_sayisi = len(df)
    df = df.drop_duplicates(subset=['Telefon'], keep='first')
    bitis_sayisi = len(df)
    print(f"\n🧹 Toplam {baslangic_sayisi - bitis_sayisi} mükerrer kayıt temizlendi.")

    df['Siralama_Kategorisi'] = pd.Categorical(df['Siralama_Kategorisi'], categories=KEYWORDS, ordered=True)
    df = df.sort_values(by=['Siralama_Kategorisi', 'Lead_Puani'], ascending=[True, True])
    df = df.drop(columns=['Lead_Puani'])
    
    filename = "Izmir_PLANN_Sinirsiz_Final.xlsx"
    
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
        
        workbook = writer.book
        worksheet = writer.sheets['Leads']
        
        link_format = workbook.add_format({
            'font_color': 'blue',
            'underline': 1,
            'bold': True
        })
        
        worksheet.set_column('A:A', 20) 
        worksheet.set_column('B:B', 30) 
        worksheet.set_column('C:C', 20) 
        worksheet.set_column('D:D', 15) 
        worksheet.set_column('E:E', 25) 
        worksheet.set_column('F:F', 30) 
        worksheet.set_column('G:G', 50) 
        
        url_col_index = df.columns.get_loc("WhatsApp_URL")
        
        for row_num, url in enumerate(df['WhatsApp_URL']):
            if url and str(url).startswith('http'):
                worksheet.write_url(row_num + 1, url_col_index, url, link_format, string="💬 MESAJ GÖNDER")
            elif not url:
                 worksheet.write_string(row_num + 1, url_col_index, "Sabit Hat")

    print(f"\n🎯 İŞLEM TAMAM! Benzersiz işletmeler '{filename}' dosyasına kaydedildi.")

else:
    print("❌ Veri bulunamadı.")