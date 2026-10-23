import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_login_ad_mock(client: AsyncClient):
    # Test Admin login
    res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["token_type"] == "bearer"
    admin_token = data["access_token"]

    # Test /me with token
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "admin"
    assert me_data["role"] == "admin"


@pytest.mark.asyncio
async def test_auth_login_invalid(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={"username": "unknown_user", "password": "bad"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_roles_list(client: AsyncClient):
    res = await client.get("/api/v1/auth/roles")
    assert res.status_code == 200
    roles = res.json()
    assert len(roles) == 3
    role_names = [r["role"] for r in roles]
    assert "admin" in role_names
    assert "operator" in role_names
    assert "viewer" in role_names


@pytest.mark.asyncio
async def test_device_groups_crud(client: AsyncClient):
    # 1. Create group
    create_res = await client.post(
        "/api/v1/groups",
        json={"name": "Core Switches", "description": "Datacenter Core Backbone Switches"},
    )
    assert create_res.status_code == 201
    group_data = create_res.json()
    group_id = group_data["id"]
    assert group_data["name"] == "Core Switches"

    # 2. Duplicate group name should fail
    dup_res = await client.post(
        "/api/v1/groups",
        json={"name": "Core Switches"},
    )
    assert dup_res.status_code == 400

    # 3. List groups
    list_res = await client.get("/api/v1/groups")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Get by ID
    get_res = await client.get(f"/api/v1/groups/{group_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Core Switches"

    # 5. Update
    update_res = await client.put(f"/api/v1/groups/{group_id}", json={"name": "Datacenter Core Switches"})
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Datacenter Core Switches"

    # 6. Delete
    del_res = await client.delete(f"/api/v1/groups/{group_id}")
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_devices_and_ports_crud(client: AsyncClient):
    # 1. Create a group first
    grp_res = await client.post("/api/v1/groups", json={"name": "Access Layer Floor 1"})
    grp_id = grp_res.json()["id"]

    # 2. Create device with credentials (encrypted by Vault)
    device_payload = {
        "hostname": "sw-access-01",
        "ip_address": "10.10.20.15",
        "vendor": "cisco",
        "model": "Catalyst 9300-48P",
        "os_type": "cisco_ios",
        "ssh_port": 22,
        "is_active": True,
        "group_id": grp_id,
        "username": "netadmin",
        "password": "SwitchSecretPassword123!",
        "enable_secret": "EnableSecret321!",
    }
    dev_res = await client.post("/api/v1/devices", json=device_payload)
    assert dev_res.status_code == 201
    dev_data = dev_res.json()
    device_id = dev_data["id"]
    assert dev_data["hostname"] == "sw-access-01"
    # Password should NOT be in response
    assert "password" not in dev_data
    assert "SwitchSecretPassword123!" not in str(dev_data)

    # 3. List devices
    dev_list = await client.get("/api/v1/devices?vendor=cisco")
    assert dev_list.status_code == 200
    assert len(dev_list.json()) == 1

    # 4. Create Port for this device
    port_payload = {
        "device_id": device_id,
        "name": "GigabitEthernet1/0/1",
        "description": "Uplink to Core-SW-01",
        "status": "up",
        "admin_status": "up",
        "vlan": 100,
        "mac_address": "00:1A:2B:3C:4D:5E",
        "speed": "1Gbps",
        "duplex": "Full",
    }
    port_res = await client.post("/api/v1/ports", json=port_payload)
    assert port_res.status_code == 201
    port_data = port_res.json()
    port_id = port_data["id"]
    assert port_data["name"] == "GigabitEthernet1/0/1"

    # 5. List ports by device_id
    ports_res = await client.get(f"/api/v1/ports?device_id={device_id}")
    assert ports_res.status_code == 200
    assert len(ports_res.json()) == 1

    # 6. Update port status
    port_upd = await client.put(f"/api/v1/ports/{port_id}", json={"status": "down"})
    assert port_upd.status_code == 200
    assert port_upd.json()["status"] == "down"

    # 7. Delete port
    del_port = await client.delete(f"/api/v1/ports/{port_id}")
    assert del_port.status_code == 204

    # 8. Delete device
    del_dev = await client.delete(f"/api/v1/devices/{device_id}")
    assert del_dev.status_code == 204
