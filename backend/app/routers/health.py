"""Health and metadata endpoints."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter

from app.config import DECISION_CUTOFF_RULE
from app.deps import SettingsDep, StoreDep
from app.jsonutil import json_safe

router = APIRouter()


def _delivery_dates(settings) -> list[str]:
    day = settings.data_start
    dates: list[str] = []
    while day < settings.data_end_exclusive:
        dates.append(day.isoformat())
        day += timedelta(days=1)
    return dates


@router.get("/health")
def health(store: StoreDep, settings: SettingsDep) -> dict:
    actuals, forecasts = store.snapshot_frames()
    return json_safe(
        {
            "status": "ok" if not actuals.empty else "degraded",
            "source": store.source,
            "cache_timestamp": store.last_refresh,
            "data_coverage": store.coverage(),
            "actual_records": len(actuals),
            "forecast_records": len(forecasts),
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            "default_cutoff_time": settings.default_cutoff_time,
        }
    )


@router.get("/meta")
def meta(store: StoreDep, settings: SettingsDep) -> dict:
    return json_safe(
        {
            "available_delivery_dates": _delivery_dates(settings),
            "defaults": {
                "cutoff_time": settings.default_cutoff_time,
                "start_date": settings.data_start.isoformat(),
                "end_date": (settings.data_end_exclusive - timedelta(days=1)).isoformat(),
            },
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            "data_coverage": store.coverage(),
            "last_refresh": store.last_refresh,
            "source": store.source,
            "timezone_note": "January 2026 is GMT; UTC equals Europe/London local time.",
        }
    )
