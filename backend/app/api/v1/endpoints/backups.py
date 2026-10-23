from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.vault import vault
from app.models.device import Device
from app.models.config_backup import ConfigBackup
from app.schemas.config_backup import (
    BackupHistoryItem,
    BackupTriggerResponse,
    ConfigBackupResponse,
    DiffResponse,
)
from app.services.automation_engine import automation_engine
from app.services.diff_service import calculate_sha256, generate_config_diff

router = APIRouter()


@router.post("/devices/{device_id}/run", response_model=BackupTriggerResponse)
async def trigger_device_backup(
    device_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger on-demand running configuration backup for a network switch."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device #{device_id} not found.",
        )

    # Decrypt credentials via Vault
    credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}

    # Fetch running-config using multi-vendor automation engine
    try:
        config_text = await automation_engine.fetch_running_config(device, credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to communicate with device: {str(e)}",
        )

    checksum = calculate_sha256(config_text)

    # Check previous latest backup
    latest_res = await db.execute(
        select(ConfigBackup)
        .filter(ConfigBackup.device_id == device_id)
        .order_by(desc(ConfigBackup.version))
        .limit(1)
    )
    latest_backup = latest_res.scalar_one_or_none()

    device.last_backup_at = datetime.now(timezone.utc)

    # Deduplication check
    if latest_backup and latest_backup.checksum_sha256 == checksum:
        await db.commit()
        return BackupTriggerResponse(
            status="unchanged",
            device_id=device.id,
            hostname=device.hostname,
            version=latest_backup.version,
            message="Configuration is identical to latest backup. No duplicate entry created.",
        )

    next_version = (latest_backup.version + 1) if latest_backup else 1
    new_backup = ConfigBackup(
        device_id=device.id,
        config_text=config_text,
        checksum_sha256=checksum,
        version=next_version,
        backup_type="manual",
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_backup)
    await db.commit()
    await db.refresh(new_backup)

    return BackupTriggerResponse(
        status="success",
        device_id=device.id,
        hostname=device.hostname,
        version=next_version,
        message=f"Successfully backed up {device.hostname} (Version {next_version}).",
    )


@router.post("/run-all")
async def trigger_bulk_backup(
    group_id: Optional[int] = Query(None, description="Optional filter by device group"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger parallel configuration backups across all active switches or a group."""
    query = select(Device).filter(Device.is_active == True)  # noqa: E712
    if group_id:
        query = query.filter(Device.group_id == group_id)

    res = await db.execute(query)
    devices = res.scalars().all()

    # In production, dispatch to Celery background task:
    # task = backup_all_devices.delay(group_id=group_id)
    # return {"status": "dispatched", "task_id": task.id, "device_count": len(devices)}

    # For fast synchronous API feedback:
    results = []
    for dev in devices:
        creds = vault.decrypt_credentials(dev.encrypted_credentials) or {}
        cfg = await automation_engine.fetch_running_config(dev, creds)
        chk = calculate_sha256(cfg)

        lat_res = await db.execute(
            select(ConfigBackup)
            .filter(ConfigBackup.device_id == dev.id)
            .order_by(desc(ConfigBackup.version))
            .limit(1)
        )
        lat = lat_res.scalar_one_or_none()
        dev.last_backup_at = datetime.now(timezone.utc)

        if lat and lat.checksum_sha256 == chk:
            results.append({"device_id": dev.id, "hostname": dev.hostname, "status": "unchanged", "version": lat.version})
        else:
            ver = (lat.version + 1) if lat else 1
            nb = ConfigBackup(
                device_id=dev.id,
                config_text=cfg,
                checksum_sha256=chk,
                version=ver,
                backup_type="bulk",
            )
            db.add(nb)
            results.append({"device_id": dev.id, "hostname": dev.hostname, "status": "backed_up", "version": ver})

    await db.commit()
    return {"total_processed": len(devices), "results": results}


@router.get("/devices/{device_id}", response_model=List[BackupHistoryItem])
async def list_device_backup_history(
    device_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List historical backup snapshots for a specific device ordered by latest version."""
    query = (
        select(ConfigBackup)
        .filter(ConfigBackup.device_id == device_id)
        .order_by(desc(ConfigBackup.version))
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{backup_id}", response_model=ConfigBackupResponse)
async def get_backup_detail(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full configuration text for a specific backup ID."""
    backup = await db.get(ConfigBackup, backup_id)
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration backup #{backup_id} not found.",
        )
    return backup


@router.get("/diff/compare", response_model=DiffResponse)
async def compare_backup_versions(
    backup_id_old: int = Query(..., description="Earlier backup ID to compare from"),
    backup_id_new: int = Query(..., description="Later backup ID to compare to"),
    db: AsyncSession = Depends(get_db),
):
    """Generate line-by-line Unix Unified Diff comparison between two configuration backups."""
    old_b = await db.get(ConfigBackup, backup_id_old)
    if not old_b:
        raise HTTPException(status_code=404, detail=f"Backup #{backup_id_old} not found.")

    new_b = await db.get(ConfigBackup, backup_id_new)
    if not new_b:
        raise HTTPException(status_code=404, detail=f"Backup #{backup_id_new} not found.")

    diff_result = generate_config_diff(
        old_config=old_b.config_text,
        new_config=new_b.config_text,
        fromfile=f"Version {old_b.version} ({old_b.created_at.strftime('%Y-%m-%d %H:%M')})",
        tofile=f"Version {new_b.version} ({new_b.created_at.strftime('%Y-%m-%d %H:%M')})",
    )

    return DiffResponse(
        backup_id_old=old_b.id,
        backup_id_new=new_b.id,
        version_old=old_b.version,
        version_new=new_b.version,
        has_changes=diff_result["has_changes"],
        lines_added=diff_result["lines_added"],
        lines_removed=diff_result["lines_removed"],
        diff_text=diff_result["diff_text"],
        diff_lines=diff_result["diff_lines"],
    )
