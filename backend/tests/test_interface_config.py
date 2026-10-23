import json
from pathlib import Path

import pytest

from app.services.interface_config import (
    UnsupportedInterfaceConfig,
    extract_interface_config,
)
from app.services.vendor_profiles import VENDOR_PROFILES


@pytest.fixture(scope="module")
def interface_config_fixtures():
    path = Path(__file__).parent / "fixtures" / "vendor_interface_configs.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_supported_vendor_config_stanzas_are_isolated(interface_config_fixtures):
    assert set(interface_config_fixtures).issubset(VENDOR_PROFILES)
    for vendor_key, fixture in interface_config_fixtures.items():
        extracted = extract_interface_config(
            fixture["config"],
            fixture["interface"],
            vendor_key,
        )
        assert "uplink-to-core" in extracted, vendor_key
        assert "unrelated-interface" not in extracted, vendor_key


@pytest.mark.parametrize("vendor_key", ["extreme_exos", "mikrotik_routeros", "fortinet"])
def test_unsupported_profiles_do_not_return_full_configuration(vendor_key):
    with pytest.raises(UnsupportedInterfaceConfig, match="not supported"):
        extract_interface_config(
            "synthetic full device config",
            "port1",
            vendor_key,
        )


def test_invalid_interface_name_is_rejected():
    with pytest.raises(UnsupportedInterfaceConfig, match="interface name"):
        extract_interface_config(
            "interface GigabitEthernet1/0/1\n description uplink\n!",
            "GigabitEthernet1/0/1\nshow running-config",
            "cisco_ios",
        )


def test_missing_or_ambiguous_interface_stanza_is_rejected():
    with pytest.raises(UnsupportedInterfaceConfig, match="not found"):
        extract_interface_config(
            "interface GigabitEthernet1/0/2\n description other\n!",
            "GigabitEthernet1/0/1",
            "cisco_ios",
        )
    with pytest.raises(UnsupportedInterfaceConfig, match="unbalanced"):
        extract_interface_config(
            "interfaces {\n    ge-0/0/1 {\n        description uplink;\n",
            "ge-0/0/1",
            "juniper_junos",
        )
    with pytest.raises(UnsupportedInterfaceConfig, match="boundary is ambiguous"):
        extract_interface_config(
            "interface GigabitEthernet1/0/1\n description uplink\nhostname edge",
            "GigabitEthernet1/0/1",
            "cisco_ios",
        )
