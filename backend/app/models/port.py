from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Port(Base):
    __tablename__ = "ports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(64), nullable=False, index=True)  # e.g. GigabitEthernet0/1, Eth1/1
    description = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="down")  # operational status: up, down
    admin_status = Column(String(20), nullable=False, default="down")  # admin status: up, down
    vlan = Column(Integer, nullable=True)
    mac_address = Column(String(32), nullable=True, index=True)
    speed = Column(String(32), nullable=True)  # 10M, 100M, 1G, 10G, Auto
    duplex = Column(String(32), nullable=True)  # Full, Half, Auto

    last_change = Column(DateTime(timezone=True), nullable=True)
    last_discovered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    device = relationship("Device", back_populates="ports")
