"""
Services Endpoints
CRUD operations for services
"""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import List
import uuid
import logging

from ....core.dependencies import get_current_user, get_current_admin_user, UserInDB
from ....core.exceptions import NotFoundException, ConflictException
from ....infrastructure.database.mongodb import get_db
from ...schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[ServiceResponse])
async def list_services(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """List all services for organization"""
    services = await db.services.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    ).to_list(length=1000)
    
    logger.info(f"📋 Listed {len(services)} services for org {current_user.organization_id}")
    return [ServiceResponse(**svc) for svc in services]


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    service: ServiceCreate,
    current_user: UserInDB = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create new service (Admin only)"""
    # Check for duplicate name
    existing = await db.services.find_one({
        "name": service.name,
        "organization_id": current_user.organization_id
    })
    
    if existing:
        raise ConflictException(detail="Service with this name already exists")
    
    service_id = str(uuid.uuid4())
    service_doc = {
        "id": service_id,
        "organization_id": current_user.organization_id,
        "name": service.name,
        "price": service.price,
        "duration": service.duration,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.services.insert_one(service_doc)
    logger.info(f"✅ Service created: {service.name} (id: {service_id})")
    
    return ServiceResponse(**service_doc)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get service by ID"""
    service = await db.services.find_one({
        "id": service_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    if not service:
        raise NotFoundException(detail="Service not found")
    
    return ServiceResponse(**service)


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    update_data: ServiceUpdate,
    current_user: UserInDB = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update service (Admin only)"""
    existing = await db.services.find_one({
        "id": service_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    if not existing:
        raise NotFoundException(detail="Service not found")
    
    update_doc = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_doc[field] = value
    
    if not update_doc:
        return ServiceResponse(**existing)
    
    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.services.update_one(
        {"id": service_id, "organization_id": current_user.organization_id},
        {"$set": update_doc}
    )
    
    updated_service = await db.services.find_one({
        "id": service_id,
        "organization_id": current_user.organization_id
    }, {"_id": 0})
    
    logger.info(f"✅ Service updated: {service_id}")
    return ServiceResponse(**updated_service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str,
    current_user: UserInDB = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Delete service (Admin only)"""
    result = await db.services.delete_one({
        "id": service_id,
        "organization_id": current_user.organization_id
    })
    
    if result.deleted_count == 0:
        raise NotFoundException(detail="Service not found")
    
    logger.info(f"🗑️ Service deleted: {service_id}")
    return None
