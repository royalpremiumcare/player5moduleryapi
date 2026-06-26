"""
WhatsApp Bildirim Servisi — Meta WhatsApp Cloud API (Direkt HTTP)

Şablon Mimarisi (8 onaylı şablon):
  CONFIRMATION x TR x Konumlu  → randevu_onay_konumlu_v2
  CONFIRMATION x TR x Metin    → randevu_onay_metin
  CONFIRMATION x EN x Konumlu  → randevu_onay_konumlu_eng_v2
  CONFIRMATION x EN x Metin    → randevu_onay_metin_eng_v2
  REMINDER     x TR x Konumlu  → randevu_hatirlatma_konumlu
  REMINDER     x TR x Metin    → randevu_hatirlatma_metin_v2
  REMINDER     x EN x Konumlu  → randevu_hatirlatma_konumlu_eng
  REMINDER     x EN x Metin    → randevu_hatirlatma_metin_v2_eng

Senaryo A (koordinat VARSA):  header = location, body = 5-6 parametre
Senaryo B (koordinat YOKSA):  header = text (işletme adı), body = 7 parametre
"""

import os
import logging
import re
import requests
from typing import Optional, Union, Dict, List
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() in ('1', 'true', 'yes')

# ============================================================================
# META WHATSAPP CLOUD API KONFİGÜRASYONU
# ============================================================================

META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
META_PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')
META_API_VERSION = os.getenv('META_API_VERSION', 'v21.0')

logger = logging.getLogger(__name__)

# ============================================================================
# ŞABLON İSİM MATRİSİ
# ============================================================================

TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "CONFIRMATION": {
        "TR": {
            "with_location":    "randevu_onay_konumlu_v2",
            "without_location": "randevu_onay_metin",
            "lang_code":        "tr",
        },
        "EN": {
            "with_location":    "randevu_onay_konumlu_eng_v2",
            "without_location": "randevu_onay_metin_eng_v2",
            "lang_code":        "en",
        },
    },
    # PLANN v2: Online full payment confirmation (amount paid)
    # Yalnızca public booking + payment_rule="online"/"full_online" akışında kullanılır
    "CONFIRMATION_FULL_PAID": {
        "TR": {
            "with_location":    "randevu_onay_konumlu_online_odemeli",
            "without_location": "randevu_onay_metin_online_odemeli",
            "lang_code":        "tr",
        },
        "EN": {
            "with_location":    "randevu_onay_konumlu_online_odemeli_eng",
            "without_location": "randevu_onay_metin_online_odemeli_eng",
            "lang_code":        "en",
        },
    },
    # PLANN v2: Deposit confirmation (amount paid + amount due on site)
    # Yalnızca public booking + payment_rule="deposit" akışında kullanılır
    "CONFIRMATION_DEPOSIT": {
        "TR": {
            "with_location":    "randevu_onay_konumlu_kapora_odemeli",
            "without_location": "randevu_onay_metin_kapora_odemeli",
            "lang_code":        "tr",
        },
        "EN": {
            # Not: Meta'da onaylı konumlu şablonun adı 'r' olmadan başlıyor.
            "with_location":    "andevu_onay_konumlu_kapora_odemeli_eng",
            "without_location": "randevu_onay_metin_kapora_odemeli_eng",
            "lang_code":        "en",
        },
    },
    "REMINDER": {
        "TR": {
            "with_location":    "randevu_hatirlatma_konumlu",
            "without_location": "randevu_hatirlatma_metin_v2",
            "lang_code":        "tr",
        },
        "EN": {
            "with_location":    "randevu_hatirlatma_konumlu_eng",
            "without_location": "randevu_hatirlatma_metin_v2_eng",
            "lang_code":        "en",
        },
    },
    "SESSION_PACKAGE": {
        "TR": {
            "with_location":    "seans_paketi_onay_konumlu",
            "without_location": "seans_paketi_onay_metin",
            "lang_code":        "tr",
        },
        "EN": {
            "with_location":    "seans_paketi_onay_konumlu_en",
            "without_location": "seans_paketi_onay_metin_en",
            "lang_code":        "en",
        },
    },
}

