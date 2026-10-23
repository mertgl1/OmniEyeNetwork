from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DeviceGroupBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Unique name of the device group")
    description: Optional[str] = Field(None, description="Detailed description or location info")


class DeviceGroupCreate(DeviceGroupBase):
    pass


class DeviceGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None


class DeviceGroupResponse(DeviceGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
