from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
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
from app.services.config_redaction import (
    count_unredacted_secret_lines,
    redact_configuration,
)
from app.services.diff_service import calculate_sha256, generate_config_diff
from app.tasks.backup_tasks import backup_all_devices
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/devices/{device_id}/run", response_model=BackupTriggerResponse)
async def trigger_device_backup(
    device_id: int,
    current_user=Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Trigger on-demand running configuration backup for a network switch."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device #{device_id} not found.",
        )

    try:
        credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}
        config_text = await automation_engine.fetch_running_config(device, credentials)
    except Exception:
        logger.exception("Manual backup failed for device %s.", device.hostname)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve configuration from the device.",
        )

    config_text, _redacted_lines = redact_configuration(config_text)
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
    current_user=Depends(require_role(["admin"])),
):
    """Queue configuration backups; device SSH operations run outside the API request."""
    try:
        task = backup_all_devices.delay(group_id=group_id, backup_type="bulk")
    except Exception:
        logger.exception("Unable to dispatch bulk configuration backup.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The background task queue is unavailable.",
        )
    return {"status": "dispatched", "task_id": task.id, "group_id": group_id}


@router.get("/devices/{device_id}", response_model=List[BackupHistoryItem])
async def list_device_backup_history(
    device_id: int,
    current_user=Depends(require_role(["admin", "operator", "viewer"])),
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


@router.get("/audit/redaction")
async def audit_legacy_backup_redaction(
    limit: int = Query(100, ge=1, le=500),
    before_id: Optional[int] = Query(None, ge=1),
    current_user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Report potentially unredacted legacy backups without returning their content."""
    query = (
        select(ConfigBackup, Device.hostname)
        .join(Device, ConfigBackup.device_id == Device.id)
        .order_by(ConfigBackup.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        query = query.where(ConfigBackup.id < before_id)
    rows = (await db.execute(query)).all()
    findings = []
    for backup, hostname in rows:
        finding_count = count_unredacted_secret_lines(backup.config_text)
        if finding_count:
            findings.append(
                {
                    "backup_id": backup.id,
                    "device_id": backup.device_id,
                    "hostname": hostname,
                    "version": backup.version,
                    "created_at": backup.created_at,
                    "potential_secret_lines": finding_count,
                }
            )
    return {
        "scanned": len(rows),
        "flagged_count": len(findings),
        "findings": findings,
        "next_before_id": rows[-1][0].id if len(rows) == limit else None,
    }


@router.get("/{backup_id}", response_model=ConfigBackupResponse)
async def get_backup_detail(
    backup_id: int,
    current_user=Depends(require_role(["admin", "operator"])),
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
    current_user=Depends(require_role(["admin", "operator"])),
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
