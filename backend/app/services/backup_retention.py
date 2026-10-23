from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.config_backup import ConfigBackup


def prune_expired_backups(
    session: Session,
    cutoff: datetime,
    minimum_versions: int = 10,
) -> int:
    """Delete expired backups while retaining each device's newest versions."""
    if minimum_versions < 1:
        raise ValueError("minimum_versions must be at least one.")

    device_ids = session.execute(
        select(ConfigBackup.device_id).distinct()
    ).scalars().all()
    deleted_count = 0
    for device_id in device_ids:
        protected_ids = (
            select(ConfigBackup.id)
            .where(ConfigBackup.device_id == device_id)
            .order_by(
                ConfigBackup.version.desc(),
                ConfigBackup.created_at.desc(),
                ConfigBackup.id.desc(),
            )
            .limit(minimum_versions)
        )
        result = session.execute(
            delete(ConfigBackup).where(
                ConfigBackup.device_id == device_id,
                ConfigBackup.created_at < cutoff,
                ConfigBackup.id.not_in(protected_ids),
            )
        )
        deleted_count += result.rowcount or 0
    return deleted_count
