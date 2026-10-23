import pytest
from app.core.ldap import ad_service
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password


@pytest.mark.asyncio
async def test_ldap_authentication_admin():
    user = await ad_service.authenticate("admin", "admin123")
    assert user is not None
    assert user.username == "admin"
    assert user.role == "admin"
    assert "Network_Admins" in user.groups


@pytest.mark.asyncio
async def test_ldap_authentication_operator():
    user = await ad_service.authenticate("operator", "operator123")
    assert user is not None
    assert user.username == "operator"
    assert user.role == "operator"
    assert "Network_Operators" in user.groups


@pytest.mark.asyncio
async def test_ldap_authentication_viewer():
    user = await ad_service.authenticate("viewer", "viewer123")
    assert user is not None
    assert user.username == "viewer"
    assert user.role == "viewer"


@pytest.mark.asyncio
async def test_ldap_authentication_invalid_password():
    user = await ad_service.authenticate("admin", "wrong_password_999")
    assert user is None


def test_role_mapping_prefers_highest_privilege():
    assert ad_service._map_groups_to_role(
        ["CN=Network_Viewers,OU=Groups,DC=example,DC=local", "CN=Network_Admins,OU=Groups,DC=example,DC=local"]
    ) == "admin"


def test_password_hashing():
    pw = "NetworkSec2026!"
    hashed = get_password_hash(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_token_flow():
    token = create_access_token(subject="netadmin", role="admin", extra_claims={"org": "NOC"})
    payload = decode_access_token(token)
    assert payload["sub"] == "netadmin"
    assert payload["role"] == "admin"
    assert payload["org"] == "NOC"
    assert "exp" in payload
