"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from app.state import init_state
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import DECISION_CUTOFF_RULE, get_settings
from app.data_store import DataStore
from app.elexon_client import ElexonClient
from app.jsonutil import json_safe
from app.models import ErrorBody, ErrorResponse
from app.routers import accuracy, data, health, refresh

logger = logging.getLogger("windbackend")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(json_safe(content))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_state(app)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="GB day-ahead wind forecast backend",
        description=(
            "National GB wind actuals (FUELHH) and WINDFOR vintages for January 2026 "
            "purchase decisions. " + DECISION_CUTOFF_RULE
        ),
        version="1.0.0",
        lifespan=lifespan,
        default_response_class=SafeJSONResponse,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    origins = settings.allowed_origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router, prefix="/api", tags=["meta"])
    application.include_router(data.router, prefix="/api", tags=["data"])
    application.include_router(accuracy.router, prefix="/api", tags=["accuracy"])
    application.include_router(refresh.router, prefix="/api", tags=["ops"])

    @application.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code="validation_error", message="Invalid request", details={"errors": exc.errors()}
            )
        )
        return SafeJSONResponse(status_code=400, content=payload.model_dump())

    @application.exception_handler(HTTPException)
    async def http_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            return SafeJSONResponse(status_code=exc.status_code, content=detail)
        payload = ErrorResponse(error=ErrorBody(code="http_error", message=str(detail), details={}))
        return SafeJSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @application.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            raise exc
        logger.exception("unhandled_error", extra={"error": str(exc)})
        payload = ErrorResponse(
            error=ErrorBody(code="internal_error", message="Internal server error", details={})
        )
        return SafeJSONResponse(status_code=500, content=payload.model_dump())

    # Serve the built React app (single-container deployment) when it exists.
    static_dir = settings.static_dir
    if static_dir.is_dir() and (static_dir / "index.html").exists():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="web")

    return application


app = create_app()
