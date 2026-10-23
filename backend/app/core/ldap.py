import os
from typing import Dict, List, Optional
from pydantic import BaseModel


class LDAPUser(BaseModel):
    username: str
    display_name: str
    email: str
    groups: List[str]
    role: str  # admin, operator, viewer


class ActiveDirectoryService:
    """Active Directory / LDAP Authentication & Role Mapping Service.
    Maps corporate AD security groups to OmniEye RBAC roles:
      - Network_Admins   -> admin (full access, vault, Web SSH, config change)
      - Network_Operators-> operator (Web SSH, live config, port operations)
      - Network_Viewers  -> viewer (read-only view)
    """

    def __init__(self):
        self.server = os.getenv("AD_SERVER", "ldap://ad.corp.local")
        self.domain = os.getenv("AD_DOMAIN", "corp.local")
        self.base_dn = os.getenv("AD_BASE_DN", "DC=corp,DC=local")
        self.admin_group = os.getenv("AD_GROUP_ADMIN", "Network_Admins")
        self.operator_group = os.getenv("AD_GROUP_OPERATOR", "Network_Operators")
        self.viewer_group = os.getenv("AD_GROUP_VIEWER", "Network_Viewers")
        self.mock_mode = os.getenv("AD_MOCK_MODE", "true").lower() in ("true", "1", "yes")

    def _map_groups_to_role(self, groups: List[str]) -> str:
        """Determines role based on AD group memberships."""
        for g in groups:
            clean_g = g.lower()
            if self.admin_group.lower() in clean_g:
                return "admin"
            if self.operator_group.lower() in clean_g:
                return "operator"
            if self.viewer_group.lower() in clean_g:
                return "viewer"
        return "viewer"

    async def authenticate(self, username: str, password: str) -> Optional[LDAPUser]:
        """Authenticates user against AD/LDAP or fallback mock mode."""
        if not username or not password:
            return None

        # Mock / Development mode for local setups & test suite
        if self.mock_mode:
            clean_username = username.split("@")[0].lower()
            # Default test users
            if clean_username in ("admin", "netadmin") and password in ("admin123", "password", "test"):
                return LDAPUser(
                    username="admin",
                    display_name="Network Administrator",
                    email="admin@omnieye.local",
                    groups=["Network_Admins", "Domain Users"],
                    role="admin",
                )
            elif clean_username in ("operator", "netop") and password in ("operator123", "password", "test"):
                return LDAPUser(
                    username="operator",
                    display_name="Network Operator",
                    email="operator@omnieye.local",
                    groups=["Network_Operators", "Domain Users"],
                    role="operator",
                )
            elif clean_username in ("viewer", "guest") and password in ("viewer123", "password", "test"):
                return LDAPUser(
                    username="viewer",
                    display_name="Network Viewer",
                    email="viewer@omnieye.local",
                    groups=["Network_Viewers", "Domain Users"],
                    role="viewer",
                )
            return None

        # Real LDAP connection logic (when AD is live in production)
        try:
            import ldap3  # type: ignore
            user_dn = f"{username}@{self.domain}" if "@" not in username else username
            server = ldap3.Server(self.server, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)

            # Search user attributes & memberOf
            search_filter = f"(&(objectClass=user)(sAMAccountName={username.split('@')[0]}))"
            conn.search(self.base_dn, search_filter, attributes=["displayName", "mail", "memberOf"])
            if not conn.entries:
                return None

            entry = conn.entries[0]
            display_name = str(entry.displayName.value) if entry.displayName else username
            email = str(entry.mail.value) if entry.mail else f"{username}@{self.domain}"
            raw_groups = [str(g) for g in entry.memberOf.values] if entry.memberOf else []

            role = self._map_groups_to_role(raw_groups)
            return LDAPUser(
                username=username.split("@")[0],
                display_name=display_name,
                email=email,
                groups=raw_groups,
                role=role,
            )
        except Exception:
            return None


ad_service = ActiveDirectoryService()
