from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.models.device import Device
from app.models.device_group import DeviceGroup
from app.models.port import Port
from app.schemas.port import PortCreate, PortResponse, PortUpdate
from app.tasks.port_discovery_tasks import dispatch_port_discovery
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/discovery/run", status_code=status.HTTP_202_ACCEPTED)
async def run_port_discovery(
    device_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    current_user=Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Queue read-only port/VLAN/MAC discovery for active enrolled devices."""
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail=f"Device #{device_id} not found.")
        if not device.is_active:
            raise HTTPException(status_code=409, detail="Inactive devices are not eligible for discovery.")
    if group_id is not None and await db.get(DeviceGroup, group_id) is None:
        raise HTTPException(status_code=404, detail=f"Device group #{group_id} not found.")
    try:
        task = dispatch_port_discovery.delay(device_id=device_id, group_id=group_id)
    except Exception:
        logger.exception("Unable to dispatch port discovery.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The background task queue is unavailable.",
        )
    return {"status": "dispatched", "task_id": task.id, "device_id": device_id, "group_id": group_id}


@router.get("", response_model=List[PortResponse])
async def list_ports(
    device_id: Optional[int] = Query(None, description="Filter by device ID"),
    vlan: Optional[int] = Query(None, description="Filter by VLAN"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (up/down)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_role(["admin", "operator", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve switch ports / interfaces with optional device_id or VLAN filtering."""
    query = select(Port)
    if device_id is not None:
        query = query.filter(Port.device_id == device_id)
    if vlan is not None:
        query = query.filter(Port.vlan == vlan)
    if status_filter:
        query = query.filter(Port.status == status_filter)

    query = query.order_by(Port.name, Port.id).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=PortResponse, status_code=status.HTTP_201_CREATED)
async def create_port(
    port_in: PortCreate,
    current_user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Add a new port/interface manually or via discovery."""
    device = await db.get(Device, port_in.device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent device #{port_in.device_id} not found.",
        )

    # Check if port with same name already exists on this device
    existing = await db.execute(
        select(Port).filter(Port.device_id == port_in.device_id, Port.name == port_in.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Port '{port_in.name}' already exists on device #{port_in.device_id}.",
        )

    port = Port(**port_in.model_dump())
    db.add(port)
    await db.commit()
    await db.refresh(port)
    return port


@router.get("/{port_id}", response_model=PortResponse)
async def get_port(
    port_id: int,
    current_user=Depends(require_role(["admin", "operator", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Get single port details."""
    port = await db.get(Port, port_id)
    if not port:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Port #{port_id} not found.",
        )
    return port


@router.put("/{port_id}", response_model=PortResponse)
async def update_port(
    port_id: int,
    port_in: PortUpdate,
    current_user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update port attributes (status, VLAN, description, speed, etc.)."""
    port = await db.get(Port, port_id)
    if not port:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Port #{port_id} not found.",
        )

    update_data = port_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(port, field, value)

    await db.commit()
    await db.refresh(port)
    return port


@router.delete("/{port_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_port(
    port_id: int,
    current_user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete port record."""
    port = await db.get(Port, port_id)
    if not port:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Port #{port_id} not found.",
        )

    await db.delete(port)
    await db.commit()
    return None
