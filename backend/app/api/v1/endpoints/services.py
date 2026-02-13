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
from pydantic import BaseModel, Field

from ....core.dependencies import get_current_user, get_current_admin_user, UserInDB
from ....core.exceptions import NotFoundException, ConflictException
from ....infrastructure.database.mongodb import get_db
from ...schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class ServiceReorderRequest(BaseModel):
    service_ids: List[str] = Field(..., min_length=1)


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_services(
    payload: ServiceReorderRequest,
    current_user: UserInDB = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    service_ids = payload.service_ids
    unique_ids = list(dict.fromkeys(service_ids))

    existing = await db.services.find(
        {"organization_id": current_user.organization_id, "id": {"$in": unique_ids}},
        {"_id": 0, "id": 1}
    ).to_list(length=2000)
    existing_ids = {s.get("id") for s in existing}
    missing = [sid for sid in unique_ids if sid not in existing_ids]
    if missing:
        raise HTTPException(status_code=400, detail="Invalid service_ids")

    now = datetime.now(timezone.utc).isoformat()
    for idx, sid in enumerate(unique_ids):
        await db.services.update_one(
            {"organization_id": current_user.organization_id, "id": sid},
            {"$set": {"order": idx, "updated_at": now}}
        )

    logger.info(f"↕️ Reordered {len(unique_ids)} services for org {current_user.organization_id}")
    return None


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

    def sort_key(svc: dict):
        order = svc.get("order")
        return (
            order if isinstance(order, int) else 1_000_000,
            svc.get("created_at") or "",
            svc.get("name") or "",
        )

    services_sorted = sorted(services, key=sort_key)
    logger.info(f"📋 Listed {len(services_sorted)} services for org {current_user.organization_id}")
    return [ServiceResponse(**service_doc) for service_doc in services_sorted]


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

    order_value = service.order
    if order_value is None:
        last = await db.services.find(
            {"organization_id": current_user.organization_id},
            {"_id": 0, "order": 1}
        ).sort("order", -1).limit(1).to_list(length=1)
        last_order = None
        if last:
            last_order = last[0].get("order")
        order_value = (last_order + 1) if isinstance(last_order, int) else 0

    service_doc = {
        "id": service_id,
        "organization_id": current_user.organization_id,
        "name": service.name,
        "price": service.price,
        "duration": service.duration,
        "order": order_value,
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
