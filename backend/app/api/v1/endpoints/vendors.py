from typing import List
from fastapi import APIRouter, HTTPException, status
from app.services.vendor_profiles import (
    VendorCommandProfile,
    list_supported_vendors,
    get_vendor_profile,
    VENDOR_PROFILES,
)

router = APIRouter()


@router.get("", response_model=List[VendorCommandProfile])
async def get_all_vendors():
    """Retrieve full catalog of supported network hardware vendors, models and command matrices."""
    return list_supported_vendors()


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
