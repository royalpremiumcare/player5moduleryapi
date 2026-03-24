"""
Service API Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class ServiceCreate(BaseModel):
    """Create service request"""
    name: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)
    duration: int = Field(30, ge=15, description="Duration in minutes")
    order: Optional[int] = None
    session_count: Optional[int] = None


class ServiceUpdate(BaseModel):
    """Update service request"""
    name: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    duration: Optional[int] = Field(None, ge=15)
    order: Optional[int] = None
    session_count: Optional[int] = None


class ServiceResponse(BaseModel):
    """Service response"""
    id: str
    name: str
    price: float
    duration: int
    order: Optional[int] = None
    session_count: Optional[int] = None
    organization_id: str
    created_at: Optional[str] = None
