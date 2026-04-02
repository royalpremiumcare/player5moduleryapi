from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


# =========================================================
# AYARLAR
# =========================================================
@dataclass(frozen=True)
class Config:
    job_id: str = "0f58a60d-dd41-477a-b66d-aef9100125cd"
    api_base_url: str = "http://46.225.238.228:8080/api/v1/jobs"
    output_file: Path = Path("İstanbul_Anadolu.csv")
    removed_file: Path = Path("silinen_kayitlar.csv")
    timeout_seconds: int = 60


# HEDEF KELİMELER 
TARGET_KEYWORDS = [
    "salon", "kuafor", "berber", "barber", "guzellik", "lazer", "epilasyon",
    "tirnak", "nail", "hair", "cilt", "bakim", "tasarim", "beauty", "estetik",
    "aesthetic", "coiffeur", "makyaj", "makeup", "friseur", "hairdresser", "kisisel bakim",
    "psikolog", "psikolojik", "terapi", "danismanlik", "psikiyatri",
    "disci", "dis hekim", "dis klinik", "dis poliklinik", "agiz ve dis", "ortodonti", "klinik", "poliklinik", "smile",
    "medical", "clinic", "hekim", "doktor", "saglik",
    "dovme", "tattoo", "piercing", "studio",
    "diyetisyen", "beslenme", "fizyoterapi", "fizyoterapist", "fizik tedavi",
    "veteriner", "pilates", "yoga"
]

# YASAKLI KELİMELER 
BANNED_KEYWORDS = [
    "hastanesi", "hastane", "tip merkezi", "belediyesi", "belediye", "dernegi", "enstitusu", "vakfi", "universitesi", "havalimani", "eczane", "vakif", "muhtarlik", "saglik ocagi",
    "otobus duragi", "durak", "metro", "istasyon", "taksi", "otogar",
    "gratis", "watsons", "rossmann", "eveshop", "kozmetik magaza", "supermarket", "bakkal", "firin", "pastane", "manav", "kasap", "tekel", "avm", "alisveris", "market", "bebek magaza", "bebek giyim", "optik", "optisyen", "gozlukcu", "kuyumcu", "giyim", "butik", "ayakkabi", "canta", "kirtasiye", "tuhafiye", "zuccaciye", "oyuncak", "kiosk", "bufe",
    "oto ", "oto kuafor", "otomotiv", "motor", "sanayi", "tamir", "yikama", "lastik", "galeri", "rent a car", "otopark",
    "restoran", "lokanta", "kafe", "cafe", "pide", "kebap", "doner", "burger", "pizza", "cigkofte", "paket yemek", "catering", "meyhane", "bar ", "kahvehane", "cay bahcesi",
    "is ortakligi", "is merkezi", "insaat", "emlak", "gayrimenkul", "mimar", "mobilya", "dekorasyon", "elektrik", "tesisat", "hirdavat", "fotograf", "dugun", "organizasyon", "hukuk", "avukat", "muhasebe", "sigorta", "turizm", "seyahat", "bilet", "kargo", "kurye", "matbaa", "reklam", "ajans", "nakliyat", "lojistik",
    "okul", "kolej", "dershane", "kurs", "kres", "anaokulu", "surucu kursu", "psikoteknik"
]

# =========================================================
# YENİ: OTOMATİK SEKTÖR SINIFLANDIRICI
# =========================================================
# Dikkat: Sıralama önemlidir! "Güzellik Salonu" kelimesinde hem "güzellik" hem "salon" vardır.
# Güzellik daha üstte olduğu için onu "Güzellik" kategorisine atacaktır.
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

def assign_clean_sector(normalized_text: str) -> str:
    """Verilen metni tarar ve en uygun ana sektörü bulur."""
    for sector_name, keywords in SECTOR_GROUPS.items():
        if any(kw in normalized_text for kw in keywords):
            return sector_name
    return "Diğer (Sağlık & Bakım)"


# =========================================================
# NORMALİZASYON
# =========================================================
TR_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})

def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).translate(TR_TRANSLATION).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def compile_pattern(keywords: list[str]) -> re.Pattern:
    escaped = sorted((re.escape(k) for k in keywords), key=len, reverse=True)
    return re.compile("(?:" + "|".join(escaped) + ")", flags=re.IGNORECASE)

def normalize_phone(phone: object) -> Optional[str]:
    if pd.isna(phone):
        return None
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return None
    if digits.startswith("90") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 11:
        return "+90" + digits[1:]
    if len(digits) == 10 and digits.startswith("5"):
        return "+90" + digits
    return None

