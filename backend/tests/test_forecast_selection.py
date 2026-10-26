"""Unit tests for day-ahead decision-time forecast selection."""

from __future__ import annotations

from datetime import UTC

import pandas as pd

from app.forecast_selection import decision_cutoff, select_decision_forecasts, select_latest_before_target


def _frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["startTime", "publishTime", "generation"])


def test_picks_max_publish_time_at_or_before_cutoff() -> None:
    data = _frame(
        [
            ("2026-01-02T12:00:00Z", "2026-01-01T07:00:00Z", 100.0),
            ("2026-01-02T12:00:00Z", "2026-01-01T09:00:00Z", 110.0),
            ("2026-01-02T12:00:00Z", "2026-01-01T08:30:00Z", 105.0),
        ]
    )
    chosen = select_decision_forecasts(data, "09:00")
    assert len(chosen) == 1
    assert chosen.iloc[0]["forecast_mw"] == 110.0
    assert chosen.iloc[0]["publishTime"] == pd.Timestamp("2026-01-01T09:00:00Z")


def test_excludes_forecasts_published_after_cutoff() -> None:
    data = _frame(
        [
            ("2026-01-02T12:00:00Z", "2026-01-01T08:00:00Z", 100.0),
            ("2026-01-02T12:00:00Z", "2026-01-01T09:01:00Z", 999.0),
            ("2026-01-02T12:00:00Z", "2026-01-01T15:00:00Z", 888.0),
        ]
    )
    chosen = select_decision_forecasts(data, "09:00")
    assert len(chosen) == 1
    assert chosen.iloc[0]["forecast_mw"] == 100.0


def test_target_with_no_eligible_forecast_is_omitted() -> None:
    data = _frame(
        [
            ("2026-01-02T12:00:00Z", "2026-01-01T10:00:00Z", 50.0),
            ("2026-01-03T12:00:00Z", "2026-01-02T08:00:00Z", 60.0),
        ]
    )
    chosen = select_decision_forecasts(data, "09:00")
    assert list(chosen["startTime"]) == [pd.Timestamp("2026-01-03T12:00:00Z")]
    assert chosen.iloc[0]["forecast_mw"] == 60.0


def test_duplicate_rows_are_collapsed() -> None:
    data = _frame(
        [
            ("2026-01-02T12:00:00Z", "2026-01-01T08:00:00Z", 10.0),
            ("2026-01-02T12:00:00Z", "2026-01-01T08:00:00Z", 11.0),
        ]
    )
    chosen = select_decision_forecasts(data, "09:00")
    assert len(chosen) == 1
    assert chosen.iloc[0]["forecast_mw"] == 11.0


def test_january_first_uses_december_cutoff() -> None:
    from datetime import date, datetime

    cutoff = decision_cutoff(date(2026, 1, 1), "09:00")
    assert cutoff == datetime(2025, 12, 31, 9, 0, tzinfo=UTC)
    data = _frame(
        [
            ("2026-01-01T00:00:00Z", "2025-12-31T08:59:00Z", 70.0),
            ("2026-01-01T00:00:00Z", "2025-12-31T09:00:00Z", 80.0),
            ("2026-01-01T00:00:00Z", "2025-12-31T09:01:00Z", 90.0),
        ]
    )
    chosen = select_decision_forecasts(data, "09:00")
    assert len(chosen) == 1
    assert chosen.iloc[0]["forecast_mw"] == 80.0
    assert chosen.iloc[0]["publishTime"] == pd.Timestamp("2025-12-31T09:00:00Z")


def test_latest_before_target_allows_intraday_updates() -> None:
    data = _frame(
        [
            ("2026-01-01T12:00:00Z", "2025-12-31T08:00:00Z", 10.0),
            ("2026-01-01T12:00:00Z", "2026-01-01T11:00:00Z", 20.0),
            ("2026-01-01T12:00:00Z", "2026-01-01T13:00:00Z", 30.0),
        ]
    )
    latest = select_latest_before_target(data)
    decision = select_decision_forecasts(data, "09:00")
    assert latest.iloc[0]["forecast_mw"] == 20.0
    assert decision.iloc[0]["forecast_mw"] == 10.0


def test_all_vintages_before_target_keeps_every_horizon():
    from app.forecast_selection import select_all_vintages_before_target

    data = _frame(
        [
            ("2026-01-02T12:00:00Z", "2026-01-01T12:00:00Z", 100.0),
            ("2026-01-02T12:00:00Z", "2026-01-02T06:00:00Z", 110.0),
            ("2026-01-02T12:00:00Z", "2026-01-02T13:00:00Z", 999.0),  # after target: excluded
        ]
    )
    out = select_all_vintages_before_target(data)
    assert sorted(out["horizon_hours"].tolist()) == [6.0, 24.0]
