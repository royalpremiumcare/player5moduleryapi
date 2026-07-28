"""
PLANN Asistan — Senaryo tanımları, profil eşleme ve karar eşikleri.

Bu modül Analytics/Health/Notification motorlarının paylaştığı SABİTLERİ tutar:
- 12 senaryo etiketi (`Scenario`)
- Ses tonu profili (`AssistantProfile`) ve sektör→profil eşleme tablosu
- `{randevu_sayisi}` placeholder'ının senaryoya göre hangi metriğe bağlanacağı
- Gün-tipi (context) karar ağacının eşik değerleri

NOT: Profil tamamen `settings.sector`'den TÜRETİLİR ve kullanıcı tarafından
DEĞİŞTİRİLEMEZ (ayarlarda seçenek yoktur). Eşleşmeyen/boş sektör → PROFESSIONAL.
"""

from enum import Enum


class Scenario(str, Enum):
    # Sabah brifingi (08:30) — kapasite odaklı
    MORNING_BUSY = "morning_busy"
    MORNING_NORMAL = "morning_normal"
    MORNING_EARLY_GAP = "morning_early_gap"
    MORNING_LATE_GAP = "morning_late_gap"
    # Gece kapanışı (22:00) — hikâye odaklı
    NIGHT_GROWTH = "night_growth"
    NIGHT_LOYALTY = "night_loyalty"
    NIGHT_BOOMERANG = "night_boomerang"
    NIGHT_REVENUE = "night_revenue"
    NIGHT_HONEST = "night_honest"
    # Haftalık CEO özeti (Pazar 22:00) — trend/"neden" odaklı
    WEEKLY_RECORD = "weekly_record"
    WEEKLY_NORMAL = "weekly_normal"
    WEEKLY_ALARM = "weekly_alarm"


MORNING_SCENARIOS = {
    Scenario.MORNING_BUSY.value,
    Scenario.MORNING_NORMAL.value,
    Scenario.MORNING_EARLY_GAP.value,
    Scenario.MORNING_LATE_GAP.value,
}
NIGHT_SCENARIOS = {
    Scenario.NIGHT_GROWTH.value,
    Scenario.NIGHT_LOYALTY.value,
    Scenario.NIGHT_BOOMERANG.value,
    Scenario.NIGHT_REVENUE.value,
    Scenario.NIGHT_HONEST.value,
}
WEEKLY_SCENARIOS = {
    Scenario.WEEKLY_RECORD.value,
    Scenario.WEEKLY_NORMAL.value,
    Scenario.WEEKLY_ALARM.value,
}


class AssistantProfile(str, Enum):
    SINCERE_BEAUTY = "SINCERE_BEAUTY"            # Güzellik Salonu, Masaj/SPA (kadın odaklı sıcak)
    SINCERE_HAIRDRESSER = "SINCERE_HAIRDRESSER"  # Kuaför (cinsiyetsiz, sıcak ama nötr)
    PROFESSIONAL = "PROFESSIONAL"                # Klinik/diyetisyen/psikolog/diğer (resmi)


DEFAULT_PROFILE = AssistantProfile.PROFESSIONAL.value

# Kayıt formundaki (RegisterPage.js) BİREBİR settings.sector değerleriyle eşleşir.
SECTOR_PROFILE_MAP = {
    "Kuaför": AssistantProfile.SINCERE_HAIRDRESSER.value,
    "Güzellik Salonu": AssistantProfile.SINCERE_BEAUTY.value,
    "Masaj / SPA": AssistantProfile.SINCERE_BEAUTY.value,
    "Diyetisyen": AssistantProfile.PROFESSIONAL.value,
    "Psikolog / Danışmanlık": AssistantProfile.PROFESSIONAL.value,
    "Diş Klinikleri": AssistantProfile.PROFESSIONAL.value,
    "Diğer/Boş": AssistantProfile.PROFESSIONAL.value,
}

