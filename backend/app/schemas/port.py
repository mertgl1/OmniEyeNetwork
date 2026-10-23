from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PortBase(BaseModel):
    name: str = Field(..., description="Interface name e.g. GigabitEthernet1/0/1")
    description: Optional[str] = Field(None, description="Interface description / alias")
    status: str = Field("down", description="Operational status: up / down")
    admin_status: str = Field("down", description="Admin status: up / down")
    vlan: Optional[int] = Field(None, ge=1, le=4094, description="Access VLAN or native VLAN")
    mac_address: Optional[str] = Field(None, description="Connected MAC address")
    speed: Optional[str] = Field(None, description="Port speed e.g. 1Gbps, 10Gbps")
    duplex: Optional[str] = Field(None, description="Duplex mode: Full, Half, Auto")


class PortCreate(PortBase):
    device_id: int = Field(..., description="Device ID this port belongs to")


class PortUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    admin_status: Optional[str] = None
    vlan: Optional[int] = Field(None, ge=1, le=4094)
    mac_address: Optional[str] = None
    speed: Optional[str] = None
    duplex: Optional[str] = None


class PortResponse(PortBase):
    id: int
    device_id: int
    last_change: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
