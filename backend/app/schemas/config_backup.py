from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ConfigBackupBase(BaseModel):
    device_id: int
    config_text: str = Field(..., description="Running configuration text")
    checksum_sha256: str = Field(..., description="SHA-256 hash of configuration")
    version: int = Field(1, description="Sequential backup version")
    backup_type: str = Field("scheduled", description="Backup trigger: manual, scheduled, trigger")


class ConfigBackupResponse(ConfigBackupBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
