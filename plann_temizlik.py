import pandas as pd
import requests
import io
import re

# ==========================================
# ⚙️ AYARLAR
# ==========================================
JOB_ID = "d5dfdbb8-1171-4aaa-b880-e5533096d8b2" 

# Scraper'ın çalıştığı sunucunun IP adresi (PDF'ten alındı)
API_URL = f"http://46.225.238.228:8080/api/v1/jobs/{JOB_ID}/download"
OUTPUT_FILE = "ESKISEHIR.csv"

# Genişletilmiş Randevulu Sektörler
HEDEF_SEKTORLER = [
    "Salon", "Kuaför", "Berber", "Güzellik", "Lazer", "Epilasyon", 
    "Tırnak", "Nail", "Hair", "Cilt", "Bakım", "Tasarım", "Beauty", "Estetik",
    "Psikolog", "Psikolojik", "Terapi", "Danışmanlık", "Psikiyatri",
    "Diş", "Dent", "Ortodonti", "Klinik", "Poliklinik",
    "Dövme", "Tattoo", "Piercing", "Stüdyo",
    "Diyetisyen", "Beslenme", "Fizyoterapi", "Fizyoterapist", "Veteriner", "Pilates", "Yoga"
]

def numarayi_formatla(tel):
    """Cep ve Sabit Hatları standart formata (+90...) sokar."""
    tel = str(tel)
    tel = re.sub(r'[^\d]', '', tel)
    if not tel: return None

    if tel.startswith('90') and len(tel) >= 12: tel = '+' + tel
    elif tel.startswith('0'): tel = '+90' + tel[1:]
    else: tel = '+90' + tel
        
    return tel if len(tel) >= 10 else None

# ==========================================
# 🚀 UZAKTAN ÇEKİM VE TEMİZLİK
# ==========================================
print(f"📥 Veriler sunucudan çekiliyor: {API_URL}")

try:
    response = requests.get(API_URL)
    if response.status_code == 200:
        print("✅ Veri başarıyla indirildi. Temizlik motoru çalışıyor...\n")
        df = pd.read_csv(io.StringIO(response.text))
        
        print(f"📊 Toplam çekilen ham veri: {len(df)}")

        df['phone'] = df['phone'].apply(numarayi_formatla)
        df = df.dropna(subset=['phone'])

        filtre = df['category'].str.contains('|'.join(HEDEF_SEKTORLER), case=False, na=False)
        df_clean = df[filtre].copy()

        df_clean = df_clean.drop_duplicates(subset=['phone'])
        df_clean = df_clean[['title', 'phone']].rename(columns={'title': 'Isletme_Adi', 'phone': 'Telefon'})
        df_clean['Isletme_Adi'] = df_clean['Isletme_Adi'].astype(str).str.strip()

        df_clean.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        
        print(f"✅ İlgisiz dükkanlar elendi!")
        print(f"🎯 NET MÜŞTERİ SAYISI: {len(df_clean)}")
        print(f"📁 Dosyan hazır: {OUTPUT_FILE}")
    else:
        print(f"❌ API Hatası! Job ID doğru mu? (Kod: {response.status_code})")
except Exception as e:
    print(f"❌ Bağlantı hatası: {e}")