def add_reason(df: pd.DataFrame, mask: pd.Series, reason: str) -> None:
    df.loc[mask, "Silinme_Nedeni"] = df.loc[mask, "Silinme_Nedeni"] + reason + ";"


# =========================================================
# ANA AKIŞ
# =========================================================
def main():
    config = Config()
    api_url = f"{config.api_base_url}/{config.job_id}/download"

    print(f"📥 Veriler sunucudan çekiliyor: {api_url}")

    try:
        response = requests.get(api_url, timeout=config.timeout_seconds)
        response.raise_for_status()
        response.encoding = 'utf-8'

        print("✅ Veri başarıyla indirildi. Temizlik motoru çalışıyor...\n")

        df = pd.read_csv(io.StringIO(response.text))
        print(f"📊 Toplam ham veri: {len(df)}")

        required_columns = {"title", "phone", "category"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(f"Eksik kolon(lar): {sorted(missing)}")

        work = df.copy()

        work["title"] = work["title"].fillna("").astype(str).str.strip()
        work["category"] = work["category"].fillna("").astype(str).str.strip()
        work["title_norm"] = work["title"].apply(normalize_text)
        work["category_norm"] = work["category"].apply(normalize_text)

        work["phone_raw"] = work["phone"]
        work["phone"] = work["phone"].apply(normalize_phone)
        work["phone_valid"] = work["phone"].notna()

        target_regex = compile_pattern(TARGET_KEYWORDS)
        banned_regex = compile_pattern(BANNED_KEYWORDS)

        combined_norm = (work["title_norm"] + " " + work["category_norm"]).str.strip()

        work["target_match"] = combined_norm.str.contains(target_regex, na=False)
        work["banned_match"] = combined_norm.str.contains(banned_regex, na=False)

        # Yeni Sistem: Temiz Sektör Ataması
        work["Temiz_Sektor"] = combined_norm.apply(assign_clean_sector)

        work["Silinme_Nedeni"] = ""
        add_reason(work, ~work["phone_valid"], "gecersiz_telefon")
        add_reason(work, work["phone_valid"] & ~work["target_match"], "hedef_eslesmedi")
        add_reason(work, work["phone_valid"] & work["target_match"] & work["banned_match"], "yasakli_kelime")

        candidate_mask = work["Silinme_Nedeni"] == ""
        candidate_idx = work.loc[candidate_mask].index
        dup_mask = work.loc[candidate_idx].duplicated(subset=["phone"], keep="first")
        dup_idx = candidate_idx[dup_mask]
        work.loc[dup_idx, "duplicate_phone"] = True
        work["duplicate_phone"] = work["duplicate_phone"].fillna(False)
        add_reason(work, work["duplicate_phone"], "duplicate_phone")

        cleaned = work[work["Silinme_Nedeni"] == ""].copy()
        
        # Artık Google'ın ham kategorisi yerine kendi bulduğumuz temiz sektörü basıyoruz!
        cleaned = cleaned[["title", "phone", "Temiz_Sektor"]].rename(
            columns={"title": "Isletme_Adi", "phone": "Telefon", "Temiz_Sektor": "Sektor"}
        )
        
        cleaned["Isletme_Adi"] = cleaned["Isletme_Adi"].astype(str).str.strip()
        cleaned.to_csv(config.output_file, index=False, encoding="utf-8-sig")

        removed = work[work["Silinme_Nedeni"] != ""].copy()
        removed["Silinme_Nedeni"] = removed["Silinme_Nedeni"].str.rstrip(";")

        removed = removed[[
            "title", "phone_raw", "phone", "category",
            "phone_valid", "target_match", "banned_match", "duplicate_phone", "Silinme_Nedeni"
        ]].rename(columns={
            "title": "Isletme_Adi",
            "phone_raw": "Telefon_Raw",
            "phone": "Telefon_Normalize",
            "category": "Google_Kategorisi",
            "phone_valid": "Telefon_Gecerli",
            "target_match": "Hedef_Eslesti",
            "banned_match": "Yasakli_Eslesti",
            "duplicate_phone": "Ayni_Telefon_Mu",
        })

        removed.to_csv(config.removed_file, index=False, encoding="utf-8-sig")

        total_raw = len(work)
        total_clean = len(cleaned)
        total_removed = len(removed)

        print("✅ Temizlik tamamlandı!")
        print(f"🎯 NET MÜŞTERİ SAYISI: {total_clean}")
        print(f"📁 Temiz dosya: {config.output_file}")
        print("\nArtık çıktı dosyanızdaki 'Sektor' sütunu kusursuz bir şekilde sınıflandırıldı!")

    except requests.RequestException as e:
        print(f"❌ Bağlantı hatası: {e}")
    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    main()