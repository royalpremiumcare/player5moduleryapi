"""
Application Constants
Plans, limits, and other static data
"""

# === SUBSCRIPTION PLANS ===
PLANS = [
    {
        "id": "tier_trial",
        "name": "Trial",
        "price_monthly": 0,
        "quota_monthly_appointments": 50,
        "ai_message_limit": 100,
        "trial_days": 7,
        "features": [
            "50 Randevu veya 7 Gün (Hangisi önce)",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Test)"
        ],
        "target_audience_tr": "Yeni kullanıcılar için deneme paketi."
    },
    {
        "id": "tier_1_standard",
        "name": "Standart",
        "price_monthly": 520,
        "quota_monthly_appointments": 100,
        "ai_message_limit": 500,
        "features": [
            "100 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Standart Kullanım)"
        ],
        "target_audience_tr": "Yeni başlayanlar, tek kişilik veya butik işletmeler için ideal başlangıç paketi."
    },
    {
        "id": "tier_2_profesyonel",
        "name": "Profesyonel",
        "price_monthly": 780,
        "quota_monthly_appointments": 300,
        "ai_message_limit": 3000,
        "features": [
            "300 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Gelişmiş Kullanım)"
        ],
        "target_audience_tr": "Büyümekte olan ve müşteri kitlesini oturtmaya başlamış salonlar için."
    },
    {
        "id": "tier_3_premium",
        "name": "Premium",
        "price_monthly": 1100,
        "quota_monthly_appointments": 600,
        "ai_message_limit": 10000,
        "features": [
            "600 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Limitsiz)"
        ],
        "target_audience_tr": "Düzenli ve sabit bir müşteri hacmine sahip, yerleşik işletmeler için."
    },
    {
        "id": "tier_4_business",
        "name": "Business",
        "price_monthly": 1300,
        "quota_monthly_appointments": 900,
        "ai_message_limit": -1,
        "features": [
            "900 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Limitsiz)"
        ],
        "target_audience_tr": "Yoğun tempolu, orta ölçekli salonlar ve merkezler için en popüler seçim."
    },
    {
        "id": "tier_5_enterprise",
        "name": "Enterprise",
        "price_monthly": 1500,
        "quota_monthly_appointments": 1200,
        "ai_message_limit": -1,
        "features": [
            "1.200 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Limitsiz)"
        ],
        "target_audience_tr": "Yüksek hacimli, birden fazla uzman/personel çalıştıran salonlar ve klinikler için."
    },
    {
        "id": "tier_6_kurumsal",
        "name": "Kurumsal",
        "price_monthly": 1990,
        "quota_monthly_appointments": 2000,
        "ai_message_limit": -1,
        "features": [
            "2.000 Randevu/Ay",
            "Randevu Hatırlatma Dahil",
            "Sınırsız Personel",
            "Sınırsız Müşteri",
            "Online Randevu",
            "İstatistikler",
            "Yapay Zeka Akıllı Asistan (Limitsiz)"
        ],
        "target_audience_tr": "Sektörün en yoğun klinikleri, poliklinikler ve büyük ölçekli işletmeler için tam çözüm."
    }
]


# Helper function to get plan by ID
def get_plan_by_id(plan_id: str) -> dict:
    """Get plan details by ID"""
    return next((p for p in PLANS if p['id'] == plan_id), None)


# === STATUS CONSTANTS ===
APPOINTMENT_STATUS = {
    "PENDING": "Bekliyor",
    "COMPLETED": "Tamamlandı",
    "CANCELLED": "İptal Edildi",
    "NO_SHOW": "Gelmedi"
}

# === USER ROLES ===
USER_ROLES = {
    "ADMIN": "admin",
    "STAFF": "staff",
    "SUPERADMIN": "superadmin"
}

# === DEFAULT VALUES ===
DEFAULT_WORKING_HOURS = {
    "monday": {"is_working": True, "start": "09:00", "end": "18:00"},
    "tuesday": {"is_working": True, "start": "09:00", "end": "18:00"},
    "wednesday": {"is_working": True, "start": "09:00", "end": "18:00"},
    "thursday": {"is_working": True, "start": "09:00", "end": "18:00"},
    "friday": {"is_working": True, "start": "09:00", "end": "18:00"},
    "saturday": {"is_working": False, "start": "09:00", "end": "18:00"},
    "sunday": {"is_working": False, "start": "09:00", "end": "18:00"}
}
