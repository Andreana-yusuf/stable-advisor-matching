from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "Alokasi Pembimbing Skripsi"
    debug: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/alokasi_pembimbing"
    db_echo: bool = False
    admin_api_key: str = Field(default="dev-admin-key", min_length=8)
    cors_origins: list[str] = []


settings = Settings()