VALID_TEMPLATE_TYPES = set(TEMPLATES.keys())

# PLANN v2: Bazı yeni şablonlar Meta'da header bileşeni OLMADAN onaylandı
# (gövde-yalnız tasarım). Bu set'teki template adları için header gönderimi
# atlanır — aksi halde Meta "Template does not contain title component" 400'ü
# döner. Yeni böyle bir şablon eklendikçe bu set'e eklenecek.
TEMPLATES_WITHOUT_HEADER: set = set()
# Not: PLANN v2 şablonların hepsinde artık header bileşeni var
# (konumlu => location header, metin => text header = işletme adı).
# `randevu_onay_metin_kapora_odemeli_eng` Meta'da onay bekliyor; onay
# gelince zaten header'lı olduğu için burada herhangi bir değişiklik
# gerekmez. Eğer Meta tekrar bir şablon için header'ı reddederse,
# adı bu set'e eklenmeli.

# ============================================================================
# DİL TESPİTİ
# ============================================================================

def detect_language_from_phone(phone: str) -> str:
    """Telefon numarasına göre dil tespiti. Türkiye → 'TR', diğer → 'EN'."""
    clean_phone = re.sub(r'[^\d+]', '', phone)
    if clean_phone.startswith('+90') or clean_phone.startswith('90'):
        return "TR"
    if clean_phone.startswith('05') and len(clean_phone) == 11:
        return "TR"
    if clean_phone.startswith('5') and len(clean_phone) == 10:
        return "TR"
    return "EN"

# ============================================================================
# TELEFON NUMARASI FORMATLAMA
# ============================================================================

def format_phone_number(phone: str) -> str:
    """Ham numarayı E.164 formatına çevirir (+ öneki olmadan)."""
    clean_phone = re.sub(r'\D', '', phone)
    if clean_phone.startswith('90') and len(clean_phone) == 12:
        return clean_phone
    elif clean_phone.startswith('5') and len(clean_phone) == 10:
        return f"90{clean_phone}"
    elif len(clean_phone) == 11 and clean_phone.startswith('05'):
        return f"90{clean_phone[1:]}"
    else:
        return clean_phone.lstrip('0') if clean_phone else clean_phone

# ============================================================================
# TARİH FORMATLAMA
# ============================================================================

