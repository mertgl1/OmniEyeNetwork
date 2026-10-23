from datetime import datetime
from typing import Any, Dict, List, Optional
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


class BackupHistoryItem(BaseModel):
    id: int
    device_id: int
    version: int
    checksum_sha256: str
    backup_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiffResponse(BaseModel):
    backup_id_old: int
    backup_id_new: int
    version_old: int
    version_new: int
    has_changes: bool
    lines_added: int
    lines_removed: int
    diff_text: str
    diff_lines: List[Dict[str, str]]


class BackupTriggerResponse(BaseModel):
    status: str
    task_id: Optional[str] = None
    message: str
    device_id: int
    hostname: Optional[str] = None
    version: Optional[int] = None
