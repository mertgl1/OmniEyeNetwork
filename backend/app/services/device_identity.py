"""Explicit, read-only SSH identity detection for device enrollment."""

import ipaddress
import re
from typing import Optional

from netmiko import ConnectHandler, SSHDetect
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.core.config import settings
from app.services.vendor_profiles import VENDOR_PROFILES, VendorCommandProfile


NETMIKO_PROFILE_MAP = {
    "cisco_ios": "cisco_ios",
    "cisco_xe": "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "cisco_xr": "cisco_xr",
    "huawei": "huawei_vrp",
    "aruba_aoscx": "aruba_os",
    "hp_procurve": "hp_procurve",
    "hp_comware": "hp_comware",
    "h3c_comware": "hp_comware",
    "juniper_junos": "juniper_junos",
    "dell_os10": "dell_os10",
    "extreme_exos": "extreme_exos",
    "mikrotik_routeros": "mikrotik_routeros",
    "fortinet": "fortinet",
}


class IdentityProbeError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def validate_probe_address(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError("Enter a literal IPv4 or IPv6 management address.") from exc

    mapped_address = parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) else None
    checked_address = mapped_address or parsed
    if (
        checked_address.is_loopback
        or checked_address.is_link_local
        or checked_address.is_multicast
        or checked_address.is_unspecified
        or checked_address.is_reserved
    ):
        raise ValueError("Loopback, link-local, multicast, reserved, and unspecified addresses cannot be probed.")
    return str(parsed)


def _connection_parameters(
    address: str,
    port: int,
    username: str,
    password: str,
    enable_secret: Optional[str],
    device_type: str,
) -> dict:
    return {
        "device_type": device_type,
        "host": address,
        "port": port,
        "username": username,
        "password": password,
        "secret": enable_secret or "",
        "conn_timeout": 8,
        "auth_timeout": 8,
        "banner_timeout": 8,
        "timeout": 8,
        "session_timeout": 30,
        "read_timeout_override": 8,
        "fast_cli": True,
        "ssh_strict": settings.SSH_STRICT_HOST_KEY_CHECKING,
        "system_host_keys": settings.SSH_STRICT_HOST_KEY_CHECKING,
        "allow_agent": False,
        "use_keys": False,
    }


def _extract_model(output: str, profile: VendorCommandProfile) -> Optional[str]:
    folded_output = output.casefold()
    for model in sorted(profile.supported_models, key=len, reverse=True):
        if model.casefold() in folded_output:
            return model

    for model in profile.supported_models:
        series = re.search(r"\d{3,5}", model)
        if series and re.search(rf"(?<!\d){series.group()}(?!\d)", output):
            return model
    return None


def _extract_os_version(output: str) -> Optional[str]:
    match = re.search(
        r"(?:software\s+version|firmware\s+version|version|release)\s*[:=]?\s*"
        r"([A-Za-z0-9][A-Za-z0-9._()+/-]{1,39})",
        output,
        flags=re.IGNORECASE,
    )
    return match.group(1).rstrip(".,") if match else None


def detect_device_identity(
    address: str,
    port: int,
    username: str,
    password: str,
    enable_secret: Optional[str] = None,
) -> dict:
    """Detect a supported Netmiko platform and query its read-only version command."""
    normalized_address = validate_probe_address(address)
    detector = None
    connection = None
    try:
        detector = SSHDetect(
            **_connection_parameters(
                normalized_address,
                port,
                username,
                password,
                enable_secret,
                "autodetect",
            )
        )
        detected_type = detector.autodetect()
        profile_key = NETMIKO_PROFILE_MAP.get(detected_type or "")
        if profile_key is None:
            raise IdentityProbeError(
                "The device type was not recognized as a supported profile. "
                "Select a profile manually or continue without detection.",
                status_code=422,
            )

        profile = VENDOR_PROFILES[profile_key]
        connection = ConnectHandler(
            **_connection_parameters(
                normalized_address,
                port,
                username,
                password,
                enable_secret,
                profile.os_type,
            )
        )
        if enable_secret:
            connection.enable()
        version_output = connection.send_command(profile.version_command, read_timeout=8)
        return {
            "vendor_key": profile.vendor_key,
            "vendor_name": profile.vendor_name,
            "os_type": profile.os_type,
            "model": _extract_model(version_output, profile),
            "os_version": _extract_os_version(version_output),
            "supported_models": profile.supported_models,
        }
    except IdentityProbeError:
        raise
    except (NetmikoAuthenticationException, NetmikoTimeoutException, OSError) as exc:
        raise IdentityProbeError(
            "SSH probe failed. Verify the management address, credentials, and device reachability."
        ) from exc
    finally:
        if connection is not None:
            connection.disconnect()
        if detector is not None:
            detector.connection.disconnect()
