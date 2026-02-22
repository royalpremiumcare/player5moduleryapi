"""
WhatsApp Bildirim Servisi

Twilio devre dışı (geçici, test amaçlı).
Meta WhatsApp Cloud API doğrudan HTTP entegrasyonu kullanılıyor.
"""

import os
import logging
import re
import json
import requests
from typing import Optional, Union, Dict
# from twilio.rest import Client                  # Twilio geçici olarak devre dışı
# from twilio.base.exceptions import TwilioException  # Twilio geçici olarak devre dışı
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Twilio WhatsApp konfigürasyonu (geçici olarak devre dışı)
# TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
# TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
# TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_FROM_NUMBER', 'whatsapp:+14155238886')
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() in ('1', 'true', 'yes')

# ============================================================================
# META WHATSAPP CLOUD API KONFİGÜRASYONU
# ============================================================================

META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
META_PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')
META_API_VERSION = os.getenv('META_API_VERSION', 'v21.0')

# Logger
logger = logging.getLogger(__name__)

# ============================================================================
# ŞABLON ID YÖNETİMİ
# ============================================================================

TEMPLATES = {
    "CONFIRMATION": {
        "TR": "HXdb5b18b2e4b59d9498176217da791091",  # randevu_onay_v1
        "EN": "HX09627707c0333f6d4cbea400a73b5d04"   # randevu_onay_v1_ingilizce
    },
    "REMINDER": {
        "TR": "HX807f1d58779d6fd7bab54b325fce7e21",  # randevu_hatirlatma_v1
        "EN": "HXc95f6ee596484b410bd68089bbeecdd8"   # randevu_hatirlatma_v1_ingilizce
    },
    "CANCELLATION": {
        "TR": "HX5cfe91716bcfb5175fcb42af743780f2",  # randevu_iptal_v1
        "EN": "HX16e5f28fb977e5fbefd49acbed1d90b7"   # randevu_iptal_v1_ingilizce
    }
}

# ============================================================================
# DİL TESPİTİ
# ============================================================================

def detect_language_from_phone(phone: str) -> str:
    """
    Telefon numarasına göre dil tespiti yapar.
    
    Args:
        phone (str): Telefon numarası (örn: "+905551234567", "5551234567")
    
    Returns:
        str: "TR" veya "EN"
    """
    # Sadece rakamları ve + işaretini al
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # +90 ile başlıyorsa Türkçe
    if clean_phone.startswith('+90') or clean_phone.startswith('90'):
        return "TR"
    
    # 0 ile başlayıp 5 ile devam ediyorsa (05XXXXXXXXX) Türkçe
    if clean_phone.startswith('05') and len(clean_phone) == 11:
        return "TR"
    
    # 5 ile başlayıp 10 haneli ise (5XXXXXXXXX) Türkçe
    if clean_phone.startswith('5') and len(clean_phone) == 10:
        return "TR"
    
    # Diğer tüm durumlar için İngilizce
    return "EN"

# ============================================================================
# TELEFON NUMARASI FORMATLAMA
# ============================================================================

def format_phone_number(phone: str) -> str:
    """
    Telefon numarasını E.164 formatına çevirir (Meta Cloud API için).
    
    Args:
        phone (str): Ham telefon numarası (örn: "5551234567", "+905551234567")
    
    Returns:
        str: E.164 formatında numara başında + olmadan (örn: "905551234567")
    """
    # Sadece rakamları al
    clean_phone = re.sub(r'\D', '', phone)
    
    # Türkiye için format kontrolü
    if clean_phone.startswith('90') and len(clean_phone) == 12:
        return clean_phone
    elif clean_phone.startswith('5') and len(clean_phone) == 10:
        return f"90{clean_phone}"
    elif len(clean_phone) == 11 and clean_phone.startswith('05'):
        return f"90{clean_phone[1:]}"
    else:
        # Diğer ülkeler: başındaki 0'ı at, olduğu gibi kullan
        return clean_phone.lstrip('0') if clean_phone else clean_phone

# ============================================================================
# TARİH FORMATLAMA
# ============================================================================

