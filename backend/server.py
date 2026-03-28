from voice_ai_service import get_voice_ai_service
from whatsapp_service import send_whatsapp_template, detect_language_from_phone
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request, Response, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Dict
import uuid
from datetime import datetime, timezone, timedelta
import requests
from zoneinfo import ZoneInfo
import re
import xml.etree.ElementTree as ET
import hashlib
import hmac
import base64
import json
import secrets
import io
from PIL import Image as PilImage
import openpyxl
import csv

from contextlib import asynccontextmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import socketio
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pywebpush import webpush, WebPushException

# (Cache ve Rate Limit importları, sizin projenizden alındı)
from cache import init_redis, invalidate_cache, cache_result
from rate_limit import initialize_limiter, rate_limit, LIMITS
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

import firebase_admin
from firebase_admin import credentials, messaging

# === SENTRY ERROR TRACKING ===
import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    send_default_pii=True,
    traces_sample_rate=0.2,  # %20 performance tracing (production için yeterli)
    profiles_sample_rate=0.1,
    environment=os.environ.get("SENTRY_ENV", "production"),
)

# Firebase Initialization moved to lifespan() for proper logging

# AI Service Import
import ai_service
from ai_service import chat_with_ai

# === LOGGING AYARLARI ===
logging.basicConfig(
    level=logging.INFO,  # INFO level for production
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/backend.log')
    ],
    force=True  # Mevcut yapılandırmayı zorla güncelle
)
logger = logging.getLogger("server")  # Logger adını sabit yap
logger.setLevel(logging.INFO)  # Logger seviyesini açıkça ayarla
# Enable socketio server logging
logging.getLogger('socketio.server').setLevel(logging.INFO)
logging.getLogger('engineio.server').setLevel(logging.INFO)

# === GÜVENLİK AYARLARI ===
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_karmaşık_bir_secret_key_ekleyin_mutlaka')
if SECRET_KEY == 'default_karmaşık_bir_secret_key_ekleyin_mutlaka':
    logging.warning("WARNING: JWT_SECRET_KEY is using default value! Please set a secure secret key in production.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

# --- ROOT DİZİN VE .ENV YÜKLEME ---
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# --- SABİT SMS AYARLARI ---
ILETIMERKEZI_API_KEY = os.environ.get('ILETIMERKEZI_API_KEY')
ILETIMERKEZI_HASH = os.environ.get('ILETIMERKEZI_HASH')
ILETIMERKEZI_SENDER = os.environ.get('ILETIMERKEZI_SENDER', 'FatihSenyuz') 
SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() in ('1', 'true', 'yes')
AUDIT_LOGS_ENABLED = os.environ.get('AUDIT_LOGS_ENABLED', 'false').lower() in ('1', 'true', 'yes')

# --- STRIPE ÖDEME AYARLARI ---
import stripe

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY") 
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Stripe'ı yapılandır
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("✅ Stripe API key configured")
else:
    logger.warning("⚠️ STRIPE_SECRET_KEY not configured. Payment features will not work.")

# Success ve Cancel URL'leri
PAYMENT_SUCCESS_URL = "https://plannapp.co/"
PAYMENT_SUCCESS_URL_NATIVE = "plannapp://payment-success"
# Native app için deep link, web için normal URL
PAYMENT_CANCEL_URL = "https://plannapp.co/dashboard"
PAYMENT_CANCEL_URL_NATIVE = "plannapp://dashboard"

# --- PUSH NOTIFICATION AYARLARI ---
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', 'BB4nvNoHrWlWS6KTM1ybHUZD260l8b7Nnr2bMHvwnbflCJ4OJVd68Dqmw1hpaOFFUNmRFySvP3Ewzm596xjqF7g')
# Private key - base64 encoded raw key (pywebpush format)
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '5V68PoLSQ16LLymN-Wur5MwrJk1Q9b3HvS6ijdGDtAM')
if VAPID_PRIVATE_KEY:
    logger.info("✅ VAPID private key configured")
else:
    logger.warning("⚠️ VAPID_PRIVATE_KEY not configured. Push notifications will not work.")
VAPID_CLAIMS = {
    "sub": "mailto:info@plannapp.co"
}

# --- BREVO EMAIL AYARLARI ---
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
if BREVO_API_KEY:
    try:
        brevo_configuration = sib_api_v3_sdk.Configuration()
        brevo_configuration.api_key['api-key'] = BREVO_API_KEY
        brevo_api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(brevo_configuration))
        logging.info("✅ Brevo API instance başarıyla oluşturuldu.")
    except Exception as e:
        logging.error(f"❌ Brevo API instance oluşturulamadı: {str(e)}")
        brevo_api_instance = None
else:
    brevo_api_instance = None
    logging.warning("⚠️ BREVO_API_KEY bulunamadı! E-posta gönderimi devre dışı.")

async def send_email(to_email: str, subject: str, html_content: str, to_name: str = None, sender_name: str = "PLANN", sender_email: str = "noreply@plannapp.co"):
    """Brevo API ile e-posta gönder - Global helper fonksiyon (async)"""
    global brevo_api_instance
    try:
        logging.info(f"📧 [SEND_EMAIL] E-posta gönderme başlatılıyor: {to_email} - Subject: {subject}")
        logging.info(f"📧 [SEND_EMAIL] Sender: {sender_name} <{sender_email}>")
        logging.info(f"📧 [SEND_EMAIL] To: {to_name or to_email}")
        
        # Runtime'da API key'i tekrar kontrol et
        current_api_key = os.environ.get('BREVO_API_KEY')
        logging.info(f"🔑 BREVO_API_KEY kontrol: {'Var' if current_api_key else 'YOK'} - Uzunluk: {len(current_api_key) if current_api_key else 0}")
        
        if not brevo_api_instance:
            logging.warning("❌ Brevo API instance bulunamadı! E-posta gönderilemedi.")
            # Runtime'da instance oluşturmayı dene
            if current_api_key:
                try:
                    logging.info("🔄 Runtime'da Brevo API instance oluşturuluyor...")
                    brevo_configuration = sib_api_v3_sdk.Configuration()
                    brevo_configuration.api_key['api-key'] = current_api_key
                    brevo_api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(brevo_configuration))
                    logging.info("✅ Runtime'da Brevo API instance oluşturuldu!")
                except Exception as e:
                    logging.error(f"❌ Runtime'da Brevo API instance oluşturulamadı: {e}")
                    return False
            else:
                return False
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email, "name": to_name or to_email}]
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to,
            sender=sender,
            subject=subject,
            html_content=html_content
        )
        
        # Async context'te sync API çağrısını thread pool'da çalıştır
        import asyncio
        logging.info(f"📤 Brevo API'ye e-posta gönderiliyor...")
        api_response = await asyncio.to_thread(brevo_api_instance.send_transac_email, send_smtp_email)
        logging.info(f"✅ E-posta başarıyla gönderildi: {to_email} - Subject: {subject} - Message ID: {api_response.message_id}")
        return True
    except ApiException as e:
        logging.error(f"❌ E-posta gönderilirken Brevo API hatası: {e.status} - {e.reason} - {e.body}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    except Exception as e:
        logging.error(f"❌ E-posta gönderilirken beklenmedik hata: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

# Subscription email helpers
def _get_domain_from_request(request: Request) -> str:
    try:
        from urllib.parse import urlparse

        raw_host = (request.headers.get('host') or '').strip()
        raw_origin = (request.headers.get('origin') or '').strip()
        raw_referer = (request.headers.get('referer') or '').strip()

        def _extract_host(value: str) -> str:
            if not value:
                return ''
            value = value.strip()
            if value.startswith('http://') or value.startswith('https://'):
                parsed = urlparse(value)
                value = parsed.netloc
            # strip port
            if ':' in value:
                value = value.split(':', 1)[0]
            return value.lower()

        # Prefer Origin/Referer (browser) to preserve www/non-www exactly, then Host
        candidates = [
            _extract_host(raw_origin),
            _extract_host(raw_referer),
            _extract_host(raw_host),
        ]

        allowed_suffixes = (
            'plannapp.co.uk',
            'plannapp.co',
            'plannapp.com.tr',
            'plannapp.com',
        )

        for c in candidates:
            if not c:
                continue
            if any(c == sfx or c.endswith('.' + sfx) for sfx in allowed_suffixes):
                return c

        return 'plannapp.co'
    except Exception:
        return 'plannapp.co'


def _get_lang_from_domain(domain: str) -> str:
    domain = (domain or '').lower()
    if 'plannapp.co.uk' in domain:
        return 'en'
    return 'tr'


def _build_subscription_email(lang: str, full_name: str, plan_name: str, billing_cycle: str, dashboard_url: str) -> tuple[str, str]:
    safe_name = full_name or ''
    safe_plan = plan_name or ''
    cycle = (billing_cycle or 'monthly').lower()
    if lang == 'en':
        subject = "Your PLANN subscription is now active"
        cycle_label = "Yearly" if cycle == 'yearly' else "Monthly"
        logo_url = "https://plannapp.co/api/static/logo.png"
        html_content = f"""
        <html>
          <body style=\"margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;\">
            <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\">
              <tr>
                <td align=\"center\" style=\"padding: 20px 0;\">
                  <table width=\"600\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);\">
                    <tr>
                      <td align=\"center\" style=\"padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;\">
                        <img src=\"{logo_url}\" alt=\"PLANN Logo\" style=\"max-width: 150px; height: auto;\">
                      </td>
                    </tr>
                    <tr style=\"background-color: #ffffff;\">
                      <td style=\"padding: 40px 30px; color: #333333; font-size: 16px;\">
                        <h1 style=\"font-size: 24px; color: #111111; margin-top: 0; text-align: center;\">Your subscription is active!</h1>
                        <p>Hello {safe_name or 'there'},</p>
                        <p>Your PLANN subscription has been successfully activated.</p>
                        <p><strong>Plan:</strong> {safe_plan}</p>
                        <p><strong>Billing:</strong> {cycle_label}</p>
                        <p style=\"text-align: center; margin-top: 30px; margin-bottom: 30px;\">
                          You can now continue using PLANN with your new plan.
                        </p>
                      </td>
                    </tr>
                    <tr style=\"background-color: #ffffff;\">
                      <td align=\"center\" style=\"padding: 0 30px 40px 30px;\">
                        <a href=\"{dashboard_url}\" target=\"_blank\" style=\"background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;\">
                          Go to Dashboard
                        </a>
                      </td>
                    </tr>
                    <tr style=\"background-color: #f9f9f9;\">
                      <td align=\"center\" style=\"padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;\">
                        <p>© 2025 PLANN. All rights reserved.</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """
        return subject, html_content

    subject = "PLANN aboneliğiniz aktif edildi"
    cycle_label = "Yıllık" if cycle == 'yearly' else "Aylık"
    logo_url = "https://plannapp.co/api/static/logo.png"
    html_content = f"""
    <html>
      <body style=\"margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;\">
        <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\">
          <tr>
            <td align=\"center\" style=\"padding: 20px 0;\">
              <table width=\"600\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);\">
                <tr>
                  <td align=\"center\" style=\"padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;\">
                    <img src=\"{logo_url}\" alt=\"PLANN Logosu\" style=\"max-width: 150px; height: auto;\">
                  </td>
                </tr>
                <tr style=\"background-color: #ffffff;\">
                  <td style=\"padding: 40px 30px; color: #333333; font-size: 16px;\">
                    <h1 style=\"font-size: 24px; color: #111111; margin-top: 0; text-align: center;\">Aboneliğiniz aktif edildi!</h1>
                    <p>Merhaba {safe_name or ' '},</p>
                    <p>Ödemeniz başarıyla alındı ve aboneliğiniz aktif edildi.</p>
                    <p><strong>Paket:</strong> {safe_plan}</p>
                    <p><strong>Dönem:</strong> {cycle_label}</p>
                    <p style=\"text-align: center; margin-top: 30px; margin-bottom: 30px;\">
                      Artık yeni paketinizle PLANN'ı kullanmaya devam edebilirsiniz.
                    </p>
                  </td>
                </tr>
                <tr style=\"background-color: #ffffff;\">
                  <td align=\"center\" style=\"padding: 0 30px 40px 30px;\">
                    <a href=\"{dashboard_url}\" target=\"_blank\" style=\"background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;\">
                      Panele git
                    </a>
                  </td>
                </tr>
                <tr style=\"background-color: #f9f9f9;\">
                  <td align=\"center\" style=\"padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;\">
                    <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    return subject, html_content


async def _send_subscription_email_once(
    db,
    request: Request,
    organization_id: str,
    session_id: str,
    plan_name: str,
    billing_cycle: str,
    payment_log: Optional[dict] = None,
    admin_user: Optional[dict] = None,
):
    if not session_id:
        return
    if payment_log and payment_log.get('subscription_email_sent') is True:
        return

    if not admin_user:
        admin_user = await db.users.find_one({"organization_id": organization_id, "role": "admin"})
    if not admin_user:
        logger.warning(f"Subscription email: admin user bulunamadı - org={organization_id}")
        return

    to_email = admin_user.get('username')
    to_name = admin_user.get('full_name')
    if not to_email:
        logger.warning(f"Subscription email: admin email bulunamadı - org={organization_id}")
        return

    domain = _get_domain_from_request(request)
    lang = _get_lang_from_domain(domain)
    dashboard_url = f"https://{domain}"
    subject, html_content = _build_subscription_email(lang, to_name, plan_name, billing_cycle, dashboard_url)

    sent_ok = await send_email(to_email=to_email, subject=subject, html_content=html_content, to_name=to_name)
    if sent_ok:
        now = datetime.now(timezone.utc).isoformat()
        await db.payment_logs.update_one(
            {"session_id": session_id},
            {"$set": {"subscription_email_sent": True, "subscription_email_sent_at": now, "subscription_email_lang": lang}},
            upsert=True
        )

# === SMS REMINDER SCHEDULER ===
scheduler = AsyncIOScheduler()
_app_instance = None  # Global app instance for scheduler

async def check_and_send_reminders():
    """Her 5 dakikada bir yaklaşan randevuları kontrol et ve WhatsApp hatırlatması gönder"""
    try:
        logging.info("=== WhatsApp Reminder Check Started ===")
        # Global app instance'ından db'yi al
        global _app_instance
        if _app_instance is None:
            logging.warning("App instance not available, skipping reminder check")
            return
        
        db = getattr(_app_instance, 'db', None)
        if db is None:
            logging.warning("MongoDB not available, skipping reminder check")
            return
        
        turkey_tz = ZoneInfo("Europe/Istanbul")
        now = datetime.now(turkey_tz)

        # DISTRIBUTED LOCK: multi-worker duplicate send prevention
        redis_client = getattr(_app_instance, 'redis_client', None)
        if redis_client:
            try:
                lock_key = f"reminder_lock:{now.strftime('%Y%m%d%H%M')}"
                if not await redis_client.set(lock_key, "1", nx=True, ex=300):
                    logging.info("Reminder check skipped - another worker holds the lock")
                    return
                logging.info(f"Distributed lock acquired: {lock_key}")
            except Exception as lock_err:
                logging.warning(f"Redis lock unavailable, proceeding without lock: {lock_err}")

        logging.info(f"Current time (Turkey): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Tüm organization'ların ayarlarını al
        all_settings = await db.settings.find({}, {"_id": 0}).to_list(1000)
        logging.info(f"Found {len(all_settings)} organizations to check")
        
        for setting in all_settings:
            org_id = setting.get('organization_id')
            reminder_hours = setting.get('sms_reminder_hours', 1.0)
            company_name = setting.get('company_name', 'İşletmeniz')
            support_phone = setting.get('support_phone', 'Destek')
            
            logging.info(f"Checking org {org_id}: reminder_hours={reminder_hours}, company={company_name}")
            
            # Hatırlatma zaman aralığını hesapla
            reminder_time_start = now + timedelta(hours=reminder_hours - 0.1)  # 6 dakika tolerance
            reminder_time_end = now + timedelta(hours=reminder_hours + 0.1)
            
            logging.info(f"  Reminder window: {reminder_time_start.strftime('%Y-%m-%d %H:%M:%S')} to {reminder_time_end.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Bu zaman aralığındaki randevuları bul
            appointments = await db.appointments.find({
                "organization_id": org_id,
                "status": "Bekliyor",
                "reminder_sent": {"$ne": True}  # Daha önce hatırlatma gönderilmemiş
            }, {"_id": 0}).to_list(1000)
            
            logging.info(f"  Found {len(appointments)} pending appointments without reminder")
            
            for apt in appointments:
                try:
                    # Randevu zamanını parse et
                    apt_datetime_str = f"{apt['appointment_date']} {apt['appointment_time']}"
                    apt_datetime = datetime.strptime(apt_datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=turkey_tz)
                    
                    logging.debug(f"  Appointment {apt.get('id')}: {apt_datetime_str} (parsed: {apt_datetime.strftime('%Y-%m-%d %H:%M:%S')})")
                    
                    # Hatırlatma zamanı geldi mi?
                    if reminder_time_start <= apt_datetime <= reminder_time_end:
                        # Atomic claim: only one worker can proceed (race condition fix)
                        claimed = await db.appointments.find_one_and_update(
                            {"id": apt['id'], "reminder_sent": {"$ne": True}},
                            {"$set": {"reminder_sent": True}},
                        )
                        if claimed is None:
                            logging.info(f"  Appointment {apt.get('id')} already claimed by another worker, skipping")
                            continue
                        logging.info(f"  Appointment {apt.get('id')} claimed. Sending WhatsApp...")
                        import asyncio
                        business = setting or {}
                        settings = business.get('settings') if isinstance(business.get('settings'), dict) else business
                        location = (settings or {}).get('location') or {}
                        coords = (location or {}).get('coordinates', {})
                        lat = coords.get('lat')
                        lng = coords.get('lng')
                        try:
                            wa_result = await asyncio.to_thread(
                                send_whatsapp_template,
                                apt['phone'], "REMINDER", apt['customer_name'],
                                company_name, apt['appointment_date'], apt['appointment_time'],
                                apt['service_name'], support_phone,
                                business_lat=lat, business_lng=lng,
                                business_address=location.get('address'),
                            )
                            logging.info(f"  WhatsApp reminder sent to {apt['customer_name']} ({apt['phone']}) apt={apt['id']}")
                            try:
                                import time as _time
                                _phone = str(apt['phone']).lstrip('+')
                                await db.whatsapp_message_logs.update_one(
                                    {"message_id": wa_result},
                                    {"$set": {"message_id": wa_result, "recipient": _phone,
                                              "status": "sent", "timestamp": int(_time.time()),
                                              "recorded_at": datetime.utcnow().isoformat(), "source": "reminder"}},
                                    upsert=True
                                )
                            except Exception:
                                pass
                        except Exception as send_err:
                            # Rollback so next scheduler run can retry
                            await db.appointments.update_one({"id": apt['id']}, {"$set": {"reminder_sent": False}})
                            raise send_err
                    else:
                        logging.debug(f"  - Appointment {apt.get('id')} is not in reminder window (time: {apt_datetime.strftime('%Y-%m-%d %H:%M:%S')})")
                
                except Exception as e:
                    logging.error(f"Error sending reminder for appointment {apt.get('id')}: {e}", exc_info=True)
                    try:
                        import time as _time
                        _phone = str(apt.get('phone', '')).lstrip('+')
                        await db.whatsapp_message_logs.update_one(
                            {"message_id": f"fail_{_phone}_{int(_time.time())}"},
                            {"$set": {
                                "recipient": _phone,
                                "status": "failed",
                                "timestamp": int(_time.time()),
                                "recorded_at": datetime.utcnow().isoformat(),
                                "errors": [{"code": "SEND_ERROR", "title": str(e)[:300]}],
                                "source": "reminder"
                            }},
                            upsert=True
                        )
                    except Exception:
                        pass
        
        logging.info("=== WhatsApp Reminder Check Completed ===")
    
    except Exception as e:
        logging.error(f"Error in check_and_send_reminders: {e}", exc_info=True)

# === Recurring Payment Checker (Her gün çalışır) ===
async def check_and_process_recurring_payments():
    """Vadesi gelen recurring payment'leri işle"""
    try:
        logging.info("=== Recurring Payment Check Started ===")
        
        if _app_instance is None or _app_instance.db is None:
            logging.warning("Database not available for recurring payment check")
            return
        
        db = _app_instance.db
        today = datetime.now(timezone.utc).date()
        today_str = today.isoformat()
        
        # Bugün ödeme günü olan organizasyonları bul
        cursor = db.organization_plans.find({
            "card_saved": True,
            "next_billing_date": {"$lte": datetime.now(timezone.utc).isoformat()},
            "plan_id": {"$ne": "tier_trial"}  # Trial paketleri hariç
        })
        
        organizations = await cursor.to_list(length=1000)
        logging.info(f"Found {len(organizations)} organizations with due payments")
        
        for org_plan in organizations:
            organization_id = org_plan.get('organization_id')
            plan_id = org_plan.get('plan_id')
            
            try:
                logging.info(f"Processing recurring payment for organization: {organization_id}, plan: {plan_id}")
                
                # Ödeme çek (internal API call simulation)
                # Gerçek implementasyonda recurring payment endpoint'ini çağır
                utoken = org_plan.get('payment_utoken')
                ctoken = org_plan.get('payment_ctoken')
                
                if not utoken or not ctoken:
                    logging.error(f"Missing payment tokens for organization: {organization_id}")
                    continue
                
                # Plan bilgilerini al
                plan_info = await get_plan_info(plan_id)
                if not plan_info:
                    logging.error(f"Plan info not found: {plan_id}")
                    continue
                
                price_monthly = plan_info.get('price_monthly', 0)
                payment_amount_kurus = int(price_monthly * 100)
                
                # Organization admin'ini bul
                user = await db.users.find_one({"organization_id": organization_id, "role": "admin"})
                if not user:
                    logging.error(f"Admin user not found for organization: {organization_id}")
                    continue
                
                user_email = user.get('username', 'noreply@royalpremiumcare.com')
                user_name = user.get('full_name', 'Kullanıcı')
                
                # Settings'den bilgi al
                settings = await db.settings.find_one({"organization_id": organization_id})
                user_address = settings.get('address', 'Adres Bilgisi Yok') if settings else 'Adres Bilgisi Yok'
                user_phone = settings.get('support_phone', '05000000000') if settings else '05000000000'
                
                # Merchant OID oluştur
                org_id_clean = organization_id.replace('-', '')
                timestamp_str = str(int(datetime.now(timezone.utc).timestamp()))
                merchant_oid = f"AUTO{org_id_clean}{timestamp_str}"
                
                # Sepet bilgisi
                plan_name = plan_info.get('name', 'Plan')
                user_basket = base64.b64encode(json.dumps([
                    [plan_name, str(price_monthly), 1]
                ]).encode('utf-8')).decode('utf-8')
                
                # PayTR parametreleri
                user_ip = "127.0.0.1"  # Sistem iç çağrısı
                payment_type = 'card'
                currency = 'TL'
                test_mode = '0'
                non_3d = '1'
                
                # Hash oluştur
                hash_str = f"{PAYTR_MERCHANT_ID}{user_ip}{merchant_oid}{user_email}{payment_amount_kurus}{payment_type}0{currency}{test_mode}{non_3d}"
                paytr_token = base64.b64encode(hmac.new(
                    PAYTR_MERCHANT_KEY.encode('utf-8'), 
                    hash_str.encode('utf-8') + PAYTR_MERCHANT_SALT.encode('utf-8'), 
                    hashlib.sha256
                ).digest()).decode('utf-8')
                
                # PayTR'a istek gönder
                post_data = {
                    'merchant_id': PAYTR_MERCHANT_ID,
                    'user_ip': user_ip,
                    'merchant_oid': merchant_oid,
                    'email': user_email,
                    'payment_type': payment_type,
                    'payment_amount': payment_amount_kurus,
                    'currency': currency,
                    'test_mode': test_mode,
                    'non_3d': non_3d,
                    'merchant_ok_url': PAYTR_SUCCESS_URL,
                    'merchant_fail_url': PAYTR_FAIL_URL,
                    'user_name': user_name,
                    'user_address': user_address[:400],
                    'user_phone': user_phone[:20],
                    'user_basket': user_basket,
                    'debug_on': '1',
                    'paytr_token': paytr_token,
                    'utoken': utoken,
                    'ctoken': ctoken,
                    'installment_count': '0'
                }
                
                # Payment log oluştur
                payment_log = {
                    "merchant_oid": merchant_oid,
                    "organization_id": organization_id,
                    "plan_id": plan_id,
                    "amount": price_monthly,
                    "status": "pending",
                    "payment_type": "auto_recurring",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.payment_logs.insert_one(payment_log)
                
                # PayTR'a istek gönder
                response = requests.post("https://www.paytr.com/odeme", data=post_data, timeout=15)
                
                if response.status_code == 200:
                    res_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    if res_data.get('status') == 'success':
                        logging.info(f"✓ Auto recurring payment successful for organization: {organization_id}")
                        
                        # Bir sonraki ödeme tarihini güncelle (30 gün sonra)
                        next_billing = datetime.now(timezone.utc) + timedelta(days=30)
                        await db.organization_plans.update_one(
                            {"organization_id": organization_id},
                            {"$set": {
                                "next_billing_date": next_billing.isoformat(),
                                "last_payment_date": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                    else:
                        error_msg = res_data.get('reason', 'Bilinmeyen hata')
                        logging.error(f"✗ Auto recurring payment failed for {organization_id}: {error_msg}")
                        
                        # Başarısız ödeme kaydını güncelle
                        await db.payment_logs.update_one(
                            {"merchant_oid": merchant_oid},
                            {"$set": {"status": "failed", "failed_reason": error_msg}}
                        )
                        
                        # Retry için 3 gün sonraya ertele
                        retry_date = datetime.now(timezone.utc) + timedelta(days=3)
                        await db.organization_plans.update_one(
                            {"organization_id": organization_id},
                            {"$set": {
                                "next_billing_date": retry_date.isoformat(),
                                "payment_retry_count": org_plan.get('payment_retry_count', 0) + 1,
                                "last_payment_attempt": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                        
                        # TODO: Admin'e e-posta gönder
                else:
                    logging.error(f"✗ PayTR HTTP error for {organization_id}: {response.status_code}")
                
            except Exception as e:
                logging.error(f"Error processing recurring payment for {organization_id}: {e}", exc_info=True)
        
        logging.info("=== Recurring Payment Check Completed ===")
    
    except Exception as e:
        logging.error(f"Error in check_and_process_recurring_payments: {e}", exc_info=True)

# === MongoDB ve Redis Yaşam Döngüsü (Lifespan) --- SYNTAX HATASI DÜZELTİLDİ ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_instance
    _app_instance = app  # Global app instance'ı sakla (scheduler için)
    app.mongodb_client = None; app.db = None; app.redis_client = None
    try:
        logging.info("Step 1: Connecting to MongoDB..."); mongo_url = os.environ.get('MONGO_URL'); db_name = os.environ.get('DB_NAME', 'royal_koltuk_dev')
        if not mongo_url:
            logging.error("CRITICAL: MONGO_URL environment variable is required!"); logging.warning("MongoDB connection will be lazy-initialized on first request.")
        else:
            try:
                app.mongodb_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000); await app.mongodb_client.admin.command('ping')
                app.db = app.mongodb_client[db_name]; logging.info(f"Step 1 SUCCESS: Successfully connected to MongoDB ({db_name})!")
            except Exception as mongo_error:
                logging.warning(f"MongoDB connection failed during startup: {mongo_error}"); logging.info("MongoDB will be lazy-initialized on first request.")
    except Exception as e:
        logging.warning(f"WARNING during MongoDB connection: {type(e).__name__}: {str(e)}"); app.mongodb_client = None; app.db = None
    try:
        logging.info("Step 2: Initializing Redis..."); app.state.redis_client = await init_redis() # <--- BURASI DEĞİŞTİ
        if app.state.redis_client:
            try: await app.state.redis_client.ping(); logging.info("Step 2 SUCCESS: Redis initialized and ping successful.")
            except Exception as redis_ping_error: logging.warning(f"Redis ping failed: {redis_ping_error}"); app.state.redis_client = None
        else: logging.warning("WARNING: Redis client could not be initialized (init_redis returned None).")
    except Exception as e:
        logging.warning(f"WARNING during Redis connection: {type(e).__name__}: {str(e)}"); app.state.redis_client = None
    try:
        logging.info("Step 3: Initializing Rate Limiter...")
        if app.redis_client is None: logging.warning("WARNING: Using dummy Rate Limiter due to failed Redis connection.")
        app.state.limiter = initialize_limiter(app.redis_client); logging.info("Step 3 SUCCESS: Rate Limiter initialized.")
    except Exception as e:
        logging.warning(f"WARNING during Rate Limiter initialization: {type(e).__name__}: {str(e)}"); app.state.limiter = None
    
    try:
        logging.info("Step 4: Starting Schedulers...")
        # WhatsApp Reminder Job - Her 5 dakikada bir (WhatsApp hatırlatmaları için)
        # NOT: Bu job WhatsApp gönderiyor, SMS değil. SMS_ENABLED kontrolü yapılmıyor.
        scheduler.add_job(
            check_and_send_reminders, 
            IntervalTrigger(minutes=5), 
            id='whatsapp_reminder_job',
            replace_existing=True,
            max_instances=1  # Aynı anda sadece bir instance çalışsın
        )
        logging.info("  - WhatsApp Reminder: Enabled (Every 5 minutes)")
        
        # Recurring Payment Job - Her gün saat 02:00'de (UTC)
        from apscheduler.triggers.cron import CronTrigger
        scheduler.add_job(
            check_and_process_recurring_payments,
            CronTrigger(hour=2, minute=0),  # Her gün 02:00
            id='recurring_payment_job',
            replace_existing=True,
            max_instances=1
        )
        
        scheduler.start()
        logging.info("Step 4 SUCCESS: Schedulers started")
        logging.info("  - Recurring Payments: Daily at 02:00 UTC")
        
        # İlk WhatsApp hatırlatma kontrolünü hemen yap
        import asyncio
        asyncio.create_task(check_and_send_reminders())
    except Exception as e:
        logging.error(f"ERROR during Scheduler initialization: {type(e).__name__}: {str(e)}", exc_info=True)
    
    try:
        logging.info("Step 5: Creating Database Indexes...")
        if app.db is not None:
            # Appointments indexes - Performance optimization
            await app.db.appointments.create_index([("organization_id", 1), ("appointment_date", -1)])
            await app.db.appointments.create_index([("organization_id", 1), ("staff_member_id", 1)])
            await app.db.appointments.create_index([("organization_id", 1), ("phone", 1)])
            await app.db.appointments.create_index([("organization_id", 1), ("status", 1)])
            
            # Users indexes
            await app.db.users.create_index([("organization_id", 1), ("role", 1)])
            try:
                await app.db.users.create_index([("slug", 1)], unique=True, sparse=True)
            except Exception as idx_err:
                # Index might already exist or have duplicate null values, skip
                logging.debug(f"Users slug index creation skipped: {idx_err}")
            
            # Settings indexes
            await app.db.settings.create_index([("organization_id", 1)], unique=True)
            try:
                await app.db.settings.create_index([("slug", 1)], unique=True, sparse=True)
            except Exception as idx_err:
                # Index might already exist or have duplicate null values, skip
                logging.debug(f"Settings slug index creation skipped: {idx_err}")
            
            # Contact requests indexes
            await app.db.contact_requests.create_index([("created_at", -1)])
            await app.db.contact_requests.create_index([("status", 1)])
            
            logging.info("Step 5 SUCCESS: Database indexes created")
        else:
            logging.warning("Step 5 SKIPPED: Database not available")
    except Exception as e:
        logging.warning(f"WARNING during Index creation: {type(e).__name__}: {str(e)}")

    # Step 6: Firebase Admin SDK
    try:
        logging.info("Step 6: Initializing Firebase Admin SDK...")
        if not firebase_admin._apps:
            firebase_cred_path = os.path.join(os.path.dirname(__file__), "firebase-admin-key.json")
            logging.info(f"  Firebase key path: {firebase_cred_path}, exists: {os.path.exists(firebase_cred_path)}")
            if os.path.exists(firebase_cred_path):
                cred = credentials.Certificate(firebase_cred_path)
                firebase_admin.initialize_app(cred)
                logging.info("Step 6 SUCCESS: ✅ Firebase Admin SDK initialized")
            else:
                logging.warning("Step 6 SKIPPED: ⚠️ firebase-admin-key.json not found")
        else:
            logging.info("Step 6 SUCCESS: Firebase Admin SDK already initialized")
    except Exception as e:
        logging.error(f"Step 6 FAILED: ❌ Firebase initialization error: {e}", exc_info=True)

    yield

    # --- Cleanup blokları ---
    # NOT: Scheduler'ı cleanup'ta kapatma - uygulama çalışırken scheduler aktif kalmalı
    # Sadece uygulama kapanırken kapatılmalı
    logging.info("Application shutdown initiated...")
    # Global app instance'ı temizle (global değişken, direkt atama yapılabilir)
    # _app_instance zaten global scope'ta tanımlı, burada sadece None yapıyoruz
    if scheduler.running:
        logging.info("Stopping WhatsApp Reminder Scheduler...")
        try: 
            scheduler.shutdown(wait=False)
            logging.info("WhatsApp Reminder Scheduler stopped")
        except Exception as e:
            logging.error(f"Error stopping scheduler: {e}")
    if app.mongodb_client:
        logging.info("Closing MongoDB connection...")
        try: app.mongodb_client.close()
        except: pass
    # hasattr veya getattr kullanarak güvenli bir şekilde kapatıyoruz
    if getattr(app.state, 'redis_client', None):
        logging.info("Closing Redis connection...")
        try: await app.state.redis_client.close()
        except: pass

# Create the main app
app = FastAPI(title="Randevu SaaS API", description="... (Açıklamanız buradaydı) ...", version="1.4.2 (Final Fixes)", lifespan=lifespan)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# === SOCKET.IO SETUP ===
# Get CORS origins for Socket.IO (same as FastAPI CORS)
cors_origins_for_socketio = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_for_socketio == '*':
    socketio_cors_origins = '*'
else:
    socketio_cors_origins = [origin.strip() for origin in cors_origins_for_socketio.split(',') if origin.strip()]

mgr = socketio.AsyncRedisManager('redis://plann_redis:6379/0')

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    client_manager=mgr,  # 🚀 İŞTE BU! 4 işçiyi birbirine bağlayan hat.
    logger=True,
    engineio_logger=True
)
socket_app = socketio.ASGIApp(sio, socketio_path='/api/socket.io', other_asgi_app=app)

# Set socketio instance for AI service
ai_service.set_socketio(sio)

# --- Router prefix'i kaldırıldı ---
api_router = APIRouter()

# === SOCKET.IO EVENT HANDLERS ===
@sio.event
async def connect(sid, environ, *args):
    """Client connected - with authentication"""
    logger.info(f"🔵 [CONNECT] WebSocket client attempting connection: {sid}")
    logger.info(f"🔍 [CONNECT] Args received: {args}")
    
    # Token'ı bul (auth parametresi, query string veya header'dan)
    token = None
    
    # 1. Socket.IO auth parametresinden token al (args'da gelebilir)
    if args and len(args) > 0:
        logger.info(f"📦 [CONNECT] Args[0] type: {type(args[0])}, content: {args[0]}")
        auth_data = args[0]
        if isinstance(auth_data, dict):
            token = auth_data.get('token')
            logger.info(f"🔑 [CONNECT] Token from auth dict: {token[:20] if token else 'None'}...")
        elif isinstance(auth_data, str):
            token = auth_data
            logger.info(f"🔑 [CONNECT] Token from auth string: {token[:20] if token else 'None'}...")
    
    # 2. Query string'den token al (client query: {token: ...} kullanırsa)
    if not token:
        query_string = environ.get('QUERY_STRING', '')
        logger.info(f"❓ [CONNECT] Query string: {query_string}")
        if query_string:
            from urllib.parse import parse_qs
            params = parse_qs(query_string)
            token_list = params.get('token', [])
            if token_list:
                token = token_list[0]
                logger.info(f"🔑 [CONNECT] Token from query: {token[:20]}...")
    
    # 3. Header'dan token al (HTTP_AUTHORIZATION)
    if not token:
        auth_header = environ.get('HTTP_AUTHORIZATION', '')
        logger.info(f"📋 [CONNECT] Auth header: {auth_header[:30] if auth_header else 'None'}...")
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            logger.info(f"🔑 [CONNECT] Token from header: {token[:20]}...")
    
    # Public sayfa için token olmayabilir - bu durumda sadece public room'lara join edebilir
    is_public_connection = False
    if not token:
        logger.info(f"🌐 [CONNECT] No token provided by {sid} - treating as public connection")
        is_public_connection = True
        # Public connection için minimal session oluştur
        await sio.save_session(sid, {
            'is_public': True
        })
        await sio.emit('connection_established', {'status': 'connected', 'public': True}, room=sid)
        return True  # Public bağlantıya izin ver
    
    # Token varsa normal authentication yap
    
    # Token'ı doğrula
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        organization_id = payload.get("org_id")
        
        if not username or not organization_id:
            logger.warning(f"⚠️ [CONNECT] Eksik payload, public'e düşürülüyor: {sid}")
            await sio.save_session(sid, {'is_public': True}) # Buraya ekle
            return True # False'u True yap!
        
        await sio.save_session(sid, {
            'username': username,
            'organization_id': organization_id,
            'role': payload.get('role')
        })
        logger.info(f"✓ [CONNECT] Authenticated: {username}")

        try:
            room_name = f"org_{organization_id}"
            await sio.enter_room(sid, room_name)
            logger.info(f"✓ [CONNECT] Auto-joined {sid} to room: {room_name}")
            await sio.emit('joined_organization', {'organization_id': organization_id}, room=sid)
        except Exception as join_error:
            logger.error(f"✗ [CONNECT] Failed to auto-join org room: {join_error}", exc_info=True)
        return True
        
    except (JWTError, Exception) as e:
        logger.warning(f"⚠️ [CONNECT] Auth hatası ({type(e).__name__}), public devam ediliyor: {sid}")
        await sio.save_session(sid, {'is_public': True})
        return True

@sio.event
async def disconnect(sid):
    """Client disconnected"""
    logger.info(f"WebSocket client disconnected: {sid}")
    
    # Voice session cleanup
    if sid in _voice_sessions:
        try:
            voice_service = get_voice_ai_service()
            if voice_service:
                session_info = _voice_sessions[sid]
                voice_session = session_info['session']
                receive_task = session_info.get('receive_task')
                
                # Receive loop'u durdur
                if receive_task and not receive_task.done():
                    receive_task.cancel()
                    try:
                        await receive_task
                    except asyncio.CancelledError:
                        pass
                
                await voice_service.close_session(voice_session)
                del _voice_sessions[sid]
                logger.info(f"🧹 [VOICE] Voice session cleaned up for disconnected client {sid}")
        except Exception as e:
            logger.error(f"Error cleaning up voice session: {e}")

@sio.event
async def join_organization(sid, data):
    """Join organization room for real-time updates - with authorization"""
    logger.info(f"🟢 [JOIN_ORG] join_organization event received from {sid} with data: {data}")
    
    try:
        # Session'dan kullanıcı bilgilerini al
        session = await sio.get_session(sid)
        if not session:
            logger.warning(f"✗ [JOIN_ORG] No session found for {sid} - connection not authenticated")
            await sio.emit('error', {'message': 'Not authenticated'}, room=sid)
            return
        
        user_org_id = session.get('organization_id')
        if not user_org_id:
            logger.warning(f"✗ [JOIN_ORG] No organization_id in session for {sid}")
            await sio.emit('error', {'message': 'Invalid session'}, room=sid)
            return
        
        # İstenen organization_id
        requested_org_id = data.get('organization_id')
        if not requested_org_id:
            logger.warning(f"⚠ [JOIN_ORG] join_organization called without organization_id from {sid}")
            await sio.emit('error', {'message': 'organization_id required'}, room=sid)
            return
        
        # KRİTİK: Kullanıcının organization_id'si ile istenen organization_id eşleşmeli
        if user_org_id != requested_org_id:
            logger.warning(f"✗ [JOIN_ORG] Authorization failed: User {session.get('username')} (org: {user_org_id}) tried to join org {requested_org_id}")
            await sio.emit('error', {'message': 'Unauthorized: Cannot join this organization'}, room=sid)
            return
        
        # Doğrulama başarılı - odaya katıl
        room_name = f"org_{requested_org_id}"
        await sio.enter_room(sid, room_name)
        logger.info(f"✓ [JOIN_ORG] Client {sid} (user: {session.get('username')}) joined organization room: {room_name}")
        
        await sio.emit('joined_organization', {'organization_id': requested_org_id}, room=sid)
        logger.info(f"✓ [JOIN_ORG] Sent joined_organization confirmation to {sid}")
        
    except Exception as e:
        logger.error(f"✗ [JOIN_ORG] Error in join_organization: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Internal server error'}, room=sid)

@sio.event
async def leave_organization(sid, data):
    """Leave organization room"""
    organization_id = data.get('organization_id')
    if organization_id:
        await sio.leave_room(sid, f"org_{organization_id}")
        logger.info(f"Client {sid} left organization room: org_{organization_id}")

@sio.event
async def join_public_organization(sid, data):
    """Public sayfa için organization room'a katıl - slug ile doğrulama"""
    logger.info(f"🌐 [JOIN_PUBLIC] join_public_organization event received from {sid} with data: {data}")
    
    try:
        slug = data.get('slug')
        organization_id = data.get('organization_id')
        
        if not slug and not organization_id:
            logger.warning(f"✗ [JOIN_PUBLIC] join_public_organization called without slug or organization_id from {sid}")
            await sio.emit('error', {'message': 'slug or organization_id required'}, room=sid)
            return
        
        # Database connection - app instance'ından al
        from motor.motor_asyncio import AsyncIOMotorDatabase
        global _app_instance
        if _app_instance is None:
            logger.error(f"✗ [JOIN_PUBLIC] App instance not available")
            await sio.emit('error', {'message': 'Internal server error'}, room=sid)
            return
        
        db = getattr(_app_instance, 'db', None)
        if db is None:
            logger.error(f"✗ [JOIN_PUBLIC] Database not available")
            await sio.emit('error', {'message': 'Internal server error'}, room=sid)
            return
        
        # Slug varsa organization_id'yi bul
        if slug and not organization_id:
            admin_user = await db.users.find_one({"slug": slug}, {"_id": 0, "organization_id": 1})
            if not admin_user:
                logger.warning(f"✗ [JOIN_PUBLIC] Slug not found: {slug}")
                await sio.emit('error', {'message': 'Invalid slug'}, room=sid)
                return
            organization_id = admin_user.get('organization_id')
        
        if not organization_id:
            logger.warning(f"✗ [JOIN_PUBLIC] organization_id not found for slug: {slug}")
            await sio.emit('error', {'message': 'Invalid organization'}, room=sid)
            return
        
        # Slug ile organization_id doğrulaması yap (güvenlik için)
        if slug:
            admin_user = await db.users.find_one({"slug": slug, "organization_id": organization_id}, {"_id": 0, "organization_id": 1})
            if not admin_user:
                logger.warning(f"✗ [JOIN_PUBLIC] Slug and organization_id mismatch: {slug} vs {organization_id}")
                await sio.emit('error', {'message': 'Invalid slug or organization_id'}, room=sid)
                return
        
        # Public room'a katıl (org_{organization_id} - aynı room, authenticated ve public client'lar birlikte)
        room_name = f"org_{organization_id}"
        await sio.enter_room(sid, room_name)
        logger.info(f"✓ [JOIN_PUBLIC] Client {sid} joined public organization room: {room_name}")
        
        await sio.emit('joined_public_organization', {'organization_id': organization_id}, room=sid)
        logger.info(f"✓ [JOIN_PUBLIC] Sent joined_public_organization confirmation to {sid}")
        
    except Exception as e:
        logger.error(f"✗ [JOIN_PUBLIC] Error in join_public_organization: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Internal server error'}, room=sid)

# === VOICE AI WEBSOCKET HANDLERS ===

# Active voice sessions dictionary
_voice_sessions = {}

async def _voice_receive_loop(sid, voice_session, voice_service):
    """
    Background task: AI'dan gelen sesleri sürekli dinle ve client'a gönder
    """
    try:
        logger.info(f"🔊 [VOICE] Receive loop started for {sid}")
        
        loop_count = 0
        while sid in _voice_sessions:
            loop_count += 1
            logger.info(f"🔄 [VOICE] Receive loop iteration {loop_count} for {sid}")
            
            # AI'dan ses cevabını al
            logger.info(f"⏳ [VOICE] Waiting for AI response for {sid}...")
            response_audio = await voice_service.receive_audio_response(voice_session)
            logger.info(f"✅ [VOICE] Received response from AI for {sid}, has_audio: {bool(response_audio)}")
            
            if response_audio:
                # Client'a ses cevabını gönder
                logger.info(f"📤 [VOICE] Sending audio response to {sid}, size: {len(response_audio)}")
                await sio.emit('voice_response', {
                    'audio': response_audio
                }, room=sid)
                
                logger.info(f"✅ [VOICE] Audio response sent to {sid}")
            else:
                logger.warning(f"⚠️ [VOICE] No audio in response for {sid}")
            
            # Küçük bir bekleme (CPU'yu aşırı yüklememek için)
            await asyncio.sleep(0.01)
    
    except asyncio.CancelledError:
        logger.info(f"🛑 [VOICE] Receive loop cancelled for {sid}")
        raise
    except Exception as e:
        logger.error(f"❌ [VOICE] Receive loop error for {sid}: {e}", exc_info=True)
        await sio.emit('voice_error', {
            'message': f'Voice receive error: {str(e)}'
        }, room=sid)

@sio.on('voice_start')
async def handle_voice_start(sid, data):
    """
    Sesli görüşme oturumunu başlat
    
    Client'tan gelen data:
    {
        "organization_id": "...",
        "user_role": "admin",
        "username": "..."
    }
    """
    try:
        logger.info(f"🎤 [VOICE] Voice session start request from {sid}")
        
        # Session kontrolü
        session_data = await sio.get_session(sid)
        if not session_data:
            await sio.emit('voice_error', {
                'message': 'Not authenticated'
            }, room=sid)
            return
        
        organization_id = data.get('organization_id')
        user_role = data.get('user_role', 'staff')
        username = data.get('username', 'User')
        
        # Voice AI service'i al
        voice_service = get_voice_ai_service()
        if not voice_service:
            await sio.emit('voice_error', {
                'message': 'Voice AI service not available'
            }, room=sid)
            return
        
        # System instruction oluştur (metin chatbot'takine benzer)
        system_instruction = f"""
Sen PLANN Asistan'sın. Randevu yönetim sistemi için sesli asistansın.

Organizasyon: {organization_id}
Kullanıcı Rolü: {user_role}
Kullanıcı: {username}

Görevlerin:
- Randevu bilgilerini sesli olarak açıkla
- Kullanıcı sorularına doğal ve akıcı yanıt ver
- Gerektiğinde metin chatbot'a yönlendir (karmaşık işlemler için)

Yanıtların kısa, net ve doğal olsun. Türkçe konuş.
"""
        
        # Yeni sesli oturum oluştur
        voice_session = await voice_service.create_session(
            system_instruction=system_instruction
        )
        
        # Background receive loop başlat
        receive_task = asyncio.create_task(
            _voice_receive_loop(sid, voice_session, voice_service)
        )
        
        # Session'ı kaydet
        _voice_sessions[sid] = {
            'session': voice_session,
            'organization_id': organization_id,
            'user_role': user_role,
            'username': username,
            'receive_task': receive_task  # Task'ı kaydet (cleanup için)
        }
        
        # Client'a başarı bildirimi gönder
        await sio.emit('voice_ready', {
            'status': 'ready',
            'message': 'Voice session initialized'
        }, room=sid)
        
        logger.info(f"✅ [VOICE] Voice session created for {sid}")
    
    except Exception as e:
        logger.error(f"❌ [VOICE] Error starting voice session: {e}", exc_info=True)
        await sio.emit('voice_error', {
            'message': f'Failed to start voice session: {str(e)}'
        }, room=sid)


@sio.on('voice_audio')
async def handle_voice_audio(sid, data):
    """
    Kullanıcıdan gelen sesi işle ve AI cevabını döndür
    
    Client'tan gelen data:
    {
        "audio": "BASE64_ENCODED_AUDIO_DATA"
    }
    """
    logger.info(f"🎤 [VOICE] handle_voice_audio called for {sid}")
    try:
        # Session kontrolü
        logger.info(f"🔍 [VOICE] Checking session for {sid}, active sessions: {list(_voice_sessions.keys())}")
        if sid not in _voice_sessions:
            logger.warning(f"⚠️ [VOICE] No session found for {sid}")
            await sio.emit('voice_error', {
                'message': 'No active voice session'
            }, room=sid)
            return
        
        logger.info(f"✅ [VOICE] Session found for {sid}")
        
        audio_base64 = data.get('audio')
        if not audio_base64:
            logger.warning(f"⚠️ [VOICE] No audio data in request from {sid}")
            await sio.emit('voice_error', {
                'message': 'No audio data provided'
            }, room=sid)
            return
        
        logger.info(f"🎤 [VOICE] Audio received from {sid}: {len(audio_base64)} chars")
        
        # Voice service ve session'ı al
        voice_service = get_voice_ai_service()
        session_info = _voice_sessions[sid]
        voice_session = session_info['session']
        
        # AI'ya sesi gönder (sadece gönder, receive loop zaten çalışıyor)
        logger.info(f"📨 [VOICE] Calling send_audio for {sid}...")
        await voice_service.send_audio(voice_session, audio_base64)
        
        logger.info(f"✅ [VOICE] Audio sent to AI from {sid}")
        
        # Receive loop otomatik olarak cevabı gönderecek
        # Burada await etmeye gerek yok
    
    except Exception as e:
        logger.error(f"❌ [VOICE] Error processing audio for {sid}: {e}", exc_info=True)
        await sio.emit('voice_error', {
            'message': f'Failed to process audio: {str(e)}'
        }, room=sid)


@sio.on('voice_stop')
async def handle_voice_stop(sid):
    """
    Sesli görüşme oturumunu kapat
    """
    try:
        if sid not in _voice_sessions:
            return
        
        logger.info(f"🛑 [VOICE] Voice session stop request from {sid}")
        
        # Voice service ve session'ı al
        voice_service = get_voice_ai_service()
        session_info = _voice_sessions[sid]
        voice_session = session_info['session']
        receive_task = session_info.get('receive_task')
        
        # Receive loop'u durdur
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        
        # Session'ı kapat
        await voice_service.close_session(voice_session)
        
        # Session'ı sil
        del _voice_sessions[sid]
        
        # Client'a bildirim gönder
        await sio.emit('voice_stopped', {
            'status': 'stopped',
            'message': 'Voice session closed'
        }, room=sid)
        
        logger.info(f"✅ [VOICE] Voice session closed for {sid}")
    
    except Exception as e:
        logger.error(f"❌ [VOICE] Error stopping voice session: {e}", exc_info=True)

# Helper function to make data JSON serializable (convert ObjectId, datetime, etc.)
def make_json_serializable(obj):
    """Recursively convert MongoDB ObjectId and datetime objects to JSON-serializable types"""
    import json
    from bson import ObjectId
    from datetime import datetime, date
    
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(item) for item in obj)
    elif isinstance(obj, set):
        return {make_json_serializable(item) for item in obj}
    else:
        # Try to convert to JSON-serializable type
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # If not serializable, convert to string
            return str(obj)

# Helper function to emit events to organization rooms
async def emit_to_organization(organization_id: str, event: str, data: dict):
    """Emit event to all clients in an organization room"""
    try:
        room_name = f"org_{organization_id}"
        logger.info(f"📤 [EMIT] About to emit {event} to room {room_name}")
        
        # Convert data to JSON-serializable format
        serializable_data = make_json_serializable(data)
        
        # Get all sockets in the room to verify
        try:
            # Note: Socket.IO doesn't have a direct way to list room members, but we can try to emit
            await sio.emit(event, serializable_data, room=room_name)
            logger.info(f"✓ [EMIT] Successfully emitted {event} to room {room_name} with data keys: {list(serializable_data.keys())}")
            
            # Debug: Try to get room info (if available in python-socketio)
            try:
                # Check if room exists by trying to get room info
                # Note: python-socketio AsyncServer doesn't expose room member count directly
                # But we can log that we attempted the emit
                logger.info(f"🔍 [EMIT] Event {event} sent to room {room_name} - waiting for client receipt")
            except Exception as debug_error:
                logger.warning(f"⚠ [EMIT] Debug check failed: {debug_error}")
        except Exception as emit_error:
            logger.error(f"✗ [EMIT] Error during emit to {room_name}: {emit_error}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"✗ [EMIT] Error emitting {event} to org_{organization_id}: {e}", exc_info=True)

# === GÜVENLİK YARDIMCI FONKSİYONLARI (Aynı kaldı) ===
_mongo_client = None; _mongo_db = None
async def ensure_db_connection(request: Request):
    global _mongo_client, _mongo_db; db = getattr(request.app, 'db', None)
    if db is None and _mongo_db is None:
        mongo_url = os.environ.get('MONGO_URL'); db_name = os.environ.get('DB_NAME', 'royal_koltuk_dev')
        if not mongo_url: raise HTTPException(status_code=503, detail="Database connection not configured.")
        try:
            new_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000); await new_client.admin.command('ping')
            new_db = new_client[db_name]; _mongo_client = new_client; _mongo_db = new_db
            request.app.mongodb_client = new_client; request.app.db = new_db
            logging.info(f"MongoDB connection established (lazy initialization) to {db_name}")
        except Exception as e:
            logging.error(f"Failed to establish MongoDB connection: {e}"); raise HTTPException(status_code=503, detail="Database connection failed.")
    elif db is None and _mongo_db is not None:
        request.app.mongodb_client = _mongo_client; request.app.db = _mongo_db; db = _mongo_db
    try:
        client_to_check = getattr(request.app, 'mongodb_client', _mongo_client)
        if client_to_check: await client_to_check.admin.command('ping')
    except Exception as e:
        logging.warning(f"MongoDB connection check failed: {e}, reconnecting..."); _mongo_client = None; _mongo_db = None; await ensure_db_connection(request) 
async def get_db(request: Request):
    await ensure_db_connection(request); db = getattr(request.app, 'db', None)
    if db is None: raise HTTPException(status_code=503, detail="Database connection failed.")
    return db
async def get_db_from_request(request: Request):
    await ensure_db_connection(request); db = getattr(request.app, 'db', None)
    if db is None: raise HTTPException(status_code=503, detail="Database connection failed.")
    return db
def verify_password(plain_password, hashed_password): return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password): return pwd_context.hash(password)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta: expire = datetime.now(timezone.utc) + expires_delta
    else: expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}); encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
async def get_user_from_db(request: Request, username: str, db=None):
    if db is None:
        await ensure_db_connection(request); db = getattr(request.app, 'db', None)
        if db is None: raise HTTPException(status_code=503, detail="Database connection failed.")
    
    # Önce tam eşleşme dene
    user = await db.users.find_one({"username": username}, {"_id": 0})
    if user:
        try: return UserInDB(**user)
        except Exception as e: logging.warning(f"Kullanıcı veritabanında, ancak UserInDB modeline uymuyor: {e}"); return None
    
    # Tam eşleşme yoksa, case-insensitive arama yap (email için)
    if "@" in username:  # Email adresi gibi görünüyorsa
        import re
        user = await db.users.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}, {"_id": 0})
        if user:
            try: return UserInDB(**user)
            except Exception as e: logging.warning(f"Kullanıcı veritabanında (case-insensitive), ancak UserInDB modeline uymuyor: {e}"); return None
    
    return None
async def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError: raise credentials_exception
    user = await get_user_from_db(request, username, db=db) 
    if user is None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

async def get_superadmin_user(request: Request, token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    """Sadece superadmin rolüne sahip kullanıcılar için dependency"""
    user = await get_current_user(request, token, db)
    if user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için superadmin yetkisi gereklidir")
    return user

async def get_marketing_user(request: Request, token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    """Sadece marketing rolüne sahip kullanıcılar için dependency"""
    user = await get_current_user(request, token, db)
    if user.role != "marketing":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için marketing yetkisi gereklidir")
    return user

# --- KOTA YÖNETİM FONKSİYONLARI ---
async def get_organization_plan(db, organization_id: str) -> Optional[dict]:
    """Organization'ın plan bilgisini getir. Yoksa trial oluştur."""
    plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
    if not plan_doc:
        # Yeni kayıt - Trial paketi oluştur
        trial_start = datetime.now(timezone.utc)
        trial_end = trial_start + timedelta(days=7)
        quota_reset = trial_start + timedelta(days=30)
        new_plan = OrganizationPlan(
            organization_id=organization_id,
            plan_id="tier_trial",
            quota_usage=0,
            quota_reset_date=quota_reset,
            quota_last_reset_date=trial_start,  # Lazy reset için başlangıç tarihi
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            is_first_month=True
        )
        plan_doc = new_plan.model_dump()
        plan_doc['trial_start_date'] = plan_doc['trial_start_date'].isoformat()
        plan_doc['trial_end_date'] = plan_doc['trial_end_date'].isoformat()
        plan_doc['quota_reset_date'] = plan_doc['quota_reset_date'].isoformat()
        plan_doc['created_at'] = plan_doc['created_at'].isoformat()
        plan_doc['updated_at'] = plan_doc['updated_at'].isoformat()
        await db.organization_plans.insert_one(plan_doc)
        return plan_doc
    
    # Datetime string'lerini parse et
    if isinstance(plan_doc.get('trial_start_date'), str):
        plan_doc['trial_start_date'] = datetime.fromisoformat(plan_doc['trial_start_date'].replace('Z', '+00:00'))
    if isinstance(plan_doc.get('trial_end_date'), str):
        plan_doc['trial_end_date'] = datetime.fromisoformat(plan_doc['trial_end_date'].replace('Z', '+00:00'))
    if isinstance(plan_doc.get('quota_reset_date'), str):
        plan_doc['quota_reset_date'] = datetime.fromisoformat(plan_doc['quota_reset_date'].replace('Z', '+00:00'))
    
    return plan_doc

async def check_and_reset_quota(db, organization_id: str) -> None:
    """
    TASK 2: Lazy Quota Reset - Yearly kullanıcılar için aylık reset kontrolü.
    
    Stripe yearly subscription'lar için aylık webhook göndermediği için,
    her ay başında quota'yu sıfırlamak için internal trigger gerekiyor.
    
    Bu fonksiyon quota_last_reset_date ile mevcut ay/yıl'ı karşılaştırır.
    Eğer ay değişmişse, quota_usage'i sıfırlar.
    """
    plan_doc = await get_organization_plan(db, organization_id)
    if not plan_doc:
        return
    
    quota_last_reset = plan_doc.get('quota_last_reset_date')
    if not quota_last_reset:
        # quota_last_reset_date yoksa, şimdi olarak ayarla
        now = datetime.now(timezone.utc)
        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {"$set": {"quota_last_reset_date": now.isoformat()}}
        )
        return
    
    # String ise datetime'a çevir
    if isinstance(quota_last_reset, str):
        quota_last_reset = datetime.fromisoformat(quota_last_reset.replace('Z', '+00:00'))
    
    # Mevcut tarih
    now = datetime.now(timezone.utc)
    
    # Ay ve yıl karşılaştırması
    last_reset_month = quota_last_reset.month
    last_reset_year = quota_last_reset.year
    current_month = now.month
    current_year = now.year
    
    # Ay değişmiş mi kontrol et
    if (current_year > last_reset_year) or (current_year == last_reset_year and current_month > last_reset_month):
        # Ay değişmiş, quota'yu sıfırla
        logger.info(f"🔄 Monthly quota reset triggered for Org ID: {organization_id} (Last reset: {last_reset_month}/{last_reset_year}, Current: {current_month}/{current_year})")
        
        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {
                "$set": {
                    "quota_usage": 0,
                    "quota_last_reset_date": now.isoformat(),
                    "updated_at": now.isoformat()
                }
            }
        )

async def check_quota_and_increment(db, organization_id: str) -> tuple[bool, str]:
    """Kota kontrolü yap ve kullanılırsa artır. (success, error_message)"""
    # TASK 2: Lazy quota reset kontrolü (yearly kullanıcılar için)
    await check_and_reset_quota(db, organization_id)
    
    plan_doc = await get_organization_plan(db, organization_id)
    if not plan_doc:
        return False, "Plan bilgisi bulunamadı"
    
    plan_id = plan_doc.get('plan_id', 'tier_trial')
    plan_info = next((p for p in PLANS if p['id'] == plan_id), None)
    if not plan_info:
        return False, "Plan bilgisi geçersiz"
    
    # Trial kontrolü
    if plan_id == 'tier_trial':
        trial_end = plan_doc.get('trial_end_date')
        if isinstance(trial_end, str):
            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
        if trial_end and datetime.now(timezone.utc) > trial_end:
            return False, "Deneme süreniz doldu. Devam etmek için lütfen bir paket seçin."
    
    # Kota reset kontrolü (eski mantık - quota_reset_date bazlı)
    quota_reset = plan_doc.get('quota_reset_date')
    if isinstance(quota_reset, str):
        quota_reset = datetime.fromisoformat(quota_reset.replace('Z', '+00:00'))
    
    current_usage = plan_doc.get('quota_usage', 0)
    
    # quota_limit'i plan_doc'dan al (webhook'tan kaydedilmiş olmalı)
    # Fallback: plan_info'dan al
    quota_limit = plan_doc.get('quota_limit')
    if not quota_limit:
        quota_limit = plan_info.get('quota_monthly_appointments', 50)
        logger.warning(f"⚠️ quota_limit plan_doc'da yok, plan_info'dan alındı: {quota_limit}")
    # Plan tanımı sınırsız ise (-1) DB kaydından bağımsız olarak override et
    if plan_info.get('quota_monthly_appointments') == -1:
        quota_limit = -1
    
    # Eğer reset tarihi geçmişse, kullanımı sıfırla
    if quota_reset and datetime.now(timezone.utc) > quota_reset:
        current_usage = 0
        # Yeni reset tarihi ayarla (bir ay sonra)
        new_reset_date = datetime.now(timezone.utc) + timedelta(days=30)
        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {
                "$set": {
                    "quota_usage": 0,
                    "ai_usage_count": 0,  # AI mesaj kotasını da sıfırla
                    "quota_reset_date": new_reset_date.isoformat(),
                    "is_first_month": False,  # İlk ay indirimi sadece bir kez
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    # Kota kontrolü (-1 = sınırsız)
    if quota_limit != -1 and current_usage >= quota_limit:
        return False, f"Aylık randevu limitinize ulaştınız ({quota_limit} randevu). Paketinizi yükseltmeniz gerekmektedir."
    
    # Kullanımı artır
    await db.organization_plans.update_one(
        {"organization_id": organization_id},
        {
            "$set": {
                "quota_usage": current_usage + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return True, ""

async def get_plan_info(plan_id: str) -> Optional[dict]:
    """Plan bilgisini getir"""
    return next((p for p in PLANS if p['id'] == plan_id), None)

# --- SMS FONKSİYONU ---
def build_sms_message(company_name: str, customer_name: str, date: str, time: str, service: str, support_phone: str, hours_until: Optional[float] = None, sms_type: str = "confirmation") -> str:
    """SMS mesajı oluşturur. Template desteği kaldırıldı, sadece default format kullanılıyor."""
    # Tarih formatını YYYY-MM-DD'den DD.MM.YYYY'ye çevir
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        # Eğer parse edilemezse olduğu gibi kullan
        formatted_date = date
    
    if sms_type == "cancellation":
        # İptal SMS'i için default
        return f"{company_name}: Randevunuz iptal edildi.\nHizmet: {service}\nTarih: {formatted_date}\nSaat: {time}\nBilgi: {support_phone}"
    elif hours_until is not None:
        # Hatırlatma SMS'i için default
        return f"Sayın {customer_name},\n{company_name} randevunuzu hatırlatmak isteriz.\nHizmet: {service}\nTarih: {formatted_date}\nSaat: {time}\nBilgi/İptal: {support_phone}"
    else:
        # Onay SMS'i için default
        return f"{company_name}: Randevunuz onaylandı.\nHizmet: {service}\nTarih: {formatted_date}\nSaat: {time}\nBilgi/İptal: {support_phone}"

def send_sms(to_phone: str, message: str):
    try:
        if not SMS_ENABLED: logging.info("SMS sending is disabled via SMS_ENABLED env. Skipping."); return True
        clean_phone = re.sub(r'\D', '', to_phone); 
        if clean_phone.startswith('90'): clean_phone = clean_phone[2:]
        if clean_phone.startswith('0'): clean_phone = clean_phone[1:]
        if not clean_phone.startswith('5') or len(clean_phone) != 10: logging.error(f"Invalid Turkish phone number format: {to_phone} -> {clean_phone}"); return False
        
        # Newline karakterlerini koru, sadece fazla boşlukları temizle
        # Önce newline'ları geçici bir karakterle değiştir
        temp_message = message.replace('\n', '|||NEWLINE|||')
        # Fazla boşlukları temizle
        temp_message = re.sub(r'[ \t]+', ' ', temp_message)
        # Newline'ları geri getir
        sanitized = temp_message.replace('|||NEWLINE|||', '\n').strip()
        MAX_LEN = 480
        if len(sanitized) > MAX_LEN: sanitized = sanitized[:MAX_LEN]
            
        api_url = "https://api.iletimerkezi.com/v1/send-sms/get/"
        params = {
            'key': ILETIMERKEZI_API_KEY, 'hash': ILETIMERKEZI_HASH, 'text': sanitized,
            'receipents': clean_phone, 'sender': ILETIMERKEZI_SENDER, 
            'iys': '1', 'iysList': 'BIREYSEL'
        }
        response = requests.get(api_url, params=params, timeout=10)
        try:
            root = ET.fromstring(response.text); status_code = root.find('.//status/code').text
            status_message = root.find('.//status/message').text
            if status_code == '200': logging.info(f"SMS sent successfully to {clean_phone} (Title: {ILETIMERKEZI_SENDER})."); return True
            else: logging.error(f"SMS failed to {clean_phone} (Title: {ILETIMERKEZI_SENDER}). Code: {status_code}, Message: {status_message}"); return False
        except ET.ParseError as e:
            logging.error(f"Failed to parse İletimerkezi response (status={response.status_code}): {response.text} | Error: {str(e)}"); return False
    except Exception as e:
        logging.error(f"Failed to send SMS to {to_phone}: {str(e)}"); return False

# === YARDIMCI FONKSİYONLAR ===
def slugify(text: str) -> str:
    """Türkçe karakterleri dönüştürerek URL-friendly slug oluşturur"""
    turkish_map = {
        'ı': 'i', 'İ': 'i', 'ğ': 'g', 'Ğ': 'g', 'ü': 'u', 'Ü': 'u',
        'ş': 's', 'Ş': 's', 'ö': 'o', 'Ö': 'o', 'ç': 'c', 'Ç': 'c'
    }
    text = text.lower()
    for turkish_char, latin_char in turkish_map.items():
        text = text.replace(turkish_char, latin_char)
    text = re.sub(r'[^a-z0-9]+', '', text)
    return text

# === AUDIT LOG HELPER ===
def clean_dict_for_audit(data: Optional[dict]) -> Optional[dict]:
    """MongoDB ObjectID'lerini temizle"""
    if not data:
        return data
    cleaned = {}
    for key, value in data.items():
        if key == '_id':
            continue  # MongoDB _id'yi atla
        if isinstance(value, dict):
            cleaned[key] = clean_dict_for_audit(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_dict_for_audit(item) if isinstance(item, dict) else item for item in value]
        else:
            cleaned[key] = value
    return cleaned

async def create_audit_log(
    db,
    organization_id: str,
    user_id: str,
    user_full_name: str,
    action: str,
    resource_type: str,
    resource_id: str,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    ip_address: Optional[str] = None
):
    """Denetim günlüğü kaydı oluştur"""
    if not AUDIT_LOGS_ENABLED:
        return
    try:
        # Clean values
        cleaned_old = clean_dict_for_audit(old_value)
        cleaned_new = clean_dict_for_audit(new_value)
        
        audit_log = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            user_full_name=user_full_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=cleaned_old,
            new_value=cleaned_new,
            ip_address=ip_address
        )
        doc = audit_log.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.audit_logs.insert_one(doc)
        logger.info(f"Audit log created: {action} {resource_type} by {user_id}")
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")

# === VERİ MODELLERİ (Aynı kaldı) ===
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None; username: str; full_name: Optional[str] = None; language: Optional[str] = None; organization_id: str = Field(default_factory=lambda: str(uuid.uuid4())); role: str = "admin"; slug: Optional[str] = None; permitted_service_ids: List[str] = []; payment_type: Optional[str] = "salary"; payment_amount: Optional[float] = 0.0; status: Optional[str] = "active"; invitation_token: Optional[str] = None; days_off: List[str] = Field(default_factory=list); onboarding_completed: bool = False; breaks: List[dict] = Field(default_factory=list); can_view_all_appointments: bool = False
class UserInDB(User): hashed_password: Optional[str] = None
class UserCreate(BaseModel): username: str; password: str; full_name: Optional[str] = None; organization_name: Optional[str] = None; support_phone: Optional[str] = None; sector: Optional[str] = None
class Token(BaseModel): access_token: str; token_type: str
class ForgotPasswordRequest(BaseModel): username: str
class ResetPasswordRequest(BaseModel): token: str; new_password: str
class SetupPasswordRequest(BaseModel): token: str; new_password: str
class SsoCodeResponse(BaseModel): code: str; expires_in: int
class SsoExchangeRequest(BaseModel): code: str
class PlanUpdateRequest(BaseModel): 
    plan_id: str
    billing_cycle: str = "monthly"
    platform: str = "web"  # 'web', 'android', 'ios'
    currency: Optional[str] = None  # 'gbp' veya 'try' - otomatik algılanır
class ContactRequest(BaseModel): name: str = Field(..., min_length=1); phone: str = Field(..., min_length=10); email: Optional[str] = None; message: Optional[str] = None
class ContactStatusUpdate(BaseModel): status: Literal["pending", "contacted", "resolved"]
class Service(BaseModel):
    model_config = ConfigDict(extra="ignore"); organization_id: str; id: str = Field(default_factory=lambda: str(uuid.uuid4())); name: str; price: float; duration: int = 30; order: Optional[int] = None; session_count: Optional[int] = None; created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
class ServiceCreate(BaseModel): name: str; price: float; duration: int = 30; order: Optional[int] = None; session_count: Optional[int] = None
class ServiceUpdate(BaseModel): name: Optional[str] = None; price: Optional[float] = None; duration: Optional[int] = None; order: Optional[int] = None; session_count: Optional[int] = None
class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore"); organization_id: str; id: str = Field(default_factory=lambda: str(uuid.uuid4())); customer_name: str; phone: str; service_id: str; service_name: str; service_price: float; appointment_date: str; appointment_time: str; notes: str = ""; status: str = "Bekliyor"; staff_member_id: Optional[str] = None; created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)); completed_at: Optional[str] = None; service_duration: Optional[int] = None; source: Optional[str] = None; session_group_id: Optional[str] = None; session_number: Optional[int] = None; session_total: Optional[int] = None; payment_status: Optional[str] = None
class AppointmentCreate(BaseModel):
    customer_name: str; phone: str; service_id: str; appointment_date: str; appointment_time: str; notes: str = ""; staff_member_id: Optional[str] = None; turnstile_token: Optional[str] = None; session_group_id: Optional[str] = None; session_number: Optional[int] = None; session_total: Optional[int] = None; payment_status: Optional[str] = None
class AppointmentUpdate(BaseModel):
    customer_name: Optional[str] = None; phone: Optional[str] = None; address: Optional[str] = None; service_id: Optional[str] = None; appointment_date: Optional[str] = None; appointment_time: Optional[str] = None; notes: Optional[str] = None; status: Optional[str] = None; staff_member_id: Optional[str] = None; session_group_id: Optional[str] = None; session_number: Optional[int] = None; session_total: Optional[int] = None; payment_status: Optional[str] = None
class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore"); organization_id: str; id: str = Field(default_factory=lambda: str(uuid.uuid4())); appointment_id: str; customer_name: str; service_name: str; amount: float; date: str; staff_member_id: Optional[str] = None; created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
class TransactionUpdate(BaseModel): amount: float
class BusinessHoursDay(BaseModel):
    is_open: bool = True
    open_time: str = "09:00"
    close_time: str = "18:00"

class LocationCoordinates(BaseModel):
    lat: float
    lng: float


class BusinessLocation(BaseModel):
    address: str
    coordinates: LocationCoordinates


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore"); organization_id: str; id: str = Field(default_factory=lambda: str(uuid.uuid4())); work_start_hour: int = 7; work_end_hour: int = 3; appointment_interval: int = 30
    company_name: str = "İşletmeniz"; support_phone: str = "05000000000"; slug: Optional[str] = None; customer_can_choose_staff: bool = False
    logo_url: Optional[str] = None; sms_reminder_hours: float = 1.0; sector: Optional[str] = None; admin_provides_service: bool = False
    images: List[str] = Field(default_factory=list)
    show_service_duration_on_public: bool = True; show_service_price_on_public: bool = True
    break_limit_minutes: int = 60; break_limit_count: int = 2
    location: Optional[BusinessLocation] = None
    business_hours: Optional[dict] = Field(default_factory=lambda: {
        "monday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
        "tuesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
        "wednesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
        "thursday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
        "friday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
        "saturday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"},
        "sunday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"}
    })

# Push Notification Subscription Model
class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # p256dh ve auth keys
    platform: Optional[str] = None # 'android', 'ios' or None (web)

class PushSubscriptionCreate(BaseModel):
    subscription: dict  # {endpoint, keys: {p256dh, auth}, platform}

# Push notification gönderme fonksiyonu
async def send_push_notification(db, organization_id: str, title: str, body: str, data: dict = None, user_id: str = None):
    """Belirli bir organizasyondaki tüm kullanıcılara veya belirli bir kullanıcıya push notification gönder"""
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not configured, skipping push notification")
        return
    
    try:
        # Abonelikleri bul
        query = {"organization_id": organization_id}
        if user_id:
            query["user_id"] = user_id
            
        subscriptions = await db.push_subscriptions.find(query).to_list(None)
        
        if not subscriptions:
            logger.info(f"No push subscriptions found for org: {organization_id}")
            return
        
        notification_payload = json.dumps({
            "title": title,
            "body": body,
            "icon": "https://plannapp.co/icons/icon-192x192.png",
            "badge": "https://plannapp.co/icons/badge-mono-96x96.png",
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Her aboneliğe bildirim gönder
        logger.info(f"🔔 Sending push to {len(subscriptions)} subscriptions")
        for sub in subscriptions:
            # Native Platform (Android/iOS) - Firebase Cloud Messaging (FCM)
            platform = sub.get("platform")
            if platform in ['android', 'ios']:
                try:
                    logger.info(f"🔔 Sending Native Push ({platform}) to: {sub.get('user_id', 'unknown')}")
                    
                    # FCM Message oluştur
                    message = messaging.Message(
                        token=sub["endpoint"], # Native için endpoint token'dır
                        notification=messaging.Notification(
                            title=title,
                            body=body,
                        ),
                        data=data or {}, # String key-value olmalı
                        android=messaging.AndroidConfig(
                            priority='high',
                            notification=messaging.AndroidNotification(
                                icon='ic_stat_icon', # Native resource adı
                                color='#2563eb',
                                click_action='FLUTTER_NOTIFICATION_CLICK' # Capacitor için standart
                            ),
                        ),
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(
                                aps=messaging.Aps(
                                    badge=1,
                                    sound='default'
                                )
                            )
                        )
                    )
                    
                    # Gönder
                    response = messaging.send(message)
                    logger.info(f"✅ Native Push sent: {response}")
                    
                except Exception as e:
                    logger.error(f"❌ Native Push Error for {sub.get('user_id', 'unknown')}: {e}")
                    # Token geçersizse sil (firebase exception kontrolü eklenebilir)
                    if 'registration-token-not-registered' in str(e) or 'invalid-argument' in str(e):
                         await db.push_subscriptions.delete_one({"_id": sub["_id"]})
                         logger.info(f"Removed invalid native subscription")
                continue # Native gönderildi, web push kısmını atla

            # Web Push (VAPID) - Mevcut Kod
            try:
                subscription_info = {
                    "endpoint": sub["endpoint"],
                    "keys": sub["keys"]
                }
                logger.info(f"🔔 Attempting Web Push to: {sub.get('user_id', 'unknown')} - endpoint: {sub['endpoint'][:50]}...")
                
                webpush(
                    subscription_info=subscription_info,
                    data=notification_payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS.copy(),
                    ttl=86400,
                    headers={"Urgency": "high"}
                )
                logger.info(f"✅ Web Push sent to user: {sub.get('user_id', 'unknown')}")
                
            except WebPushException as e:
                # Subscription geçersiz - sil
                logger.error(f"❌ WebPushException for {sub.get('user_id', 'unknown')}: {e}")
                if e.response:
                    logger.error(f"   Response status: {e.response.status_code}")
                    logger.error(f"   Response headers: {dict(e.response.headers) if e.response.headers else 'none'}")
                    logger.error(f"   Response body: {e.response.text if e.response.text else 'empty'}")
                if e.response and e.response.status_code in [404, 410]:
                    await db.push_subscriptions.delete_one({"_id": sub["_id"]})
                    logger.info(f"Removed invalid push subscription: {sub.get('user_id', 'unknown')}")
            except Exception as e:
                logger.error(f"❌ Unexpected error for {sub.get('user_id', 'unknown')}: {type(e).__name__}: {e}")
                    
    except Exception as e:
        logger.error(f"Error sending push notifications: {e}")

# === ABONELİK PAKETLERİ ===
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
        "price_monthly": 710,
        "price_yearly": 7100,
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
        "price_monthly": 1020,
        "price_yearly": 10200,
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
        "price_monthly": 1530,
        "price_yearly": 15300,
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
        "price_monthly": 1940,
        "price_yearly": 19400,
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
        "price_monthly": 2350,
        "price_yearly": 23500,
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
        "price_monthly": 3580,
        "price_yearly": 35800,
        "quota_monthly_appointments": -1,
        "ai_message_limit": -1,
        "features": [
            "Sınırsız Randevu/Ay",
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

class OrganizationPlan(BaseModel):
    """Organization'ın abonelik planı ve kota bilgisi"""
    model_config = ConfigDict(extra="ignore")
    organization_id: str
    plan_id: str = "tier_trial"  # Default trial
    quota_usage: int = 0  # Bu ay kullanılan randevu sayısı
    ai_usage_count: int = 0  # Bu ay atılan AI mesaj sayısı
    quota_reset_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))  # Kota sıfırlama tarihi
    quota_last_reset_date: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))  # Son quota reset tarihi (lazy reset için)
    trial_start_date: Optional[datetime] = None  # Trial başlangıç tarihi
    trial_end_date: Optional[datetime] = None  # Trial bitiş tarihi
    is_first_month: bool = True  # İlk ay indirimi için
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AuditLog(BaseModel):
    """Denetim günlüğü modeli - Kritik işlemleri kaydeder"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    user_id: str  # username
    user_full_name: str
    action: str  # CREATE, UPDATE, DELETE
    resource_type: str  # APPOINTMENT, SETTINGS, CUSTOMER, SERVICE, STAFF
    resource_id: str
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None

# === GÜVENLİK API ENDPOINT'LERİ ===
@api_router.post("/register", response_model=User)
@rate_limit(LIMITS['register']) 
async def register_user(request: Request, user_in: UserCreate, db = Depends(get_db)):
    existing_user = await get_user_from_db(request, user_in.username, db=db)
    if existing_user: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This username is already registered.")
    
    # Yeni organization ID oluştur
    new_org_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_in.password)
    
    # Slug oluştur (organization_name'den)
    base_slug = slugify(user_in.organization_name or user_in.username)
    unique_slug = base_slug
    
    # Slug benzersizlik kontrolü
    slug_counter = 1
    while await db.users.find_one({"slug": unique_slug}):
        unique_slug = f"{base_slug}{str(uuid.uuid4())[:4]}"
        slug_counter += 1
        if slug_counter > 10:  # Sonsuz döngüyü önle
            unique_slug = f"{base_slug}{str(uuid.uuid4())[:8]}"
            break
    
    # User kaydını oluştur
    accept_language = request.headers.get('Accept-Language', '')
    request_lang = get_request_language(request) if accept_language else None
    lang = request_lang or get_email_language(user_in.username)
    if lang not in ['tr', 'en']:
        lang = 'tr'
    user_db_data = user_in.model_dump(exclude={"organization_name", "support_phone"})
    user_db = UserInDB(**user_db_data, hashed_password=hashed_password, organization_id=new_org_id, role="admin", slug=unique_slug, permitted_service_ids=[], onboarding_completed=False, language=lang)
    await db.users.insert_one(user_db.model_dump())
    
    # Bu kullanıcı için varsayılan Settings oluştur (kayıt bilgileriyle)
    default_settings = Settings(
        organization_id=new_org_id,
        company_name=user_in.organization_name or "İşletmeniz",
        support_phone=user_in.support_phone or "05000000000",
        slug=unique_slug,
        customer_can_choose_staff=False,
        sector=getattr(user_in, 'sector', None)
    )
    await db.settings.insert_one(default_settings.model_dump())
    
    # Yeni kayıt için Trial paketi oluştur
    trial_start = datetime.now(timezone.utc)
    trial_end = trial_start + timedelta(days=7)
    quota_reset = trial_start + timedelta(days=30)
    trial_plan = OrganizationPlan(
        organization_id=new_org_id,
        plan_id="tier_trial",
        quota_usage=0,
        quota_reset_date=quota_reset,
        quota_last_reset_date=trial_start,  # Lazy reset için başlangıç tarihi
        trial_start_date=trial_start,
        trial_end_date=trial_end,
        is_first_month=True
    )
    plan_doc = trial_plan.model_dump()
    plan_doc['trial_start_date'] = plan_doc['trial_start_date'].isoformat()
    plan_doc['trial_end_date'] = plan_doc['trial_end_date'].isoformat()
    plan_doc['quota_reset_date'] = plan_doc['quota_reset_date'].isoformat()
    plan_doc['created_at'] = plan_doc['created_at'].isoformat()
    plan_doc['updated_at'] = plan_doc['updated_at'].isoformat()
    await db.organization_plans.insert_one(plan_doc)
    
    # Sektör bazlı default services ekle ve admin'e ata
    sector = getattr(user_in, 'sector', None)
    service_ids = []
    
    if sector and sector != "Diğer/Boş":
        # Dil belirleme - önce request'den, yoksa kayıt dilinden (fallback)
        lang_for_services = lang
        if not lang_for_services:
            lang_for_services = get_request_language(request)
        if not lang_for_services:
            lang_for_services = 'tr'
        
        # Default services'i dil bazlı al
        services_to_add = get_sector_default_services(sector, lang_for_services)
        
        # Eğer dil bazlı bulunamazsa, Türkçe'den al
        if not services_to_add:
            services_to_add = get_sector_default_services(sector, 'tr')
        
        # Price'ları ekle (dil bazlı değil, sabit)
        price_map = {
            "Kuaför": {"Saç Kesimi": 150, "Saç Boyama": 300, "Sakal Traşı": 80, "Haircut": 150, "Hair Colouring": 300, "Beard Trim": 80},
            "Güzellik Salonu": {"Manikür": 100, "Pedikür": 120, "Cilt Bakımı": 250, "Kaş Dizaynı": 80, "Manicure": 100, "Pedicure": 120, "Facial Treatment": 250, "Eyebrow Design": 80},
            "Masaj / SPA": {"Klasik Masaj": 300, "Aromaterapi Masajı": 350, "İsveç Masajı": 400, "Classic Massage": 300, "Aromatherapy Massage": 350, "Swedish Massage": 400},
            "Diyetisyen": {"İlk Danışma": 300, "Kontrol Muayenesi": 200, "Diyet Planı": 250, "Initial Consultation": 300, "Follow-up Consultation": 200, "Diet Plan": 250},
            "Psikolog / Danışmanlık": {"Bireysel Terapi": 500, "Çift Terapisi": 700, "Aile Danışmanlığı": 600, "Individual Therapy": 500, "Couples Therapy": 700, "Family Counselling": 600},
            "Diş Klinikleri": {"Muayene": 200, "Dolgu": 400, "Diş Temizliği": 300, "Beyazlatma": 1500, "Examination": 200, "Filling": 400, "Teeth Cleaning": 300, "Teeth Whitening": 1500},
        }
        
        # Price'ları ekle
        for service in services_to_add:
            service_name = service.get("name", "")
            if sector in price_map and service_name in price_map[sector]:
                service["price"] = price_map[sector][service_name]
        
        # Services'leri oluştur
        for service_data in services_to_add:
            service_id = str(uuid.uuid4())
            service = Service(
                id=service_id,
                organization_id=new_org_id,
                **service_data
            )
            await db.services.insert_one(service.model_dump())
            service_ids.append(service_id)
    
    # Admin'e tüm hizmetleri ata
    if service_ids:
        await db.users.update_one(
            {"username": user_in.username},
            {"$set": {"permitted_service_ids": service_ids}}
        )
    
    # Brevo ile hoş geldin e-postası gönder
    try:
        # Dil belirleme (kayıt sırasında belirlenen dil)
        lang_for_email = lang or get_email_language(user_in.username)
        if lang_for_email not in ['tr', 'en']:
            lang_for_email = 'tr'
        
        logo_url = "https://plannapp.co/api/static/logo.png"
        dashboard_url = "https://plannapp.co.uk" if lang_for_email == 'en' else "https://plannapp.co"
        user_name = user_in.full_name or user_in.username
        
        if lang_for_email == 'en':
            subject = "Welcome to PLANN! Your Free Trial Has Started."
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logo" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">Welcome to PLANN Appointment System!</h1>
                                        <p>Hello {user_name},</p>
                                        <p>Thank you for deciding to bring your business into the digital world with PLANN.</p>
                                        <p>Your <strong>7-day (or 50-appointment)</strong> free trial has been successfully started, giving you access to all our features designed to simplify your appointment management.</p>
                                        <p style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
                                            You can now go to your dashboard to create your first appointment and start exploring the system.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{dashboard_url}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Get Started
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        else:
            subject = "PLANN'a Hoş Geldiniz! Ücretsiz Deneme Sürümünüz Başladı."
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logosu" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">PLANN Randevu Sistemine Hoş Geldiniz!</h1>
                                        <p>Merhaba {user_name},</p>
                                        <p>İşletmenizi PLANN ile dijital dünyaya taşımaya karar verdiğiniz için teşekkür ederiz.</p>
                                        <p>Randevu yönetiminizi kolaylaştırmak için tasarlanan tüm özelliklerimize erişim sağlayan <strong>7 günlük (veya 50 randevuluk)</strong> ücretsiz deneme sürümünüz başarıyla başlatıldı.</p>
                                        <p style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
                                            Artık panonuza giderek ilk randevunuzu oluşturabilir ve sistemi keşfetmeye başlayabilirsiniz.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{dashboard_url}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Kullanmaya Başla
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        
        await send_email(
            to_email=user_in.username,
            subject=subject,
            html_content=html_content,
            to_name=user_name
        )
    except Exception as e:
        logging.error(f"E-posta gönderme sırasında beklenmedik hata: {e}")
        # E-posta gönderilemese bile kayıt başarılı olmalı
    
    return User(**user_db.model_dump())

@api_router.post("/token", response_model=Token)
@rate_limit(LIMITS['login']) 
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    try:
        user = await get_user_from_db(request, form_data.username, db=db)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
        
        # Pending (bekleyen) kullanıcılar giriş yapamaz
        if user.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hesabınız henüz aktif değil. Lütfen e-postanızdaki davet linkine tıklayarak şifrenizi belirleyin.")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data = {
            "sub": user.username, 
            "org_id": user.organization_id, 
            "role": user.role, 
            "onboarding_completed": user.onboarding_completed,
            "full_name": user.full_name or None,
            "can_view_all_appointments": user.can_view_all_appointments
        }
        access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException: raise
    except Exception as e:
        logging.error(f"Login error: {type(e).__name__}: {str(e)}"); import traceback; logging.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during login. Please try again later.")

@api_router.post("/sso/create", response_model=SsoCodeResponse)
@rate_limit(LIMITS.get('sso_create', LIMITS['login']))
async def create_sso_code(request: Request, current_user: UserInDB = Depends(get_current_user)):
    try:
        redis_client = getattr(getattr(request.app, 'state', None), 'redis_client', None) or getattr(request.app, 'redis_client', None)

        ttl_seconds = int(os.environ.get('SSO_CODE_TTL_SECONDS', '60'))
        code = secrets.token_urlsafe(32)
        payload = {
            "sub": current_user.username,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if redis_client:
            redis_key = f"sso:{code}"
            await redis_client.set(redis_key, json.dumps(payload), ex=ttl_seconds)
        else:
            db_inst = getattr(request.app, 'db', None)
            if db_inst is not None:
                from datetime import timedelta
                await db_inst.sso_codes.insert_one({"code": code, "payload": json.dumps(payload), "expire_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)})
            else:
                raise HTTPException(status_code=503, detail="SSO unavailable")
        return {"code": code, "expires_in": ttl_seconds}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"SSO create error: {type(e).__name__}: {str(e)}");
        raise HTTPException(status_code=500, detail="Failed to create SSO code")

@api_router.post("/sso/exchange", response_model=Token)
@rate_limit(LIMITS.get('sso_exchange', LIMITS['login']))
async def exchange_sso_code(request: Request, body: SsoExchangeRequest, db = Depends(get_db)):
    try:
        redis_client = getattr(getattr(request.app, 'state', None), 'redis_client', None) or getattr(request.app, 'redis_client', None)

        code = (body.code or '').strip()
        if not code or len(code) < 10:
            raise HTTPException(status_code=400, detail="Invalid code")

        raw = None
        if redis_client:
            redis_key = f"sso:{code}"
            try:
                raw = await redis_client.getdel(redis_key)
            except Exception:
                raw = await redis_client.get(redis_key)
                if raw is not None:
                    await redis_client.delete(redis_key)
        else:
            sso_doc = await db.sso_codes.find_one_and_delete({"code": code})
            if sso_doc:
                expire_at = sso_doc.get("expire_at")
                if expire_at and expire_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    raw = sso_doc.get("payload")

        if not raw:
            raise HTTPException(status_code=400, detail="Code expired or already used")

        payload = json.loads(raw)
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=400, detail="Invalid code")

        user = await get_user_from_db(request, username, db=db)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})

        if user.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hesabınız henüz aktif değil.")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data = {
            "sub": user.username,
            "org_id": user.organization_id,
            "role": user.role,
            "onboarding_completed": user.onboarding_completed,
            "full_name": user.full_name or None,
            "can_view_all_appointments": user.can_view_all_appointments
        }
        access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"SSO exchange error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="SSO exchange failed")

# === E-POSTA GÖNDERME FONKSİYONLARI ===
def get_email_language(email: str) -> str:
    """Email domain'ine göre dil belirler"""
    if email and ('.co.uk' in email.lower() or '@' in email and email.split('@')[1].startswith('uk')):
        return 'en'
    return 'tr'

def get_request_language(request: Request) -> str:
    """Request header'dan dil belirler"""
    accept_language = request.headers.get('Accept-Language', '')
    if not accept_language:
        return 'tr'

    raw = accept_language.lower().strip()
    first = raw.split(',')[0].strip()
    if first.startswith('en'):
        return 'en'
    if first.startswith('tr'):
        return 'tr'

    if 'en' in raw and 'tr' not in raw:
        return 'en'
    if 'tr' in raw:
        return 'tr'
    return 'tr'

def detect_currency(request: Request, user_phone: Optional[str] = None) -> str:
    """
    Para birimini algılar: Telefon prefix veya IP bazlı.
    
    Args:
        request: FastAPI Request objesi
        user_phone: Kullanıcı telefon numarası (opsiyonel)
    
    Returns:
        'gbp' veya 'try'
    """
    # 1. Telefon numarası prefix kontrolü
    if user_phone:
        clean_phone = re.sub(r'[^\d+]', '', user_phone)
        if clean_phone.startswith('+44') or clean_phone.startswith('44'):
            return 'gbp'
        if clean_phone.startswith('+90') or clean_phone.startswith('90'):
            return 'try'
        if clean_phone.startswith('0') and len(clean_phone) == 11:
            return 'try'
    
    # 2. IP bazlı algılama (basit - UK IP'leri için)
    # Not: Production'da daha gelişmiş bir IP geolocation servisi kullanılabilir
    client_ip = request.client.host if request.client else None
    if client_ip:
        # Basit kontrol: localhost veya private IP'ler için TRY
        if client_ip in ['127.0.0.1', 'localhost'] or client_ip.startswith('192.168.') or client_ip.startswith('10.'):
            return 'try'
        # Production'da burada bir IP geolocation API çağrısı yapılabilir
    
    # 3. Accept-Language header kontrolü
    accept_language = request.headers.get('Accept-Language', '')
    if accept_language and 'en' in accept_language.lower() and 'tr' not in accept_language.lower():
        # İngilizce dil tercihi varsa GBP'ye yönlendir (UK pazarı için)
        return 'gbp'
    
    # 4. Varsayılan: TRY
    return 'try'

def get_stripe_lookup_key(plan_id: str, billing_cycle: str, currency: str) -> str:
    """
    Stripe lookup key oluşturur (currency ile birlikte).
    
    Format: {plan_name}_{billing_cycle}_{currency}
    Örnek: standard_monthly_gbp, professional_monthly_try
    
    Note: Stripe'da her currency için ayrı lookup key kullanılıyor.
    Bu sayede doğrudan ilgili fiyatı çekebiliriz, filtrelemeye gerek yok.
    
    Args:
        plan_id: Plan ID (tier_1_standard, tier_2_profesyonel, vb.)
        billing_cycle: 'monthly' veya 'yearly'
        currency: 'gbp' veya 'try'
    
    Returns:
        Lookup key string (currency ile birlikte)
    """
    # Plan ID'den plan adını çıkar
    # Not: Stripe'da "standart" kullanılıyor (Türkçe), "standard" değil
    plan_name_map = {
        'tier_1_standard': 'standart',  # Stripe'da "standart" olarak kayıtlı
        'tier_2_profesyonel': 'professional',
        'tier_3_premium': 'premium',
        'tier_4_business': 'business',
        'tier_5_enterprise': 'enterprise',
        'tier_6_kurumsal': 'corporate'
    }
    
    plan_name = plan_name_map.get(plan_id, plan_id.replace('tier_', '').replace('_', ''))
    currency_lower = currency.lower()
    
    return f"{plan_name}_{billing_cycle}_{currency_lower}"

def get_stripe_price_by_lookup_key(lookup_key: str) -> Optional[stripe.Price]:
    """
    Stripe'dan lookup key ile fiyat çeker.
    
    Lookup key zaten currency içeriyor (örn: professional_monthly_gbp),
    bu yüzden doğrudan ilgili fiyatı çekebiliriz, filtrelemeye gerek yok.
    
    Args:
        lookup_key: Stripe lookup key (örn: standard_monthly_gbp, professional_monthly_try)
    
    Returns:
        Stripe Price objesi veya None
    """
    try:
        if not STRIPE_SECRET_KEY:
            logger.error("STRIPE_SECRET_KEY tanımlı değil!")
            return None
        
        logger.info(f"🔍 Stripe'da lookup key aranıyor: '{lookup_key}'")
        
        # Stripe'da lookup key ile fiyat ara (currency zaten key'de)
        prices = stripe.Price.list(
            lookup_keys=[lookup_key],
            active=True,
            limit=1  # Currency-specific key olduğu için sadece 1 sonuç bekleniyor
        )
        
        if not prices.data or len(prices.data) == 0:
            logger.warning(f"❌ Stripe'da lookup key bulunamadı: '{lookup_key}'")
            logger.warning(f"   💡 Kontrol edin: Stripe Dashboard'da bu lookup key ile bir fiyat var mı?")
            logger.warning(f"   💡 Lookup key formatı: '{lookup_key}' (örn: 'standard_monthly_gbp', 'professional_monthly_try')")
            return None
        
        # İlk (ve muhtemelen tek) fiyatı döndür
        price = prices.data[0]
        logger.info(f"✅ Stripe fiyat bulundu: lookup_key={lookup_key}, currency={price.currency}, price_id={price.id}, amount={price.unit_amount}")
        return price
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe lookup key hatası: {e}")
        logger.error(f"   Lookup key: '{lookup_key}'")
        return None
    except Exception as e:
        logger.error(f"❌ Fiyat çekme hatası: {e}")
        logger.error(f"   Lookup key: '{lookup_key}'")
        return None

async def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """
    Gerçek kur bilgisini API'den çeker.
    
    Args:
        from_currency: Kaynak para birimi (örn: 'TRY')
        to_currency: Hedef para birimi (örn: 'GBP')
    
    Returns:
        Kur oranı (örn: 1 TRY = X GBP)
    """
    # Aynı para birimiyse 1.0 döndür
    if from_currency.upper() == to_currency.upper():
        return 1.0
    
    try:
        # ExchangeRate-API (ücretsiz tier) kullan
        # Alternatif: exchangerate-api.com veya fixer.io
        api_url = f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}"
        
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        rates = data.get('rates', {})
        
        if to_currency.upper() in rates:
            rate = rates[to_currency.upper()]
            logger.info(f"✅ Kur bilgisi alındı: 1 {from_currency.upper()} = {rate} {to_currency.upper()}")
            return float(rate)
        else:
            logger.warning(f"⚠️ Kur bulunamadı: {to_currency.upper()}, gerçek kur fallback kullanılıyor")
            # Fallback: GBP/TRY için gerçek kur (güncel: 2025-12-19)
            if from_currency.upper() == 'TRY' and to_currency.upper() == 'GBP':
                return 0.0175  # 1 TRY = 0.0175 GBP (gerçek kur)
            elif from_currency.upper() == 'GBP' and to_currency.upper() == 'TRY':
                return 57.14  # 1 GBP = 57.14 TRY (gerçek kur)
            return 1.0
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Kur API hatası: {e}, gerçek kur fallback kullanılıyor")
        # Fallback: GBP/TRY için gerçek kur (güncel: 2025-12-19)
        if from_currency.upper() == 'TRY' and to_currency.upper() == 'GBP':
            return 0.0175  # 1 TRY = 0.0175 GBP (gerçek kur)
        elif from_currency.upper() == 'GBP' and to_currency.upper() == 'TRY':
            return 57.14  # 1 GBP = 57.14 TRY (gerçek kur)
        return 1.0
    except Exception as e:
        logger.error(f"❌ Kur hesaplama hatası: {e}, gerçek kur fallback kullanılıyor")
        # Fallback: GBP/TRY için gerçek kur (güncel: 2025-12-19)
        if from_currency.upper() == 'TRY' and to_currency.upper() == 'GBP':
            return 0.0175  # 1 TRY = 0.0175 GBP (gerçek kur)
        elif from_currency.upper() == 'GBP' and to_currency.upper() == 'TRY':
            return 57.14  # 1 GBP = 57.14 TRY (gerçek kur)
        return 1.0

def get_sector_default_services(sector: str, lang: str = 'tr') -> list:
    """Sektör bazlı default hizmetleri dil bazlı döndürür"""
    if lang == 'en':
        sector_defaults = {
            "Hair Salon": [
                {"name": "Haircut", "price": 0, "duration": 30},
                {"name": "Hair Colouring", "price": 0, "duration": 60},
                {"name": "Beard Trim", "price": 0, "duration": 20}
            ],
            "Beauty Salon": [
                {"name": "Manicure", "price": 0, "duration": 30},
                {"name": "Pedicure", "price": 0, "duration": 40},
                {"name": "Facial Treatment", "price": 0, "duration": 60},
                {"name": "Eyebrow Design", "price": 0, "duration": 20}
            ],
            "Massage / SPA": [
                {"name": "Classic Massage", "price": 0, "duration": 60},
                {"name": "Aromatherapy Massage", "price": 0, "duration": 90},
                {"name": "Swedish Massage", "price": 0, "duration": 60}
            ],
            "Dietitian": [
                {"name": "Initial Consultation", "price": 0, "duration": 45},
                {"name": "Follow-up Consultation", "price": 0, "duration": 30},
                {"name": "Diet Plan", "price": 0, "duration": 60}
            ],
            "Psychologist / Counselling": [
                {"name": "Individual Therapy", "price": 0, "duration": 60},
                {"name": "Couples Therapy", "price": 0, "duration": 90},
                {"name": "Family Counselling", "price": 0, "duration": 90}
            ],
            "Dental Clinics": [
                {"name": "Examination", "price": 0, "duration": 30},
                {"name": "Filling", "price": 0, "duration": 45},
                {"name": "Teeth Cleaning", "price": 0, "duration": 40},
                {"name": "Teeth Whitening", "price": 0, "duration": 60}
            ],
        }
        # Türkçe sektör isimlerini İngilizce'ye map et
        sector_map = {
            "Kuaför": "Hair Salon",
            "Güzellik Salonu": "Beauty Salon",
            "Masaj / SPA": "Massage / SPA",
            "Diyetisyen": "Dietitian",
            "Psikolog / Danışmanlık": "Psychologist / Counselling",
            "Diş Klinikleri": "Dental Clinics"
        }
        mapped_sector = sector_map.get(sector, sector)
        return sector_defaults.get(mapped_sector, [])
    else:
        sector_defaults = {
            "Kuaför": [
                {"name": "Saç Kesimi", "price": 0, "duration": 30},
                {"name": "Saç Boyama", "price": 0, "duration": 60},
                {"name": "Sakal Traşı", "price": 0, "duration": 20}
            ],
            "Güzellik Salonu": [
                {"name": "Manikür", "price": 0, "duration": 30},
                {"name": "Pedikür", "price": 0, "duration": 40},
                {"name": "Cilt Bakımı", "price": 0, "duration": 60},
                {"name": "Kaş Dizaynı", "price": 0, "duration": 20}
            ],
            "Masaj / SPA": [
                {"name": "Klasik Masaj", "price": 0, "duration": 60},
                {"name": "Aromaterapi Masajı", "price": 0, "duration": 90},
                {"name": "İsveç Masajı", "price": 0, "duration": 60}
            ],
            "Diyetisyen": [
                {"name": "İlk Danışma", "price": 0, "duration": 45},
                {"name": "Kontrol Muayenesi", "price": 0, "duration": 30},
                {"name": "Diyet Planı", "price": 0, "duration": 60}
            ],
            "Psikolog / Danışmanlık": [
                {"name": "Bireysel Terapi", "price": 0, "duration": 60},
                {"name": "Çift Terapisi", "price": 0, "duration": 90},
                {"name": "Aile Danışmanlığı", "price": 0, "duration": 90}
            ],
            "Diş Klinikleri": [
                {"name": "Muayene", "price": 0, "duration": 30},
                {"name": "Dolgu", "price": 0, "duration": 45},
                {"name": "Diş Temizliği", "price": 0, "duration": 40},
                {"name": "Beyazlatma", "price": 0, "duration": 60}
            ],
        }
        return sector_defaults.get(sector, [])

async def send_personnel_invitation_email(recipient_email: str, recipient_name: str, admin_name: str, organization_name: str, invitation_token: str, lang: Optional[str] = None):
    """Personel davet e-postası gönderir."""
    try:
        # Dil belirleme
        lang = (lang or '').strip().lower()
        if lang not in ['tr', 'en']:
            lang = get_email_language(recipient_email)
        
        # Invitation link oluştur (setup-password route'u kullan)
        invitation_link = f"https://plannapp.co/setup-password?token={invitation_token}" if lang == 'tr' else f"https://plannapp.co.uk/setup-password?token={invitation_token}"
        
        logo_url = "https://plannapp.co/api/static/logo.png"
        
        if lang == 'en':
            subject = "PLANN Invitation: Create Your Account"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logo" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">PLANN Invitation</h1>
                                        <p>Hello {recipient_name},</p>
                                        <p><strong>{admin_name}</strong> has added you as staff to <strong>{organization_name}</strong>'s PLANN appointment system.</p>
                                        <p>Please click the button below to activate your account and set your password.</p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{invitation_link}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Set Password and Log In
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        else:
            subject = "PLANN Davetiyesi: Hesabınızı Oluşturun"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logosu" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">PLANN Davetiyesi</h1>
                                        <p>Merhaba {recipient_name},</p>
                                        <p><strong>{admin_name}</strong> sizi <strong>{organization_name}</strong> işletmesinin PLANN randevu sistemine personel olarak ekledi.</p>
                                        <p>Hesabınızı aktif etmek ve şifrenizi belirlemek için lütfen aşağıdaki butona tıklayın.</p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{invitation_link}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Şifremi Belirle ve Giriş Yap
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        
        logging.info(f"📧 Personel davet e-postası gönderiliyor: {recipient_email} (Token: {invitation_token[:8]}...)")
        
        result = await send_email(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            to_name=recipient_name
        )
        
        if result:
            logging.info(f"✅ Personel davet e-postası başarıyla gönderildi: {recipient_email}")
        else:
            logging.error(f"❌ Personel davet e-postası gönderilemedi: {recipient_email}")
        
        return result
    except Exception as e:
        logging.error(f"❌ E-posta gönderme sırasında beklenmedik hata: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False

async def send_password_reset_email(user_email: str, user_name: str, reset_link: str, lang: Optional[str] = None):
    """Kullanıcıya şifre sıfırlama linkini içeren kurumsal e-postayı gönderir."""
    try:
        # user_name kontrolü
        if not user_name or user_name.strip() == "":
            user_name = user_email.split("@")[0]  # Email'den isim çıkar
            logging.warning(f"⚠️ [SEND_PASSWORD_RESET_EMAIL] user_name boş, email'den çıkarıldı: {user_name}")
        
        logging.info(f"📧 [SEND_PASSWORD_RESET_EMAIL] user_email: {user_email}, user_name: {user_name}, reset_link: {reset_link[:50]}...")
        
        # Dil belirleme
        lang = (lang or '').strip().lower()
        if lang not in ['tr', 'en']:
            lang = get_email_language(user_email)
        
        logo_url = "https://plannapp.co/api/static/logo.png"
        
        if lang == 'en':
            subject = "PLANN Password Reset Request"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logo" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">Forgot Your Password?</h1>
                                        <p>Hello {user_name},</p>
                                        <p>We received a password reset request for your PLANN account. Please click the button below to regain access to your account.</p>
                                        <p>This link will expire after <strong>30 minutes</strong> for security reasons.</p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{reset_link}" target="_blank" style="background-color: #dc3545; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px; font-size: 14px; color: #888888;">
                                        <p style="border-top: 1px solid #eeeeee; padding-top: 20px;">
                                            If you did not make this request, please ignore this email. Your account will remain secure.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        else:
            subject = "PLANN Şifre Sıfırlama Talebi"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logosu" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">Şifrenizi mi Unuttunuz?</h1>
                                        <p>Merhaba {user_name},</p>
                                        <p>PLANN hesabınız için bir şifre sıfırlama talebi aldık. Hesabınıza yeniden erişim sağlamak için lütfen aşağıdaki butona tıklayın.</p>
                                        <p>Bu link, güvenlik nedeniyle <strong>30 dakika</strong> sonra geçerliliğini yitirecektir.</p>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px;">
                                        <a href="{reset_link}" target="_blank" style="background-color: #dc3545; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 18px; font-weight: bold; display: inline-block;">
                                            Şifremi Sıfırla
                                        </a>
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td align="center" style="padding: 0 30px 40px 30px; font-size: 14px; color: #888888;">
                                        <p style="border-top: 1px solid #eeeeee; padding-top: 20px;">
                                            Eğer bu talebi siz yapmadıysanız, bu e-postayı dikkate almayınız. Hesabınız güvende kalmaya devam edecektir.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        
        # HTML içeriğinin uzunluğunu kontrol et
        html_length = len(html_content)
        logging.info(f"📧 [SEND_PASSWORD_RESET_EMAIL] HTML içerik uzunluğu: {html_length} karakter")
        
        if html_length < 100:
            logging.error(f"❌ [SEND_PASSWORD_RESET_EMAIL] HTML içerik çok kısa! ({html_length} karakter)")
            logging.error(f"❌ [SEND_PASSWORD_RESET_EMAIL] HTML içerik: {html_content[:200]}")
            return False
        
        result = await send_email(
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            to_name=user_name,
            sender_name="PLANN Destek"
        )
        
        logging.info(f"📧 [SEND_PASSWORD_RESET_EMAIL] Email gönderim sonucu: {result}")
        return result
    except Exception as e:
        logging.error(f"❌ [SEND_PASSWORD_RESET_EMAIL] E-posta gönderme sırasında beklenmedik hata: {e}", exc_info=True)
        return False

async def send_contact_notification_email(contact_name: str, contact_phone: str, contact_email: Optional[str], contact_message: Optional[str]):
    """Yeni iletişim talebi için bildirim e-postası gönderir (admin'e)"""
    try:
        # Admin e-posta adresi - environment variable'dan al veya default kullan
        admin_email = os.environ.get('ADMIN_EMAIL', 'fatihsenyuz12@gmail.com')
        
        # Dil belirleme - contact_email veya contact_phone'a göre
        lang = get_email_language(contact_email or contact_phone) if contact_email else 'tr'
        
        logo_url = "https://plannapp.co/api/static/logo.png"
        
        if lang == 'en':
            subject = "PLANN - New Contact Request"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logo" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">New Contact Request</h1>
                                        <p>Hello,</p>
                                        <p>A new contact request has been received from the PLANN interface. Details are below:</p>
                                        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                                            <p style="margin: 10px 0;"><strong>Full Name:</strong> {contact_name}</p>
                                            <p style="margin: 10px 0;"><strong>Phone:</strong> <a href="tel:{contact_phone}" style="color: #007bff; text-decoration: none;">{contact_phone}</a></p>
                                            <p style="margin: 10px 0;"><strong>Email:</strong> {contact_email if contact_email else '<em>Not provided</em>'}</p>
                                            {f'<p style="margin: 10px 0;"><strong>Message:</strong></p><p style="margin: 10px 0; padding: 10px; background-color: #ffffff; border-left: 3px solid #007bff;">{contact_message}</p>' if contact_message else ''}
                                        </div>
                                        <p style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
                                            Please contact the customer as soon as possible.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        else:
            subject = "PLANN - Yeni İletişim Talebi"
            html_content = f"""
            <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                                <tr>
                                    <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                        <img src="{logo_url}" alt="PLANN Logosu" style="max-width: 150px; height: auto;">
                                    </td>
                                </tr>
                                <tr style="background-color: #ffffff;">
                                    <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                        <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">Yeni İletişim Talebi</h1>
                                        <p>Merhaba,</p>
                                        <p>PLANN arayüzünden yeni bir iletişim talebi alındı. Detaylar aşağıdadır:</p>
                                        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                                            <p style="margin: 10px 0;"><strong>Ad Soyad:</strong> {contact_name}</p>
                                            <p style="margin: 10px 0;"><strong>Telefon:</strong> <a href="tel:{contact_phone}" style="color: #007bff; text-decoration: none;">{contact_phone}</a></p>
                                            <p style="margin: 10px 0;"><strong>E-posta:</strong> {contact_email if contact_email else '<em>Belirtilmemiş</em>'}</p>
                                            {f'<p style="margin: 10px 0;"><strong>Mesaj:</strong></p><p style="margin: 10px 0; padding: 10px; background-color: #ffffff; border-left: 3px solid #007bff;">{contact_message}</p>' if contact_message else ''}
                                        </div>
                                        <p style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
                                            Lütfen en kısa sürede müşteri ile iletişime geçin.
                                        </p>
                                    </td>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                        <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
        
        result = await send_email(
            to_email=admin_email,
            subject=subject,
            html_content=html_content,
            to_name="PLANN Yönetim",
            sender_name="PLANN Sistem"
        )
        
        logging.info(f"📧 [SEND_CONTACT_NOTIFICATION] Email gönderim sonucu: {result}")
        return result
    except Exception as e:
        logging.error(f"❌ [SEND_CONTACT_NOTIFICATION] E-posta gönderme sırasında beklenmedik hata: {e}", exc_info=True)
        return False

async def send_contact_confirmation_email(contact_name: str, contact_email: str):
    """Kullanıcıya iletişim talebi onay e-postası gönderir"""
    try:
        logo_url = "https://plannapp.co/api/static/logo.png"
        dashboard_url = "https://plannapp.co"
        subject = "PLANN - Talebiniz Alındı"
        html_content = f"""
        <html>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6;">
            <table width="100%" border="0" cellpadding="0" cellspacing="0">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                            <tr>
                                <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                                    <img src="{logo_url}" alt="PLANN Logosu" style="max-width: 150px; height: auto;">
                                </td>
                            </tr>
                            <tr style="background-color: #ffffff;">
                                <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                                    <h1 style="font-size: 24px; color: #111111; margin-top: 0; text-align: center;">Talebiniz Alındı!</h1>
                                    <p>Merhaba {contact_name},</p>
                                    <p>PLANN iletişim formunu doldurduğunuz için teşekkür ederiz.</p>
                                    <p>İletişim bilgileriniz kaydedildi ve en kısa sürede sizinle iletişime geçeceğiz.</p>
                                    <p style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
                                        Sorularınız için bizimle iletişime geçebilirsiniz.
                                    </p>
                                </td>
                            </tr>
                            <tr style="background-color: #ffffff;">
                                <td align="center" style="padding: 0 30px 40px 30px;">
                                    <a href="{dashboard_url}" target="_blank" style="background-color: #111111; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 25px; font-size: 16px; font-weight: bold; display: inline-block;">
                                        PLANN'ı Keşfet
                                    </a>
                                </td>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                                    <p>© 2025 PLANN. Tüm hakları saklıdır.</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        result = await send_email(
            to_email=contact_email,
            subject=subject,
            html_content=html_content,
            to_name=contact_name,
            sender_name="PLANN"
        )
        
        logging.info(f"📧 [SEND_CONTACT_CONFIRMATION] Kullanıcıya onay e-postası gönderildi: {contact_email} - Sonuç: {result}")
        return result
    except Exception as e:
        logging.error(f"❌ [SEND_CONTACT_CONFIRMATION] Kullanıcıya e-posta gönderme hatası: {e}", exc_info=True)
        return False

@api_router.post("/contact")
async def submit_contact(request: Request, contact_data: ContactRequest, db = Depends(get_db)):
    """Landing page'den gelen iletişim formu"""
    try:
        logging.info(f"📞 [CONTACT] Yeni iletişim talebi: {contact_data.name} - {contact_data.phone}")
        
        # IP adresini al
        client_ip = None
        if request.client:
            client_ip = request.client.host
        # Nginx proxy arkasındaysa X-Forwarded-For'dan al
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        contact_doc = {
            "id": str(uuid.uuid4()),
            "name": contact_data.name.strip(),
            "phone": contact_data.phone.strip(),
            "email": contact_data.email.strip() if contact_data.email else None,
            "message": contact_data.message.strip() if contact_data.message else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",  # pending, contacted, resolved
            "ip_address": client_ip
        }
        
        await db.contact_requests.insert_one(contact_doc)
        logging.info(f"✅ [CONTACT] İletişim talebi kaydedildi: {contact_doc['id']}")
        
        # Admin'e e-posta bildirimi gönder
        try:
            await send_contact_notification_email(
                contact_name=contact_data.name,
                contact_phone=contact_data.phone,
                contact_email=contact_data.email,
                contact_message=contact_data.message
            )
        except Exception as email_error:
            logging.error(f"⚠️ [CONTACT] Admin'e e-posta bildirimi gönderilemedi: {email_error}")
            # E-posta gönderilemese bile kayıt başarılı olmalı
        
        # Kullanıcıya onay e-postası gönder (eğer e-posta girildiyse)
        if contact_data.email and contact_data.email.strip():
            try:
                await send_contact_confirmation_email(
                    contact_name=contact_data.name,
                    contact_email=contact_data.email.strip()
                )
            except Exception as user_email_error:
                logging.error(f"⚠️ [CONTACT] Kullanıcıya onay e-postası gönderilemedi: {user_email_error}")
                # Kullanıcı e-postası gönderilemese bile kayıt başarılı olmalı
        
        return {"success": True, "message": "Talebiniz alındı, en kısa sürede size ulaşacağız."}
    except Exception as e:
        logging.error(f"❌ [CONTACT] İletişim talebi kaydedilemedi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Bir hata oluştu, lütfen tekrar deneyin.")

@api_router.post("/forgot-password")
@rate_limit("3/hour")
async def forgot_password(request: Request, forgot_request: ForgotPasswordRequest, db = Depends(get_db)):
    """Kullanıcıya şifre sıfırlama e-postası gönderir."""
    try:
        logging.info(f"🔐 [FORGOT_PASSWORD] Request alındı: {forgot_request.username}")
        # Kullanıcıyı bul
        user = await get_user_from_db(request, forgot_request.username, db=db)
        if not user:
            # Güvenlik nedeniyle kullanıcı yoksa da başarılı mesajı döndür
            logging.warning(f"⚠️ [FORGOT_PASSWORD] Kullanıcı bulunamadı: {forgot_request.username}")
            return {"message": "Eğer bu e-posta adresi kayıtlıysa, şifre sıfırlama linki gönderildi."}
        
        logging.info(f"✅ [FORGOT_PASSWORD] Kullanıcı bulundu: {user.username}")

        accept_language = request.headers.get('Accept-Language', '')
        request_lang = get_request_language(request) if accept_language else None
        user_lang = getattr(user, 'language', None)
        lang = user_lang or request_lang or get_email_language(user.username)
        if lang not in ['tr', 'en']:
            lang = 'tr'
        
        # Benzersiz token oluştur
        reset_token = str(uuid.uuid4()) + str(uuid.uuid4()).replace('-', '')
        
        # Token'ı veritabanına kaydet (30 dakika geçerli)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db.password_reset_tokens.insert_one({
            "username": user.username,
            "token": reset_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": False
        })
        
        # Reset link oluştur
        reset_link = f"https://plannapp.co.uk/reset-password?token={reset_token}" if lang == 'en' else f"https://plannapp.co/reset-password?token={reset_token}"
        
        # E-posta gönder
        user_name = user.full_name or user.username
        logging.info(f"🔐 [FORGOT_PASSWORD] Token oluşturuldu, email gönderiliyor: {user.username}")
        logging.info(f"🔐 [FORGOT_PASSWORD] Reset link: {reset_link}")
        try:
            email_sent = await send_password_reset_email(user.username, user_name, reset_link, lang=lang)
            logging.info(f"🔐 [FORGOT_PASSWORD] send_password_reset_email çağrıldı, sonuç: {email_sent}")
        except Exception as email_error:
            logging.error(f"❌ [FORGOT_PASSWORD] Email gönderim hatası: {email_error}", exc_info=True)
            email_sent = False
        
        if email_sent:
            logging.info(f"✅ [FORGOT_PASSWORD] Şifre sıfırlama token'ı oluşturuldu ve e-posta gönderildi: {user.username}")
        else:
            logging.error(f"❌ [FORGOT_PASSWORD] Şifre sıfırlama token'ı oluşturuldu ancak e-posta gönderilemedi: {user.username}")
        
        # Güvenlik nedeniyle her zaman başarılı mesajı döndür
        return {"message": "Eğer bu e-posta adresi kayıtlıysa, şifre sıfırlama linki gönderildi."}
    except Exception as e:
        logging.error(f"Şifre sıfırlama talebi hatası: {e}")
        import traceback
        logging.error(traceback.format_exc())
        # Güvenlik nedeniyle hata durumunda da başarılı mesajı döndür
        return {"message": "Eğer bu e-posta adresi kayıtlıysa, şifre sıfırlama linki gönderildi."}

@api_router.post("/auth/setup-password")
@rate_limit(LIMITS['register'])
async def setup_password(request: Request, setup_request: SetupPasswordRequest, db = Depends(get_db)):
    """Personel davet token'ı ile şifre belirleme."""
    try:
        # Token ile kullanıcıyı bul
        user = await db.users.find_one({"invitation_token": setup_request.token})
        if not user:
            raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş davet linki")
        
        # Kullanıcı zaten aktif mi kontrol et
        if user.get("status") == "active":
            raise HTTPException(status_code=400, detail="Bu hesap zaten aktif edilmiş")
        
        # Şifreyi hashle
        hashed_password = get_password_hash(setup_request.new_password)
        
        # Kullanıcıyı güncelle: şifre ekle, status'u active yap, invitation_token'ı sil
        await db.users.update_one(
            {"invitation_token": setup_request.token},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "status": "active"
                },
                "$unset": {
                    "invitation_token": ""
                }
            }
        )
        
        logging.info(f"Personel şifre belirleme tamamlandı: {user.get('username')}")
        return {"message": "Şifreniz başarıyla belirlendi. Giriş yapabilirsiniz."}
    except HTTPException: raise
    except Exception as e:
        logging.error(f"Şifre belirleme hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Şifre belirlenirken bir hata oluştu")

@api_router.post("/reset-password")
@rate_limit(LIMITS['register'])
async def reset_password(request: Request, reset_request: ResetPasswordRequest, db = Depends(get_db)):
    """Token ile şifreyi sıfırlar."""
    try:
        # Token'ı bul
        token_doc = await db.password_reset_tokens.find_one({
            "token": reset_request.token,
            "used": False
        })
        
        if not token_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz veya kullanılmış token."
            )
        
        # Token'ın süresi dolmuş mu kontrol et
        expires_at = datetime.fromisoformat(token_doc['expires_at'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            # Süresi dolmuş token'ı işaretle
            await db.password_reset_tokens.update_one(
                {"token": reset_request.token},
                {"$set": {"used": True}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token'ın süresi dolmuş. Lütfen yeni bir şifre sıfırlama talebi oluşturun."
            )
        
        # Kullanıcıyı bul
        username = token_doc['username']
        user = await get_user_from_db(request, username, db=db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kullanıcı bulunamadı."
            )
        
        # Yeni şifreyi hashle ve güncelle
        new_hashed_password = get_password_hash(reset_request.new_password)
        await db.users.update_one(
            {"username": username},
            {"$set": {"hashed_password": new_hashed_password}}
        )
        
        # Token'ı kullanıldı olarak işaretle
        await db.password_reset_tokens.update_one(
            {"token": reset_request.token},
            {"$set": {"used": True}}
        )
        
        logging.info(f"Şifre başarıyla sıfırlandı: {username}")
        return {"message": "Şifreniz başarıyla sıfırlandı. Yeni şifrenizle giriş yapabilirsiniz."}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Şifre sıfırlama hatası: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Şifre sıfırlama sırasında bir hata oluştu. Lütfen tekrar deneyin."
        )

# === APPOINTMENTS ROUTES ===
@api_router.delete("/appointments/{appointment_id}")
async def delete_appointment(request: Request, appointment_id: str, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request); query = {"id": appointment_id, "organization_id": current_user.organization_id}
    
    # Get appointment before deleting (for audit log)
    appointment = await db.appointments.find_one(query, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Randevu bulunamadı")
    
    result = await db.appointments.delete_one(query)
    
    # Randevuyla ilişkili transaction'ları da sil
    try:
        transaction_query = {
            "appointment_id": appointment_id,
            "organization_id": current_user.organization_id
        }
        transaction_delete_result = await db.transactions.delete_many(transaction_query)
        if transaction_delete_result.deleted_count > 0:
            logger.info(f"Deleted {transaction_delete_result.deleted_count} transaction(s) for appointment {appointment_id}")
    except Exception as e:
        logger.error(f"Error deleting transactions for appointment {appointment_id}: {e}", exc_info=True)
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="DELETE",
        resource_type="APPOINTMENT",
        resource_id=appointment_id,
        old_value=appointment,
        ip_address=request.client.host if request.client else None
    )
    
    # Emit WebSocket event for real-time update
    logger.info(f"About to emit appointment_deleted for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'appointment_deleted',
            {'appointment_id': appointment_id}
        )
        logger.info(f"Successfully emitted appointment_deleted for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit appointment_deleted: {emit_error}", exc_info=True)
    
    return {"message": "Randevu silindi"}

@api_router.put("/appointments/{appointment_id}", response_model=Appointment)
async def update_appointment(request: Request, appointment_id: str, appointment_update: AppointmentUpdate, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request); settings_data = await db.settings.find_one({"organization_id": current_user.organization_id})
    if not settings_data:
        default_settings = Settings(organization_id=current_user.organization_id); settings_data = default_settings.model_dump()
    company_name = settings_data.get("company_name", "İşletmeniz"); support_phone = settings_data.get("support_phone", "Destek Hattı")
    query = {"id": appointment_id, "organization_id": current_user.organization_id}; appointment = await db.appointments.find_one(query, {"_id": 0})
    if not appointment: raise HTTPException(status_code=404, detail="Randevu bulunamadı")
    update_data = {k: v for k, v in appointment_update.model_dump().items() if v is not None}
    # Tarih/saat veya personel değişikliği varsa çakışma kontrolü yap
    if 'appointment_date' in update_data or 'appointment_time' in update_data or 'staff_member_id' in update_data:
        check_date = update_data.get('appointment_date', appointment['appointment_date'])
        check_time = update_data.get('appointment_time', appointment['appointment_time'])
        check_staff = update_data.get('staff_member_id', appointment.get('staff_member_id'))

        # Hizmet süresini bul (güncelleniyorsa yeni hizmet, değilse mevcut)
        check_service_id = update_data.get('service_id', appointment.get('service_id'))
        service_duration = appointment.get('service_duration') or 30
        if check_service_id:
            service_doc = await db.services.find_one(
                {"id": check_service_id, "organization_id": current_user.organization_id},
                {"_id": 0, "duration": 1}
            )
            if service_doc and service_doc.get('duration'):
                service_duration = service_doc.get('duration')

        # Yeni randevunun bitiş saatini hesapla
        new_start_hour, new_start_minute = map(int, check_time.split(':'))
        new_end_minute = new_start_minute + int(service_duration)
        new_end_hour = new_start_hour + (new_end_minute // 60)
        new_end_minute = new_end_minute % 60
        new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"

        # Aynı personelin aynı günkü randevularında overlap kontrolü
        existing_appointments = await db.appointments.find(
            {
                "organization_id": current_user.organization_id,
                "id": {"$ne": appointment_id},
                "staff_member_id": check_staff,
                "appointment_date": check_date,
                "status": {"$ne": "İptal"}
            },
            {"_id": 0, "appointment_time": 1, "service_id": 1, "service_duration": 1}
        ).to_list(200)

        def time_to_minutes(time_str: str) -> int:
            try:
                hour, minute = map(int, time_str.split(':'))
                return hour * 60 + minute
            except Exception:
                return 0

        new_start_min = time_to_minutes(check_time)
        new_end_min = time_to_minutes(new_end_time)

        for existing_appt in existing_appointments:
            existing_start_time = existing_appt.get('appointment_time')
            if not existing_start_time:
                continue
            existing_duration = existing_appt.get('service_duration')
            if not existing_duration and existing_appt.get('service_id'):
                existing_service = await db.services.find_one(
                    {"id": existing_appt.get('service_id'), "organization_id": current_user.organization_id},
                    {"_id": 0, "duration": 1}
                )
                existing_duration = existing_service.get('duration') if existing_service else 30
            existing_duration = int(existing_duration or 30)

            existing_start_min = time_to_minutes(existing_start_time)
            existing_end_min = existing_start_min + existing_duration

            # overlap: new_start < existing_end AND new_end > existing_start
            if (new_start_min < existing_end_min and new_end_min > existing_start_min):
                raise HTTPException(
                    status_code=400,
                    detail=f"Bu personelin {check_date} tarihinde seçilen saat aralığında zaten randevusu var. Lütfen başka bir saat seçin."
                )

        # Time block (break) çakışması kontrolü
        has_break_conflict = await check_break_conflict(
            db, check_staff, check_date, check_time, new_end_time, current_user.organization_id
        )
        if has_break_conflict:
            raise HTTPException(
                status_code=400,
                detail=f"Bu personelin {check_date} tarihinde {check_time} saatinde mola var. Lütfen başka bir saat seçin."
            )
    if 'service_id' in update_data:
        service_query = {"id": update_data['service_id'], "organization_id": current_user.organization_id}; service = await db.services.find_one(service_query, {"_id": 0})
        if service: update_data['service_name'] = service['name']; update_data['service_price'] = service['price']
    new_status = update_data.get('status'); old_status = appointment['status']
    if new_status == 'Tamamlandı' and old_status != 'Tamamlandı':
        update_data['completed_at'] = datetime.now(timezone.utc).isoformat()
        transaction = Transaction(organization_id=current_user.organization_id, appointment_id=appointment_id, customer_name=appointment['customer_name'], service_name=appointment['service_name'], amount=appointment['service_price'], date=appointment['appointment_date'])
        trans_doc = transaction.model_dump(); trans_doc['created_at'] = trans_doc['created_at'].isoformat()
        await db.transactions.insert_one(trans_doc)
        # Tamamlanma SMS'i kaldırıldı (maliyet nedeniyle)
    elif new_status == 'İptal' and old_status != 'İptal':
        # Randevu iptal edildiğinde
        try:
            # İptal SMS'i - Default mesaj kullan
            sms_message = build_sms_message(
                company_name, appointment['customer_name'],
                appointment['appointment_date'], appointment['appointment_time'],
                appointment['service_name'], support_phone, sms_type="cancellation"
            )
            send_sms(appointment['phone'], sms_message)
        except Exception as e: logging.error(f"İptal SMS'i gönderilirken hata oluştu: {e}")
    if update_data: await db.appointments.update_one(query, {"$set": update_data})
    updated_appointment = await db.appointments.find_one(query, {"_id": 0})
    if isinstance(updated_appointment['created_at'], str): updated_appointment['created_at'] = datetime.fromisoformat(updated_appointment['created_at'].replace('Z', '+00:00'))
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="UPDATE",
        resource_type="APPOINTMENT",
        resource_id=appointment_id,
        old_value=appointment,
        new_value=updated_appointment,
        ip_address=request.client.host if request.client else None
    )
    
    # Emit WebSocket event for real-time update
    # Convert datetime to ISO format if it's a datetime object
    # make_json_serializable function will handle this, but we can also do it explicitly
    if isinstance(updated_appointment.get('created_at'), datetime):
        updated_appointment['created_at'] = updated_appointment['created_at'].isoformat()
    logger.info(f"About to emit appointment_updated for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'appointment_updated',
            {'appointment': updated_appointment}
        )
        logger.info(f"Successfully emitted appointment_updated for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit appointment_updated: {emit_error}", exc_info=True)
    
    return updated_appointment

@api_router.get("/appointments/{appointment_id}", response_model=Appointment)
async def get_appointment(request: Request, appointment_id: str, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request)
    query = {"id": appointment_id, "organization_id": current_user.organization_id}
    appointment = await db.appointments.find_one(query, {"_id": 0})
    if not appointment: raise HTTPException(status_code=404, detail="Randevu bulunamadı")
    if isinstance(appointment['created_at'], str): appointment['created_at'] = datetime.fromisoformat(appointment['created_at'].replace('Z', '+00:00'))
    return appointment

# Yardımcı fonksiyon: Mola çakışması kontrolü
async def check_break_conflict(db, staff_id: str, date: str, start_time: str, end_time: str, organization_id: str) -> bool:
    """Personelin belirtilen tarih ve saatte mola çakışması var mı kontrol eder"""
    try:
        # Personeli bul ve molalarını al
        staff = await db.users.find_one(
            {"username": staff_id, "organization_id": organization_id},
            {"_id": 0, "breaks": 1}
        )
        
        if not staff:
            return False
        
        staff_breaks = staff.get('breaks', [])
        
        # Zamanları dakika cinsinden sayıya çevir
        def time_to_minutes(time_str):
            try:
                hour, minute = map(int, time_str.split(':'))
                return hour * 60 + minute
            except (ValueError, AttributeError):
                return 0
        
        new_start_min = time_to_minutes(start_time)
        new_end_min = time_to_minutes(end_time)
        
        # O tarihteki molaları kontrol et
        for brk in staff_breaks:
            if brk.get('date') == date:
                break_start = brk.get('start_time')
                break_end = brk.get('end_time')
                
                if break_start and break_end:
                    break_start_min = time_to_minutes(break_start)
                    break_end_min = time_to_minutes(break_end)
                    
                    # Çakışma kontrolü: (yeni_başlangıç < mola_bitiş) VE (yeni_bitiş > mola_başlangıç)
                    if (new_start_min < break_end_min and new_end_min > break_start_min):
                        logging.info(f"⚠️ Break conflict detected: New {start_time}-{end_time} overlaps with break {break_start}-{break_end} for staff {staff_id}")
                        return True
        
        return False
    except Exception as e:
        logging.error(f"Error checking break conflict: {e}", exc_info=True)
        return False

@api_router.post("/appointments", response_model=Appointment)
async def create_appointment(request: Request, appointment: AppointmentCreate, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request)
    
    # ---------------------------------------------------------
    # 🔒 ADIM 1: REDIS LOCK (ÇİFTE REZERVASYON ENGELLEYİCİ)
    # ---------------------------------------------------------
    # Aynı personelin aynı saatine aynı anda sızılmasını milisaniyeler içinde engeller.
    redis_client = getattr(request.app.state, 'redis_client', None)
    
    if redis_client:
        # Kilit anahtarı: plann:lock:appt:orgID:staffID:date:time
        staff_id = appointment.staff_member_id or "unassigned"
        lock_key = f"plann:lock:appt:{current_user.organization_id}:{staff_id}:{appointment.appointment_date}:{appointment.appointment_time}"
        
        # setnx: Anahtar yoksa oluşturur. Varsa False döner.
        acquired = await redis_client.setnx(lock_key, "locked")
        if not acquired:
            raise HTTPException(
                status_code=409, 
                detail="Bu randevu saati için şu an başka bir işlem yapılıyor. Lütfen 10 saniye sonra tekrar deneyin veya farklı bir saat seçin."
            )
        # Kilidin asılı kalmaması için 5 saniyelik ömür veriyoruz.
        await redis_client.expire(lock_key, 5)
    # ---------------------------------------------------------
    
    # KOTA KONTROLÜ - Randevu oluşturmadan önce kontrol et
    quota_ok, quota_error = await check_quota_and_increment(db, current_user.organization_id)
    if not quota_ok:
        raise HTTPException(status_code=403, detail=quota_error)
    
    service_query = {"id": appointment.service_id, "organization_id": current_user.organization_id}
    service = await db.services.find_one(service_query, {"_id": 0})
    if not service: 
        # Kota artırıldı ama hizmet bulunamadı, geri al
        plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
        if plan_doc:
            await db.organization_plans.update_one(
                {"organization_id": current_user.organization_id},
                {"$inc": {"quota_usage": -1}}
            )
        raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    
    # PERSONEL KONTROL: Staff ise sadece kendi hizmetlerine randevu alabilir (can_view_all_appointments yetkisi yoksa)
    if current_user.role == "staff" and not current_user.can_view_all_appointments:
        if service["id"] not in current_user.permitted_service_ids:
            # Kota artırıldı ama yetki yok, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": current_user.organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(status_code=403, detail="Bu hizmete randevu alma yetkiniz yok")
        
        # Personel kendi adına randevu oluşturuyor, kendi molasını kontrol et
        # Staff role olduğunda, staff_member_id belirtilmese bile personel kendine atanacak
        service_duration = service.get('duration', 30)
        new_start_hour, new_start_minute = map(int, appointment.appointment_time.split(':'))
        new_end_minute = new_start_minute + service_duration
        new_end_hour = new_start_hour + (new_end_minute // 60)
        new_end_minute = new_end_minute % 60
        new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"
        
        # Personelin kendi molasını kontrol et
        has_break_conflict = await check_break_conflict(
            db, current_user.username, appointment.appointment_date,
            appointment.appointment_time, new_end_time, current_user.organization_id
        )
        
        if has_break_conflict:
            # Kota artırıldı ama mola çakışması var, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": current_user.organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(
                status_code=400,
                detail=f"Bu saatte mola var. Lütfen başka bir saat seçin."
            )
        
        # Personel kendi adına randevu oluşturuyor, otomatik olarak kendine ata
        # Normal akışa devam et, ama staff_member_id kontrolünü atlamak için 
        # appointment.staff_member_id'yi current_user.username olarak set et
        # Pydantic model olduğu için object.__setattr__ kullan
        if not appointment.staff_member_id or appointment.staff_member_id != current_user.username:
            object.__setattr__(appointment, 'staff_member_id', current_user.username)
    
    # Otomatik atama mantığı
    assigned_staff_id = None
    
    if appointment.staff_member_id:
        # Belirli bir personel seçildi - çakışma kontrolü yap (duration'a göre)
        service_duration = service.get('duration', 30)
        
        # Yeni randevunun başlangıç ve bitiş saatlerini hesapla
        new_start_hour, new_start_minute = map(int, appointment.appointment_time.split(':'))
        new_end_minute = new_start_minute + service_duration
        new_end_hour = new_start_hour + (new_end_minute // 60)
        new_end_minute = new_end_minute % 60
        new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"
        
        # Bu personelin o tarihteki tüm randevularını çek
        existing_appointments = await db.appointments.find(
            {
                "organization_id": current_user.organization_id,
                "staff_member_id": appointment.staff_member_id,
                "appointment_date": appointment.appointment_date,
                "status": {"$ne": "İptal"}
            },
            {"_id": 0, "appointment_time": 1, "service_id": 1}
        ).to_list(100)
        
        # --- PERFORMANS DOKUNUŞU: BULK FETCH ---
        # 1. Mevcut randevulardaki benzersiz hizmet ID'lerini topla
        unique_service_ids = list(set(appt.get('service_id') for appt in existing_appointments if appt.get('service_id')))
        
        # 2. Tüm bu hizmetlerin sürelerini TEK BİR sorguyla çek
        services_data = await db.services.find(
            {"id": {"$in": unique_service_ids}, "organization_id": current_user.organization_id},
            {"id": 1, "duration": 1, "_id": 0}
        ).to_list(len(unique_service_ids))
        
        # 3. Hızlı arama için bir harita (Map) oluştur
        duration_map = {s['id']: s.get('duration', 30) for s in services_data}
        
        # Her randevunun bitiş saatini hesapla ve çakışma kontrolü yap
        has_conflict = False
        for existing_appt in existing_appointments:
            existing_start_time = existing_appt['appointment_time']
            existing_service_id = existing_appt.get('service_id')
            
            # Veritabanına gitmek yerine sözlükten (hafızadan) süreyi al
            existing_duration = duration_map.get(existing_service_id, 30)
            
            # Mevcut randevunun bitiş saatini hesapla
            existing_start_hour, existing_start_minute = map(int, existing_start_time.split(':'))
            existing_end_minute = existing_start_minute + existing_duration
            existing_end_hour = existing_start_hour + (existing_end_minute // 60)
            existing_end_minute = existing_end_minute % 60
            existing_end_time = f"{str(existing_end_hour).zfill(2)}:{str(existing_end_minute).zfill(2)}"
            
            # Çakışma kontrolü: Zamanları sayısal değerlere çevir (dakika cinsinden)
            def time_to_minutes(time_str):
                """Zaman string'ini (HH:MM) dakika cinsinden sayıya çevir"""
                try:
                    hour, minute = map(int, time_str.split(':'))
                    return hour * 60 + minute
                except (ValueError, AttributeError):
                    return 0
            
            new_start_min = time_to_minutes(appointment.appointment_time)
            new_end_min = time_to_minutes(new_end_time)
            existing_start_min = time_to_minutes(existing_start_time)
            existing_end_min = time_to_minutes(existing_end_time)
            
            # Çakışma kontrolü: (yeni_başlangıç < mevcut_bitiş) VE (yeni_bitiş > mevcut_başlangıç)
            if (new_start_min < existing_end_min and new_end_min > existing_start_min):
                has_conflict = True
                logging.info(f"⚠️ Conflict detected: New {appointment.appointment_time}-{new_end_time} overlaps with existing {existing_start_time}-{existing_end_time}")
                break
        
        if has_conflict:
            # Kota artırıldı ama çakışma var, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": current_user.organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(
                status_code=400,
                detail=f"Bu personelin {appointment.appointment_date} tarihinde {appointment.appointment_time} saatinde zaten bir randevusu var. Lütfen başka bir saat seçin."
            )
        
        # Mola çakışması kontrolü
        has_break_conflict = await check_break_conflict(
            db, appointment.staff_member_id, appointment.appointment_date,
            appointment.appointment_time, new_end_time, current_user.organization_id
        )
        
        if has_break_conflict:
            # Kota artırıldı ama mola çakışması var, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": current_user.organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(
                status_code=400,
                detail=f"Bu personelin {appointment.appointment_date} tarihinde {appointment.appointment_time} saatinde mola var. Lütfen başka bir saat seçin."
            )
        
        assigned_staff_id = appointment.staff_member_id
    else:
        # Otomatik atama: Bu hizmeti verebilen personellerden boş olanı bul
        # Admin'in de hizmet verip vermediğini kontrol et
        settings_data = await db.settings.find_one({"organization_id": current_user.organization_id})
        admin_provides_service = settings_data.get('admin_provides_service', True) if settings_data else True
        no_assignable_staff = False
        
        # Bu hizmeti verebilen personelleri bul
        qualified_staff_query = {
            "organization_id": current_user.organization_id,
            "permitted_service_ids": {"$in": [appointment.service_id]}
        }
        
        # Admin hizmet vermiyorsa, admin'i listeden çıkar
        if not admin_provides_service:
            qualified_staff_query["role"] = {"$ne": "admin"}
        
        qualified_staff = await db.users.find(
            qualified_staff_query,
            {"_id": 0, "username": 1, "role": 1}
        ).to_list(1000)
        
        # Eğer admin_provides_service açıksa ve başka personel yoksa, admin'i personel listesine ekle
        if not qualified_staff:
            # Admin'in bu hizmeti verebilip veremediğini kontrol et
            admin_user = await db.users.find_one(
                {"username": current_user.username, "organization_id": current_user.organization_id, "role": "admin"},
                {"_id": 0, "username": 1, "role": 1, "permitted_service_ids": 1}
            )
            if admin_provides_service and admin_user and appointment.service_id in (admin_user.get('permitted_service_ids') or []):
                qualified_staff = [{"username": admin_user['username'], "role": "admin"}]
                logging.info(f"⚠️ No staff found, but admin can provide service. Using admin: {admin_user['username']}")

        if not qualified_staff:
            # Admin panelinde personel hiç yoksa (ve admin de hizmet vermiyorsa),
            # randevuyu personelsiz (unassigned) kaydetmeye izin ver.
            if current_user.role == "admin":
                no_assignable_staff = True
                assigned_staff_id = None
                logging.info("ℹ️ No assignable staff found; creating appointment as unassigned (admin)")
            else:
                # Kota artırıldı ama personel bulunamadı, geri al
                plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": current_user.organization_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Bu hizmet için uygun personel bulunamadı"
                )

        # Personelsiz kayıt (admin) durumunda, organizasyon bazlı çakışma kontrolü yapılır
        # (personel seçilmediği için herhangi bir randevu ile çakışmayı engelle)
        if no_assignable_staff:
            service_duration = service.get('duration', 30)

            new_start_hour, new_start_minute = map(int, appointment.appointment_time.split(':'))
            new_end_minute = new_start_minute + service_duration
            new_end_hour = new_start_hour + (new_end_minute // 60)
            new_end_minute = new_end_minute % 60
            new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"

            org_appointments = await db.appointments.find(
                {
                    "organization_id": current_user.organization_id,
                    "appointment_date": appointment.appointment_date,
                    "status": {"$ne": "İptal"}
                },
                {"_id": 0, "appointment_time": 1, "service_id": 1}
            ).to_list(1000)

            def time_to_minutes(time_str):
                try:
                    hour, minute = map(int, time_str.split(':'))
                    return hour * 60 + minute
                except (ValueError, AttributeError):
                    return 0

            new_start_min = time_to_minutes(appointment.appointment_time)
            new_end_min = time_to_minutes(new_end_time)

            for existing_appt in org_appointments:
                existing_start_time = existing_appt.get('appointment_time')
                if not existing_start_time:
                    continue
                existing_service_id = existing_appt.get('service_id')

                if existing_service_id:
                    existing_service = await db.services.find_one({"id": existing_service_id}, {"_id": 0, "duration": 1})
                    existing_duration = existing_service.get('duration', 30) if existing_service else 30
                else:
                    existing_duration = 30

                existing_start_hour, existing_start_minute = map(int, existing_start_time.split(':'))
                existing_end_minute = existing_start_minute + existing_duration
                existing_end_hour = existing_start_hour + (existing_end_minute // 60)
                existing_end_minute = existing_end_minute % 60
                existing_end_time = f"{str(existing_end_hour).zfill(2)}:{str(existing_end_minute).zfill(2)}"

                existing_start_min = time_to_minutes(existing_start_time)
                existing_end_min = time_to_minutes(existing_end_time)

                if new_start_min < existing_end_min and new_end_min > existing_start_min:
                    plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
                    if plan_doc:
                        await db.organization_plans.update_one(
                            {"organization_id": current_user.organization_id},
                            {"$inc": {"quota_usage": -1}}
                        )
                    raise HTTPException(
                        status_code=400,
                        detail="Bu saat dilimi doludur. Lütfen başka bir saat seçin."
                    )
        else:
            # Boş personel bul (duration'a göre çakışma kontrolü ile)
            service_duration = service.get('duration', 30)
            
            # Yeni randevunun başlangıç ve bitiş saatlerini hesapla
            new_start_hour, new_start_minute = map(int, appointment.appointment_time.split(':'))
            new_end_minute = new_start_minute + service_duration
            new_end_hour = new_start_hour + (new_end_minute // 60)
            new_end_minute = new_end_minute % 60
            new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"
            
            for staff in qualified_staff:
                # Bu personelin o tarihteki tüm randevularını çek
                existing_appointments = await db.appointments.find(
                    {
                        "organization_id": current_user.organization_id,
                        "staff_member_id": staff['username'],
                        "appointment_date": appointment.appointment_date,
                        "status": {"$ne": "İptal"}
                    },
                    {"_id": 0, "appointment_time": 1, "service_id": 1}
                ).to_list(100)
                
                # Çakışma kontrolü
                has_conflict = False
                for existing_appt in existing_appointments:
                    existing_start_time = existing_appt['appointment_time']
                    existing_service_id = existing_appt.get('service_id')
                    
                    # Mevcut randevunun hizmet süresini bul
                    if existing_service_id:
                        existing_service = await db.services.find_one({"id": existing_service_id}, {"_id": 0, "duration": 1})
                        existing_duration = existing_service.get('duration', 30) if existing_service else 30
                    else:
                        existing_duration = 30
                    
                    # Mevcut randevunun bitiş saatini hesapla
                    existing_start_hour, existing_start_minute = map(int, existing_start_time.split(':'))
                    existing_end_minute = existing_start_minute + existing_duration
                    existing_end_hour = existing_start_hour + (existing_end_minute // 60)
                    existing_end_minute = existing_end_minute % 60
                    existing_end_time = f"{str(existing_end_hour).zfill(2)}:{str(existing_end_minute).zfill(2)}"
                    
                    # Çakışma kontrolü
                    if (appointment.appointment_time < existing_end_time and new_end_time > existing_start_time):
                        has_conflict = True
                        logging.debug(f"   ⚠️ Staff {staff['username']} has conflict: {appointment.appointment_time}-{new_end_time} overlaps with {existing_start_time}-{existing_end_time}")
                        break
                
                # Mola çakışması kontrolü
                has_break_conflict = await check_break_conflict(
                    db, staff['username'], appointment.appointment_date,
                    appointment.appointment_time, new_end_time, current_user.organization_id
                )
                
                if not has_conflict and not has_break_conflict:
                    # Bu personel boş ve mola yok!
                    assigned_staff_id = staff['username']
                    logging.info(f"✅ Auto-assigned to {staff['username']} for {appointment.appointment_time}")
                    break
            
            if not assigned_staff_id:
                # Kota artırıldı ama personel bulunamadı, geri al
                plan_doc = await db.organization_plans.find_one({"organization_id": current_user.organization_id})
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": current_user.organization_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Bu saat dilimi doludur. Lütfen başka bir saat seçin."
                )
    
    appointment_data = appointment.model_dump(); 
    appointment_data['service_name'] = service['name']; 
    appointment_data['service_price'] = service['price']
    appointment_data['staff_member_id'] = assigned_staff_id
    appointment_data['service_duration'] = service.get('duration', 30)  # Hizmet süresini ekle
    try:
        turkey_tz = ZoneInfo("Europe/Istanbul"); now = datetime.now(turkey_tz); dt_str = f"{appointment.appointment_date} {appointment.appointment_time}"
        naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M"); appointment_dt = naive_dt.replace(tzinfo=turkey_tz)
        # Randevu bitiş saatini hesapla (başlangıç saati + hizmet süresi)
        service_duration_minutes = service.get('duration', 30)
        completion_threshold = appointment_dt + timedelta(minutes=service_duration_minutes)
        if now >= completion_threshold: appointment_data['status'] = 'Tamamlandı'; appointment_data['completed_at'] = datetime.now(timezone.utc).isoformat()
        else: appointment_data['status'] = 'Bekliyor'
    except (ValueError, TypeError) as e: logging.warning(f"Randevu durumu ayarlanırken tarih hatası: {e}"); appointment_data['status'] = 'Bekliyor'
    appointment_obj = Appointment(**appointment_data, organization_id=current_user.organization_id)
    doc = appointment_obj.model_dump(); doc['created_at'] = doc['created_at'].isoformat()
    await db.appointments.insert_one(doc)
    # ---------------------------------------------------------
    # 🧹 ADIM 2: SÜPÜRGE (Cache Invalidation)
    # ---------------------------------------------------------
    # Veritabanına kayıt başarılı! Şimdi Redis'teki eski verileri temizleme vakti.
    try:
        # Dashboard ve Müşteri listesini siliyoruz ki yeni veri anında görünsün
        await invalidate_cache(request, "dashboard_stats", current_user)
        await invalidate_cache(request, "customers_list", current_user)
        
        # 🔑 İşimiz bitti, en başta koyduğumuz kilidi (Lock) artık kaldırabiliriz
        redis_client = getattr(request.app.state, 'redis_client', None)
        if redis_client:
            # Fonksiyonun başında tanımladığımız lock_key'i siliyoruz
            await redis_client.delete(lock_key)
            logging.info(f"🔑 Lock released and cache cleared for org: {current_user.organization_id}")
            
    except Exception as e:
        logging.error(f"❌ Süpürge işlemi sırasında hata oluştu: {e}")
    # ---------------------------------------------------------
    # Müşteriyi customers collection'ına ekle (eğer yoksa)
    try:
        # Aynı telefon numarasına sahip müşterileri bul
        customers_with_phone = await db.customers.find(
            {
                "organization_id": current_user.organization_id,
                "phone": appointment.phone
            },
            {"_id": 0, "name": 1, "phone": 1}
        ).to_list(100)
        
        # İsim-soyisim kontrolü (büyük-küçük harf duyarsız)
        customer_name_normalized = appointment.customer_name.strip().lower()
        existing_customer = None
        for customer in customers_with_phone:
            if customer.get("name", "").strip().lower() == customer_name_normalized:
                existing_customer = customer
                break
        
        if not existing_customer:
            # Müşteri yoksa ekle
            customer_doc = {
                "id": str(uuid.uuid4()),
                "organization_id": current_user.organization_id,
                "name": appointment.customer_name.strip(),
                "phone": appointment.phone,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": ""
            }
            await db.customers.insert_one(customer_doc)
            logging.info(f"Customer auto-added: {appointment.customer_name} ({appointment.phone}) for org {current_user.organization_id}")
            
            # Cache invalidation SONRASI müşteri eklendi — tekrar temizle (race condition fix)
            try:
                await invalidate_cache(request, "customers_list", current_user)
            except Exception:
                pass
            
            # WebSocket event gönder (müşteriler listesini güncellemek için)
            try:
                await emit_to_organization(
                    current_user.organization_id,
                    'customer_added',
                    {'customer': customer_doc}
                )
            except Exception as emit_error:
                logging.warning(f"Failed to emit customer_added event: {emit_error}")
    except Exception as e:
        logging.warning(f"Error adding customer to collection: {e}")
    
    if appointment_obj.status == 'Tamamlandı':
        transaction = Transaction(organization_id=current_user.organization_id, appointment_id=appointment_obj.id, customer_name=appointment_obj.customer_name, service_name=appointment_obj.service_name, amount=appointment_obj.service_price, date=appointment_obj.appointment_date)
        trans_doc = transaction.model_dump(); trans_doc['created_at'] = trans_doc['created_at'].isoformat()
        await db.transactions.insert_one(trans_doc)

    settings_data = await db.settings.find_one({"organization_id": current_user.organization_id})
    if not settings_data:
        default_settings = Settings(organization_id=current_user.organization_id); settings_data = default_settings.model_dump()
    company_name = settings_data.get("company_name", "İşletmeniz")
    support_phone = settings_data.get("support_phone", "Destek Hattı")
    business = settings_data or {}
    settings = business.get('settings') if isinstance(business.get('settings'), dict) else business
    location = (settings or {}).get('location') or {}
    coordinates = (location or {}).get('coordinates', {})
    lat = coordinates.get('lat')
    lng = coordinates.get('lng')
    
    # SMS gönder - Default mesaj kullan
    sms_message = build_sms_message(
        company_name, appointment.customer_name,
        appointment.appointment_date, appointment.appointment_time,
        service['name'], support_phone, sms_type="confirmation"
    )
    
    send_sms(appointment.phone, sms_message)
    
    # WhatsApp ONAY mesajı gönderimi
    try:
        _wa_msg_id = send_whatsapp_template(
            to_number=appointment.phone,
            template_type="CONFIRMATION",
            customer_name=appointment.customer_name,
            company_name=company_name,
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            service_name=service['name'],
            support_phone=support_phone or "+44 7474 626 900",
            business_lat=lat,
            business_lng=lng,
            business_address=location.get('address'),
        )
        try:
            import time as _time
            _phone = str(appointment.phone).lstrip('+')
            await db.whatsapp_message_logs.update_one(
                {"message_id": _wa_msg_id},
                {"$set": {
                    "message_id": _wa_msg_id,
                    "recipient": _phone,
                    "status": "sent",
                    "timestamp": int(_time.time()),
                    "recorded_at": datetime.utcnow().isoformat(),
                    "source": "admin_create"
                }},
                upsert=True
            )
        except Exception:
            pass
    except Exception as whatsapp_error:
        logger.warning(f"⚠️ WhatsApp mesajı gönderilemedi: {whatsapp_error}")
        try:
            import time as _time
            _phone = str(appointment.phone).lstrip('+')
            await db.whatsapp_message_logs.update_one(
                {"message_id": f"fail_{_phone}_{int(_time.time())}"},
                {"$set": {
                    "recipient": _phone,
                    "status": "failed",
                    "timestamp": int(_time.time()),
                    "recorded_at": datetime.utcnow().isoformat(),
                    "errors": [{"code": "SEND_ERROR", "title": str(whatsapp_error)[:300]}],
                    "source": "admin_create"
                }},
                upsert=True
            )
        except Exception:
            pass
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="CREATE",
        resource_type="APPOINTMENT",
        resource_id=appointment_obj.id,
        new_value=doc,
        ip_address=request.client.host if request.client else None
    )
    
    # Emit WebSocket event for real-time update
    # Use appointment_obj.model_dump() instead of doc to avoid MongoDB _id issues
    appointment_for_emit = appointment_obj.model_dump()
    appointment_for_emit['created_at'] = appointment_for_emit['created_at'].isoformat()
    logger.info(f"About to emit appointment_created for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'appointment_created',
            {'appointment': appointment_for_emit}
        )
        logger.info(f"Successfully emitted appointment_created for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit appointment_created: {emit_error}", exc_info=True)
    
    return appointment_obj

# === SESSION PACKAGE MODELS ===
class SessionSlot(BaseModel):
    date: str
    time: str

class BulkSessionCreate(BaseModel):
    customer_name: str; phone: str; service_id: str; staff_member_id: Optional[str] = None; notes: str = ""
    session_group_id: Optional[str] = None; starting_session_number: int = 1; session_total: Optional[int] = None
    sessions: list[SessionSlot]

class BulkCheckRequest(BaseModel):
    service_id: str; staff_id: Optional[str] = None; slots: list[str]

# === SESSION PACKAGE ENDPOINTS ===

def _time_to_minutes(time_str: str) -> int:
    try:
        hour, minute = map(int, time_str.split(':'))
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return 0

def _minutes_to_time(minutes: int) -> str:
    return f"{str(minutes // 60).zfill(2)}:{str(minutes % 60).zfill(2)}"

async def _check_slot_conflict(db, organization_id: str, staff_id: str, date: str, time: str, service_duration: int) -> bool:
    """Belirtilen slotun çakışma durumunu kontrol eder. True = çakışma var."""
    new_start_min = _time_to_minutes(time)
    new_end_min = new_start_min + service_duration
    query = {"organization_id": organization_id, "appointment_date": date, "status": {"$nin": ["İptal", "İptal Edildi"]}}
    if staff_id:
        query["staff_member_id"] = staff_id
    existing = await db.appointments.find(
        query,
        {"_id": 0, "appointment_time": 1, "service_id": 1, "service_duration": 1}
    ).to_list(200)
    for appt in existing:
        ex_start = _time_to_minutes(appt.get('appointment_time', '00:00'))
        ex_dur = appt.get('service_duration') or 30
        ex_end = ex_start + ex_dur
        if new_start_min < ex_end and new_end_min > ex_start:
            return True
    return False

async def _find_alternative_slots(db, organization_id: str, staff_id: str, date: str, preferred_time: str, service_duration: int, max_alternatives: int = 3) -> list[str]:
    """Çakışan slot için aynı günden en yakın müsait saatleri bulur."""
    preferred_min = _time_to_minutes(preferred_time)
    existing = await db.appointments.find(
        {"organization_id": organization_id, "staff_member_id": staff_id, "appointment_date": date, "status": {"$nin": ["İptal", "İptal Edildi"]}},
        {"_id": 0, "appointment_time": 1, "service_duration": 1}
    ).to_list(200)
    busy_ranges = []
    for appt in existing:
        s = _time_to_minutes(appt.get('appointment_time', '00:00'))
        d = appt.get('service_duration') or 30
        busy_ranges.append((s, s + d))
    # Molalar da kontrol
    if staff_id:
        staff_doc = await db.users.find_one({"username": staff_id, "organization_id": organization_id}, {"_id": 0, "breaks": 1})
        if staff_doc:
            for brk in staff_doc.get('breaks', []):
                if brk.get('date') == date:
                    bs = _time_to_minutes(brk.get('start_time', '00:00'))
                    be = _time_to_minutes(brk.get('end_time', '00:00'))
                    busy_ranges.append((bs, be))
    def is_free(start_min):
        end_min = start_min + service_duration
        for bs, be in busy_ranges:
            if start_min < be and end_min > bs:
                return False
        return True
    alternatives = []
    # Tercih edilen saatten 30'ar dk uzaklaşarak ara
    for offset in range(1, 20):
        for delta in [offset * 30, -offset * 30]:
            candidate = preferred_min + delta
            if candidate < 480 or candidate > 1200:  # 08:00 - 20:00 arası
                continue
            if is_free(candidate):
                alternatives.append(_minutes_to_time(candidate))
                if len(alternatives) >= max_alternatives:
                    return alternatives
    return alternatives

async def _find_available_staff_for_slot(db, organization_id: str, service_id: str, date: str, time: str, service_duration: int, exclude_staff_id: str = None) -> str | None:
    """Belirtilen slotta bu hizmeti verebilen müsait bir personel bulur. Bulamazsa None döner."""
    # Bu hizmeti verebilen tüm personelleri bul
    staff_query = {"organization_id": organization_id, "role": {"$in": ["staff", "admin"]}, "permitted_service_ids": service_id}
    staff_members = await db.users.find(staff_query, {"_id": 0, "username": 1}).to_list(50)
    
    for staff in staff_members:
        sid = staff.get("username")
        if not sid or sid == exclude_staff_id:
            continue
        # Çakışma kontrolü
        has_conflict = await _check_slot_conflict(db, organization_id, sid, date, time, service_duration)
        if has_conflict:
            continue
        # Mola kontrolü
        end_time = _minutes_to_time(_time_to_minutes(time) + service_duration)
        has_break = await check_break_conflict(db, sid, date, time, end_time, organization_id)
        if has_break:
            continue
        return sid
    return None

@api_router.post("/appointments/bulk-session")
async def create_bulk_session(request: Request, bulk: BulkSessionCreate, current_user: UserInDB = Depends(get_current_user)):
    """Seans paketi oluştur — atomik toplu randevu oluşturma"""
    db = await get_db_from_request(request)
    if not bulk.sessions:
        raise HTTPException(status_code=400, detail="En az bir seans slotu gereklidir")
    
    # Hizmet doğrulama
    service = await db.services.find_one({"id": bulk.service_id, "organization_id": current_user.organization_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    service_duration = service.get('duration', 30)
    
    # Personel doğrulama
    assigned_staff_id = bulk.staff_member_id
    if current_user.role == "staff" and not current_user.can_view_all_appointments:
        if service["id"] not in (current_user.permitted_service_ids or []):
            raise HTTPException(status_code=403, detail="Bu hizmete randevu alma yetkiniz yok")
        assigned_staff_id = current_user.username
    
    # Kota kontrolü (toplam seans sayısı kadar)
    total_sessions = len(bulk.sessions)
    for i in range(total_sessions):
        quota_ok, quota_error = await check_quota_and_increment(db, current_user.organization_id)
        if not quota_ok:
            # Artırılan kotaları geri al
            if i > 0:
                await db.organization_plans.update_one(
                    {"organization_id": current_user.organization_id},
                    {"$inc": {"quota_usage": -i}}
                )
            raise HTTPException(status_code=403, detail=quota_error)
    
    # Her slot için çakışma kontrolü
    redis_client = getattr(request.app.state, 'redis_client', None)
    lock_keys = []
    staff_assignments = {}  # idx -> staff_id (çakışma durumunda farklı personel atanabilir)
    try:
        for idx, session in enumerate(bulk.sessions):
            # Redis lock
            if redis_client and assigned_staff_id:
                lk = f"plann:lock:appt:{current_user.organization_id}:{assigned_staff_id}:{session.date}:{session.time}"
                acquired = await redis_client.setnx(lk, "locked")
                if not acquired:
                    raise HTTPException(status_code=409, detail=f"Seans {idx+1} ({session.date} {session.time}) için başka bir işlem yapılıyor.")
                await redis_client.expire(lk, 10)
                lock_keys.append(lk)
            
            # Çakışma kontrolü — çakışma varsa otomatik başka personele ata
            slot_staff = assigned_staff_id
            has_conflict = await _check_slot_conflict(db, current_user.organization_id, slot_staff, session.date, session.time, service_duration)
            has_break = False
            if slot_staff and not has_conflict:
                end_time = _minutes_to_time(_time_to_minutes(session.time) + service_duration)
                has_break = await check_break_conflict(db, slot_staff, session.date, session.time, end_time, current_user.organization_id)
            if has_conflict or has_break:
                alt_staff = await _find_available_staff_for_slot(db, current_user.organization_id, bulk.service_id, session.date, session.time, service_duration, exclude_staff_id=slot_staff)
                if alt_staff:
                    slot_staff = alt_staff
                else:
                    raise HTTPException(status_code=400, detail=f"Seans {idx+1}: {session.date} {session.time} saatinde hiç müsait personel yok.")
            staff_assignments[idx] = slot_staff
        
        # Tümü geçti — randevuları oluştur
        group_id = bulk.session_group_id or str(uuid.uuid4())
        session_total = bulk.session_total or total_sessions
        created_appointments = []
        
        for idx, session in enumerate(bulk.sessions):
            session_number = bulk.starting_session_number + idx
            is_first_session = (session_number == 1)
            
            # Tarih/saat ile status hesapla
            turkey_tz = ZoneInfo("Europe/Istanbul")
            now = datetime.now(turkey_tz)
            try:
                naive_dt = datetime.strptime(f"{session.date} {session.time}", "%Y-%m-%d %H:%M")
                appointment_dt = naive_dt.replace(tzinfo=turkey_tz)
                completion_threshold = appointment_dt + timedelta(minutes=service_duration)
                apt_status = 'Tamamlandı' if now >= completion_threshold else 'Bekliyor'
            except (ValueError, TypeError):
                apt_status = 'Bekliyor'
            
            apt_doc = {
                "id": str(uuid.uuid4()),
                "organization_id": current_user.organization_id,
                "customer_name": bulk.customer_name,
                "phone": bulk.phone,
                "service_id": bulk.service_id,
                "service_name": service['name'],
                "service_price": service['price'] if is_first_session else 0,
                "appointment_date": session.date,
                "appointment_time": session.time,
                "notes": bulk.notes,
                "status": apt_status,
                "staff_member_id": staff_assignments.get(idx, assigned_staff_id),
                "service_duration": service_duration,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_group_id": group_id,
                "session_number": session_number,
                "session_total": session_total,
                "payment_status": "paid" if is_first_session else "package_included",
                "source": "admin_bulk"
            }
            if apt_status == 'Tamamlandı':
                apt_doc['completed_at'] = datetime.now(timezone.utc).isoformat()
            created_appointments.append(apt_doc)
        
        # Atomik insert
        if created_appointments:
            await db.appointments.insert_many(created_appointments)
        
        # Müşteri kaydı (upsert)
        try:
            existing_customer = await db.customers.find_one({"phone": bulk.phone, "organization_id": current_user.organization_id})
            if not existing_customer:
                await db.customers.insert_one({
                    "id": str(uuid.uuid4()), "organization_id": current_user.organization_id,
                    "name": bulk.customer_name, "phone": bulk.phone,
                    "created_at": datetime.now(timezone.utc).isoformat(), "notes": ""
                })
        except Exception as e:
            logging.warning(f"Customer upsert error in bulk-session: {e}")
        
        # Cache invalidation
        try:
            await invalidate_cache(request, "dashboard_stats", current_user)
            await invalidate_cache(request, "customers_list", current_user)
        except Exception as e:
            logging.warning(f"Cache invalidation error: {e}")
        
        # WebSocket emit
        try:
            await emit_to_organization(current_user.organization_id, 'appointments_bulk_created', {
                'session_group_id': group_id, 'count': len(created_appointments)
            })
        except Exception as e:
            logging.warning(f"WebSocket emit error: {e}")
        
        logging.info(f"✅ Bulk session created: {len(created_appointments)} appointments, group={group_id}")
        # MongoDB insert_many _id ekler, response'tan temizle
        clean_appointments = [{k: v for k, v in apt.items() if k != '_id'} for apt in created_appointments]
        return {"message": f"{len(created_appointments)} seans başarıyla oluşturuldu", "session_group_id": group_id, "appointments": clean_appointments}
    
    except HTTPException:
        # Kota geri al
        await db.organization_plans.update_one(
            {"organization_id": current_user.organization_id},
            {"$inc": {"quota_usage": -total_sessions}}
        )
        raise
    finally:
        # Lock'ları temizle
        if redis_client and lock_keys:
            for lk in lock_keys:
                try:
                    await redis_client.delete(lk)
                except Exception:
                    pass

@api_router.post("/availability/bulk-check")
async def bulk_check_availability(request: Request, check: BulkCheckRequest, current_user: UserInDB = Depends(get_current_user)):
    """Birden fazla tarih/saat slotunun müsaitliğini kontrol eder ve alternatif önerir."""
    db = await get_db_from_request(request)
    service = await db.services.find_one({"id": check.service_id, "organization_id": current_user.organization_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    service_duration = service.get('duration', 30)
    staff_id = check.staff_id
    results = []
    for slot_str in check.slots:
        try:
            parts = slot_str.split('T')
            date = parts[0]
            time = parts[1] if len(parts) > 1 else "00:00"
        except (IndexError, ValueError):
            results.append({"slot": slot_str, "available": False, "alternatives": [], "error": "Geçersiz format"})
            continue
        conflict = await _check_slot_conflict(db, current_user.organization_id, staff_id, date, time, service_duration)
        break_conflict = False
        if staff_id:
            end_time = _minutes_to_time(_time_to_minutes(time) + service_duration)
            break_conflict = await check_break_conflict(db, staff_id, date, time, end_time, current_user.organization_id)
        available = not conflict and not break_conflict
        alternatives = []
        suggested_staff = None
        suggested_staff_name = None
        if not available:
            # Aynı saatte başka müsait personel var mı?
            alt_staff = await _find_available_staff_for_slot(db, current_user.organization_id, check.service_id, date, time, service_duration, exclude_staff_id=staff_id)
            if alt_staff:
                suggested_staff = alt_staff
                staff_doc = await db.users.find_one({"username": alt_staff, "organization_id": current_user.organization_id}, {"_id": 0, "full_name": 1})
                suggested_staff_name = staff_doc.get("full_name", alt_staff) if staff_doc else alt_staff
                available = True  # Başka personel müsait → slot kullanılabilir
            elif staff_id:
                alternatives = await _find_alternative_slots(db, current_user.organization_id, staff_id, date, time, service_duration)
        result_item = {"date": date, "time": time, "available": available, "alternatives": alternatives}
        if suggested_staff:
            result_item["suggested_staff"] = suggested_staff
            result_item["suggested_staff_name"] = suggested_staff_name
        results.append(result_item)
    return results

@api_router.post("/appointments/session-group/{group_id}/cancel-remaining")
async def cancel_remaining_sessions(request: Request, group_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Seans grubundaki tarihi gelmemiş tüm randevuları toplu iptal eder."""
    db = await get_db_from_request(request)
    turkey_tz = ZoneInfo("Europe/Istanbul")
    today_str = datetime.now(turkey_tz).strftime("%Y-%m-%d")
    # Personel yetki kontrolü
    query = {
        "session_group_id": group_id,
        "organization_id": current_user.organization_id,
        "appointment_date": {"$gte": today_str},
        "status": {"$nin": ["İptal", "İptal Edildi", "Tamamlandı"]}
    }
    if current_user.role == "staff" and not current_user.can_view_all_appointments:
        query["staff_member_id"] = current_user.username
    future_sessions = await db.appointments.find(query, {"_id": 0, "id": 1}).to_list(100)
    if not future_sessions:
        raise HTTPException(status_code=404, detail="İptal edilecek bekleyen seans bulunamadı")
    cancel_count = len(future_sessions)
    ids_to_cancel = [s['id'] for s in future_sessions]
    await db.appointments.update_many(
        {"id": {"$in": ids_to_cancel}, "organization_id": current_user.organization_id},
        {"$set": {"status": "İptal Edildi"}}
    )
    # Kota geri iadesi
    try:
        await db.organization_plans.update_one(
            {"organization_id": current_user.organization_id},
            {"$inc": {"quota_usage": -cancel_count}}
        )
    except Exception as e:
        logging.warning(f"Quota refund error: {e}")
    # Cache + WebSocket
    try:
        await invalidate_cache(request, "dashboard_stats", current_user)
        await invalidate_cache(request, "customers_list", current_user)
        await emit_to_organization(current_user.organization_id, 'appointments_bulk_updated', {'session_group_id': group_id, 'cancelled': cancel_count})
    except Exception as e:
        logging.warning(f"Post-cancel cleanup error: {e}")
    logging.info(f"✅ Cancelled {cancel_count} remaining sessions for group {group_id}")
    return {"message": f"{cancel_count} seans iptal edildi", "cancelled_count": cancel_count, "session_group_id": group_id}

@api_router.get("/appointments", response_model=List[Appointment])
async def get_appointments(
    request: Request, 
    date: Optional[str] = None, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None, 
    search: Optional[str] = None,
    staff_member_id: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}
    
    # Personel sadece kendine atanan randevuları görebilir (can_view_all_appointments yetkisi yoksa)
    if current_user.role == "staff" and not current_user.can_view_all_appointments:
        query['staff_member_id'] = current_user.username
    elif staff_member_id and (current_user.role == "admin" or current_user.can_view_all_appointments):
        # Admin için personel filtresi
        if staff_member_id != "all" and staff_member_id != "unassigned":
            query['staff_member_id'] = staff_member_id
        elif staff_member_id == "unassigned":
            query['$or'] = [
                {'staff_member_id': {'$exists': False}},
                {'staff_member_id': None},
                {'staff_member_id': ''}
            ]
    
    if date: 
        query['appointment_date'] = date
    elif start_date and end_date:
        # Tarih aralığı sorgusu
        query['appointment_date'] = {
            '$gte': start_date,
            '$lte': end_date
        }
    elif start_date:
        query['appointment_date'] = {'$gte': start_date}
    elif end_date:
        query['appointment_date'] = {'$lte': end_date}
    
    if status: query['status'] = status
    if search:
        query['$or'] = [
            {'customer_name': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}}
        ]
    
    appointments_from_db = await db.appointments.find(query, {"_id": 0}).sort([("appointment_date", 1), ("appointment_time", 1)]).to_list(1000)
    try:
        turkey_tz = ZoneInfo("Europe/Istanbul"); now = datetime.now(turkey_tz)
    except Exception:
        turkey_tz = timezone(timedelta(hours=3)); now = datetime.now(turkey_tz)
    
    # Tüm servisleri bir kerede çek (performans için)
    service_ids = [appt.get('service_id') for appt in appointments_from_db if appt.get('service_id')]
    services_dict = {}
    if service_ids:
        unique_service_ids = list(set(service_ids))
        logging.info(f"🔍 GET /appointments: {len(unique_service_ids)} unique service_id bulundu: {unique_service_ids[:5]}")
        services = await db.services.find(
            {"id": {"$in": unique_service_ids}, "organization_id": current_user.organization_id},
            {"_id": 0, "id": 1, "duration": 1}
        ).to_list(1000)
        services_dict = {s['id']: s.get('duration', 30) for s in services}
        logging.info(f"✅ GET /appointments: {len(services_dict)} servis bulundu, durations: {list(services_dict.values())[:5]}")
    else:
        logging.warning("⚠️ GET /appointments: Hiç service_id bulunamadı")
    
    ids_to_update = []; transactions_to_create = [] 
    for appt in appointments_from_db:
        if isinstance(appt.get('created_at'), str): appt['created_at'] = datetime.fromisoformat(appt['created_at'].replace('Z', '+00:00'))
        
        # Service duration ekle (bitiş saati hesaplamak için)
        appt_service_id = appt.get('service_id')
        if appt_service_id and appt_service_id in services_dict:
            appt['service_duration'] = services_dict[appt_service_id]
            logging.debug(f"✅ Randevu {appt.get('id', 'unknown')}: service_duration={appt['service_duration']} (service_id={appt_service_id})")
        else:
            appt['service_duration'] = 30
            if appt_service_id:
                logging.warning(f"⚠️ Randevu {appt.get('id', 'unknown')}: service_id={appt_service_id} services_dict'te bulunamadı, default 30 kullanılıyor")
            else:
                logging.warning(f"⚠️ Randevu {appt.get('id', 'unknown')}: service_id yok, default 30 kullanılıyor")
        
        if appt.get('status') == 'Bekliyor':
            try:
                dt_str = f"{appt['appointment_date']} {appt['appointment_time']}"
                naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M"); appointment_dt = naive_dt.replace(tzinfo=turkey_tz)
                
                # Randevu bitiş saatini hesapla (başlangıç saati + hizmet süresi)
                service_duration_minutes = appt.get('service_duration', 30)
                completion_threshold = appointment_dt + timedelta(minutes=service_duration_minutes)
                
                # Şu anki saat >= bitiş saati ise tamamlandı olarak işaretle
                if now >= completion_threshold:
                    appt['status'] = 'Tamamlandı'; completed_at_iso = datetime.now(timezone.utc).isoformat()
                    appt['completed_at'] = completed_at_iso; ids_to_update.append(appt['id'])
                    logging.info(f"✅ Randevu {appt.get('id', 'unknown')} otomatik tamamlandı: {appt['appointment_time']} + {service_duration_minutes}dk = {completion_threshold.strftime('%H:%M')}, şimdi: {now.strftime('%H:%M')}")
                    transaction = Transaction(organization_id=current_user.organization_id, appointment_id=appt['id'], customer_name=appt['customer_name'], service_name=appt['service_name'], amount=appt['service_price'], date=appt['appointment_date'], staff_member_id=appt.get('staff_member_id'))
                    trans_doc = transaction.model_dump(); trans_doc['created_at'] = trans_doc['created_at'].isoformat()
                    transactions_to_create.append(trans_doc)
            except (ValueError, TypeError) as e: logging.warning(f"Randevu {appt['id']} için tarih ayrıştırılamadı: {e}")
    if ids_to_update:
        await db.appointments.update_many({"organization_id": current_user.organization_id, "id": {"$in": ids_to_update}}, {"$set": {"status": "Tamamlandı", "completed_at": datetime.now(timezone.utc).isoformat()}})
    if transactions_to_create:
        await db.transactions.insert_many(transactions_to_create)
    return appointments_from_db

# === SERVICES ROUTES ===
@api_router.post("/services/reorder", status_code=204)
async def reorder_services(request: Request, payload: dict, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin sıralayabilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    service_ids = payload.get("service_ids")
    if not isinstance(service_ids, list) or not service_ids:
        raise HTTPException(status_code=400, detail="Invalid service_ids")

    unique_ids = list(dict.fromkeys(service_ids))
    db = await get_db_from_request(request)

    existing = await db.services.find(
        {"organization_id": current_user.organization_id, "id": {"$in": unique_ids}},
        {"_id": 0, "id": 1}
    ).to_list(2000)
    existing_ids = {s.get("id") for s in existing}
    missing = [sid for sid in unique_ids if sid not in existing_ids]
    if missing:
        raise HTTPException(status_code=400, detail="Invalid service_ids")

    now = datetime.now(timezone.utc).isoformat()
    for idx, sid in enumerate(unique_ids):
        await db.services.update_one(
            {"organization_id": current_user.organization_id, "id": sid},
            {"$set": {"order": idx, "updated_at": now}}
        )

    return None

@api_router.delete("/services/{service_id}")
async def delete_service(request: Request, service_id: str, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin silebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request); query = {"id": service_id, "organization_id": current_user.organization_id}
    result = await db.services.delete_one(query)
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    return {"message": "Hizmet silindi"}

@api_router.put("/services/{service_id}", response_model=Service)
async def update_service(request: Request, service_id: str, service_update: ServiceUpdate, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin güncelleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request); query = {"id": service_id, "organization_id": current_user.organization_id}
    service = await db.services.find_one(query, {"_id": 0})
    if not service: raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    update_data = {k: v for k, v in service_update.model_dump().items() if v is not None}
    if update_data: await db.services.update_one(query, {"$set": update_data})
    updated_service = await db.services.find_one(query, {"_id": 0})
    if isinstance(updated_service['created_at'], str): updated_service['created_at'] = datetime.fromisoformat(updated_service['created_at'].replace('Z', '+00:00'))
    return updated_service

@api_router.get("/services/{service_id}", response_model=Service)
async def get_service(request: Request, service_id: str, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request); query = {"id": service_id, "organization_id": current_user.organization_id}
    service = await db.services.find_one(query, {"_id": 0})
    if not service: raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    if isinstance(service['created_at'], str): service['created_at'] = datetime.fromisoformat(service['created_at'].replace('Z', '+00:00'))
    return service

@api_router.post("/services", response_model=Service)
async def create_service(request: Request, service: ServiceCreate, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin ekleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)

    service_data = service.model_dump()
    if service_data.get("order") is None:
        last = await db.services.find(
            {"organization_id": current_user.organization_id},
            {"_id": 0, "order": 1}
        ).sort("order", -1).limit(1).to_list(1)
        last_order = None
        if last:
            last_order = last[0].get("order")
        service_data["order"] = (last_order + 1) if isinstance(last_order, int) else 0

    service_obj = Service(**service_data, organization_id=current_user.organization_id)
    doc = service_obj.model_dump(); doc['created_at'] = doc['created_at'].isoformat()
    await db.services.insert_one(doc)
    try:
        await db.users.update_many(
            {"organization_id": current_user.organization_id, "role": "admin"},
            {"$addToSet": {"permitted_service_ids": service_obj.id}}
        )
    except Exception as e:
        logging.error(f"Failed to auto-assign service to admins: {e}")
    return service_obj

@api_router.get("/services", response_model=List[Service])
async def get_services(request: Request, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request); query = {"organization_id": current_user.organization_id}
    services = await db.services.find(query, {"_id": 0}).to_list(1000)
    for service in services:
        if isinstance(service.get('created_at'), str):
            service['created_at'] = datetime.fromisoformat(service['created_at'].replace('Z', '+00:00'))

    def sort_key(svc: dict):
        order = svc.get("order")
        created = svc.get("created_at")
        created_str = created.isoformat() if isinstance(created, datetime) else (created or "")
        return (
            order if isinstance(order, int) else 1_000_000,
            created_str,
            svc.get("name") or "",
        )

    services_sorted = sorted(services, key=sort_key)
    return services_sorted

# === TRANSACTIONS ROUTES ===
@api_router.get("/transactions", response_model=List[Transaction])
async def get_transactions(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin görebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request); query = {"organization_id": current_user.organization_id}
    if start_date and end_date: query['date'] = {'$gte': start_date, '$lte': end_date}
    elif start_date: query['date'] = {'$gte': start_date}
    elif end_date: query['date'] = {'$lte': end_date}
    transactions = await db.transactions.find(query, {"_id": 0}).to_list(1000)
    for transaction in transactions:
        if isinstance(transaction['created_at'], str): transaction['created_at'] = datetime.fromisoformat(transaction['created_at'].replace('Z', '+00:00'))
    return transactions

@api_router.put("/transactions/{transaction_id}", response_model=Transaction)
async def update_transaction(request: Request, transaction_id: str, transaction_update: TransactionUpdate, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin güncelleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request); query = {"id": transaction_id, "organization_id": current_user.organization_id}
    transaction = await db.transactions.find_one(query, {"_id": 0})
    if not transaction: raise HTTPException(status_code=404, detail="İşlem bulunamadı")
    await db.transactions.update_one(query, {"$set": {"amount": transaction_update.amount}})
    updated_transaction = await db.transactions.find_one(query, {"_id": 0})
    if isinstance(updated_transaction['created_at'], str): updated_transaction['created_at'] = datetime.fromisoformat(updated_transaction['created_at'].replace('Z', '+00:00'))
    
    # Emit WebSocket event for real-time update
    logger.info(f"About to emit transaction_updated for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'transaction_updated',
            updated_transaction
        )
        logger.info(f"Successfully emitted transaction_updated for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit transaction_updated: {emit_error}", exc_info=True)
    
    return updated_transaction

@api_router.delete("/transactions/{transaction_id}")
async def delete_transaction(request: Request, transaction_id: str, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin silebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request); query = {"id": transaction_id, "organization_id": current_user.organization_id}
    result = await db.transactions.delete_one(query)
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="İşlem bulunamadı")
    
    # Emit WebSocket event for real-time update
    logger.info(f"About to emit transaction_deleted for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'transaction_deleted',
            {'id': transaction_id}
        )
        logger.info(f"Successfully emitted transaction_deleted for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit transaction_deleted: {emit_error}", exc_info=True)
    
    return {"message": "İşlem silindi"}

# === DASHBOARD STATS ===
# === PLAN ENDPOINT'LERİ ===
@api_router.get("/plans")
async def get_plans(request: Request):
    """Tüm planları getir (herkese açık) - Para birimine göre Stripe fiyatlarını çeker"""
    # Dil ve para birimi algılama (Accept-Language header'ından)
    accept_language = request.headers.get('Accept-Language', 'tr')
    lang = 'en' if accept_language.startswith('en') else 'tr'
    currency = 'gbp' if lang == 'en' else 'try'
    
    # Features çeviri mapping'i
    features_translation = {
        'tr': {
            '50 Randevu veya 7 Gün (Hangisi önce)': '50 Randevu veya 7 Gün (Hangisi önce)',
            'Randevu Hatırlatma Dahil': 'Randevu Hatırlatma Dahil',
            'Sınırsız Personel': 'Sınırsız Personel',
            'Sınırsız Müşteri': 'Sınırsız Müşteri',
            'Online Randevu': 'Online Randevu',
            'İstatistikler': 'İstatistikler',
            'Yapay Zeka Akıllı Asistan (Test)': 'Yapay Zeka Akıllı Asistan (Test)',
            '100 Randevu/Ay': '100 Randevu/Ay',
            '300 Randevu/Ay': '300 Randevu/Ay',
            '600 Randevu/Ay': '600 Randevu/Ay',
            '900 Randevu/Ay': '900 Randevu/Ay',
            '1.200 Randevu/Ay': '1.200 Randevu/Ay',
            'Sınırsız Randevu/Ay': 'Sınırsız Randevu/Ay',
            'Yapay Zeka Akıllı Asistan (Standart Kullanım)': 'Yapay Zeka Akıllı Asistan (Standart Kullanım)',
            'Yapay Zeka Akıllı Asistan (Gelişmiş Kullanım)': 'Yapay Zeka Akıllı Asistan (Gelişmiş Kullanım)',
            'Yapay Zeka Akıllı Asistan (Limitsiz)': 'Yapay Zeka Akıllı Asistan (Limitsiz)',
        },
        'en': {
            '50 Randevu veya 7 Gün (Hangisi önce)': '50 Appointments or 7 Days (Whichever comes first)',
            'Randevu Hatırlatma Dahil': 'Appointment Reminders Included',
            'Sınırsız Personel': 'Unlimited Staff',
            'Sınırsız Müşteri': 'Unlimited Customers',
            'Online Randevu': 'Online Appointment',
            'İstatistikler': 'Statistics',
            'Yapay Zeka Akıllı Asistan (Test)': 'AI Smart Assistant (Test)',
            '100 Randevu/Ay': '100 Appointments / Monthly',
            '300 Randevu/Ay': '300 Appointments / Monthly',
            '600 Randevu/Ay': '600 Appointments / Monthly',
            '900 Randevu/Ay': '900 Appointments / Monthly',
            '1.200 Randevu/Ay': '1,200 Appointments / Monthly',
            'Sınırsız Randevu/Ay': 'Unlimited Appointments / Monthly',
            'Yapay Zeka Akıllı Asistan (Standart Kullanım)': 'AI Smart Assistant (Standard Use)',
            'Yapay Zeka Akıllı Asistan (Gelişmiş Kullanım)': 'AI Smart Assistant (Advanced Use)',
            'Yapay Zeka Akıllı Asistan (Limitsiz)': 'AI Smart Assistant (Unlimited)',
        }
    }
    
    # İlk ay %25 indirimli fiyatları hesapla
    plans_with_discount = []
    for plan in PLANS:
        if plan['id'] == 'tier_trial':
            plan_copy = plan.copy()
            # Features'ları çevir
            if 'features' in plan_copy and lang == 'en':
                plan_copy['features'] = [features_translation['en'].get(f, f) for f in plan_copy['features']]
            plans_with_discount.append(plan_copy)
            continue
        
        plan_copy = plan.copy()
        
        # Stripe'dan fiyatları çek (GBP için)
        if currency == 'gbp':
            try:
                # Monthly fiyat
                monthly_lookup_key = get_stripe_lookup_key(plan['id'], 'monthly', 'gbp')
                monthly_price = get_stripe_price_by_lookup_key(monthly_lookup_key)
                if monthly_price:
                    plan_copy['price_monthly'] = monthly_price.unit_amount / 100  # Stripe cent'ten çevir
                    logger.info(f"✅ Stripe'dan GBP monthly fiyat çekildi: {plan['id']} = {plan_copy['price_monthly']} GBP")
                else:
                    logger.warning(f"⚠️ Stripe'dan GBP monthly fiyat bulunamadı: {plan['id']}, TRY fiyatı kullanılıyor")
                
                # Yearly fiyat
                yearly_lookup_key = get_stripe_lookup_key(plan['id'], 'yearly', 'gbp')
                yearly_price = get_stripe_price_by_lookup_key(yearly_lookup_key)
                if yearly_price:
                    plan_copy['price_yearly'] = yearly_price.unit_amount / 100  # Stripe cent'ten çevir
                    logger.info(f"✅ Stripe'dan GBP yearly fiyat çekildi: {plan['id']} = {plan_copy['price_yearly']} GBP")
                else:
                    # Yearly bulunamazsa monthly'den hesapla (veya TRY fiyatını kullan)
                    if 'price_monthly' in plan_copy:
                        plan_copy['price_yearly'] = plan_copy['price_monthly'] * 10
                    else:
                        logger.warning(f"⚠️ Stripe'dan GBP yearly fiyat bulunamadı: {plan['id']}, TRY fiyatı kullanılıyor")
            except Exception as e:
                logger.warning(f"⚠️ Stripe'dan GBP fiyat çekilemedi, TRY fiyatları kullanılıyor: {e}")
                # Hata durumunda TRY fiyatlarını kullan (plan_copy zaten plan.copy() ile oluşturuldu)
        
        # Features'ları çevir
        if 'features' in plan_copy:
            plan_copy['features'] = [features_translation.get(lang, features_translation['tr']).get(f, f) for f in plan_copy['features']]
        
        # İlk ay indirimli fiyatları hesapla
        plan_copy['price_monthly_original'] = plan_copy.get('price_monthly', plan['price_monthly'])
        plan_copy['price_monthly_discounted'] = int(plan_copy['price_monthly_original'] * 0.75)  # %25 indirim
        plan_copy['discount_percentage'] = 25
        plans_with_discount.append(plan_copy)
    
    return {"plans": plans_with_discount}

@api_router.get("/plan/current")
async def get_current_plan(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Mevcut plan bilgisini getir"""
    db = await get_db_from_request(request)
    plan_doc = await get_organization_plan(db, current_user.organization_id)
    if not plan_doc:
        raise HTTPException(status_code=404, detail="Plan bilgisi bulunamadı")
    
    plan_id = plan_doc.get('plan_id', 'tier_trial')
    plan_info = await get_plan_info(plan_id)
    if not plan_info:
        raise HTTPException(status_code=404, detail="Plan bilgisi geçersiz")
    
    # Datetime'ları string'e çevir
    billing_cycle = plan_doc.get('billing_cycle', 'monthly')
    
    # quota_limit zaten database'de aylık olarak tutuluyor (lazy quota reset mekanizması ile)
    # Yıllık plan için de aylık gösterilecek, sadece badge'de "Yıllık Plan" yazacak
    quota_limit = plan_doc.get('quota_limit')
    if not quota_limit:
        # Fallback: Eğer database'de quota_limit yoksa plan_info'dan al (aylık)
        quota_limit = plan_info.get('quota_monthly_appointments', 50)
    # Plan tanımı sınırsız ise (-1) DB kaydından bağımsız olarak override et
    if plan_info.get('quota_monthly_appointments') == -1:
        quota_limit = -1
    
    result = {
        "plan_id": plan_id,
        "plan_name": plan_info.get('name'),
        "quota_usage": plan_doc.get('quota_usage', 0),
        "quota_limit": quota_limit,
        "quota_reset_date": plan_doc.get('quota_reset_date').isoformat() if isinstance(plan_doc.get('quota_reset_date'), datetime) else plan_doc.get('quota_reset_date'),
        "is_first_month": plan_doc.get('is_first_month', False),
        "trial_start_date": plan_doc.get('trial_start_date').isoformat() if plan_doc.get('trial_start_date') and isinstance(plan_doc.get('trial_start_date'), datetime) else plan_doc.get('trial_start_date'),
        "trial_end_date": plan_doc.get('trial_end_date').isoformat() if plan_doc.get('trial_end_date') and isinstance(plan_doc.get('trial_end_date'), datetime) else plan_doc.get('trial_end_date'),
        "is_trial": plan_id == 'tier_trial',
        "billing_cycle": billing_cycle,
        "is_yearly": billing_cycle == 'yearly'
    }
    
    # Trial kontrolü
    if plan_id == 'tier_trial':
        trial_end = plan_doc.get('trial_end_date')
        if isinstance(trial_end, str):
            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
        if trial_end:
            result['trial_days_remaining'] = max(0, (trial_end - datetime.now(timezone.utc)).days)
    
    return result

@api_router.put("/plan/update")
async def update_plan(request: Request, plan_update: dict, current_user: UserInDB = Depends(get_current_user)):
    """Plan güncelle (şimdilik sadece plan_id değişikliği)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    new_plan_id = plan_update.get('plan_id')
    if not new_plan_id:
        raise HTTPException(status_code=400, detail="plan_id gerekli")
    
    plan_info = await get_plan_info(new_plan_id)
    if not plan_info:
        raise HTTPException(status_code=400, detail="Geçersiz plan_id")
    
    db = await get_db_from_request(request)
    
    # Mevcut plan bilgisini al
    plan_doc = await get_organization_plan(db, current_user.organization_id)
    
    # Yeni plana geç
    quota_reset = datetime.now(timezone.utc) + timedelta(days=30)
    # Trial dışına çıkarken is_first_month tekrar TRUE olmamalı
    is_first_month = False if new_plan_id != 'tier_trial' else False
    
    update_data = {
        "plan_id": new_plan_id,
        "quota_usage": 0,  # Yeni plana geçince sıfırla
        "quota_reset_date": quota_reset.isoformat(),
        "is_first_month": is_first_month,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Trial paketine geçiliyorsa trial tarihlerini ayarla
    if new_plan_id == 'tier_trial':
        trial_start = datetime.now(timezone.utc)
        trial_end = trial_start + timedelta(days=7)
        update_data['trial_start_date'] = trial_start.isoformat()
        update_data['trial_end_date'] = trial_end.isoformat()
    else:
        # Trial'dan çıkıyorsa trial tarihlerini temizle
        update_data['trial_start_date'] = None
        update_data['trial_end_date'] = None
    
    await db.organization_plans.update_one(
        {"organization_id": current_user.organization_id},
        {"$set": update_data}
    )
    
    return {"message": "Plan güncellendi", "plan_id": new_plan_id}

@api_router.post("/subscription/portal")
async def create_customer_portal_session(
    request: Request,
    current_user: UserInDB = Depends(get_current_user)
):
    """Stripe Customer Portal session oluştur (iptal, fatura görüntüleme vb.)"""
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        db = await get_db_from_request(request)
        
        # Mevcut plan bilgisini al
        plan_doc = await get_organization_plan(db, current_user.organization_id)
        if not plan_doc:
            raise HTTPException(status_code=404, detail="Plan bilgisi bulunamadı")
        
        current_plan_id = plan_doc.get('plan_id', 'tier_trial')
        
        # Trial'daysa portal'a gerek yok
        if current_plan_id == 'tier_trial':
            raise HTTPException(status_code=400, detail="Trial paketinde Stripe portal kullanılamaz")
        
        # Stripe customer_id'yi bul
        customer_id = None
        
        # Önce organization_plans'dan stripe_customer_id'yi kontrol et
        stripe_customer_id = plan_doc.get('stripe_customer_id')
        if stripe_customer_id:
            customer_id = stripe_customer_id
            logger.info(f"Customer ID organization_plans'dan alındı: {customer_id}")
        else:
            # Payment logs'dan bul
            try:
                payment_log = await db.payment_logs.find_one(
                    {
                        "organization_id": current_user.organization_id,
                        "status": {"$in": ["active", "completed"]}
                    },
                    sort=[("created_at", -1)]
                )
                
                if payment_log and payment_log.get('session_id'):
                    # Stripe session'dan customer_id'yi al
                    session = stripe.checkout.Session.retrieve(payment_log['session_id'])
                    customer_id = session.customer
                    logger.info(f"Customer ID payment_logs'dan alındı: {customer_id}")
            except Exception as e:
                logger.error(f"Customer ID bulunamadı: {e}")
        
        if not customer_id:
            logger.warning(f"Customer ID bulunamadı - org: {current_user.organization_id}, plan: {current_plan_id}")
            raise HTTPException(status_code=404, detail="Stripe müşteri bilgisi bulunamadı. Henüz bir ödeme yapmamış olabilirsiniz.")
        
        # Customer Portal Session oluştur
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=PAYMENT_SUCCESS_URL  # Portal'dan döndükten sonra gidilecek sayfa
        )
        
        logger.info(f"Stripe Customer Portal oluşturuldu: customer={customer_id}, org={current_user.organization_id}")
        
        return {
            "portal_url": portal_session.url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Customer Portal oluşturma hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Portal oluşturulamadı: {str(e)}")

@api_router.post("/payments/create-checkout-session")
async def create_checkout_session(
    request: Request,
    plan_request: PlanUpdateRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """PayTR ödeme oturumu oluştur"""
    try:
        # Maps normalized 'lookup_key' to the ACTUAL Stripe Coupon ID
        COUPON_MAP = {
            # --- MONTHLY TRY COUPONS (Turkey) ---
            'standard_monthly_try':     'qcrphAHF',  # LAUNCH_STD_TRY (-200 TL)
            'professional_monthly_try': 'LhtiDQfU',  # LAUNCH_PRO_TRY (-250 TL)
            'premium_monthly_try':      'aMUqlGOn',  # LAUNCH_PRE_TRY (-400 TL)
            'business_monthly_try':     'SJSEK6LZ',  # LAUNCH_BUS_TRY (-500 TL)
            'enterprise_monthly_try':   'EgiWhRFI',  # LAUNCH_ENT_TRY (-600 TL)
            'corporate_monthly_try':    'z7n9rmxE',  # LAUNCH_COR_TRY (-900 TL)
            # --- MONTHLY GBP COUPONS (UK) ---
            'standard_monthly_gbp':     'JqOc3ta6',  # LAUNCH_STD_GBP (-£4)
            'professional_monthly_gbp': 'drRoM3Kc',  # LAUNCH_PRO_GBP (-£6)
            'premium_monthly_gbp':      'NFnpf2Og',  # LAUNCH_PRE_GBP (-£8)
            'business_monthly_gbp':     'XOnrysiP',  # LAUNCH_BUS_GBP (-£10)
            'enterprise_monthly_gbp':   'C6g1vI2G',  # LAUNCH_ENT_GBP (-£14)
            'corporate_monthly_gbp':    'u4jV6TAJ',  # LAUNCH_COR_GBP (-£20)
        }
        
        # Log mesajını hem console'a hem de file'a yaz
        billing_cycle = plan_request.billing_cycle or "monthly"
        log_msg = f"Payment checkout session başlatılıyor: user={current_user.username}, plan_id={plan_request.plan_id}, billing_cycle={billing_cycle}"
        logger.info(log_msg)
        print(f"[PAYMENT] {log_msg}")  # Console'a da yaz
        
        if current_user.role != "admin":
            logger.warning(f"Payment endpoint: Yetkisiz erişim denemesi - user={current_user.username}, role={current_user.role}")
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        # Stripe ayarlarını kontrol et
        if not STRIPE_SECRET_KEY:
            logger.error("STRIPE_SECRET_KEY tanımlı değil!")
            raise HTTPException(status_code=500, detail="Ödeme sistemi yapılandırılmamış")
        
        # 1. İstenen planı bul ve fiyatını al
        plan = await get_plan_info(plan_request.plan_id)
        if not plan:
            logger.error(f"Plan bulunamadı: plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=404, detail="Plan bulunamadı")
        
        # Plan dict'inin gerekli alanlarını kontrol et
        if 'price_monthly' not in plan or 'name' not in plan:
            logger.error(f"Plan eksik alanlar içeriyor: plan={plan}, plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=500, detail="Plan verisi eksik veya geçersiz")
        
        # Yıllık/Aylık fiyat belirleme
        is_yearly = billing_cycle == "yearly"
        price_yearly = plan.get('price_yearly', plan.get('price_monthly', 0) * 10)
        
        # Trial paketini satın alınamaz
        if plan_request.plan_id == 'tier_trial':
            raise HTTPException(status_code=400, detail="Trial paketi satın alınamaz")
        
        db = await get_db_from_request(request)

        # 2. İndirimi uygula (organizasyon bazında sadece 1 kere)
        # NOT: is_first_month flag'ine güvenme; direkt payment_logs geçmişine bak.
        old_payment = await db.payment_logs.find_one({
            "organization_id": current_user.organization_id,
            "status": {"$in": ["completed", "active"]}
        })
        is_old_customer = bool(old_payment)
        is_first_month = not is_old_customer
        
        # price_monthly değerini güvenli şekilde al
        price_monthly = plan.get('price_monthly', 0)
        if not isinstance(price_monthly, (int, float)) or price_monthly < 0:
            logger.error(f"Geçersiz price_monthly değeri: {price_monthly}, plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=500, detail="Plan fiyatı geçersiz")
        
        # E-posta kontrolü
        user_email = (current_user.username or "").strip().lower()
        if not user_email or "@" not in user_email:
            logger.error(f"Geçersiz email (kullanıcı: {current_user.username}): {user_email}")
            raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi gerekli")
        
        # Para birimi algılama
        # Settings'den telefon numarasını al
        settings_doc = await db.settings.find_one({"organization_id": current_user.organization_id})
        user_phone = settings_doc.get("support_phone") if settings_doc else None
        
        currency = plan_request.currency or detect_currency(request, user_phone)
        currency_upper = currency.upper()  # 'GBP' veya 'TRY'
        
        logger.info(f"💱 Para birimi algılandı: {currency_upper} (plan_id={plan_request.plan_id}, phone={user_phone})")
        
        # Stripe Checkout Session oluştur
        try:
            # Yıllık veya aylık fiyat belirleme
            if is_yearly:
                # Yıllık abonelik - tek seferlik yıllık ödeme
                price_amount = price_yearly
                recurring_interval = 'year'
                plan_suffix = "(Yıllık)"
                # Yıllık ödemede ilk ay indirimi yok
                is_first_month = False
            else:
                # Aylık abonelik
                price_amount = price_monthly
                recurring_interval = 'month'
                plan_suffix = "(Aylık)"
            
            # Verbose logging: Raw payload
            logger.info(f"🔍 DEBUG - Raw Payload:")
            logger.info(f"   plan_id: '{plan_request.plan_id}'")
            logger.info(f"   currency: '{currency}'")
            logger.info(f"   billing_cycle: '{billing_cycle}'")
            
            # Lookup key ile Stripe'dan fiyat çekmeyi dene
            # Not: Lookup key currency içerir (örn: standard_monthly_gbp, professional_monthly_try)
            lookup_key = get_stripe_lookup_key(plan_request.plan_id, billing_cycle, currency)
            logger.info(f"🔑 Generated Lookup Key: '{lookup_key}'")
            
            stripe_price = get_stripe_price_by_lookup_key(lookup_key)
            
            # COUPON_MAP için lookup_key'i normalize et (standart -> standard)
            # Normalize: lowercase, strip whitespace, standart -> standard
            coupon_lookup_key = lookup_key.lower().strip()
            coupon_lookup_key = coupon_lookup_key.replace('standart_', 'standard_') if 'standart_' in coupon_lookup_key else coupon_lookup_key
            logger.info(f"🔑 Normalized Coupon Lookup Key: '{coupon_lookup_key}'")
            
            if stripe_price:
                # Lookup key ile fiyat bulundu, kullan
                logger.info(f"✅ Stripe lookup key ile fiyat bulundu: {lookup_key} (currency: {currency})")
                price = stripe_price
            else:
                # Lookup key ile bulunamadı, dinamik oluştur (fallback)
                logger.warning(f"⚠️ Stripe lookup key bulunamadı: {lookup_key}, dinamik fiyat oluşturuluyor")
                
                # Para birimine göre fiyat dönüşümü - Gerçek kur API kullan
                if currency == 'gbp':
                    # GBP fiyatları (plan'dan alınan TRY fiyatlarını GBP'ye çevir)
                    # Gerçek kur API'sinden kur bilgisi al
                    exchange_rate = await get_exchange_rate('TRY', 'GBP')
                    price_amount_gbp = price_amount * exchange_rate
                    price_kurus = int(price_amount_gbp * 100)  # GBP için pence
                    logger.info(f"💱 Kur dönüşümü: {price_amount} TRY × {exchange_rate:.6f} = {price_amount_gbp:.2f} GBP")
                else:
                    # TRY fiyatları
                    price_kurus = int(price_amount * 100)  # TRY için kuruş
                
                # Stripe Price objesi oluştur (fallback - lookup key kullanmıyoruz)
                # Not: lookup_key kullanmıyoruz çünkü Stripe'da zaten o key'e sahip fiyatlar olabilir
                # Bu dinamik fiyatlar geçici/fallback amaçlı, lookup key'e gerek yok
                price = stripe.Price.create(
                    currency=currency,
                    unit_amount=price_kurus,
                    recurring={'interval': recurring_interval},
                    product_data={
                        'name': f'PLANN {plan.get("name", "Plan")} {plan_suffix}'
                    }
                    # lookup_key kullanmıyoruz - çakışma önlemek için
                )
                logger.info(f"✅ Dinamik Stripe fiyat oluşturuldu (fallback): currency={currency}, amount={price_kurus}, lookup_key={lookup_key} (kullanılmadı)")
            
            logger.info(f"💰 Fiyat Hesaplama - Plan: {plan_request.plan_id}")
            logger.info(f"💰 Billing Cycle: {billing_cycle}")
            logger.info(f"💰 Currency: {currency_upper}")
            logger.info(f"💰 Fiyat: {price_amount} ({currency_upper}) ({recurring_interval})")
            logger.info(f"💰 is_first_month: {is_first_month}")
            
            # COUPON_MAP'ten coupon ID al (sadece aylık planlar için)
            coupon_id = None
            if (not is_yearly) and (not is_old_customer):
                # Explicit key check with verbose logging
                logger.info(f"🔍 Checking COUPON_MAP for key: '{coupon_lookup_key}'")
                logger.info(f"📋 Available Keys in COUPON_MAP: {list(COUPON_MAP.keys())}")
                
                if coupon_lookup_key in COUPON_MAP:
                    coupon_id = COUPON_MAP[coupon_lookup_key]
                    logger.info(f"✅ Coupon found: '{coupon_id}' for key '{coupon_lookup_key}'")
                else:
                    error_msg = f"❌ CRITICAL MISMATCH: Key '{coupon_lookup_key}' is NOT in COUPON_MAP."
                    logger.error(error_msg)
                    logger.error(f"📋 Available Keys in Map: {list(COUPON_MAP.keys())}")
                    logger.error(f"🔑 Original Lookup Key: '{lookup_key}'")
                    logger.error(f"🔑 Normalized Key: '{coupon_lookup_key}'")
                    raise ValueError(f"{error_msg} Available keys: {list(COUPON_MAP.keys())}")
            
            # Checkout Session oluştur
            # Native app için deep link, web için normal URL
            is_native = plan_request.platform in ['android', 'ios']
            
            # Domain algılama: Host/Origin/Referer üzerinden domain'i çıkar
            domain = _get_domain_from_request(request)
            
            success_url = PAYMENT_SUCCESS_URL_NATIVE if is_native else f"https://{domain}/?session_id={{CHECKOUT_SESSION_ID}}#/payment-success"
            cancel_url = PAYMENT_CANCEL_URL_NATIVE if is_native else f"https://{domain}/#/subscribe"
            
            logger.info(f"🌐 Domain algılandı: {domain}, cancel_url: {cancel_url}, success_url: {success_url}")
            
            session_params = {
                'payment_method_types': ['card'],
                'mode': 'subscription',
                'line_items': [{
                    'price': price.id,
                    'quantity': 1,
                }],
                'customer_email': user_email,
                'metadata': {
                    'user_id': current_user.organization_id,
                    'plan_id': plan_request.plan_id,
                    'organization_id': current_user.organization_id,
                    'is_first_month': str(is_first_month),
                    'billing_cycle': billing_cycle,
                    'currency': currency,
                    'appointment_limit': str(plan.get('quota_monthly_appointments', 0))  # Metadata'ya appointment_limit ekle
                },
                'success_url': success_url,
                'cancel_url': cancel_url,
                'billing_address_collection': 'required',
            }
            
            # COUPON_MAP'ten gelen coupon'u uygula (sadece monthly planlar için)
            if coupon_id:
                session_params['discounts'] = [{'coupon': coupon_id}]
                logger.info(f"🎁 COUPON_MAP coupon uygulandı: {coupon_id} (lookup_key: {coupon_lookup_key})")
            else:
                # Coupon yoksa promotion code'a izin ver
                session_params['allow_promotion_codes'] = True
            
            try:
                session = stripe.checkout.Session.create(**session_params)
            except stripe.error.StripeError as stripe_err:
                # Stripe hatası durumunda detaylı log
                logger.error(f"❌ Stripe Checkout Session Creation Failed:")
                logger.error(f"   Error Type: {type(stripe_err).__name__}")
                logger.error(f"   Error Message: {str(stripe_err)}")
                if coupon_id:
                    logger.error(f"   Attempted Coupon ID: '{coupon_id}'")
                    logger.error(f"   ⚠️ Coupon '{coupon_id}' might not exist in Stripe!")
                logger.error(f"   Session Params: {session_params}")
                # Re-raise the error so it's properly handled
                raise
            
            # Payment log oluştur
            if is_yearly:
                actual_amount = price_yearly
                original_amount = price_yearly
            else:
                actual_amount = price_monthly * 0.75 if is_first_month else price_monthly
                original_amount = price_monthly
            
            await db.payment_logs.insert_one({
                "session_id": session.id,
                "organization_id": current_user.organization_id,
                "user_id": current_user.username,
                "plan_id": plan_request.plan_id,
                "status": "pending",
                "amount": actual_amount,
                "original_amount": original_amount,
                "currency": currency_upper,
                "is_first_month": is_first_month,
                "discount_applied": is_first_month and not is_yearly,
                "billing_cycle": billing_cycle,
                "payment_provider": "stripe",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Stripe checkout session oluşturuldu: {session.id} - {plan_request.plan_id}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe hatası: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ödeme oturumu oluşturulamadı: {str(e)}")
        except Exception as e:
            logger.error(f"Stripe checkout session oluşturma hatası: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")
        
        # 3. Kullanıcı IP Adresini Al
        user_ip = request.client.host if request.client else "127.0.0.1"
        
        # 4. Benzersiz Sipariş ID'si Oluştur (Sadece alfanumerik karakterler)
        # PayTR özel karakter kabul etmez, organization_id'deki tireleri kaldır
        org_id_clean = current_user.organization_id.replace('-', '')
        timestamp_str = str(int(datetime.now(timezone.utc).timestamp()))
        merchant_oid = f"PLANN{org_id_clean}{timestamp_str}"
        
        # 5. BASİTLEŞTİRİLMİŞ KULLANICI BİLGİLERİ (None-Safe)
        
        # E-posta (Temel Kontrol)
        user_email = (current_user.username or "").strip().lower()
        if not user_email or "@" not in user_email or not re.match(r'^[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', user_email):
            logger.error(f"Geçersiz email (kullanıcı: {current_user.username}): {user_email}")
            raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi gerekli")
        
        user_name = (current_user.full_name or user_email.split('@')[0]).strip()[:50]
        
        # Adres ve Telefon (None-Safe Kontrol)
        settings = await db.settings.find_one({"organization_id": current_user.organization_id})
        
        user_address = "Adres Bilgisi Yok"  # PayTR boş kabul etmez
        user_phone = "05000000000"  # PayTR için geçerli bir varsayılan
        
        if settings:
            # DB'den gelen veriyi al ve 'str' olduğuna emin ol
            user_address_raw = str(settings.get("address", "")).strip()
            user_phone_raw = str(settings.get("support_phone", "")).strip()
            
            # Placeholder (TODO) metinlerini ve boşlukları temizle
            if user_address_raw and "Müşteri Adresi" not in user_address_raw:
                user_address = user_address_raw
            if user_phone_raw and "Müşteri Telefonu" not in user_phone_raw and len(user_phone_raw) >= 10:
                user_phone = user_phone_raw
        
        # 6. Sepet Bilgisi
        plan_name = plan.get('name', 'Plan')
        user_basket = base64.b64encode(json.dumps([
            [plan_name, str(price_to_pay), 1]
        ]).encode('utf-8')).decode('utf-8')  # UTF-8 kullan
        
        # 7. PayTR Ek Parametreleri
        no_installment = '1'  # Taksit yok
        max_installment = '0'  # Max taksit sayısı
        currency = 'TL'
        test_mode = '0'  # Production mode (1 = test mode)
        debug_on = '1'  # Debug açık
        timeout_limit = '30'  # Timeout süresi (dakika)
        store_card = '1'  # Kart tokenize et (recurring payment için)
        
        # 8. PAYTR TOKEN (HASH) OLUŞTURMA
        # Doğru sıra: merchant_id + user_ip + merchant_oid + email + payment_amount + user_basket + no_installment + max_installment + currency + test_mode
        # NOT: store_card hash'e dahil DEĞİL, sadece post_data'ya eklenir
        hash_str = f"{PAYTR_MERCHANT_ID}{user_ip}{merchant_oid}{user_email}{payment_amount_kurus}{user_basket}{no_installment}{max_installment}{currency}{test_mode}"
        
        paytr_token = base64.b64encode(hmac.new(
            PAYTR_MERCHANT_KEY.encode('utf-8'), 
            hash_str.encode('utf-8') + PAYTR_MERCHANT_SALT.encode('utf-8'), 
            hashlib.sha256
        ).digest()).decode('utf-8')
        
        # 9. PAYTR API'SİNE İSTEK GÖNDERME
        logger.info(f"PayTR için email: '{user_email}' (len: {len(user_email)}), user_ip: '{user_ip}'")
        
        post_data = {
            'merchant_id': PAYTR_MERCHANT_ID,
            'user_ip': user_ip,  # Zorunlu parametre
            'merchant_oid': merchant_oid,
            'email': user_email,  # 'user_email' değil, 'email' kullanılmalı!
            'payment_amount': payment_amount_kurus,
            'paytr_token': paytr_token,
            'user_basket': user_basket,
            'debug_on': debug_on,
            'no_installment': no_installment,
            'max_installment': max_installment,
            'user_name': user_name,
            'user_address': user_address[:400],  # Limiti aşmadığından emin ol
            'user_phone': user_phone[:20],
            'merchant_ok_url': PAYTR_SUCCESS_URL,
            'merchant_fail_url': PAYTR_FAIL_URL,
            'timeout_limit': timeout_limit,
            'currency': currency,
            'test_mode': test_mode,
            'store_card': store_card  # Kart saklama
        }
        
        # PayTR için kritik alanları logla
        logger.info(f"PayTR post_data hazırlandı: email='{post_data['email']}', user_ip='{post_data['user_ip']}', user_address='{post_data['user_address'][:50]}...', user_phone='{post_data['user_phone']}'")
        
        try:
            # PayTR'a isteği gönder - data parametresi form-urlencoded formatında gönderir
            response = requests.post(PAYTR_API_URL, data=post_data, timeout=10)
            logger.info(f"PayTR API HTTP Status: {response.status_code}")
            logger.info(f"PayTR API Response Text: {response.text}")
            
            # Debug: Gönderilen request body'yi logla
            if hasattr(response, 'request') and hasattr(response.request, 'body'):
                logger.info(f"PayTR Request Body (ilk 500 karakter): {str(response.request.body)[:500]}")
            
            # HTTP hata kontrolü
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                logger.error(f"PayTR API HTTP Hatası: {e}")
                logger.error(f"Response text: {response.text}")
                raise HTTPException(status_code=503, detail="Ödeme servisi şu an hizmet veremiyor.")
            
            # PayTR'den gelen yanıtı parse et
            try:
                res_data = response.json()
            except Exception as e:
                logger.error(f"PayTR yanıtı JSON parse edilemedi: {e}")
                logger.error(f"Response text: {response.text}")
                raise HTTPException(status_code=500, detail="Ödeme servisi yanıtı işlenemedi")
            
            logger.info(f"PayTR API yanıtı (JSON): {res_data}")
            
            # PayTR'den gelen hata detaylarını logla (status: 'failed' durumu)
            if res_data.get('status') != 'success':
                error_reason = res_data.get('reason', 'Bilinmeyen hata')
                error_details = res_data.get('errors', {})
                
                logger.error(f"PayTR HATA DETAYLARI: reason={error_reason}, errors={error_details}")
                logger.error(f"PayTR Full Response: {res_data}")
                
                if 'email' in str(error_details).lower() or 'user_email' in str(error_details).lower() or 'email' in str(error_reason).lower():
                    logger.error(f"EMAIL HATASI TESPİT EDİLDİ!")
                    logger.error(f"Gönderilen email: '{user_email}'")
                    logger.error(f"Email uzunluk: {len(user_email)}")
                    logger.error(f"Email bytes: {user_email.encode('utf-8')}")
                    logger.error(f"Email repr: {repr(user_email)}")
                    logger.error(f"Email karakterler (ilk 20): {[ord(c) for c in user_email[:20]]}")
                    
                    # Email'i hex formatında göster
                    logger.error(f"Email hex: {user_email.encode('utf-8').hex()}")
                    
                    # PayTR post_data'daki email'i göster
                    logger.error(f"post_data['user_email']: '{post_data.get('user_email')}'")
                    logger.error(f"post_data['user_email'] type: {type(post_data.get('user_email'))}")
                    
                    # Hata mesajını oluştur
                    if error_details:
                        error_details_list = []
                        for field, message in error_details.items():
                            error_details_list.append(f"{field}: {message}")
                        error_msg = f"{error_reason} - {', '.join(error_details_list)}"
                    else:
                        error_msg = error_reason
                    
                    logger.error(f"PayTR hatası nedeniyle HTTPException fırlatılıyor: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Ödeme başlatılamadı: {error_msg}")
            
            if res_data.get('status') == 'success':
                # 7. BAŞARILI: ÖDEME LİNKİNİ (TOKEN) AL
                paytr_iframe_token = res_data.get('token')
                
                if not paytr_iframe_token:
                    logger.error(f"PayTR başarılı ama token yok: {res_data}")
                    raise HTTPException(status_code=500, detail="PayTR token alınamadı")
                
                # Bu link, frontend'i PayTR ödeme sayfasına yönlendirecek
                checkout_url = f"https://www.paytr.com/odeme/guvenli/{paytr_iframe_token}"
                
                # 8. 'merchant_oid'yi veritabanına 'pending' olarak kaydet
                await db.payment_logs.insert_one({
                    "merchant_oid": merchant_oid,
                    "organization_id": current_user.organization_id,
                    "user_id": current_user.username,
                    "plan_id": plan_request.plan_id,
                    "status": "pending",
                    "amount": price_to_pay,
                    "amount_kurus": payment_amount_kurus,
                    "is_first_month": is_first_month,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
                logger.info(f"PayTR checkout session oluşturuldu: {merchant_oid} - {plan_request.plan_id}")
                return {"checkout_url": checkout_url}
            else:
                # PayTR token oluşturamadı
                # PayTR hata mesajını düzgün çıkar
                error_reason = res_data.get('reason', 'Bilinmeyen hata')
                errors = res_data.get('errors', {})
                
                # Eğer errors dict'i varsa, içindeki hataları birleştir
                if errors:
                    error_details = []
                    for field, message in errors.items():
                        error_details.append(f"{field}: {message}")
                    error_msg = f"{error_reason} - {', '.join(error_details)}"
                else:
                    error_msg = error_reason
                
                logger.error(f"PayTR token alma hatası: reason={error_reason}, errors={errors}, full_response={res_data}")
                raise HTTPException(status_code=500, detail=f"Ödeme başlatılamadı: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"PayTR API isteği hatası: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail="Ödeme servisi şu an hizmet veremiyor.")
    
    except HTTPException:
        # HTTPException'ları tekrar fırlat (zaten doğru şekilde işlenmiş)
        raise
    except AttributeError as e:
        # NoneType hatası veya eksik attribute hatası
        logger.error(f"create_checkout_session İÇİNDE AttributeError: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Veri hatası: {str(e)}")
    except Exception as e:
        # BU, TÜM DİĞER (AttributeError vb.) ÇÖKMELERİ YAKALAR
        logger.error(f"create_checkout_session İÇİNDE BEKLENMEDİK HATA: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")


class StripeConfirmCheckoutRequest(BaseModel):
    session_id: str


@api_router.post("/payments/confirm-checkout-session")
async def confirm_stripe_checkout_session(
    request: Request,
    body: StripeConfirmCheckoutRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

        if not STRIPE_SECRET_KEY:
            logger.error("STRIPE_SECRET_KEY tanımlı değil!")
            raise HTTPException(status_code=500, detail="Ödeme sistemi yapılandırılmamış")

        session_id = (body.session_id or "").strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id gerekli")

        logger.info(f"🔁 Confirm checkout session requested: session_id={session_id}, org={current_user.organization_id}")

        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['line_items.data.price.product']
        )

        payment_status = session.get('payment_status')
        status_value = session.get('status')
        if payment_status not in ('paid', 'no_payment_required') and status_value != 'complete':
            raise HTTPException(status_code=400, detail=f"Ödeme tamamlanmamış (payment_status={payment_status}, status={status_value})")

        metadata = session.get('metadata', {}) or {}
        organization_id = metadata.get('organization_id') or metadata.get('user_id')
        if organization_id and organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="session organization uyumsuz")
        organization_id = current_user.organization_id

        db = await get_db_from_request(request)

        payment_log = await db.payment_logs.find_one({"session_id": session_id})
        if payment_log and payment_log.get("status") == "active":
            try:
                plan_id_existing = payment_log.get('plan_id') or (metadata.get('plan_id') if isinstance(metadata, dict) else None)
                plan_data_existing = await get_plan_info(plan_id_existing) if plan_id_existing else None
                plan_name_existing = (plan_data_existing or {}).get('name') or plan_id_existing or ''
                billing_cycle_existing = payment_log.get('billing_cycle') or (metadata.get('billing_cycle', 'monthly') if isinstance(metadata, dict) else 'monthly')
                await _send_subscription_email_once(
                    db=db,
                    request=request,
                    organization_id=organization_id,
                    session_id=session_id,
                    plan_name=plan_name_existing,
                    billing_cycle=billing_cycle_existing,
                    payment_log=payment_log,
                )
            except Exception as e:
                logger.warning(f"Subscription email (already processed) gönderilemedi: {e}")
            return {"status": "ok", "already_processed": True}

        plan_id = None
        if payment_log:
            plan_id = payment_log.get('plan_id')
        if not plan_id:
            plan_id = metadata.get('plan_id')
        if not plan_id:
            raise HTTPException(status_code=400, detail="Plan bilgisi bulunamadı")

        plan_data = await get_plan_info(plan_id)
        if not plan_data:
            raise HTTPException(status_code=400, detail="Plan bulunamadı")

        billing_cycle = metadata.get('billing_cycle', 'monthly')

        appointment_limit = None
        quota_limit = None
        try:
            line_items = session.get('line_items', {})
            if isinstance(line_items, dict) and 'data' in line_items:
                line_items = line_items['data']
            elif not isinstance(line_items, list):
                line_items = []

            if line_items and len(line_items) > 0:
                price_obj = line_items[0].get('price')
                if price_obj:
                    price_metadata = price_obj.get('metadata', {})
                    appointment_limit = price_metadata.get('appointment_limit')
                    if not appointment_limit:
                        product_obj = price_obj.get('product')
                        if isinstance(product_obj, dict):
                            product_metadata = product_obj.get('metadata', {})
                            appointment_limit = product_metadata.get('appointment_limit')
                        elif isinstance(product_obj, str):
                            try:
                                product_retrieved = stripe.Product.retrieve(product_obj)
                                product_metadata = product_retrieved.get('metadata', {})
                                appointment_limit = product_metadata.get('appointment_limit')
                            except Exception as e:
                                logger.warning(f"⚠️ Product retrieve hatası: {e}")

                    if appointment_limit:
                        try:
                            quota_limit = int(appointment_limit)
                        except (ValueError, TypeError):
                            quota_limit = None

            if not quota_limit:
                appointment_limit = metadata.get('appointment_limit')
                if appointment_limit:
                    try:
                        quota_limit = int(appointment_limit)
                    except (ValueError, TypeError):
                        quota_limit = None
            if not quota_limit:
                quota_limit = plan_data.get('quota_monthly_appointments', 100)
        except Exception as e:
            logger.error(f"❌ Confirm: appointment_limit alınırken hata: {e}")
            quota_limit = plan_data.get('quota_monthly_appointments', 100)

        now = datetime.now(timezone.utc)
        if billing_cycle == 'yearly':
            quota_reset = now + timedelta(days=365)
        else:
            quota_reset = now + timedelta(days=30)

        update_data = {
            "plan_id": plan_id,
            "quota_usage": 0,
            "quota_limit": quota_limit,
            "quota_reset_date": quota_reset.isoformat(),
            "quota_last_reset_date": now.isoformat(),
            "is_first_month": False,
            "billing_cycle": billing_cycle,
            "updated_at": now.isoformat(),
            "trial_start_date": None,
            "trial_end_date": None,
        }

        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        if subscription_id:
            update_data['stripe_subscription_id'] = subscription_id
            update_data['stripe_customer_id'] = customer_id
            update_data['next_billing_date'] = quota_reset.isoformat()

        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {"$set": update_data},
            upsert=True
        )

        await db.payment_logs.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "active",
                "completed_at": now.isoformat(),
                "subscription_id": subscription_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id
            }},
            upsert=True
        )

        try:
            updated_payment_log = await db.payment_logs.find_one({"session_id": session_id})
            await _send_subscription_email_once(
                db=db,
                request=request,
                organization_id=organization_id,
                session_id=session_id,
                plan_name=plan_data.get('name') if isinstance(plan_data, dict) else plan_id,
                billing_cycle=billing_cycle,
                payment_log=updated_payment_log,
            )
        except Exception as e:
            logger.warning(f"Subscription email gönderilemedi: {e}")

        return {"status": "ok", "plan_id": plan_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Confirm checkout session hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Confirm işlemi başarısız")

@api_router.post("/webhook/stripe")
async def handle_stripe_webhook(request: Request):
    """Stripe webhook - Ödeme başarılı olduğunda çağrılır"""
    # Stripe webhook secret kontrolü
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET tanımlı değil!")
        return Response(content="ERROR", status_code=500)
    
    try:
        # Stripe webhook signature doğrulaması
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not sig_header:
            logger.warning("Stripe webhook: stripe-signature header eksik")
            return Response(content="ERROR", status_code=400)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Stripe webhook: Invalid payload - {e}")
            return Response(content="ERROR", status_code=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook: Invalid signature - {e}")
            return Response(content="ERROR", status_code=400)
        
        # === SIGNATURE DOĞRULANDI, WEBHOOK GÜVENLİ ===
        logger.info(f"✅ Stripe webhook event: {event['type']}")
        
        db = await get_db_from_request(request)
        
        # checkout.session.completed - Ödeme başarılı
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            
            logger.info(f"💳 Ödeme başarılı: session_id={session_id}")
            
            # Payment log'u bul
            payment_log = await db.payment_logs.find_one({"session_id": session_id})
            
            if not payment_log:
                metadata = session.get('metadata', {}) or {}
                plan_id_meta = metadata.get('plan_id')
                organization_id_meta = metadata.get('organization_id') or metadata.get('user_id')
                if not plan_id_meta or not organization_id_meta:
                    logger.error(f"Webhook hatası: session_id={session_id} payment_logs kaydı yok ve metadata eksik (plan_id/org_id).")
                    return Response(content="OK", status_code=200)

                billing_cycle_meta = metadata.get('billing_cycle', 'monthly')
                customer_email = session.get('customer_email')
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.payment_logs.update_one(
                    {"session_id": session_id},
                    {
                        "$setOnInsert": {
                            "session_id": session_id,
                            "organization_id": organization_id_meta,
                            "user_id": customer_email,
                            "plan_id": plan_id_meta,
                            "status": "pending",
                            "payment_provider": "stripe",
                            "created_at": now_iso,
                        },
                        "$set": {
                            "stripe_customer_id": session.get('customer'),
                            "stripe_subscription_id": session.get('subscription'),
                            "billing_cycle": billing_cycle_meta,
                            "currency": (session.get('currency') or '').upper() or None,
                            "updated_at": now_iso,
                        }
                    },
                    upsert=True
                )
                payment_log = await db.payment_logs.find_one({"session_id": session_id})
                logger.warning(f"Webhook: payment_logs kaydı yoktu, metadata ile upsert edildi. session_id={session_id}, org={organization_id_meta}, plan={plan_id_meta}")
            
            if payment_log.get("status") == "active":
                logger.info(f"Webhook: {session_id} zaten işlenmiş.")
                return Response(content="OK", status_code=200)
            
            # 4. ABONELİĞİ GÜNCELLE (Kritik Mantık)
            plan_id = payment_log.get("plan_id")
            organization_id = payment_log.get("organization_id")
            
            plan_data = await get_plan_info(plan_id)
            if not plan_data:
                logger.error(f"Webhook hatası: Plan {plan_id} bulunamadı.")
                return Response(content="OK", status_code=200)
            
            # Mevcut plan bilgisini al
            plan_doc = await get_organization_plan(db, organization_id)
            
            # Billing cycle'ı metadata'dan al
            metadata = session.get('metadata', {})
            billing_cycle = metadata.get('billing_cycle', 'monthly')
            
            # TASK 1: appointment_limit'i Price Object'in metadata'sından al (Single Source of Truth)
            # Stripe session'da line_items var, onun içindeki price'ın metadata'sına bakmalıyız
            appointment_limit = None
            quota_limit = None
            
            try:
                # TASK 1: Price Object'in metadata'sından appointment_limit almak için
                # Stripe session'da line_items expand edilmemiş olabilir, retrieve et
                # Product metadata fallback için product'ı da expand et
                session_expanded = stripe.checkout.Session.retrieve(
                    session_id,
                    expand=['line_items.data.price.product']
                )
                
                line_items = session_expanded.get('line_items', {})
                if isinstance(line_items, dict) and 'data' in line_items:
                    line_items = line_items['data']
                elif not isinstance(line_items, list):
                    line_items = []
                
                # İlk line item'dan price'ı al
                if line_items and len(line_items) > 0:
                    price_obj = line_items[0].get('price')
                    if price_obj:
                        # FALLBACK STRATEGY: First check price.metadata, then product.metadata
                        # Step 1: Check Price metadata
                        price_metadata = price_obj.get('metadata', {})
                        appointment_limit = price_metadata.get('appointment_limit')
                        
                        # Step 2: If not found in price, check product metadata
                        if not appointment_limit:
                            product_obj = price_obj.get('product')
                            if product_obj:
                                # product_obj can be a string (ID) or dict (expanded)
                                if isinstance(product_obj, dict):
                                    product_metadata = product_obj.get('metadata', {})
                                    appointment_limit = product_metadata.get('appointment_limit')
                                    if appointment_limit:
                                        logger.info(f"✅ Appointment limit Product metadata'dan alındı (fallback): {appointment_limit}")
                                elif isinstance(product_obj, str):
                                    # Product not expanded, retrieve it
                                    try:
                                        product_retrieved = stripe.Product.retrieve(product_obj)
                                        product_metadata = product_retrieved.get('metadata', {})
                                        appointment_limit = product_metadata.get('appointment_limit')
                                        if appointment_limit:
                                            logger.info(f"✅ Appointment limit Product metadata'dan alındı (fallback, retrieved): {appointment_limit}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Product retrieve hatası: {e}")
                        
                        if appointment_limit:
                            try:
                                quota_limit = int(appointment_limit)
                                source = "Price metadata" if price_metadata.get('appointment_limit') else "Product metadata"
                                logger.info(f"✅ Appointment limit {source}'dan alındı: {quota_limit} (Monthly Capacity)")
                            except (ValueError, TypeError):
                                logger.warning(f"⚠️ Metadata'daki appointment_limit geçersiz: {appointment_limit}")
                        else:
                            logger.warning(f"⚠️ Price ve Product metadata'da appointment_limit bulunamadı. Price ID: {price_obj.get('id')}")
                
                if not quota_limit:
                    # Fallback: Session metadata'dan dene
                    appointment_limit = metadata.get('appointment_limit')
                    if appointment_limit:
                        try:
                            quota_limit = int(appointment_limit)
                            logger.info(f"✅ Appointment limit session metadata'dan alındı: {quota_limit}")
                        except (ValueError, TypeError):
                            pass
                
                # Son fallback: Plan'dan al
                if not quota_limit:
                    quota_limit = plan_data.get('quota_monthly_appointments', 100)
                    logger.warning(f"⚠️ Appointment limit Price metadata'dan alınamadı, plan'dan alındı: {quota_limit}")
                    
            except Exception as e:
                logger.error(f"❌ Price metadata'dan appointment_limit alınırken hata: {e}")
                # Fallback: Plan'dan al
                quota_limit = plan_data.get('quota_monthly_appointments', 100)
                logger.warning(f"⚠️ Hata nedeniyle appointment limit plan'dan alındı: {quota_limit}")
            
            # CRITICAL RULE: quota_limit metadata'daki değer aynen kullanılır (Monthly Capacity)
            # Yearly planlar için 12 ile çarpılmaz - her ay aynı limit yenilenir
            logger.info(f"📊 Quota limit kaydediliyor: {quota_limit} (Monthly Capacity, billing_cycle={billing_cycle})")
            
            # Yeni plana geç - yıllık ise 365 gün, aylık ise 30 gün
            if billing_cycle == 'yearly':
                quota_reset = datetime.now(timezone.utc) + timedelta(days=365)
            else:
                quota_reset = datetime.now(timezone.utc) + timedelta(days=30)
            
            # quota_last_reset_date'i şimdi olarak ayarla (lazy reset için)
            now = datetime.now(timezone.utc)
            
            update_data = {
                "plan_id": plan_id,
                "quota_usage": 0,  # Yeni plana geçince sıfırla
                "quota_limit": quota_limit,  # Price metadata'dan alınan appointment_limit (Monthly Capacity)
                "quota_reset_date": quota_reset.isoformat(),
                "quota_last_reset_date": now.isoformat(),  # Lazy reset için son reset tarihi
                "is_first_month": False,  # Artık indirim kullanamaz
                "billing_cycle": billing_cycle,  # Yıllık/Aylık bilgisi
                "updated_at": now.isoformat()
            }
            
            # Trial tarihlerini temizle
            update_data['trial_start_date'] = None
            update_data['trial_end_date'] = None
            
            # Stripe subscription bilgilerini kaydet
            subscription_id = session.get('subscription')
            customer_id = session.get('customer')
            
            if subscription_id:
                update_data['stripe_subscription_id'] = subscription_id
                update_data['stripe_customer_id'] = customer_id
                update_data['next_billing_date'] = quota_reset.isoformat()
                logger.info(f"Stripe subscription kaydedildi: organization_id={organization_id}, subscription_id={subscription_id}, billing_cycle={billing_cycle}")
            
            await db.organization_plans.update_one(
                {"organization_id": organization_id},
                {"$set": update_data},
                upsert=True
            )
            
            # 5. Ödeme kaydını 'active' yap
            await db.payment_logs.update_one(
                {"session_id": session_id},
                {"$set": {
                    "status": "active",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "subscription_id": subscription_id
                }}
            )
            
            logger.info(f"✅ STRIPE BAŞARILI: {session_id} - Plan güncellendi. Organization: {organization_id}, Plan: {plan_id}")

            try:
                updated_payment_log = await db.payment_logs.find_one({"session_id": session_id})
                await _send_subscription_email_once(
                    db=db,
                    request=request,
                    organization_id=organization_id,
                    session_id=session_id,
                    plan_name=plan_data.get('name') if isinstance(plan_data, dict) else plan_id,
                    billing_cycle=billing_cycle,
                    payment_log=updated_payment_log,
                )
            except Exception as e:
                logger.warning(f"Subscription email (webhook) gönderilemedi: {e}")
        
        # customer.subscription.updated - Abonelik güncellendi (iptal planlandı)
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            cancel_at_period_end = subscription.get('cancel_at_period_end', False)
            
            if cancel_at_period_end:
                logger.info(f"⚠️ Abonelik iptal planlandı (dönem sonunda): subscription_id={subscription_id}")
                
                # Subscription ID ile organization'ı bul
                plan_doc = await db.organization_plans.find_one({"stripe_subscription_id": subscription_id})
                
                if plan_doc:
                    organization_id = plan_doc.get('organization_id')
                    # İsteğe bağlı: Organization'a bildirim gönderebilirsiniz
                    logger.info(f"ℹ️ Organization {organization_id} aboneliğini dönem sonunda iptal edecek")
        
        # customer.subscription.deleted - Abonelik iptal edildi
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            customer_id = subscription['customer']
            
            logger.info(f"🚫 Abonelik iptal edildi: subscription_id={subscription_id}, customer_id={customer_id}")
            
            # Subscription ID ile organization'ı bul
            plan_doc = await db.organization_plans.find_one({"stripe_subscription_id": subscription_id})
            
            if not plan_doc:
                logger.warning(f"Webhook: subscription_id={subscription_id} için organization bulunamadı")
                return Response(content="OK", status_code=200)
            
            organization_id = plan_doc.get('organization_id')
            
            # Trial'a döndür
            trial_start = datetime.now(timezone.utc)
            trial_end = trial_start + timedelta(days=7)
            
            update_data = {
                "plan_id": "tier_trial",
                "quota_usage": 0,
                "quota_reset_date": trial_end.isoformat(),
                "trial_start_date": trial_start.isoformat(),
                "trial_end_date": trial_end.isoformat(),
                "is_first_month": False,
                "stripe_subscription_id": None,
                "stripe_customer_id": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.organization_plans.update_one(
                {"organization_id": organization_id},
                {"$set": update_data}
            )
            
            logger.info(f"✅ Abonelik iptal edildi ve trial'a döndürüldü: organization_id={organization_id}")
        
        # Diğer event'ler için
        logger.info(f"ℹ️ Stripe webhook event işlendi: {event['type']}")
        return Response(content="OK", status_code=200)
        
    except Exception as e:
        logger.error(f"Stripe webhook işleme hatası: {e}", exc_info=True)
        return Response(content="ERROR", status_code=500)


@api_router.post("/payments/webhook/stripe")
async def handle_stripe_webhook_compat(request: Request):
    return await handle_stripe_webhook(request)


@app.post("/webhook/stripe")
async def handle_stripe_webhook_root(request: Request):
    return await handle_stripe_webhook(request)


@app.post("/payments/webhook/stripe")
async def handle_stripe_webhook_payments_root(request: Request):
    return await handle_stripe_webhook(request)

@api_router.post("/payments/process-recurring")
async def process_recurring_payment(request: Request, organization_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Kayıtlı kart ile recurring payment çek (Internal API - Cron job için)"""
    try:
        # Sadece superadmin veya sistem çağrısı yapabilir
        if current_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        db = await get_db_from_request(request)
        
        # Organization plan bilgilerini al
        plan_doc = await get_organization_plan(db, organization_id)
        if not plan_doc:
            logger.error(f"Recurring payment: Plan bulunamadı - organization_id={organization_id}")
            return {"status": "error", "message": "Plan bulunamadı"}
        
        # Kart token bilgilerini kontrol et
        if not plan_doc.get('card_saved') or not plan_doc.get('payment_utoken') or not plan_doc.get('payment_ctoken'):
            logger.warning(f"Recurring payment: Kayıtlı kart yok - organization_id={organization_id}")
            return {"status": "error", "message": "Kayıtlı kart bulunamadı"}
        
        utoken = plan_doc.get('payment_utoken')
        ctoken = plan_doc.get('payment_ctoken')
        plan_id = plan_doc.get('plan_id')
        
        # Plan bilgilerini al
        plan_info = await get_plan_info(plan_id)
        if not plan_info:
            logger.error(f"Recurring payment: Plan info bulunamadı - plan_id={plan_id}")
            return {"status": "error", "message": "Plan bilgisi bulunamadı"}
        
        # Ödeme tutarı (recurring'de indirim yok)
        price_monthly = plan_info.get('price_monthly', 0)
        payment_amount_kurus = int(price_monthly * 100)
        
        # Organization bilgilerini al
        user = await db.users.find_one({"organization_id": organization_id, "role": "admin"})
        if not user:
            logger.error(f"Recurring payment: Admin user bulunamadı - organization_id={organization_id}")
            return {"status": "error", "message": "Admin kullanıcı bulunamadı"}
        
        user_email = user.get('username', 'noreply@royalpremiumcare.com')
        user_name = user.get('full_name', 'Kullanıcı')
        
        # Settings'den adres ve telefon al
        settings = await db.settings.find_one({"organization_id": organization_id})
        user_address = settings.get('address', 'Adres Bilgisi Yok') if settings else 'Adres Bilgisi Yok'
        user_phone = settings.get('support_phone', '05000000000') if settings else '05000000000'
        
        # Merchant OID oluştur
        org_id_clean = organization_id.replace('-', '')
        timestamp_str = str(int(datetime.now(timezone.utc).timestamp()))
        merchant_oid = f"RECUR{org_id_clean}{timestamp_str}"
        
        # User IP (sistem iç çağrısı için)
        user_ip = request.client.host if request.client else "127.0.0.1"
        
        # Sepet bilgisi
        plan_name = plan_info.get('name', 'Plan')
        user_basket = base64.b64encode(json.dumps([
            [plan_name, str(price_monthly), 1]
        ]).encode('utf-8')).decode('utf-8')
        
        # PayTR parametreleri
        no_installment = '1'
        max_installment = '0'
        currency = 'TL'
        test_mode = '0'
        non_3d = '1'  # Recurring payment için Non-3D zorunlu
        payment_type = 'card'
        
        # Hash oluştur (recurring payment için farklı sıra)
        hash_str = f"{PAYTR_MERCHANT_ID}{user_ip}{merchant_oid}{user_email}{payment_amount_kurus}{payment_type}0{currency}{test_mode}{non_3d}"
        paytr_token = base64.b64encode(hmac.new(
            PAYTR_MERCHANT_KEY.encode('utf-8'), 
            hash_str.encode('utf-8') + PAYTR_MERCHANT_SALT.encode('utf-8'), 
            hashlib.sha256
        ).digest()).decode('utf-8')
        
        # PayTR API'sine recurring payment isteği gönder
        post_data = {
            'merchant_id': PAYTR_MERCHANT_ID,
            'user_ip': user_ip,
            'merchant_oid': merchant_oid,
            'email': user_email,
            'payment_type': payment_type,
            'payment_amount': payment_amount_kurus,
            'currency': currency,
            'test_mode': test_mode,
            'non_3d': non_3d,
            'merchant_ok_url': PAYTR_SUCCESS_URL,
            'merchant_fail_url': PAYTR_FAIL_URL,
            'user_name': user_name,
            'user_address': user_address[:400],
            'user_phone': user_phone[:20],
            'user_basket': user_basket,
            'debug_on': '1',
            'paytr_token': paytr_token,
            'utoken': utoken,
            'ctoken': ctoken,
            'installment_count': '0'
        }
        
        # Payment log oluştur
        payment_log = {
            "merchant_oid": merchant_oid,
            "organization_id": organization_id,
            "plan_id": plan_id,
            "amount": price_monthly,
            "status": "pending",
            "payment_type": "recurring",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.payment_logs.insert_one(payment_log)
        
        # PayTR'a istek gönder
        logger.info(f"Recurring payment başlatılıyor: organization_id={organization_id}, merchant_oid={merchant_oid}")
        response = requests.post("https://www.paytr.com/odeme", data=post_data, timeout=15)
        
        logger.info(f"PayTR recurring response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            res_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            
            if res_data.get('status') == 'success':
                logger.info(f"Recurring payment başarılı: organization_id={organization_id}")
                return {"status": "success", "message": "Ödeme başarılı", "merchant_oid": merchant_oid}
            else:
                error_msg = res_data.get('reason', 'Bilinmeyen hata')
                logger.error(f"Recurring payment başarısız: {error_msg}")
                
                # Başarısız ödeme kaydını güncelle
                await db.payment_logs.update_one(
                    {"merchant_oid": merchant_oid},
                    {"$set": {"status": "failed", "failed_reason": error_msg}}
                )
                
                return {"status": "failed", "message": error_msg}
        else:
            logger.error(f"PayTR recurring HTTP hatası: {response.status_code}")
            return {"status": "error", "message": "Ödeme servisi hatası"}
            
    except Exception as e:
        logger.error(f"Recurring payment işleme hatası: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@api_router.get("/stats/dashboard")
async def get_dashboard_stats(request: Request, current_user: UserInDB = Depends(get_current_user)):
    # 1. Yetki Kontrolü
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    # 2. SuperAdmin için sabit response
    if current_user.role == "superadmin":
        return {
            "today_appointments": 0, "today_completed": 0, "today_income": 0,
            "bugunku_toplam_hizmet_tutari": 0, "month_income": 0, "quota": None
        }
    
    logger.info(f"📊 Stats endpoint çağrıldı - Organization: {current_user.organization_id}")
    db = await get_db_from_request(request)
    turkey_tz = ZoneInfo("Europe/Istanbul")
    now = datetime.now(turkey_tz)
    today = now.date().isoformat()
    base_query = {"organization_id": current_user.organization_id}
    
    # --- OTOMATİK TAMAMLAMA MANTIĞI ---
    # Süresi geçen "Bekliyor" randevuları bul
    today_waiting_appointments = await db.appointments.find(
        {**base_query, "appointment_date": today, "status": "Bekliyor"},
        {"_id": 0, "id": 1, "appointment_date": 1, "appointment_time": 1, "service_price": 1, "customer_name": 1, "service_name": 1, "service_id": 1, "staff_member_id": 1}
    ).to_list(1000)

    if today_waiting_appointments:
        # Servis sürelerini toplu çek
        service_ids = list(set(appt.get('service_id') for appt in today_waiting_appointments if appt.get('service_id')))
        services_dict = {}
        if service_ids:
            services = await db.services.find(
                {"id": {"$in": service_ids}, "organization_id": current_user.organization_id},
                {"_id": 0, "id": 1, "duration": 1}
            ).to_list(100)
            services_dict = {s['id']: s.get('duration', 30) for s in services}

        ids_to_update = []
        transactions_to_create = []
        for appt in today_waiting_appointments:
            try:
                dt_str = f"{appt['appointment_date']} {appt['appointment_time']}"
                appointment_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=turkey_tz)
                duration = services_dict.get(appt.get('service_id'), 30)
                if now >= (appointment_dt + timedelta(minutes=duration)):
                    ids_to_update.append(appt['id'])
                    transactions_to_create.append(Transaction(
                        organization_id=current_user.organization_id,
                        appointment_id=appt['id'],
                        customer_name=appt['customer_name'],
                        service_name=appt['service_name'],
                        amount=appt.get('service_price', 0) or 0,
                        date=appt['appointment_date'],
                        staff_member_id=appt.get('staff_member_id')
                    ).model_dump(mode='json'))
            except Exception as e:
                logging.warning(f"Randevu {appt['id']} işlenirken hata: {e}")

        if ids_to_update:
            await db.appointments.update_many(
                {"organization_id": current_user.organization_id, "id": {"$in": ids_to_update}},
                {"$set": {"status": "Tamamlandı", "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
        if transactions_to_create:
            for t in transactions_to_create: t['created_at'] = datetime.now(timezone.utc).isoformat() if 'created_at' not in t else t['created_at']
            await db.transactions.insert_many(transactions_to_create)

    # --- İSTATİSTİK HESAPLAMA ---
    today_appointments = await db.appointments.count_documents({**base_query, "appointment_date": today, "status": {"$ne": "İptal"}})
    today_completed_list = await db.appointments.find(
        {**base_query, "appointment_date": today, "status": "Tamamlandı"},
        {"service_price": 1}
    ).to_list(1000)
    
    today_completed = len(today_completed_list)
    bugunku_toplam_hizmet_tutari = sum(apt.get('service_price', 0) or 0 for apt in today_completed_list)
    
    today_transactions = await db.transactions.find({**base_query, "date": today}).to_list(1000)
    today_income = sum(t.get('amount', 0) or 0 for t in today_transactions)
    
    month_start = now.date().replace(day=1).isoformat()
    month_transactions = await db.transactions.find({**base_query, "date": {"$gte": month_start}}).to_list(2000)
    month_income = sum(t.get('amount', 0) or 0 for t in month_transactions)

    # --- KOTA BİLGİSİ ---
    plan_doc = await get_organization_plan(db, current_user.organization_id)
    quota_info = None
    if plan_doc:
        plan_id = plan_doc.get('plan_id', 'tier_trial')
        plan_info = await get_plan_info(plan_id)
        if plan_info:
            quota_usage = plan_doc.get('quota_usage', 0)
            quota_limit = plan_doc.get('quota_limit') or plan_info.get('quota_monthly_appointments', 50)
            quota_remaining = -1 if quota_limit == -1 else max(0, quota_limit - quota_usage)
            quota_percentage = (quota_usage / quota_limit * 100) if quota_limit > 0 else 0
            
            quota_info = {
                "plan_id": plan_id, "plan_name": plan_info.get('name'),
                "quota_usage": quota_usage, "quota_limit": quota_limit,
                "quota_remaining": quota_remaining, "quota_percentage": round(quota_percentage, 2),
                "is_trial": plan_id == 'tier_trial', "is_low_quota": quota_percentage >= 90
            }

    return {
        "today_appointments": today_appointments,
        "today_completed": today_completed,
        "today_income": today_income,
        "bugunku_toplam_hizmet_tutari": bugunku_toplam_hizmet_tutari,
        "month_income": month_income,
        "quota": quota_info
    }

@api_router.get("/stats/personnel")
async def get_personnel_stats(request: Request, current_user: UserInDB = Depends(get_current_user)):
    # Sadece personel görebilir
    if current_user.role != "staff":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    logger.info(f"👤 Personel stats endpoint çağrıldı - Staff: {current_user.username}")
    db = await get_db_from_request(request)
    turkey_tz = ZoneInfo("Europe/Istanbul")
    today = datetime.now(turkey_tz).date().isoformat()
    now = datetime.now(turkey_tz)
    base_query = {"organization_id": current_user.organization_id}
    
    # ÖNCE: Bugünkü "Bekliyor" status'ündeki personelin randevularını otomatik tamamla
    today_waiting_appointments = await db.appointments.find(
        {**base_query, "appointment_date": today, "status": "Bekliyor", "staff_member_id": current_user.username},
        {"_id": 0, "id": 1, "appointment_date": 1, "appointment_time": 1, "service_price": 1, "customer_name": 1, "service_name": 1, "service_id": 1}
    ).to_list(1000)
    
    # Servisleri çek (duration bilgisi için)
    service_ids = [appt.get('service_id') for appt in today_waiting_appointments if appt.get('service_id')]
    services_dict = {}
    if service_ids:
        services = await db.services.find(
            {"id": {"$in": list(set(service_ids))}, "organization_id": current_user.organization_id},
            {"_id": 0, "id": 1, "duration": 1}
        ).to_list(1000)
        services_dict = {s['id']: s.get('duration', 30) for s in services}
    
    ids_to_update = []
    transactions_to_create = []
    for appt in today_waiting_appointments:
        try:
            dt_str = f"{appt['appointment_date']} {appt['appointment_time']}"
            naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            appointment_dt = naive_dt.replace(tzinfo=turkey_tz)
            # Randevu bitiş saatini hesapla (başlangıç saati + hizmet süresi)
            service_duration_minutes = services_dict.get(appt.get('service_id'), 30)
            completion_threshold = appointment_dt + timedelta(minutes=service_duration_minutes)
            if now >= completion_threshold:
                ids_to_update.append(appt['id'])
                transaction = Transaction(
                    organization_id=current_user.organization_id,
                    appointment_id=appt['id'],
                    customer_name=appt['customer_name'],
                    service_name=appt['service_name'],
                    amount=appt.get('service_price', 0),
                    date=appt['appointment_date'],
                    staff_member_id=appt.get('staff_member_id')
                )
                trans_doc = transaction.model_dump()
                trans_doc['created_at'] = trans_doc['created_at'].isoformat()
                transactions_to_create.append(trans_doc)
        except (ValueError, TypeError) as e:
            logging.warning(f"Randevu {appt['id']} için tarih ayrıştırılamadı: {e}")
    
    # Otomatik tamamlanan randevuları güncelle
    if ids_to_update:
        logger.info(f"✅ Personel için {len(ids_to_update)} randevu otomatik tamamlanacak")
        await db.appointments.update_many(
            {"organization_id": current_user.organization_id, "id": {"$in": ids_to_update}},
            {"$set": {"status": "Tamamlandı", "completed_at": datetime.now(timezone.utc).isoformat()}}
        )
    # Otomatik tamamlanan randevular için transaction oluştur
    if transactions_to_create:
        await db.transactions.insert_many(transactions_to_create)
    
    # Personelin bugünkü tamamlanan randevularını bul
    today_completed_appointments = await db.appointments.find(
        {**base_query, "appointment_date": today, "status": "Tamamlandı", "staff_member_id": current_user.username},
        {"_id": 0, "service_price": 1, "id": 1}
    ).to_list(1000)
    
    # Toplam hizmet tutarı ve randevu sayısı
    total_revenue_generated = sum(apt.get('service_price', 0) or 0 for apt in today_completed_appointments)
    completed_appointments_count = len(today_completed_appointments)
    
    logger.info(f"👤 Personel {current_user.username}: {completed_appointments_count} tamamlanan randevu, Toplam: {total_revenue_generated} ₺")
    
    return {
        "total_revenue_generated": total_revenue_generated,
        "completed_appointments_count": completed_appointments_count
    }

# === PUSH NOTIFICATION ROUTES ===
@api_router.get("/push/vapid-key")
async def get_vapid_public_key():
    """VAPID public key'i döndür - subscription için gerekli"""
    return {"publicKey": VAPID_PUBLIC_KEY}

@api_router.post("/push/subscribe")
async def subscribe_push(request: Request, subscription_data: PushSubscriptionCreate, current_user: UserInDB = Depends(get_current_user)):
    """Push notification aboneliği oluştur"""
    db = await get_db_from_request(request)
    
    subscription = subscription_data.subscription
    endpoint = subscription["endpoint"]
    
    # ÖNEMLİ: Aynı endpoint'e sahip ama farklı kullanıcıya/organization'a ait subscription varsa temizle
    # Bu, cross-account bildirim karışıklığını önler
    existing_any = await db.push_subscriptions.find_one({
        "endpoint": endpoint
    })
    
    if existing_any:
        # Eğer mevcut subscription farklı bir kullanıcıya/organization'a aitse, onu sil
        if (existing_any.get("organization_id") != current_user.organization_id or 
            existing_any.get("user_id") != current_user.username):
            logger.warning(
                f"⚠️ Found existing subscription for endpoint {endpoint[:50]}... "
                f"belonging to different user/org: {existing_any.get('user_id')}/{existing_any.get('organization_id')} "
                f"(current: {current_user.username}/{current_user.organization_id}). Deleting old subscription."
            )
            await db.push_subscriptions.delete_one({"_id": existing_any["_id"]})
            existing_any = None
    
    platform = subscription.get("platform", "web")
    
    # Native platformlar (ios/android) için: aynı kullanıcı+platform için eski token'ı güncelle
    # Token her app restart'ta değişebilir, endpoint bazlı değil user+platform bazlı eşleştir
    if platform in ('ios', 'android'):
        existing_native = await db.push_subscriptions.find_one({
            "organization_id": current_user.organization_id,
            "user_id": current_user.username,
            "platform": platform
        })
        if existing_native:
            await db.push_subscriptions.update_one(
                {"_id": existing_native["_id"]},
                {"$set": {
                    "endpoint": endpoint,
                    "keys": subscription["keys"],
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"✅ Push subscription updated (token refresh) for user: {current_user.username}, platform: {platform}")
            return {"message": "Push subscription updated"}
    
    # Web için: aynı endpoint bazlı eşleştir
    existing = await db.push_subscriptions.find_one({
        "organization_id": current_user.organization_id,
        "user_id": current_user.username,
        "endpoint": endpoint
    })
    
    if existing:
        await db.push_subscriptions.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "keys": subscription["keys"], 
                "platform": platform,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.info(f"✅ Push subscription updated for user: {current_user.username}, platform: {platform}")
        return {"message": "Push subscription updated"}
    
    # Yeni abonelik oluştur
    push_doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "user_id": current_user.username,
        "user_role": current_user.role,
        "endpoint": endpoint,
        "keys": subscription["keys"],
        "platform": subscription.get("platform", "web"),  # android, ios, web
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.push_subscriptions.insert_one(push_doc)
    logger.info(f"✅ Push subscription created for user: {current_user.username}, platform: {subscription.get('platform', 'web')}")
    
    return {"message": "Push subscription created"}

@api_router.delete("/push/unsubscribe")
async def unsubscribe_push(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Push notification aboneliğini iptal et"""
    db = await get_db_from_request(request)
    
    result = await db.push_subscriptions.delete_many({
        "organization_id": current_user.organization_id,
        "user_id": current_user.username
    })
    
    return {"message": f"Deleted {result.deleted_count} subscriptions"}

@api_router.post("/push/debug")
async def push_debug(request: Request):
    """iOS push debug - her adımı logla"""
    try:
        body = await request.json()
        step = body.get("step", "unknown")
        data = body.get("data", {})
        error = body.get("error", None)
        platform = body.get("platform", "unknown")
        logger.info(f"📲 PUSH DEBUG [{platform}] Step: {step} | Data: {data} | Error: {error}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Push debug error: {e}")
        return {"ok": False}

@api_router.post("/push/test")
async def test_push_notification(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Test push notification - sadece admin için"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    try:
        await send_push_notification(
            db=db,
            organization_id=current_user.organization_id,
            title="🧪 Test Bildirimi",
            body="Push notification sistemi çalışıyor!",
            data={"type": "test", "url": "/"}
        )
        return {"message": "Test bildirimi gönderildi", "success": True}
    except Exception as e:
        logger.error(f"Test push notification error: {e}")
        return {"message": f"Hata: {str(e)}", "success": False}

# === SETTINGS ROUTES ===
@api_router.get("/settings", response_model=Settings)
async def get_settings(request: Request, current_user: UserInDB = Depends(get_current_user)):
    # Personel okuyabilir, ama sadece admin güncelleyebilir
    db = await get_db_from_request(request); query = {"organization_id": current_user.organization_id}
    settings = await db.settings.find_one(query, {"_id": 0})
    if not settings:
        default_settings = Settings(organization_id=current_user.organization_id); await db.settings.insert_one(default_settings.model_dump())
        return default_settings
    return Settings(**settings)

@api_router.put("/settings", response_model=Settings)
async def update_settings(request: Request, settings: Settings, current_user: UserInDB = Depends(get_current_user)):
    # Sadece admin güncelleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}
    
    # Mevcut ayarları al
    current_settings = await db.settings.find_one(query, {"_id": 0})
    
    update_data = settings.model_dump(exclude_unset=True)
    update_data["organization_id"] = current_user.organization_id
    
    # Eğer company_name değiştiyse, yeni slug oluştur
    if current_settings and "company_name" in update_data and current_settings.get('company_name') != settings.company_name:
        # Yeni slug oluştur
        base_slug = slugify(settings.company_name)
        unique_slug = base_slug
        
        # Slug benzersizlik kontrolü
        slug_counter = 1
        while await db.users.find_one({"slug": unique_slug, "username": {"$ne": current_user.username}}):
            unique_slug = f"{base_slug}{str(uuid.uuid4())[:4]}"
            slug_counter += 1
            if slug_counter > 10:
                unique_slug = f"{base_slug}{str(uuid.uuid4())[:8]}"
                break
        
        # User'ın slug'ını güncelle
        await db.users.update_one(
            {"username": current_user.username},
            {"$set": {"slug": unique_slug}}
        )
        
        # Settings'e yeni slug'ı ekle
        update_data["slug"] = unique_slug
        
        logging.info(f"Company name changed. New slug: {unique_slug}")
    
    await db.settings.update_one(query, {"$set": update_data}, upsert=True)
    updated_settings = await db.settings.find_one(query, {"_id": 0})
    
    # business_hours değiştiyse, kapalı günleri tüm personelin days_off'una senkronize et
    if "business_hours" in update_data and update_data.get("business_hours"):
        # Eski (update öncesi) kapalı günleri bul (fallback olarak kullanılacak)
        prev_closed_days = []
        prev_business_hours = (current_settings or {}).get('business_hours', {}) or {}
        prev_day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in prev_day_names:
            prev_day_settings = prev_business_hours.get(day, {}) or {}
            if not prev_day_settings.get('is_open', True):
                prev_closed_days.append(day)

        # Kapalı günleri bul
        closed_days = []
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in day_names:
            day_settings = settings.business_hours.get(day, {})
            if not day_settings.get('is_open', True):
                closed_days.append(day)

        # Tüm personelin days_off'unu güncelle:
        # - Kapalı günleri days_off'a ekle
        # - Daha önce otomatik senkronize edilip artık açık olan günleri days_off'tan çıkar
        # Not: Bilinçli olarak eklenmiş days_off değerlerini silmemek için, kullanıcı bazında synced_closed_days takip edilir.
        all_users = await db.users.find(
            {"organization_id": current_user.organization_id}
        ).to_list(1000)

        for user in all_users:
            current_days_off = user.get('days_off', []) or []
            # Eğer eski sistemde synced_closed_days alanı yoksa, previous business_hours'tan gelen kapalı günleri fallback olarak kullan
            previously_synced = user.get('synced_closed_days')
            if previously_synced is None:
                previously_synced = prev_closed_days
            previously_synced = previously_synced or []

            # Önceden otomatik eklenmiş ama artık kapalı olmayan günleri kaldır
            to_remove = set(previously_synced) - set(closed_days)
            updated_days_off_set = set(current_days_off) - to_remove

            # Kapalı günleri ekle
            updated_days_off_set |= set(closed_days)

            await db.users.update_one(
                {"username": user['username']},
                {"$set": {"days_off": list(updated_days_off_set), "synced_closed_days": closed_days}}
            )

        logging.info(
            f"✅ Synced business closed days to all staff days_off for org {current_user.organization_id}. closed_days={closed_days}"
        )
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="UPDATE",
        resource_type="SETTINGS",
        resource_id=current_user.organization_id,
        old_value=current_settings,
        new_value=updated_settings,
        ip_address=request.client.host if request.client else None
    )
    
    return Settings(**updated_settings)

class SettingsLocationUpdate(BaseModel):
    address: str
    coordinates: LocationCoordinates


@api_router.put("/settings/location")
async def update_settings_location(request: Request, data: SettingsLocationUpdate, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}

    current_settings = await db.settings.find_one(query, {"_id": 0})
    old_location = current_settings.get("location") if current_settings else None

    await db.settings.update_one(
        query,
        {"$set": {"location": data.model_dump()}},
        upsert=True
    )

    updated_settings = await db.settings.find_one(query, {"_id": 0})
    new_location = updated_settings.get("location") if updated_settings else None

    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="UPDATE",
        resource_type="SETTINGS_LOCATION",
        resource_id=current_user.organization_id,
        old_value=old_location,
        new_value=new_location,
        ip_address=request.client.host if request.client else None
    )

    return {"location": new_location}


@api_router.delete("/settings/location")
async def delete_settings_location(request: Request, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}

    current_settings = await db.settings.find_one(query, {"_id": 0})
    old_location = current_settings.get("location") if current_settings else None

    await db.settings.update_one(
        query,
        {"$unset": {"location": ""}},
        upsert=False
    )

    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="DELETE",
        resource_type="SETTINGS_LOCATION",
        resource_id=current_user.organization_id,
        old_value=old_location,
        new_value=None,
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Konum kaldırıldı"}

# === ONBOARDING ENDPOINTS ===
@api_router.get("/onboarding/info")
async def get_onboarding_info(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Onboarding için gerekli bilgileri döndürür (sector, default services, vb.)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Settings'den sector bilgisini al
    settings = await db.settings.find_one({"organization_id": current_user.organization_id}, {"_id": 0})
    sector = settings.get("sector") if settings else None
    
    # Mevcut hizmetleri al
    services = await db.services.find(
        {"organization_id": current_user.organization_id}
    ).to_list(100)
    
    # Services'i temizle
    services_clean = []
    for service in services:
        services_clean.append({
            "id": service.get("id"),
            "name": service.get("name"),
            "price": service.get("price", 0),
            "duration": service.get("duration", 30)
        })
    
    # Dil belirleme - request header'dan
    lang = get_request_language(request)
    
    # Sector bazlı default hizmet önerileri (frontend için) - dil bazlı
    default_services = get_sector_default_services(sector, lang) if sector else []
    
    return {
        "user": {
            "username": current_user.username,
            "full_name": current_user.full_name,
            "onboarding_completed": current_user.onboarding_completed
        },
        "sector": sector,
        "existing_services": services_clean,
        "default_services": default_services,
        "business_hours": settings.get("business_hours") if settings else {}
    }

class OnboardingServiceUpdate(BaseModel):
    services: List[dict]  # [{"id": "...", "price": 100, "duration": 30}, ...]

@api_router.post("/onboarding/update-services")
async def update_onboarding_services(request: Request, data: OnboardingServiceUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Onboarding sırasında hizmetlerin fiyat ve sürelerini güncelle"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    updated_services = []
    for service_data in data.services:
        service_id = service_data.get("id")
        price = service_data.get("price", 0)
        duration = service_data.get("duration", 30)
        
        if service_id:
            # Mevcut hizmeti güncelle
            result = await db.services.update_one(
                {"id": service_id, "organization_id": current_user.organization_id},
                {"$set": {"price": price, "duration": duration}}
            )
            
            if result.modified_count > 0:
                updated_service = await db.services.find_one(
                    {"id": service_id, "organization_id": current_user.organization_id},
                    {"_id": 0}
                )
                updated_services.append(updated_service)
    
    return {"message": f"{len(updated_services)} hizmet güncellendi", "services": updated_services}

class OnboardingNewService(BaseModel):
    name: str
    price: float
    duration: int

@api_router.post("/onboarding/add-service")
async def add_onboarding_service(request: Request, data: OnboardingNewService, current_user: UserInDB = Depends(get_current_user)):
    """Onboarding sırasında yeni hizmet ekle"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    service_id = str(uuid.uuid4())
    new_service = Service(
        id=service_id,
        name=data.name,
        price=data.price,
        duration=data.duration,
        organization_id=current_user.organization_id
    )
    
    await db.services.insert_one(new_service.model_dump())

    try:
        await db.users.update_many(
            {"organization_id": current_user.organization_id, "role": "admin"},
            {"$addToSet": {"permitted_service_ids": service_id}}
        )
    except Exception as e:
        logging.error(f"Failed to auto-assign service to admins (onboarding): {e}")
    
    return {"message": "Hizmet eklendi", "service": new_service.model_dump()}

class OnboardingHoursUpdate(BaseModel):
    business_hours: dict

@api_router.post("/onboarding/update-hours")
async def update_onboarding_hours(request: Request, data: OnboardingHoursUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Onboarding sırasında çalışma saatlerini güncelle"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    await db.settings.update_one(
        {"organization_id": current_user.organization_id},
        {"$set": {"business_hours": data.business_hours}},
        upsert=True
    )
    
    return {"message": "Çalışma saatleri güncellendi", "business_hours": data.business_hours}

class OnboardingComplete(BaseModel):
    admin_days_off: Optional[List[str]] = []
    staff_invites: Optional[List[dict]] = []  # [{"username": "...", "full_name": "...", "phone": "..."}]

@api_router.post("/onboarding/complete")
async def complete_onboarding(request: Request, data: OnboardingComplete, current_user: UserInDB = Depends(get_current_user)):
    """Onboarding sihirbazını tamamla - Admin'in tatil günlerini ayarla ve personel davet et"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Admin'in tatil günlerini güncelle
    if data.admin_days_off is not None:
        await db.users.update_one(
            {"username": current_user.username},
            {"$set": {"days_off": data.admin_days_off}}
        )
    
    # Personel davetlerini gönder (eğer varsa)
    invited_staff = []
    if data.staff_invites:
        # Organization name'i settings'den al
        org_settings = await db.settings.find_one({"organization_id": current_user.organization_id})
        organization_name = org_settings.get("company_name", "İşletme") if org_settings else "İşletme"
        
        # Admin'in tatil günlerini al (personele de aynısı uygulanacak)
        admin_days_off = data.admin_days_off if data.admin_days_off is not None else []
        
        for staff_data in data.staff_invites:
            username = staff_data.get("username")
            full_name = staff_data.get("full_name")
            
            # Kullanıcı zaten var mı kontrol et
            existing_user = await db.users.find_one({"username": username})
            if existing_user:
                logging.warning(f"⚠️ Kullanıcı zaten mevcut: {username}")
                invited_staff.append({"username": username, "full_name": full_name, "status": "already_exists"})
                continue
            
            # Davet token'ı oluştur
            invitation_token = str(uuid.uuid4())
            
            # Staff için unique slug oluştur (username'den)
            staff_slug = username.split('@')[0] + '-' + str(uuid.uuid4())[:8]
            
            # Yeni staff kullanıcısı oluştur - Admin'in tatil günleriyle
            invite_lang = getattr(current_user, 'language', None) or get_request_language(request)
            if invite_lang not in ['tr', 'en']:
                invite_lang = 'tr'
            staff_user = UserInDB(
                username=username,
                full_name=full_name,
                organization_id=current_user.organization_id,
                role="staff",
                slug=staff_slug,  # Unique slug ekle
                status="pending",
                invitation_token=invitation_token,
                days_off=admin_days_off,  # Admin'in tatil günlerini uygula
                language=invite_lang,
                hashed_password=None  # Şifre davet linkinden belirlenecek
            )
            
            await db.users.insert_one(staff_user.model_dump())
            logging.info(f"✅ Staff kullanıcısı oluşturuldu: {username}")
            
            # Davet e-postası gönder
            try:
                result = await send_personnel_invitation_email(
                    recipient_email=username,
                    recipient_name=full_name,
                    admin_name=current_user.full_name or current_user.username,
                    organization_name=organization_name,
                    invitation_token=invitation_token,
                    lang=invite_lang
                )
                
                if result:
                    invited_staff.append({"username": username, "full_name": full_name, "status": "invited"})
                else:
                    invited_staff.append({"username": username, "full_name": full_name, "status": "email_failed"})
            except Exception as e:
                logging.error(f"❌ Davet e-postası gönderilemedi ({username}): {e}")
                import traceback
                logging.error(traceback.format_exc())
                invited_staff.append({"username": username, "full_name": full_name, "status": "email_failed"})
    
    # Kullanıcının onboarding_completed flag'ini True yap
    await db.users.update_one(
        {"username": current_user.username},
        {"$set": {"onboarding_completed": True}}
    )
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="UPDATE",
        resource_type="USER",
        resource_id=current_user.username,
        old_value={"onboarding_completed": False},
        new_value={"onboarding_completed": True},
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "message": "Onboarding tamamlandı",
        "onboarding_completed": True,
        "admin_days_off": data.admin_days_off,
        "invited_staff": invited_staff
    }

@api_router.post("/settings/logo")
async def upload_logo(request: Request, file: UploadFile = File(...), current_user: UserInDB = Depends(get_current_user)):
    """Logo upload endpoint"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    # File validation
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Sadece resim dosyaları yüklenebilir")
    
    # File size check (5MB)
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya boyutu 5MB'dan büyük olamaz")
    
    # Save file to static directory
    static_dir = ROOT_DIR / "static" / "logos"
    static_dir.mkdir(parents=True, exist_ok=True)
    
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{current_user.organization_id}_{str(uuid.uuid4())[:8]}.{file_extension}"
    file_path = static_dir / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Update settings with logo URL (with /api prefix for ingress routing)
    logo_url = f"/api/static/logos/{unique_filename}"
    
    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}
    await db.settings.update_one(query, {"$set": {"logo_url": logo_url}}, upsert=True)
    
    return {"logo_url": logo_url, "message": "Logo başarıyla yüklendi"}


@api_router.post("/upload/image")
async def upload_image(request: Request, file: UploadFile = File(...), current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Sadece resim dosyaları yüklenebilir")

    file_content = await file.read()
    if len(file_content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya boyutu 8MB'dan büyük olamaz")

    static_dir = ROOT_DIR / "static" / "gallery"
    static_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{current_user.organization_id}_{str(uuid.uuid4())[:8]}.jpg"
    file_path = static_dir / unique_filename

    try:
        img = PilImage.open(io.BytesIO(file_content))
        img = img.convert("RGB")
        img.thumbnail((900, 600), PilImage.LANCZOS)
        img.save(file_path, "JPEG", quality=82, optimize=True)
    except Exception:
        with open(file_path, "wb") as f:
            f.write(file_content)

    url = f"/api/static/gallery/{unique_filename}"
    return {"url": url}

# === USERS/PERSONEL LİSTESİ (Model D) ===
@api_router.get("/users")
async def get_users(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Aynı organization'daki tüm kullanıcıları listele (şifreler hariç)"""
    db = await get_db_from_request(request)
    
    users = await db.users.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0, "hashed_password": 0}  # Şifreleri gizle
    ).to_list(1000)
    
    return users

# === STAFF/PERSONEL YÖNETİMİ (Model D) ===
class PaymentUpdate(BaseModel):
    payment_type: str
    payment_amount: Optional[float] = None
    days_off: Optional[List[str]] = None

class StaffCreate(BaseModel):
    username: str
    password: Optional[str] = None  # Artık optional, e-posta daveti kullanılıyor
    full_name: Optional[str] = None  # Opsiyonel, e-posta'dan çıkarılabilir
    payment_type: Optional[str] = None  # null olabilir (admin için)
    payment_amount: Optional[float] = None  # null olabilir (admin için)
    role: Optional[str] = "staff"  # "staff" veya "admin" - admin davet için

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
    days_off: Optional[List[str]] = None

@api_router.post("/staff/add")
async def add_staff(request: Request, staff_data: StaffCreate, current_user: UserInDB = Depends(get_current_user)):
    """Admin, yeni personel veya admin ekleyebilir (E-posta daveti ile)"""
    # Sadece admin ekleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    # Role validasyonu
    invited_role = staff_data.role or "staff"
    if invited_role not in ["staff", "admin"]:
        raise HTTPException(status_code=400, detail="Geçersiz rol. 'staff' veya 'admin' olmalı")
    
    db = await get_db_from_request(request)
    
    # payment_amount'u float'a çevir (eğer string ise)
    payment_amount = staff_data.payment_amount
    if payment_amount is not None:
        if isinstance(payment_amount, str):
            try:
                payment_amount = float(payment_amount)
            except (ValueError, TypeError):
                payment_amount = 0.0
        elif not isinstance(payment_amount, (int, float)):
            payment_amount = 0.0
    else:
        payment_amount = 0.0
    
    # Kullanıcı adı zaten var mı kontrol et
    existing = await db.users.find_one({"username": staff_data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı")
    
    # Invitation token oluştur
    invitation_token = str(uuid.uuid4())
    
    # İşletme adını al
    settings = await db.settings.find_one({"organization_id": current_user.organization_id})
    organization_name = settings.get("company_name", "İşletme") if settings else "İşletme"

    # İşletmenin kapalı günlerini yeni personele varsayılan olarak uygula
    closed_days = []
    business_hours = (settings or {}).get("business_hours") or {}
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in day_names:
        day_settings = business_hours.get(day, {}) or {}
        if not day_settings.get("is_open", True):
            closed_days.append(day)
    
    try:
        # Yeni personel oluştur (password olmadan, pending status ile)
        # Eğer full_name yoksa, email'den isim çıkar
        full_name = staff_data.full_name
        if not full_name:
            # Email'den isim çıkar (örn: john.doe@example.com -> John Doe)
            email_local = staff_data.username.split('@')[0]
            name_parts = email_local.split('.')
            if len(name_parts) > 1:
                full_name = ' '.join([part.capitalize() for part in name_parts])
            else:
                full_name = email_local.capitalize()
        
        # Admin için tüm hizmetleri al
        all_service_ids = []
        if invited_role == "admin":
            services = await db.services.find({"organization_id": current_user.organization_id}).to_list(None)
            all_service_ids = [s.get("id") for s in services if s.get("id")]
        
        new_user = UserInDB(
            username=staff_data.username,
            full_name=full_name,
            hashed_password=None,  # Şifre henüz belirlenmedi
            organization_id=current_user.organization_id,
            role=invited_role,  # staff veya admin rolü
            slug=None,  # Admin/Personellerin slug'ı yok
            permitted_service_ids=all_service_ids if invited_role == "admin" else [],  # Admin tüm hizmetlere erişebilir
            payment_type=staff_data.payment_type or "salary" if invited_role == "staff" else None,
            payment_amount=payment_amount if invited_role == "staff" else None,
            status="pending",  # Bekliyor durumu
            invitation_token=invitation_token,
            days_off=closed_days if invited_role == "staff" else [],
            language=getattr(current_user, 'language', None) or get_request_language(request)
        )
        
        user_dict = new_user.model_dump()
        # Personel için slug field'ını kaldır (MongoDB unique index hatası önlemek için)
        user_dict.pop('slug', None)
        if invited_role == "staff":
            user_dict["synced_closed_days"] = closed_days
        # Admin için onboarding tamamlanmış olarak işaretle (organization zaten kurulu)
        if invited_role == "admin":
            user_dict["onboarding_completed"] = True
        # MongoDB'ye ekle
        await db.users.insert_one(user_dict)
        
        # E-posta daveti gönder
        email_sent = await send_personnel_invitation_email(
            recipient_email=staff_data.username,
            recipient_name=full_name,
            admin_name=current_user.full_name or current_user.username,
            organization_name=organization_name,
            invitation_token=invitation_token,
            lang=getattr(current_user, 'language', None) or get_request_language(request)
        )
        
        if not email_sent:
            logging.warning(f"{'Admin' if invited_role == 'admin' else 'Personel'} eklendi ancak e-posta gönderilemedi: {staff_data.username}")
        
    except Exception as e:
        logging.error(f"{'Admin' if invited_role == 'admin' else 'Personel'} ekleme hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{'Admin' if invited_role == 'admin' else 'Personel'} eklenirken bir hata oluştu: {str(e)}")
    
    role_text = "Admin" if invited_role == "admin" else "Personel"
    return {"message": f"{role_text} başarıyla eklendi ve davet e-postası gönderildi", "username": staff_data.username, "full_name": staff_data.full_name, "role": invited_role}

@api_router.put("/users/me")
async def update_current_user(request: Request, user_update: UserUpdate, current_user: UserInDB = Depends(get_current_user), db = Depends(get_db)):
    """Mevcut kullanıcının kendi bilgilerini güncelle"""
    try:
        update_data = {}
        
        if user_update.full_name is not None:
            update_data["full_name"] = user_update.full_name
        
        if user_update.password is not None:
            if len(user_update.password) < 6:
                raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalıdır")
            update_data["hashed_password"] = get_password_hash(user_update.password)
        
        if user_update.days_off is not None:
            update_data["days_off"] = user_update.days_off
        
        if not update_data:
            raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi")
        
        await db.users.update_one(
            {"username": current_user.username, "organization_id": current_user.organization_id},
            {"$set": update_data}
        )
        
        # Audit log (hata olursa skip edilir)
        try:
            await create_audit_log(
                db=db,
                organization_id=current_user.organization_id,
                user_id=current_user.username,
                user_full_name=current_user.full_name or current_user.username,
                action="update",
                resource_type="user",
                resource_id=current_user.username,
                new_value={"updated_fields": list(update_data.keys())}
            )
        except Exception as audit_error:
            logger.warning(f"Audit log oluşturulamadı: {audit_error}")
        
        return {"message": "Profil bilgileri güncellendi"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kullanıcı güncelleme hatası: {e}")
        raise HTTPException(status_code=500, detail="Profil güncellenirken hata oluştu")

@api_router.put("/staff/{staff_id}/payment")
async def update_staff_payment(request: Request, staff_id: str, payment_data: PaymentUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Admin, personelin ödeme ayarlarını (maaş/prim) güncelleyebilir"""
    try:
        # Sadece admin güncelleyebilir
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        db = await get_db_from_request(request)
        
        # URL decode staff_id (email olabilir)
        import urllib.parse
        staff_id_decoded = urllib.parse.unquote(staff_id)
        
        # Personelin aynı organization'da olduğunu kontrol et
        staff = await db.users.find_one({"username": staff_id_decoded, "organization_id": current_user.organization_id})
        if not staff:
            raise HTTPException(status_code=404, detail="Personel bulunamadı veya erişim yok")
        
        # payment_amount'u float'a çevir (eğer string ise)
        payment_amount = payment_data.payment_amount
        if payment_amount is not None:
            if isinstance(payment_amount, str):
                try:
                    payment_amount = float(payment_amount)
                except (ValueError, TypeError):
                    payment_amount = 0.0
            elif not isinstance(payment_amount, (int, float)):
                payment_amount = 0.0
        else:
            payment_amount = 0.0
        
        # Payment bilgilerini güncelle
        update_fields = {
            "payment_type": payment_data.payment_type,
            "payment_amount": payment_amount
        }
        
        # days_off varsa ekle (PaymentUpdate modelinde artık optional)
        if hasattr(payment_data, 'days_off') and payment_data.days_off is not None:
            update_fields["days_off"] = payment_data.days_off
        
        await db.users.update_one(
            {"username": staff_id_decoded, "organization_id": current_user.organization_id},
            {"$set": update_fields}
        )
        
        logging.info(f"Personel ödeme ayarları güncellendi: {staff_id_decoded}, payment_type={payment_data.payment_type}, payment_amount={payment_amount}")
        
        return {"message": "Personel ödeme ayarları güncellendi", "staff_id": staff_id_decoded, "payment_type": payment_data.payment_type, "payment_amount": payment_amount}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Personel ödeme ayarı güncelleme hatası: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ödeme ayarları güncellenirken hata oluştu: {str(e)}")

@api_router.put("/staff/{staff_id}/days-off")
async def update_staff_days_off(request: Request, staff_id: str, days_off_data: dict, current_user: UserInDB = Depends(get_current_user)):
    """Admin, personelin tatil günlerini güncelleyebilir"""
    # Sadece admin güncelleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Personelin aynı organization'da olduğunu kontrol et
    staff = await db.users.find_one({"username": staff_id, "organization_id": current_user.organization_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Personel bulunamadı veya erişim yok")
    
    # days_off'u al
    days_off = days_off_data.get('days_off', [])
    if not isinstance(days_off, list):
        raise HTTPException(status_code=400, detail="days_off bir liste olmalıdır")
    
    # days_off'u güncelle
    await db.users.update_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"$set": {"days_off": days_off}}
    )
    
    logging.info(f"Personel tatil günleri güncellendi: {staff_id}, days_off={days_off}")
    
    return {"message": "Personel tatil günleri güncellendi", "staff_id": staff_id, "days_off": days_off}

@api_router.put("/staff/{staff_id}/toggle-permission")
async def toggle_staff_permission(request: Request, staff_id: str, permission_data: dict, current_user: UserInDB = Depends(get_current_user)):
    """Admin, personelin tüm randevuları görme yetkisini açıp kapatabilir"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    staff = await db.users.find_one({"username": staff_id, "organization_id": current_user.organization_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Personel bulunamadı veya erişim yok")
    
    can_view_all = permission_data.get('can_view_all_appointments', False)
    
    await db.users.update_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"$set": {"can_view_all_appointments": bool(can_view_all)}}
    )
    
    logging.info(f"Personel yetki güncellendi: {staff_id}, can_view_all_appointments={can_view_all}")
    
    return {"message": "Personel yetkisi güncellendi", "staff_id": staff_id, "can_view_all_appointments": can_view_all}

@api_router.delete("/staff/{staff_id}")
async def delete_staff(request: Request, staff_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Admin, personel/yönetici silebilir (kurucu admin diğer yöneticileri silebilir)"""
    # Sadece admin silebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Silinecek kullanıcıyı bul
    staff = await db.users.find_one({"username": staff_id, "organization_id": current_user.organization_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı veya erişim yok")
    
    # Kendini silemez
    if staff.get("username") == current_user.username:
        raise HTTPException(status_code=400, detail="Kendinizi silemezsiniz")
    
    # Eğer silinecek kullanıcı admin ise, kurucu admin kontrolü yap
    if staff.get("role") == "admin":
        # Kurucu admin'i bul (is_founder flag'i veya en eski admin)
        founder = await db.users.find_one({
            "organization_id": current_user.organization_id,
            "role": "admin",
            "is_founder": True
        })
        
        # Eğer is_founder flag yoksa, en eski admin'i kurucu kabul et
        if not founder:
            oldest_admin = await db.users.find_one(
                {"organization_id": current_user.organization_id, "role": "admin"},
                sort=[("_id", 1)]  # MongoDB ObjectId sıralı, ilk oluşturulan en eski
            )
            founder = oldest_admin
        
        # Silinecek kişi kurucu admin ise silinemez
        if staff.get("username") == founder.get("username"):
            raise HTTPException(status_code=400, detail="Kurucu yönetici silinemez")
        
        # Silmeye çalışan kişi kurucu admin değilse, diğer adminleri silemez
        if current_user.username != founder.get("username"):
            raise HTTPException(status_code=403, detail="Sadece kurucu yönetici diğer yöneticileri silebilir")
    
    # Kullanıcıyı sil
    await db.users.delete_one({"username": staff_id, "organization_id": current_user.organization_id})
    
    role_text = "Yönetici" if staff.get("role") == "admin" else "Personel"
    return {"message": f"{role_text} başarıyla silindi"}

@api_router.put("/staff/{staff_id}/services")
async def update_staff_services(request: Request, staff_id: str, service_ids: List[str], current_user: UserInDB = Depends(get_current_user)):
    """Admin, personelin verebileceği hizmetleri güncelleyebilir (sadece kurucu admin diğer adminleri düzenleyebilir)"""
    # Sadece admin güncelleyebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Düzenlenecek kullanıcıyı bul
    staff = await db.users.find_one({"username": staff_id, "organization_id": current_user.organization_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı veya erişim yok")
    
    # Eğer düzenlenecek kullanıcı admin ise, kurucu admin kontrolü yap
    if staff.get("role") == "admin":
        # Kurucu admin'i bul
        founder = await db.users.find_one({
            "organization_id": current_user.organization_id,
            "role": "admin",
            "is_founder": True
        })
        if not founder:
            founder = await db.users.find_one(
                {"organization_id": current_user.organization_id, "role": "admin"},
                sort=[("_id", 1)]
            )
        
        # Admin kendi hizmetlerini düzenleyebilir, diğer adminlerin hizmetlerini sadece kurucu düzenleyebilir
        if staff_id != current_user.username and current_user.username != founder.get("username"):
            raise HTTPException(status_code=403, detail="Sadece kurucu yönetici diğer yöneticilerin hizmetlerini düzenleyebilir")
    
    # Kullanıcının permitted_service_ids'ini güncelle
    await db.users.update_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"$set": {"permitted_service_ids": service_ids}}
    )
    
    return {"message": "Kullanıcı hizmetleri güncellendi", "staff_id": staff_id, "permitted_service_ids": service_ids}

# === STAFF BREAKS ROUTES ===
class BreakCreate(BaseModel):
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM

@api_router.get("/staff/breaks")
async def get_my_breaks(request: Request, date: Optional[str] = None, current_user: UserInDB = Depends(get_current_user)):
    """Personel kendi molalarını listeler"""
    db = await get_db_from_request(request)
    user = await db.users.find_one(
        {"username": current_user.username, "organization_id": current_user.organization_id},
        {"_id": 0, "breaks": 1}
    )
    breaks = user.get("breaks", []) if user else []
    
    # Tarih filtresi varsa uygula
    if date:
        breaks = [b for b in breaks if b.get("date") == date]
    
    return {"breaks": breaks}

@api_router.post("/staff/breaks")
async def add_break(request: Request, break_data: BreakCreate, current_user: UserInDB = Depends(get_current_user)):
    """Personel mola ekler"""
    db = await get_db_from_request(request)

    # Mevcut molaları al
    user = await db.users.find_one(
        {"username": current_user.username, "organization_id": current_user.organization_id},
        {"_id": 0, "breaks": 1}
    )
    breaks = user.get("breaks", []) if user else []
    
    # Yeni mola süresini hesapla
    start_parts = break_data.start_time.split(":")
    end_parts = break_data.end_time.split(":")
    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
    new_break_duration = end_minutes - start_minutes
    
    if new_break_duration <= 0:
        raise HTTPException(status_code=400, detail="Bitiş saati başlangıç saatinden sonra olmalı")
    
    if new_break_duration < 15:
        raise HTTPException(status_code=400, detail="Mola en az 15 dakika olmalı")
    
    # Randevu çakışması kontrolü
    appointments = await db.appointments.find(
        {
            "organization_id": current_user.organization_id,
            "appointment_date": break_data.date,
            "staff_member_id": current_user.username,
            "status": {"$ne": "İptal"}
        },
        {"_id": 0, "appointment_time": 1, "service_id": 1, "customer_name": 1}
    ).to_list(100)
    
    # Her randevunun bitiş saatini hesapla ve çakışma kontrol et
    conflicting_appointments = []
    for appt in appointments:
        # Randevu süresini al
        appt_service = await db.services.find_one({"id": appt.get("service_id")}, {"_id": 0, "duration": 1})
        appt_duration = appt_service.get("duration", 30) if appt_service else 30
        
        appt_start_time = appt["appointment_time"]
        appt_start_parts = appt_start_time.split(":")
        appt_start_minutes = int(appt_start_parts[0]) * 60 + int(appt_start_parts[1])
        appt_end_minutes = appt_start_minutes + appt_duration
        
        # Çakışma kontrolü: Mola ile randevu saatleri çakışıyor mu?
        if not (end_minutes <= appt_start_minutes or start_minutes >= appt_end_minutes):
            appt_end_hour = appt_end_minutes // 60
            appt_end_minute = appt_end_minutes % 60
            appt_end_time = f"{str(appt_end_hour).zfill(2)}:{str(appt_end_minute).zfill(2)}"
            conflicting_appointments.append({
                "customer_name": appt.get("customer_name", ""),
                "time": f"{appt_start_time} - {appt_end_time}"
            })
    
    if conflicting_appointments:
        conflict_details = ", ".join([f"{a['customer_name']} ({a['time']})" for a in conflicting_appointments])
        raise HTTPException(
            status_code=400, 
            detail=f"Bu saatte randevunuz var: {conflict_details}. Lütfen farklı bir saat seçin."
        )
    
    # Yeni mola oluştur
    new_break = {
        "id": str(uuid.uuid4()),
        "date": break_data.date,
        "start_time": break_data.start_time,
        "end_time": break_data.end_time,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Veritabanına ekle
    await db.users.update_one(
        {"username": current_user.username, "organization_id": current_user.organization_id},
        {"$push": {"breaks": new_break}}
    )
    
    return {"message": "Mola eklendi", "break": new_break}

@api_router.delete("/staff/breaks/{break_id}")
async def delete_break(request: Request, break_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Personel molasını siler"""
    db = await get_db_from_request(request)
    
    result = await db.users.update_one(
        {"username": current_user.username, "organization_id": current_user.organization_id},
        {"$pull": {"breaks": {"id": break_id}}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Mola bulunamadı")
    
    return {"message": "Mola silindi"}


# === ADMIN TIME BLOCK ROUTES ===
@api_router.get("/admin/staff/{staff_id}/breaks")
async def admin_get_staff_breaks(
    request: Request,
    staff_id: str,
    date: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin, personelin zaman bloklarını listeler"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    db = await get_db_from_request(request)
    user = await db.users.find_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"_id": 0, "breaks": 1}
    )
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    breaks = user.get("breaks", [])
    if date:
        breaks = [b for b in breaks if b.get("date") == date]
    return {"breaks": breaks}


@api_router.post("/admin/staff/{staff_id}/breaks")
async def admin_add_staff_break(
    request: Request,
    staff_id: str,
    break_data: BreakCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin, personel için zaman kapatma (blok) ekler"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    db = await get_db_from_request(request)

    staff_user = await db.users.find_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"_id": 0, "username": 1}
    )
    if not staff_user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    # Süre hesapla
    start_parts = break_data.start_time.split(":")
    end_parts = break_data.end_time.split(":")
    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
    new_break_duration = end_minutes - start_minutes

    if new_break_duration <= 0:
        raise HTTPException(status_code=400, detail="Bitiş saati başlangıç saatinden sonra olmalı")
    if new_break_duration < 15:
        raise HTTPException(status_code=400, detail="Mola en az 15 dakika olmalı")

    # Randevu çakışması kontrolü
    appointments = await db.appointments.find(
        {
            "organization_id": current_user.organization_id,
            "appointment_date": break_data.date,
            "staff_member_id": staff_id,
            "status": {"$ne": "İptal"}
        },
        {"_id": 0, "appointment_time": 1, "service_id": 1, "customer_name": 1}
    ).to_list(100)

    conflicting_appointments = []
    for appt in appointments:
        appt_service = await db.services.find_one({"id": appt.get("service_id")}, {"_id": 0, "duration": 1})
        appt_duration = appt_service.get("duration", 30) if appt_service else 30

        appt_start_time = appt["appointment_time"]
        appt_start_parts = appt_start_time.split(":")
        appt_start_minutes = int(appt_start_parts[0]) * 60 + int(appt_start_parts[1])
        appt_end_minutes = appt_start_minutes + appt_duration

        if not (end_minutes <= appt_start_minutes or start_minutes >= appt_end_minutes):
            appt_end_hour = appt_end_minutes // 60
            appt_end_minute = appt_end_minutes % 60
            appt_end_time = f"{str(appt_end_hour).zfill(2)}:{str(appt_end_minute).zfill(2)}"
            conflicting_appointments.append({
                "customer_name": appt.get("customer_name", ""),
                "time": f"{appt_start_time} - {appt_end_time}"
            })

    if conflicting_appointments:
        conflict_details = ", ".join([f"{a['customer_name']} ({a['time']})" for a in conflicting_appointments])
        raise HTTPException(
            status_code=400,
            detail=f"Bu saatte randevunuz var: {conflict_details}. Lütfen farklı bir saat seçin."
        )

    new_break = {
        "id": str(uuid.uuid4()),
        "date": break_data.date,
        "start_time": break_data.start_time,
        "end_time": break_data.end_time,
        "created_at": datetime.utcnow().isoformat()
    }

    await db.users.update_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"$push": {"breaks": new_break}}
    )

    return {"message": "Mola eklendi", "break": new_break}


@api_router.delete("/admin/staff/{staff_id}/breaks/{break_id}")
async def admin_delete_staff_break(
    request: Request,
    staff_id: str,
    break_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin, personelin zaman bloğunu siler"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    db = await get_db_from_request(request)
    result = await db.users.update_one(
        {"username": staff_id, "organization_id": current_user.organization_id},
        {"$pull": {"breaks": {"id": break_id}}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Mola bulunamadı")
    return {"message": "Mola silindi"}

# === CUSTOMERS ROUTES ===
@api_router.get("/customers")
@cache_result(prefix="customers_list", ttl=120)
async def get_customers(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Tüm unique müşterileri listele (organization bazlı)"""
    db = await get_db_from_request(request)
    
    # Tüm randevuları çek
    appointments = await db.appointments.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    ).to_list(10000)
    
    # Unique müşterileri grupla
    customer_map = {}
    for apt in appointments:
        phone = apt.get('phone')
        if phone and phone not in customer_map:
            customer_map[phone] = {
                "name": apt.get('customer_name', ''),
                "phone": phone,
                "total_appointments": 0,
                "completed_appointments": 0
            }
        
        if phone:
            customer_map[phone]['total_appointments'] += 1
            if apt.get('status') == 'Tamamlandı':
                customer_map[phone]['completed_appointments'] += 1
    
    # Veritabanından kayıtlı müşterileri de ekle (randevusu olmayan müşteriler)
    try:
        db_customers = await db.customers.find(
            {"organization_id": current_user.organization_id},
            {"_id": 0, "name": 1, "phone": 1}
        ).to_list(50000)
        
        for db_customer in db_customers:
            phone = db_customer.get('phone')
            if phone and phone not in customer_map:
                customer_map[phone] = {
                    "name": db_customer.get('name', ''),
                    "phone": phone,
                    "total_appointments": 0,
                    "completed_appointments": 0,
                    "is_pending": True  # Randevusu olmayan müşteri
                }
    except Exception as e:
        logging.warning(f"Error loading customers from database: {e}")
    
    # Liste olarak döndür
    customers = list(customer_map.values())
    customers.sort(key=lambda x: (x.get('name') or '').lower())
    
    logging.info(f"📋 GET /customers: {len(customers)} müşteri döndürülüyor (org: {current_user.organization_id[:8]})")
    return customers

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Müşteri adı")
    phone: str = Field(..., min_length=10, description="Telefon numarası")

@api_router.post("/customers")
async def create_customer(request: Request, customer_data: CustomerCreate, current_user: UserInDB = Depends(get_current_user)):
    """Yeni müşteri ekle (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    name = customer_data.name.strip()
    phone = customer_data.phone.strip()
    
    if not name or not phone:
        raise HTTPException(status_code=400, detail="Müşteri adı ve telefon numarası gereklidir")
    
    # Telefon numarasını normalize et
    clean_phone = re.sub(r'\D', '', phone)
    if len(clean_phone) < 10:
        raise HTTPException(status_code=400, detail="Geçerli bir telefon numarası girin")
    
    # Telefon varyasyonlarını oluştur (farklı formatlarla kaydedilmiş olabilir)
    phone_variants = [clean_phone]
    if clean_phone.startswith('90') and len(clean_phone) == 12:
        phone_variants.append(clean_phone[2:])           # 5362231743
        phone_variants.append('0' + clean_phone[2:])     # 05362231743
    elif len(clean_phone) == 10 and not clean_phone.startswith('0'):
        phone_variants.append('90' + clean_phone)        # 905362231743
        phone_variants.append('0' + clean_phone)         # 05362231743
    
    # Aynı telefon numarasına sahip müşteri var mı kontrol et (randevulardan ve customers collection'ından)
    existing_appointment = await db.appointments.find_one(
        {"organization_id": current_user.organization_id, "phone": {"$in": phone_variants}},
        {"_id": 0, "id": 1}
    )
    
    if existing_appointment:
        raise HTTPException(status_code=400, detail="Bu telefon numarasına sahip bir müşteri zaten var")
    
    # customers collection'ında da kontrol et
    existing_customer = await db.customers.find_one(
        {"organization_id": current_user.organization_id, "phone": {"$in": phone_variants}},
        {"_id": 0, "id": 1}
    )
    
    if existing_customer:
        raise HTTPException(status_code=400, detail="Bu telefon numarasına sahip bir müşteri zaten var")
    
    # Müşteriyi customers collection'ına kaydet (eğer collection yoksa otomatik oluşturulur)
    customer_doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "name": name,
        "phone": clean_phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": ""
    }
    
    # customers collection'ına kaydet
    await db.customers.insert_one(customer_doc)
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="CREATE",
        resource_type="CUSTOMER",
        resource_id=customer_doc["id"],
        new_value=customer_doc,
        ip_address=request.client.host if request.client else None
    )
    
    logging.info(f"New customer created: {name} ({phone}) for org {current_user.organization_id}")

    try:
        await invalidate_cache(request, "customers_list", current_user)
    except Exception as e:
        logging.warning(f"Customer cache invalidation failed: {e}")
    
    try:
        await emit_to_organization(current_user.organization_id, 'customer_added', {'customer': customer_doc})
    except Exception as e:
        logging.warning(f"Failed to emit customer_added event: {e}")
    
    return {
        "id": customer_doc["id"],
        "name": name,
        "phone": phone,
        "message": "Müşteri başarıyla eklendi"
    }

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

@api_router.put("/customers/{phone}")
async def update_customer(request: Request, phone: str, update_data: CustomerUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Müşteri bilgilerini güncelle (ad, telefon). Admin ve personel kullanabilir."""
    db = await get_db_from_request(request)
    customer = await db.customers.find_one({"phone": phone, "organization_id": current_user.organization_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")
    
    updates = {}
    if update_data.name and update_data.name.strip():
        updates["name"] = update_data.name.strip()
    
    new_phone = None
    if update_data.phone and update_data.phone.strip():
        new_phone = re.sub(r'\D', '', update_data.phone.strip())
        if len(new_phone) < 10:
            raise HTTPException(status_code=400, detail="Geçerli bir telefon numarası girin")
        if new_phone != phone:
            existing = await db.customers.find_one({"phone": new_phone, "organization_id": current_user.organization_id})
            if existing:
                raise HTTPException(status_code=400, detail="Bu telefon numarasına sahip başka bir müşteri zaten var")
            updates["phone"] = new_phone
    
    if not updates:
        raise HTTPException(status_code=400, detail="Güncellenecek bir bilgi yok")
    
    await db.customers.update_one({"phone": phone, "organization_id": current_user.organization_id}, {"$set": updates})
    
    # Telefon değiştiyse randevuları da güncelle
    if new_phone and new_phone != phone:
        await db.appointments.update_many(
            {"phone": phone, "organization_id": current_user.organization_id},
            {"$set": {"phone": new_phone}}
        )
    # İsim değiştiyse randevulardaki müşteri adını da güncelle
    if "name" in updates:
        phone_to_match = new_phone if new_phone and new_phone != phone else phone
        await db.appointments.update_many(
            {"phone": phone_to_match, "organization_id": current_user.organization_id},
            {"$set": {"customer_name": updates["name"]}}
        )
    
    try:
        await invalidate_cache(request, "customers_list", current_user)
        await invalidate_cache(request, "dashboard_stats", current_user)
    except Exception:
        pass
    
    try:
        await emit_to_organization(current_user.organization_id, 'customer_updated', {'phone': phone})
    except Exception:
        pass
    
    logging.info(f"Customer updated: {phone} -> {updates} for org {current_user.organization_id}")
    return {"message": "Müşteri bilgileri güncellendi", "updates": updates}

@api_router.delete("/customers/{phone}")
async def delete_customer(request: Request, phone: str, current_user: UserInDB = Depends(get_current_user)):
    """Müşteriyi ve TÜM randevularını sil"""
    # Sadece admin silebilir
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Önce customers collection'ından müşteriyi bul
    customer_query = {"phone": phone, "organization_id": current_user.organization_id}
    customer = await db.customers.find_one(customer_query, {"_id": 0})
    
    # Randevuları sil (varsa)
    appointment_query = {"phone": phone, "organization_id": current_user.organization_id}
    appointments_to_delete = await db.appointments.find(appointment_query, {"_id": 0}).to_list(1000)
    appointment_result = await db.appointments.delete_many(appointment_query)
    
    # Transaction'ları da sil (eğer varsa)
    transaction_result = await db.transactions.delete_many(appointment_query)
    
    # Customers collection'ından müşteriyi sil
    customer_result = await db.customers.delete_many(customer_query)
    
    # Eğer ne müşteri ne de randevu bulunamadıysa hata ver
    if customer_result.deleted_count == 0 and appointment_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bu telefon numarasına ait müşteri veya randevu bulunamadı")

    try:
        await invalidate_cache(request, "customers_list", current_user)
        await invalidate_cache(request, "dashboard_stats", current_user)
        
        if hasattr(request.app.state, 'redis') and request.app.state.redis:
            redis_client = request.app.state.redis
            cache_key = f"plann:org_{current_user.organization_id}:customers_list"
            await redis_client.delete(cache_key)
            logger.info(f"Cache deleted: {cache_key}")
            
    except Exception as e:
        logger.warning(f"Customer cache invalidation failed: {e}")
    
    # Audit log
    await create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.username,
        user_full_name=current_user.full_name or current_user.username,
        action="DELETE",
        resource_type="CUSTOMER",
        resource_id=phone,
        old_value={
            "phone": phone, 
            "customer_deleted": customer_result.deleted_count > 0,
            "appointments": appointments_to_delete, 
            "appointments_count": appointment_result.deleted_count,
            "transactions_count": transaction_result.deleted_count
        },
        ip_address=request.client.host if request.client else None
    )
    
    # Emit WebSocket event for real-time update
    logger.info(f"About to emit customer_deleted for org: {current_user.organization_id}")
    try:
        await emit_to_organization(
            current_user.organization_id,
            'customer_deleted',
            {
                'phone': phone, 
                'deleted_appointments': appointment_result.deleted_count,
                'deleted_customer': customer_result.deleted_count > 0
            }
        )
        logger.info(f"Successfully emitted customer_deleted for org: {current_user.organization_id}")
    except Exception as emit_error:
        logger.error(f"Failed to emit customer_deleted: {emit_error}", exc_info=True)

    try:
        if appointment_result.deleted_count > 0:
            await emit_to_organization(
                current_user.organization_id,
                'appointment_deleted',
                {
                    'deleted_count': appointment_result.deleted_count,
                    'phone': phone,
                }
            )
    except Exception as emit_error:
        logger.error(f"Failed to emit appointment_deleted after customer delete: {emit_error}", exc_info=True)
    
    # Mesaj oluştur
    messages = []
    if customer_result.deleted_count > 0:
        messages.append("Müşteri")
    if appointment_result.deleted_count > 0:
        messages.append(f"{appointment_result.deleted_count} randevu")
    if transaction_result.deleted_count > 0:
        messages.append(f"{transaction_result.deleted_count} işlem")
    
    message = " ve ".join(messages) + " silindi"
    
    return {
        "message": message,
        "deleted_customer": customer_result.deleted_count > 0,
        "deleted_appointments": appointment_result.deleted_count,
        "deleted_transactions": transaction_result.deleted_count
    }

# === AUDIT LOGS ROUTES ===
@api_router.get("/audit-logs", response_model=List[AuditLog])
async def get_audit_logs(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    """Denetim günlüklerini getir - Sadece admin"""
    if not AUDIT_LOGS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    query = {"organization_id": current_user.organization_id}
    
    # Filters
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    if resource_type:
        query["resource_type"] = resource_type
    if start_date or end_date:
        query["timestamp"] = {}
        if start_date:
            query["timestamp"]["$gte"] = start_date
        if end_date:
            query["timestamp"]["$lte"] = end_date
    
    # Get logs, sorted by timestamp descending
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)
    
    # Convert timestamp strings back to datetime
    for log in logs:
        if isinstance(log.get('timestamp'), str):
            log['timestamp'] = datetime.fromisoformat(log['timestamp'])
    
    return logs

@api_router.get("/export/appointments")
async def export_appointments(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Randevuları CSV formatında export et"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    appointments = await db.appointments.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    ).sort("appointment_date", -1).to_list(10000)
    
    # CSV formatında hazırla
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Randevu ID", "Müşteri Adı", "Telefon", "Tarih", "Saat",
        "Hizmet", "Personel", "Durum", "Fiyat", "Notlar", "Oluşturma Tarihi"
    ])
    
    # Data
    for apt in appointments:
        writer.writerow([
            apt.get('id', ''),
            apt.get('customer_name', ''),
            apt.get('phone', ''),
            apt.get('appointment_date', ''),
            apt.get('appointment_time', ''),
            apt.get('service_name', ''),
            apt.get('staff_member_name', 'Atanmadı'),
            apt.get('status', ''),
            apt.get('price', 0),
            apt.get('notes', ''),
            str(apt.get('created_at', ''))
        ])
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=randevular.csv"}
    )

@api_router.get("/export/customers")
async def export_customers(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Müşterileri CSV formatında export et"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Tüm randevuları çek
    appointments = await db.appointments.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    ).to_list(10000)
    
    # Unique müşterileri grupla
    customer_map = {}
    for apt in appointments:
        phone = apt.get('phone')
        if phone and phone not in customer_map:
            customer_map[phone] = {
                "name": apt.get('customer_name', ''),
                "phone": phone,
                "total_appointments": 0,
                "completed_appointments": 0,
                "last_appointment_date": apt.get('appointment_date', '')
            }
        
        if phone:
            customer_map[phone]['total_appointments'] += 1
            if apt.get('status') == 'Tamamlandı':
                customer_map[phone]['completed_appointments'] += 1
            # En son randevu tarihini güncelle
            if apt.get('appointment_date', '') > customer_map[phone]['last_appointment_date']:
                customer_map[phone]['last_appointment_date'] = apt.get('appointment_date', '')
    
    # CSV formatında hazırla
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Müşteri Adı", "Telefon", "Toplam Randevu",
        "Tamamlanan Randevu", "Son Randevu Tarihi"
    ])
    
    # Data
    customers = sorted(customer_map.values(), key=lambda x: x['total_appointments'], reverse=True)
    for customer in customers:
        writer.writerow([
            customer['name'],
            customer['phone'],
            customer['total_appointments'],
            customer['completed_appointments'],
            customer['last_appointment_date']
        ])
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=musteriler.csv"}
    )

@api_router.get("/customers/{phone}/history")
async def get_customer_history(request: Request, phone: str, current_user: UserInDB = Depends(get_current_user)):
    db = await get_db_from_request(request); query = {"phone": phone, "organization_id": current_user.organization_id}
    appointments = await db.appointments.find(query, {"_id": 0}).sort("appointment_date", -1).to_list(1000)
    for appointment in appointments:
        if isinstance(appointment['created_at'], str): appointment['created_at'] = datetime.fromisoformat(appointment['created_at'].replace('Z', '+00:00'))
    total_completed = len([a for a in appointments if a['status'] == 'Tamamlandı'])
    
    # Müşteri notlarını getir
    customer_note = await db.customer_notes.find_one(
        {"phone": phone, "organization_id": current_user.organization_id},
        {"_id": 0, "notes": 1}
    )
    notes = customer_note.get("notes", "") if customer_note else ""
    
    return {"phone": phone, "total_appointments": len(appointments), "completed_appointments": total_completed, "appointments": appointments, "notes": notes}

@api_router.put("/customers/{phone}/notes")
async def update_customer_notes(request: Request, phone: str, notes_data: dict, current_user: UserInDB = Depends(get_current_user)):
    """Müşteri notlarını güncelle (Admin ve Personel - sadece kendi müşterileri)"""
    db = await get_db_from_request(request)
    notes = notes_data.get("notes", "")
    
    # Personel için: Bu müşterinin kendisiyle randevusu var mı kontrol et
    if current_user.role == "staff":
        staff_appointments = await db.appointments.find_one(
            {"phone": phone, "organization_id": current_user.organization_id, "staff_member_id": current_user.username},
            {"_id": 1}
        )
        if not staff_appointments:
            raise HTTPException(status_code=403, detail="Bu müşteriye not ekleme yetkiniz yok")
    
    # Müşteri notlarını güncelle veya oluştur
    await db.customer_notes.update_one(
        {"phone": phone, "organization_id": current_user.organization_id},
        {"$set": {"notes": notes, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

    try:
        await invalidate_cache(request, "customers_list", current_user)
    except Exception as e:
        logging.warning(f"Customer cache invalidation failed: {e}")
    
    return {"message": "Notlar güncellendi", "notes": notes}

# === FINANCE & EXPENSES ROUTES ===
class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    date: str

class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    date: Optional[str] = None

@api_router.get("/finance/summary")
async def get_finance_summary(request: Request, period: str = "this_month", current_user: UserInDB = Depends(get_current_user)):
    """Finans özeti: Gelir, Gider, Net Kâr (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Tarih aralığını hesapla
    from datetime import datetime, timedelta
    # UTC timezone kullan (tutarlılık için)
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    if period == "today":
        start_date = today_str
        end_date = today_str
    elif period == "this_month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = today_str
    elif period == "last_month":
        first_day_this_month = now.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start_date = last_day_last_month.replace(day=1).strftime("%Y-%m-%d")
        end_date = last_day_last_month.strftime("%Y-%m-%d")
    elif period == "this_year":
        start_date = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        end_date = today_str
    else:
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = today_str
    
    logging.info(f"Finance summary - Date range calculation: period={period}, start_date={start_date}, end_date={end_date}, today={today_str}, now={now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Toplam Gelir: Tamamlanan randevuların toplam hizmet bedeli
    completed_appointments = await db.appointments.find(
        {
            "organization_id": current_user.organization_id,
            "status": "Tamamlandı",
            "appointment_date": {"$gte": start_date, "$lte": end_date}
        },
        {"_id": 0, "service_price": 1, "staff_member_id": 1}
    ).to_list(10000)
    
    total_revenue = sum(apt.get("service_price", 0) or 0 for apt in completed_appointments)
    
    # Personel bazlı kazançları hesapla
    staff_earnings_dict = {}
    for apt in completed_appointments:
        staff_id = apt.get("staff_member_id")
        if staff_id:
            price = apt.get("service_price", 0) or 0
            if staff_id not in staff_earnings_dict:
                staff_earnings_dict[staff_id] = 0
            staff_earnings_dict[staff_id] += price
    
    # Personel isimlerini al
    staff_users = await db.users.find(
        {"organization_id": current_user.organization_id, "username": {"$in": list(staff_earnings_dict.keys())}},
        {"_id": 0, "username": 1, "full_name": 1}
    ).to_list(100)
    staff_name_map = {u["username"]: u.get("full_name", u["username"]) for u in staff_users}
    
    staff_earnings = [
        {"username": staff_id, "full_name": staff_name_map.get(staff_id, staff_id), "total": amount}
        for staff_id, amount in staff_earnings_dict.items()
    ]
    staff_earnings.sort(key=lambda x: x["total"], reverse=True)
    
    # Toplam Gider: Expenses tablosundaki kayıtların toplamı
    # MongoDB sorgusu ile doğrudan filtreleme yapıyoruz (this_month için ay filtresi dahil)
    expense_query = {"organization_id": current_user.organization_id}
    
    # Tarih filtresini MongoDB sorgusuna ekle
    date_conditions = [{"date": {"$exists": True}}, {"date": {"$ne": ""}}]  # Sadece tarihi olan expense'leri al
    
    if period == "this_month":
        # Bu ay için: ayın ilk gününden son gününe kadar
        first_day_of_month = now.replace(day=1).strftime("%Y-%m-%d")
        # Ayın son gününü hesapla
        if now.month == 12:
            last_day_of_month = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_month = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
        last_day_str = last_day_of_month.strftime("%Y-%m-%d")
        date_conditions.append({"date": {"$gte": first_day_of_month, "$lte": last_day_str}})
        logging.info(f"Finance summary - this_month filter: {first_day_of_month} to {last_day_str}")
    elif period == "today":
        date_conditions.append({"date": {"$gte": start_date, "$lte": end_date}})
    elif period == "last_month":
        date_conditions.append({"date": {"$gte": start_date, "$lte": end_date}})
    elif period == "this_year":
        first_day_of_year = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        date_conditions.append({"date": {"$gte": first_day_of_year, "$lte": today_str}})
    else:
        # Varsayılan olarak bu ay
        first_day_of_month = now.replace(day=1).strftime("%Y-%m-%d")
        if now.month == 12:
            last_day_of_month = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_month = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
        last_day_str = last_day_of_month.strftime("%Y-%m-%d")
        date_conditions.append({"date": {"$gte": first_day_of_month, "$lte": last_day_str}})
    
    if len(date_conditions) > 0:
        expense_query["$and"] = date_conditions
    
    expenses = await db.expenses.find(
        expense_query,
        {"_id": 0, "amount": 1, "date": 1, "title": 1}
    ).to_list(10000)
    
    logging.info(f"Finance summary - period: {period}, start_date: {start_date}, end_date: {end_date}")
    logging.info(f"Finance summary - FILTERED expenses count: {len(expenses)}")
    for exp in expenses[:5]:  # İlk 5 filtrelenmiş expense'i logla
        logging.info(f"  FILTERED Expense: {exp.get('title')}, date: {exp.get('date')}, amount: {exp.get('amount')}")
    
    total_expenses = sum(float(exp.get("amount", 0) or 0) for exp in expenses)
    logging.info(f"Finance summary - total_expenses: {total_expenses}")
    
    # Net Kâr
    net_profit = total_revenue - total_expenses
    
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "staff_earnings": staff_earnings
    }

@api_router.get("/expenses")
async def get_expenses(request: Request, current_user: UserInDB = Depends(get_current_user)):
    """Giderleri listele (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    expenses = await db.expenses.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    ).sort("date", -1).to_list(1000)
    
    return expenses

@api_router.post("/expenses")
async def create_expense(request: Request, expense: ExpenseCreate, current_user: UserInDB = Depends(get_current_user)):
    """Yeni gider ekle (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    expense_data = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "title": expense.title,
        "amount": expense.amount,
        "category": expense.category,
        "date": expense.date,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        await db.expenses.insert_one(expense_data)
        logging.info(f"Gider başarıyla kaydedildi: {expense_data.get('title')}, tutar: {expense_data.get('amount')}")
    except Exception as insert_error:
        logging.error(f"Gider kaydetme hatası: {type(insert_error).__name__}: {str(insert_error)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gider kaydedilirken bir hata oluştu: {str(insert_error)}")
    
    # Response için expense_data'yı temizle (MongoDB ObjectId gibi serialize edilemeyen alanları kaldır)
    response_expense = {
        "id": expense_data["id"],
        "organization_id": expense_data["organization_id"],
        "title": expense_data["title"],
        "amount": float(expense_data["amount"]),
        "category": expense_data["category"],
        "date": expense_data["date"],
        "created_at": expense_data["created_at"]
    }
    
    return {"message": "Gider eklendi", "expense": response_expense}

@api_router.put("/expenses/{expense_id}")
async def update_expense(request: Request, expense_id: str, expense_update: ExpenseUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Gider güncelle (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    update_data = {}
    if expense_update.title is not None:
        update_data["title"] = expense_update.title
    if expense_update.amount is not None:
        update_data["amount"] = expense_update.amount
    if expense_update.category is not None:
        update_data["category"] = expense_update.category
    if expense_update.date is not None:
        update_data["date"] = expense_update.date
    
    result = await db.expenses.update_one(
        {"id": expense_id, "organization_id": current_user.organization_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")
    
    return {"message": "Gider güncellendi"}

@api_router.delete("/expenses/{expense_id}")
async def delete_expense(request: Request, expense_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Gider sil (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    result = await db.expenses.delete_one(
        {"id": expense_id, "organization_id": current_user.organization_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")
    
    return {"message": "Gider silindi"}

@api_router.get("/finance/payroll")
async def get_payroll(request: Request, period: str = "this_month", current_user: UserInDB = Depends(get_current_user)):
    """Personel hakedişlerini hesapla (Sadece admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    
    db = await get_db_from_request(request)
    
    # Tarih aralığını hesapla
    from datetime import datetime, timedelta
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    if period == "this_month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = today_str
    elif period == "last_month":
        first_day_this_month = now.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start_date = last_day_last_month.replace(day=1).strftime("%Y-%m-%d")
        end_date = last_day_last_month.strftime("%Y-%m-%d")
    else:
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = today_str
    
    logging.info(f"Payroll - period: {period}, start_date: {start_date}, end_date: {end_date}, today: {today_str}")
    
    # Tüm personelleri getir
    staff_members = await db.users.find(
        {"organization_id": current_user.organization_id, "role": "staff"},
        {"_id": 0, "username": 1, "full_name": 1, "payment_type": 1, "payment_amount": 1}
    ).to_list(1000)
    
    payroll_list = []
    
    for staff in staff_members:
        username = staff.get("username")
        full_name = staff.get("full_name") or username
        payment_type = staff.get("payment_type", "salary")
        payment_amount = staff.get("payment_amount", 0.0) or 0.0
        
        # Hakediş hesapla
        if payment_type == "salary":
            # Sabit maaş
            earned = float(payment_amount) if payment_amount else 0.0
        else:
            # Komisyon: Personelin o ay tamamladığı toplam ciro * (payment_amount / 100)
            completed_appointments = await db.appointments.find(
                {
                    "organization_id": current_user.organization_id,
                    "staff_member_id": username,
                    "status": "Tamamlandı",
                    "appointment_date": {"$gte": start_date, "$lte": end_date}
                },
                {"_id": 0, "service_price": 1}
            ).to_list(10000)
            
            total_revenue = sum(apt.get("service_price", 0) or 0 for apt in completed_appointments)
            commission_rate = float(payment_amount) if payment_amount else 0.0
            earned = total_revenue * (commission_rate / 100.0)
            
            # Debug logging
            logging.info(f"Payroll calculation for {username}: total_revenue={total_revenue}, commission_rate={commission_rate}%, earned={earned}")
        
        # Ödenen tutarı hesapla (Personel Ödemesi kategorisindeki giderler)
        # staff_username field'ı varsa direkt eşleştir, yoksa title'dan kontrol et
        # Tüm personel ödemelerini al (tarih filtresi olmadan) - debug için
        all_staff_payments = await db.expenses.find(
            {
                "organization_id": current_user.organization_id,
                "category": "Personel Ödemesi",
                "$or": [
                    {"staff_username": username},  # Yeni format: staff_username field'ı
                    {"title": {"$regex": username, "$options": "i"}},  # Eski format: title'da username
                    {"title": {"$regex": full_name, "$options": "i"}}  # Eski format: title'da isim
                ]
            },
            {"_id": 0, "amount": 1, "date": 1, "title": 1, "staff_username": 1}
        ).to_list(1000)
        
        logging.info(f"Payroll - {username}: Found {len(all_staff_payments)} total staff payments")
        for payment in all_staff_payments[:5]:
            logging.info(f"  Payment: {payment.get('title')}, date: {payment.get('date')}, amount: {payment.get('amount')}, staff_username: {payment.get('staff_username')}")
        
        # Tarih aralığına göre filtrele
        if period == "this_month":
            # Bu ay içindeki tüm ödemeleri dahil et (ay kontrolü)
            staff_payments = []
            for payment in all_staff_payments:
                payment_date = payment.get('date', '')
                if payment_date:
                    try:
                        payment_date_obj = datetime.strptime(payment_date, "%Y-%m-%d")
                        if payment_date_obj.year == now.year and payment_date_obj.month == now.month:
                            staff_payments.append(payment)
                            logging.info(f"  INCLUDED Payment: {payment.get('title')}, date: {payment_date}, amount: {payment.get('amount')}")
                        else:
                            logging.info(f"  EXCLUDED Payment (wrong month): {payment.get('title')}, date: {payment_date}")
                    except (ValueError, TypeError) as e:
                        logging.warning(f"  EXCLUDED Payment (invalid date): {payment.get('title')}, date: {payment_date}, error: {str(e)}")
        else:
            # Diğer period'lar için normal tarih aralığı kontrolü
            staff_payments = [p for p in all_staff_payments if p.get('date') and start_date <= p.get('date') <= end_date]
        
        logging.info(f"Payroll - {username}: Filtered {len(staff_payments)} payments for period {period}")
        
        paid = sum(float(payment.get("amount", 0) or 0) for payment in staff_payments)
        logging.info(f"Payroll - {username}: paid = {paid}")
        balance = earned - paid
        
        payroll_list.append({
            "username": username,
            "full_name": full_name,
            "payment_type": payment_type,
            "payment_amount": payment_amount,
            "earned": earned,
            "paid": paid,
            "balance": balance
        })
    
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "payroll": payroll_list
    }

class PayrollPaymentRequest(BaseModel):
    staff_username: str
    amount: float
    date: Optional[str] = None

@api_router.post("/finance/payroll/payment")
async def make_payroll_payment(request: Request, payment_data: PayrollPaymentRequest, current_user: UserInDB = Depends(get_current_user)):
    """Personel ödemesi yap (Gider olarak kaydet) (Sadece admin)"""
    logging.info("=== PAYROLL PAYMENT ENDPOINT ÇAĞRILDI ===")
    try:
        logging.info(f"Request body: staff_username={payment_data.staff_username}, amount={payment_data.amount}, date={payment_data.date}")
        logging.info(f"Current user: {current_user.username if current_user else 'None'}, role: {current_user.role if current_user else 'None'}")
    except Exception as log_error:
        logging.error(f"Logging hatası: {type(log_error).__name__}: {str(log_error)}", exc_info=True)
    
    logging.info(f"Personel ödemesi isteği alındı: {payment_data.staff_username}, tutar: {payment_data.amount}")
    try:
        if current_user.role != "admin":
            logging.warning(f"Yetkisiz erişim denemesi: {current_user.username}")
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        db = await get_db_from_request(request)
        logging.info(f"Database bağlantısı başarılı: {current_user.organization_id}")
        
        staff_username = payment_data.staff_username
        amount = float(payment_data.amount)  # Pydantic zaten float olarak validate ediyor ama emin olmak için
        date = payment_data.date or datetime.now().strftime("%Y-%m-%d")
        
        logging.info(f"Personel aranıyor: {staff_username}, organization: {current_user.organization_id}")
        
        # Personel bilgisini al
        staff = await db.users.find_one(
            {"username": staff_username, "organization_id": current_user.organization_id, "role": "staff"},
            {"_id": 0, "full_name": 1}
        )
        
        if not staff:
            logging.error(f"Personel bulunamadı: {staff_username}")
            raise HTTPException(status_code=404, detail="Personel bulunamadı")
        
        staff_name = staff.get("full_name") or staff_username
        logging.info(f"Personel bulundu: {staff_name}")
        
        # Gider olarak kaydet
        expense_data = {
            "id": str(uuid.uuid4()),
            "organization_id": current_user.organization_id,
            "title": f"{staff_name} - Personel Ödemesi",
            "amount": float(amount),
            "category": "Personel Ödemesi",
            "date": date,
            "staff_username": staff_username,  # Personel takibi için
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        logging.info(f"Expense data hazırlandı: {expense_data}")
        logging.info(f"Expenses collection'a kaydediliyor...")
        
        try:
            result = await db.expenses.insert_one(expense_data)
            logging.info(f"MongoDB insert result: inserted_id={result.inserted_id}")
        except Exception as insert_error:
            logging.error(f"Expenses collection'a yazma hatası: {type(insert_error).__name__}: {str(insert_error)}")
            raise
        
        logging.info(f"Personel ödemesi başarıyla kaydedildi: {staff_username}, tutar: {amount}, tarih: {date}")
        
        # Response için expense_data'yı temizle (MongoDB ObjectId gibi serialize edilemeyen alanları kaldır)
        response_expense = {
            "id": expense_data["id"],
            "organization_id": expense_data["organization_id"],
            "title": expense_data["title"],
            "amount": float(expense_data["amount"]),
            "category": expense_data["category"],
            "date": expense_data["date"],
            "staff_username": expense_data.get("staff_username"),
            "created_at": expense_data["created_at"]
        }
        
        try:
            response_data = {"message": "Ödeme kaydedildi", "expense": response_expense}
            logging.info(f"Response hazırlandı: {response_data}")
            return response_data
        except Exception as response_error:
            logging.error(f"Response oluşturma hatası: {type(response_error).__name__}: {str(response_error)}", exc_info=True)
            # Yine de başarılı response dön
            return {"message": "Ödeme kaydedildi", "expense_id": expense_data.get("id")}
    except HTTPException as e:
        logging.error(f"HTTPException: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        import traceback
        full_traceback = traceback.format_exc()
        logging.error(f"Personel ödemesi kaydetme hatası: {error_type}: {error_message}")
        logging.error(f"Full traceback:\n{full_traceback}")
        raise HTTPException(status_code=500, detail=f"Ödeme kaydedilirken bir hata oluştu: {error_message}")

# === PUBLIC API ROUTES (TOKEN GEREKTİRMEZ) ===
@api_router.get("/public/business/{slug}")
async def get_public_business(request: Request, slug: str):
    """Slug ile işletme bilgilerini, hizmetlerini, personellerini ve ayarlarını getir (Model D)"""
    db = await get_db_from_request(request)
    
    # İlk önce user'dan slug'ı bul (admin kullanıcısı)
    admin_user = await db.users.find_one({"slug": slug}, {"_id": 0})
    if not admin_user:
        raise HTTPException(status_code=404, detail="İşletme bulunamadı")
    
    organization_id = admin_user.get('organization_id')
    
    # Hizmetleri çek
    services = await db.services.find({"organization_id": organization_id}, {"_id": 0}).to_list(1000)

    def sort_key(svc: dict):
        order = svc.get("order")
        return (
            order if isinstance(order, int) else 1_000_000,
            svc.get("created_at") or "",
            svc.get("name") or "",
        )

    services = sorted(services, key=sort_key)
    
    # Ayarları çek
    settings = await db.settings.find_one({"organization_id": organization_id}, {"_id": 0})
    if not settings:
        # Varsayılan ayarlar
        settings = {
            "customer_can_choose_staff": False,
            "work_start_hour": 9,
            "work_end_hour": 18,
            "appointment_interval": 30,
            "company_name": admin_user.get('full_name', 'İşletme'),
            "admin_provides_service": True,
            "show_service_duration_on_public": True,
            "show_service_price_on_public": True
        }
    else:
        # Yeni alanlar yoksa varsayılan değerleri ekle
        if "show_service_duration_on_public" not in settings:
            settings["show_service_duration_on_public"] = True
        if "show_service_price_on_public" not in settings:
            settings["show_service_price_on_public"] = True
    
    # Tüm personelleri çek (SADECE gerekli alanlar - ŞİFRELER HARİÇ!)
    staff_members = await db.users.find(
        {"organization_id": organization_id}, 
        {"_id": 0, "full_name": 1, "id": 1, "permitted_service_ids": 1, "username": 1, "role": 1}
    ).to_list(1000)
    
    # Admin hizmet vermiyorsa admin'i listeden çıkar
    if not settings.get('admin_provides_service', True):
        staff_members = [staff for staff in staff_members if staff.get('role') != 'admin']
    
    return {
        "business_name": settings.get('company_name', admin_user.get('full_name', 'İşletme')),
        "logo_url": settings.get('logo_url'),
        "images": settings.get('images', []) or [],
        "location": settings.get('location'),
        "organization_id": organization_id,
        "services": services,
        "staff_members": staff_members,
        "settings": {
            "customer_can_choose_staff": settings.get('customer_can_choose_staff', False),
            "work_start_hour": settings.get('work_start_hour', 9),
            "work_end_hour": settings.get('work_end_hour', 18),
            "appointment_interval": settings.get('appointment_interval', 30),
            "show_service_duration_on_public": settings.get('show_service_duration_on_public', True),
            "show_service_price_on_public": settings.get('show_service_price_on_public', True)
        }
    }

@api_router.get("/public/availability/{organization_id}")
async def get_availability(request: Request, organization_id: str, service_id: str, date: str, staff_id: Optional[str] = None):
    """Model D: Personel bazlı akıllı müsaitlik kontrolü - business_hours ve days_off kullanır"""
    db = await get_db_from_request(request)
    
    # Ayarları al (admin_provides_service ve business_hours için)
    settings = await db.settings.find_one({"organization_id": organization_id}, {"_id": 0})
    if not settings:
        settings = {
            "work_start_hour": 9, 
            "work_end_hour": 18, 
            "appointment_interval": 30, 
            "admin_provides_service": True,
            "business_hours": {
                "monday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "tuesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "wednesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "thursday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "friday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "saturday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"},
                "sunday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"}
            }
        }
    
    admin_provides_service = settings.get('admin_provides_service', True)
    business_hours = settings.get('business_hours', {})
    
    # Tarihin hangi güne denk geldiğini bul (0=Monday, 6=Sunday)
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.weekday()  # 0=Monday, 6=Sunday
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_name = day_names[weekday]
    except (ValueError, TypeError):
        day_name = "monday"  # Varsayılan
    
    # Eğer müşteri belirli bir personel seçtiyse, sadece o personele bak
    selected_staff = None
    if staff_id:
        staff_query = {
            "organization_id": organization_id,
            "username": staff_id,
            "permitted_service_ids": {"$in": [service_id]}
        }
        
        # Admin'in "hizmet verir" ayarı kapalıysa, admin'i personel listesinden çıkar
        if not admin_provides_service:
            staff_query["role"] = {"$ne": "admin"}
        
        staff_members = await db.users.find(
            staff_query,
            {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1, "breaks": 1}
        ).to_list(1000)
        
        # Eğer seçilen personel bulunamadıysa ve admin_provides_service kapalıysa bile, admin'in bu hizmeti verebilip veremediğini kontrol et
        if not staff_members:
            # Admin'in bu hizmeti verebilip veremediğini kontrol et (eğer seçilen staff_id admin ise)
            admin_user = await db.users.find_one(
                {"organization_id": organization_id, "role": "admin", "username": staff_id},
                {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1}
            )
            if admin_user and service_id in (admin_user.get('permitted_service_ids') or []):
                # Admin bu hizmeti verebiliyorsa, admin'i personel listesine ekle
                staff_members = [admin_user]
                logging.info(f"⚠️ Availability: Selected staff not found, but admin can provide service. Using admin: {admin_user['username']}")
        
        if not staff_members:
            return {"available_slots": [], "message": "Seçilen personel bu hizmeti veremiyor"}
        
        selected_staff = staff_members[0]
        
        # Personelin days_off kontrolü
        staff_days_off = selected_staff.get('days_off') or []
        if day_name in staff_days_off:
            # Personel bu gün izinli, müsaitlik yok
            logging.info(f"Staff {staff_id} is off on {day_name}")
            return {
                "available_slots": [],
                "all_slots": [],
                "busy_slots": [],
                "message": "Seçili personel bu gün izinli"
            }
    else:
        # O hizmeti verebilen TÜM personelleri bul (Array içinde arama)
        staff_query = {
            "organization_id": organization_id,
            "permitted_service_ids": {"$in": [service_id]}
        }
        
        # Admin'in "hizmet verir" ayarı kapalıysa, admin'i personel listesinden çıkar
        if not admin_provides_service:
            staff_query["role"] = {"$ne": "admin"}
        
        staff_members = await db.users.find(
            staff_query,
            {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1, "breaks": 1}
        ).to_list(1000)
        
        # Eğer başka personel yoksa ve admin_provides_service kapalıysa bile, admin'in bu hizmeti verebilip veremediğini kontrol et
        if not staff_members:
            logging.info(f"⚠️ Availability: No staff found for service_id={service_id}, admin_provides_service={admin_provides_service}. Checking admin...")
            # Admin'in bu hizmeti verebilip veremediğini kontrol et
            admin_user = await db.users.find_one(
                {"organization_id": organization_id, "role": "admin"},
                {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1}
            )
            if admin_user:
                admin_permitted_services = admin_user.get('permitted_service_ids') or []
                logging.info(f"⚠️ Availability: Admin found: {admin_user['username']}, permitted_service_ids: {admin_permitted_services}, checking service_id: {service_id}")
                if service_id in admin_permitted_services:
                    # Admin bu hizmeti verebiliyorsa, admin'i personel listesine ekle
                    # Admin'in tüm gerekli alanlarını ekle
                    admin_staff_member = {
                        "id": admin_user.get('id', admin_user.get('username')),
                        "username": admin_user['username'],
                        "role": "admin",
                        "days_off": admin_user.get('days_off', []),
                        "permitted_service_ids": admin_permitted_services
                    }
                    staff_members = [admin_staff_member]
                    logging.info(f"✅ Availability: Admin can provide service. Using admin: {admin_user['username']}, staff_member: {admin_staff_member}")
                else:
                    logging.warning(f"❌ Availability: Admin found but service_id {service_id} not in permitted_service_ids: {admin_permitted_services}")
            else:
                logging.warning(f"❌ Availability: No admin user found for organization_id: {organization_id}")
        
        if not staff_members:
            # Hiç personel yoksa veya hiçbiri bu hizmeti vermiyorsa boş dön
            logging.warning(f"❌ Availability: No staff members found after admin check. Returning empty slots.")
            return {"available_slots": [], "message": "Bu hizmet için uygun personel bulunamadı"}
    
        logging.info(f"✅ Availability: Found {len(staff_members)} staff member(s): {[s.get('username') for s in staff_members]}")
    
        # Tüm personellerin bu gün izinli olup olmadığını kontrol et
        all_staff_off = all(
            day_name in (staff.get('days_off') or [])
            for staff in staff_members
        )
        if all_staff_off:
            logging.info(f"❌ Availability: All staff are off on {day_name}. Staff: {[s.get('username') for s in staff_members]}, days_off: {[s.get('days_off') for s in staff_members]}")
            return {
                "available_slots": [],
                "all_slots": [],
                "busy_slots": [],
                "message": "Tüm personeller bu gün izinli"
            }
    
    # business_hours'dan o günün saatlerini al
    day_hours = business_hours.get(day_name, {})
    logging.info(f"🔍 Availability Check - Date: {date}, Day: {day_name}, day_hours: {day_hours}")
    is_open_value = day_hours.get('is_open', True)
    logging.info(f"🔍 is_open value: {is_open_value}, type: {type(is_open_value)}")
    
    if not is_open_value:
        # İşletme bu gün kapalı
        logging.info(f"❌ Business is closed on {day_name}")
        return {
            "available_slots": [],
            "all_slots": [],
            "busy_slots": [],
            "message": "İşletme bu gün kapalı"
        }
    
    logging.info(f"✅ Business is open on {day_name}")
    
    # Açılış ve kapanış saatlerini parse et
    open_time_str = day_hours.get('open_time', '09:00')
    close_time_str = day_hours.get('close_time', '18:00')
    
    try:
        open_hour, open_minute = map(int, open_time_str.split(':'))
        close_hour, close_minute = map(int, close_time_str.split(':'))
        # "00:00" gece yarısı demek — 24:00 olarak işle (günün sonu)
        if close_hour == 0 and close_minute == 0:
            close_hour = 24
    except (ValueError, AttributeError):
        # Varsayılan saatler
        open_hour, open_minute = 9, 0
        close_hour, close_minute = 18, 0
    
    # Hizmet süresini al
    service = await db.services.find_one({"id": service_id}, {"_id": 0, "duration": 1})
    if not service:
        return {"available_slots": [], "all_slots": [], "busy_slots": [], "message": "Hizmet bulunamadı"}
    
    service_duration = service.get('duration', 30)  # Dakika cinsinden
    
    # KRİTİK: Personel aynı anda sadece 1 müşteriye hizmet verebilir
    # O hizmeti verebilen personellerin o tarihteki TÜM randevularını çek (hangi hizmet olursa olsun)
    staff_ids = [staff['username'] for staff in staff_members]
    logging.info(f"📋 Availability: staff_members count: {len(staff_members)}, staff_ids: {staff_ids}, staff_id param: {staff_id}")
    
    # Personellerin o gün için TÜM randevularını al (tüm hizmetler dahil) - başlangıç ve bitiş saatleriyle
    # staff_member_id=None (atanmamış) randevuları da dahil et — tek kişilik org'larda çakışma kaçmasın
    all_staff_appointments = await db.appointments.find(
        {
            "organization_id": organization_id,
            "appointment_date": date,
            "status": {"$ne": "İptal"},
            "$or": [
                {"staff_member_id": {"$in": staff_ids}},
                {"staff_member_id": None}
            ]
        },
        {"_id": 0, "appointment_time": 1, "staff_member_id": 1, "service_name": 1, "service_id": 1}
    ).to_list(1000)
    
    logging.info(f"📋 Found {len(all_staff_appointments)} appointments for staff_ids: {staff_ids}")
    if len(all_staff_appointments) > 0:
        for appt in all_staff_appointments[:5]:  # İlk 5 randevuyu logla
            logging.info(f"   - {appt.get('appointment_time')} - Staff: {appt.get('staff_member_id')} - Service: {appt.get('service_id')}")
    else:
        logging.info(f"   ⚠️ No appointments found for date {date} and staff_ids {staff_ids}")
        # Tüm randevuları kontrol et (debug için)
        all_appts_debug = await db.appointments.find(
            {
                "organization_id": organization_id,
                "appointment_date": date,
                "status": {"$ne": "İptal"}
            },
            {"_id": 0, "appointment_time": 1, "staff_member_id": 1, "service_id": 1}
        ).to_list(10)
        logging.info(f"   🔍 Debug: Total appointments for date {date} (all staff): {len(all_appts_debug)}")
        for appt_debug in all_appts_debug:
            logging.info(f"      - {appt_debug.get('appointment_time')} - Staff: {appt_debug.get('staff_member_id')} - Service: {appt_debug.get('service_id')}")
    
    # Her randevunun bitiş saatini hesapla (hizmet süresine göre)
    appointments_with_end_time = []
    for appt in all_staff_appointments:
        appt_service_id = appt.get('service_id')
        if appt_service_id:
            appt_service = await db.services.find_one({"id": appt_service_id}, {"_id": 0, "duration": 1})
            appt_duration = appt_service.get('duration', 30) if appt_service else 30
        else:
            appt_duration = 30  # Varsayılan
        
        start_time_str = appt['appointment_time']
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_minute = start_minute + appt_duration
        end_hour = start_hour + (end_minute // 60)
        end_minute = end_minute % 60
        end_time_str = f"{str(end_hour).zfill(2)}:{str(end_minute).zfill(2)}"
        
        appointments_with_end_time.append({
            "start_time": start_time_str,
            "end_time": end_time_str,
            "staff_member_id": appt['staff_member_id']
        })
    
    # Personel molalarını da meşgul slotlara ekle
    for staff in staff_members:
        staff_breaks = staff.get('breaks', [])
        for brk in staff_breaks:
            if brk.get('date') == date:
                appointments_with_end_time.append({
                    "start_time": brk['start_time'],
                    "end_time": brk['end_time'],
                    "staff_member_id": staff['username'],
                    "is_break": True
                })
    
    # Gizli adım aralığı (15 dakika)
    STEP_INTERVAL = 15  # Dakika
    
    # Bugünün saatini al (geçmiş saat kontrolü için)
    now = datetime.now(timezone.utc)
    turkey_tz = timezone(timedelta(hours=3))
    now_turkey = now.astimezone(turkey_tz)
    is_today = date == now_turkey.strftime("%Y-%m-%d")
    current_hour_now = now_turkey.hour
    current_minute_now = now_turkey.minute
    
    # Potansiyel slotları oluştur (15 dakikalık adımlarla)
    potential_slots = []
    current_hour = open_hour
    current_minute = open_minute
    
    while True:
        # Kapanış saatine ulaştık mı kontrol et
        if current_hour > close_hour or (current_hour == close_hour and current_minute >= close_minute):
            break
        
        time_str = f"{str(current_hour).zfill(2)}:{str(current_minute).zfill(2)}"
        potential_slots.append(time_str)
        
        # 15 dakika ilerle
        current_minute += STEP_INTERVAL
        if current_minute >= 60:
            current_minute = current_minute % 60
            current_hour += 1
    
    # Müsait saatleri hesapla
    final_available_slots = []
    busy_slots = []
    
    for potential_start_time in potential_slots:
        # Bitiş saatini hesapla
        start_hour, start_minute = map(int, potential_start_time.split(':'))
        end_minute = start_minute + service_duration
        end_hour = start_hour + (end_minute // 60)
        end_minute = end_minute % 60
        potential_end_time = f"{str(end_hour).zfill(2)}:{str(end_minute).zfill(2)}"
        
        # Geçmiş saat kontrolü
        if is_today:
            if start_hour < current_hour_now or (start_hour == current_hour_now and start_minute < current_minute_now):
                # Geçmiş saat - busy slot olarak işaretle (gösterilecek ama seçilemeyecek)
                busy_slots.append(potential_start_time)
                continue  # Bu slotu atla
        
        # Genel saat kontrolü (bitiş saati kapanış saatini aşıyor mu?)
        if end_hour > close_hour or (end_hour == close_hour and end_minute > close_minute):
            continue  # Bu slotu atla
        
        # Randevu çakışma kontrolü
        if staff_id:
            # Belirli bir personel seçildi - sadece onun randevularını kontrol et
            has_conflict = False
            for appt in appointments_with_end_time:
                if appt['staff_member_id'] != staff_id:
                    continue
                
                appt_start = appt['start_time']
                appt_end = appt['end_time']
                
                # Çakışma kontrolü: Zamanları sayısal değerlere çevir (dakika cinsinden)
                def time_to_minutes(time_str):
                    """Zaman string'ini (HH:MM) dakika cinsinden sayıya çevir"""
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        return hour * 60 + minute
                    except (ValueError, AttributeError):
                        return 0
                
                potential_start_min = time_to_minutes(potential_start_time)
                potential_end_min = time_to_minutes(potential_end_time)
                appt_start_min = time_to_minutes(appt_start)
                appt_end_min = time_to_minutes(appt_end)
                
                # Çakışma kontrolü: (yeni_başlangıç < mevcut_bitiş) VE (yeni_bitiş > mevcut_başlangıç)
                if (potential_start_min < appt_end_min and potential_end_min > appt_start_min):
                    has_conflict = True
                    logging.info(f"   ⚠️ Conflict: Slot {potential_start_time}-{potential_end_time} overlaps with {appt_start}-{appt_end} (Staff: {staff_id})")
                    break
            
            if has_conflict:
                # Seçili personel için busy slot
                busy_slots.append(potential_start_time)
                continue
            else:
                # Seçili personel için müsait (çakışma yok)
                final_available_slots.append(potential_start_time)
                logging.debug(f"   ✅ Available slot: {potential_start_time}-{potential_end_time} (Staff: {staff_id})")
        else:
            # Otomatik atama - Tüm personeller için kontrol et
            # En az bir personel müsait olmalı
            busy_staff_at_slot = []
            
            # Zamanları sayısal değerlere çevir (dakika cinsinden)
            def time_to_minutes(time_str):
                """Zaman string'ini (HH:MM) dakika cinsinden sayıya çevir"""
                try:
                    hour, minute = map(int, time_str.split(':'))
                    return hour * 60 + minute
                except (ValueError, AttributeError):
                    return 0
            
            potential_start_min = time_to_minutes(potential_start_time)
            potential_end_min = time_to_minutes(potential_end_time)
            
            for appt in appointments_with_end_time:
                appt_start = appt['start_time']
                appt_end = appt['end_time']
                
                appt_start_min = time_to_minutes(appt_start)
                appt_end_min = time_to_minutes(appt_end)
                
                # Bu personel bu slotta dolu mu?
                if (potential_start_min < appt_end_min and potential_end_min > appt_start_min):
                    busy_staff_at_slot.append(appt['staff_member_id'])
            
            busy_staff_unique = list(set(busy_staff_at_slot))
            
            # Eğer tüm personeller doluysa busy slot
            if len(busy_staff_unique) >= len(staff_members):
                busy_slots.append(potential_start_time)
                logging.debug(f"   🚫 All staff busy at {potential_start_time}-{potential_end_time}")
            else:
                # En az bir personel müsait - slot müsait
                final_available_slots.append(potential_start_time)
                available_count = len(staff_members) - len(busy_staff_unique)
                logging.debug(f"   ✅ Available slot: {potential_start_time}-{potential_end_time} ({available_count}/{len(staff_members)} staff available)")
    
    logging.info(f"🔍 Service: {service_id}, Date: {date}, Duration: {service_duration}min")
    logging.info(f"👥 Qualified staff: {len(staff_members)} - {staff_ids}")
    logging.info(f"📅 Total appointments: {len(appointments_with_end_time)}")
    logging.info(f"✅ Available slots: {len(final_available_slots)}")
    logging.info(f"🚫 Busy slots: {len(busy_slots)}")
    return {
        "available_slots": final_available_slots,
        "busy_slots": busy_slots,
        "all_slots": potential_slots,
        "message": "OK"
    }


@api_router.get("/availability")
async def get_internal_availability(
    request: Request,
    service_id: str,
    date: str,
    staff_id: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    """İç kullanım müsaitlik endpoint'i.

    Admin panelindeki randevu oluşturma akışında, personel seçilmediyse (auto-assign)
    slotlar personelin haftalık izin günlerine (days_off) bağlı olmamalıdır.
    staff_id verilirse, seçilen personelin days_off kontrolü uygulanır.
    """
    db = await get_db_from_request(request)
    organization_id = current_user.organization_id

    settings = await db.settings.find_one({"organization_id": organization_id}, {"_id": 0})
    if not settings:
        settings = {
            "work_start_hour": 9,
            "work_end_hour": 18,
            "appointment_interval": 30,
            "admin_provides_service": True,
            "business_hours": {
                "monday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "tuesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "wednesday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "thursday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "friday": {"is_open": True, "open_time": "09:00", "close_time": "18:00"},
                "saturday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"},
                "sunday": {"is_open": False, "open_time": "09:00", "close_time": "18:00"}
            }
        }

    admin_provides_service = settings.get('admin_provides_service', True)
    business_hours = settings.get('business_hours', {})

    # Tarihin hangi güne denk geldiğini bul (0=Monday, 6=Sunday)
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.weekday()  # 0=Monday, 6=Sunday
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_name = day_names[weekday]
    except (ValueError, TypeError):
        day_name = "monday"  # Varsayılan

    if staff_id:
        staff_query = {
            "organization_id": organization_id,
            "username": staff_id,
            "permitted_service_ids": {"$in": [service_id]}
        }

        if not admin_provides_service:
            staff_query["role"] = {"$ne": "admin"}

        staff_members = await db.users.find(
            staff_query,
            {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1, "breaks": 1}
        ).to_list(1000)

        if not staff_members:
            return {"available_slots": [], "all_slots": [], "busy_slots": [], "message": "Seçilen personel bu hizmeti veremiyor"}

        selected_staff = staff_members[0]
        staff_days_off = selected_staff.get('days_off') or []
        if day_name in staff_days_off:
            return {
                "available_slots": [],
                "all_slots": [],
                "busy_slots": [],
                "message": "Seçili personel bu gün izinli"
            }
    else:
        staff_query = {
            "organization_id": organization_id,
            "permitted_service_ids": {"$in": [service_id]}
        }

        if not admin_provides_service:
            staff_query["role"] = {"$ne": "admin"}

        staff_members = await db.users.find(
            staff_query,
            {"_id": 0, "id": 1, "username": 1, "role": 1, "days_off": 1, "permitted_service_ids": 1, "breaks": 1}
        ).to_list(1000)

        if not staff_members:
            # Admin panelinde hiç uygun personel yoksa (ve staff_id seçilmemişse),
            # admin unassigned randevu yazabilsin diye slotları işletme saatlerinden üret.
            # Not: staff_id seçilmişse zaten yukarıda "Seçilen personel..." mesajı dönüyoruz.
            if current_user.role != "admin":
                return {"available_slots": [], "all_slots": [], "busy_slots": [], "message": "Bu hizmet için uygun personel bulunamadı"}

            # business_hours'dan o günün saatlerini al
            day_hours = business_hours.get(day_name, {})
            is_open_value = day_hours.get('is_open', True)
            if not is_open_value:
                return {
                    "available_slots": [],
                    "all_slots": [],
                    "busy_slots": [],
                    "message": "İşletme bu gün kapalı"
                }

            open_time_str = day_hours.get('open_time', '09:00')
            close_time_str = day_hours.get('close_time', '18:00')
            try:
                open_hour, open_minute = map(int, open_time_str.split(':'))
                close_hour, close_minute = map(int, close_time_str.split(':'))
                # "00:00" gece yarısı demek — 24:00 olarak işle (günün sonu)
                if close_hour == 0 and close_minute == 0:
                    close_hour = 24
            except (ValueError, AttributeError):
                open_hour, open_minute = 9, 0
                close_hour, close_minute = 18, 0

            service = await db.services.find_one(
                {"id": service_id, "organization_id": organization_id},
                {"_id": 0, "duration": 1}
            )
            if not service:
                return {"available_slots": [], "all_slots": [], "busy_slots": [], "message": "Hizmet bulunamadı"}

            service_duration = service.get('duration', 30)

            # Organizasyondaki tüm randevular: aynı gün/saatte çakışma varsa slotu "busy" say.
            org_appointments = await db.appointments.find(
                {
                    "organization_id": organization_id,
                    "appointment_date": date,
                    "status": {"$ne": "İptal"},
                },
                {"_id": 0, "appointment_time": 1, "service_id": 1}
            ).to_list(1000)

            appointments_with_end_time = []
            for appt in org_appointments:
                appt_service_id = appt.get('service_id')
                if appt_service_id:
                    appt_service = await db.services.find_one(
                        {"id": appt_service_id, "organization_id": organization_id},
                        {"_id": 0, "duration": 1}
                    )
                    appt_duration = appt_service.get('duration', 30) if appt_service else 30
                else:
                    appt_duration = 30

                start_time_str = appt.get('appointment_time')
                if not start_time_str:
                    continue
                start_hour, start_minute = map(int, start_time_str.split(':'))
                end_minute = start_minute + appt_duration
                end_hour = start_hour + (end_minute // 60)
                end_minute = end_minute % 60
                end_time_str = f"{str(end_hour).zfill(2)}:{str(end_minute).zfill(2)}"
                appointments_with_end_time.append({
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                })

            STEP_INTERVAL = 15

            now = datetime.now(timezone.utc)
            turkey_tz = timezone(timedelta(hours=3))
            now_turkey = now.astimezone(turkey_tz)
            is_today = date == now_turkey.strftime("%Y-%m-%d")
            current_now_minutes = now_turkey.hour * 60 + now_turkey.minute

            potential_slots = []
            current_hour = open_hour
            current_minute = open_minute
            while True:
                if current_hour > close_hour or (current_hour == close_hour and current_minute >= close_minute):
                    break
                potential_slots.append(f"{str(current_hour).zfill(2)}:{str(current_minute).zfill(2)}")
                current_minute += STEP_INTERVAL
                if current_minute >= 60:
                    current_minute = current_minute % 60
                    current_hour += 1

            def time_to_minutes(time_str: str) -> int:
                try:
                    h, m = map(int, time_str.split(':'))
                    return h * 60 + m
                except Exception:
                    return 0

            available_slots = []
            busy_slots = []
            for start_time in potential_slots:
                start_minutes = time_to_minutes(start_time)
                end_minutes = start_minutes + service_duration

                # Kapanış saatini aşan başlangıçları engelle
                close_minutes = close_hour * 60 + close_minute
                if end_minutes > close_minutes:
                    continue

                if is_today and start_minutes <= current_now_minutes:
                    continue

                has_conflict = False
                for ex in appointments_with_end_time:
                    ex_start = time_to_minutes(ex['start_time'])
                    ex_end = time_to_minutes(ex['end_time'])
                    if start_minutes < ex_end and end_minutes > ex_start:
                        has_conflict = True
                        break

                if has_conflict:
                    busy_slots.append(start_time)
                else:
                    available_slots.append(start_time)

            return {
                "available_slots": available_slots,
                "busy_slots": busy_slots,
                "all_slots": potential_slots,
                "message": "OK"
            }

    # business_hours'dan o günün saatlerini al
    day_hours = business_hours.get(day_name, {})
    is_open_value = day_hours.get('is_open', True)
    if not is_open_value:
        return {
            "available_slots": [],
            "all_slots": [],
            "busy_slots": [],
            "message": "İşletme bu gün kapalı"
        }

    open_time_str = day_hours.get('open_time', '09:00')
    close_time_str = day_hours.get('close_time', '18:00')
    try:
        open_hour, open_minute = map(int, open_time_str.split(':'))
        close_hour, close_minute = map(int, close_time_str.split(':'))
        # "00:00" gece yarısı demek — 24:00 olarak işle (günün sonu)
        if close_hour == 0 and close_minute == 0:
            close_hour = 24
    except (ValueError, AttributeError):
        open_hour, open_minute = 9, 0
        close_hour, close_minute = 18, 0

    service = await db.services.find_one(
        {"id": service_id, "organization_id": organization_id},
        {"_id": 0, "duration": 1}
    )
    if not service:
        return {"available_slots": [], "all_slots": [], "busy_slots": [], "message": "Hizmet bulunamadı"}

    service_duration = service.get('duration', 30)

    staff_ids = [staff['username'] for staff in staff_members]
    all_staff_appointments = await db.appointments.find(
        {
            "organization_id": organization_id,
            "appointment_date": date,
            "status": {"$ne": "İptal"},
            "staff_member_id": {"$in": staff_ids}
        },
        {"_id": 0, "appointment_time": 1, "staff_member_id": 1, "service_id": 1}
    ).to_list(1000)

    appointments_with_end_time = []
    for appt in all_staff_appointments:
        appt_service_id = appt.get('service_id')
        if appt_service_id:
            appt_service = await db.services.find_one(
                {"id": appt_service_id, "organization_id": organization_id},
                {"_id": 0, "duration": 1}
            )
            appt_duration = appt_service.get('duration', 30) if appt_service else 30
        else:
            appt_duration = 30

        start_time_str = appt['appointment_time']
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_minute = start_minute + appt_duration
        end_hour = start_hour + (end_minute // 60)
        end_minute = end_minute % 60
        end_time_str = f"{str(end_hour).zfill(2)}:{str(end_minute).zfill(2)}"

        appointments_with_end_time.append({
            "start_time": start_time_str,
            "end_time": end_time_str,
            "staff_member_id": appt['staff_member_id']
        })

    for staff in staff_members:
        staff_breaks = staff.get('breaks', [])
        for brk in staff_breaks:
            if brk.get('date') == date:
                appointments_with_end_time.append({
                    "start_time": brk['start_time'],
                    "end_time": brk['end_time'],
                    "staff_member_id": staff['username'],
                    "is_break": True
                })

    STEP_INTERVAL = 15

    now = datetime.now(timezone.utc)
    turkey_tz = timezone(timedelta(hours=3))
    now_turkey = now.astimezone(turkey_tz)
    is_today = date == now_turkey.strftime("%Y-%m-%d")
    current_hour_now = now_turkey.hour
    current_minute_now = now_turkey.minute

    potential_slots = []
    current_hour = open_hour
    current_minute = open_minute
    while True:
        if current_hour > close_hour or (current_hour == close_hour and current_minute >= close_minute):
            break
        potential_slots.append(f"{str(current_hour).zfill(2)}:{str(current_minute).zfill(2)}")
        current_minute += STEP_INTERVAL
        if current_minute >= 60:
            current_minute = current_minute % 60
            current_hour += 1

    final_available_slots = []
    busy_slots = []

    def time_to_minutes(time_str):
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour * 60 + minute
        except (ValueError, AttributeError):
            return 0

    for potential_start_time in potential_slots:
        start_hour, start_minute = map(int, potential_start_time.split(':'))
        end_minute_total = start_minute + service_duration
        end_hour = start_hour + (end_minute_total // 60)
        end_minute = end_minute_total % 60
        potential_end_time = f"{str(end_hour).zfill(2)}:{str(end_minute).zfill(2)}"

        if is_today:
            if start_hour < current_hour_now or (start_hour == current_hour_now and start_minute < current_minute_now):
                busy_slots.append(potential_start_time)
                continue

        if end_hour > close_hour or (end_hour == close_hour and end_minute > close_minute):
            continue

        potential_start_min = time_to_minutes(potential_start_time)
        potential_end_min = time_to_minutes(potential_end_time)

        if staff_id:
            has_conflict = False
            for appt in appointments_with_end_time:
                if appt['staff_member_id'] != staff_id:
                    continue
                appt_start_min = time_to_minutes(appt['start_time'])
                appt_end_min = time_to_minutes(appt['end_time'])
                if (potential_start_min < appt_end_min and potential_end_min > appt_start_min):
                    has_conflict = True
                    break
            if has_conflict:
                busy_slots.append(potential_start_time)
                continue
            final_available_slots.append(potential_start_time)
        else:
            # Auto-assign: en az bir personelde çakışma olmamalı (days_off dikkate alınmaz)
            any_available = False
            for staff_username in staff_ids:
                has_conflict = False
                for appt in appointments_with_end_time:
                    if appt['staff_member_id'] != staff_username:
                        continue
                    appt_start_min = time_to_minutes(appt['start_time'])
                    appt_end_min = time_to_minutes(appt['end_time'])
                    if (potential_start_min < appt_end_min and potential_end_min > appt_start_min):
                        has_conflict = True
                        break
                if not has_conflict:
                    any_available = True
                    break
            if any_available:
                final_available_slots.append(potential_start_time)
            else:
                busy_slots.append(potential_start_time)

    return {
        "available_slots": final_available_slots,
        "busy_slots": busy_slots,
        "all_slots": potential_slots,
        "message": "OK"
    }

# ═══════════════════════════════════════════════════════════════════════
# 🔒 PLANN GÜVENLİK — Yardımcı Fonksiyonlar (5 Katmanlı Savunma)
# ═══════════════════════════════════════════════════════════════════════

async def verify_turnstile(token: str, client_ip: str = "") -> bool:
    """Cloudflare Turnstile token doğrulama — Katman 1"""
    secret = os.getenv("TURNSTILE_SECRET_KEY", "")
    if not secret:
        logging.warning("TURNSTILE_SECRET_KEY eksik — Turnstile atlanıyor (dev mode)")
        return True
    if not token:
        return False
    try:
        def _check():
            resp = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token, "remoteip": client_ip},
                timeout=5.0,
            )
            return resp.json().get("success", False)
        return await asyncio.to_thread(_check)
    except Exception as e:
        logging.error(f"Turnstile doğrulama hatası: {e}")
        return False

_PHONE_COUNTRY_MAP = {
    "90": "TR", "44": "GB", "1": "US", "49": "DE",
    "33": "FR", "39": "IT", "34": "ES", "31": "NL",
    "7": "RU", "86": "CN", "81": "JP", "82": "KR",
    "61": "AU", "55": "BR", "91": "IN",
}

def get_phone_country(phone: str) -> str:
    """Telefon numarasından ülke kodu tahmin et — Katman 4"""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) == 11:
        return "TR"
    for prefix_len in (3, 2, 1):
        country = _PHONE_COUNTRY_MAP.get(digits[:prefix_len])
        if country:
            return country
    return ""

async def get_geo_country(redis_client, ip: str) -> str:
    """IP → ülke kodu (Redis 24h cache, ip-api.com) — Katman 4"""
    if not ip or ip in ("127.0.0.1", "::1", ""):
        return ""
    cache_key = f"plann:geo:{ip}"
    try:
        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached
        def _fetch():
            resp = requests.get(
                f"http://ip-api.com/json/{ip}?fields=countryCode",
                timeout=3.0,
            )
            return resp.json().get("countryCode", "")
        country = await asyncio.to_thread(_fetch)
        if redis_client and country:
            await redis_client.setex(cache_key, 86400, country)
        return country
    except Exception:
        return ""

async def create_pending_verification(redis_client, phone: str, org_id: str, appointment_data: dict) -> str:
    """
    WhatsApp doğrulama için Redis'e kayıt yaz (TTL 15 dk).
    Aynı numara için eski pending varsa EZİLİR — upsert mantığı.
    APScheduler gerekmez, Redis TTL otomatik temizler.
    """
    code = f"RND-{secrets.randbelow(90000) + 10000}"
    phone_map_key = f"plann:pending:phone:{phone}:{org_id}"
    ttl = 900  # 15 dakika
    if redis_client:
        old_code = await redis_client.get(phone_map_key)
        if old_code:
            old_str = old_code.decode() if isinstance(old_code, bytes) else old_code
            await redis_client.delete(f"plann:pending:{old_str}")
        code_key = f"plann:pending:{code}"
        await redis_client.hset(code_key, mapping={
            "phone": phone,
            "org_id": org_id,
            "appointment_data": json.dumps(appointment_data, ensure_ascii=False),
        })
        await redis_client.expire(code_key, ttl)
        await redis_client.setex(phone_map_key, ttl, code)
    return code


@api_router.post("/public/appointments")
async def create_public_appointment(request: Request, appointment: AppointmentCreate, organization_id: str):
    """Model D: Public randevu oluştur — 5 Katmanlı Güvenlik + Akıllı personel atama"""
    db = await get_db_from_request(request)
    redis_client = getattr(request.app.state, 'redis_client', None)

    # Gerçek istemci IP'si (Cloudflare proxy arkasında da doğru çalışır)
    client_ip = (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        (request.client.host if request.client else "")
    )

    # ═══════════════════════════════════════════════════════════
    # 🔒 KATMAN 1: CLOUDFLARE TURNSTILE
    # ═══════════════════════════════════════════════════════════
    turnstile_ok = await verify_turnstile(appointment.turnstile_token or "", client_ip)
    if not turnstile_ok:
        raise HTTPException(
            status_code=400,
            detail="Güvenlik doğrulaması başarısız. Lütfen sayfayı yenileyip tekrar deneyin.",
        )

    # ═══════════════════════════════════════════════════════════
    # 🔒 KATMAN 2: IP RATE LIMIT (15 istek / 12 saat)
    # ═══════════════════════════════════════════════════════════
    if redis_client and client_ip and client_ip not in ("127.0.0.1", "::1"):
        ip_key = f"plann:rate:ip:{client_ip}"
        ip_count = await redis_client.incr(ip_key)
        if ip_count == 1:
            await redis_client.expire(ip_key, 43200)  # 12 saat
        if ip_count > 50:
            raise HTTPException(
                status_code=429,
                detail="Bu ağdan çok fazla randevu talebi geldi. Lütfen daha sonra tekrar deneyin.",
            )

    # ═══════════════════════════════════════════════════════════
    # 🔒 KATMAN 3: TANINIK MÜŞTERİ BYPASS (MongoDB customers)
    # ═══════════════════════════════════════════════════════════
    existing_customer = await db.customers.find_one({
        "organization_id": organization_id,
        "phone": appointment.phone,
    })

    # ═══════════════════════════════════════════════════════════
    # 🔒 KATMAN 4: COĞRAFİ RİSK SKORU (ip-api.com, Redis 24h cache)
    # ═══════════════════════════════════════════════════════════
    high_risk = False
    if not existing_customer:
        geo_country = await get_geo_country(redis_client, client_ip)
        phone_country = get_phone_country(appointment.phone)
        if geo_country and phone_country and geo_country != phone_country:
            high_risk = True
            logging.info(f"🌍 Geo uyuşmazlık: IP={geo_country}, tel={phone_country} → yüksek risk")

    # KATMAN 3 KARAR: VIP bypass mı, WhatsApp doğrulama mı?
    skip_verification = False
    if existing_customer and not high_risk:
        if redis_client:
            known_key = f"plann:rate:known:{appointment.phone}"
            known_count = await redis_client.incr(known_key)
            if known_count == 1:
                await redis_client.expire(known_key, 86400)  # 24 saat
            if known_count <= 3:
                skip_verification = True
                logging.info(f"✅ Tanıdık müşteri bypass: {appointment.phone} ({known_count}/3 bugün)")
            else:
                logging.info(f"⚠️ Tanıdık müşteri günlük limit ({known_count}/3), WhatsApp zorunlu")
        else:
            skip_verification = True  # Redis yoksa bypass ver

    # ═══════════════════════════════════════════════════════════
    # 🔒 KATMAN 5: WHATSAPP NUMARA DOĞRULAMA
    # ═══════════════════════════════════════════════════════════
    if not skip_verification:
        # WA flood kontrolü (5 kod / 1 saat)
        if redis_client:
            wa_key = f"plann:rate:wa_req:{appointment.phone}"
            wa_count = await redis_client.incr(wa_key)
            if wa_count == 1:
                await redis_client.expire(wa_key, 3600)
            if wa_count > 5:
                raise HTTPException(
                    status_code=429,
                    detail="Çok fazla doğrulama kodu istediniz. Lütfen 1 saat sonra tekrar deneyin.",
                )

        appointment_payload = {
            "customer_name": appointment.customer_name,
            "phone": appointment.phone,
            "service_id": appointment.service_id,
            "appointment_date": appointment.appointment_date,
            "appointment_time": appointment.appointment_time,
            "notes": appointment.notes,
            "staff_member_id": appointment.staff_member_id,
        }
        code = await create_pending_verification(
            redis_client, appointment.phone, organization_id, appointment_payload
        )

        wa_business_number = os.getenv("WHATSAPP_BUSINESS_NUMBER", "")
        wa_number_clean = re.sub(r"\D", "", wa_business_number)
        wa_link = (
            f"https://wa.me/{wa_number_clean}?text=Randevu+onay%C4%B1:+{code}"
            if wa_number_clean else ""
        )
        logging.info(f"📱 WhatsApp doğrulama: {appointment.phone} → {code}")

        return {
            "needs_verification": True,
            "code": code,
            "wa_number": wa_business_number,
            "wa_link": wa_link,
            "message": "Lütfen WhatsApp'tan doğrulama kodunu gönderin.",
        }

    # ═══════════════════════════════════════════════════════════
    # ✅ GÜVENLİK KATMANLARI ONAYLADI — RANDEVU OLUŞTURMA
    # ═══════════════════════════════════════════════════════════

    # ---------------------------------------------------------
    # 🔒 ADIM 1: REDIS LOCK (ÇİFTE REZERVASYON ENGELLEYİCİ)
    # ---------------------------------------------------------
    lock_key = None # Hata durumunda silmek için dışarıda tanımlıyoruz

    if redis_client:
        # Eğer personel seçilmemişse "auto" kullanıyoruz
        staff_id_lock = appointment.staff_member_id or "auto"
        lock_key = f"plann:lock:appt:{organization_id}:{staff_id_lock}:{appointment.appointment_date}:{appointment.appointment_time}"
        
        acquired = await redis_client.setnx(lock_key, "locked")
        if not acquired:
            # Milisaniyelik farkla başkası tıkladı!
            raise HTTPException(
                status_code=409, 
                detail="Bu saat dilimi şu an başka bir müşteri tarafından dolduruluyor. Lütfen 10 saniye sonra tekrar deneyin."
            )
        await redis_client.expire(lock_key, 15) # Public tarafta işlem süresi (WhatsApp vs.) uzun sürebilir, 15sn ideal.
    
    # DEBUG: Frontend'ten gelen veriyi logla
    logging.info(f"🔍 PUBLIC APPOINTMENT REQUEST - staff_member_id: {appointment.staff_member_id}, service_id: {appointment.service_id}")
    
    # KOTA KONTROLÜ - Randevu oluşturmadan önce kontrol et
    quota_ok, quota_error = await check_quota_and_increment(db, organization_id)
    if not quota_ok:
        raise HTTPException(status_code=403, detail=quota_error)
    
    # Service'i bul
    service = await db.services.find_one({"id": appointment.service_id}, {"_id": 0})
    if not service:
        # Kota artırıldı ama hizmet bulunamadı, geri al
        plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
        if plan_doc:
            await db.organization_plans.update_one(
                {"organization_id": organization_id},
                {"$inc": {"quota_usage": -1}}
            )
        raise HTTPException(status_code=404, detail="Hizmet bulunamadı")
    
    assigned_staff_id = None
    
    # AKILLI ATAMA MANTIĞI
    service_duration = service.get('duration', 30)
    
    # Yeni randevunun başlangıç ve bitiş saatlerini hesapla
    new_start_hour, new_start_minute = map(int, appointment.appointment_time.split(':'))
    new_end_minute = new_start_minute + service_duration
    new_end_hour = new_start_hour + (new_end_minute // 60)
    new_end_minute = new_end_minute % 60
    new_end_time = f"{str(new_end_hour).zfill(2)}:{str(new_end_minute).zfill(2)}"
    
    if appointment.staff_member_id:
        # Müşteri belirli bir personel seçti - çakışma kontrolü yap (duration'a göre)
        # Bu personelin o tarihteki tüm randevularını çek
        existing_appointments = await db.appointments.find(
            {
            "organization_id": organization_id,
            "staff_member_id": appointment.staff_member_id,
            "appointment_date": appointment.appointment_date,
            "status": {"$ne": "İptal"}
            },
            {"_id": 0, "appointment_time": 1, "service_id": 1}
        ).to_list(100)
        
        # Her randevunun bitiş saatini hesapla ve çakışma kontrolü yap
        has_conflict = False
        for existing_appt in existing_appointments:
            existing_start_time = existing_appt['appointment_time']
            existing_service_id = existing_appt.get('service_id')
            
            # Mevcut randevunun hizmet süresini bul
            if existing_service_id:
                existing_service = await db.services.find_one({"id": existing_service_id}, {"_id": 0, "duration": 1})
                existing_duration = existing_service.get('duration', 30) if existing_service else 30
            else:
                existing_duration = 30
            
            # Mevcut randevunun bitiş saatini hesapla
            existing_start_hour, existing_start_minute = map(int, existing_start_time.split(':'))
            existing_end_minute = existing_start_minute + existing_duration
            existing_end_hour = existing_start_hour + (existing_end_minute // 60)
            existing_end_minute = existing_end_minute % 60
            existing_end_time = f"{str(existing_end_hour).zfill(2)}:{str(existing_end_minute).zfill(2)}"
            
            # Çakışma kontrolü
            if (appointment.appointment_time < existing_end_time and new_end_time > existing_start_time):
                has_conflict = True
                logging.info(f"⚠️ Public booking conflict: New {appointment.appointment_time}-{new_end_time} overlaps with existing {existing_start_time}-{existing_end_time}")
                break
        
        if has_conflict:
            # Kota artırıldı ama personel dolu, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(
                status_code=400,
                detail="Seçtiğiniz personel bu saatte dolu. Lütfen başka bir saat veya personel seçin."
            )
        
        # Mola çakışması kontrolü
        has_break_conflict = await check_break_conflict(
            db, appointment.staff_member_id, appointment.appointment_date,
            appointment.appointment_time, new_end_time, organization_id
        )
        
        if has_break_conflict:
            # Kota artırıldı ama mola çakışması var, geri al
            plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": organization_id},
                    {"$inc": {"quota_usage": -1}}
                )
            raise HTTPException(
                status_code=400,
                detail="Seçtiğiniz personel bu saatte mola. Lütfen başka bir saat veya personel seçin."
            )
        
        assigned_staff_id = appointment.staff_member_id
    else:
        # Müşteri "Farketmez" seçti veya personel seçimi yok
        # Önce customer_can_choose_staff ve admin_provides_service ayarlarını kontrol et
        settings_data = await db.settings.find_one({"organization_id": organization_id})
        customer_can_choose_staff = settings_data.get('customer_can_choose_staff', False) if settings_data else False
        admin_provides_service = settings_data.get('admin_provides_service', True) if settings_data else True
        
        # Eğer customer_can_choose_staff kapalıysa ama admin_provides_service açıksa, otomatik atama yap
        # customer_can_choose_staff açıksa da otomatik atama yap
        # Her ikisi de kapalıysa bile, admin hizmet verebiliyorsa otomatik atama yap
        if not customer_can_choose_staff and not admin_provides_service:
            # Her ikisi de kapalıysa, önce admin'i kontrol et
            admin_user = await db.users.find_one(
                {"organization_id": organization_id, "role": "admin"},
                {"_id": 0, "username": 1, "role": 1, "permitted_service_ids": 1}
            )
            if admin_user and appointment.service_id in (admin_user.get('permitted_service_ids') or []):
                # Çakışma kontrolü — admin'in VE atanmamış randevuları kontrol et
                admin_username = admin_user['username']
                conflict_appts = await db.appointments.find(
                    {
                        "organization_id": organization_id,
                        "$or": [
                            {"staff_member_id": admin_username},
                            {"staff_member_id": None}
                        ],
                        "appointment_date": appointment.appointment_date,
                        "status": {"$ne": "İptal"}
                    },
                    {"_id": 0, "appointment_time": 1, "service_id": 1}
                ).to_list(100)

                has_conflict = False
                for ca in conflict_appts:
                    ca_start = ca.get('appointment_time', '')
                    if not ca_start:
                        continue
                    ca_svc = await db.services.find_one({"id": ca.get('service_id', '')}, {"_id": 0, "duration": 1})
                    ca_dur = ca_svc.get('duration', 30) if ca_svc else 30
                    ca_sh, ca_sm = map(int, ca_start.split(':'))
                    ca_em = ca_sm + ca_dur
                    ca_eh = ca_sh + ca_em // 60
                    ca_em = ca_em % 60
                    ca_end = f"{str(ca_eh).zfill(2)}:{str(ca_em).zfill(2)}"
                    if appointment.appointment_time < ca_end and new_end_time > ca_start:
                        has_conflict = True
                        logging.info(f"⚠️ Public conflict (no-staff-setting): {appointment.appointment_time}-{new_end_time} overlaps {ca_start}-{ca_end}")
                        break

                if has_conflict:
                    plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
                    if plan_doc:
                        await db.organization_plans.update_one(
                            {"organization_id": organization_id},
                            {"$inc": {"quota_usage": -1}}
                        )
                    raise HTTPException(status_code=400, detail="Bu saat dilimi doludur. Lütfen başka bir saat seçin.")

                assigned_staff_id = admin_username
                logging.info(f"ℹ️ customer_can_choose_staff and admin_provides_service are both disabled, but using admin: {admin_username}")
            else:
                # Admin bu hizmeti veremiyorsa, personel atama yapma
                logging.info(f"ℹ️ customer_can_choose_staff and admin_provides_service are both disabled, and admin cannot provide this service")
                assigned_staff_id = None
        else:
            # customer_can_choose_staff açıksa veya admin_provides_service açıksa, otomatik atama yap
            # Bu hizmeti verebilen personelleri bul
            qualified_staff_query = {
                "organization_id": organization_id,
                "permitted_service_ids": {"$in": [appointment.service_id]}
            }
            
            # Admin hizmet vermiyorsa, admin'i listeden çıkar
            if not admin_provides_service:
                qualified_staff_query["role"] = {"$ne": "admin"}
            
            qualified_staff = await db.users.find(
                qualified_staff_query,
                {"_id": 0, "username": 1, "role": 1}
            ).to_list(1000)
            
            # Eğer başka personel yoksa, admin'i personel listesine ekle (admin_provides_service açıksa)
            # (Admin hizmet vermiyor ayarı açık olsa bile, başka personel yoksa admin'i kullanabiliriz)
            if not qualified_staff:
                # Admin'in bu hizmeti verebilip veremediğini kontrol et
                admin_user = await db.users.find_one(
                    {"organization_id": organization_id, "role": "admin"},
                    {"_id": 0, "username": 1, "role": 1, "permitted_service_ids": 1}
                )
                if admin_user and appointment.service_id in (admin_user.get('permitted_service_ids') or []):
                    qualified_staff = [{"username": admin_user['username'], "role": "admin"}]
                    logging.info(f"⚠️ Public: No staff found, but admin can provide service. Using admin: {admin_user['username']}")
            
            if not qualified_staff:
                # Kota artırıldı ama personel bulunamadı, geri al
                plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": organization_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Bu hizmet için uygun personel bulunamadı"
                )
            
            # Boş personel bul (duration'a göre çakışma kontrolü ile)
            for staff in qualified_staff:
                # Bu personelin o tarihteki tüm randevularını çek
                # staff_member_id=None (atanmamış) randevuları da dahil et — tek kişilik org'larda çakışma kaçmasın
                existing_appointments = await db.appointments.find(
                    {
                        "organization_id": organization_id,
                        "$or": [
                            {"staff_member_id": staff['username']},
                            {"staff_member_id": None}
                        ],
                        "appointment_date": appointment.appointment_date,
                        "status": {"$ne": "İptal"}
                    },
                    {"_id": 0, "appointment_time": 1, "service_id": 1}
                ).to_list(100)
                
                # Çakışma kontrolü
                has_conflict = False
                for existing_appt in existing_appointments:
                    existing_start_time = existing_appt['appointment_time']
                    existing_service_id = existing_appt.get('service_id')
                    
                    # Mevcut randevunun hizmet süresini bul
                    if existing_service_id:
                        existing_service = await db.services.find_one({"id": existing_service_id}, {"_id": 0, "duration": 1})
                        existing_duration = existing_service.get('duration', 30) if existing_service else 30
                    else:
                        existing_duration = 30
                    
                    # Mevcut randevunun bitiş saatini hesapla
                    existing_start_hour, existing_start_minute = map(int, existing_start_time.split(':'))
                    existing_end_minute = existing_start_minute + existing_duration
                    existing_end_hour = existing_start_hour + (existing_end_minute // 60)
                    existing_end_minute = existing_end_minute % 60
                    existing_end_time = f"{str(existing_end_hour).zfill(2)}:{str(existing_end_minute).zfill(2)}"
                    
                    # Çakışma kontrolü
                    if (appointment.appointment_time < existing_end_time and new_end_time > existing_start_time):
                        has_conflict = True
                        logging.debug(f"   ⚠️ Public: Staff {staff['username']} has conflict: {appointment.appointment_time}-{new_end_time} overlaps with {existing_start_time}-{existing_end_time}")
                        break
                
                # Mola çakışması kontrolü
                has_break_conflict = await check_break_conflict(
                    db, staff['username'], appointment.appointment_date,
                    appointment.appointment_time, new_end_time, organization_id
                )
                
                if not has_conflict and not has_break_conflict:
                    # Bu personel boş ve mola yok!
                    assigned_staff_id = staff['username']
                    logging.info(f"✅ Public booking auto-assigned to {staff['username']} for {appointment.appointment_time}")
                    break
        
        # Eğer ayarlar kapalıysa (customer_can_choose_staff ve admin_provides_service kapalı), 
        # staff_member_id None olarak kaydedilebilir (atama yapılmaz)
        if not assigned_staff_id:
            if not customer_can_choose_staff and not admin_provides_service:
                # Ayarlar kapalıysa, randevuyu staff_member_id None olarak kaydet (atama yapma)
                logging.info(f"ℹ️ Public booking: Settings disabled, saving appointment without staff assignment")
                assigned_staff_id = None  # None olarak kalacak, randevu oluşturulacak
            else:
                # Ayarlar açıksa ama personel bulunamadı, hata ver
                plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": organization_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Bu saat dilimi doludur. Lütfen başka bir saat seçin."
                )
    
    # Randevuyu oluştur
    appointment_data = appointment.model_dump()
    appointment_data['service_name'] = service['name']
    appointment_data['service_price'] = service['price']
    appointment_data['service_duration'] = service.get('duration', 30)  # Hizmet süresini ekle
    appointment_data['staff_member_id'] = assigned_staff_id
    appointment_data['source'] = 'public_booking'  # Public booking'den geldiğini işaretle
    
    # Seans paketi desteği: Hizmetin session_count > 1 ise otomatik olarak ilk seans bilgilerini ekle
    service_session_count = service.get('session_count')
    if service_session_count and service_session_count > 1:
        appointment_data['session_group_id'] = str(uuid.uuid4())
        appointment_data['session_number'] = 1
        appointment_data['session_total'] = service_session_count
        appointment_data['payment_status'] = 'paid'
    
    # Randevu durumunu kontrol et (bitiş saatine göre)
    try:
        turkey_tz = ZoneInfo("Europe/Istanbul")
        now = datetime.now(turkey_tz)
        dt_str = f"{appointment.appointment_date} {appointment.appointment_time}"
        naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        appointment_dt = naive_dt.replace(tzinfo=turkey_tz)
        # Randevu bitiş saatini hesapla (başlangıç saati + hizmet süresi)
        service_duration_minutes = service.get('duration', 30)
        completion_threshold = appointment_dt + timedelta(minutes=service_duration_minutes)
        if now >= completion_threshold:
            appointment_data['status'] = 'Tamamlandı'
            appointment_data['completed_at'] = datetime.now(timezone.utc).isoformat()
        else:
            appointment_data['status'] = 'Bekliyor'
    except (ValueError, TypeError) as e:
        logging.warning(f"Public randevu durumu ayarlanırken tarih hatası: {e}")
        appointment_data['status'] = 'Bekliyor'
    
    appointment_obj = Appointment(**appointment_data, organization_id=organization_id)
    doc = appointment_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.appointments.insert_one(doc)
    
    # 🔒 Redis lock'u sil (başarılı randevu — diğer müşteriler beklemek zorunda kalmasın)
    if redis_client and lock_key:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
    
    # 🧹 Cache temizliği (Dashboard + Müşteri listesi güncellensin)
    try:
        mock_user = type('obj', (object,), {'organization_id': organization_id})
        await invalidate_cache(request, "dashboard_stats", mock_user)
        await invalidate_cache(request, "customers_list", mock_user)
        logging.info(f"🧹 Public randevu sonrası admin cache temizlendi: {organization_id}")
    except Exception as e:
        logging.error(f"❌ Public süpürge hatası: {e}")
    # Müşteriyi customers collection'ına ekle (eğer yoksa)
    try:
        # Aynı telefon numarasına sahip müşterileri bul
        customers_with_phone = await db.customers.find(
            {
                "organization_id": organization_id,
                "phone": appointment.phone
            },
            {"_id": 0, "name": 1, "phone": 1}
        ).to_list(100)
        
        # İsim-soyisim kontrolü (büyük-küçük harf duyarsız)
        customer_name_normalized = appointment.customer_name.strip().lower()
        existing_customer = None
        for customer in customers_with_phone:
            if customer.get("name", "").strip().lower() == customer_name_normalized:
                existing_customer = customer
                break
        
        if not existing_customer:
            # Müşteri yoksa ekle
            customer_doc = {
                "id": str(uuid.uuid4()),
                "organization_id": organization_id,
                "name": appointment.customer_name.strip(),
                "phone": appointment.phone,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": ""
            }
            await db.customers.insert_one(customer_doc)
            logging.info(f"Customer auto-added from public booking: {appointment.customer_name} ({appointment.phone}) for org {organization_id}")
            
            # Cache invalidation SONRASI müşteri eklendi — tekrar temizle (race condition fix)
            try:
                mock_user = type('obj', (object,), {'organization_id': organization_id})
                await invalidate_cache(request, "customers_list", mock_user)
            except Exception:
                pass
            
            # WebSocket event gönder (müşteriler listesini güncellemek için)
            try:
                await emit_to_organization(
                    organization_id,
                    'customer_added',
                    {'customer': customer_doc}
                )
            except Exception as emit_error:
                logging.warning(f"Failed to emit customer_added event: {emit_error}")
    except Exception as e:
        logging.warning(f"Error adding customer to collection: {e}")
    
    # WhatsApp ve Push Notification'ları background'da gönder (kullanıcıyı bekletmemek için)
    settings_data = await db.settings.find_one({"organization_id": organization_id})
    
    async def send_notifications_background():
        """Tüm bildirimleri background'da gönder"""
        try:
            if settings_data:
                company_name = settings_data.get("company_name", "İşletmeniz")
                support_phone = settings_data.get("support_phone", "Destek Hattı")
                business = settings_data or {}
                settings = business.get('settings') if isinstance(business.get('settings'), dict) else business
                location = (settings or {}).get('location') or {}
                coordinates = (location or {}).get('coordinates', {})
                lat = coordinates.get('lat')
                lng = coordinates.get('lng')
                
                # WhatsApp onay mesajı gönder (Content API)
                try:
                    _wa_msg_id = await asyncio.to_thread(
                        send_whatsapp_template,
                        appointment.phone,
                        "CONFIRMATION",
                        appointment.customer_name,
                        company_name,
                        appointment.appointment_date,
                        appointment.appointment_time,
                        service['name'],
                        support_phone,
                        business_lat=lat,
                        business_lng=lng,
                        business_address=location.get('address'),
                    )
                    logging.info(f"✓ WhatsApp confirmation sent to {appointment.phone}")
                    try:
                        import time as _time
                        _phone = str(appointment.phone).lstrip('+')
                        await db.whatsapp_message_logs.update_one(
                            {"message_id": _wa_msg_id},
                            {"$set": {
                                "message_id": _wa_msg_id,
                                "recipient": _phone,
                                "status": "sent",
                                "timestamp": int(_time.time()),
                                "recorded_at": datetime.utcnow().isoformat(),
                                "source": "public_booking"
                            }},
                            upsert=True
                        )
                    except Exception:
                        pass
                except Exception as wa_error:
                    logging.error(f"WhatsApp error: {wa_error}")
                    try:
                        import time as _time
                        _phone = str(appointment.phone).lstrip('+')
                        await db.whatsapp_message_logs.update_one(
                            {"message_id": f"fail_{_phone}_{int(_time.time())}"},
                            {"$set": {
                                "recipient": _phone,
                                "status": "failed",
                                "timestamp": int(_time.time()),
                                "recorded_at": datetime.utcnow().isoformat(),
                                "errors": [{"code": "SEND_ERROR", "title": str(wa_error)[:300]}],
                                "source": "public_booking"
                            }},
                            upsert=True
                        )
                    except Exception:
                        pass
            
            # Push notification gönder (admin ve ilgili personele)
            try:
                service_info = service.get('name', 'Randevu')
                notification_data = {
                    "type": "new_appointment",
                    "appointment_id": appointment_for_emit.get('id'),
                    "source": "public_booking"
                }
                # Tarih formatını dd.mm.yyyy olarak ayarla
                try:
                    date_parts = appointment.appointment_date.split('-')
                    formatted_date = f"{date_parts[2]}.{date_parts[1]}.{date_parts[0]}"
                except:
                    formatted_date = appointment.appointment_date
                    
                notification_body = f"{appointment.customer_name} - {service_info} ({formatted_date} {appointment.appointment_time})"
                
                # Admin'lere bildirim gönder
                admins = await db.users.find({"organization_id": organization_id, "role": "admin"}).to_list(100)
                for admin in admins:
                    await send_push_notification(
                        db=db,
                        organization_id=organization_id,
                        title="🔔 Yeni Online Randevu!",
                        body=notification_body,
                        data=notification_data,
                        user_id=admin['username']
                    )
                
                # Atanan personele bildirim gönder (admin değilse)
                if assigned_staff_id:
                    staff = await db.users.find_one({"username": assigned_staff_id, "organization_id": organization_id})
                    if staff and staff.get('role') != 'admin':
                        await send_push_notification(
                            db=db,
                            organization_id=organization_id,
                            title="🔔 Yeni Randevu Atandı!",
                            body=notification_body,
                            data=notification_data,
                            user_id=assigned_staff_id
                        )
                logging.info(f"✓ Push notifications sent for appointment {appointment_for_emit.get('id')}")
            except Exception as push_error:
                logging.error(f"Push notification error: {push_error}")
        except Exception as e:
            logging.error(f"Background notification error: {e}")
    
    # Emit WebSocket event for real-time update (bu hızlı, bekletmez)
    appointment_for_emit = appointment_obj.model_dump()
    appointment_for_emit['created_at'] = appointment_for_emit['created_at'].isoformat()
    logger.info(f"About to emit appointment_created for org: {organization_id} (public endpoint)")
    try:
        await emit_to_organization(
            organization_id,
            'appointment_created',
            {'appointment': appointment_for_emit}
        )
        logger.info(f"Successfully emitted appointment_created for org: {organization_id} (public endpoint)")
    except Exception as emit_error:
        logger.error(f"Failed to emit appointment_created (public endpoint): {emit_error}", exc_info=True)
    
    # Background task olarak başlat (kullanıcıyı bekletmez - WhatsApp ve push notification arka planda gönderilir)
    asyncio.create_task(send_notifications_background())
    
    return {"message": "Randevu başarıyla oluşturuldu", "appointment": appointment_obj}


@api_router.get("/public/verify-status")
async def check_verification_status(code: str, request: Request):
    """WhatsApp doğrulama durumunu sorgula (frontend 3sn polling)"""
    redis_client = getattr(request.app.state, 'redis_client', None)
    if not redis_client:
        raise HTTPException(status_code=503, detail="Servis geçici olarak kullanılamıyor.")

    # Webhook tarafından tamamlandı mı? (5 dk TTL flag)
    is_verified = await redis_client.get(f"plann:verified:{code}")
    if is_verified:
        return {"status": "verified", "message": "Doğrulama tamamlandı, randevunuz oluşturuldu."}

    # Pending kayıt hala var mı?
    exists = await redis_client.exists(f"plann:pending:{code}")
    if exists:
        return {"status": "pending", "message": "Doğrulama bekleniyor."}

    # Kod yok ve verified da değil → süresi dolmuş
    return {"status": "expired", "message": "Doğrulama kodunun süresi doldu. Lütfen tekrar deneyin."}


# === SUPER ADMIN ENDPOINT'LERİ ===
@api_router.get("/superadmin/stats")
async def get_superadmin_stats(request: Request, current_user: UserInDB = Depends(get_superadmin_user), db = Depends(get_db)):
    """Platform özeti - Sadece superadmin"""
    try:
        now = datetime.now(timezone.utc)
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Bu ayın son gününü hesapla
        if now.month == 12:
            last_day_of_month = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_month = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
        last_day_of_month = last_day_of_month.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        first_day_str = first_day_of_month.strftime("%Y-%m-%d")
        last_day_str = last_day_of_month.strftime("%Y-%m-%d")
        
        # 1. Toplam İşletme Sayısı (Settings koleksiyonundan unique organization_id sayısı)
        total_organizations = await db.settings.count_documents({})
        
        # 2. Bu Ayki Toplam Abonelik Geliri (organization_plans'den aktif planların toplamı)
        # Trial hariç, aktif planların aylık fiyatlarını topla
        active_plans = await db.organization_plans.find({}).to_list(10000)
        total_monthly_revenue = 0.0
        
        for plan in active_plans:
            plan_id = plan.get('plan_id', 'tier_trial')
            # Trial paketleri gelir sayılmaz
            if plan_id != 'tier_trial':
                plan_info = next((p for p in PLANS if p['id'] == plan_id), None)
                if plan_info:
                    # Trial bitiş tarihi kontrolü - eğer trial bitmişse ve plan aktifse
                    trial_end = plan.get('trial_end_date')
                    if trial_end:
                        if isinstance(trial_end, str):
                            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
                        # Trial bitmişse plan fiyatını ekle
                        if trial_end < now:
                            total_monthly_revenue += plan_info.get('price_monthly', 0)
                    else:
                        # Trial yoksa direkt fiyatı ekle
                        total_monthly_revenue += plan_info.get('price_monthly', 0)
        
        # 3. Bu Ayki Toplam Randevu Sayısı (Tüm organizasyonların appointments'ları)
        total_appointments_this_month = await db.appointments.count_documents({
            "appointment_date": {"$gte": first_day_str, "$lte": last_day_str}
        })
        
        # 4. Toplam Aktif Kullanıcı (Customers + Personnel/Users)
        total_customers = await db.customers.count_documents({})
        total_personnel = await db.users.count_documents({"role": "staff"})
        total_active_users = total_customers + total_personnel
        
        return {
            "toplam_isletme": total_organizations,
            "toplam_gelir_bu_ay": round(total_monthly_revenue, 2),
            "toplam_randevu_bu_ay": total_appointments_this_month,
            "toplam_aktif_kullanici": total_active_users
        }
    except Exception as e:
        logging.error(f"Error in get_superadmin_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"İstatistikler alınırken hata oluştu: {str(e)}")

@api_router.get("/superadmin/contact-requests")
async def get_superadmin_contact_requests(request: Request, current_user: UserInDB = Depends(get_superadmin_user), db = Depends(get_db)):
    """SuperAdmin için iletişim taleplerini getir"""
    try:
        contacts = await db.contact_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return {"contacts": contacts}
    except Exception as e:
        logging.error(f"Error in get_superadmin_contact_requests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Veriler yüklenirken hata oluştu")

@api_router.put("/superadmin/contact-requests/{contact_id}/status")
async def update_contact_status(
    request: Request,
    contact_id: str,
    status_update: ContactStatusUpdate,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Contact request durumunu güncelle - Sadece superadmin"""
    try:
        # Contact request'i bul
        contact = await db.contact_requests.find_one({"id": contact_id}, {"_id": 0})
        if not contact:
            raise HTTPException(status_code=404, detail="İletişim talebi bulunamadı")
        
        # Durumu güncelle
        await db.contact_requests.update_one(
            {"id": contact_id},
            {"$set": {"status": status_update.status}}
        )
        
        logging.info(f"✅ [SUPERADMIN] Contact request {contact_id} durumu güncellendi: {status_update.status}")
        
        # Güncellenmiş contact request'i döndür
        updated_contact = await db.contact_requests.find_one({"id": contact_id}, {"_id": 0})
        return {"success": True, "contact": updated_contact}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ [SUPERADMIN] Contact request durumu güncellenirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Durum güncellenirken hata oluştu")

@api_router.delete("/superadmin/contact-requests/{contact_id}")
async def delete_contact_request(
    request: Request,
    contact_id: str,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Contact request'i sil - Sadece superadmin"""
    try:
        # Contact request'i bul
        contact = await db.contact_requests.find_one({"id": contact_id}, {"_id": 0})
        if not contact:
            raise HTTPException(status_code=404, detail="İletişim talebi bulunamadı")
        
        # Contact request'i sil
        await db.contact_requests.delete_one({"id": contact_id})
        
        logging.info(f"✅ [SUPERADMIN] Contact request silindi: {contact_id}")
        
        return {"success": True, "message": "İletişim talebi silindi"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ [SUPERADMIN] Contact request silinirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="İletişim talebi silinirken hata oluştu")

@api_router.delete("/superadmin/contact-requests/bulk/delete-resolved")
async def delete_resolved_contacts(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Çözülen (resolved) contact request'leri toplu sil - Sadece superadmin"""
    try:
        # Resolved status'lu contact request'leri bul ve sil
        result = await db.contact_requests.delete_many({"status": "resolved"})
        
        deleted_count = result.deleted_count
        logging.info(f"✅ [SUPERADMIN] {deleted_count} adet çözülen iletişim talebi silindi")
        
        return {"success": True, "deleted_count": deleted_count, "message": f"{deleted_count} adet çözülen iletişim talebi silindi"}
    except Exception as e:
        logging.error(f"❌ [SUPERADMIN] Çözülen iletişim talepleri silinirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Çözülen iletişim talepleri silinirken hata oluştu")

@api_router.get("/superadmin/organizations")
async def get_superadmin_organizations(request: Request, current_user: UserInDB = Depends(get_superadmin_user), db = Depends(get_db)):
    """Detaylı işletme listesi - Sadece superadmin"""
    try:
        now = datetime.now(timezone.utc)
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if now.month == 12:
            last_day_of_month = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_month = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
        last_day_of_month = last_day_of_month.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        first_day_str = first_day_of_month.strftime("%Y-%m-%d")
        last_day_str = last_day_of_month.strftime("%Y-%m-%d")
        
        all_settings = await db.settings.find({}).to_list(10000)
        organizations_list = []
        
        for setting in all_settings:
            org_id = setting.get('organization_id')
            if not org_id:
                continue
            
            isletme_adi = setting.get('company_name', 'İsimsiz İşletme')
            telefon_numarasi = setting.get('support_phone', 'Telefon Yok')
            
            # Admin kullanıcıyı bul (işletme sahibi)
            admin_user = await db.users.find_one({"organization_id": org_id, "role": "admin"})
            admin_full_name = admin_user.get('full_name', '-') if admin_user else '-'
            admin_email = admin_user.get('username', '-') if admin_user else '-'
            
            # Abonelik bilgileri
            plan_doc = await db.organization_plans.find_one({"organization_id": org_id})
            billing_cycle = 'monthly'
            days_left = None
            toplam_odeme = 0
            
            if not plan_doc:
                abonelik_paketi = "Trial"
                plan_id = 'tier_trial'
                abonelik_durumu = "Kayıt Yok"
            else:
                plan_id = plan_doc.get('plan_id', 'tier_trial')
                plan_info = next((p for p in PLANS if p['id'] == plan_id), None)
                abonelik_paketi = plan_info.get('name', 'Trial') if plan_info else 'Trial'
                billing_cycle = plan_doc.get('billing_cycle', 'monthly')
                
                # Kalan gün hesapla
                if plan_id == 'tier_trial':
                    trial_end = plan_doc.get('trial_end_date')
                    if trial_end:
                        if isinstance(trial_end, str):
                            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
                        days_left = (trial_end - now).days
                        if days_left < 0:
                            abonelik_durumu = "Deneme Bitti"
                        else:
                            abonelik_durumu = f"{days_left} Gün Kaldı"
                    else:
                        abonelik_durumu = "Trial"
                else:
                    # Ücretli paket - quota_reset_date'e bak
                    quota_reset = plan_doc.get('quota_reset_date')
                    if quota_reset:
                        if isinstance(quota_reset, str):
                            quota_reset = datetime.fromisoformat(quota_reset.replace('Z', '+00:00'))
                        days_left = (quota_reset - now).days
                        abonelik_durumu = f"{days_left} Gün Kaldı" if days_left >= 0 else "Yenileme Bekliyor"
                    else:
                        abonelik_durumu = "Aktif"
                        days_left = 30
            
            # Toplam ödeme miktarı
            payment_logs = await db.payment_logs.find({
                "organization_id": org_id,
                "status": {"$in": ["active", "completed"]}
            }).to_list(1000)
            toplam_odeme = sum(log.get('amount', 0) for log in payment_logs)
            
            # Bu ayki randevu sayısı
            bu_ayki_randevu_sayisi = await db.appointments.count_documents({
                "organization_id": org_id,
                "appointment_date": {"$gte": first_day_str, "$lte": last_day_str}
            })
            
            # Toplam müşteri sayısı
            toplam_musteri_sayisi = await db.customers.count_documents({"organization_id": org_id})
            
            # Toplam personel sayısı
            toplam_personel_sayisi = await db.users.count_documents({"organization_id": org_id, "role": "staff"})
            
            organizations_list.append({
                "organization_id": org_id,
                "isletme_adi": isletme_adi,
                "telefon_numarasi": telefon_numarasi,
                "admin_full_name": admin_full_name,
                "admin_email": admin_email,
                "plan_id": plan_id,
                "abonelik_paketi": abonelik_paketi,
                "billing_cycle": billing_cycle,
                "abonelik_durumu": abonelik_durumu,
                "days_left": days_left,
                "toplam_odeme": toplam_odeme,
                "bu_ayki_randevu_sayisi": bu_ayki_randevu_sayisi,
                "toplam_musteri_sayisi": toplam_musteri_sayisi,
                "toplam_personel_sayisi": toplam_personel_sayisi
            })
        
        return {"organizations": organizations_list}
    except Exception as e:
        logging.error(f"Error in get_superadmin_organizations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"İşletme listesi alınırken hata oluştu: {str(e)}")

@api_router.post("/superadmin/organizations/{org_id}/assign-plan")
async def assign_plan_to_organization(
    org_id: str,
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """İşletmeye paket ata - Sadece superadmin"""
    try:
        body = await request.json()
        plan_id = body.get('plan_id')
        billing_cycle = body.get('billing_cycle', 'monthly')
        
        if not plan_id:
            raise HTTPException(status_code=400, detail="Plan ID gerekli")
        
        plan_info = next((p for p in PLANS if p['id'] == plan_id), None)
        if not plan_info:
            raise HTTPException(status_code=400, detail="Geçersiz plan ID")
        
        now = datetime.now(timezone.utc)
        
        if plan_id == 'tier_trial':
            # Trial paketi ata
            trial_end = now + timedelta(days=7)
            update_data = {
                "organization_id": org_id,
                "plan_id": plan_id,
                "quota_usage": 0,
                "billing_cycle": "monthly",
                "trial_start_date": now.isoformat(),
                "trial_end_date": trial_end.isoformat(),
                "quota_reset_date": trial_end.isoformat(),
                "updated_at": now.isoformat()
            }
        else:
            # Ücretli paket ata
            if billing_cycle == 'yearly':
                quota_reset = now + timedelta(days=365)
            else:
                quota_reset = now + timedelta(days=30)
            
            update_data = {
                "organization_id": org_id,
                "plan_id": plan_id,
                "quota_usage": 0,
                "billing_cycle": billing_cycle,
                "trial_start_date": None,
                "trial_end_date": None,
                "quota_reset_date": quota_reset.isoformat(),
                "updated_at": now.isoformat()
            }
        
        await db.organization_plans.update_one(
            {"organization_id": org_id},
            {"$set": update_data},
            upsert=True
        )
        
        logger.info(f"SuperAdmin paket atadı: org={org_id}, plan={plan_id}, cycle={billing_cycle}")
        return {"message": f"Paket başarıyla atandı: {plan_info.get('name')}", "plan_id": plan_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in assign_plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Paket atanırken hata: {str(e)}")

@api_router.delete("/superadmin/organizations/{org_id}")
async def delete_organization(
    org_id: str,
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """İşletmeyi tamamen sil - Sadece superadmin"""
    try:
        # Tüm ilgili verileri sil
        await db.users.delete_many({"organization_id": org_id})
        await db.appointments.delete_many({"organization_id": org_id})
        await db.customers.delete_many({"organization_id": org_id})
        await db.services.delete_many({"organization_id": org_id})
        await db.transactions.delete_many({"organization_id": org_id})
        await db.expenses.delete_many({"organization_id": org_id})
        await db.settings.delete_one({"organization_id": org_id})
        await db.organization_plans.delete_one({"organization_id": org_id})
        await db.audit_logs.delete_many({"organization_id": org_id})
        await db.customer_notes.delete_many({"organization_id": org_id})
        await db.payment_logs.delete_many({"organization_id": org_id})
        
        logger.info(f"SuperAdmin işletmeyi sildi: org={org_id}")
        return {"message": "İşletme ve tüm verileri silindi"}
    
    except Exception as e:
        logging.error(f"Error in delete_organization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"İşletme silinirken hata: {str(e)}")

@api_router.delete("/superadmin/organizations/{org_id}/staff/{user_id}")
async def delete_staff_member(
    org_id: str,
    user_id: str,
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Personeli sil - Sadece superadmin"""
    try:
        # Personeli kontrol et
        user = await db.users.find_one({"id": user_id, "organization_id": org_id, "role": "staff"})
        if not user:
            raise HTTPException(status_code=404, detail="Personel bulunamadı")
        
        await db.users.delete_one({"id": user_id})
        
        logger.info(f"SuperAdmin personeli sildi: user={user_id}, org={org_id}")
        return {"message": "Personel silindi"}
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in delete_staff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Personel silinirken hata: {str(e)}")

@api_router.get("/superadmin/organizations/{org_id}/staff")
async def get_organization_staff(
    org_id: str,
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """İşletmenin personel listesi - Sadece superadmin"""
    try:
        staff_list = await db.users.find(
            {"organization_id": org_id, "role": "staff"},
            {"_id": 0, "id": 1, "full_name": 1, "username": 1, "status": 1}
        ).to_list(1000)
        
        return {"staff": staff_list}
    
    except Exception as e:
        logging.error(f"Error in get_staff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Personel listesi alınırken hata: {str(e)}")

@api_router.get("/superadmin/plans")
async def get_available_plans(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user)
):
    """Mevcut planları getir - Sadece superadmin"""
    return {"plans": PLANS}

@api_router.get("/superadmin/whatsapp-logs")
async def get_whatsapp_message_logs(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db),
    status_filter: Optional[str] = None,   # ?status_filter=failed
    limit: int = 200,
    skip: int = 0,
):
    """
    WhatsApp mesaj durum logları - Sadece superadmin.
    Kaydedilen alanlar: message_id, recipient, status (sent/delivered/read/failed),
    timestamp (Unix), errors (failed durumunda), recorded_at.
    """
    try:
        query = {}
        if status_filter:
            query["status"] = status_filter

        logs = await db.whatsapp_message_logs.find(
            query, {"_id": 0}
        ).sort("recorded_at", -1).skip(skip).limit(limit).to_list(limit)

        total = await db.whatsapp_message_logs.count_documents(query)

        failed_count    = await db.whatsapp_message_logs.count_documents({"status": "failed"})
        delivered_count = await db.whatsapp_message_logs.count_documents({"status": "delivered"})
        read_count      = await db.whatsapp_message_logs.count_documents({"status": "read"})
        sent_count      = await db.whatsapp_message_logs.count_documents({"status": "sent"})

        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit,
            "summary": {
                "sent":      sent_count,
                "delivered": delivered_count,
                "read":      read_count,
                "failed":    failed_count,
            },
        }
    except Exception as e:
        logging.error(f"Error in get_whatsapp_message_logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="WhatsApp logları alınırken hata oluştu")

# === SUPERADMIN FINANCIAL STATS ===
@api_router.get("/superadmin/financial-stats")
async def get_financial_stats(request: Request, current_user: UserInDB = Depends(get_superadmin_user), db = Depends(get_db)):
    """SaaS finansal özet: MRR, Toplam Ciro, Aktif İşletme, Churn"""
    try:
        now = datetime.now(timezone.utc)
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = now - timedelta(days=30)

        # Tüm org plan kayıtları
        all_plans = await db.organization_plans.find({}, {"_id": 0}).to_list(10000)
        active_plans = [p for p in all_plans if p.get("status") == "active"]

        # MRR hesabı
        plan_prices = {p["id"]: p.get("price_monthly", 0) for p in PLANS}
        mrr = 0
        for p in active_plans:
            pid = p.get("plan_id", "")
            cycle = p.get("billing_cycle", "monthly")
            price = plan_prices.get(pid, 0)
            if cycle == "yearly":
                mrr += price  # zaten aylık fiyat
            else:
                mrr += price

        # Toplam ciro (tüm zamanlar — payment_history)
        all_payments = await db.payment_history.find({}, {"_id": 0, "amount": 1}).to_list(100000)
        total_revenue = sum(p.get("amount", 0) for p in all_payments)

        # Aktif işletme sayısı
        active_count = len(active_plans)

        # Churn: son 30 günde süresi dolmuş / iptal edilmiş
        churn_count = await db.organization_plans.count_documents({
            "status": {"$in": ["expired", "cancelled"]},
            "updated_at": {"$gte": thirty_days_ago.isoformat()}
        })

        # Bu ay yeni kayıtlar
        new_this_month = await db.users.count_documents({
            "role": "admin",
            "created_at": {"$gte": first_day.isoformat()}
        })

        # WhatsApp başarı oranı (son 7 gün)
        seven_days_ago = now - timedelta(days=7)
        wa_total = await db.whatsapp_message_logs.count_documents({
            "recorded_at": {"$gte": seven_days_ago.isoformat()}
        })
        wa_success = await db.whatsapp_message_logs.count_documents({
            "status": {"$in": ["delivered", "read"]},
            "recorded_at": {"$gte": seven_days_ago.isoformat()}
        })
        wa_success_rate = round((wa_success / wa_total * 100) if wa_total > 0 else 0, 1)

        # Toplam randevu bu ay
        total_appointments_month = await db.appointments.count_documents({
            "created_at": {"$gte": first_day.isoformat()}
        })

        return {
            "mrr": mrr,
            "total_revenue": total_revenue,
            "active_businesses": active_count,
            "churn_last_30d": churn_count,
            "new_registrations_this_month": new_this_month,
            "wa_success_rate": wa_success_rate,
            "total_appointments_this_month": total_appointments_month,
        }
    except Exception as e:
        logging.error(f"Error in get_financial_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Finansal istatistikler alınamadı")


# === SUPERADMIN — MARKETING KULLANICI YÖNETİMİ ===
class MarketingUserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None

@api_router.post("/superadmin/users/marketing")
async def create_marketing_user(
    request: Request,
    user_data: MarketingUserCreate,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Marketing kullanıcısı oluştur - Sadece superadmin"""
    existing = await db.users.find_one({"username": user_data.username.lower().strip()})
    if existing:
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanılıyor")
    hashed = pwd_context.hash(user_data.password)
    new_user = {
        "id": str(uuid.uuid4()),
        "username": user_data.username.lower().strip(),
        "full_name": user_data.full_name or user_data.username,
        "role": "marketing",
        "organization_id": "global",
        "hashed_password": hashed,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)
    new_user.pop("hashed_password", None)
    new_user.pop("_id", None)
    logging.info(f"Marketing kullanıcısı oluşturuldu: {new_user['username']}")
    return {"message": "Marketing kullanıcısı oluşturuldu", "user": new_user}

@api_router.get("/superadmin/users/marketing")
async def list_marketing_users(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Marketing kullanıcılarını listele"""
    users = await db.users.find({"role": "marketing"}, {"_id": 0, "hashed_password": 0}).to_list(500)
    return {"users": users}

@api_router.delete("/superadmin/users/marketing/{user_id}")
async def delete_marketing_user(
    request: Request,
    user_id: str,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Marketing kullanıcısını sil"""
    result = await db.users.delete_one({"id": user_id, "role": "marketing"})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return {"message": "Kullanıcı silindi"}


# === SUPERADMIN — LEAD YÖNETİMİ ===
LEAD_CLAIM_TIMEOUT_MINUTES = 15

async def _release_expired_claims(db):
    """Süresi dolmuş claim'leri havuza geri at ve sistem logu düş"""
    timeout_dt = datetime.now(timezone.utc) - timedelta(minutes=LEAD_CLAIM_TIMEOUT_MINUTES)
    expired = await db.leads.find({
        "status": "claimed",
        "claimed_at": {"$lt": timeout_dt.isoformat()}
    }, {"_id": 0}).to_list(1000)
    for lead in expired:
        system_log = {
            "action": "timeout_expired",
            "user": lead.get("claimed_by_name", "?"),
            "user_id": lead.get("claimed_by"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": f"15 dakika süre doldu, {lead.get('claimed_by_name', '?')} işlem yapmadan süresi doldu"
        }
        await db.leads.update_one(
            {"id": lead["id"]},
            {"$set": {"status": "pool", "claimed_by": None, "claimed_at": None, "claimed_by_name": None},
             "$push": {"system_logs": system_log}}
        )
    return len(expired)

@api_router.post("/superadmin/leads/upload/preview")
async def preview_lead_upload(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_superadmin_user),
):
    """CSV/XLSX dosyasının sütunlarını ve ilk 5 satırını döndür"""
    try:
        content = await file.read()
        filename = (file.filename or "").lower()
        columns = []
        preview_rows = []

        if filename.endswith(".csv"):
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            columns = list(reader.fieldnames or [])
            for i, row in enumerate(reader):
                if i >= 5:
                    break
                preview_rows.append(dict(row))
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                columns = [str(c) if c is not None else "" for c in rows[0]]
                for row in rows[1:6]:
                    preview_rows.append({columns[i]: (str(row[i]) if row[i] is not None else "") for i in range(len(columns))})
        else:
            raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı. CSV veya XLSX yükleyin.")

        return {"columns": columns, "preview": preview_rows, "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Lead upload preview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dosya okunamadı: {str(e)}")

class LeadUploadConfirm(BaseModel):
    filename: str
    batch_name: str
    company_col: str
    phone_col: str
    file_data: str  # base64 encoded

@api_router.post("/superadmin/leads/upload/confirm")
async def confirm_lead_upload(
    request: Request,
    payload: LeadUploadConfirm,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Column mapping ile lead'leri yükle"""
    try:
        import base64 as b64
        content = b64.b64decode(payload.file_data)
        filename = payload.filename.lower()
        rows = []

        if filename.endswith(".csv"):
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                rows.append(dict(row))
        else:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            if all_rows:
                cols = [str(c) if c is not None else "" for c in all_rows[0]]
                for row in all_rows[1:]:
                    rows.append({cols[i]: (str(row[i]) if row[i] is not None else "") for i in range(len(cols))})

        batch_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        leads_to_insert = []
        skipped = 0
        for row in rows:
            company = str(row.get(payload.company_col, "") or "").strip()
            phone = str(row.get(payload.phone_col, "") or "").strip()
            if not company and not phone:
                skipped += 1
                continue
            leads_to_insert.append({
                "id": str(uuid.uuid4()),
                "batch_id": batch_id,
                "batch_name": payload.batch_name,
                "company_name": company,
                "phone": phone,
                "status": "pool",
                "claimed_by": None,
                "claimed_at": None,
                "claimed_by_name": None,
                "note": "",
                "system_logs": [],
                "uploaded_by": current_user.id,
                "uploaded_by_name": current_user.full_name or current_user.username,
                "created_at": now_iso,
                "updated_at": now_iso,
            })

        if leads_to_insert:
            await db.leads.insert_many(leads_to_insert)

        # Batch kaydı
        await db.lead_batches.insert_one({
            "id": batch_id,
            "batch_name": payload.batch_name,
            "total": len(leads_to_insert),
            "skipped": skipped,
            "uploaded_by": current_user.id,
            "uploaded_by_name": current_user.full_name or current_user.username,
            "created_at": now_iso,
        })
        logging.info(f"Lead upload: {len(leads_to_insert)} lead yüklendi, batch={batch_id}")
        return {"message": f"{len(leads_to_insert)} lead yüklendi", "batch_id": batch_id, "total": len(leads_to_insert), "skipped": skipped}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Lead upload confirm error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Yükleme başarısız: {str(e)}")

@api_router.get("/superadmin/leads")
async def get_all_leads(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db),
    status_filter: Optional[str] = None,
    batch_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Tüm leadleri listele (superadmin)"""
    await _release_expired_claims(db)
    query = {}
    if status_filter:
        query["status"] = status_filter
    if batch_id:
        query["batch_id"] = batch_id
    if assigned_to:
        query["claimed_by"] = assigned_to
    total = await db.leads.count_documents(query)
    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"leads": leads, "total": total}

@api_router.get("/superadmin/leads/stats")
async def get_lead_stats(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Lead dönüşüm istatistikleri"""
    await _release_expired_claims(db)
    total = await db.leads.count_documents({})
    pool = await db.leads.count_documents({"status": "pool"})
    claimed = await db.leads.count_documents({"status": "claimed"})
    interested = await db.leads.count_documents({"status": "interested"})
    unreachable = await db.leads.count_documents({"status": "unreachable"})
    not_interested = await db.leads.count_documents({"status": "not_interested"})
    waiting = await db.leads.count_documents({"status": "waiting"})
    registered = await db.leads.count_documents({"status": "registered"})
    called = total - pool
    conversion_rate = round((registered / called * 100) if called > 0 else 0, 1)
    return {
        "total": total, "pool": pool, "claimed": claimed,
        "interested": interested, "unreachable": unreachable,
        "not_interested": not_interested, "waiting": waiting,
        "registered": registered, "called": called,
        "conversion_rate": conversion_rate
    }

@api_router.get("/superadmin/leads/batches")
async def get_lead_batches(
    request: Request,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Yükleme geçmişi"""
    batches = await db.lead_batches.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"batches": batches}

@api_router.delete("/superadmin/leads/batch/{batch_id}")
async def delete_lead_batch(
    request: Request,
    batch_id: str,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    """Yükleme grubunu ve tüm leadlerini sil"""
    result = await db.leads.delete_many({"batch_id": batch_id})
    await db.lead_batches.delete_one({"id": batch_id})
    return {"message": f"{result.deleted_count} lead silindi"}

@api_router.delete("/superadmin/leads/{lead_id}")
async def delete_single_lead(
    request: Request,
    lead_id: str,
    current_user: UserInDB = Depends(get_superadmin_user),
    db = Depends(get_db)
):
    await db.leads.delete_one({"id": lead_id})
    return {"message": "Lead silindi"}


# === MARKETING — TELE-SATIŞ CRM ===
@api_router.get("/marketing/leads")
async def get_marketing_leads(
    request: Request,
    current_user: UserInDB = Depends(get_marketing_user),
    db = Depends(get_db),
    tab: str = "pool"  # "pool" | "mine"
):
    """Havuz leadleri veya benim leadlerim"""
    await _release_expired_claims(db)
    if tab == "mine":
        query = {"claimed_by": current_user.id, "status": {"$in": ["claimed", "interested", "unreachable", "not_interested", "waiting", "registered"]}}
        leads = await db.leads.find(query, {"_id": 0}).sort("updated_at", -1).to_list(500)
    else:
        query = {"status": "pool"}
        leads = await db.leads.find(query, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"leads": leads}

@api_router.post("/marketing/leads/{lead_id}/claim")
async def claim_lead(
    request: Request,
    lead_id: str,
    current_user: UserInDB = Depends(get_marketing_user),
    db = Depends(get_db)
):
    """Lead'i al (15dk kilit)"""
    await _release_expired_claims(db)
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead bulunamadı")
    if lead["status"] != "pool":
        raise HTTPException(status_code=409, detail="Bu lead başka biri tarafından alınmış")
    now = datetime.now(timezone.utc).isoformat()
    system_log = {
        "action": "claimed",
        "user": current_user.full_name or current_user.username,
        "user_id": current_user.id,
        "timestamp": now,
        "note": ""
    }
    await db.leads.update_one(
        {"id": lead_id, "status": "pool"},
        {"$set": {
            "status": "claimed",
            "claimed_by": current_user.id,
            "claimed_by_name": current_user.full_name or current_user.username,
            "claimed_at": now,
            "updated_at": now,
        }, "$push": {"system_logs": system_log}}
    )
    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not updated or updated.get("claimed_by") != current_user.id:
        raise HTTPException(status_code=409, detail="Lead başka biri tarafından alındı")
    return {"message": "Lead alındı", "lead": updated}

@api_router.put("/marketing/leads/{lead_id}/status")
async def update_lead_status(
    request: Request,
    lead_id: str,
    current_user: UserInDB = Depends(get_marketing_user),
    db = Depends(get_db)
):
    """Lead durumunu güncelle"""
    body = await request.json()
    new_status = body.get("status")
    note = body.get("note", "").strip()
    valid_statuses = ["interested", "unreachable", "not_interested", "waiting", "registered"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Geçersiz durum")
    if new_status in ["not_interested", "waiting"] and not note:
        raise HTTPException(status_code=400, detail="Bu durum için not zorunludur")
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead bulunamadı")
    if lead.get("claimed_by") != current_user.id:
        raise HTTPException(status_code=403, detail="Bu lead size ait değil")
    now = datetime.now(timezone.utc).isoformat()
    system_log = {
        "action": f"status_updated_{new_status}",
        "user": current_user.full_name or current_user.username,
        "user_id": current_user.id,
        "timestamp": now,
        "note": note
    }
    update_data = {
        "status": new_status,
        "note": note,
        "updated_at": now,
        "claimed_by": None,
        "claimed_at": None,
        "claimed_by_name": None,
    }
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": update_data, "$push": {"system_logs": system_log}}
    )
    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return {"message": "Durum güncellendi", "lead": updated}

@api_router.post("/marketing/leads/{lead_id}/release")
async def release_lead(
    request: Request,
    lead_id: str,
    current_user: UserInDB = Depends(get_marketing_user),
    db = Depends(get_db)
):
    """Lead'i havuza geri bırak"""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead bulunamadı")
    if lead.get("claimed_by") != current_user.id:
        raise HTTPException(status_code=403, detail="Bu lead size ait değil")
    now = datetime.now(timezone.utc).isoformat()
    system_log = {
        "action": "manual_release",
        "user": current_user.full_name or current_user.username,
        "user_id": current_user.id,
        "timestamp": now,
        "note": "Manuel bırakıldı"
    }
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"status": "pool", "claimed_by": None, "claimed_at": None, "claimed_by_name": None, "updated_at": now},
         "$push": {"system_logs": system_log}}
    )
    return {"message": "Lead havuza bırakıldı"}

@api_router.get("/marketing/my-stats")
async def get_my_marketing_stats(
    request: Request,
    current_user: UserInDB = Depends(get_marketing_user),
    db = Depends(get_db)
):
    """Pazarlamacının kendi istatistikleri"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    total_called = await db.leads.count_documents({"claimed_by": current_user.id, "status": {"$nin": ["pool", "claimed"]}})
    interested = await db.leads.count_documents({"claimed_by": current_user.id, "status": "interested"})
    registered = await db.leads.count_documents({"claimed_by": current_user.id, "status": "registered"})
    # Bugün güncellenenler (yaklaşık)
    today_leads = await db.leads.count_documents({
        "claimed_by": current_user.id,
        "updated_at": {"$gte": today_start}
    })
    conversion = round((registered / total_called * 100) if total_called > 0 else 0, 1)
    return {
        "total_called": total_called,
        "today_called": today_leads,
        "interested": interested,
        "registered": registered,
        "conversion_rate": conversion
    }

@api_router.get("/marketing/profile")
async def get_marketing_profile(
    request: Request,
    current_user: UserInDB = Depends(get_marketing_user),
):
    """Marketing kullanıcısının profil bilgileri"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }


# === AI CHATBOT ENDPOINT ===
class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict]] = []
    language: Optional[str] = "tr"

@api_router.post("/ai/chat")
@rate_limit(LIMITS["ai_chat"])
async def ai_chat_endpoint(
    body: AIChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    AI Chatbot endpoint - Gemini 2.5 Flash ile sohbet
    
    Request body:
    {
        "message": "Kullanıcının mesajı",
        "history": [  // Opsiyonel chat history
            {"role": "user", "parts": [{"text": "..."}]},
            {"role": "model", "parts": [{"text": "..."}]}
        ]
    }
    """
    try:
        # current_user is UserInDB Pydantic model, not dict
        user_role = getattr(current_user, 'role', 'staff')
        username = current_user.username
        organization_id = current_user.organization_id
        user_full_name = getattr(current_user, 'full_name', username) or username
        
        # AI MESAJ KOTA KONTROLÜ
        plan_doc = await db.organization_plans.find_one({"organization_id": organization_id})
        if not plan_doc:
            # Plan yoksa default trial oluştur
            plan_doc = {
                "organization_id": organization_id,
                "plan_id": "tier_trial",
                "quota_usage": 0,
                "ai_usage_count": 0,
                "quota_reset_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.organization_plans.insert_one(plan_doc)
        
        # Plan limitini al
        plan_id = plan_doc.get('plan_id', 'tier_trial')
        plan_info = next((p for p in PLANS if p['id'] == plan_id), None)
        
        if not plan_info:
            raise HTTPException(status_code=500, detail="Plan bilgisi bulunamadı")
        
        ai_message_limit = plan_info.get('ai_message_limit', 100)
        current_ai_usage = plan_doc.get('ai_usage_count', 0)
        
        # Limit kontrolü (Sınırsız değilse)
        if ai_message_limit != -1 and current_ai_usage >= ai_message_limit:
            raise HTTPException(
                status_code=403,
                detail=f"Aylık AI kullanım limitiniz doldu ({ai_message_limit} mesaj). Kesintisiz hizmet için paketinizi yükseltin."
            )
        
        # Organizasyon bilgisini al
        settings = await db.settings.find_one({"organization_id": organization_id})
        organization_name = settings.get('company_name', 'İşletme') if settings else 'İşletme'
        
        # AI ile sohbet et
        result = await chat_with_ai(
            db=db,
            user_message=body.message,
            chat_history=body.history,
            user_role=user_role,
            username=username,
            organization_id=organization_id,
            organization_name=organization_name,
            language=body.language or "tr",
            can_view_all_appointments=getattr(current_user, 'can_view_all_appointments', False)
        )
        
        if not result.get('success'):
            status_code = int(result.get('status', 500))
            detail_msg = result.get('message', 'AI hatası')
            raise HTTPException(status_code=status_code, detail=detail_msg)
        
        # Başarılı mesaj - Kullanımı artır
        await db.organization_plans.update_one(
            {"organization_id": organization_id},
            {"$inc": {"ai_usage_count": 1}}
        )
        
        # Güncel kullanım bilgisini al
        new_usage = current_ai_usage + 1
        
        return {
            "success": True,
            "message": result.get('message'),
            "history": result.get('history', []),
            "usage_info": {
                "current": new_usage,
                "limit": ai_message_limit
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI sohbet hatası: {str(e)}")

# --- Router prefix'i buraya taşındı ---
app.include_router(api_router, prefix="/api")

# === WhatsApp Webhook (Meta Cloud API) ===

META_WEBHOOK_VERIFY_TOKEN = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "plann_meta_webhook_2025")
_META_WH_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
_META_WH_PHONE_ID = os.getenv("META_PHONE_NUMBER_ID")
_META_WH_API_VERSION = os.getenv("META_API_VERSION", "v21.0")


def _send_whatsapp_text_reply(to_number: str, text: str) -> None:
    """Gelen mesaja düz metin (text) olarak otomatik yanıt gönderir."""
    if not _META_WH_ACCESS_TOKEN or not _META_WH_PHONE_ID:
        logger.warning("Meta WA credentials eksik, auto-reply gönderilemedi.")
        return
    url = f"https://graph.facebook.com/{_META_WH_API_VERSION}/{_META_WH_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    try:
        import requests as _req
        resp = _req.post(
            url,
            headers={"Authorization": f"Bearer {_META_WH_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Auto-reply hata: {resp.status_code} {resp.text}")
        else:
            logger.info(f"Auto-reply gönderildi → {to_number}")
    except Exception as e:
        logger.error(f"Auto-reply exception: {e}")


@app.get("/webhook")
async def whatsapp_webhook_verify(request: Request):
    """
    Meta webhook doğrulama: GET isteğiyle hub.challenge döner.
    """
    params = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == META_WEBHOOK_VERIFY_TOKEN:
        logger.info("✅ Meta webhook doğrulandı.")
        return Response(content=challenge, media_type="text/plain")

    logger.warning(f"❌ Webhook doğrulama başarısız. token={token}")
    raise HTTPException(status_code=403, detail="Webhook doğrulama başarısız.")


@app.get("/api/webhook")
async def whatsapp_webhook_verify_api_app(request: Request):
    return await whatsapp_webhook_verify(request)


@api_router.get("/webhook")
async def whatsapp_webhook_verify_api(request: Request):
    return await whatsapp_webhook_verify(request)


async def _process_whatsapp_verification(db, redis_client, from_wa_number: str, code: str) -> dict:
    """
    Webhook'tan gelen RND kodunu doğrula ve randevuyu oluştur.
    from_wa_number: Meta API'den gelen gönderenin numarası (90XXXXXXXXXX formatı)
    """
    if not redis_client:
        return {"reply": "Sistem geçici olarak kullanılamıyor."}

    pending_key = f"plann:pending:{code}"
    raw = await redis_client.hgetall(pending_key)

    if not raw:
        lang = detect_language_from_phone(from_wa_number)
        if lang == "TR":
            return {"reply": f"❌ '{code}' kodu bulunamadı veya süresi doldu. Lütfen yeniden randevu talebinde bulunun."}
        return {"reply": f"❌ Code '{code}' not found or expired. Please submit a new appointment request."}

    data = {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in raw.items()
    }
    stored_phone = data.get("phone", "")
    org_id = data.get("org_id", "")

    def _norm(p: str) -> str:
        return re.sub(r"\D", "", p).lstrip("0")

    if _norm(from_wa_number)[-9:] != _norm(stored_phone)[-9:]:
        lang = detect_language_from_phone(from_wa_number)
        if lang == "TR":
            return {"reply": "❌ Bu numara randevu formundaki telefon numarasıyla eşleşmiyor. Lütfen randevuyu oluşturduğunuz numara ile mesaj gönderin."}
        return {"reply": "❌ This number does not match the booking form's phone number."}

    try:
        apt_dict = json.loads(data.get("appointment_data", "{}"))
    except Exception:
        return {"reply": "❌ Randevu verisi işlenirken hata oluştu."}

    try:
        quota_ok, quota_error = await check_quota_and_increment(db, org_id)
        if not quota_ok:
            return {"reply": f"❌ {quota_error}"}

        service = await db.services.find_one({"id": apt_dict.get("service_id")}, {"_id": 0})
        if not service:
            await db.organization_plans.update_one(
                {"organization_id": org_id}, {"$inc": {"quota_usage": -1}}
            )
            return {"reply": "❌ Hizmet bulunamadı. Lütfen tekrar randevu alın."}

        apt_obj = Appointment(**{
            **apt_dict,
            "organization_id": org_id,
            "service_name": service.get("name", ""),
            "service_price": service.get("price", 0),
            "service_duration": service.get("duration", 30),
            "source": "public_booking_wa_verified",
            "status": "Bekliyor",
        })
        doc = apt_obj.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.appointments.insert_one(doc)

        await db.customers.update_one(
            {"organization_id": org_id, "phone": apt_dict.get("phone", "")},
            {
                "$set": {
                    "name": apt_dict.get("customer_name", ""),
                    "phone": apt_dict.get("phone", ""),
                    "organization_id": org_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "notes": "",
                },
            },
            upsert=True,
        )

        phone_map_key = f"plann:pending:phone:{stored_phone}:{org_id}"
        await redis_client.delete(pending_key)
        await redis_client.delete(phone_map_key)
        await redis_client.setex(f"plann:verified:{code}", 300, "1")

        try:
            apt_clean = {k: v for k, v in doc.items() if k != "_id"}
            await emit_to_organization(org_id, "appointment_created", {"appointment": apt_clean})
        except Exception:
            pass

        # ── Push notifications → admin + personel ───────────────────
        try:
            apt_date_raw = apt_dict.get("appointment_date", "")
            try:
                _d = apt_date_raw.split("-")
                apt_date_fmt_push = f"{_d[2]}.{_d[1]}.{_d[0]}"
            except Exception:
                apt_date_fmt_push = apt_date_raw
            notif_body = (
                f"{apt_dict.get('customer_name', '')} - {service.get('name', '')} "
                f"({apt_date_fmt_push} {apt_dict.get('appointment_time', '')})"
            )
            notif_data = {
                "type": "new_appointment",
                "appointment_id": doc.get("id"),
                "source": "public_booking_wa_verified",
            }
            admins = await db.users.find({"organization_id": org_id, "role": "admin"}).to_list(100)
            for admin in admins:
                await send_push_notification(
                    db=db,
                    organization_id=org_id,
                    title="🔔 Yeni Online Randevu!",
                    body=notif_body,
                    data=notif_data,
                    user_id=admin["username"],
                )
            assigned = apt_dict.get("staff_member_id")
            if assigned:
                staff_doc = await db.users.find_one({"username": assigned, "organization_id": org_id})
                if staff_doc and staff_doc.get("role") != "admin":
                    await send_push_notification(
                        db=db,
                        organization_id=org_id,
                        title="🔔 Yeni Randevu Atandı!",
                        body=notif_body,
                        data=notif_data,
                        user_id=assigned,
                    )
            logging.info(f"✓ Push notifications sent for WA-verified appointment {doc.get('id')}")
        except Exception as _push_err:
            logging.error(f"WA verified push notification hatası: {_push_err}")

        settings_data = await db.settings.find_one({"organization_id": org_id})
        company_name  = (settings_data or {}).get("company_name", "İşletmeniz")
        support_phone = (settings_data or {}).get("support_phone", "")
        location      = (settings_data or {}).get("location") or {}
        coords        = location.get("coordinates") or {}
        lat           = coords.get("lat")
        lng           = coords.get("lng")
        address       = location.get("address", "")

        try:
            await asyncio.to_thread(
                send_whatsapp_template,
                apt_dict.get("phone", ""),
                "CONFIRMATION",
                apt_dict.get("customer_name", ""),
                company_name,
                apt_dict.get("appointment_date", ""),
                apt_dict.get("appointment_time", ""),
                service.get("name", ""),
                support_phone,
                business_lat=lat,
                business_lng=lng,
                business_address=address,
            )
        except Exception as _wa_err:
            logging.warning(f"WA onay template gönderilemedi: {_wa_err}")

        return {"reply": ""}  # Template gönderildi, ek düz metin gerekmez

    except Exception as e:
        logging.error(f"WA doğrulama randevu hatası: {e}", exc_info=True)
        return {"reply": "❌ Randevu oluşturulurken bir hata oluştu. Lütfen tekrar deneyin."}


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """
    Meta'dan gelen mesajları ve durum güncellemelerini dinler.
    - messages  → dil tespiti yaparak otomatik yanıt gönderir
    - statuses  → sent/delivered/read/failed durumlarını DB'ye kaydeder
    """
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=200)

    logger.info(f"📩 Meta Webhook gövdesi: {body}")

    db = await get_db_from_request(request)

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # ── 1. Gelen müşteri mesajları ──────────────────────────────
                for message in value.get("messages", []):
                    from_number = message.get("from")
                    msg_type    = message.get("type", "")
                    if not from_number or msg_type not in (
                        "text", "audio", "image", "video", "document",
                        "sticker", "location", "contacts", "interactive", "button",
                    ):
                        continue
                    logger.info(f"📩 Gelen WA mesajı: from={from_number} type={msg_type}")

                    # ── RND doğrulama kodu kontrolü ──────────────────────────
                    if msg_type == "text":
                        text_body = message.get("text", {}).get("body", "")
                        rnd_match = re.search(r"\bRND-\d{5}\b", text_body.upper())
                        if rnd_match:
                            redis_client_wh = getattr(request.app.state, "redis_client", None)
                            result = await _process_whatsapp_verification(
                                db, redis_client_wh, from_number, rnd_match.group(0)
                            )
                            if result.get("reply"):
                                _send_whatsapp_text_reply(from_number, result["reply"])
                            continue

                    # ── Varsayılan otomatik yanıt ────────────────────────────
                    lang = detect_language_from_phone(from_number)
                    if lang == "TR":
                        reply = (
                            "Bu numara sadece bilgilendirme amaçlıdır, "
                            "lütfen doğrudan işletmeyle iletişime geçin."
                        )
                    else:
                        reply = (
                            "This number is for information purposes only, "
                            "please contact the business directly."
                        )
                    _send_whatsapp_text_reply(from_number, reply)

                # ── 2. Mesaj durumu güncellemeleri → DB'ye kaydet ────────────
                for status_obj in value.get("statuses", []):
                    message_id   = status_obj.get("id")
                    recipient    = status_obj.get("recipient_id")
                    wa_status    = status_obj.get("status")        # sent/delivered/read/failed
                    timestamp_ms = status_obj.get("timestamp")
                    errors       = status_obj.get("errors", [])

                    if wa_status == "failed" and errors:
                        logger.error(
                            f"❌ WA mesaj gönderilemedi | id={message_id} "
                            f"to={recipient} errors={errors}"
                        )
                    else:
                        logger.info(
                            f"📬 WA durum: {wa_status} | id={message_id} to={recipient}"
                        )

                    if db is not None:
                        try:
                            log_doc = {
                                "message_id": message_id,
                                "recipient":  recipient,
                                "status":     wa_status,
                                "timestamp":  int(timestamp_ms) if timestamp_ms else None,
                                "errors":     errors,
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                            }
                            await db.whatsapp_message_logs.update_one(
                                {"message_id": message_id, "status": wa_status},
                                {"$set": log_doc},
                                upsert=True,
                            )
                        except Exception as db_err:
                            logger.error(f"WA log DB kayıt hatası: {db_err}")

    except Exception as e:
        logger.error(f"Webhook işleme hatası: {e}")

    return Response(status_code=200)


@app.post("/api/webhook")
async def whatsapp_webhook_api_app(request: Request):
    return await whatsapp_webhook(request)


@api_router.post("/webhook")
async def whatsapp_webhook_api(request: Request):
    return await whatsapp_webhook(request)

# === CORS Preflight için OPTIONS handler (router'dan SONRA) ===
@app.options("/api/{path:path}")
async def options_handler(response: Response, request: Request):
    response.status_code = status.HTTP_204_NO_CONTENT
    return response

# Static files serving for logos (must be after router)
static_files_dir = str(ROOT_DIR / "static")
app.mount("/api/static", StaticFiles(directory=static_files_dir), name="static")

# --- CORS Ayarı ---
cors_origins_str = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_str == '*':
    cors_origins = ['*']
else:
    # Virgülle ayrılmış origin'leri parse et ve boşlukları temizle
    cors_origins = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()]
logging.info(f"CORS origins configured: {cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], 
    allow_headers=["*"],
)

# Export socket_app as the main application for ASGI servers
# This allows both FastAPI and Socket.IO to work together
application = socket_app

async def run_stripe_audit():
    """
    COMPREHENSIVE STRIPE AUDIT
    Verifies that every plan, cycle, and currency combination exists in Stripe
    AND has the correct appointment_limit in its metadata.
    """
    if not STRIPE_SECRET_KEY:
        logger.error("❌ STRIPE_SECRET_KEY tanımlı değil! Audit çalıştırılamıyor.")
        return
    
    # Expected Source of Truth
    EXPECTED_CONFIG = {
        "standart": 100,  # Not: "standard" değil, "standart" (Türkçe)
        "professional": 300,
        "premium": 600,
        "business": 900,
        "enterprise": 1200,
        "corporate": -1
    }
    CYCLES = ["monthly", "yearly"]
    CURRENCIES = ["gbp", "try"]
    
    logger.info("=" * 80)
    logger.info("🔍 STRIPE COMPREHENSIVE AUDIT - Starting...")
    logger.info("=" * 80)
    
    results = {
        "pass": [],
        "fail": [],
        "warn": []
    }
    
    total_checks = 0
    
    # Iterate through every Plan x Cycle x Currency combination
    for plan_name, expected_limit in EXPECTED_CONFIG.items():
        for cycle in CYCLES:
            for currency in CURRENCIES:
                total_checks += 1
                lookup_key = f"{plan_name}_{cycle}_{currency}"
                
                try:
                    # Call Stripe API with product expansion for fallback
                    prices = stripe.Price.list(
                        lookup_keys=[lookup_key],
                        active=True,
                        limit=1,
                        expand=['data.product']
                    )
                    
                    # Check 1: Existence
                    if not prices.data or len(prices.data) == 0:
                        error_msg = f"Price not found in Stripe"
                        results["fail"].append({
                            "lookup_key": lookup_key,
                            "error": error_msg,
                            "expected_limit": expected_limit
                        })
                        logger.error(f"[❌ FAIL] {lookup_key:35} | Expected Limit: {expected_limit:4} | Error: {error_msg}")
                        continue
                    
                    price = prices.data[0]
                    
                    # Check 2: Metadata Presence (FALLBACK STRATEGY)
                    # Step 1: Check Price metadata
                    price_metadata = price.metadata or {}
                    appointment_limit = price_metadata.get('appointment_limit')
                    metadata_source = "Price"
                    
                    # Step 2: If not found in price, check product metadata
                    if not appointment_limit:
                        product_obj = price.product
                        if product_obj:
                            # product_obj can be a string (ID) or dict (expanded)
                            if isinstance(product_obj, dict):
                                product_metadata = product_obj.get('metadata', {})
                                appointment_limit = product_metadata.get('appointment_limit')
                                if appointment_limit:
                                    metadata_source = "Product"
                                    logger.info(f"✅ Found appointment_limit in Product metadata (fallback): {appointment_limit}")
                            elif isinstance(product_obj, str):
                                # Product not expanded, retrieve it
                                try:
                                    product_retrieved = stripe.Product.retrieve(product_obj)
                                    product_metadata = product_retrieved.get('metadata', {})
                                    appointment_limit = product_metadata.get('appointment_limit')
                                    if appointment_limit:
                                        metadata_source = "Product"
                                        logger.info(f"✅ Found appointment_limit in Product metadata (fallback, retrieved): {appointment_limit}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Product retrieve hatası: {e}")
                    
                    if not appointment_limit:
                        error_msg = f"Metadata 'appointment_limit' missing in both Price and Product"
                        results["warn"].append({
                            "lookup_key": lookup_key,
                            "error": error_msg,
                            "expected_limit": expected_limit,
                            "price_id": price.id,
                            "currency": price.currency.upper()
                        })
                        logger.warning(f"[⚠️ WARN] {lookup_key:35} | Expected Limit: {expected_limit:4} | Error: {error_msg} | Price ID: {price.id}")
                        continue
                    
                    # Check 3: Metadata Accuracy
                    try:
                        actual_limit = int(appointment_limit)
                    except (ValueError, TypeError):
                        error_msg = f"Metadata 'appointment_limit' is not a valid integer: '{appointment_limit}'"
                        results["fail"].append({
                            "lookup_key": lookup_key,
                            "error": error_msg,
                            "expected_limit": expected_limit,
                            "price_id": price.id
                        })
                        logger.error(f"[❌ FAIL] {lookup_key:35} | Expected Limit: {expected_limit:4} | Error: {error_msg} | Price ID: {price.id}")
                        continue
                    
                    # Yearly plans must also have the MONTHLY limit (not multiplied by 12)
                    if actual_limit == expected_limit:
                        results["pass"].append({
                            "lookup_key": lookup_key,
                            "expected_limit": expected_limit,
                            "actual_limit": actual_limit,
                            "price_id": price.id,
                            "currency": price.currency.upper(),
                            "amount": price.unit_amount / 100,
                            "metadata_source": metadata_source
                        })
                        logger.info(f"[✅ PASS] {lookup_key:35} | Limit: {actual_limit:4} (Expected: {expected_limit:4}) | Source: {metadata_source:7} | {price.currency.upper():4} | {price.unit_amount/100:8.2f} | Price ID: {price.id}")
                    else:
                        error_msg = f"Limit mismatch: Expected {expected_limit}, Found {actual_limit}"
                        results["fail"].append({
                            "lookup_key": lookup_key,
                            "error": error_msg,
                            "expected_limit": expected_limit,
                            "actual_limit": actual_limit,
                            "price_id": price.id
                        })
                        logger.error(f"[❌ FAIL] {lookup_key:35} | Expected Limit: {expected_limit:4} | Actual Limit: {actual_limit:4} | Error: {error_msg} | Price ID: {price.id}")
                
                except stripe.error.StripeError as e:
                    error_msg = f"Stripe API error: {str(e)}"
                    results["fail"].append({
                        "lookup_key": lookup_key,
                        "error": error_msg,
                        "expected_limit": expected_limit
                    })
                    logger.error(f"[❌ FAIL] {lookup_key:35} | Expected Limit: {expected_limit:4} | Error: {error_msg}")
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    results["fail"].append({
                        "lookup_key": lookup_key,
                        "error": error_msg,
                        "expected_limit": expected_limit
                    })
                    logger.error(f"[❌ FAIL] {lookup_key:35} | Expected Limit: {expected_limit:4} | Error: {error_msg}")
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 AUDIT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Checks: {total_checks}")
    logger.info(f"✅ PASS: {len(results['pass'])}")
    logger.info(f"⚠️  WARN: {len(results['warn'])}")
    logger.info(f"❌ FAIL: {len(results['fail'])}")
    logger.info("=" * 80)
    
    if results["fail"]:
        logger.error("\n❌ FAILED ITEMS:")
        for item in results["fail"]:
            logger.error(f"   - {item['lookup_key']}: {item['error']}")
    
    if results["warn"]:
        logger.warning("\n⚠️  WARNINGS:")
        for item in results["warn"]:
            logger.warning(f"   - {item['lookup_key']}: {item['error']}")
    
    if len(results["pass"]) == total_checks:
        logger.info("\n✅ ALL CHECKS PASSED! Stripe configuration is perfect!")
    else:
        logger.warning(f"\n⚠️  {len(results['fail']) + len(results['warn'])} issues found. Please fix them in Stripe Dashboard.")
    
    logger.info("=" * 80)
    
    return results
