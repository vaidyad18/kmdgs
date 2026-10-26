"""JSON-safe conversion for API payloads (NaN/inf -> null, UTC Z timestamps)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from math import isinf, isnan
from typing import Any

import numpy as np
import pandas as pd


def iso_z(value: datetime | pd.Timestamp) -> str:
    """Format a timezone-aware timestamp as ISO-8601 UTC with a Z suffix."""
    if isinstance(value, pd.Timestamp):
        ts = value.tz_convert("UTC") if value.tzinfo is not None else value.tz_localize("UTC")
        dt = ts.to_pydatetime()
    else:
        dt = value
    if dt.tzinfo is None:
        raise ValueError("refusing to serialise a naive datetime")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    """Recursively convert values into JSON-serialisable, NaN-free structures."""
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (datetime, pd.Timestamp)):
        return iso_z(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if isnan(number) or isinf(number):
            return None
        return number
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, pd.DataFrame):
        return [json_safe(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return json_safe(value.to_dict())
    if pd.isna(value):
        return None
    return value
