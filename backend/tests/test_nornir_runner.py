from dataclasses import replace

import pytest

from app.services.nornir_runner import DeviceCommandRequest, run_device_commands


class FakeConnection:
    def __init__(self, **parameters):
        self.parameters = parameters
        self.commands = []
        self.enabled = False
        self.disconnected = False

    def enable(self):
        self.enabled = True

    def send_command(self, command):
        self.commands.append(command)
        return f"output:{command}"

    def disconnect(self):
        self.disconnected = True


def _request(key):
    return DeviceCommandRequest(
        key=key,
        hostname=key,
        ip_address="192.0.2.10" if key == "switch-a" else "192.0.2.11",
        port=22,
        username="test-user",
        password="test-password",
        device_type="cisco_ios",
        commands={"interfaces": "show ip interface brief"},
        enable_secret="enable-test",
        paging_disable_command="terminal length 0",
    )


def test_nornir_executes_profile_commands_for_all_inventory_hosts(monkeypatch):
    connections = {}

    def fake_connect_handler(**parameters):
        connection = FakeConnection(**parameters)
        connections[parameters["host"]] = connection
        return connection

    monkeypatch.setattr(
        "nornir_netmiko.connections.netmiko.ConnectHandler",
        fake_connect_handler,
    )

    first = _request("switch-a")
    second = replace(_request("switch-b"), ssh_strict=True)
    results = run_device_commands([first, second], 2)

    assert set(results) == {"switch-a", "switch-b"}
    for key, result in results.items():
        address = "192.0.2.10" if key == "switch-a" else "192.0.2.11"
        assert result.error_type is None
        assert result.outputs == {"interfaces": "output:show ip interface brief"}
        assert connections[address].enabled
        assert connections[address].commands == [
            "terminal length 0",
            "show ip interface brief",
        ]
        assert connections[address].disconnected
    assert connections["192.0.2.10"].parameters["device_type"] == "cisco_ios"
    assert connections["192.0.2.10"].parameters["ssh_strict"] is False
    assert connections["192.0.2.10"].parameters["system_host_keys"] is False
    assert connections["192.0.2.11"].parameters["ssh_strict"] is True
    assert connections["192.0.2.10"].parameters["secret"] == "enable-test"


def test_nornir_rejects_duplicate_inventory_keys():
    with pytest.raises(ValueError, match="unique"):
        run_device_commands([_request("duplicate"), _request("duplicate")])


def test_nornir_rejects_missing_device_credentials():
    request = replace(_request("switch-a"), password="")
    with pytest.raises(ValueError, match="credentials"):
        run_device_commands([request])