def format_date_for_display(date_input: str) -> str:
    """Tarihi DD.MM.YYYY formatına çevirir. Desteklenen: YYYY-MM-DD, DD/MM/YYYY vb."""
    from datetime import datetime
    if not date_input:
        return date_input
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_input):
        return date_input
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(date_input.strip(), fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    logger.warning(f"Could not parse date format: {date_input}. Using original value.")
    return date_input

# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def _normalise_template_var(value: object, fallback: str = "-") -> str:
    """Template değişkenlerini güvenli, boşluksuz string'e çevirir."""
    if value is None:
        return fallback
    try:
        text = str(value).strip()
    except Exception:
        return fallback
    return text if text else fallback


def _has_valid_coordinates(lat, lng) -> bool:
    """Geçerli (non-None, sayısal) koordinat çifti var mı kontrol eder."""
    try:
        if lat is None or lng is None:
            return False
        float(lat)
        float(lng)
        return True
    except (ValueError, TypeError):
        return False

# ============================================================================
# COMPONENT OLUŞTURUCULAR
# ============================================================================

def _build_location_header(lat: float, lng: float, name: str, address: str) -> dict:
    """Senaryo A — location tipi header component."""
    return {
        "type": "header",
        "parameters": [
            {
                "type": "location",
                "location": {
                    "latitude":  str(lat),
                    "longitude": str(lng),
                    "name":      name,
                    "address":   address,
                },
            }
        ],
    }


def _build_text_header(company_name: str) -> dict:
    """Senaryo B — text tipi header component (işletme adı kalın görünür)."""
    return {
        "type": "header",
        "parameters": [
            {"type": "text", "text": company_name}
        ],
    }


def _build_body(params: List[str]) -> dict:
    """Sıralı string listesinden body component oluşturur."""
    return {
        "type": "body",
        "parameters": [
            {"type": "text", "text": _normalise_template_var(p)}
            for p in params
        ],
    }

# ============================================================================
# RETRY HELPER — Meta transient hataları (code 1/2, 5xx, timeout) için
# ============================================================================

WA_MAX_RETRIES = 3
WA_RETRY_DELAYS = [2, 5, 10]  # saniye (deneme 1→2, 2→3, ...)


def _is_transient_meta_error(response) -> bool:
    """Meta yanıtı geçici (retry edilebilir) bir hata mı?

    Retry koşulları:
      - HTTP 5xx
      - Hata gövdesinde is_transient: true
      - Hata kodu 1 (API Unknown) veya 2 (API Service)
    """
    if response.status_code >= 500:
        return True
    try:
        err = response.json().get("error", {})
        if err.get("is_transient"):
            return True
        if err.get("code") in (1, 2):
            return True
    except Exception:
        pass
    return False


def _post_with_retry(url: str, headers: dict, payload: dict, context: str) -> dict:
    """Meta WA API'ye retry'lı POST. Başarılı yanıtın JSON gövdesini döner.

    Transient hatalarda (5xx, code 1/2, is_transient, timeout/bağlantı) max
    WA_MAX_RETRIES deneme yapar, aralarda exponential backoff bekler.
    Kalıcı 4xx hatalarda hemen raise eder.
    """
    import time

    last_exception = None
    for attempt in range(1, WA_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as conn_err:
            last_exception = conn_err
            logger.warning(
                f"Meta WA bağlantı hatası ({context}) attempt={attempt}/{WA_MAX_RETRIES}: {conn_err}"
            )
            if attempt < WA_MAX_RETRIES:
                time.sleep(WA_RETRY_DELAYS[attempt - 1])
            continue

        if response.ok:
            return response.json()

        logger.error(
            f"Meta WA API error ({context}) attempt={attempt}/{WA_MAX_RETRIES}: "
            f"status={response.status_code} body={response.text}"
        )

        if not _is_transient_meta_error(response):
            # Kalıcı hata (geçersiz şablon, izin, numara format vb.) — retry anlamsız
            response.raise_for_status()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            last_exception = http_err

        if attempt < WA_MAX_RETRIES:
            delay = WA_RETRY_DELAYS[attempt - 1]
            logger.warning(f"Meta WA transient hata ({context}) — {delay}s sonra tekrar denenecek")
            time.sleep(delay)

    logger.error(f"Meta WA gönderim {WA_MAX_RETRIES} denemede de başarısız ({context})")
    raise last_exception


# ============================================================================
# META WHATSAPP CLOUD API — DÜŞÜK SEVİYE GÖNDERME
# ============================================================================

def send_meta_whatsapp_template(
    to_number: str,
    template_name: str,
    language_code: str,
    components: Optional[List[dict]] = None,
) -> str:
    """
    Meta WhatsApp Cloud API'ye direkt HTTP isteği atar.

    Args:
        to_number:     Alıcı numara (ham, E.164'e çevrilir)
        template_name: Meta'da onaylı şablon adı
        language_code: "tr" veya "en"
        components:    [header_component, body_component, ...] listesi

    Returns:
        str: Meta API'den dönen mesaj ID'si
    """
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        raise Exception(
            "Meta WhatsApp Cloud API credentials eksik. "
            "META_ACCESS_TOKEN ve META_PHONE_NUMBER_ID env variable'larını ayarlayın."
        )

    url = (
        f"https://graph.facebook.com/{META_API_VERSION}"
        f"/{META_PHONE_NUMBER_ID}/messages"
    )
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    formatted_to = format_phone_number(to_number)

    template_payload: Dict = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if components:
        template_payload["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_to,
        "type": "template",
        "template": template_payload,
    }

    logger.info(
        f"Meta WA → template={template_name} lang={language_code} "
        f"to={formatted_to} components={len(components) if components else 0}"
    )

    data = _post_with_retry(url, headers, payload, context=f"template={template_name}")
    message_id = data.get("messages", [{}])[0].get("id", "unknown")
    logger.info(f"Meta WA mesaj gönderildi. id={message_id}")
    return message_id


# ============================================================================
# PAY-BY-LINK ("ÖDEME İSTE") ŞABLON GÖNDERİMİ
# ============================================================================

def send_payment_link_template(
    to_number: str,
    customer_name: str,
    company_name: str,
    description: str,
    final_amount_display: str,
    checkout_url: str,
    header_image_url: str = "https://plannapp.co/api/static/plannlogo.png",
) -> str:
    """
    Tek seferlik ödeme talebini, Meta'da onaylı `tek_seferlik_odeme_tr` şablonuyla
    müşteriye WhatsApp üzerinden gönderir.

    Şablon yapısı:
        HEADER = IMAGE (header_image_url — işletme logosu / varsayılan PLANN logosu)
        BODY:
            {{1}} = customer_name (müşteri)
            {{2}} = company_name (işletme)
            {{3}} = description
            {{4}} = final_amount_display (ör. "₺1.250,00")
        BUTTON (URL, index 0) dinamik suffix = `checkout_url.split("/pay/")[-1]`
            → `cs_live_...` segmenti. Şablonun buton base URL'i Stripe checkout
            domain'i olarak yapılandırılmıştır.
    """
    if not WHATSAPP_ENABLED:
        return "disabled"

    # URL butonu için dinamik segmenti ayıkla
    url_suffix = checkout_url.split("/pay/")[-1] if "/pay/" in checkout_url else checkout_url

    components = [
        {
            "type": "header",
            "parameters": [
                {"type": "image", "image": {"link": header_image_url}},
            ],
        },
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(customer_name or "")},
                {"type": "text", "text": str(company_name or "")},
                {"type": "text", "text": str(description or "")},
                {"type": "text", "text": str(final_amount_display or "")},
            ],
        },
        {
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [
                {"type": "text", "text": url_suffix},
            ],
        },
    ]

    return send_meta_whatsapp_template(
        to_number=to_number,
        template_name="tek_seferlik_odeme_tr",
        language_code="tr",
        components=components,
    )


