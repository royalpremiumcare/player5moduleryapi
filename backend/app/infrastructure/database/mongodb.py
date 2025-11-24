"""
MongoDB Database Connection
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls, mongodb_url: str, db_name: str):
        """Connect to MongoDB"""
        try:
            cls.client = AsyncIOMotorClient(mongodb_url)
            cls.db = cls.client[db_name]
            # Test connection
            await cls.client.admin.command('ping')
            logger.info(f"✅ MongoDB connected: {db_name}")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    @classmethod
    async def close(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        return cls.db


# Dependency for FastAPI
async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get database"""
    return MongoDB.get_database()
