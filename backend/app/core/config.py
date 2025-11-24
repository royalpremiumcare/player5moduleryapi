"""
Core Configuration Module
Environment variables and application settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Load .env file
ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / '.env')


class Settings:
    """Application Settings - Simple config class"""
    
    # JWT Security
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_karmaşık_bir_secret_key_ekleyin_mutlaka')
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    
    # MongoDB
    MONGODB_URL = os.environ.get('MONGODB_URL', 'mongodb://localhost:27017')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'royalpremiumcare')
    
    # Redis
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    
    # SMS Settings
    ILETIMERKEZI_API_KEY = os.environ.get('ILETIMERKEZI_API_KEY')
    ILETIMERKEZI_HASH = os.environ.get('ILETIMERKEZI_HASH')
    ILETIMERKEZI_SENDER = os.environ.get('ILETIMERKEZI_SENDER', 'FatihSenyuz')
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    
    # Stripe Payment
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    PAYMENT_SUCCESS_URL = "https://plannapp.co/#/"
    PAYMENT_CANCEL_URL = "https://plannapp.co/#/subscribe"
    
    # Email (Brevo)
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
    
    # AI Service
    GOOGLE_GEMINI_KEY = os.environ.get('GOOGLE_GEMINI_KEY')
    
    # Application
    APP_NAME = "PLANN API"
    APP_VERSION = "2.0.0"
    DEBUG = os.environ.get('DEBUG', 'false').lower() in ('1', 'true', 'yes')
    
    # CORS
    CORS_ORIGINS = [
        "http://localhost:3000",
        "https://plannapp.co",
        "https://www.plannapp.co"
    ]
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "/tmp/backend.log"


# Create settings instance
settings = Settings()

# Validate critical settings
if settings.JWT_SECRET_KEY == 'default_karmaşık_bir_secret_key_ekleyin_mutlaka':
    import logging
    logging.warning("⚠️ WARNING: JWT_SECRET_KEY is using default value! Set a secure secret key in production.")

if not settings.STRIPE_SECRET_KEY:
    import logging
    logging.warning("⚠️ STRIPE_SECRET_KEY not configured. Payment features will not work.")

if not settings.BREVO_API_KEY:
    import logging
    logging.warning("⚠️ BREVO_API_KEY not configured. Email features will not work.")