# ============================================================================
# DÜZ METİN MESAJ GÖNDERİMİ (newline destekler)
# ============================================================================

def send_whatsapp_text(to_number: str, body: str) -> str:
    """Template sonrası takip mesajı gibi düz metin gönderir. Newline destekler."""
    if not WHATSAPP_ENABLED:
        return "disabled"
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        raise Exception("Meta WhatsApp credentials eksik.")

    formatted_to = format_phone_number(to_number)
    url = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": formatted_to, "type": "text", "text": {"body": body}}

    data = _post_with_retry(url, headers, payload, context="text")
    msg_id = data.get("messages", [{}])[0].get("id", "unknown")
    logger.info(f"Meta WA text gönderildi. id={msg_id} to={formatted_to}")
    return msg_id


# ============================================================================
# ANA GÖNDERIM FONKSİYONU
# ============================================================================

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
    business_lng: Optional[Union[float, int, str]] = None,
    business_address: Optional[str] = None,
    session_count: Optional[int] = None,
    session_dates_text: Optional[str] = None,
    amount_paid_display: Optional[str] = None,
    on_site_amount_display: Optional[str] = None,
) -> str:
    """
    Müşteri diline ve işletme koordinatına göre doğru Meta WA şablonunu seçip gönderir.

    CONFIRMATION / REMINDER:
      Senaryo A (konum VAR): header=location, body={{1..6}}
      Senaryo B (konum YOK): header=text, body={{1..7}}

    SESSION_PACKAGE (her iki senaryo):
      body: {{1}} müşteri, {{2}} hizmet, {{3}} toplam seans, {{4}} seans listesi, {{5}} iletişim
      Senaryo A: header=location  |  Senaryo B: header=text (işletme adı)
    """
    try:
        if not WHATSAPP_ENABLED:
            logger.info("WhatsApp messaging is disabled via WHATSAPP_ENABLED env. Skipping.")
            return "disabled"

        template_type_upper = template_type.upper()
        if template_type_upper not in VALID_TEMPLATE_TYPES:
            raise ValueError(
                f"Geçersiz template_type: '{template_type}'. "
                f"Geçerli değerler: {list(VALID_TEMPLATE_TYPES)}"
            )

        language = detect_language_from_phone(to_number)
        template_info = TEMPLATES[template_type_upper][language]
        lang_code = template_info["lang_code"]
        formatted_date = format_date_for_display(appointment_date)
        has_location = _has_valid_coordinates(business_lat, business_lng)

        if has_location:
            lat = float(business_lat)
            lng = float(business_lng)
            addr_text = _normalise_template_var(business_address, fallback=company_name)
            template_name = template_info["with_location"]
            header = _build_location_header(lat, lng, company_name, addr_text)
        else:
            template_name = template_info["without_location"]
            header = _build_text_header(company_name)

        amount_paid = _normalise_template_var(amount_paid_display, fallback="-")
        on_site_amount = _normalise_template_var(on_site_amount_display, fallback="-")

        if template_type_upper == "SESSION_PACKAGE":
            # {{1}} müşteri, {{2}} hizmet, {{3}} toplam seans, {{4}} seans listesi, {{5}} iletişim
            body = _build_body([
                customer_name,
                service_name,
                str(session_count or ""),
                session_dates_text or "",
                support_phone,
            ])
        elif template_type_upper == "CONFIRMATION_FULL_PAID":
            # PLANN v2 — Online tam ödeme onayı (Meta'da onaylı güncel şablonlara göre)
            #   Konumlu (8 param): {{1}} müşteri, {{2}} işletme, {{3}} tarih, {{4}} saat,
            #                       {{5}} hizmet, {{6}} iletişim, {{7}} tutar, {{8}} tutar
            #   Metin   (7 param): {{1}} müşteri, {{2}} tutar, {{3}} tarih, {{4}} saat,
            #                       {{5}} hizmet, {{6}} tutar, {{7}} iletişim
            if has_location:
                body = _build_body([
                    customer_name, company_name,
                    formatted_date, appointment_time,
                    service_name, support_phone,
                    amount_paid, amount_paid,
                ])
            else:
                body = _build_body([
                    customer_name, amount_paid,
                    formatted_date, appointment_time, service_name,
                    amount_paid, support_phone,
                ])
        elif template_type_upper == "CONFIRMATION_DEPOSIT":
            # PLANN v2 — Kapora ödemeli onay (Meta'da onaylı güncel şablonlara göre)
            #   Konumlu (9 param): {{1}} müşteri, {{2}} işletme, {{3}} tarih, {{4}} saat,
            #                       {{5}} hizmet, {{6}} iletişim, {{7}} kapora, {{8}} kapora,
            #                       {{9}} işletmede ödenecek
            #   Metin   (8 param): {{1}} müşteri, {{2}} kapora, {{3}} tarih, {{4}} saat,
            #                       {{5}} hizmet, {{6}} kapora, {{7}} işletmede ödenecek,
            #                       {{8}} iletişim
            if has_location:
                body = _build_body([
                    customer_name, company_name,
                    formatted_date, appointment_time,
                    service_name, support_phone,
                    amount_paid, amount_paid, on_site_amount,
                ])
            else:
                body = _build_body([
                    customer_name, amount_paid,
                    formatted_date, appointment_time, service_name,
                    amount_paid, on_site_amount, support_phone,
                ])
        elif template_type_upper == "CONFIRMATION":
            if has_location:
                # randevu_onay_konumlu_v2 (TR/EN) — değişmedi, 6 param
                # {{1}} müşteri, {{2}} işletme, {{3}} tarih, {{4}} saat, {{5}} hizmet, {{6}} iletişim
                body = _build_body([
                    customer_name, company_name,
                    formatted_date, appointment_time, service_name,
                    support_phone,
                ])
            else:
                # randevu_onay_metin (TR) / randevu_onay_metin_eng_v2 (EN) — YENİ 5-param içerik
                # {{1}} müşteri, {{2}} tarih, {{3}} saat, {{4}} hizmet, {{5}} iletişim
                body = _build_body([
                    customer_name,
                    formatted_date, appointment_time, service_name,
                    support_phone,
                ])
        else:
            # REMINDER — değişmedi
            # Konumlu (6): {{1}} müşteri, {{2}} işletme, {{3}} tarih, {{4}} saat, {{5}} hizmet, {{6}} iletişim
            # Metin   (7): + {{7}} adres
            if has_location:
                body = _build_body([
                    customer_name, company_name,
                    formatted_date, appointment_time, service_name,
                    support_phone,
                ])
            else:
                location_fallback = "Konum girilmedi" if language == "TR" else "Location not provided"
                location_text = _normalise_template_var(business_address, fallback=location_fallback)
                body = _build_body([
                    customer_name, company_name,
                    formatted_date, appointment_time, service_name,
                    support_phone, location_text,
                ])

        if template_name in TEMPLATES_WITHOUT_HEADER:
            components = [body]
        else:
            components = [header, body]

        logger.info(
            f"WhatsApp gönderimi → type={template_type_upper} lang={language} "
            f"template={template_name} header={'no' if template_name in TEMPLATES_WITHOUT_HEADER else 'yes'} "
            f"senaryo={'A (konumlu)' if has_location else 'B (metin)'} to={to_number}"
        )

        message_id = send_meta_whatsapp_template(
            to_number=to_number,
            template_name=template_name,
            language_code=lang_code,
            components=components,
        )

        logger.info(f"WhatsApp (Meta) gönderildi. id={message_id} to={to_number}")
        return message_id

    except Exception as e:
        logger.error(f"send_whatsapp_template hatası [{to_number}]: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

# ============================================================================
# TEST FONKSİYONU
# ============================================================================

if __name__ == "__main__":
    print("Meta WhatsApp Cloud API — Entegrasyon Testi")
    print("=" * 60)

    # Test 1: TR — Senaryo A (Konumlu Onay)
    r1 = send_whatsapp_template(
        to_number="+905551234567", template_type="CONFIRMATION",
        customer_name="Ahmet Yılmaz", company_name="Royal Premium Care",
        appointment_date="2025-04-25", appointment_time="14:20",
        service_name="Halı Yıkama", support_phone="05321234567",
        business_lat=38.6248, business_lng=34.7142, business_address="Nevşehir Merkez",
    )
    print(f"Test 1 — TR Onay (Konumlu):     {r1}")

    # Test 2: TR — Senaryo B (Metin Hatırlatma)
    r2 = send_whatsapp_template(
        to_number="+905559876543", template_type="REMINDER",
        customer_name="Fatma Kaya", company_name="Royal Premium Care",
        appointment_date="2025-04-25", appointment_time="11:00",
        service_name="Saç Kesimi", support_phone="05321234567",
        business_address="Atatürk Cad. No:5, Nevşehir",
    )
    print(f"Test 2 — TR Hatırlatma (Metin): {r2}")

    # Test 3: EN — Senaryo A (Konumlu Onay)
    r3 = send_whatsapp_template(
        to_number="+441234567890", template_type="CONFIRMATION",
        customer_name="John Doe", company_name="Royal Premium Care",
        appointment_date="2025-04-25", appointment_time="14:20",
        service_name="Haircut", support_phone="+44201234567",
        business_lat=51.5074, business_lng=-0.1278,
        business_address="123 Oxford Street, London",
    )
    print(f"Test 3 — EN Onay (Konumlu):     {r3}")

    # Test 4: EN — Senaryo B (Metin Hatırlatma)
    r4 = send_whatsapp_template(
        to_number="+441234567891", template_type="REMINDER",
        customer_name="Jane Smith", company_name="Royal Premium Care",
        appointment_date="2025-04-25", appointment_time="15:00",
        service_name="Massage", support_phone="+44201234567",
    )
    print(f"Test 4 — EN Hatırlatma (Metin): {r4}")

    print("=" * 60)
    print("Test tamamlandı.")
