from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vendor_catalog_marks_ubiquiti_as_catalog_only(client: AsyncClient):
    response = await client.get("/api/v1/vendors/catalog")

    assert response.status_code == 200
    ubiquiti = next(item for item in response.json() if item["vendor_key"] == "ubiquiti")
    assert ubiquiti["supported"] is False
    assert ubiquiti["os_type"] is None
    assert "ayrı bir fazda" in ubiquiti["support_note"]

    fortinet = next(item for item in response.json() if item["vendor_key"] == "fortinet")
    assert fortinet["models_by_device_type"]["switch"] == [
        "FortiSwitch 124E",
        "FortiSwitch 248E",
        "FortiSwitch 448E",
    ]
    assert fortinet["models_by_device_type"]["firewall"] == [
        "FortiGate 60F",
        "FortiGate 100F",
    ]


@pytest.mark.asyncio
async def test_identity_probe_requires_admin_role(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    response = await client.post(
        "/api/v1/vendors/detect",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={
            "ip_address": "10.10.1.2",
            "username": "network-user",
            "password": "temporary-secret",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_identity_probe_rejects_loopback_before_network_call(client: AsyncClient):
    with patch("app.api.v1.endpoints.vendors.detect_device_identity") as detect:
        response = await client.post(
            "/api/v1/vendors/detect",
            json={
                "ip_address": "127.0.0.1",
                "username": "network-user",
                "password": "temporary-secret",
            },
        )

    assert response.status_code == 422
    detect.assert_not_called()


@pytest.mark.asyncio
async def test_identity_probe_does_not_return_credentials(client: AsyncClient):
    detected = {
        "vendor_key": "cisco_ios",
        "vendor_name": "Cisco Systems (IOS / IOS-XE)",
        "os_type": "cisco_ios",
        "model": "Catalyst 9300",
        "os_version": "17.09.04a",
        "supported_models": ["Catalyst 9300"],
    }
    with patch(
        "app.api.v1.endpoints.vendors.detect_device_identity",
        return_value=detected,
    ) as detect:
        response = await client.post(
            "/api/v1/vendors/detect",
            json={
                "ip_address": "10.10.1.2",
                "ssh_port": 2222,
                "username": "network-user",
                "password": "temporary-secret",
                "enable_secret": "temporary-enable-secret",
            },
        )

    assert response.status_code == 200
    assert response.json()["model"] == "Catalyst 9300"
    assert "temporary-secret" not in response.text
    assert "temporary-enable-secret" not in response.text
    detect.assert_called_once_with(
        "10.10.1.2",
        2222,
        "network-user",
        "temporary-secret",
        "temporary-enable-secret",
    )
