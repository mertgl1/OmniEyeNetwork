import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import require_role
from app.services.vendor_profiles import (
    VendorCommandProfile,
    list_supported_vendors,
    list_vendor_catalog,
    get_vendor_profile,
    VENDOR_PROFILES,
)
from app.schemas.device import IdentityProbeRequest, IdentityProbeResponse
from app.services.device_identity import IdentityProbeError, detect_device_identity

router = APIRouter()
logger = logging.getLogger(__name__)


class VendorCatalogEntry(BaseModel):
    vendor_key: str
    vendor_name: str
    os_type: Optional[str] = None
    supported_models: List[str]
    supported: bool
    support_note: Optional[str] = None
    device_types: List[str]
    models_by_device_type: dict[str, List[str]]


@router.get("", response_model=List[VendorCommandProfile])
async def get_all_vendors():
    """Retrieve full catalog of supported network hardware vendors, models and command matrices."""
    return list_supported_vendors()


@router.get("/catalog", response_model=List[VendorCatalogEntry])
async def get_vendor_catalog():
    """List supported vendor profiles and explicitly catalog-only vendors."""
    return list_vendor_catalog()


@router.post("/detect", response_model=IdentityProbeResponse)
async def detect_vendor_identity(
    probe: IdentityProbeRequest,
    current_user=Depends(require_role(["admin"])),
):
    """Run an admin-triggered, read-only SSH platform detection probe."""
    try:
        result = await asyncio.to_thread(
            detect_device_identity,
            str(probe.ip_address),
            probe.ssh_port,
            probe.username,
            probe.password,
            probe.enable_secret,
        )
    except IdentityProbeError as exc:
        logger.info("Device identity probe returned an expected failure for %s.", current_user.username)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning(
            "Device identity probe failed for %s with error type %s.",
            current_user.username,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SSH identity probe failed. Check device reachability and credentials.",
        ) from None
    logger.info(
        "Device identity probe succeeded for %s with profile %s.",
        current_user.username,
        result["os_type"],
    )
    return result


@router.get("/{vendor_key}", response_model=VendorCommandProfile)
async def get_vendor_details(vendor_key: str):
    """Get specific CLI command syntax and driver mapping for a vendor/OS family."""
    clean_key = vendor_key.lower().strip()
    profile = get_vendor_profile(vendor=clean_key, os_type=clean_key)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor profile '{vendor_key}' not found.",
        )
    return profile
