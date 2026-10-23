from unittest.mock import Mock

import pytest

from app.services import device_identity


def test_probe_detects_supported_profile_and_returns_model_without_raw_output(monkeypatch):
    detector_connection = Mock()
    detector = Mock()
    detector.connection = detector_connection
    detector.autodetect.return_value = "cisco_xe"
    monkeypatch.setattr(device_identity, "SSHDetect", Mock(return_value=detector))

    version_connection = Mock()
    version_connection.send_command.return_value = (
        "Cisco IOS XE Software, Version 17.09.04a\n"
        "Model Number : C9300-48P"
    )
    monkeypatch.setattr(device_identity, "ConnectHandler", Mock(return_value=version_connection))

    result = device_identity.detect_device_identity(
        "10.10.1.2",
        22,
        "netadmin",
        "temporary-secret",
    )

    assert result["vendor_key"] == "cisco_ios"
    assert result["os_type"] == "cisco_ios"
    assert result["model"] == "Catalyst 9300"
    assert result["os_version"] == "17.09.04a"
    assert "temporary-secret" not in str(result)
    version_connection.send_command.assert_called_once_with("show version", read_timeout=8)
    version_connection.disconnect.assert_called_once()
    detector_connection.disconnect.assert_called_once()


def test_probe_rejects_unsupported_platform_without_opening_second_connection(monkeypatch):
    detector = Mock()
    detector.connection = Mock()
    detector.autodetect.return_value = "ubiquiti_edgeswitch"
    monkeypatch.setattr(device_identity, "SSHDetect", Mock(return_value=detector))
    connect_handler = Mock()
    monkeypatch.setattr(device_identity, "ConnectHandler", connect_handler)

    with pytest.raises(device_identity.IdentityProbeError) as error:
        device_identity.detect_device_identity(
            "10.10.1.2",
            22,
            "netadmin",
            "temporary-secret",
        )

    assert error.value.status_code == 422
    connect_handler.assert_not_called()
    detector.connection.disconnect.assert_called_once()


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "169.254.169.254", "224.0.0.1", "::1", "::ffff:127.0.0.1"],
)
def test_probe_rejects_sensitive_or_non_routable_addresses(address):
    with pytest.raises(ValueError):
        device_identity.validate_probe_address(address)


def test_probe_requires_literal_ip_address():
    with pytest.raises(ValueError, match="literal IPv4 or IPv6"):
        device_identity.validate_probe_address("switch.example.test")
