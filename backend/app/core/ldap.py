import asyncio
import logging
import ssl
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LDAPUser(BaseModel):
    username: str
    display_name: str
    email: str
    groups: List[str]
    role: str


class ActiveDirectoryService:
    """Authenticate AD users and map configured groups to application roles."""

    def __init__(self):
        self.server = settings.AD_SERVER
        self.domain = settings.AD_DOMAIN
        self.base_dn = settings.AD_BASE_DN
        self.use_ssl = settings.AD_USE_SSL
        self.admin_group = settings.AD_GROUP_ADMIN
        self.operator_group = settings.AD_GROUP_OPERATOR
        self.viewer_group = settings.AD_GROUP_VIEWER
        self.mock_mode = settings.AD_MOCK_MODE

    def _map_groups_to_role(self, groups: List[str]) -> str:
        normalized_groups = [group.lower() for group in groups]
        if any(self.admin_group.lower() in group for group in normalized_groups):
            return "admin"
        if any(self.operator_group.lower() in group for group in normalized_groups):
            return "operator"
        return "viewer"

    async def authenticate(self, username: str, password: str) -> Optional[LDAPUser]:
        """Authenticate against the configured directory without blocking the event loop."""
        if not username or not password:
            return None
        if self.mock_mode:
            return self._authenticate_mock(username, password)
        return await asyncio.to_thread(self._authenticate_directory, username, password)

    @staticmethod
    def _authenticate_mock(username: str, password: str) -> Optional[LDAPUser]:
        clean_username = username.split("@")[0].lower()
        mock_users = {
            "admin": ("admin123", "Network Administrator", "Network_Admins", "admin"),
            "netadmin": ("admin123", "Network Administrator", "Network_Admins", "admin"),
            "operator": ("operator123", "Network Operator", "Network_Operators", "operator"),
            "netop": ("operator123", "Network Operator", "Network_Operators", "operator"),
            "viewer": ("viewer123", "Network Viewer", "Network_Viewers", "viewer"),
            "guest": ("viewer123", "Network Viewer", "Network_Viewers", "viewer"),
        }
        user = mock_users.get(clean_username)
        if user is None or password not in (user[0], "password", "test"):
            return None
        _, display_name, group, role = user
        return LDAPUser(
            username=clean_username,
            display_name=display_name,
            email=f"{clean_username}@omnieye.local",
            groups=[group, "Domain Users"],
            role=role,
        )

    def _authenticate_directory(self, username: str, password: str) -> Optional[LDAPUser]:
        conn = None
        try:
            import ldap3  # type: ignore
            from ldap3.utils.conv import escape_filter_chars

            parsed_server = urlparse(
                self.server if "://" in self.server else f"ldaps://{self.server}"
            )
            if not parsed_server.hostname:
                raise ValueError("AD_SERVER must contain a valid LDAP server hostname.")
            use_ssl = self.use_ssl or parsed_server.scheme.lower() == "ldaps"
            server = ldap3.Server(
                parsed_server.hostname,
                port=parsed_server.port or (636 if use_ssl else 389),
                use_ssl=use_ssl,
                tls=ldap3.Tls(validate=ssl.CERT_REQUIRED),
                get_info=ldap3.NONE,
            )
            user_dn = f"{username}@{self.domain}" if "@" not in username and self.domain else username
            conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True,
            )

            if not self.base_dn:
                raise ValueError("AD_BASE_DN must be configured when LDAP authentication is enabled.")
            search_filter = (
                f"(&(objectClass=user)(sAMAccountName="
                f"{escape_filter_chars(username.split('@')[0])}))"
            )
            conn.search(self.base_dn, search_filter, attributes=["displayName", "mail", "memberOf"])
            if not conn.entries:
                return None

            entry = conn.entries[0]
            display_name = str(entry.displayName.value) if entry.displayName else username
            email = str(entry.mail.value) if entry.mail else f"{username}@{self.domain}"
            raw_groups = [str(group) for group in entry.memberOf.values] if entry.memberOf else []
            return LDAPUser(
                username=username.split("@")[0],
                display_name=display_name,
                email=email,
                groups=raw_groups,
                role=self._map_groups_to_role(raw_groups),
            )
        except Exception:
            logger.warning("LDAP authentication failed for user %s.", username, exc_info=True)
            return None
        finally:
            if conn is not None and conn.bound:
                conn.unbind()


ad_service = ActiveDirectoryService()
