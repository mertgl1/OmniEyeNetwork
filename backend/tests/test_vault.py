import pytest
from app.core.vault import VaultEngine, vault


def test_vault_encryption_and_decryption():
    raw_creds = {
        "username": "cisco_admin",
        "password": "SuperSecretPassword123!",
        "enable_secret": "EnableSecret987!",
    }

    encrypted = vault.encrypt_credentials(raw_creds)
    assert encrypted != ""
    assert "SuperSecretPassword123!" not in encrypted
    assert "cisco_admin" not in encrypted

    decrypted = vault.decrypt_credentials(encrypted)
    assert decrypted == raw_creds
    assert decrypted["username"] == "cisco_admin"
    assert decrypted["password"] == "SuperSecretPassword123!"
    assert decrypted["enable_secret"] == "EnableSecret987!"


def test_vault_empty_credentials():
    assert vault.decrypt_credentials(None) is None
    assert vault.decrypt_credentials("") is None


def test_vault_tampered_ciphertext():
    raw_creds = {"username": "admin", "password": "123"}
    encrypted = vault.encrypt_credentials(raw_creds)

    # Tamper with encrypted string
    tampered = encrypted[:-5] + "AAAAA"
    with pytest.raises(Exception):
        vault.decrypt_credentials(tampered)


def test_vault_custom_key_generation():
    key1 = VaultEngine.generate_new_vault_key()
    key2 = VaultEngine.generate_new_vault_key()
    assert key1 != key2
    assert len(key1) > 20

    custom_vault = VaultEngine(key=key1)
    encrypted = custom_vault.encrypt_credentials({"secret": "val"})
    assert custom_vault.decrypt_credentials(encrypted) == {"secret": "val"}
