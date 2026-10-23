from cryptography.fernet import Fernet

from app.core.config import Settings


def test_settings_load_runtime_keys_from_compose_secret_files(tmp_path):
    values = {
        "DB_PASSWORD": "db-secret-from-file",
        "VAULT_SECRET_KEY": Fernet.generate_key().decode("ascii"),
        "SECRET_KEY": "jwt-secret-value-that-is-long-enough-for-validation",
    }
    files = {}
    for name, value in values.items():
        path = tmp_path / name.lower()
        path.write_text(value + "\n", encoding="utf-8")
        files[f"{name}_FILE"] = str(path)

    settings = Settings(
        ENVIRONMENT="test",
        DB_PASSWORD="",
        VAULT_SECRET_KEY="",
        SECRET_KEY="",
        **files,
    )

    assert settings.DB_PASSWORD == values["DB_PASSWORD"]
    assert settings.VAULT_SECRET_KEY == values["VAULT_SECRET_KEY"]
    assert settings.SECRET_KEY == values["SECRET_KEY"]


def test_settings_report_unreadable_secret_file(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="Unable to read the configured DB_PASSWORD_FILE"):
        Settings(
            ENVIRONMENT="test",
            DB_PASSWORD="",
            DB_PASSWORD_FILE=str(tmp_path / "missing"),
        )
