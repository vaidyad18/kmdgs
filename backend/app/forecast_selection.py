"""Pure, vectorized selection of the latest eligible wind forecast vintage."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pandas as pd

DECISION_COLUMNS = ["startTime", "publishTime", "forecast_mw", "decision_cutoff", "horizon_hours"]
LATEST_COLUMNS = ["startTime", "publishTime", "forecast_mw", "horizon_hours"]


def decision_cutoff(delivery_day: date, cutoff_time: str = "09:00") -> datetime:
    """Gate-closure instant for delivery day D: D-1 at cutoff_time, UTC.

    January 2026 is GMT in Europe/London, so 09:00 UTC == 09:00 London.
    """
    hour, minute = map(int, cutoff_time.split(":"))
    return datetime.combine(delivery_day - timedelta(days=1), time(hour, minute), tzinfo=UTC)


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype="object") for name in columns})


def _prepare(forecasts: pd.DataFrame) -> pd.DataFrame:
    data = forecasts[["startTime", "publishTime", "generation"]].copy()
    data["startTime"] = pd.to_datetime(data["startTime"], utc=True)
    data["publishTime"] = pd.to_datetime(data["publishTime"], utc=True)
    return data.drop_duplicates(["startTime", "publishTime"], keep="last")


def select_decision_forecasts(forecasts: pd.DataFrame, cutoff_time: str = "09:00") -> pd.DataFrame:
    """Latest forecast available at day-ahead gate closure, with no look-ahead.

    For each target ``startTime`` T on delivery day D, keep vintages with the
    same T whose ``publishTime`` is <= cutoff(D-1), then take MAX(publishTime).

    Vectorized via a single cutoff timestamp per row, a boolean mask, a sort,
    and ``drop_duplicates(startTime, keep='last')``. Duplicate
    (startTime, publishTime) rows are collapsed first.
    """
    if forecasts.empty:
        return _empty(DECISION_COLUMNS)
    data = _prepare(forecasts)
    hour, minute = map(int, cutoff_time.split(":"))
    data["decision_cutoff"] = (
        data["startTime"].dt.normalize() - pd.Timedelta(days=1) + pd.Timedelta(hours=hour, minutes=minute)
    )
    eligible = data.loc[data["publishTime"] <= data["decision_cutoff"]]
    if eligible.empty:
        return _empty(DECISION_COLUMNS)
    chosen = eligible.sort_values(["startTime", "publishTime"]).drop_duplicates("startTime", keep="last")
    chosen = chosen.rename(columns={"generation": "forecast_mw"})
    chosen["horizon_hours"] = (chosen["startTime"] - chosen["publishTime"]).dt.total_seconds() / 3600.0
    return chosen[DECISION_COLUMNS].sort_values("startTime").reset_index(drop=True)


def select_latest_before_target(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Latest vintage published at or before the target time (horizon analysis).

    Distinct from decision-time mode: this is allowed to use intra-day updates
    after the D-1 gate closure, but still forbids publishTime > startTime.
    """
    if forecasts.empty:
        return _empty(LATEST_COLUMNS)
    data = _prepare(forecasts)
    eligible = data.loc[data["publishTime"] <= data["startTime"]]
    if eligible.empty:
        return _empty(LATEST_COLUMNS)
    chosen = eligible.sort_values(["startTime", "publishTime"]).drop_duplicates("startTime", keep="last")
    chosen = chosen.rename(columns={"generation": "forecast_mw"})
    chosen["horizon_hours"] = (chosen["startTime"] - chosen["publishTime"]).dt.total_seconds() / 3600.0
    return chosen[LATEST_COLUMNS].sort_values("startTime").reset_index(drop=True)


def select_all_vintages_before_target(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Every vintage published at or before the target time (for horizon analysis).

    Unlike ``select_latest_before_target`` this keeps all vintages, so each
    forecast horizon (0-6h, 6-12h, ... 48h+) can be scored separately.
    """
    if forecasts.empty:
        return _empty(LATEST_COLUMNS)
    data = _prepare(forecasts)
    eligible = data.loc[data["publishTime"] <= data["startTime"]].copy()
    if eligible.empty:
        return _empty(LATEST_COLUMNS)
    eligible = eligible.rename(columns={"generation": "forecast_mw"})
    eligible["horizon_hours"] = (eligible["startTime"] - eligible["publishTime"]).dt.total_seconds() / 3600.0
    return eligible[LATEST_COLUMNS].sort_values(["startTime", "publishTime"]).reset_index(drop=True)
