"""
Auth API Schemas
Request and Response models for authentication
"""
from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    """User registration schema"""
    username: str = Field(..., description="Email address")
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    organization_name: Optional[str] = None
    support_phone: Optional[str] = None
    sector: Optional[str] = None


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login credentials"""
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    username: str


class ResetPasswordRequest(BaseModel):
    """Reset password with token"""
    token: str
    new_password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    """User info response (without password)"""
    username: str
    full_name: Optional[str] = None
    organization_id: str
    role: str
    slug: Optional[str] = None
    onboarding_completed: bool = False
    # Stable identity + Aha activation flow
    user_id: Optional[str] = None
    activation_state: Optional[str] = None
