import asyncio
import logging
from typing import Any, Dict, Optional
from app.core.config import settings
from app.services.nornir_runner import (
    DeviceCommandRequest,
    DeviceCommandResult,
    run_device_commands,
)
from app.services.vendor_profiles import get_vendor_profile

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Core network automation engine for multi-vendor switches and routers.
    Manages SSH connectivity, vendor command dispatch, and running-config retrieval.
    """

    def __init__(self):
        self.simulation_mode = settings.NETWORK_SIMULATION_MODE.lower()

    def _generate_simulated_config(self, device: Any, vendor_profile: Any) -> str:
        """Generates realistic vendor-compliant configuration for development and test suites."""
        v_key = vendor_profile.vendor_key
        hostname = getattr(device, "hostname", "OmniEye-Switch")
        ip = getattr(device, "ip_address", "10.10.10.1")

        if "huawei" in v_key:
            return f"""#
! Software Version V200R019C00SPC500
sysname {hostname}
#
vlan batch 10 20 30 100
#
interface Vlanif100
 ip address {ip} 255.255.255.0
#
interface GigabitEthernet0/0/1
 port link-type trunk
 port trunk allow-pass vlan 10 20 30 100
#
interface GigabitEthernet0/0/2
 port link-type access
 port default vlan 10
#
user-interface vty 0 4
 authentication-mode aaa
 user privilege level 15
 protocol inbound ssh
#
return"""

        elif "juniper" in v_key:
            return f"""system {{
    host-name {hostname};
    services {{
        ssh;
    }}
}}
interfaces {{
    ge-0/0/0 {{
        unit 0 {{
            family ethernet-switching {{
                vlan {{
                    members [ vlan10 vlan20 ];
                }}
            }}
        }}
    }}
    vlan {{
        unit 100 {{
            family inet {{
                address {ip}/24;
            }}
        }}
    }}
}}"""

        # Default Cisco / Aruba / ProCurve format
        return f"""!
version 17.3
service timestamps debug datetime msec
service timestamps log datetime msec
no service password-encryption
!
hostname {hostname}
!
ip routing
!
vlan 10
 name USERS
!
vlan 20
 name SERVERS
!
vlan 100
 name MANAGEMENT
!
interface GigabitEthernet1/0/1
 description Uplink-Core
 switchport mode trunk
 switchport trunk allowed vlan 10,20,100
!
interface GigabitEthernet1/0/2
 description User-Port
 switchport access vlan 10
 switchport mode access
 spanning-tree portfast
!
interface Vlan100
 ip address {ip} 255.255.255.0
 no shutdown
!
line vty 0 4
 transport input ssh
 login local
