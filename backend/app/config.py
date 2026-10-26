"""Application configuration loaded from environment variables."""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CUTOFF_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

DECISION_CUTOFF_RULE = (
    "For delivery day D, the purchase decision uses the latest WINDFOR vintage "
    "with the same startTime whose publishTime is at or before D-1 at cutoff_time UTC "
    "(default 09:00 UTC, which is 09:00 Europe/London in January). "
    "Forecasts published after the cutoff are never used. "
    "WINDFOR is hourly; FUELHH is half-hourly. Exact startTime matches only; "
    "missing slots are null, never interpolated."
)


class Settings(BaseSettings):
    """Runtime settings. Names map to uppercase env vars (e.g. CORS_ORIGINS)."""

    port: int = 8000
    cors_origins: str = "*"
    refresh_token: str | None = None
    default_cutoff_time: str = "09:00"
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    data_cache_dir: Path = Path("./data_cache")
    snapshot_dir: Path = Path("./data/snapshot")
    log_level: str = "INFO"
    static_dir: Path = Path("./static")  # built React app, served at "/" when present
    data_start: date = Field(default=date(2026, 1, 1))
    data_end_exclusive: date = Field(default=date(2026, 2, 1))
    # Publish window: verified ~66.5h max WINDFOR horizon; 2025-12-25 is a buffer.
    forecast_publish_start: date = Field(default=date(2025, 12, 25))
    forecast_publish_end_exclusive: date = Field(default=date(2026, 2, 1))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("default_cutoff_time")
    @classmethod
    def validate_cutoff(cls, value: str) -> str:
        if not CUTOFF_PATTERN.fullmatch(value):
            raise ValueError("DEFAULT_CUTOFF_TIME must use HH:MM (UTC)")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
