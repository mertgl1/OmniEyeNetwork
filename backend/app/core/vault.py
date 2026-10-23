import base64
import json
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class VaultEngine:
    """AES-256 Vault engine for encrypting and decrypting sensitive network credentials.
    Ensures passwords and enable secrets are never stored in plaintext in the database.
    """

    def __init__(self, key: Optional[str] = None):
        raw_key = key or settings.VAULT_SECRET_KEY
        try:
            self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        except Exception:
            # Fallback: derive a valid 32-byte url-safe base64 key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"omnieye_static_salt_2026",
                iterations=100_000,
            )
            derived = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
            self._fernet = Fernet(derived)

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """Serializes and encrypts credentials dict into an AES-256 encrypted string."""
        json_str = json.dumps(credentials)
        encrypted_bytes = self._fernet.encrypt(json_str.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt_credentials(self, encrypted_data: Optional[str]) -> Optional[Dict[str, Any]]:
        """Decrypts AES-256 ciphertext and deserializes back into a credentials dict."""
        if not encrypted_data:
            return None
        decrypted_bytes = self._fernet.decrypt(encrypted_data.encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))

    @staticmethod
    def generate_new_vault_key() -> str:
        """Utility to generate a new 32-byte URL-safe base64 Fernet key."""
        return Fernet.generate_key().decode("utf-8")


# Global singleton instance
vault = VaultEngine()
