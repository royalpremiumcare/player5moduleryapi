"""
Redis Cache Helper Module - PLANN Turbo Motoru 🚀 (Ağır Loglamalı Versiyon)
"""
import json
import os
import asyncio
from typing import Optional, Any
from functools import wraps
import logging
from fastapi import Request
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

# Try to import redis.asyncio, but make it optional
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis (asyncio) module not found. Cache functionality will be disabled.")


async def init_redis():
    """
    Initialize Redis connection and return the client.
    Does not use a global variable to ensure thread/async safety.
    """
    if not REDIS_AVAILABLE:
        logger.info("Redis module not available. Cache functionality disabled.")
        return None
    
    try:
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        # decode_responses=True ile byte yerine direkt string alıyoruz
        redis_client = redis.from_url(
            redis_url, 
            decode_responses=True,
            socket_connect_timeout=2,  # 2 saniye timeout (Sunucu takılmasın diye)
            socket_timeout=2,
            retry_on_timeout=False
        )
        
        # Bağlantıyı test et
        await asyncio.wait_for(redis_client.ping(), timeout=2)
        logger.info("✅ Redis (asyncio) connection established. PLANN Turbo is ON!")
        return redis_client
        
    except asyncio.TimeoutError:
        logger.warning("⚠️ Redis connection timeout. Cache will be bypassed.")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Redis (asyncio) connection failed: {e}. Cache will be bypassed.")
        return None


def get_cache_key(prefix: str, org_id: str, extra: str = "") -> str:
    """Çok Kiracılı (Multi-Tenant) Güvenli Cache Anahtarı"""
    base_key = f"plann:org_{org_id}:{prefix}"
    return f"{base_key}:{extra}" if extra else base_key


def cache_result(prefix: str, ttl: int = 300):
    """
    FastAPI endpoint'leri için Turbo Önbellek Dekoratörü.
    Fonksiyona 'request: Request' ve 'current_user' parametrelerinin geçilmiş olması ZORUNLUDUR.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            
            # 1. İstek (Request) ve Kullanıcı (User) objelerini güvenli şekilde yakala
            request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                        
            current_user = kwargs.get('current_user')
            if not current_user:
                for arg in args:
                    if hasattr(arg, 'organization_id'):
                        current_user = arg
                        break

            # Redis client'ı FastAPI app state'inden al
            redis_client = getattr(request.app.state, 'redis_client', None) if hasattr(request, 'app') else None

            # --- DEDEKTİF MODU AÇIK: SESSİZ BYPASS YERİNE BAĞIRAN LOGLAR ---
            if not request:
                logger.warning(f"Bypass ({prefix}): 'request' objesi bulunamadı! Lütfen endpoint'e 'request: Request' parametresini ekleyin.")
                return await func(*args, **kwargs)
            if not current_user:
                logger.warning(f"Bypass ({prefix}): 'current_user' objesi bulunamadı! Lütfen endpoint'te kullanıcıyı doğrulayın.")
                return await func(*args, **kwargs)
            if not redis_client:
                logger.warning(f"Bypass ({prefix}): 'redis_client' bulunamadı! (lifespan'da state'e eklenmemiş veya init_redis() başarısız)")
                return await func(*args, **kwargs)
            # ----------------------------------------------------------------

            org_id = getattr(current_user, 'organization_id', None)
            if not org_id:
                logger.warning(f"Bypass ({prefix}): Kullanıcının 'organization_id'si yok.")
                return await func(*args, **kwargs)

            # 2. Güvenli Cache Anahtarını Oluştur (A firması B firmasını göremez!)
            cache_key = get_cache_key(prefix, org_id)

            # 3. Redis'te var mı diye bak (Işık hızında okuma)
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"⚡ CACHE HIT: {cache_key} (Veritabanı kurtarıldı!)")
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Redis Okuma Hatası: {e}")

            # 4. Redis'te yoksa, gerçek fonksiyonu (MongoDB'yi) çalıştır
            logger.info(f"🐢 CACHE MISS: Veritabanından hesaplanıyor... {cache_key}")
            result = await func(*args, **kwargs)

            # 5. Sonucu Redis'e kaydet (jsonable_encoder ile tarih/saat objelerini string'e çevir)
            try:
                # ttl süresi (saniye) kadar hafızada kalacak
                encoded_result = jsonable_encoder(result)
                await redis_client.setex(cache_key, ttl, json.dumps(encoded_result))
            except Exception as e:
                logger.error(f"Redis Yazma Hatası ({cache_key}): {e}")

            return result
        return wrapper
    return decorator


async def invalidate_cache(request: Request, prefix: str, current_user: Any):
    """
    Yeni bir randevu eklendiğinde veya müşteri güncellendiğinde, 
    eskiyen cache'i anında silmek için kullanılır.
    """
    redis_client = getattr(request.app.state, 'redis_client', None) if hasattr(request, 'app') else None
    if not redis_client or not current_user:
        return
    
    org_id = getattr(current_user, 'organization_id', None)
    if org_id:
        cache_key = get_cache_key(prefix, org_id)
        try:
            deleted_exact = 0
            try:
                deleted_exact = await redis_client.delete(cache_key)
            except Exception as exact_delete_error:
                logger.error(f"Redis Silme Hatası (exact key): {exact_delete_error}")

            # Pattern matching ile bu prefix'e ait her şeyi sil
            # Örn: plann:org_123:dashboard_stats*
            keys = await redis_client.keys(f"{cache_key}*")
            if keys:
                await redis_client.delete(*keys)
                logger.info(f"🧹 CACHE TEMİZLENDİ: {len(keys)} adet '{prefix}' kaydı silindi.")
            elif deleted_exact:
                logger.info(f"🧹 CACHE TEMİZLENDİ: 1 adet '{prefix}' kaydı silindi.")
            else:
                logger.info(f"🧹 CACHE TEMİZ: '{prefix}' için silinecek kayıt bulunamadı.")
        except Exception as e:
            logger.error(f"Redis Silme Hatası: {e}")