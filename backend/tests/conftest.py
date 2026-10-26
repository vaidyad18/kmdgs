"""Shared fixtures. API tests never touch the live Elexon network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def synthetic_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals = pd.DataFrame(
        {
            "startTime": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:30:00Z",
                    "2026-01-01T01:00:00Z",
                ],
                utc=True,
            ),
            "generation": [1000.0, 1100.0, 1200.0],
        }
    )
    forecasts = pd.DataFrame(
        {
            "startTime": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                ],
                utc=True,
            ),
            "publishTime": pd.to_datetime(
                [
                    "2025-12-30T08:00:00Z",
                    "2025-12-31T08:00:00Z",
                    "2025-12-31T12:00:00Z",
                    "2025-12-31T08:00:00Z",
                ],
                utc=True,
            ),
            "generation": [900.0, 950.0, 999.0, 1300.0],
        }
    )
    return actuals, forecasts


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthetic_frames):
    actuals, forecasts = synthetic_frames
    snap = tmp_path / "snapshot"
    cache = tmp_path / "cache"
    snap.mkdir()
    actuals.to_parquet(snap / "actuals.parquet", index=False)
    forecasts.to_parquet(snap / "forecasts.parquet", index=False)
    (snap / "meta.json").write_text('{"last_refresh":"2026-02-01T00:00:00Z"}', encoding="utf-8")
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap))
    monkeypatch.setenv("DATA_CACHE_DIR", str(cache))
    monkeypatch.setenv("REFRESH_TOKEN", "secret")
    get_settings.cache_clear()
    from app.main import create_app

    application = create_app()
    with TestClient(application) as client:
        yield client
    get_settings.cache_clear()
