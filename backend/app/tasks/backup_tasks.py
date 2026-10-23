from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import asyncio
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.vault import vault
from app.models.device import Device
from app.models.config_backup import ConfigBackup
from app.services.automation_engine import automation_engine
from app.services.backup_retention import prune_expired_backups
from app.services.config_redaction import redact_configuration
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

        config_text = asyncio.run(
            automation_engine.fetch_running_config(device, credentials)
        )
        result = _record_backup(session, device, config_text, backup_type)
        session.commit()
        return result


@celery_app.task(name="app.tasks.backup_tasks.backup_all_devices")
def backup_all_devices(group_id: Optional[int] = None, backup_type: str = "bulk") -> Dict[str, Any]:
    """Retrieve a multi-device backup batch concurrently through Nornir."""
    with Session(sync_engine) as session:
        query = select(Device).where(Device.is_active.is_(True))
        if group_id is not None:
            query = query.filter(Device.group_id == group_id)
        devices = session.execute(query).scalars().all()
        device_inputs = {
            f"device:{device.id}": (
                device,
                vault.decrypt_credentials(device.encrypted_credentials) or {},
            )
            for device in devices
        }
        outputs = asyncio.run(automation_engine.fetch_running_configs(device_inputs))
        successes = []
        failures = []
        for key, (device, _credentials) in device_inputs.items():
            config = outputs.get(key, {}).get("config")
            if config is None:
                failures.append({"device_id": device.id, "hostname": device.hostname})
                continue
            successes.append(
                _record_backup(session, device, config, backup_type)
            )
        session.commit()

        return {
            "status": "completed" if not failures else "completed_with_errors",
            "total_devices": len(devices),
            "succeeded": len(successes),
            "failed": len(failures),
            "results": successes,
            "failures": failures,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@celery_app.task(name="app.tasks.backup_tasks.dispatch_scheduled_backups")
def dispatch_scheduled_backups() -> Dict[str, Any]:
    return backup_all_devices(group_id=None, backup_type="scheduled")


@celery_app.task(name="app.tasks.backup_tasks.prune_expired_backups_task")
def prune_expired_backups_task() -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.BACKUP_RETENTION_DAYS)
    with Session(sync_engine) as session:
        deleted = prune_expired_backups(
            session,
            cutoff=cutoff,
            minimum_versions=settings.BACKUP_MIN_VERSIONS,
        )
        session.commit()
    return {
        "status": "success",
        "deleted": deleted,
        "retention_days": settings.BACKUP_RETENTION_DAYS,
        "minimum_versions": settings.BACKUP_MIN_VERSIONS,
        "cutoff": cutoff.isoformat(),
    }


def _record_backup(
    session: Session,
    device: Device,
    config_text: str,
    backup_type: str,
) -> Dict[str, Any]:
    config_text, _redacted_lines = redact_configuration(config_text)
    checksum = calculate_sha256(config_text)
    latest_backup = session.execute(
        select(ConfigBackup)
        .where(ConfigBackup.device_id == device.id)
        .order_by(desc(ConfigBackup.version))
        .limit(1)
    ).scalar_one_or_none()
    device.last_backup_at = datetime.now(timezone.utc)

    if latest_backup and latest_backup.checksum_sha256 == checksum:
        return {
            "status": "unchanged",
            "device_id": device.id,
            "hostname": device.hostname,
            "version": latest_backup.version,
            "checksum": checksum,
        }

    next_version = latest_backup.version + 1 if latest_backup else 1
    backup = ConfigBackup(
        device_id=device.id,
        config_text=config_text,
        checksum_sha256=checksum,
        version=next_version,
        backup_type=backup_type,
        created_at=datetime.now(timezone.utc),
    )
    session.add(backup)
    return {
        "status": "success",
        "device_id": device.id,
        "hostname": device.hostname,
        "version": next_version,
        "checksum": checksum,
    }
