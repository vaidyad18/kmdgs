"""Accuracy analysis endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Query

from app.config import DECISION_CUTOFF_RULE
from app.deps import (
    CutoffQuery,
    SettingsDep,
    StoreDep,
    parse_cutoff,
    parse_date_param,
    require_in_window,
    validate_range,
)
from app.forecast_selection import select_all_vintages_before_target, select_decision_forecasts
from app.jsonutil import json_safe
from app.metrics import (
    breakdown_by_day,
    breakdown_by_horizon,
    breakdown_by_hour,
    breakdown_by_wind_level,
    compute_metrics,
    error_histogram,
    generate_insights,
    join_forecasts_actuals,
    rolling_24h,
)

router = APIRouter()


def _windowed(store, settings, start_date: str | None, end_date: str | None, cutoff_time: str | None):
    start = require_in_window(
        parse_date_param(start_date, "start_date", settings.data_start), settings, "start_date"
    )
    end_default = settings.data_end_exclusive - timedelta(days=1)
    end = require_in_window(parse_date_param(end_date, "end_date", end_default), settings, "end_date")
    validate_range(start, end)
    cutoff = parse_cutoff(cutoff_time, settings)
    actuals, forecasts = store.snapshot_frames()
    start_ts = datetime.combine(start, time.min, tzinfo=UTC)
    end_ts = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    actuals = actuals[(actuals["startTime"] >= start_ts) & (actuals["startTime"] < end_ts)]
    forecasts = forecasts[(forecasts["startTime"] >= start_ts) & (forecasts["startTime"] < end_ts)]
    decision = select_decision_forecasts(forecasts, cutoff)
    latest = select_all_vintages_before_target(forecasts)
    decision_joined, decision_counts = join_forecasts_actuals(decision, actuals)
    latest_joined, latest_counts = join_forecasts_actuals(latest, actuals)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "cutoff_time": cutoff,
        "decision_cutoff_rule": DECISION_CUTOFF_RULE,
        "decision_joined": decision_joined,
        "latest_joined": latest_joined,
        "decision_counts": decision_counts,
        "latest_counts": latest_counts,
    }


@router.get("/accuracy/summary")
def accuracy_summary(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    metrics = compute_metrics(ctx["decision_joined"])
    insights = generate_insights(ctx["decision_joined"], ctx["latest_joined"], ctx["decision_counts"])
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "join_counts": ctx["decision_counts"],
            "metrics": metrics,
            "rolling_24h": rolling_24h(ctx["decision_joined"]),
            "insights": insights,
        }
    )


@router.get("/accuracy/by-day")
def accuracy_by_day(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "join_counts": ctx["decision_counts"],
            "records": breakdown_by_day(ctx["decision_joined"]),
        }
    )


@router.get("/accuracy/by-hour")
def accuracy_by_hour(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    parts = breakdown_by_hour(ctx["decision_joined"])
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "join_counts": ctx["decision_counts"],
            **parts,
        }
    )


@router.get("/accuracy/by-horizon")
def accuracy_by_horizon(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "mode": "all_vintages_before_target",
            "join_counts": ctx["latest_counts"],
            "records": breakdown_by_horizon(ctx["latest_joined"]),
        }
    )


@router.get("/accuracy/by-wind-level")
def accuracy_by_wind_level(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "join_counts": ctx["decision_counts"],
            "bucket_rule": "Tertiles of actual wind MW in the selected window (low/medium/high).",
            "records": breakdown_by_wind_level(ctx["decision_joined"]),
        }
    )


@router.get("/accuracy/error-distribution")
def accuracy_error_distribution(
    store: StoreDep,
    settings: SettingsDep,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    cutoff_time: CutoffQuery = None,
) -> dict:
    ctx = _windowed(store, settings, start_date, end_date, cutoff_time)
    return json_safe(
        {
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "cutoff_time": ctx["cutoff_time"],
            "decision_cutoff_rule": ctx["decision_cutoff_rule"],
            "join_counts": ctx["decision_counts"],
            "distribution": error_histogram(ctx["decision_joined"]),
        }
    )
