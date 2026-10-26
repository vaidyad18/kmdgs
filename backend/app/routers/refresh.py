"""Refresh endpoint: re-fetch Elexon data and rebuild the on-disk cache."""

from __future__ import annotations

from fastapi import APIRouter, Header

from app.config import DECISION_CUTOFF_RULE
from app.deps import SettingsDep, StoreDep, error_payload
from app.jsonutil import json_safe

router = APIRouter()


@router.post("/refresh")
def refresh(
    store: StoreDep,
    settings: SettingsDep,
    x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token"),
) -> dict:
    expected = settings.refresh_token
    if expected:
        if not x_refresh_token or x_refresh_token != expected:
            raise error_payload(401, "unauthorized", "refresh token missing or invalid")
    try:
        result = store.refresh()
    except Exception as exc:  # noqa: BLE001 - convert upstream failures to a 502
        raise error_payload(
            502,
            "refresh_failed",
            "Elexon refresh failed; cached data was left unchanged",
            {"reason": str(exc)},
        ) from exc
    return json_safe(
        {
            "status": "ok",
            "decision_cutoff_rule": DECISION_CUTOFF_RULE,
            **result,
        }
    )
