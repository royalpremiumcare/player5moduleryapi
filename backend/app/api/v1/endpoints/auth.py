"""
Authentication Endpoints
Login, Register, Token management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
import uuid
import re
import logging

from ....core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token
)
from ....core.dependencies import get_current_user, UserInDB
from ....core.constants import DEFAULT_WORKING_HOURS
from ....infrastructure.database.mongodb import get_db
from ...schemas.auth import (
    UserCreate, 
    Token, 
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest
)

logger = logging.getLogger(__name__)

router = APIRouter()


def slugify(text: str) -> str:
    """Create URL-friendly slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Register new user and organization
    
    Creates:
    - User account (admin role)
    - Organization
    - Default settings
    - Trial plan (7 days, 50 appointments)
    """
    # Check if user already exists
    existing_user = await db.users.find_one({"username": user_in.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already registered."
        )
    
    # Create new organization ID
    new_org_id = str(uuid.uuid4())
    
    # Hash password
    hashed_password = get_password_hash(user_in.password)
    
    # Generate unique slug
    base_slug = slugify(user_in.organization_name or user_in.username)
    unique_slug = base_slug
    
    slug_counter = 1
    while await db.users.find_one({"slug": unique_slug}):
        unique_slug = f"{base_slug}{str(uuid.uuid4())[:4]}"
        slug_counter += 1
        if slug_counter > 10:
            unique_slug = f"{base_slug}{str(uuid.uuid4())[:8]}"
            break
    
    # Create user document
    user_doc = {
        "username": user_in.username,
        "hashed_password": hashed_password,
        "full_name": user_in.full_name,
        "organization_id": new_org_id,
        "role": "admin",
        "slug": unique_slug,
        "permitted_service_ids": [],
        "onboarding_completed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Create default settings
    settings_doc = {
        "organization_id": new_org_id,
        "company_name": user_in.organization_name or "İşletmeniz",
        "support_phone": user_in.support_phone or "05000000000",
        "slug": unique_slug,
        "customer_can_choose_staff": False,
        "sector": user_in.sector,
        "working_hours": DEFAULT_WORKING_HOURS,
        "sms_reminder_hours": 1.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.settings.insert_one(settings_doc)
    
    # Create trial plan
    trial_start = datetime.now(timezone.utc)
    trial_end = trial_start + timedelta(days=7)
    
    trial_plan_doc = {
        "organization_id": new_org_id,
        "plan_id": "tier_trial",
        "quota_usage": 0,
        "ai_usage_count": 0,
        "quota_reset_date": (trial_start + timedelta(days=30)).isoformat(),
        "trial_start_date": trial_start.isoformat(),
        "trial_end_date": trial_end.isoformat(),
        "is_first_month": True,
        "created_at": trial_start.isoformat()
    }
    
    await db.organization_plans.insert_one(trial_plan_doc)
    
    logger.info(f"✅ New user registered: {user_in.username} (org: {new_org_id})")
    
    return UserResponse(
        username=user_in.username,
        full_name=user_in.full_name,
        organization_id=new_org_id,
        role="admin",
        slug=unique_slug,
        onboarding_completed=False
    )


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    OAuth2 compatible token login
    Returns JWT access token
    """
    # Find user
    user = await db.users.find_one({"username": form_data.username})
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "org_id": user["organization_id"],
            "role": user["role"],
            "onboarding_completed": user.get("onboarding_completed", False),
            "full_name": user.get("full_name", "")
        }
    )
    
    logger.info(f"✅ User logged in: {user['username']}")
    
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserInDB = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse(
        username=current_user.username,
        full_name=current_user.full_name,
        organization_id=current_user.organization_id,
        role=current_user.role,
        slug=current_user.slug,
        onboarding_completed=current_user.onboarding_completed
    )


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Request password reset
    Sends email with reset token
    """
    user = await db.users.find_one({"username": request.username})
    
    if not user:
        # Don't reveal if user exists (security best practice)
        return {"message": "If the email exists, a reset link has been sent."}
    
    # Create reset token
    reset_token = create_password_reset_token(request.username)
    
    # TODO: Send email with reset token
    # For now, just log it (in production, send via email service)
    logger.info(f"Password reset requested for: {request.username}")
    logger.info(f"Reset token: {reset_token}")
    
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Reset password using token"""
    email = verify_password_reset_token(request.token)
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    new_hashed_password = get_password_hash(request.new_password)
    
    result = await db.users.update_one(
        {"username": email},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"✅ Password reset successful for: {email}")
    
    return {"message": "Password reset successful"}
