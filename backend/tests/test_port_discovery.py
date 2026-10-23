from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.services.automation_engine import automation_engine
from app.services.port_discovery import parse_port_inventory, sync_device_ports
from app.models.device import Device
from app.models.port import Port
from sqlalchemy import select
from conftest import TestingSessionLocal


def test_parse_interface_vlan_and_mac_inventory():
    parsed = parse_port_inventory(automation_engine._simulated_inventory_outputs())
    assert len(parsed) == 2
    first = next(port for port in parsed if port["name"] == "GigabitEthernet1/0/1")
    assert first["status"] == "up"
    assert first["vlan"] == 10
    assert first["mac_address"] == "001a.2b3c.4d5e"


@pytest.mark.asyncio
async def test_readonly_command_allowlist_rejects_configuration_changes():
    device = SimpleNamespace(
        vendor="cisco",
        os_type="cisco_ios",
        model="Catalyst 9300",
        hostname="test-switch",
        ip_address="192.0.2.10",
        ssh_port=22,
    )
    result = await automation_engine.send_readonly_command(device, {}, "show version")
    assert "Simulation mode" in result

    with pytest.raises(ValueError, match="read-only"):
        await automation_engine.send_readonly_command(device, {}, "write erase")


@pytest.mark.asyncio
async def test_port_discovery_is_queued_for_inventory_devices(client: AsyncClient, monkeypatch):
    device = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "discovery-switch",
            "ip_address": "192.0.2.11",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
        },
    )
    assert device.status_code == 201
    monkeypatch.setattr(
        "app.api.v1.endpoints.ports.dispatch_port_discovery.delay",
        lambda **kwargs: SimpleNamespace(id="test-discovery-task"),
    )

    response = await client.post(
        "/api/v1/ports/discovery/run",
        params={"device_id": device.json()["id"]},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "dispatched"
    assert response.json()["task_id"] == "test-discovery-task"


@pytest.mark.asyncio
async def test_port_discovery_upserts_port_rows(client: AsyncClient, monkeypatch):
    device_response = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "port-sync-switch",
            "ip_address": "192.0.2.15",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
        },
    )
    assert device_response.status_code == 201
    device_id = device_response.json()["id"]

    async def fake_outputs(device, credentials):
        return {
            "interfaces": "GigabitEthernet1/0/1 unassigned up up\n",
            "vlans": "10 USERS active GigabitEthernet1/0/1\n",
            "macs": "10 001a.2b3c.4d5e DYNAMIC GigabitEthernet1/0/1\n",
        }

    monkeypatch.setattr(automation_engine, "fetch_inventory_outputs", fake_outputs)
    async with TestingSessionLocal() as db:
        device = await db.get(Device, device_id)
        assert device is not None
        assert await sync_device_ports(db, device) == 1
        assert await sync_device_ports(db, device) == 1
        result = await db.execute(select(Port).where(Port.device_id == device_id))
        ports = result.scalars().all()
        assert len(ports) == 1
        assert ports[0].status == "up"
        assert ports[0].vlan == 10
        assert ports[0].mac_address == "001a.2b3c.4d5e"


@pytest.mark.asyncio
async def test_live_config_requires_operator_role(client: AsyncClient):
    device = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "live-config-switch",
            "ip_address": "192.0.2.12",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
        },
    )
    assert device.status_code == 201
    viewer = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    response = await client.get(
        f"/api/v1/devices/{device.json()['id']}/live-config",
        headers={"Authorization": f"Bearer {viewer.json()['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_read_backup_configuration(client: AsyncClient):
    device = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "backup-rbac-switch",
            "ip_address": "192.0.2.13",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
        },
    )
    assert device.status_code == 201
    backup = await client.post(f"/api/v1/backups/devices/{device.json()['id']}/run")
    assert backup.status_code == 200
    history = await client.get(f"/api/v1/backups/devices/{device.json()['id']}")
    assert history.status_code == 200
    viewer = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    detail = await client.get(
        f"/api/v1/backups/{history.json()[0]['id']}",
        headers={"Authorization": f"Bearer {viewer.json()['access_token']}"},
    )
    assert detail.status_code == 403