!
end"""

    async def fetch_running_config(
        self,
        device: Any,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Fetches the active running-config from device using vendor-specific CLI commands."""
        profile = get_vendor_profile(
            vendor=getattr(device, "vendor", "cisco"),
            os_type=getattr(device, "os_type", None),
            model=getattr(device, "model", None),
        )

        if self._simulation_enabled():
            return self._generate_simulated_config(device, profile)

        try:
            result = await self.fetch_running_configs(
                {device.hostname: (device, credentials or {})}
            )
            return result[device.hostname]["config"]
        except Exception:
            logger.warning(
                "Configuration retrieval failed for device %s (%s).",
                device.hostname,
                device.ip_address,
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to retrieve configuration from device {device.hostname}."
            ) from None

    async def fetch_running_configs(
        self,
        devices: Dict[str, tuple[Any, Dict[str, Any]]],
    ) -> Dict[str, Dict[str, str]]:
        """Fetch configurations concurrently; individual device failures are isolated."""
        if self._simulation_enabled():
            return {
                key: {
                    "config": self._generate_simulated_config(
                        device,
                        get_vendor_profile(
                            getattr(device, "vendor", "cisco"),
                            getattr(device, "os_type", None),
                            getattr(device, "model", None),
                        ),
                    )
                }
                for key, (device, _credentials) in devices.items()
            }

        requests = []
        request_keys = []
        failed: Dict[str, Dict[str, str]] = {}
        for key, (device, credentials) in devices.items():
            profile = get_vendor_profile(
                getattr(device, "vendor", "cisco"),
                getattr(device, "os_type", None),
                getattr(device, "model", None),
            )
            try:
                requests.append(
                    self._command_request(
                        key,
                        device,
                        profile,
                        credentials,
                        {"config": profile.backup_command},
                    )
                )
                request_keys.append(key)
            except ValueError:
                failed[key] = {}

        results = await asyncio.to_thread(
            run_device_commands,
            requests,
            settings.NORNIR_NUM_WORKERS,
        )
        for key in request_keys:
            result = results[key]
            failed[key] = result.outputs or {}
        return failed

    async def fetch_inventory_outputs(
        self,
        device: Any,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Collect the vendor profile's read-only interface, VLAN and MAC command outputs."""
        profile = get_vendor_profile(
            vendor=getattr(device, "vendor", "cisco"),
            os_type=getattr(device, "os_type", None),
            model=getattr(device, "model", None),
        )
        commands = {
            "interfaces": profile.interface_command,
            "vlans": profile.vlan_command,
            "macs": profile.mac_command,
        }
        if self._simulation_enabled():
            return self._simulated_inventory_outputs()
        result = await self.fetch_inventory_outputs_batch(
            {device.hostname: (device, credentials or {})}
        )
        outputs = result.get(device.hostname)
        if outputs is None:
            raise RuntimeError(
                f"Failed to retrieve inventory from device {device.hostname}."
            )
        return outputs

    async def fetch_inventory_outputs_batch(
        self,
        devices: Dict[str, tuple[Any, Dict[str, Any]]],
    ) -> Dict[str, Dict[str, str]]:
        """Fetch per-device interface, VLAN and MAC command output concurrently."""
        if self._simulation_enabled():
            return {
                key: self._simulated_inventory_outputs()
                for key in devices
            }

        requests = []
        request_keys = []
        for key, (device, credentials) in devices.items():
            profile = get_vendor_profile(
                getattr(device, "vendor", "cisco"),
                getattr(device, "os_type", None),
                getattr(device, "model", None),
            )
            commands = {
                "interfaces": profile.interface_command,
                "vlans": profile.vlan_command,
                "macs": profile.mac_command,
            }
            try:
                requests.append(
                    self._command_request(key, device, profile, credentials, commands)
                )
                request_keys.append(key)
            except ValueError:
                continue

        results = await asyncio.to_thread(
            run_device_commands,
            requests,
            settings.NORNIR_NUM_WORKERS,
        )
        return {
            key: results[key].outputs
            for key in request_keys
            if results[key].outputs is not None
        }

    async def send_readonly_command(
        self,
        device: Any,
        credentials: Optional[Dict[str, Any]],
        command: str,
    ) -> str:
        """Run only an exact vendor-profile show command; arbitrary CLI input is rejected."""
        profile = get_vendor_profile(
            vendor=getattr(device, "vendor", "cisco"),
            os_type=getattr(device, "os_type", None),
            model=getattr(device, "model", None),
        )
        allowed_commands = {
            profile.interface_command,
            profile.vlan_command,
            profile.mac_command,
            profile.version_command,
        }
        if command not in allowed_commands:
            raise ValueError("Command is not in the device's read-only command allowlist.")
        if self._simulation_enabled():
            return f"Simulation mode: {command}\nNo device connection was made."
        result = await self.fetch_readonly_commands(
            {
                device.hostname: (
                    device,
                    credentials or {},
                    command,
                )
            }
        )
        output = result.get(device.hostname)
        if output is None:
            raise RuntimeError(
                f"Failed to execute read-only command on device {device.hostname}."
            )
        return output

    async def fetch_readonly_commands(
        self,
        devices: Dict[str, tuple[Any, Dict[str, Any], str]],
    ) -> Dict[str, str]:
        """Execute allowlisted commands concurrently and isolate device failures."""
        requests = []
        request_keys = []
        for key, (device, credentials, command) in devices.items():
            profile = get_vendor_profile(
                getattr(device, "vendor", "cisco"),
                getattr(device, "os_type", None),
                getattr(device, "model", None),
            )
            allowed_commands = {
                profile.interface_command,
                profile.vlan_command,
                profile.mac_command,
                profile.version_command,
            }
            if command not in allowed_commands:
                raise ValueError(
                    "Command is not in the device's read-only command allowlist."
                )
            try:
                requests.append(
                    self._command_request(
                        key, device, profile, credentials, {"output": command}
                    )
                )
                request_keys.append(key)
            except ValueError:
                continue

        if self._simulation_enabled():
            return {
                key: f"Simulation mode: {command}\nNo device connection was made."
                for key, (_device, _credentials, command) in devices.items()
            }

        results = await asyncio.to_thread(
            run_device_commands,
            requests,
            settings.NORNIR_NUM_WORKERS,
        )
        return {
            key: results[key].outputs["output"]
            for key in request_keys
            if results[key].outputs is not None
        }

    def _simulation_enabled(self) -> bool:
        return settings.ENVIRONMENT == "test" or self.simulation_mode in ("true", "1", "yes")

    @staticmethod
    def _command_request(
        key: str,
        device: Any,
        profile: Any,
        credentials: Dict[str, Any],
        commands: Dict[str, str],
    ) -> DeviceCommandRequest:
        if not credentials.get("username") or not credentials.get("password"):
            raise ValueError("Device SSH credentials are not configured.")
        return DeviceCommandRequest(
            key=key,
            hostname=device.hostname,
            ip_address=device.ip_address,
            port=device.ssh_port or 22,
            username=credentials["username"],
            password=credentials["password"],
            device_type=profile.os_type,
            commands=commands,
            enable_secret=credentials.get("enable_secret", ""),
            paging_disable_command=profile.paging_disable_command,
            ssh_strict=settings.SSH_STRICT_HOST_KEY_CHECKING,
        )

    @staticmethod
    def _simulated_inventory_outputs() -> Dict[str, str]:
        return {
            "interfaces": (
                "Interface              IP-Address      Status                Protocol\n"
                "GigabitEthernet1/0/1   unassigned      up                    up\n"
                "GigabitEthernet1/0/2   unassigned      down                  down\n"
            ),
            "vlans": (
                "VLAN Name                             Status    Ports\n"
                "10   USERS                            active    GigabitEthernet1/0/1\n"
                "20   SERVERS                          active    GigabitEthernet1/0/2\n"
            ),
            "macs": (
                "Vlan    Mac Address       Type        Ports\n"
                "10      001a.2b3c.4d5e    DYNAMIC     GigabitEthernet1/0/1\n"
            ),
        }


automation_engine = AutomationEngine()
