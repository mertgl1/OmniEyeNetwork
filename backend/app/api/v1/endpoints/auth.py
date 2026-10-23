from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.ldap import ad_service
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate via Active Directory / LDAP (or local user) and return JWT access token."""
    username = login_data.username.strip()
    password = login_data.password

    # 1. First attempt Active Directory / LDAP authentication
    ldap_user = await ad_service.authenticate(username, password)

    if ldap_user:
        # Sync AD user to local DB
        result = await db.execute(select(User).filter(User.username == ldap_user.username))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                username=ldap_user.username,
                display_name=ldap_user.display_name,
                email=ldap_user.email,
                role=ldap_user.role,
                is_active=True,
                is_ad_user=True,
                last_login=datetime.now(timezone.utc),
            )
            db.add(user)
        else:
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated.",
                )
            # Update role and profile attributes from AD groups
            user.display_name = ldap_user.display_name
            user.email = ldap_user.email
            user.role = ldap_user.role
            user.last_login = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)

        token = create_access_token(
            subject=user.username,
            role=user.role,
            extra_claims={"display_name": user.display_name},
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            username=user.username,
            display_name=user.display_name,
        )

    # 2. Fallback to local DB user verification (if created locally)
    result = await db.execute(select(User).filter(User.username == username))
    local_user = result.scalar_one_or_none()

    if local_user and local_user.hashed_password and verify_password(password, local_user.hashed_password):
        if not local_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        if not local_user.hashed_password.startswith("pbkdf2_sha256$"):
            from app.core.security import get_password_hash

            local_user.hashed_password = get_password_hash(password)
        local_user.last_login = datetime.now(timezone.utc)
        await db.commit()

        token = create_access_token(
            subject=local_user.username,
            role=local_user.role,
            extra_claims={"display_name": local_user.display_name},
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=local_user.role,
            username=local_user.username,
            display_name=local_user.display_name,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Active Directory or local authentication failed.",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile and assigned role of current authenticated user."""
    return current_user


@router.get("/roles")
async def list_roles():
    """List available RBAC roles and permissions."""
    return [
        {
            "role": "admin",
            "ad_group": "Network_Admins",
            "description": "Full access to inventory, credentials Vault, Web SSH terminal, and configuration changes.",
        },
        {
            "role": "operator",
            "ad_group": "Network_Operators",
            "description": "Access to Web SSH terminal, live config views, and port status inspections.",
        },
        {
            "role": "viewer",
            "ad_group": "Network_Viewers",
            "description": "Read-only access to switch inventories, port mappings, and backup histories.",
        },
    ]
