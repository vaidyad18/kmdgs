"""Accuracy metrics, breakdowns, and data-backed plain-language insights."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

LONDON = ZoneInfo("Europe/London")

HORIZON_BINS = [0, 6, 12, 24, 36, 48, np.inf]
HORIZON_LABELS = ["0-6", "6-12", "12-24", "24-36", "36-48", "48+"]
WIND_LABELS = ["low", "medium", "high"]


def _finite(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def add_errors(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach error columns. Percentage error is null when actual_mw == 0."""
    out = frame.copy()
    out["error_mw"] = out["forecast_mw"] - out["actual_mw"]
    out["abs_error_mw"] = out["error_mw"].abs()
    actual = _finite(out["actual_mw"])
    out["pct_error"] = np.where(actual == 0, np.nan, out["error_mw"] / actual * 100.0)
    return out


def compute_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    """Hand-checkable metrics on rows that already contain forecast_mw and actual_mw.

    MAPE is the mean of |error|/actual for actual != 0. NMAE is MAE / mean(actual),
    which remains defined when some actuals are zero. Sample std uses ddof=1 and is
    null for n < 2. R^2 is null when actuals have zero variance.
    """
    if frame is None or frame.empty:
        return _empty_metrics(0)
    work = frame.dropna(subset=["forecast_mw", "actual_mw"]).copy()
    n = int(len(work))
    if n == 0:
        return _empty_metrics(0)
    work = add_errors(work)
    error = _finite(work["error_mw"]).to_numpy(dtype=float)
    actual = _finite(work["actual_mw"]).to_numpy(dtype=float)
    forecast = _finite(work["forecast_mw"]).to_numpy(dtype=float)
    abs_err = np.abs(error)
    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean(error**2)))
    bias = float(np.mean(error))
    mean_actual = float(np.mean(actual))
    nmae = float(mae / mean_actual) if mean_actual != 0 else None
    nonzero = actual != 0
    mape = float(np.mean(np.abs(error[nonzero] / actual[nonzero]))) if nonzero.any() else None
    ss_res = float(np.sum((actual - forecast) ** 2))
    ss_tot = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot != 0 else None
    corr = None
    if n >= 2 and np.std(actual, ddof=1) > 0 and np.std(forecast, ddof=1) > 0:
        corr = float(np.corrcoef(actual, forecast)[0, 1])
    std_error = float(np.std(error, ddof=1)) if n >= 2 else None
    signed_q = np.quantile(error, [0.05, 0.25, 0.50, 0.75, 0.95])
    abs_q = np.quantile(abs_err, [0.50, 0.90, 0.95, 0.99])
    return {
        "n": n,
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "mape": mape,
        "nmae": nmae,
        "median_abs_error": float(abs_q[0]),
        "p90_abs_error": float(abs_q[1]),
        "p95_abs_error": float(abs_q[2]),
        "p99_abs_error": float(abs_q[3]),
        "std_error": std_error,
        "r2": r2,
        "correlation": corr,
        "error_quantiles": {
            "p5": float(signed_q[0]),
            "p25": float(signed_q[1]),
            "p50": float(signed_q[2]),
            "p75": float(signed_q[3]),
            "p95": float(signed_q[4]),
        },
        "mape_definition": (
            "MAPE is mean(|forecast-actual|/actual) over rows with actual != 0. "
            "NMAE is MAE / mean(actual) over all joined rows."
        ),
    }


def _empty_metrics(n: int) -> dict[str, Any]:
    return {
        "n": n,
        "mae": None,
        "rmse": None,
        "bias": None,
        "mape": None,
        "nmae": None,
        "median_abs_error": None,
        "p90_abs_error": None,
        "p95_abs_error": None,
        "p99_abs_error": None,
        "std_error": None,
        "r2": None,
        "correlation": None,
        "error_quantiles": {"p5": None, "p25": None, "p50": None, "p75": None, "p95": None},
        "mape_definition": (
            "MAPE is mean(|forecast-actual|/actual) over rows with actual != 0. "
            "NMAE is MAE / mean(actual) over all joined rows."
        ),
    }


