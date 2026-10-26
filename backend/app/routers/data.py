"""Actuals and forecast query endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pandas as pd
from fastapi import APIRouter, Query

from app.config import DECISION_CUTOFF_RULE
from app.data_store import expected_half_hours
from app.deps import (
    CutoffQuery,
    SettingsDep,
    StoreDep,
    error_payload,
    parse_cutoff,
    parse_date_param,
    parse_iso_datetime,
    require_in_window,
    validate_range,
)
from app.forecast_selection import select_decision_forecasts
from app.jsonutil import iso_z, json_safe

router = APIRouter()


def _filter_start_end(
    frame: pd.DataFrame, start: datetime, end: datetime, column: str = "startTime"
) -> pd.DataFrame:
    return frame[(frame[column] >= start) & (frame[column] < end)]


@router.get("/actuals")
def actuals(
    store: StoreDep,
    settings: SettingsDep,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
) -> dict:
    start_date = require_in_window(parse_date_param(start, "start", settings.data_start), settings, "start")
    end_date = parse_date_param(end, "end", settings.data_end_exclusive)
    if end is None:
        end_exclusive = settings.data_end_exclusive
    else:
        end_exclusive = end_date if end_date == settings.data_end_exclusive else end_date + timedelta(days=1)
        if end_date < settings.data_start or end_date > settings.data_end_exclusive:
            raise error_payload(
                400, "date_out_of_range", "end is outside the configured window", {"end": end}
            )
    if start_date >= end_exclusive:
        raise error_payload(400, "invalid_range", "start must be before end")
    actuals_df, _ = store.snapshot_frames()
    start_ts = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_ts = datetime.combine(end_exclusive, time.min, tzinfo=UTC)
    window = _filter_start_end(actuals_df, start_ts, end_ts)
    expected = expected_half_hours(start_date, end_exclusive)
    present = set(window["startTime"]) if not window.empty else set()
    rows = [
        {"startTime": iso_z(row.startTime), "actual_mw": float(row.generation)}
        for row in window.itertuples(index=False)
    ]
    return json_safe(
        {
            "start": iso_z(start_ts),
            "end": iso_z(end_ts),
            "n": len(rows),
            "expected_half_hours": int(len(expected)),
            "missing_actuals": int(len(expected) - len(present)),
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            "records": rows,
        }
    )


def _decision_payload(
    store,
    settings,
    start_date: date,
    end_date_inclusive: date,
    cutoff_time: str,
) -> dict:
    require_in_window(start_date, settings, "start_date")
    require_in_window(end_date_inclusive, settings, "end_date")
    validate_range(start_date, end_date_inclusive)
    end_exclusive = end_date_inclusive + timedelta(days=1)
    if end_exclusive > settings.data_end_exclusive:
        end_exclusive = settings.data_end_exclusive
    actuals_df, forecasts_df = store.snapshot_frames()
    start_ts = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_ts = datetime.combine(end_exclusive, time.min, tzinfo=UTC)
    forecasts_window = _filter_start_end(forecasts_df, start_ts, end_ts)
    actuals_window = _filter_start_end(actuals_df, start_ts, end_ts)
    selected = select_decision_forecasts(forecasts_window, cutoff_time)
    grid = pd.DataFrame({"startTime": expected_half_hours(start_date, end_exclusive)})
    merged = grid.merge(selected, on="startTime", how="left")
    if not actuals_window.empty:
        merged = merged.merge(
            actuals_window.rename(columns={"generation": "actual_mw"}),
            on="startTime",
            how="left",
        )
    else:
        merged["actual_mw"] = pd.NA
    merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
    records = []
    for row in merged.itertuples(index=False):
        forecast = None if pd.isna(row.forecast_mw) else float(row.forecast_mw)
        actual = None if pd.isna(row.actual_mw) else float(row.actual_mw)
        error = None if forecast is None or actual is None else forecast - actual
        publish = None if pd.isna(row.publishTime) else iso_z(row.publishTime)
        horizon = None if pd.isna(row.horizon_hours) else float(row.horizon_hours)
        records.append(
            {
                "startTime": iso_z(row.startTime),
                "forecast_mw": forecast,
                "publishTime": publish,
                "horizon_hours": horizon,
                "actual_mw": actual,
                "error_mw": error,
            }
        )
    forecast_series = merged["forecast_mw"].dropna()
    publish_series = merged["publishTime"].dropna()
    summary = {
        "min_forecast_mw": float(forecast_series.min()) if not forecast_series.empty else None,
        "max_forecast_mw": float(forecast_series.max()) if not forecast_series.empty else None,
        "mean_forecast_mw": float(forecast_series.mean()) if not forecast_series.empty else None,
        "forecast_publish_time_min": iso_z(publish_series.min()) if not publish_series.empty else None,
        "forecast_publish_time_max": iso_z(publish_series.max()) if not publish_series.empty else None,
        "slots": int(len(merged)),
        "slots_with_forecast": int(forecast_series.shape[0]),
        "slots_with_actual": int(merged["actual_mw"].notna().sum()),
        "slots_with_both": int((merged["forecast_mw"].notna() & merged["actual_mw"].notna()).sum()),
    }
    return json_safe(
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date_inclusive.isoformat(),
            "cutoff_time": cutoff_time,
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            "summary": summary,
            "records": records,
        }
    )


@router.get("/forecasts/decision")
def forecasts_decision(
    store: StoreDep,
    settings: SettingsDep,
    delivery_date: str = Query(..., description="Delivery day YYYY-MM-DD"),
    cutoff_time: CutoffQuery = None,
) -> dict:
    day = require_in_window(
        parse_date_param(delivery_date, "delivery_date", settings.data_start), settings, "delivery_date"
    )
    cutoff = parse_cutoff(cutoff_time, settings)
    return _decision_payload(store, settings, day, day, cutoff)


@router.get("/forecasts/decision/range")
def forecasts_decision_range(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    start = require_in_window(
        parse_date_param(start_date, "start_date", settings.data_start), settings, "start_date"
    )
    end_default = settings.data_end_exclusive - timedelta(days=1)
    end = require_in_window(parse_date_param(end_date, "end_date", end_default), settings, "end_date")
    cutoff = parse_cutoff(cutoff_time, settings)
    return _decision_payload(store, settings, start, end, cutoff)


@router.get("/forecasts/vintages")
def forecast_vintages(
    store: StoreDep,
    settings: SettingsDep,
    target_time: str = Query(..., description="Target half-hour ISO-8601 UTC"),
) -> dict:
    instant = parse_iso_datetime(target_time, "target_time")
    instant_date = instant.date()
    require_in_window(instant_date, settings, "target_time")
    _, forecasts = store.snapshot_frames()
    window = forecasts[forecasts["startTime"] == pd.Timestamp(instant)]
    records = [
        {
            "publishTime": iso_z(row.publishTime),
            "forecast_mw": float(row.generation),
            "horizon_hours": float((row.startTime - row.publishTime).total_seconds() / 3600.0),
        }
        for row in window.sort_values("publishTime").itertuples(index=False)
    ]
    return json_safe(
        {
            "target_time": iso_z(instant),
            "n": len(records),
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            "records": records,
        }
    )
