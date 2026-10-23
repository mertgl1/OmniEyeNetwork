import pytest
from types import SimpleNamespace
from httpx import AsyncClient
from app.services.diff_service import calculate_sha256, generate_config_diff


def test_sha256_calculation():
    text1 = "hostname Switch-Core-01\ninterface GigabitEthernet0/1\n"
    text2 = "hostname Switch-Core-01\r\ninterface GigabitEthernet0/1\r\n"
    # Should normalize CRLF to LF
    assert calculate_sha256(text1) == calculate_sha256(text2)
    assert len(calculate_sha256(text1)) == 64


def test_unified_diff_generation():
    cfg_v1 = """hostname Core-SW-01
vlan 10
 name USERS
interface GigabitEthernet1/0/1
 switchport access vlan 10
"""

    cfg_v2 = """hostname Core-SW-01
vlan 10
 name USERS
vlan 20
 name SERVERS
interface GigabitEthernet1/0/1
 switchport access vlan 20
"""

    diff = generate_config_diff(cfg_v1, cfg_v2, "v1", "v2")
    assert diff["has_changes"] is True
    assert diff["lines_added"] >= 2  # vlan 20, name SERVERS, switchport access vlan 20
    assert diff["lines_removed"] >= 1  # switchport access vlan 10
    assert "vlan 20" in diff["diff_text"]
    assert any(line["type"] == "added" for line in diff["diff_lines"])
    assert any(line["type"] == "removed" for line in diff["diff_lines"])


def test_unified_diff_identical():
    cfg = "hostname SW-01\ninterface Gi0/1\n"
    diff = generate_config_diff(cfg, cfg, "v1", "v2")
    assert diff["has_changes"] is False
    assert diff["lines_added"] == 0
    assert diff["lines_removed"] == 0
    assert diff["diff_text"] == ""


@pytest.mark.asyncio
async def test_vendor_api_endpoints(client: AsyncClient):
    res = await client.get("/api/v1/vendors")
    assert res.status_code == 200
    vendors = res.json()
    assert len(vendors) >= 10
    keys = [v["vendor_key"] for v in vendors]
    assert "cisco_ios" in keys
    assert "huawei_vrp" in keys
    assert "juniper_junos" in keys

    cisco_res = await client.get("/api/v1/vendors/cisco_ios")
    assert cisco_res.status_code == 200
    assert cisco_res.json()["backup_command"] == "show running-config"


@pytest.mark.asyncio
async def test_backup_and_diff_flow(client: AsyncClient, monkeypatch):
    # 1. Create a Huawei Switch device
    dev_res = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "hw-leaf-01",
            "ip_address": "192.168.100.5",
            "vendor": "Huawei",
            "model": "CloudEngine 6800",
            "os_type": "huawei_vrp",
            "ssh_port": 22,
            "username": "admin",
            "password": "HuaweiSecretPassword123!",
        },
    )
    assert dev_res.status_code == 201
    device_id = dev_res.json()["id"]

    # 2. Trigger first backup run -> Version 1
    run1 = await client.post(f"/api/v1/backups/devices/{device_id}/run")
    assert run1.status_code == 200
    run1_data = run1.json()
    assert run1_data["status"] == "success"
    assert run1_data["version"] == 1
    assert "hw-leaf-01" in run1_data["hostname"]

    # 3. Second run with unchanged configuration -> status="unchanged"
    run2 = await client.post(f"/api/v1/backups/devices/{device_id}/run")
    assert run2.status_code == 200
    run2_data = run2.json()
    assert run2_data["status"] == "unchanged"
    assert run2_data["version"] == 1

    # 4. List backup history for device
    hist_res = await client.get(f"/api/v1/backups/devices/{device_id}")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) == 1
    backup1_id = history[0]["id"]
    assert history[0]["version"] == 1

    # 5. Get full backup content
    b1_detail = await client.get(f"/api/v1/backups/{backup1_id}")
    assert b1_detail.status_code == 200
    cfg_text = b1_detail.json()["config_text"]
    assert "sysname hw-leaf-01" in cfg_text  # Huawei format

    # 6. Test bulk run dispatches to Celery rather than blocking the API request
    monkeypatch.setattr(
        "app.api.v1.endpoints.backups.backup_all_devices.delay",
        lambda **kwargs: SimpleNamespace(id="test-backup-task"),
    )
    bulk_res = await client.post("/api/v1/backups/run-all")
    assert bulk_res.status_code == 200
    assert bulk_res.json()["status"] == "dispatched"
    assert bulk_res.json()["task_id"] == "test-backup-task"
