from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import base64
import hashlib
import hmac
import secrets
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify PBKDF2 password hashes and legacy salted SHA-256 hashes."""
    try:
        algorithm, iterations, salt, stored_hash = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"),
            base64.urlsafe_b64decode(salt.encode("ascii")), int(iterations),
        )
        return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode("ascii"), stored_hash)
    except (ValueError, TypeError):
        try:
            salt, stored_hash = hashed_password.split("$", 1)
            computed_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
            return hmac.compare_digest(stored_hash, computed_hash)
        except ValueError:
            return False


def get_password_hash(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join((
        "pbkdf2_sha256",
        str(iterations),
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    ))


def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates an encrypted JWT access token containing subject, role and expiration."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
