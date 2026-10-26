"""Optional live integration test. Skipped unless RUN_LIVE_TESTS=1."""

from __future__ import annotations

import os

import pytest

from app.elexon_client import ElexonClient

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="live Elexon test disabled by default")
def test_live_fuelhh_one_day() -> None:
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1")
    from datetime import date

    rows = client.fetch_actuals(date(2026, 1, 1), date(2026, 1, 2))
    assert isinstance(rows, list)
    assert rows
    assert rows[0]["fuelType"] == "WIND"
    assert "startTime" in rows[0]
