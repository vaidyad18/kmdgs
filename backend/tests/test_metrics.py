"""Unit tests for accuracy metrics against hand-computed values."""

from __future__ import annotations

import math

import pandas as pd

from app.metrics import compute_metrics, join_forecasts_actuals


def test_metrics_match_hand_computed_values() -> None:
    frame = pd.DataFrame(
        {
            "startTime": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"], utc=True
            ),
            "forecast_mw": [10.0, 20.0, 30.0],
            "actual_mw": [8.0, 25.0, 30.0],
        }
    )
    metrics = compute_metrics(frame)
    errors = [2.0, -5.0, 0.0]
    abs_err = [2.0, 5.0, 0.0]
    assert metrics["n"] == 3
    assert metrics["mae"] == sum(abs_err) / 3
    assert math.isclose(metrics["rmse"], math.sqrt(sum(e * e for e in errors) / 3))
    assert metrics["bias"] == sum(errors) / 3
    assert math.isclose(metrics["mape"], (abs(2 / 8) + abs(-5 / 25) + 0) / 3)
    mean_actual = (8 + 25 + 30) / 3
    assert math.isclose(metrics["nmae"], (sum(abs_err) / 3) / mean_actual)
    assert metrics["median_abs_error"] == 2.0
    assert metrics["error_quantiles"]["p50"] == 0.0


def test_empty_input_returns_null_metrics() -> None:
    metrics = compute_metrics(pd.DataFrame(columns=["forecast_mw", "actual_mw"]))
    assert metrics["n"] == 0
    assert metrics["mae"] is None
    assert metrics["error_quantiles"]["p95"] is None


def test_single_row_std_is_null() -> None:
    frame = pd.DataFrame({"forecast_mw": [12.0], "actual_mw": [10.0]})
    metrics = compute_metrics(frame)
    assert metrics["n"] == 1
    assert metrics["mae"] == 2.0
    assert metrics["rmse"] == 2.0
    assert metrics["bias"] == 2.0
    assert metrics["std_error"] is None
    assert metrics["correlation"] is None


def test_join_reports_missing_counts() -> None:
    forecasts = pd.DataFrame(
        {
            "startTime": pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"], utc=True),
            "forecast_mw": [1.0, 2.0],
        }
    )
    actuals = pd.DataFrame(
        {
            "startTime": pd.to_datetime(["2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"], utc=True),
            "generation": [10.0, 20.0],
        }
    )
    joined, counts = join_forecasts_actuals(forecasts, actuals)
    assert counts["joined_rows"] == 1
    assert counts["forecasts_missing_actual"] == 1
    assert counts["actuals_missing_forecast"] == 1
    assert len(joined) == 1
