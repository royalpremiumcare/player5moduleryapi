"""
Customers Endpoints
CRUD operations for customers
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

from ....core.dependencies import get_current_user, UserInDB
from ....core.exceptions import NotFoundException, ConflictException
from ....infrastructure.database.mongodb import get_db
from ...schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[CustomerResponse])
async def list_customers(
    search: Optional[str] = Query(None, description="Search by name or phone"),
    limit: int = Query(100, le=500),
    skip: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """List all customers for organization"""
    query = {"organization_id": current_user.organization_id}
    
    # Search filter
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    
    customers = await db.customers.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(length=limit)
    
    # Get appointment counts
    for customer in customers:
        apt_count = await db.appointments.count_documents({
            "phone": customer["phone"],
            "organization_id": current_user.organization_id
        })
        customer["appointment_count"] = apt_count
    
    logger.info(f"📋 Listed {len(customers)} customers for org {current_user.organization_id}")
    return [CustomerResponse(**cust) for cust in customers]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create new customer"""
    # Check for duplicate phone
    existing = await db.customers.find_one({
        "phone": customer.phone,
        "organization_id": current_user.organization_id
    })
    
    if existing:
        raise ConflictException(detail="Customer with this phone number already exists")
    
    customer_id = str(uuid.uuid4())
    customer_doc = {
        "id": customer_id,
        "organization_id": current_user.organization_id,
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "notes": customer.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "appointment_count": 0
    }
    
    await db.customers.insert_one(customer_doc)
    logger.info(f"✅ Customer created: {customer.name} ({customer.phone})")
    
    return CustomerResponse(**customer_doc)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get customer by ID"""
    customer = await db.customers.find_one({
        "id": customer_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    if not customer:
        raise NotFoundException(detail="Customer not found")
    
    # Get appointment count
    apt_count = await db.appointments.count_documents({
        "phone": customer["phone"],
        "organization_id": current_user.organization_id
    })
    customer["appointment_count"] = apt_count
    
    return CustomerResponse(**customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    update_data: CustomerUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update customer"""
    existing = await db.customers.find_one({
        "id": customer_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    if not existing:
        raise NotFoundException(detail="Customer not found")
    
    update_doc = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_doc[field] = value
    
    if not update_doc:
        apt_count = await db.appointments.count_documents({
            "phone": existing["phone"],
            "organization_id": current_user.organization_id
        })
        existing["appointment_count"] = apt_count
        return CustomerResponse(**existing)
    
    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.customers.update_one(
        {"id": customer_id, "organization_id": current_user.organization_id},
        {"$set": update_doc}
    )
    
    updated_customer = await db.customers.find_one({
        "id": customer_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    # Get appointment count
    apt_count = await db.appointments.count_documents({
        "phone": updated_customer["phone"],
        "organization_id": current_user.organization_id
    })
    updated_customer["appointment_count"] = apt_count
    
    logger.info(f"✅ Customer updated: {customer_id}")
    return CustomerResponse(**updated_customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Delete customer"""
    result = await db.customers.delete_one({
        "id": customer_id,
        "organization_id": current_user.organization_id
    })
    
    if result.deleted_count == 0:
        raise NotFoundException(detail="Customer not found")
    
    logger.info(f"🗑️ Customer deleted: {customer_id}")
    return None
