from app.services.vendor_profiles import (
    VENDOR_PROFILES,
    get_vendor_profile,
    list_supported_vendors,
)


def test_all_vendor_profiles_configured():
    assert len(VENDOR_PROFILES) >= 10
    required_vendors = [
        "cisco_ios",
        "cisco_nxos",
        "cisco_xr",
        "huawei_vrp",
        "aruba_os",
        "hp_procurve",
        "hp_comware",
        "juniper_junos",
        "dell_os10",
        "extreme_exos",
        "mikrotik_routeros",
        "fortinet",
    ]
    for v in required_vendors:
        assert v in VENDOR_PROFILES
        profile = VENDOR_PROFILES[v]
        assert profile.backup_command != ""
        assert profile.vlan_command != ""
        assert profile.mac_command != ""
        assert profile.interface_command != ""
        assert len(profile.supported_models) > 0


def test_vendor_heuristic_resolution():
    # Cisco variants
    cisco_ios = get_vendor_profile("cisco", model="Catalyst 9300")
    assert cisco_ios.os_type == "cisco_ios"
    assert cisco_ios.backup_command == "show running-config"

    cisco_nexus = get_vendor_profile("cisco", model="Nexus 9300")
    assert cisco_nexus.os_type == "cisco_nxos"

    cisco_xr = get_vendor_profile("cisco", model="ASR 9000")
    assert cisco_xr.os_type == "cisco_xr"

    # Huawei VRP
    huawei = get_vendor_profile("Huawei Technologies", model="CloudEngine 6800")
    assert huawei.os_type == "huawei_vrp"
    assert huawei.backup_command == "display current-configuration"
    assert huawei.paging_disable_command == "screen-length 0 temporary"

    # Aruba vs ProCurve
    aruba = get_vendor_profile("Aruba", model="CX 6300")
    assert aruba.os_type == "aruba_os"
    assert aruba.backup_command == "show running-config"

    procurve = get_vendor_profile("HPE", model="ProCurve 2930F")
    assert procurve.os_type == "hp_procurve"

    # Juniper JunOS
    juniper = get_vendor_profile("Juniper Networks", model="EX4300")
    assert juniper.os_type == "juniper_junos"
    assert juniper.backup_command == "show configuration"

    # Dell OS10
    dell = get_vendor_profile("Dell", model="PowerSwitch S5200")
    assert dell.os_type == "dell_os10"

    # MikroTik
    mikrotik = get_vendor_profile("Mikrotik", model="CRS326")
    assert mikrotik.os_type == "mikrotik_routeros"
    assert mikrotik.backup_command == "/export verbose"

    # Fortinet
    fortinet = get_vendor_profile("Fortinet", model="FortiSwitch 124E")
    assert fortinet.os_type == "fortinet"


def test_list_supported_vendors():
    vendors = list_supported_vendors()
    assert len(vendors) >= 10
    names = [v.vendor_name for v in vendors]
    assert any("Cisco" in name for name in names)
    assert any("Huawei" in name for name in names)
    assert any("Juniper" in name for name in names)