def join_forecasts_actuals(
    forecasts: pd.DataFrame, actuals: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Inner-join on startTime. Counts never silently drop rows without reporting."""
    left = forecasts.copy()
    right = actuals.rename(columns={"generation": "actual_mw"}) if not actuals.empty else actuals
    if left.empty or right.empty:
        counts = {
            "forecast_rows": int(len(left)),
            "actual_rows": int(len(right) if right is not None else 0),
            "joined_rows": 0,
            "forecasts_missing_actual": int(len(left)),
            "actuals_missing_forecast": int(len(right) if right is not None else 0),
        }
        return pd.DataFrame(columns=["startTime", "forecast_mw", "actual_mw"]), counts
    outer = left.merge(right[["startTime", "actual_mw"]], on="startTime", how="outer", indicator=True)
    counts = {
        "forecast_rows": int(len(left)),
        "actual_rows": int(len(right)),
        "joined_rows": int((outer["_merge"] == "both").sum()),
        "forecasts_missing_actual": int((outer["_merge"] == "left_only").sum()),
        "actuals_missing_forecast": int((outer["_merge"] == "right_only").sum()),
    }
    joined = outer.loc[outer["_merge"] == "both"].drop(columns="_merge")
    return add_errors(joined), counts


def breakdown_by_day(joined: pd.DataFrame) -> list[dict[str, Any]]:
    if joined.empty:
        return []
    work = joined.copy()
    work["delivery_date"] = work["startTime"].dt.tz_convert(LONDON).dt.date.astype(str)
    rows = []
    for key, group in work.groupby("delivery_date", sort=True):
        metrics = compute_metrics(group)
        metrics["delivery_date"] = key
        rows.append(metrics)
    return rows


def breakdown_by_hour(joined: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if joined.empty:
        return {"by_hour": [], "by_half_hour": []}
    work = joined.copy()
    local = work["startTime"].dt.tz_convert(LONDON)
    work["hour"] = local.dt.hour
    work["minute"] = local.dt.minute
    by_hour = []
    for key, group in work.groupby("hour", sort=True):
        metrics = compute_metrics(group)
        metrics["hour"] = int(key)
        by_hour.append(metrics)
    by_half = []
    for (hour, minute), group in work.groupby(["hour", "minute"], sort=True):
        metrics = compute_metrics(group)
        metrics["hour"] = int(hour)
        metrics["minute"] = int(minute)
        by_half.append(metrics)
    return {"by_hour": by_hour, "by_half_hour": by_half}


def breakdown_by_horizon(joined: pd.DataFrame) -> list[dict[str, Any]]:
    if joined.empty or "horizon_hours" not in joined.columns:
        return []
    work = joined.copy()
    work["horizon_bucket"] = pd.cut(
        work["horizon_hours"],
        bins=HORIZON_BINS,
        labels=HORIZON_LABELS,
        right=False,
        include_lowest=True,
    )
    rows = []
    for key, group in work.groupby("horizon_bucket", observed=False, sort=True):
        metrics = compute_metrics(group)
        metrics["horizon_bucket"] = str(key)
        rows.append(metrics)
    return rows


def breakdown_by_wind_level(joined: pd.DataFrame) -> list[dict[str, Any]]:
    if joined.empty:
        return []
    work = joined.copy()
    actual = _finite(work["actual_mw"])
    try:
        work["wind_level"] = pd.qcut(actual, q=3, labels=WIND_LABELS, duplicates="drop")
    except ValueError:
        work["wind_level"] = "medium"
    rows = []
    for key, group in work.groupby("wind_level", observed=False, sort=False):
        metrics = compute_metrics(group)
        metrics["wind_level"] = str(key)
        q = actual.loc[group.index]
        metrics["actual_mw_min"] = float(q.min())
        metrics["actual_mw_max"] = float(q.max())
        rows.append(metrics)
    return rows


def rolling_24h(joined: pd.DataFrame) -> list[dict[str, Any]]:
    if joined.empty:
        return []
    work = joined.sort_values("startTime").set_index("startTime")
    window = work["error_mw"].rolling("24h")
    abs_window = work["abs_error_mw"].rolling("24h")
    out = pd.DataFrame(
        {
            "startTime": work.index,
            "n": window.count().astype(int),
            "bias": window.mean(),
            "mae": abs_window.mean(),
        }
    )
    return out.reset_index(drop=True).to_dict(orient="records")


def error_histogram(joined: pd.DataFrame, bins: int = 20) -> dict[str, Any]:
    if joined.empty:
        return {"bins": [], "counts": [], "bin_edges_mw": []}
    error = _finite(joined["error_mw"]).dropna().to_numpy(dtype=float)
    counts, edges = np.histogram(error, bins=bins)
    slots = []
    for index, count in enumerate(counts.tolist()):
        slots.append(
            {
                "bin_start_mw": float(edges[index]),
                "bin_end_mw": float(edges[index + 1]),
                "count": int(count),
            }
        )
    return {"bins": slots, "counts": [int(x) for x in counts], "bin_edges_mw": [float(x) for x in edges]}


def generate_insights(
    decision_joined: pd.DataFrame,
    horizon_joined: pd.DataFrame,
    counts: dict[str, int],
) -> list[str]:
    """Plain-language findings. Only states quantities computed from the frames."""
    findings: list[str] = []
    findings.append(
        f"Joined {counts.get('joined_rows', 0)} native startTime rows "
        f"(forecasts missing actual: {counts.get('forecasts_missing_actual', 0)}; "
        f"actuals missing forecast: {counts.get('actuals_missing_forecast', 0)}). "
        "WINDFOR is hourly so half-hour actuals at :30 have no exact forecast match."
    )
    if decision_joined.empty:
        findings.append("No overlapping decision-time forecast and actual rows were available.")
        return findings
    overall = compute_metrics(decision_joined)
    bias = overall["bias"]
    if bias is not None:
        direction = (
            "over-forecast"
            if bias > 0
            else "under-forecast"
            if bias < 0
            else "neither over- nor under-forecast"
        )
        findings.append(
            f"Across {overall['n']} decision-time pairs, mean error (forecast minus actual) "
            f"is {bias:.1f} MW, so forecasts {direction} on average. MAE is {overall['mae']:.1f} MW."
        )
    quantiles = overall["error_quantiles"]
    if quantiles.get("p95") is not None:
        findings.append(
            f"The 95th percentile of signed error is {quantiles['p95']:.1f} MW "
            f"(5th percentile {quantiles['p5']:.1f} MW). A purchase buffer sized to P95 "
            "would cover historically observed over-forecasts at that confidence in this sample."
        )
    by_day = breakdown_by_day(decision_joined)
    scored = [row for row in by_day if row.get("mae") is not None]
    if scored:
        worst = max(scored, key=lambda row: row["mae"])
        best = min(scored, key=lambda row: row["mae"])
        findings.append(
            f"Highest daily MAE is {worst['mae']:.1f} MW on {worst['delivery_date']}; "
            f"lowest is {best['mae']:.1f} MW on {best['delivery_date']}."
        )
    if not horizon_joined.empty:
        by_h = [
            row for row in breakdown_by_horizon(horizon_joined) if row.get("mae") is not None and row["n"] > 0
        ]
        if len(by_h) >= 2:
            first, last = by_h[0], by_h[-1]
            grew = last["mae"] > first["mae"]
            findings.append(
                f"Scoring every vintage by horizon, MAE is {first['mae']:.1f} MW in bucket "
                f"{first['horizon_bucket']} (n={first['n']}) and {last['mae']:.1f} MW in bucket "
                f"{last['horizon_bucket']} (n={last['n']}); "
                + (
                    "error is larger at the longer horizon in this sample."
                    if grew
                    else "error is not larger at the longest populated horizon in this sample."
                )
            )
    return findings
