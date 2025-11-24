"""
Plans & Subscription Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
import logging

from ....core.dependencies import get_current_user, UserInDB
from ....core.constants import PLANS, get_plan_by_id
from ....core.exceptions import NotFoundException
from ....infrastructure.database.mongodb import get_db
from ...schemas.plan import PlanResponse, OrganizationPlanResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans():
    """
    List all available subscription plans
    
    Public endpoint - no authentication required
    """
    logger.info(f"📋 Plans list requested")
    return [PlanResponse(**plan) for plan in PLANS]


@router.get("/plan/current", response_model=OrganizationPlanResponse)
async def get_current_plan(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get current organization's plan details
    
    Returns:
    - Current plan info
    - Quota usage
    - AI usage
    - Reset dates
    """
    plan_doc = await db.organization_plans.find_one(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    )
    
    if not plan_doc:
        raise NotFoundException(detail="Organization plan not found")
    
    # Get plan details
    plan_id = plan_doc.get("plan_id", "tier_trial")
    plan = get_plan_by_id(plan_id)
    
    if not plan:
        raise NotFoundException(detail="Plan configuration not found")
    
    response = OrganizationPlanResponse(
        organization_id=plan_doc["organization_id"],
        plan_id=plan_id,
        quota_usage=plan_doc.get("quota_usage", 0),
        quota_limit=plan.get("quota_monthly_appointments", 0),
        ai_usage_count=plan_doc.get("ai_usage_count", 0),
        ai_limit=plan.get("ai_message_limit", 0),
        quota_reset_date=plan_doc.get("quota_reset_date", ""),
        is_first_month=plan_doc.get("is_first_month", False),
        trial_end_date=plan_doc.get("trial_end_date")
    )
    
    logger.info(f"📊 Current plan: {plan_id} for org {current_user.organization_id}")
    return response
