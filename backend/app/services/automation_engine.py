import asyncio
import logging
from typing import Any, Dict, Optional
from app.core.config import settings
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
            return await asyncio.to_thread(
                self._send_device_command,
                device,
                profile,
                credentials or {},
                profile.backup_command,
            )
        except Exception as e:
            logger.warning(
                "Configuration retrieval failed for device %s (%s).",
                device.hostname,
                device.ip_address,
                exc_info=True,
            )
            raise RuntimeError(f"Failed to connect to device {device.hostname} ({device.ip_address}): {str(e)}")

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
        return await asyncio.to_thread(
            self._collect_inventory_outputs,
            device,
            profile,
            credentials or {},
            commands,
        )

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
        return await asyncio.to_thread(
            self._send_device_command,
            device,
            profile,
            credentials or {},
            command,
        )

    def _simulation_enabled(self) -> bool:
        return settings.ENVIRONMENT == "test" or self.simulation_mode in ("true", "1", "yes")

    @staticmethod
    def _device_params(device: Any, profile: Any, credentials: Dict[str, Any]) -> Dict[str, Any]:
        if not credentials.get("username") or not credentials.get("password"):
            raise RuntimeError("Device SSH credentials are not configured.")
        return {
            "device_type": profile.os_type,
            "host": device.ip_address,
            "port": device.ssh_port or 22,
            "username": credentials["username"],
            "password": credentials["password"],
            "secret": credentials.get("enable_secret", ""),
            "timeout": 20,
            "session_timeout": 60,
            "ssh_strict": settings.SSH_STRICT_HOST_KEY_CHECKING,
            "system_host_keys": settings.SSH_STRICT_HOST_KEY_CHECKING,
        }

    @classmethod
    def _send_device_command(
        cls,
        device: Any,
        profile: Any,
        credentials: Dict[str, Any],
        command: str,
    ) -> str:
        from netmiko import ConnectHandler

        with ConnectHandler(**cls._device_params(device, profile, credentials)) as connection:
            if credentials.get("enable_secret"):
                connection.enable()
            if profile.paging_disable_command:
                connection.send_command(profile.paging_disable_command)
            return connection.send_command(command)

    @classmethod
    def _collect_inventory_outputs(
        cls,
        device: Any,
        profile: Any,
        credentials: Dict[str, Any],
        commands: Dict[str, str],
    ) -> Dict[str, str]:
        from netmiko import ConnectHandler

        with ConnectHandler(**cls._device_params(device, profile, credentials)) as connection:
            if credentials.get("enable_secret"):
                connection.enable()
            if profile.paging_disable_command:
                connection.send_command(profile.paging_disable_command)
            return {
                key: connection.send_command(command)
                for key, command in commands.items()
            }

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
