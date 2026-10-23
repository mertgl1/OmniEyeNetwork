from typing import Dict, List, Optional
from pydantic import BaseModel


class VendorCommandProfile(BaseModel):
    vendor_key: str
    vendor_name: str
    os_type: str  # Netmiko device_type
    supported_models: List[str]
    backup_command: str
    vlan_command: str
    mac_command: str
    interface_command: str
    version_command: str
    paging_disable_command: Optional[str] = None
    save_command: Optional[str] = None


# Comprehensive Enterprise Multi-Vendor Command Matrix
VENDOR_PROFILES: Dict[str, VendorCommandProfile] = {
    # 1. Cisco IOS / IOS-XE
    "cisco_ios": VendorCommandProfile(
        vendor_key="cisco_ios",
        vendor_name="Cisco Systems (IOS / IOS-XE)",
        os_type="cisco_ios",
        supported_models=["Catalyst 2960", "Catalyst 3850", "Catalyst 9200", "Catalyst 9300", "Catalyst 9500", "ISR 4000", "ASR 1000"],
        backup_command="show running-config",
        vlan_command="show vlan brief",
        mac_command="show mac address-table",
        interface_command="show ip interface brief",
        version_command="show version",
        paging_disable_command="terminal length 0",
        save_command="write memory",
    ),
    # 2. Cisco NX-OS (Nexus)
    "cisco_nxos": VendorCommandProfile(
        vendor_key="cisco_nxos",
        vendor_name="Cisco Nexus (NX-OS Data Center)",
        os_type="cisco_nxos",
        supported_models=["Nexus 3000", "Nexus 5000", "Nexus 7000", "Nexus 9000", "Nexus 9300"],
        backup_command="show running-config",
        vlan_command="show vlan",
        mac_command="show mac address-table",
        interface_command="show interface brief",
        version_command="show version",
        paging_disable_command="terminal length 0",
        save_command="copy running-config startup-config",
    ),
    # 3. Cisco IOS-XR
    "cisco_xr": VendorCommandProfile(
        vendor_key="cisco_xr",
        vendor_name="Cisco Service Provider (IOS-XR)",
        os_type="cisco_xr",
        supported_models=["ASR 9000", "NCS 5500", "8000 Series"],
        backup_command="show running-config",
        vlan_command="show vlan",
        mac_command="show l2vpn mac-learning",
        interface_command="show ipv4 interface brief",
        version_command="show version",
        paging_disable_command="terminal length 0",
        save_command="commit",
    ),
    # 4. Huawei VRP
    "huawei_vrp": VendorCommandProfile(
        vendor_key="huawei_vrp",
        vendor_name="Huawei Technologies (VRP)",
        os_type="huawei_vrp",
        supported_models=["CloudEngine 6800", "CloudEngine 8800", "CloudEngine 12800", "S5700", "S6700", "S12700", "AR Series Routers"],
        backup_command="display current-configuration",
        vlan_command="display vlan",
        mac_command="display mac-address",
        interface_command="display interface brief",
        version_command="display version",
        paging_disable_command="screen-length 0 temporary",
        save_command="save safely",
    ),
    # 5. ArubaOS-CX
    "aruba_os": VendorCommandProfile(
        vendor_key="aruba_os",
        vendor_name="Aruba Networks (ArubaOS-CX)",
        os_type="aruba_os",
        supported_models=["Aruba CX 6000", "Aruba CX 6100", "Aruba CX 6200", "Aruba CX 6300", "Aruba CX 8320", "Aruba CX 8400"],
        backup_command="show running-config",
        vlan_command="show vlan",
        mac_command="show mac-address",
        interface_command="show interface brief",
        version_command="show version",
        paging_disable_command="no page",
        save_command="write memory",
    ),
    # 6. HPE ProCurve
    "hp_procurve": VendorCommandProfile(
        vendor_key="hp_procurve",
        vendor_name="HPE ProCurve (Provision OS)",
        os_type="hp_procurve",
        supported_models=["ProCurve 2530", "ProCurve 2920", "ProCurve 2930F", "ProCurve 5400R zl2"],
        backup_command="show running-config",
        vlan_command="show vlans",
        mac_command="show mac-address",
        interface_command="show interfaces brief",
        version_command="show system-information",
        paging_disable_command="no page",
        save_command="write memory",
    ),
    # 7. HPE Comware / H3C
    "hp_comware": VendorCommandProfile(
        vendor_key="hp_comware",
        vendor_name="HPE FlexFabric / H3C (Comware 7)",
        os_type="hp_comware",
        supported_models=["FlexFabric 5900", "FlexFabric 5940", "FlexFabric 12500", "H3C S5500"],
        backup_command="display current-configuration",
        vlan_command="display vlan all",
        mac_command="display mac-address",
        interface_command="display interface brief",
        version_command="display version",
        paging_disable_command="screen-length 0 temporary",
        save_command="save safely force",
    ),
    # 8. Juniper JunOS
    "juniper_junos": VendorCommandProfile(
        vendor_key="juniper_junos",
        vendor_name="Juniper Networks (JunOS)",
        os_type="juniper_junos",
        supported_models=["EX2300", "EX3400", "EX4300", "EX4600", "QFX5100", "QFX5200", "SRX300", "SRX1500"],
        backup_command="show configuration",
        vlan_command="show vlans",
        mac_command="show ethernet-switching table",
        interface_command="show interfaces terse",
        version_command="show version",
        paging_disable_command="set cli screen-length 0",
        save_command="commit",
    ),
    # 9. Dell OS10
    "dell_os10": VendorCommandProfile(
        vendor_key="dell_os10",
        vendor_name="Dell EMC PowerSwitch (OS10)",
        os_type="dell_os10",
        supported_models=["PowerSwitch S4100", "PowerSwitch S5200", "PowerSwitch Z9264F", "S4048-ON"],
        backup_command="show running-configuration",
        vlan_command="show vlan",
        mac_command="show mac-address-table",
        interface_command="show interface status",
        version_command="show version",
        paging_disable_command="terminal length 0",
        save_command="write memory",
    ),
    # 10. Extreme EXOS
    "extreme_exos": VendorCommandProfile(
        vendor_key="extreme_exos",
        vendor_name="Extreme Networks (EXOS)",
        os_type="extreme_exos",
        supported_models=["Summit X440-G2", "Summit X460-G2", "Summit X670-G2", "5520 Series"],
        backup_command="show configuration",
        vlan_command="show vlan",
        mac_command="show fdb",
        interface_command="show ports no-refresh",
        version_command="show switch",
        paging_disable_command="disable clipaging",
        save_command="save configuration",
    ),
    # 11. MikroTik RouterOS
    "mikrotik_routeros": VendorCommandProfile(
        vendor_key="mikrotik_routeros",
        vendor_name="MikroTik (RouterOS / Cloud Router Switch)",
        os_type="mikrotik_routeros",
        supported_models=["CRS326", "CRS328", "CRS354", "CCR1036", "CCR2004", "RB5009"],
        backup_command="/export verbose",
        vlan_command="/interface bridge vlan print terse",
        mac_command="/interface bridge host print terse",
        interface_command="/interface print terse",
        version_command="/system resource print",
        paging_disable_command=None,
        save_command=None,
    ),
    # 12. Fortinet FortiOS / FortiSwitch
    "fortinet": VendorCommandProfile(
        vendor_key="fortinet",
        vendor_name="Fortinet (FortiSwitch / FortiOS)",
        os_type="fortinet",
        supported_models=["FortiSwitch 124E", "FortiSwitch 248E", "FortiSwitch 448E", "FortiGate 60F", "FortiGate 100F"],
        backup_command="show full-configuration",
        vlan_command="diagnose switch vlan list",
        mac_command="diagnose switch mac-address list",
        interface_command="get system interface physical",
        version_command="get system status",
        paging_disable_command="config system console\nset output standard\nend",
        save_command=None,
    ),
}


