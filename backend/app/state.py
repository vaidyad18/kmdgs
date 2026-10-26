from __future__ import annotations

import logging
import threading

from fastapi import FastAPI

from app.config import get_settings
from app.data_store import DataStore
from app.elexon_client import ElexonClient

logger = logging.getLogger("windbackend")
_lock = threading.Lock()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def init_state(application: FastAPI) -> DataStore:
    """Create the DataStore once per process and attach it to the app."""
    store = getattr(application.state, "store", None)
    if store is not None:
        return store
    with _lock:
        store = getattr(application.state, "store", None)
        if store is not None:
            return store
        settings = get_settings()
        configure_logging(settings.log_level)
        store = DataStore(settings, ElexonClient(settings.elexon_base_url))
        store.load()
        application.state.settings = settings
        application.state.store = store
        logger.info("startup_complete", extra={"source": store.source})
        return store