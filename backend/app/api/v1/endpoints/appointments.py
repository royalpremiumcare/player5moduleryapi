"""
Appointments Endpoints
CRUD operations for appointments
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid
import logging

from ....core.dependencies import get_current_user, get_current_admin_user, UserInDB
from ....core.exceptions import QuotaExceededException, TrialExpiredException, NotFoundException
from ....core.constants import get_plan_by_id
from ....infrastructure.database.mongodb import get_db
from ...schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def check_quota_and_increment(db: AsyncIOMotorDatabase, org_id: str) -> bool:
    """
    Check appointment quota and increment if available
    Returns True if quota available, raises exception if not
    """
    plan_doc = await db.organization_plans.find_one({"organization_id": org_id})
    
    if not plan_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization plan not found"
        )
    
    plan_id = plan_doc.get("plan_id", "tier_trial")
    plan = get_plan_by_id(plan_id)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid plan configuration"
        )
    
    # Check trial expiration
    if plan_id == "tier_trial":
        trial_end = plan_doc.get("trial_end_date")
        if trial_end:
            if isinstance(trial_end, str):
                trial_end = datetime.fromisoformat(trial_end)
            if datetime.now(timezone.utc) > trial_end:
                raise TrialExpiredException(
                    detail="Trial period has expired. Please upgrade to continue."
                )
    
    # Check quota
    quota_limit = plan.get("quota_monthly_appointments", 0)
    current_usage = plan_doc.get("quota_usage", 0)
    
    if quota_limit != -1 and current_usage >= quota_limit:
        raise QuotaExceededException(
            detail=f"Monthly appointment quota exceeded ({quota_limit} appointments). Please upgrade your plan."
        )
    
    # Increment quota
    await db.organization_plans.update_one(
        {"organization_id": org_id},
        {"$inc": {"quota_usage": 1}}
    )
    
    logger.info(f"✅ Quota incremented for org {org_id}: {current_usage + 1}/{quota_limit}")
    return True


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, le=500),
    skip: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    List appointments for current organization
    
    Filters:
    - status: Filter by appointment status
    - date_from/date_to: Date range filter
    - Staff users only see their own appointments
    """
    # Build query
    query = {"organization_id": current_user.organization_id}
    
    # Staff users only see their appointments
    if current_user.role == "staff" and current_user.staff_member_id:
        query["staff_member_id"] = current_user.staff_member_id
    
    # Status filter
    if status_filter:
        query["status"] = status_filter
    
    # Date range filter
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        query["appointment_date"] = date_query
    
    # Get appointments
    cursor = db.appointments.find(query, {"_id": 0}).sort("appointment_date", -1).skip(skip).limit(limit)
    appointments = await cursor.to_list(length=limit)
    
    # Get total count
    total = await db.appointments.count_documents(query)
    
    # Enrich with service and staff names
    for apt in appointments:
        # Get service name
        if apt.get("service_id"):
            service = await db.services.find_one(
                {"id": apt["service_id"], "organization_id": current_user.organization_id},
                {"_id": 0, "name": 1}
            )
            if service:
                apt["service_name"] = service["name"]
        
        # Get staff member name
        if apt.get("staff_member_id"):
            staff = await db.users.find_one(
                {"staff_member_id": apt["staff_member_id"], "organization_id": current_user.organization_id},
                {"_id": 0, "full_name": 1}
            )
            if staff:
                apt["staff_member_name"] = staff.get("full_name", "Unknown")
    
    logger.info(f"📋 Listed {len(appointments)} appointments for org {current_user.organization_id}")
    
    return AppointmentListResponse(
        appointments=[AppointmentResponse(**apt) for apt in appointments],
        total=total
    )


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appointment: AppointmentCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Create new appointment
    
    - Checks quota before creation
    - Auto-assigns staff if not specified
    - Creates customer record if not exists
    """
    # Check quota
    await check_quota_and_increment(db, current_user.organization_id)
    
    # Verify service exists
    service = await db.services.find_one({
        "id": appointment.service_id,
        "organization_id": current_user.organization_id
    })
    
    if not service:
        raise NotFoundException(detail="Service not found")
    
    # Create appointment document
    apt_id = str(uuid.uuid4())
    apt_doc = {
        "id": apt_id,
        "organization_id": current_user.organization_id,
        "customer_name": appointment.customer_name,
        "phone": appointment.phone,
        "service_id": appointment.service_id,
        "service_name": service.get("name", "Unknown"),
        "appointment_date": appointment.appointment_date,
        "appointment_time": appointment.appointment_time,
        "status": "Bekliyor",
        "staff_member_id": appointment.staff_member_id,
        "notes": appointment.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reminder_sent": False
    }
    
    await db.appointments.insert_one(apt_doc)
    
    # Create/update customer record
    await db.customers.update_one(
        {
            "phone": appointment.phone,
            "organization_id": current_user.organization_id
        },
        {
            "$set": {
                "name": appointment.customer_name,
                "phone": appointment.phone,
                "organization_id": current_user.organization_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    logger.info(f"✅ Appointment created: {apt_id} for {appointment.customer_name}")
    
    # TODO: Send SMS reminder
    # TODO: Emit WebSocket event
    
    return AppointmentResponse(**apt_doc)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get appointment by ID"""
    query = {
        "id": appointment_id,
        "organization_id": current_user.organization_id
    }
    
    # Staff can only see their appointments
    if current_user.role == "staff" and current_user.staff_member_id:
        query["staff_member_id"] = current_user.staff_member_id
    
    apt = await db.appointments.find_one(query, {"_id": 0})
    
    if not apt:
        raise NotFoundException(detail="Appointment not found")
    
    return AppointmentResponse(**apt)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: str,
    update_data: AppointmentUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Update appointment
    
    - Admin can update any appointment
    - Staff can only update their own appointments
    """
    query = {
        "id": appointment_id,
        "organization_id": current_user.organization_id
    }
    
    # Staff can only update their appointments
    if current_user.role == "staff" and current_user.staff_member_id:
        query["staff_member_id"] = current_user.staff_member_id
    
    # Check if appointment exists
    existing = await db.appointments.find_one(query, {"_id": 0})
    if not existing:
        raise NotFoundException(detail="Appointment not found")
    
    # Build update document
    update_doc = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_doc[field] = value
    
    if not update_doc:
        return AppointmentResponse(**existing)
    
    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Update appointment
    await db.appointments.update_one(query, {"$set": update_doc})
    
    # Get updated document
    updated_apt = await db.appointments.find_one(query, {"_id": 0})
    
    logger.info(f"✅ Appointment updated: {appointment_id}")
    
    # TODO: Emit WebSocket event
    
    return AppointmentResponse(**updated_apt)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_admin_user),  # Only admin can delete
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Delete appointment (Admin only)
    
    - Decrements quota
    - Permanently removes appointment
    """
    query = {
        "id": appointment_id,
        "organization_id": current_user.organization_id
    }
    
    # Check if exists
    apt = await db.appointments.find_one(query, {"_id": 0})
    if not apt:
        raise NotFoundException(detail="Appointment not found")
    
    # Delete appointment
    result = await db.appointments.delete_one(query)
    
    if result.deleted_count == 0:
        raise NotFoundException(detail="Appointment not found")
    
    # Decrement quota
    await db.organization_plans.update_one(
        {"organization_id": current_user.organization_id},
        {"$inc": {"quota_usage": -1}}
    )
    
    logger.info(f"🗑️ Appointment deleted: {appointment_id}")
    
    # TODO: Emit WebSocket event
    
    return None
