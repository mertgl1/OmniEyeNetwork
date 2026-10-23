from typing import List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OmniEyeNetwork"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Database
    DB_HOST: str = "mariadb"
    DB_PORT: int = 3306
    DB_USER: str = "omnieye_user"
    DB_PASSWORD: str = Field(min_length=1)
    DB_NAME: str = "omnieye_db"

    # Redis & Celery
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Security
    VAULT_SECRET_KEY: str = Field(min_length=1)
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    AD_MOCK_MODE: bool = False
    AD_SERVER: str = "ldaps://localhost"
    AD_DOMAIN: str = ""
    AD_BASE_DN: str = ""
    AD_USE_SSL: bool = True
    AD_GROUP_ADMIN: str = "Network_Admins"
    AD_GROUP_OPERATOR: str = "Network_Operators"
    AD_GROUP_VIEWER: str = "Network_Viewers"
    SSH_STRICT_HOST_KEY_CHECKING: bool = False
    NETWORK_SIMULATION_MODE: str = "false"
    CELERY_TIMEZONE: str = "Europe/Istanbul"

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT.lower() == "production":
            from cryptography.fernet import Fernet

            try:
                Fernet(self.VAULT_SECRET_KEY.encode())
            except (TypeError, ValueError) as exc:
                raise ValueError("Production requires a valid Fernet VAULT_SECRET_KEY.") from exc
            if self.AD_MOCK_MODE:
                raise ValueError("AD_MOCK_MODE must be disabled in production.")
            if self.DB_PASSWORD == "omnieye_secret_pass":
                raise ValueError("Production DB_PASSWORD must not use the development default.")
            if len(self.SECRET_KEY) < 48 or self.SECRET_KEY.startswith(
                "supersecretjwtkeyforauthenticationshouldbechangedinproduction"
            ):
                raise ValueError("Production SECRET_KEY must be at least 48 characters.")
            if self.ACCESS_TOKEN_EXPIRE_MINUTES > 60:
                raise ValueError("Production access tokens must expire within 60 minutes.")
            if not self.SSH_STRICT_HOST_KEY_CHECKING:
                raise ValueError("SSH_STRICT_HOST_KEY_CHECKING must be enabled in production.")
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled in production.")
            if not self.AD_USE_SSL or not self.AD_BASE_DN or not self.AD_DOMAIN:
                raise ValueError("Production requires LDAPS and a configured AD domain and base DN.")
            if self.NETWORK_SIMULATION_MODE.lower() in ("true", "1", "yes", "auto"):
                raise ValueError("Network simulation must be disabled in production.")
            if any(
                origin == "*" or "localhost" in origin or "127.0.0.1" in origin
                for origin in self.ALLOWED_ORIGINS
            ):
                raise ValueError("Production ALLOWED_ORIGINS must not include localhost.")
        return self

    # Backend
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    @property
    def async_database_url(self) -> str:
        if self.ENVIRONMENT == "test":
            return "sqlite+aiosqlite:///:memory:"
        from sqlalchemy.engine import URL

        return URL.create(
            "mysql+asyncmy",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    @property
    def sync_database_url(self) -> str:
        if self.ENVIRONMENT == "test":
            return "sqlite:///:memory:"
        from sqlalchemy.engine import URL

        return URL.create(
            "mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
