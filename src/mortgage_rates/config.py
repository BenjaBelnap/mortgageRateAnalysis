"""Runtime configuration, sourced from env vars / .env (pydantic-settings)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MORTGAGE_RATES_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./mortgage_rates.db"
    lenders_config_path: Path = Path("lenders.yaml")
    log_level: str = "INFO"
    request_timeout_seconds: float = 15.0


def get_settings() -> Settings:
    return Settings()
