from fastapi import APIRouter
from app.api.v1.endpoints import auth, devices, groups, health, ports

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health & Status"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & RBAC"])
api_router.include_router(groups.router, prefix="/groups", tags=["Device Groups"])
api_router.include_router(devices.router, prefix="/devices", tags=["Network Devices"])
api_router.include_router(ports.router, prefix="/ports", tags=["Switch Ports"])
