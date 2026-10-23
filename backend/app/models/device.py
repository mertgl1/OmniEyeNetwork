from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hostname = Column(String(128), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    vendor = Column(String(50), nullable=False, index=True)  # cisco, huawei, aruba, juniper, etc.
    model = Column(String(100), nullable=True)
    device_type = Column(String(32), nullable=False, default="switch", server_default="switch", index=True)
    os_type = Column(String(50), nullable=False, default="cisco_ios")  # Netmiko device_type mapping
    os_version = Column(String(100), nullable=True)
    ssh_port = Column(Integer, nullable=False, default=22)
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="unknown")  # online, offline, error, unknown

    # Encrypted credentials for Vault integration (AES-256 encrypted username/password/enable_secret)
    encrypted_credentials = Column(Text, nullable=True)

    group_id = Column(Integer, ForeignKey("device_groups.id", ondelete="SET NULL"), nullable=True)

    last_backup_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    group = relationship("DeviceGroup", back_populates="devices")
    ports = relationship("Port", back_populates="device", cascade="all, delete-orphan")
    backups = relationship("ConfigBackup", back_populates="device", cascade="all, delete-orphan")
