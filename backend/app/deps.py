"""Shared FastAPI dependencies and request validation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated
from app.state import init_state
from fastapi import Depends, HTTPException, Query, Request

from app.config import CUTOFF_PATTERN, Settings, get_settings
from app.data_store import DataStore
from app.models import ErrorBody, ErrorResponse

CUTOFF_RE = CUTOFF_PATTERN


def error_payload(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return HTTPException(status_code=status_code, detail=body.model_dump())


def get_store(request: Request) -> DataStore:
    store = getattr(request.app.state, "store", None)
    return store if store is not None else init_state(request.app)


def current_settings() -> Settings:
    return get_settings()


def parse_cutoff(cutoff_time: str | None, settings: Settings) -> str:
    value = cutoff_time or settings.default_cutoff_time
    if not CUTOFF_RE.fullmatch(value):
        raise error_payload(400, "invalid_cutoff", "cutoff_time must be HH:MM in UTC", {"cutoff_time": value})
    return value


def parse_iso_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise error_payload(400, "invalid_datetime", f"{field} must be ISO-8601", {"value": value}) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date_param(value: str | None, field: str, default: date) -> date:
    if value is None:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise error_payload(400, "invalid_date", f"{field} must be YYYY-MM-DD", {"value": value}) from exc


def require_in_window(value: date, settings: Settings, field: str) -> date:
    if value < settings.data_start or value >= settings.data_end_exclusive:
        raise error_payload(
            400,
            "date_out_of_range",
            f"{field} must fall in the configured delivery window",
            {
                "value": value.isoformat(),
                "allowed_start": settings.data_start.isoformat(),
                "allowed_end_exclusive": settings.data_end_exclusive.isoformat(),
            },
        )
    return value


def validate_range(start: date, end: date) -> None:
    if start > end:
        raise error_payload(
            400,
            "invalid_range",
            "start_date must be on or before end_date",
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )


StoreDep = Annotated[DataStore, Depends(get_store)]
SettingsDep = Annotated[Settings, Depends(current_settings)]
CutoffQuery = Annotated[str | None, Query(description="Gate-closure time HH:MM UTC")]