def format_date_for_display(date_input: str) -> str:
    """
    Tarihi kullanıcı dostu formata çevirir (DD.MM.YYYY).
    
    Desteklenen giriş formatları:
    - YYYY-MM-DD (örn: "2025-12-25")
    - DD.MM.YYYY (zaten formatlanmış)
    - DD/MM/YYYY
    - YYYY/MM/DD
    
    Args:
        date_input (str): Ham tarih string'i
    
    Returns:
        str: DD.MM.YYYY formatında tarih (örn: "25.12.2025")
    """
    from datetime import datetime
    
    if not date_input:
        return date_input
    
    # Zaten DD.MM.YYYY formatındaysa olduğu gibi döndür
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_input):
        return date_input
    
    # Farklı formatları dene
    date_formats = [
        "%Y-%m-%d",      # 2025-12-25
        "%d.%m.%Y",      # 25.12.2025
        "%d/%m/%Y",      # 25/12/2025
        "%Y/%m/%d",      # 2025/12/25
        "%d-%m-%Y",      # 25-12-2025
        "%Y-%m-%d %H:%M:%S",  # 2025-12-25 14:30:00 (datetime string)
    ]
    
    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(date_input.strip(), date_format)
            # DD.MM.YYYY formatına çevir
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            continue
    
    # Hiçbir format uymazsa, orijinal değeri döndür ve uyarı ver
    logger.warning(f"Could not parse date format: {date_input}. Using original value.")
    return date_input

# ============================================================================
# META WHATSAPP CLOUD API - MESAJ GÖNDERME
# ============================================================================

def send_meta_whatsapp_template(
    to_number: str,
    template_name: str,
    language_code: str,
    body_params: list,
) -> str:
    """
    Meta WhatsApp Cloud API kullanarak şablon mesajı gönderir.

    Args:
        to_number (str): Alıcı telefon numarası (ham format, E.164'e çevrilir)
        template_name (str): Meta'da onaylı şablon adı (örn: "randevu_onay")
        language_code (str): Şablon dil kodu (örn: "tr", "en")
        body_params (list): Şablondaki {{1}}, {{2}}... değişkenlerine karşılık gelen
                            string listesi (sıra önemli)

    Returns:
        str: Meta API'den dönen mesaj ID'si

    Raises:
        Exception: API hatası veya eksik konfigürasyon durumunda
    """
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        raise Exception(
            "Meta WhatsApp Cloud API credentials not found. "
            "Set META_ACCESS_TOKEN and META_PHONE_NUMBER_ID environment variables."
        )

    url = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    formatted_to = format_phone_number(to_number)

    parameters = [
        {"type": "text", "text": _normalise_template_var(p)}
        for p in body_params
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": [
                {
                    "type": "body",
                    "parameters": parameters,
                }
            ],
        },
    }

    logger.info(
        f"Meta WA → template={template_name} lang={language_code} to={formatted_to} "
        f"params={body_params}"
    )

    response = requests.post(url, headers=headers, json=payload, timeout=15)

    if not response.ok:
        logger.error(
            f"Meta WA API error: status={response.status_code} body={response.text}"
        )
        response.raise_for_status()

    data = response.json()
    message_id = data.get("messages", [{}])[0].get("id", "unknown")
    logger.info(f"Meta WA message sent. id={message_id}")
    return message_id


# ============================================================================
# TWILIO (devre dışı) → Meta Cloud API'ye yönlendirme
# ============================================================================

def _normalise_template_var(value: object, fallback: str = "-") -> str:
    """Twilio Content API content_variables must contain non-null string values."""
    if value is None:
        return fallback
    try:
        text = str(value).strip()
    except Exception:
        return fallback
    return text if text else fallback

