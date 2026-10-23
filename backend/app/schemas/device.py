from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    hostname: str = Field(..., min_length=2, max_length=128, description="Device hostname")
    ip_address: str = Field(..., description="IPv4 or IPv6 management address")
    vendor: str = Field(..., description="Vendor: cisco, huawei, aruba, juniper, etc.")
    model: Optional[str] = Field(None, description="Hardware model e.g. Catalyst 9300")
    os_type: str = Field("cisco_ios", description="Netmiko device type, e.g. cisco_ios, huawei_vrp")
    os_version: Optional[str] = Field(None, description="Operating system firmware version")
    ssh_port: int = Field(22, ge=1, le=65535, description="SSH management port")
    is_active: bool = Field(True, description="Whether device is monitored")
    group_id: Optional[int] = Field(None, description="Associated device group ID")


class DeviceCreate(DeviceBase):
    # Optional credentials to be encrypted into Vault in Phase 2
    username: Optional[str] = Field(None, description="SSH management username")
    password: Optional[str] = Field(None, description="SSH management password")
    enable_secret: Optional[str] = Field(None, description="Enable secret if applicable")


class DeviceUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=2, max_length=128)
    ip_address: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    is_active: Optional[bool] = None
    status: Optional[str] = None
    group_id: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enable_secret: Optional[str] = None


class DeviceResponse(DeviceBase):
    id: int
    status: str
    last_backup_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
