from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.device import Device
from app.models.device_group import DeviceGroup
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate

router = APIRouter()


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    group_id: Optional[int] = Query(None, description="Filter by device group"),
    vendor: Optional[str] = Query(None, description="Filter by vendor (cisco, huawei, aruba, etc.)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List network devices with optional filtering and pagination."""
    query = select(Device)
    if group_id is not None:
        query = query.filter(Device.group_id == group_id)
    if vendor:
        query = query.filter(Device.vendor.ilike(f"%{vendor}%"))
    if status_filter:
        query = query.filter(Device.status == status_filter)
    if is_active is not None:
        query = query.filter(Device.is_active == is_active)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device_in: DeviceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a new network device to OmniEye inventory."""
    # Check if hostname already exists
    existing = await db.execute(select(Device).filter(Device.hostname == device_in.hostname))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device with hostname '{device_in.hostname}' already exists.",
        )

    # Validate group_id if provided
    if device_in.group_id:
        group = await db.get(DeviceGroup, device_in.group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device group #{device_in.group_id} does not exist.",
            )

    device_data = device_in.model_dump(exclude={"username", "password", "enable_secret"})
    # TODO in Phase 2: Encrypt credentials with Vault AES-256 and store in encrypted_credentials
    device = Device(**device_data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get device details by ID."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device #{device_id} not found.",
        )
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    device_in: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update device configuration and inventory details."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device #{device_id} not found.",
        )

    update_data = device_in.model_dump(exclude_unset=True, exclude={"username", "password", "enable_secret"})

    # Check hostname collision
    if "hostname" in update_data and update_data["hostname"] != device.hostname:
        existing = await db.execute(select(Device).filter(Device.hostname == update_data["hostname"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device with hostname '{update_data['hostname']}' already exists.",
            )

    # Validate group if changed
    if "group_id" in update_data and update_data["group_id"] is not None:
        group = await db.get(DeviceGroup, update_data["group_id"])
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device group #{update_data['group_id']} does not exist.",
            )

    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a device and its related port and backup history."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device #{device_id} not found.",
        )

    await db.delete(device)
    await db.commit()
    return None
