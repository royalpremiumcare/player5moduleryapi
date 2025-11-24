"""
Redis Connection
"""
import redis.asyncio as redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis connection manager"""
    
    client: Optional[redis.Redis] = None
    
    @classmethod
    async def connect(cls, host: str, port: int, password: Optional[str] = None, db: int = 0):
        """Connect to Redis"""
        try:
            cls.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True
            )
            await cls.client.ping()
            logger.info(f"✅ Redis connected: {host}:{port}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            cls.client = None
    
    @classmethod
    async def close(cls):
        """Close Redis connection"""
        if cls.client:
            await cls.client.close()
            logger.info("Redis connection closed")
    
    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        """Get Redis client"""
        return cls.client
