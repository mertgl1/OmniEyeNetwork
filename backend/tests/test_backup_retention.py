from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.models.device_group import DeviceGroup
from app.services.backup_retention import prune_expired_backups


def test_retention_deletes_expired_backups_but_keeps_each_devices_minimum():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            DeviceGroup.__table__,
            Device.__table__,
            ConfigBackup.__table__,
        ],
    )
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    with Session(engine) as session:
        first = Device(
            hostname="retention-12",
            ip_address="192.0.2.20",
            vendor="Cisco",
            os_type="cisco_ios",
            ssh_port=22,
            is_active=True,
            status="unknown",
        )
        second = Device(
            hostname="retention-5",
            ip_address="192.0.2.21",
            vendor="Cisco",
            os_type="cisco_ios",
            ssh_port=22,
            is_active=True,
            status="unknown",
        )
        session.add_all([first, second])
        session.flush()
        for device, versions in ((first, 12), (second, 5)):
            session.add_all(
                [
                    ConfigBackup(
                        device_id=device.id,
                        config_text=f"hostname {device.hostname} version {version}",
                        checksum_sha256=f"{version:064x}",
                        version=version,
                        backup_type="scheduled",
                        created_at=now - timedelta(days=60),
                    )
                    for version in range(1, versions + 1)
                ]
            )
        session.commit()

        deleted = prune_expired_backups(session, cutoff=cutoff, minimum_versions=10)
        session.commit()

        first_versions = session.execute(
            select(ConfigBackup.version)
            .where(ConfigBackup.device_id == first.id)
            .order_by(ConfigBackup.version)
        ).scalars().all()
        second_versions = session.execute(
            select(ConfigBackup.version)
            .where(ConfigBackup.device_id == second.id)
            .order_by(ConfigBackup.version)
        ).scalars().all()

    assert deleted == 2
    assert first_versions == list(range(3, 13))
    assert second_versions == list(range(1, 6))
    engine.dispose()
