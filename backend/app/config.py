from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Конфигурация из переменных окружения (см. .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://runners:runners@localhost:5432/runners"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "tracks"
    s3_region: str = "us-east-1"
    health_timeout_s: int = 2

    # Аутентификация
    jwt_secret: str = "dev-insecure-secret-change-me-0123456789"
    access_token_ttl_s: int = 15 * 60
    refresh_token_ttl_s: int = 30 * 24 * 3600
    google_client_id: str | None = None
    auth_dev_login: bool = False
    cookie_secure: bool = False

    @field_validator("google_client_id")
    @classmethod
    def _empty_is_none(cls, value: str | None) -> str | None:
        return value or None


@lru_cache
def get_config() -> Config:
    return Config()
