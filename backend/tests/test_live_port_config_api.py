import pytest
from httpx import AsyncClient

from app.services.automation_engine import automation_engine


async def _create_device_and_port(client: AsyncClient, vendor="Cisco", os_type="cisco_ios"):
    device_response = await client.post(
        "/api/v1/devices",
        json={
            "hostname": f"port-config-{vendor.lower()}",
            "ip_address": "192.0.2.70",
            "vendor": vendor,
            "os_type": os_type,
        },
    )
    assert device_response.status_code == 201
    device_id = device_response.json()["id"]
    port_response = await client.post(
        "/api/v1/ports",
        json={
            "device_id": device_id,
            "name": "GigabitEthernet1/0/1" if os_type == "cisco_ios" else "ether1",
            "status": "up",
            "admin_status": "up",
            "vlan": 10,
        },
    )
    assert port_response.status_code == 201
    return device_id, port_response.json()["id"]


@pytest.mark.asyncio
async def test_live_port_config_returns_only_redacted_interface_stanza(
    client: AsyncClient,
    monkeypatch,
):
    device_id, port_id = await _create_device_and_port(client)

    async def fake_config(_device, _credentials):
        return (
            "hostname fixture-switch\n"
            "interface GigabitEthernet1/0/1\n"
            " description uplink\n"
            " password 7 sanitized-secret-value\n"
            " switchport access vlan 10\n"
            "!\n"
            "interface GigabitEthernet1/0/2\n"
            " description unrelated-interface\n"
            "!"
        )

    monkeypatch.setattr(automation_engine, "fetch_running_config", fake_config)
    response = await client.get(
        f"/api/v1/devices/{device_id}/ports/{port_id}/live-config"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interface_name"] == "GigabitEthernet1/0/1"
    assert "description uplink" in payload["config_text"]
    assert "[REDACTED]" in payload["config_text"]
    assert "sanitized-secret-value" not in payload["config_text"]
    assert "unrelated-interface" not in payload["config_text"]
    assert "retrieved_at" in payload


@pytest.mark.asyncio
async def test_live_port_config_rejects_viewer_before_device_access(
    client: AsyncClient,
    monkeypatch,
):
    device_id, port_id = await _create_device_and_port(client)
    viewer = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    assert viewer.status_code == 200
    called = False

    async def unexpected_config(*_args):
        nonlocal called
        called = True
        return ""

    monkeypatch.setattr(automation_engine, "fetch_running_config", unexpected_config)
    response = await client.get(
        f"/api/v1/devices/{device_id}/ports/{port_id}/live-config",
        headers={"Authorization": f"Bearer {viewer.json()['access_token']}"},
    )

    assert response.status_code == 403
    assert not called


@pytest.mark.asyncio
async def test_live_port_config_checks_port_device_ownership(
    client: AsyncClient,
    monkeypatch,
):
    device_id, port_id = await _create_device_and_port(client)
    other_device = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "port-config-other",
            "ip_address": "192.0.2.71",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
        },
    )
    assert other_device.status_code == 201

    async def unexpected_config(*_args):
        raise AssertionError("Ownership must be checked before connecting.")

    monkeypatch.setattr(automation_engine, "fetch_running_config", unexpected_config)
    response = await client.get(
        f"/api/v1/devices/{other_device.json()['id']}/ports/{port_id}/live-config"
    )

    assert response.status_code == 404
    assert device_id != other_device.json()["id"]


@pytest.mark.asyncio
async def test_unsupported_vendor_does_not_return_full_configuration(
    client: AsyncClient,
    monkeypatch,
):
    device_id, port_id = await _create_device_and_port(
        client,
        vendor="MikroTik",
        os_type="mikrotik_routeros",
    )

    async def unexpected_config(*_args):
        raise AssertionError("Unsupported profiles must not initiate a device connection.")

    monkeypatch.setattr(automation_engine, "fetch_running_config", unexpected_config)
    response = await client.get(
        f"/api/v1/devices/{device_id}/ports/{port_id}/live-config"
    )

    assert response.status_code == 422
    assert "not supported" in response.json()["detail"]
    assert "default-name" not in response.text


@pytest.mark.asyncio
async def test_live_port_config_allows_operator_role(client: AsyncClient, monkeypatch):
    device_id, port_id = await _create_device_and_port(client)
    operator = await client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "operator123"},
    )
    assert operator.status_code == 200

    async def fake_config(_device, _credentials):
        return "interface GigabitEthernet1/0/1\n description operator-test\n!"

    monkeypatch.setattr(automation_engine, "fetch_running_config", fake_config)
    response = await client.get(
        f"/api/v1/devices/{device_id}/ports/{port_id}/live-config",
        headers={"Authorization": f"Bearer {operator.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert "operator-test" in response.json()["config_text"]
