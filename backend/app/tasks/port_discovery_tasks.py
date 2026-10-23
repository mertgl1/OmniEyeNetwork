from typing import Any, Dict, Optional

from celery import group
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.device import Device
from app.services.port_discovery import sync_device_ports_sync

sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)


@celery_app.task(name="app.tasks.port_discovery_tasks.sync_device_ports")
def sync_device_ports_task(device_id: int) -> Dict[str, Any]:
    with Session(sync_engine) as session:
        device = session.get(Device, device_id)
        if device is None:
            return {"status": "error", "device_id": device_id, "message": "Device not found."}
        if not device.is_active:
            return {"status": "skipped", "device_id": device_id, "message": "Device is inactive."}
        count = sync_device_ports_sync(session, device)
        return {"status": "success", "device_id": device_id, "ports_discovered": count}


@celery_app.task(name="app.tasks.port_discovery_tasks.dispatch_port_discovery")
def dispatch_port_discovery(
    device_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> Dict[str, Any]:
    with Session(sync_engine) as session:
        query = select(Device.id).where(Device.is_active.is_(True))
        if device_id is not None:
            query = query.where(Device.id == device_id)
        if group_id is not None:
            query = query.where(Device.group_id == group_id)
        device_ids = session.execute(query).scalars().all()

    result = group(sync_device_ports_task.s(current_id) for current_id in device_ids).apply_async()
    return {
        "status": "dispatched",
        "device_count": len(device_ids),
        "group_task_id": result.id,
    }
