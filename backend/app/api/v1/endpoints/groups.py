from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.device_group import DeviceGroup
from app.schemas.device_group import DeviceGroupCreate, DeviceGroupResponse, DeviceGroupUpdate

router = APIRouter()


@router.get("", response_model=List[DeviceGroupResponse])
async def list_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all device groups."""
    result = await db.execute(select(DeviceGroup).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("", response_model=DeviceGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_in: DeviceGroupCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new device group."""
    existing = await db.execute(select(DeviceGroup).filter(DeviceGroup.name == group_in.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device group with name '{group_in.name}' already exists.",
        )

    group = DeviceGroup(**group_in.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/{group_id}", response_model=DeviceGroupResponse)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get device group details by ID."""
    group = await db.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device group #{group_id} not found.",
        )
    return group


@router.put("/{group_id}", response_model=DeviceGroupResponse)
async def update_group(
    group_id: int,
    group_in: DeviceGroupUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a device group."""
    group = await db.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device group #{group_id} not found.",
        )

    update_data = group_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != group.name:
        existing = await db.execute(select(DeviceGroup).filter(DeviceGroup.name == update_data["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device group with name '{update_data['name']}' already exists.",
            )

    for field, value in update_data.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a device group."""
    group = await db.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device group #{group_id} not found.",
        )

    await db.delete(group)
    await db.commit()
    return None
