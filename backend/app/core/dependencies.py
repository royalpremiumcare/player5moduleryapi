"""
Common Dependencies for FastAPI
Authentication, database access, etc.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
import logging

from .security import decode_access_token
from ..infrastructure.database.mongodb import get_db

logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


# === USER MODELS ===
class UserInDB(BaseModel):
    """User database model"""
    model_config = ConfigDict(extra="ignore")
    username: str
    hashed_password: str
    full_name: Optional[str] = None
    organization_id: str
    role: str = "staff"
    slug: Optional[str] = None
    permitted_service_ids: list = []
    onboarding_completed: bool = False
    staff_member_id: Optional[str] = None
    created_at: Optional[str] = None
    can_view_all_appointments: bool = False
    # Aha activation flow + stable identity (lazy-backfilled)
    user_id: Optional[str] = None
    activation_state: Optional[str] = None
    aha_skipped_reason: Optional[str] = None
    aha_skipped_at: Optional[str] = None
    aha_wa_message_id: Optional[str] = None
    aha_wa_last_error: Optional[str] = None
    aha_appointment_id: Optional[str] = None
    first_appointment_at: Optional[str] = None


async def _ensure_user_identity_fields(db: AsyncIOMotorDatabase, user_doc: dict) -> dict:
    """
    Lazy backfill: ilk okuma anında eksik `user_id` (UUID) ve `activation_state`
    alanlarını doldurur. Mevcut admin'ler `aha_skipped` (legacy) olarak işaretlenir
    ki sürpriz Aha overlay'i çıkmasın.
    """
    import uuid as _uuid
    updates = {}
    if not user_doc.get("user_id"):
        updates["user_id"] = str(_uuid.uuid4())
    if not user_doc.get("activation_state"):
        role = user_doc.get("role") or "staff"
        if role != "admin":
            updates["activation_state"] = "not_applicable"
        elif bool(user_doc.get("onboarding_completed")):
            updates["activation_state"] = "aha_skipped"
            updates["aha_skipped_reason"] = "legacy_backfill"
        else:
            updates["activation_state"] = "pending_aha_appointment"
    if updates:
        try:
            await db.users.update_one(
                {"username": user_doc.get("username")},
                {"$set": updates},
            )
            user_doc.update(updates)
        except Exception as e:
            logger.warning(f"Identity backfill failed for {user_doc.get('username')}: {e}")
    return user_doc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> UserInDB:
    """
    Get current authenticated user from JWT token
    
    This is the main authentication dependency used across all protected endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
        
        # Get user from database
        user_doc = await db.users.find_one({"username": username}, {"_id": 0})
        
        if user_doc is None:
            raise credentials_exception

        # Lazy backfill stable user_id + activation_state for legacy users
        user_doc = await _ensure_user_identity_fields(db, user_doc)

        return UserInDB(**user_doc)
    
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception


async def get_current_admin_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """Require admin role"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_current_superadmin_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """Require superadmin role"""
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required"
        )
    return current_user


async def get_db_from_request(request: Request) -> AsyncIOMotorDatabase:
    """Get database from request state (for backwards compatibility)"""
    if hasattr(request.app.state, "db") and request.app.state.db:
        return request.app.state.db
    return await get_db()