def send_whatsapp_template(
    to_number: str,
    template_type: str,
    customer_name: str,
    company_name: str,
    appointment_date: str,
    appointment_time: str,
    service_name: str,
    support_phone: str,
    business_lat: Optional[Union[float, int, str]] = None,
    business_lng: Optional[Union[float, int, str]] = None
) -> str:
    """
    Twilio Content API kullanarak WhatsApp şablon mesajı gönderir.
    
    Args:
        to_number (str): Alıcı telefon numarası
        template_type (str): Şablon tipi ("CONFIRMATION", "REMINDER", "CANCELLATION")
        customer_name (str): Müşteri adı
        company_name (str): İşletme adı
        appointment_date (str): Randevu tarihi (format: YYYY-MM-DD)
        appointment_time (str): Randevu saati (format: HH:MM)
        service_name (str): Hizmet adı
        support_phone (str): İletişim numarası
    
    Returns:
        str: Message SID (başarılı ise)
    
    Raises:
        TwilioException: Twilio API hatası durumunda
        ValueError: Geçersiz parametreler durumunda
        Exception: Diğer hatalar durumunda
    """
    try:
        # WhatsApp devre dışı ise logla ve skip et
        if not WHATSAPP_ENABLED:
            logger.info("WhatsApp messaging is disabled via WHATSAPP_ENABLED env. Skipping.")
            return "disabled"

        # Dil tespiti
        language = detect_language_from_phone(to_number)

        # Şablon tipi kontrolü
        template_type_upper = template_type.upper()
        if template_type_upper not in TEMPLATES:
            error_msg = f"Invalid template type: {template_type}. Must be one of: {list(TEMPLATES.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Tarih formatını düzenle (DD.MM.YYYY)
        formatted_date = format_date_for_display(appointment_date)

        # Konum linki oluştur
        map_link: Optional[str] = None
        try:
            if business_lat is not None and business_lng is not None:
                lat = float(business_lat)
                lng = float(business_lng)
                map_link = f"https://maps.google.com/?q={lat},{lng}"
        except Exception:
            map_link = None

        map_link_fallback = "Konum girilmedi" if language == "TR" else "-"
        map_link_value = _normalise_template_var(map_link, fallback=map_link_fallback)

        # ----------------------------------------------------------------
        # TWILIO ÇAĞRISI DEVRE DIŞI (geçici, test amaçlı)
        # ----------------------------------------------------------------
        # client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # message = client.messages.create(
        #     content_sid=content_sid,
        #     content_variables=json.dumps(content_variables),
        #     from_=TWILIO_WHATSAPP_FROM,
        #     to=formatted_to
        # )
        # return message.sid
        # ----------------------------------------------------------------

        # META WHATSAPP CLOUD API'ye yönlendir
        # Şu an için sadece "randevu_onay" şablonu (CONFIRMATION) destekleniyor.
        # REMINDER ve CANCELLATION için Meta'da şablon onayı sonrası genişletilebilir.

        if template_type_upper == "CONFIRMATION":
            meta_template_name = "randevu_onay"
        elif template_type_upper == "REMINDER":
            meta_template_name = "randevu_onay"  # Geçici: hatırlatma için de aynı şablon
        elif template_type_upper == "CANCELLATION":
            meta_template_name = "randevu_onay"  # Geçici: iptal şablonu onaylanana kadar
        else:
            meta_template_name = "randevu_onay"

        # Parametreler: {{1}}=müşteri adı, {{2}}=işletme adı, {{3}}=tarih,
        #               {{4}}=saat, {{5}}=hizmet, {{6}}=destek tel, {{7}}=harita
        body_params = [
            _normalise_template_var(customer_name),
            _normalise_template_var(company_name),
            _normalise_template_var(formatted_date),
            _normalise_template_var(appointment_time),
            _normalise_template_var(service_name),
            _normalise_template_var(support_phone),
            map_link_value,
        ]

        lang_code = "tr" if language == "TR" else "en"

        message_id = send_meta_whatsapp_template(
            to_number=to_number,
            template_name=meta_template_name,
            language_code=lang_code,
            body_params=body_params,
        )

        logger.info(
            f"WhatsApp (Meta) sent to {to_number}. "
            f"Template: {meta_template_name} ({lang_code}), id: {message_id}"
        )
        return message_id

    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp to {to_number}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


# ============================================================================
# TEST FONKSİYONU
# ============================================================================

if __name__ == "__main__":
    # Test mesajı
    print("Testing WhatsApp Content API Integration...")
    print("=" * 60)
    
    # Test 1: Türkçe numara ile onay mesajı
    result1 = send_whatsapp_template(
        to_number="+905551234567",
        template_type="CONFIRMATION",
        customer_name="Ahmet Yılmaz",
        company_name="Test Kuaför",
        appointment_date="2025-12-25",
        appointment_time="14:30",
        service_name="Saç Kesimi",
        support_phone="0532 123 45 67"
    )
    print(f"Test 1 (TR Confirmation): {result1}")
    
    # Test 2: İngilizce numara ile hatırlatma mesajı
    result2 = send_whatsapp_template(
        to_number="+441234567890",
        template_type="REMINDER",
        customer_name="John Doe",
        company_name="Test Salon",
        appointment_date="2025-12-25",
        appointment_time="15:00",
        service_name="Haircut",
        support_phone="+44 20 1234 5678"
    )
    print(f"Test 2 (EN Reminder): {result2}")
    
    print("=" * 60)
    print("Tests completed.")
