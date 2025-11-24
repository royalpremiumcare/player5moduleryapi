"""
Main FastAPI Application - Clean Architecture
Entry point for the refactored modular application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .core.config import settings
from .infrastructure.database.mongodb import MongoDB
from .infrastructure.database.redis_client import RedisClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    
    # === STARTUP ===
    logger.info("🚀 Starting PLANN API (Clean Architecture)")
    
    # Connect to MongoDB
    try:
        await MongoDB.connect(settings.MONGODB_URL, settings.MONGODB_DB_NAME)
        app.state.db = MongoDB.get_database()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    
    # Connect to Redis (optional)
    try:
        await RedisClient.connect(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB
        )
        app.state.redis = RedisClient.get_client()
    except Exception as e:
        logger.warning(f"Redis connection failed (non-critical): {e}")
        app.state.redis = None
    
    logger.info("✅ Application started successfully")
    
    yield
    
    # === SHUTDOWN ===
    logger.info("🛑 Shutting down PLANN API")
    
    # Close MongoDB
    await MongoDB.close()
    
    # Close Redis
    if app.state.redis:
        await RedisClient.close()
    
    logger.info("✅ Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === HEALTH CHECK ===
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": "PLANN API (Clean Architecture)"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PLANN API - Clean Architecture",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


# === IMPORT AND INCLUDE ROUTERS ===
from .api.v1.router import api_router
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8003,  # Different port from old server.py (8002)
        reload=True
    )