# Metin havuzunda ilgili profil boşsa geri düşülecek sıra (güvenlik ağı).
PROFILE_FALLBACK = {
    AssistantProfile.SINCERE_BEAUTY.value: [
        AssistantProfile.SINCERE_BEAUTY.value,
        AssistantProfile.SINCERE_HAIRDRESSER.value,
        AssistantProfile.PROFESSIONAL.value,
    ],
    AssistantProfile.SINCERE_HAIRDRESSER.value: [
        AssistantProfile.SINCERE_HAIRDRESSER.value,
        AssistantProfile.SINCERE_BEAUTY.value,
        AssistantProfile.PROFESSIONAL.value,
    ],
    AssistantProfile.PROFESSIONAL.value: [
        AssistantProfile.PROFESSIONAL.value,
    ],
}


def resolve_profile(sector) -> str:
    """settings.sector → ses tonu profili. Eşleşmeyen/boş → PROFESSIONAL."""
    key = (sector or "").strip()
    return SECTOR_PROFILE_MAP.get(key, DEFAULT_PROFILE)


def is_sincere(profile: str) -> bool:
    return profile in (
        AssistantProfile.SINCERE_BEAUTY.value,
        AssistantProfile.SINCERE_HAIRDRESSER.value,
    )


# ---------------------------------------------------------------------------
# Placeholder aliasing (KRİTİK)
# Aynı `{randevu_sayisi}` etiketi senaryoya göre FARKLI metriğe bağlanır:
#   - night_growth   → o gün kazanılan YENİ müşteri sayısı
#   - night_boomerang→ geri kazanılan (uyuyan) müşteri sayısı
#   - diğer tüm senaryolar → o günün TOPLAM aktif randevu sayısı
# ---------------------------------------------------------------------------
SCENARIO_APPT_COUNT_SOURCE = {
    Scenario.NIGHT_GROWTH.value: "new_customers",
    Scenario.NIGHT_BOOMERANG.value: "boomerang_customers",
}
DEFAULT_APPT_COUNT_SOURCE = "total_appointments"


def randevu_sayisi_source(scenario: str) -> str:
    return SCENARIO_APPT_COUNT_SOURCE.get(scenario, DEFAULT_APPT_COUNT_SOURCE)


# ---------------------------------------------------------------------------
# Karar ağacı eşikleri
# ---------------------------------------------------------------------------
DEFAULT_LANG = "tr"

# Sabah brifingi (08:30) referans dakikası — "lead time" bu ankora göre ölçülür.
MORNING_ANCHOR = "08:30"
MORNING_ANCHOR_MIN = 8 * 60 + 30  # 510

# Doluluk (kapasite) yüzdesi eşikleri
FULLNESS_BUSY_PCT = 75       # bu ve üzeri → morning_busy
FULLNESS_NORMAL_MIN_PCT = 25  # bilgi amaçlı; altı ve boşluk varsa gap senaryosu

# Boşluk (gap) analizi
GAP_MIN_MINUTES = 120                 # dikkate alınacak minimum kesintisiz boşluk
GAP_EARLY_LATE_LEAD_MINUTES = 180     # gap başlangıcı ankordan <180dk → early, ≥180dk → late

# Gece kapanışı hikâye eşikleri
GROWTH_NEW_CUSTOMERS = 2              # bu ve üzeri yeni müşteri → büyüme günü
BOOMERANG_INACTIVE_DAYS = 180        # geri kazanım için pasiflik eşiği (gün)
BOOMERANG_MIN = 1                    # bu ve üzeri boomerang → geri kazanım günü
LOYALTY_RETURNING_FRACTION = 0.70    # dönen müşteri oranı bu ve üzeri → sadakat günü
LOYALTY_MIN_CUSTOMERS = 3            # sadakat için minimum benzersiz müşteri
REVENUE_UP_PCT = 20                  # baseline'a göre +%20 ve üzeri → ciro günü

# Haftalık CEO özeti eşikleri
WEEKLY_RECORD_PCT = 15               # +%15 ve üzeri → rekor
WEEKLY_ALARM_PCT = -15               # -%15 ve altı → alarm

# Isınma (cold start) dönemi
WARMUP_DAYS = 7                      # ilk 7 gün → "motivasyon modu" (düne göre)

# Not: Profil kayıtta saklanmaz; her zaman sector'den runtime'da türetilir.
