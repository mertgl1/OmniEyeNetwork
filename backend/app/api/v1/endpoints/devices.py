import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.core.vault import vault
from app.models.device import Device
from app.models.device_group import DeviceGroup
from app.models.port import Port
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from app.services.automation_engine import automation_engine
from app.services.config_redaction import redact_configuration
from app.services.interface_config import (
    UnsupportedInterfaceConfig,
    extract_interface_config,
    supports_interface_config,
)
from app.services.vendor_profiles import get_vendor_profile, is_supported_vendor_profile

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    group_id: Optional[int] = Query(None, description="Filter by device group"),
    device_type: Optional[Literal["switch", "router", "firewall", "access_point", "other"]] = Query(
        None,
        description="Filter by inventory category",
    ),
    vendor: Optional[str] = Query(None, description="Filter by vendor (cisco, huawei, aruba, etc.)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(require_role(["admin", "operator", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """List network devices with optional filtering and pagination."""
    query = select(Device)
    if group_id is not None:
        query = query.filter(Device.group_id == group_id)
    if device_type is not None:
        query = query.filter(Device.device_type == device_type)
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
    current_user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Add a new network device to OmniEye inventory."""
    if not is_supported_vendor_profile(device_in.vendor, device_in.os_type):
        raise HTTPException(
            status_code=422,
            detail="Select a supported vendor and matching Netmiko OS profile.",
        )

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

    # Encrypt credentials with AES-256 Vault if supplied
    cred_dict = {}
    if device_in.username:
        cred_dict["username"] = device_in.username
    if device_in.password:
        cred_dict["password"] = device_in.password
    if device_in.enable_secret:
        cred_dict["enable_secret"] = device_in.enable_secret

    if cred_dict:
        device_data["encrypted_credentials"] = vault.encrypt_credentials(cred_dict)

    device = Device(**device_data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    current_user=Depends(require_role(["admin", "operator", "viewer"])),
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


@router.get("/{device_id}/ports/{port_id}/live-config")
async def get_live_port_config(
    device_id: int,
    port_id: int,
    current_user=Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a redacted configuration stanza for one enrolled device interface."""
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device #{device_id} not found.")
    result = await db.execute(
        select(Port).where(Port.id == port_id, Port.device_id == device_id)
    )
    port = result.scalar_one_or_none()
    if port is None:
        raise HTTPException(
            status_code=404,
            detail=f"Port #{port_id} was not found on device #{device_id}.",
        )
    profile = get_vendor_profile(device.vendor, device.os_type, device.model)
    if not supports_interface_config(profile.vendor_key):
        raise HTTPException(
            status_code=422,
            detail=(
                "Port-level configuration is not supported for vendor profile "
                f"{profile.vendor_key}."
            ),
        )

    try:
        credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}
        full_config = await automation_engine.fetch_running_config(device, credentials)
    except Exception:
        device.status = "error"
        await db.commit()
        logger.exception(
            "Live interface configuration request failed for device %s.",
            device.hostname,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve configuration from the device.",
        ) from None
    device.status = "online"
    await db.commit()
    try:
        config_text = extract_interface_config(
            full_config,
            port.name,
            profile.vendor_key,
        )
    except UnsupportedInterfaceConfig as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    config_text, _redacted_lines = redact_configuration(config_text)

    logger.info(
        "Live interface configuration retrieved by %s for device %s port %s.",
        current_user.username,
        device.hostname,
        port.name,
    )
    return {
        "device_id": device.id,
        "port_id": port.id,
        "interface_name": port.name,
        "config_text": config_text,
        "retrieved_at": datetime.now(timezone.utc),
    }


@router.get("/{device_id}/live-config")
async def get_live_config(
    device_id: int,
    current_user=Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a fresh running configuration from an enrolled device."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device #{device_id} not found.")
    try:
        credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}
        config_text = await automation_engine.fetch_running_config(device, credentials)
        config_text, _redacted_lines = redact_configuration(config_text)
    except Exception:
        device.status = "error"
        await db.commit()
        logger.exception("Live configuration request failed for device %s.", device.hostname)
        raise HTTPException(status_code=502, detail="Unable to retrieve live configuration from the device.")
    device.status = "online"
    await db.commit()
    logger.info("Live configuration retrieved by %s for device %s.", current_user.username, device.hostname)
    return {
        "device_id": device.id,
        "hostname": device.hostname,
        "config_text": config_text,
        "retrieved_at": datetime.now(timezone.utc),
    }


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    device_in: DeviceUpdate,
    current_user=Depends(require_role(["admin"])),
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

    if "vendor" in update_data or "os_type" in update_data:
        next_vendor = update_data.get("vendor", device.vendor)
        next_os_type = update_data.get("os_type", device.os_type)
        if not is_supported_vendor_profile(next_vendor, next_os_type):
            raise HTTPException(
                status_code=422,
                detail="Select a supported vendor and matching Netmiko OS profile.",
            )

    # Update Vault credentials if any credential fields are explicitly updated
    if any(k in device_in.model_fields_set for k in ("username", "password", "enable_secret")):
        existing_creds = vault.decrypt_credentials(device.encrypted_credentials) or {}
        if device_in.username is not None:
            existing_creds["username"] = device_in.username
        if device_in.password is not None:
            existing_creds["password"] = device_in.password
        if device_in.enable_secret is not None:
            existing_creds["enable_secret"] = device_in.enable_secret

        if existing_creds:
            update_data["encrypted_credentials"] = vault.encrypt_credentials(existing_creds)

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
    current_user=Depends(require_role(["admin"])),
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
