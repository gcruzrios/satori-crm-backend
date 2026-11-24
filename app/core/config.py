from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "satori-crm-backend"
    app_env: Literal["development", "staging", "production"] = "production"
    # Required: set via environment variables / .env (never commit real values).
    database_url: str
    database_url_sync: str | None = None
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    redis_url: str = "redis://localhost:6379/0"
    # Comma-separated list of allowed browser origins (override with CORS_ORIGINS).
    cors_origins: str = "https://crm.satori.cr,https://satoricrm.greiv.in"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
