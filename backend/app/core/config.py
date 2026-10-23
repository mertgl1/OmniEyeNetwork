from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OmniEyeNetwork"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DB_HOST: str = "mariadb"
    DB_PORT: int = 3306
    DB_USER: str = "omnieye_user"
    DB_PASSWORD: str = "omnieye_secret_pass"
    DB_NAME: str = "omnieye_db"

    # Redis & Celery
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Security
    VAULT_SECRET_KEY: str = "k27jU6iXn1p7s2_v8xR3yA6b_E9gW1qT5z0mL4oI8c="
    SECRET_KEY: str = "supersecretjwtkeyforauthenticationshouldbechangedinproduction12345"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

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
        return f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def sync_database_url(self) -> str:
        if self.ENVIRONMENT == "test":
            return "sqlite:///:memory:"
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
