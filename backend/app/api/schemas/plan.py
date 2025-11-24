"""
Plan & Payment API Schemas
"""
from pydantic import BaseModel
from typing import Optional, List


class PlanResponse(BaseModel):
    """Plan details response"""
    id: str
    name: str
    price_monthly: int
    quota_monthly_appointments: int
    ai_message_limit: int
    features: List[str]
    target_audience_tr: str
    trial_days: Optional[int] = None


class OrganizationPlanResponse(BaseModel):
    """Organization's current plan"""
    organization_id: str
    plan_id: str
    quota_usage: int
    quota_limit: int
    ai_usage_count: int
    ai_limit: int
    quota_reset_date: str
    is_first_month: bool
    trial_end_date: Optional[str] = None


class CheckoutRequest(BaseModel):
    """Stripe checkout request"""
    plan_id: str


class CheckoutResponse(BaseModel):
    """Stripe checkout response"""
    checkout_url: str
    session_id: str
