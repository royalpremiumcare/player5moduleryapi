"""
Twilio WhatsApp Business API Entegrasyonu - Content API (Template) Yapısı
Randevu bilgilendirmeleri için WhatsApp mesajları gönderir.
"""

import os
import logging
import re
import json
from typing import Optional, Union, Dict
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Twilio WhatsApp konfigürasyonu
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_FROM_NUMBER', 'whatsapp:+14155238886')  # Sandbox default
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() in ('1', 'true', 'yes')

# Logger
logger = logging.getLogger(__name__)

# ============================================================================
# ŞABLON ID YÖNETİMİ
# ============================================================================

TEMPLATES = {
    "CONFIRMATION": {
        "TR": "HXc9d5674a770f66306b6b68ca0ecc3e34",  # randevu_onay_v1
        "EN": "HX09627707c0333f6d4cbea400a73b5d04"   # randevu_onay_v1_ingilizce
    },
    "REMINDER": {
        "TR": "HX0d3fca96d6e7546d4029c136b66ebdb9",  # randevu_hatirlatma_v1
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
    Telefon numarasını Twilio WhatsApp formatına çevirir.
    
    Args:
        phone (str): Ham telefon numarası (örn: "5551234567", "+905551234567")
    
    Returns:
        str: Twilio formatında numara (örn: "whatsapp:+905551234567")
    """
    # Sadece rakamları al
    clean_phone = re.sub(r'\D', '', phone)
    
    # Türkiye için format kontrolü
    if clean_phone.startswith('90'):
        # Zaten +90 ile başlıyor
        formatted = f"+{clean_phone}"
    elif clean_phone.startswith('5') and len(clean_phone) == 10:
        # 5XXXXXXXXX formatında, +90 ekle
        formatted = f"+90{clean_phone}"
    elif len(clean_phone) == 11 and clean_phone.startswith('05'):
        # 05XXXXXXXXX formatında, 0'ı kaldır ve +90 ekle
        formatted = f"+90{clean_phone[1:]}"
    else:
        # Diğer durumlar için olduğu gibi kullan
        formatted = f"+{clean_phone}" if not clean_phone.startswith('+') else clean_phone
    
    return f"whatsapp:{formatted}"

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
# CONTENT API İLE MESAJ GÖNDERME
# ============================================================================

def send_whatsapp_template(
    to_number: str,
    template_type: str,
    customer_name: str,
    company_name: str,
    appointment_date: str,
    appointment_time: str,
    service_name: str,
    support_phone: str
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
        # WhatsApp devre dışı ise logla ve skip et (bu bir hata değil, bir ayar)
        if not WHATSAPP_ENABLED:
            logger.info("WhatsApp messaging is disabled via WHATSAPP_ENABLED env. Skipping.")
            return "disabled"  # Placeholder değer, gerçek SID değil
        
        # API anahtarları kontrolü
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials not found in environment variables")
            raise Exception("Twilio credentials not found in environment variables")
        
        # Dil tespiti
        language = detect_language_from_phone(to_number)
        
        # Şablon tipi kontrolü
        template_type_upper = template_type.upper()
        if template_type_upper not in TEMPLATES:
            error_msg = f"Invalid template type: {template_type}. Must be one of: {list(TEMPLATES.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Şablon ID'yi al
        content_sid = TEMPLATES[template_type_upper].get(language)
        if not content_sid:
            error_msg = f"Template SID not found for type '{template_type_upper}' and language '{language}'"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Tarih formatını düzenle (DD.MM.YYYY formatına çevir)
        # Kullanıcı dostu format: 25.12.2025 (Gün.Ay.Yıl)
        formatted_date = format_date_for_display(appointment_date)
        
        # Content Variables oluştur (Twilio Content API formatı)
        # Sıralama: 1=Müşteri Adı, 2=İşletme Adı, 3=Tarih, 4=Saat, 5=Hizmet Adı, 6=İletişim Numarası
        content_variables = {
            "1": customer_name,      # Müşteri Adı
            "2": company_name,        # İşletme Adı
            "3": formatted_date,       # Tarih
            "4": appointment_time,    # Saat
            "5": service_name,        # Hizmet Adı
            "6": support_phone        # İletişim Numarası
        }
        
        # Telefon numarasını formatla
        formatted_to = format_phone_number(to_number)
        
        # Twilio client oluştur
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # DEBUG: Template SID'yi logla
        print(f"DEBUG: Sending Template SID: {content_sid} to {formatted_to}")
        logger.info(f"DEBUG: Sending Template SID: {content_sid} to {formatted_to}")
        
        # WhatsApp mesajı gönder (Content API - SADECE content_sid ve content_variables kullan)
        # ÖNEMLİ: body parametresi KULLANILMAMALI (24 saat kuralı nedeniyle Error 63016 hatası verir)
        message = client.messages.create(
            content_sid=content_sid,
            content_variables=json.dumps(content_variables),
            from_=TWILIO_WHATSAPP_FROM,
            to=formatted_to
        )
        
        logger.info(
            f"WhatsApp template message sent successfully to {formatted_to}. "
            f"Template: {template_type_upper} ({language}), SID: {message.sid}"
        )
        return message.sid
        
    except TwilioException as e:
        logger.error(f"Twilio WhatsApp error for {to_number}: {str(e)}")
        # Fallback yok - hata varsa kod patlasın, yanlış yöntem denemesin
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp to {to_number}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Fallback yok - hata varsa kod patlasın, yanlış yöntem denemesin
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
