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
async def test_inventory_requires_auth_and_viewers_cannot_write(client: AsyncClient):
    unauthenticated = await client.get("/api/v1/devices", headers={"Authorization": ""})
    assert unauthenticated.status_code == 401

    login = await client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert login.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    denied = await client.post(
        "/api/v1/groups",
        headers=viewer_headers,
        json={"name": "Viewer must not create groups"},
    )
    assert denied.status_code == 403


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
    assert dev_data["device_type"] == "switch"
    # Password should NOT be in response
    assert "password" not in dev_data
    assert "SwitchSecretPassword123!" not in str(dev_data)

    # 3. List devices
    dev_list = await client.get("/api/v1/devices?vendor=cisco")
    assert dev_list.status_code == 200
    assert len(dev_list.json()) == 1
    filtered_switches = await client.get("/api/v1/devices?device_type=switch")
    assert filtered_switches.status_code == 200
    assert [item["id"] for item in filtered_switches.json()] == [device_id]

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


@pytest.mark.asyncio
async def test_deleting_group_detaches_devices(client: AsyncClient):
    group = await client.post("/api/v1/groups", json={"name": "preserve-devices-group"})
    device = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "preserve-device",
            "ip_address": "192.0.2.14",
            "vendor": "Cisco",
            "os_type": "cisco_ios",
            "group_id": group.json()["id"],
        },
    )
    assert device.status_code == 201

    deleted = await client.delete(f"/api/v1/groups/{group.json()['id']}")
    assert deleted.status_code == 204
    retained = await client.get(f"/api/v1/devices/{device.json()['id']}")
    assert retained.status_code == 200
    assert retained.json()["group_id"] is None


@pytest.mark.asyncio
async def test_device_category_can_be_filtered_and_updated(client: AsyncClient):
    created = await client.post(
        "/api/v1/devices",
        json={
            "hostname": "future-category-device",
            "ip_address": "10.20.0.5",
            "device_type": "router",
            "vendor": "Cisco",
            "os_type": "cisco_xr",
        },
    )

    assert created.status_code == 201
    device_id = created.json()["id"]
    assert created.json()["device_type"] == "router"

    router_list = await client.get("/api/v1/devices?device_type=router")
    assert [device["id"] for device in router_list.json()] == [device_id]

    updated = await client.put(
        f"/api/v1/devices/{device_id}",
        json={"device_type": "firewall"},
    )
    assert updated.status_code == 200
    assert updated.json()["device_type"] == "firewall"

    assert (await client.get("/api/v1/devices?device_type=router")).json() == []


@pytest.mark.asyncio
async def test_device_enrollment_rejects_catalog_only_or_mismatched_vendor(client: AsyncClient):
    payload = {
        "hostname": "unsupported-vendor-device",
        "ip_address": "10.20.0.6",
        "vendor": "Ubiquiti",
        "os_type": "cisco_ios",
    }

    unsupported = await client.post("/api/v1/devices", json=payload)
    assert unsupported.status_code == 422

    payload["hostname"] = "mismatched-vendor-device"
    payload["vendor"] = "Cisco"
    payload["os_type"] = "huawei_vrp"
    mismatched = await client.post("/api/v1/devices", json=payload)
    assert mismatched.status_code == 422
