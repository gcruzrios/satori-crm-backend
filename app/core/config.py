from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "satori-crm-backend"
    app_env: Literal["development", "staging", "production"] = "production"
    database_url: str = "postgresql+asyncpg://user:REDACTED@host/neondb?sslmode=require&channel_binding=require"
    database_url_sync: str = "postgresql://user:REDACTED@host/neondb?sslmode=require&channel_binding=require"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
