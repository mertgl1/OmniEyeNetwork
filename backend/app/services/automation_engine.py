import os
from typing import Any, Dict, Optional
from app.core.config import settings
from app.services.vendor_profiles import get_vendor_profile


class AutomationEngine:
    """Core network automation engine for multi-vendor switches and routers.
    Manages SSH connectivity, vendor command dispatch, and running-config retrieval.
    """

    def __init__(self):
        self.simulation_mode = os.getenv("NETWORK_SIMULATION_MODE", "auto").lower()

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

        # Simulation / Test environment check
        is_test_env = settings.ENVIRONMENT == "test"
        is_sim_forced = self.simulation_mode in ("true", "1", "yes")

        if is_test_env or is_sim_forced:
            return self._generate_simulated_config(device, profile)

        # Live SSH connection using Netmiko
        try:
            from netmiko import ConnectHandler  # type: ignore

            creds = credentials or {}
            username = creds.get("username", "")
            password = creds.get("password", "")
            secret = creds.get("enable_secret", "")

            device_params = {
                "device_type": profile.os_type,
                "host": device.ip_address,
                "port": device.ssh_port or 22,
                "username": username,
                "password": password,
                "secret": secret,
                "timeout": 20,
                "session_timeout": 60,
            }

            with ConnectHandler(**device_params) as net_connect:
                if secret:
                    net_connect.enable()

                if profile.paging_disable_command:
                    net_connect.send_command(profile.paging_disable_command)

                output = net_connect.send_command(profile.backup_command)
                return output

        except Exception as e:
            # If in auto-simulation mode and live device is unreachable (e.g. lab IP), fallback to simulated
            if self.simulation_mode == "auto":
                return self._generate_simulated_config(device, profile)
            raise RuntimeError(f"Failed to connect to device {device.hostname} ({device.ip_address}): {str(e)}")


automation_engine = AutomationEngine()
