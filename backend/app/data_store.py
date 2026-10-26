"""On-disk cache, committed snapshot fallback, and in-memory store with swap lock."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.config import Settings
from app.elexon_client import ElexonClient
from app.models import ActualRecord, ForecastRecord

logger = logging.getLogger(__name__)


def expected_half_hours(start: date, end_exclusive: date) -> pd.DatetimeIndex:
    start_ts = pd.Timestamp(datetime(start.year, start.month, start.day, tzinfo=UTC))
    end_ts = pd.Timestamp(datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=UTC))
    return pd.date_range(start_ts, end_ts, freq="30min", inclusive="left")


def _validate_rows(rows: list[dict[str, Any]], model: type, dataset: str) -> tuple[pd.DataFrame, int]:
    parsed: list[dict[str, Any]] = []
    bad = 0
    for row in rows:
        try:
            item = model.model_validate(row)
            parsed.append(item.model_dump())
        except (ValidationError, TypeError, ValueError):
            bad += 1
            logger.warning("skip_malformed_row", extra={"dataset": dataset, "row": row})
    return pd.DataFrame(parsed), bad


def normalize_actuals(
    rows: list[dict[str, Any]], start: date, end_exclusive: date
) -> tuple[pd.DataFrame, int]:
    wind_rows = [row for row in rows if str(row.get("fuelType", "")).upper() == "WIND"]
    dropped_non_wind = len(rows) - len(wind_rows)
    if dropped_non_wind:
        logger.info("dropped_non_wind_rows", extra={"count": dropped_non_wind})
    frame, bad = _validate_rows(wind_rows, ActualRecord, "FUELHH")
    if frame.empty:
        return pd.DataFrame(columns=["startTime", "generation"]), bad
    frame["startTime"] = pd.to_datetime(frame["startTime"], utc=True)
    start_ts = pd.Timestamp(datetime(start.year, start.month, start.day, tzinfo=UTC))
    end_ts = pd.Timestamp(datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=UTC))
    before = len(frame)
    frame = frame[(frame.startTime >= start_ts) & (frame.startTime < end_ts)]
    logger.info("filtered_actuals_to_window", extra={"before": before, "after": len(frame)})
    frame = frame.drop_duplicates(["startTime"], keep="last").sort_values("startTime").reset_index(drop=True)
    return frame[["startTime", "generation"]], bad


def normalize_forecasts(
    rows: list[dict[str, Any]], start: date, end_exclusive: date
) -> tuple[pd.DataFrame, int]:
    frame, bad = _validate_rows(rows, ForecastRecord, "WINDFOR")
    if frame.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "generation"]), bad
    frame["startTime"] = pd.to_datetime(frame["startTime"], utc=True)
    frame["publishTime"] = pd.to_datetime(frame["publishTime"], utc=True)
    start_ts = pd.Timestamp(datetime(start.year, start.month, start.day, tzinfo=UTC))
    end_ts = pd.Timestamp(datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=UTC))
    before = len(frame)
    frame = frame[(frame.startTime >= start_ts) & (frame.startTime < end_ts)]
    logger.info("filtered_forecasts_to_window", extra={"before": before, "after": len(frame)})
    frame = frame.drop_duplicates(["startTime", "publishTime"], keep="last")
    frame = frame.sort_values(["startTime", "publishTime"]).reset_index(drop=True)
    return frame[["startTime", "publishTime", "generation"]], bad


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    parse = ["startTime"]
    header = path.read_text(encoding="utf-8").splitlines()[0] if path.exists() else ""
    if "publishTime" in header:
        parse.append("publishTime")
    return pd.read_csv(path, parse_dates=parse)


def _write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


class DataStore:
    """Thread-safe in-memory frames plus parquet/JSON on disk."""

    def __init__(self, settings: Settings, client: ElexonClient) -> None:
        self.settings = settings
        self.client = client
        self.snapshot_dir = Path(settings.snapshot_dir)
        self.cache_dir = Path(settings.data_cache_dir)
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self.actuals = pd.DataFrame(columns=["startTime", "generation"])
        self.forecasts = pd.DataFrame(columns=["startTime", "publishTime", "generation"])
        self.last_refresh: datetime | None = None
        self.source = "empty"
        self.invalid_actual_rows = 0
        self.invalid_forecast_rows = 0

    def load(self) -> None:
        """Load disk cache, else committed snapshot. Never requires the network."""
        if self._load_from(self.cache_dir, source="disk_cache"):
            return
        if self._load_from(self.snapshot_dir, source="snapshot"):
            return
        logger.warning("no_cache_or_snapshot")

    def _load_from(self, directory: Path, source: str) -> bool:
        actuals_path = self._first_existing(directory, ["actuals.parquet", "actuals.csv"])
        forecasts_path = self._first_existing(directory, ["forecasts.parquet", "forecasts.csv"])
        if actuals_path is None or forecasts_path is None:
            return False
        actuals = _read_table(actuals_path)
        forecasts = _read_table(forecasts_path)
        meta_path = directory / "meta.json"
        last_refresh = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            raw = meta.get("last_refresh")
            if raw:
                last_refresh = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        with self._lock:
            self.actuals = actuals
            self.forecasts = forecasts
            self._ensure_utc()
            self.source = source
            self.last_refresh = last_refresh
        logger.info(
            "loaded_store",
            extra={"source": source, "actuals": len(self.actuals), "forecasts": len(self.forecasts)},
        )
        return True

    @staticmethod
    def _first_existing(directory: Path, names: list[str]) -> Path | None:
        for name in names:
            path = directory / name
            if path.exists():
                return path
        return None

    def _ensure_utc(self) -> None:
        if "startTime" in self.actuals.columns:
            self.actuals["startTime"] = pd.to_datetime(self.actuals["startTime"], utc=True)
        if "startTime" in self.forecasts.columns:
            self.forecasts["startTime"] = pd.to_datetime(self.forecasts["startTime"], utc=True)
        if "publishTime" in self.forecasts.columns:
            self.forecasts["publishTime"] = pd.to_datetime(self.forecasts["publishTime"], utc=True)

    def snapshot_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with self._lock:
            return self.actuals.copy(), self.forecasts.copy()

    def refresh(self) -> dict[str, Any]:
        """Re-fetch from Elexon, rebuild cache, then atomically swap memory."""
        with self._refresh_lock:
            settings = self.settings
            raw_actuals = self.client.fetch_actuals(settings.data_start, settings.data_end_exclusive)
            publish_start = datetime(
                settings.forecast_publish_start.year,
                settings.forecast_publish_start.month,
                settings.forecast_publish_start.day,
                tzinfo=UTC,
            )
            publish_end = datetime(
                settings.forecast_publish_end_exclusive.year,
                settings.forecast_publish_end_exclusive.month,
                settings.forecast_publish_end_exclusive.day,
                tzinfo=UTC,
            )
            raw_forecasts = self.client.fetch_forecasts(publish_start, publish_end)
            actuals, bad_a = normalize_actuals(raw_actuals, settings.data_start, settings.data_end_exclusive)
            forecasts, bad_f = normalize_forecasts(
                raw_forecasts, settings.data_start, settings.data_end_exclusive
            )
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "actuals_raw.json").write_text(json.dumps(raw_actuals), encoding="utf-8")
            (self.cache_dir / "forecasts_raw.json").write_text(json.dumps(raw_forecasts), encoding="utf-8")
            _write_table(actuals, self.cache_dir / "actuals.parquet")
            _write_table(forecasts, self.cache_dir / "forecasts.parquet")
            stamp = datetime.now(UTC)
            meta = {
                "last_refresh": stamp.isoformat().replace("+00:00", "Z"),
                "source": "live_refresh",
                "invalid_actual_rows": bad_a,
                "invalid_forecast_rows": bad_f,
            }
            (self.cache_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            with self._lock:
                self.actuals = actuals
                self.forecasts = forecasts
                self.invalid_actual_rows = bad_a
                self.invalid_forecast_rows = bad_f
                self.last_refresh = stamp
                self.source = "live_refresh"
            coverage = self.coverage()
            return {
                "actual_records": len(actuals),
                "forecast_records": len(forecasts),
                "invalid_actual_rows": bad_a,
                "invalid_forecast_rows": bad_f,
                "coverage": coverage,
                "last_refresh": stamp,
            }

    def write_snapshot(self) -> None:
        """Persist the current frames into the committed snapshot directory."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            actuals = self.actuals.copy()
            forecasts = self.forecasts.copy()
            stamp = self.last_refresh or datetime.now(UTC)
        _write_table(actuals, self.snapshot_dir / "actuals.parquet")
        _write_table(forecasts, self.snapshot_dir / "forecasts.parquet")
        meta = {
            "last_refresh": stamp.isoformat().replace("+00:00", "Z"),
            "source": "snapshot",
            "actual_records": len(actuals),
            "forecast_records": len(forecasts),
        }
        (self.snapshot_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def coverage(self) -> dict[str, Any]:
        with self._lock:
            actuals = self.actuals
            forecasts = self.forecasts
            invalid_a = self.invalid_actual_rows
            invalid_f = self.invalid_forecast_rows
        expected = expected_half_hours(self.settings.data_start, self.settings.data_end_exclusive)
        expected_n = int(len(expected))
        actual_times = set(actuals["startTime"]) if not actuals.empty else set()
        forecast_times = set(forecasts["startTime"]) if not forecasts.empty else set()
        actual_present = int(sum(ts in actual_times for ts in expected))
        native_forecast_present = int(sum(ts in forecast_times for ts in expected))
        joined_native = int(len(actual_times & forecast_times))
        return {
            "expected_half_hours": expected_n,
            "actual_records": int(len(actuals)),
            "forecast_records": int(len(forecasts)),
            "actuals_in_window": actual_present,
            "missing_actuals": expected_n - actual_present,
            "targets_with_any_forecast": native_forecast_present,
            "missing_forecast_targets": expected_n - native_forecast_present,
            "joined_native_records": joined_native,
            "actual_coverage_pct": round(100 * actual_present / expected_n, 2) if expected_n else 0.0,
            "native_forecast_coverage_pct": round(100 * native_forecast_present / expected_n, 2)
            if expected_n
            else 0.0,
            "invalid_actual_rows": invalid_a,
            "invalid_forecast_rows": invalid_f,
            "note": (
                "WINDFOR startTimes are hourly. native_forecast_coverage_pct is relative to "
                "1488 half-hours; ~50% is expected when every hourly slot is populated."
            ),
        }
