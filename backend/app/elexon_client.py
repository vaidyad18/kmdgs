"""HTTP client for verified Elexon BMRS stream endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class TransientElexonError(Exception):
    """Retryable HTTP failure (timeout, 429, 5xx)."""


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, (TransientElexonError, httpx.TimeoutException, httpx.TransportError))


class ElexonClient:
    """Fetches FUELHH and WINDFOR stream payloads as bare JSON lists."""

    def __init__(self, base_url: str, timeout: float = 45.0, retries: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _get(self, client: httpx.Client, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        logger.info("elexon_request", extra={"path": path, "params": params})
        try:
            response = client.get(url, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("elexon_transport_error", extra={"path": path, "error": str(exc)})
            raise TransientElexonError(str(exc)) from exc
        if response.status_code in {429} or response.status_code >= 500:
            logger.warning(
                "elexon_retryable_status",
                extra={"path": path, "status": response.status_code},
            )
            raise TransientElexonError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            logger.error(
                "elexon_client_error",
                extra={"path": path, "status": response.status_code, "body": response.text[:500]},
            )
            response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON array from {path}")
        if not payload:
            logger.info("elexon_empty_response", extra={"path": path, "params": params})
        return payload

    def fetch_actuals(self, start: date, end_exclusive: date) -> list[dict[str, Any]]:
        """WIND actuals by settlement date, chunked weekly (inclusive API dates)."""
        rows: list[dict[str, Any]] = []
        cursor = start
        with httpx.Client(timeout=self.timeout, headers={"Accept": "application/json"}) as client:
            while cursor < end_exclusive:
                chunk_end = min(cursor + timedelta(days=6), end_exclusive - timedelta(days=1))
                rows.extend(
                    self._get(
                        client,
                        "/datasets/FUELHH/stream",
                        {
                            "settlementDateFrom": cursor.isoformat(),
                            "settlementDateTo": chunk_end.isoformat(),
                            "fuelType": "WIND",
                        },
                    )
                )
                cursor = chunk_end + timedelta(days=1)
        return rows

    def fetch_forecasts(self, start: datetime, end_exclusive: datetime) -> list[dict[str, Any]]:
        """WINDFOR vintages by publish-time, chunked into one UTC day per request."""
        rows: list[dict[str, Any]] = []
        cursor = start.astimezone(UTC)
        stop = end_exclusive.astimezone(UTC)
        with httpx.Client(timeout=self.timeout, headers={"Accept": "application/json"}) as client:
            while cursor < stop:
                boundary = min(cursor + timedelta(days=1), stop)
                rows.extend(
                    self._get(
                        client,
                        "/datasets/WINDFOR/stream",
                        {
                            "publishDateTimeFrom": cursor.isoformat(timespec="seconds").replace(
                                "+00:00", "Z"
                            ),
                            "publishDateTimeTo": boundary.isoformat(timespec="seconds").replace(
                                "+00:00", "Z"
                            ),
                        },
                    )
                )
                cursor = boundary
        return rows
