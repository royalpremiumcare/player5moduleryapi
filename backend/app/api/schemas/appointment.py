"""
Appointment API Schemas
Request and Response models for appointments
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class AppointmentCreate(BaseModel):
    """Create appointment request"""
    customer_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=10)
    service_id: str
    appointment_date: str = Field(..., description="YYYY-MM-DD format")
    appointment_time: str = Field(..., description="HH:MM format")
    staff_member_id: Optional[str] = None
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """Update appointment request"""
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    service_id: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    staff_member_id: Optional[str] = None
    status: Optional[Literal["Bekliyor", "Tamamlandı", "İptal Edildi", "Gelmedi"]] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Appointment response"""
    id: str
    customer_name: str
    phone: str
    service_id: str
    service_name: Optional[str] = None
    appointment_date: str
    appointment_time: str
    status: str = "Bekliyor"
    staff_member_id: Optional[str] = None
    staff_member_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    organization_id: str


class AppointmentListResponse(BaseModel):
    """List of appointments"""
    appointments: list[AppointmentResponse]
    total: int
