import pandas as pd
from pathlib import Path
import warnings
import re
import unicodedata

# Uyarıları gizle
warnings.filterwarnings("ignore")

ESKI_KLASOR = Path("/var/www/player5moduleryapi/eski_datalar")
YENI_KLASOR = Path("/var/www/player5moduleryapi/yeni_datalar")
CIKTI_KLASOR = Path("/var/www/player5moduleryapi/Pazarlama_Dosyalari")

# =========================================================
# SEKTÖR DÜZELTİCİ MOTOR (Kategorileri standart yapar)
# =========================================================
SECTOR_GROUPS = {
    "Diş Kliniği": ["dis", "dent", "ortodonti", "smile"],
    "Psikolog / Terapist": ["psikolog", "psikolojik", "terapi", "psikiyatri", "danismanlik"],
    "Diyetisyen": ["diyet", "beslenme", "nutrition"],
    "Dövme & Piercing": ["dovme", "tattoo", "piercing"],
    "Fizyoterapi": ["fizyoterapi", "fizyoterapist", "fizik tedavi"],
    "Veteriner": ["veteriner"],
    "Pilates / Yoga": ["pilates", "yoga"],
    "Güzellik Salonu": ["guzellik", "lazer", "epilasyon", "tirnak", "nail", "cilt", "estetik", "beauty", "aesthetic", "makyaj", "makeup"],
    "Kuaför / Berber": ["kuafor", "berber", "barber", "coiffeur", "hair", "sac", "salon"]
}

TR_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})

def normalize_text(value: object) -> str:
    if pd.isna(value): return ""
    text = str(value).translate(TR_TRANSLATION).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def assign_clean_sector(row) -> str:
    isletme_adi = str(row.get("Isletme_Adi", ""))
    eski_sektor = str(row.get("Sektor", ""))
    combined_norm = normalize_text(isletme_adi) + " " + normalize_text(eski_sektor)
    for sector_name, keywords in SECTOR_GROUPS.items():
        if any(kw in combined_norm for kw in keywords):
            return sector_name
    return "Diğer (Sağlık & Bakım)"

# =========================================================
# TELEFON STANDARTLAŞTIRMA
# =========================================================
def fix_phone(p):
    if pd.isna(p): return ""
    p = str(p).strip()
    digits = ''.join(filter(str.isdigit, p))
    if not digits: return ""
    if digits.startswith("90") and len(digits) == 12: return "+" + digits
    if digits.startswith("0") and len(digits) == 11: return "+90" + digits[1:]
    if len(digits) == 10 and digits.startswith("5"): return "+90" + digits
    return p

# =========================================================
# BÖLGE TESPİT EDİCİ (GÜNCELLENDİ)
# =========================================================
def get_bolge(dosya_adi):
    """Dosya isminden şehri otomatik algılar. Kaç part olduğu fark etmez."""
    cevirici = str.maketrans("IİıiÇçŞşĞğÖöÜü", "iiiiccssggoouu")
    ad = str(dosya_adi).translate(cevirici).lower()
    
    if "avrupa" in ad: return "Istanbul_Avrupa"
    if "anadolu" in ad: return "Istanbul_Anadolu"
    if "izmir" in ad: return "Izmir"
    if "ankara" in ad: return "Ankara"
    if "konya" in ad: return "Konya" # Konya desteği eklendi
    
    # Eğer listede yoksa, dosya adının ilk kelimesini şehir kabul et
    return "Diger_" + ad.split('_')[0].capitalize()

def klasorden_veri_yukle(klasor_yolu: Path):
    dfs = []
    if not klasor_yolu.exists():
        klasor_yolu.mkdir(parents=True, exist_ok=True)
        return pd.DataFrame()
    
    for dosya in klasor_yolu.glob("*.csv"):
        try:
            df = pd.read_csv(dosya, dtype=str)
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            
            col_map = {
                "title": "Isletme_Adi",
                "phone": "Telefon",
                "Telefon_Normalize": "Telefon",
                "category": "Sektor",
                "Kategori": "Sektor"
            }
            df.rename(columns=col_map, inplace=True)
            
            for col in ["Isletme_Adi", "Telefon", "Sektor"]:
                if col not in df.columns: df[col] = ""
                    
            df["Sehir_Bolge"] = get_bolge(dosya.name)
            df = df[["Sehir_Bolge", "Isletme_Adi", "Telefon", "Sektor"]]
            df["Telefon"] = df["Telefon"].apply(fix_phone)
            df["Sektor"] = df.apply(assign_clean_sector, axis=1)
            
            dfs.append(df)
            print(f"  ✓ {dosya.name} okundu -> [{get_bolge(dosya.name)}]")
        except Exception as e:
            print(f"  ❌ {dosya.name} okunamadı: {e}")
            
    if dfs: return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

def main():
    print("="*60)
    print("🔄 BÖLGESEL PARÇALAYICI & OTOMATİK SEKTÖR DÜZELTİCİ")
    print("="*60)
    
    print("\n[1] Yeni Datalar Yükleniyor (Partlar dahil)...")
    df_yeni = klasorden_veri_yukle(YENI_KLASOR)
    
    print("\n[2] Eski Datalar Yükleniyor...")
    df_eski = klasorden_veri_yukle(ESKI_KLASOR)
    
    df_master = pd.concat([df_yeni, df_eski], ignore_index=True)
    
    if df_master.empty:
        print("\n⚠️ İşlenecek veri bulunamadı!")
        return

    toplam_satir = len(df_master)
    df_master = df_master[df_master["Telefon"] != ""]
    
    # Mükerrerleri sil (Part 1 ve Part 2 arasındaki aynı numaralar burada elenir)
    df_master.drop_duplicates(subset=["Telefon"], keep="first", inplace=True)
    
    net_satir = len(df_master)
    print(f"\n📊 Toplam Satır: {toplam_satir} | Eşsiz Müşteri: {net_satir}\n")
    
    CIKTI_KLASOR.mkdir(parents=True, exist_ok=True)
    
    print("📂 ŞEHİRLERE GÖRE TEMİZ DOSYALAR OLUŞTURULUYOR:")
    for sehir, df_sehir in df_master.groupby("Sehir_Bolge"):
        dosya_adi = CIKTI_KLASOR / f"Temiz_Data_{sehir}.csv"
        df_ihrac = df_sehir[["Isletme_Adi", "Telefon", "Sektor"]]
        df_ihrac.to_csv(dosya_adi, index=False, encoding="utf-8-sig")
        print(f"  -> 📌 {sehir}: {len(df_ihrac)} benzersiz kayıt ({dosya_adi.name})")

    print("\n" + "="*60)
    print("✅ TÜM PARTLAR BİRLEŞTİRİLDİ VE TEMİZLENDİ!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()