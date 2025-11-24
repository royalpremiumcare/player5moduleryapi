"""
Customer API Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class CustomerCreate(BaseModel):
    """Create customer request"""
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=10)
    email: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Update customer request"""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(BaseModel):
    """Customer response"""
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    notes: Optional[str] = None
    organization_id: str
    created_at: Optional[str] = None
    appointment_count: Optional[int] = 0
