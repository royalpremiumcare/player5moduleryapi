"""
API v1 Router
Collects all v1 endpoints
"""
from fastapi import APIRouter
from .endpoints import auth

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# TODO: Add more routers as we create them
# api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
# api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
# api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
# api_router.include_router(services.router, prefix="/services", tags=["Services"])
