import pandas as pd

# Dosya artık VS Code'da gördüğün klasörde
INPUT_FILE = "ankara_ham.csv"
OUTPUT_FILE = "ankara_nokta_atisi.csv"

# PLANN için hedef sektörler
HEDEF_SEKTORLER = [
    "Salon", "Kuaför", "Berber", "Güzellik", "Lazer", "Epilasyon", 
    "Tırnak", "Nail", "Hair", "Cilt", "Bakım", "Tasarım", "Beauty","Estetik"
]

try:
    df = pd.read_csv(INPUT_FILE)
    print(f"Toplam çekilen ham veri: {len(df)}")

    # 1. Telefonu olmayanları temizle
    df = df.dropna(subset=['phone'])
    df = df[df['phone'].astype(str).str.contains(r'\d', na=False)] 

    # 2. Sektör Filtreleme
    # Scraper 33+ veri noktası çeker, 'category' bunlardan biridir
    filtre = df['category'].str.contains('|'.join(HEDEF_SEKTORLER), case=False, na=False)
    df_clean = df[filtre].copy()

    # 3. Aynı işletmeleri (telefon bazlı) tekilleştir
    df_clean = df_clean.drop_duplicates(subset=['phone'])

    # Sonucu Kaydet
    df_clean.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Temizlik Bitti! {len(df_clean)} adet gerçek salon ayrıldı.")
    print(f"📁 Yeni dosyan: {OUTPUT_FILE}")

except Exception as e:
    print(f"Hata: {e}")
