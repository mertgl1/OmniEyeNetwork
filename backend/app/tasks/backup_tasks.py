from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.vault import vault
from app.models.device import Device
from app.models.config_backup import ConfigBackup
from app.services.automation_engine import automation_engine
from app.services.diff_service import calculate_sha256

# Synchronous engine for Celery background workers
sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)


@celery_app.task(name="app.tasks.backup_tasks.backup_single_device")
def backup_single_device(device_id: int, backup_type: str = "manual") -> Dict[str, Any]:
    """Celery worker task: Asynchronously retrieves running-config for a device,
    computes SHA-256, and records a versioned backup if changed.
    """
    with Session(sync_engine) as session:
        device = session.get(Device, device_id)
        if not device:
            return {"status": "error", "message": f"Device #{device_id} not found."}

        # Decrypt credentials via Vault
        credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}

        # Fetch config (running sync in Celery worker thread)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            config_text = loop.run_until_complete(
                automation_engine.fetch_running_config(device, credentials)
            )
        finally:
            loop.close()

        checksum = calculate_sha256(config_text)

        # Get the latest backup for this device
        latest_backup = session.execute(
            select(ConfigBackup)
            .filter(ConfigBackup.device_id == device_id)
            .order_by(desc(ConfigBackup.version))
            .limit(1)
        ).scalar_one_or_none()

        device.last_backup_at = datetime.now(timezone.utc)

        # Check if config is identical to previous version
        if latest_backup and latest_backup.checksum_sha256 == checksum:
            session.commit()
            return {
                "status": "unchanged",
                "device_id": device.id,
                "hostname": device.hostname,
                "version": latest_backup.version,
                "checksum": checksum,
                "message": "Configuration identical to latest backup. Skipped duplicate entry.",
            }

        # New version creation
        next_version = (latest_backup.version + 1) if latest_backup else 1
        new_backup = ConfigBackup(
            device_id=device.id,
            config_text=config_text,
            checksum_sha256=checksum,
            version=next_version,
            backup_type=backup_type,
            created_at=datetime.now(timezone.utc),
        )
        session.add(new_backup)
        session.commit()
        session.refresh(new_backup)

        return {
            "status": "success",
            "backup_id": new_backup.id,
            "device_id": device.id,
            "hostname": device.hostname,
            "version": next_version,
            "checksum": checksum,
            "message": f"Successfully backed up {device.hostname} (Version {next_version}).",
        }


@celery_app.task(name="app.tasks.backup_tasks.backup_all_devices")
def backup_all_devices(group_id: Optional[int] = None) -> Dict[str, Any]:
    """Celery worker task: Triggers backup tasks for all active devices in parallel."""
    with Session(sync_engine) as session:
        query = select(Device).filter(Device.is_active == True)  # noqa: E712
        if group_id:
            query = query.filter(Device.group_id == group_id)

        devices = session.execute(query).scalars().all()
        results = []

        for device in devices:
            # Execute inline or queue subtask
            res = backup_single_device(device.id, backup_type="scheduled")
            results.append(res)

        return {
            "total_devices": len(devices),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
