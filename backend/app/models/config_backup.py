from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ConfigBackup(Base):
    __tablename__ = "config_backups"
    __table_args__ = (
        Index(
            "ix_config_backups_device_created_version",
            "device_id",
            "created_at",
            "version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    config_text = Column(Text, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    backup_type = Column(String(32), nullable=False, default="scheduled")  # manual, scheduled, trigger
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    device = relationship("Device", back_populates="backups")
