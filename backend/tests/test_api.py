"""API tests with the Elexon client unused (snapshot-only, no network)."""

from __future__ import annotations

from unittest.mock import patch


def test_health_and_meta(api_client) -> None:
    health = api_client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] in {"ok", "degraded"}
    assert "decision_cutoff_rule" in body
    assert body["actual_records"] == 3
    meta = api_client.get("/api/meta")
    assert meta.status_code == 200
    assert "2026-01-01" in meta.json()["available_delivery_dates"]
    assert meta.json()["defaults"]["cutoff_time"] == "09:00"


def test_actuals_happy_path(api_client) -> None:
    response = api_client.get("/api/actuals", params={"start": "2026-01-01", "end": "2026-01-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 3
    assert body["records"][0]["startTime"].endswith("Z")
    assert 0 <= body["records"][0]["actual_mw"] <= 25000


def test_invalid_dates_are_400(api_client) -> None:
    response = api_client.get("/api/actuals", params={"start": "2025-12-01"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "date_out_of_range"
    response = api_client.get("/api/forecasts/decision", params={"delivery_date": "not-a-date"})
    assert response.status_code == 400
    response = api_client.get(
        "/api/forecasts/decision/range",
        params={"start_date": "2026-01-10", "end_date": "2026-01-01"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_decision_forecast_excludes_post_cutoff_vintage(api_client) -> None:
    response = api_client.get(
        "/api/forecasts/decision",
        params={"delivery_date": "2026-01-01", "cutoff_time": "09:00"},
    )
    assert response.status_code == 200
    body = response.json()
    records = {row["startTime"]: row for row in body["records"]}
    midnight = records["2026-01-01T00:00:00Z"]
    assert midnight["forecast_mw"] == 950.0
    assert midnight["publishTime"] == "2025-12-31T08:00:00Z"
    half = records["2026-01-01T00:30:00Z"]
    assert half["forecast_mw"] is None
    assert half["actual_mw"] == 1100.0


def test_vintages_and_missing_target(api_client) -> None:
    response = api_client.get("/api/forecasts/vintages", params={"target_time": "2026-01-01T00:00:00Z"})
    assert response.status_code == 200
    assert response.json()["n"] == 3
    empty = api_client.get("/api/forecasts/vintages", params={"target_time": "2026-01-01T00:30:00Z"})
    assert empty.status_code == 200
    assert empty.json()["n"] == 0


def test_accuracy_summary(api_client) -> None:
    response = api_client.get("/api/accuracy/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["join_counts"]["joined_rows"] >= 1
    assert "mae" in body["metrics"]
    assert body["insights"]


def test_refresh_requires_token_and_keeps_cache_on_failure(api_client) -> None:
    denied = api_client.post("/api/refresh")
    assert denied.status_code == 401
    with patch("app.elexon_client.ElexonClient.fetch_actuals", side_effect=RuntimeError("down")):
        failed = api_client.post("/api/refresh", headers={"X-Refresh-Token": "secret"})
    assert failed.status_code == 502
    health = api_client.get("/api/health")
    assert health.json()["actual_records"] == 3


def test_refresh_happy_path(api_client) -> None:
    actuals = [
        {
            "dataset": "FUELHH",
            "startTime": "2026-01-01T00:00:00Z",
            "publishTime": "2026-01-01T00:30:00Z",
            "fuelType": "WIND",
            "generation": 1500,
        }
    ]
    forecasts = [
        {
            "dataset": "WINDFOR",
            "startTime": "2026-01-01T00:00:00Z",
            "publishTime": "2025-12-31T08:00:00Z",
            "generation": 1400,
        }
    ]
    with (
        patch("app.elexon_client.ElexonClient.fetch_actuals", return_value=actuals),
        patch("app.elexon_client.ElexonClient.fetch_forecasts", return_value=forecasts),
    ):
        response = api_client.post("/api/refresh", headers={"X-Refresh-Token": "secret"})
    assert response.status_code == 200
    assert response.json()["actual_records"] == 1
    health = api_client.get("/api/health")
    assert health.json()["actual_records"] == 1


def test_invalid_cutoff(api_client) -> None:
    response = api_client.get(
        "/api/forecasts/decision",
        params={"delivery_date": "2026-01-01", "cutoff_time": "25:00"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cutoff"