def get_vendor_profile(vendor: str, os_type: Optional[str] = None, model: Optional[str] = None) -> VendorCommandProfile:
    """Intelligently resolves and returns the correct VendorCommandProfile
    based on vendor, model and os_type strings.
    """
    clean_vendor = (vendor or "").lower().strip()
    clean_os = (os_type or "").lower().strip()
    clean_model = (model or "").lower().strip()

    # Direct match on os_type if known
    if clean_os in VENDOR_PROFILES:
        return VENDOR_PROFILES[clean_os]

    # Vendor based heuristics
    if "cisco" in clean_vendor:
        if "nexus" in clean_model or "nxos" in clean_os or "n9k" in clean_model or "n7k" in clean_model:
            return VENDOR_PROFILES["cisco_nxos"]
        if "xr" in clean_os or "asr" in clean_model or "ncs" in clean_model:
            return VENDOR_PROFILES["cisco_xr"]
        return VENDOR_PROFILES["cisco_ios"]

    if "huawei" in clean_vendor:
        return VENDOR_PROFILES["huawei_vrp"]

    if "aruba" in clean_vendor:
        return VENDOR_PROFILES["aruba_os"]

    if "hp" in clean_vendor or "hpe" in clean_vendor:
        if "comware" in clean_os or "flexfabric" in clean_model or "h3c" in clean_vendor:
            return VENDOR_PROFILES["hp_comware"]
        return VENDOR_PROFILES["hp_procurve"]

    if "juniper" in clean_vendor or "junos" in clean_os:
        return VENDOR_PROFILES["juniper_junos"]

    if "dell" in clean_vendor:
        return VENDOR_PROFILES["dell_os10"]

    if "extreme" in clean_vendor:
        return VENDOR_PROFILES["extreme_exos"]

    if "mikrotik" in clean_vendor or "routeros" in clean_os:
        return VENDOR_PROFILES["mikrotik_routeros"]

    if "fortinet" in clean_vendor or "forti" in clean_vendor:
        return VENDOR_PROFILES["fortinet"]

    # Default fallback to standard Cisco IOS-like syntax
    return VENDOR_PROFILES["cisco_ios"]


def list_supported_vendors() -> List[VendorCommandProfile]:
    """Returns list of all available vendor command profiles."""
    return list(VENDOR_PROFILES.values())
