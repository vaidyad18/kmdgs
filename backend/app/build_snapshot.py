"""Fetch January 2026 Elexon data and write the committed snapshot.

Usage (from backend/): python -m app.build_snapshot
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.data_store import DataStore
from app.elexon_client import ElexonClient


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    store = DataStore(settings, ElexonClient(settings.elexon_base_url))
    result = store.refresh()
    store.write_snapshot()
    logging.info("snapshot_written", extra=result)


if __name__ == "__main__":
    main()
