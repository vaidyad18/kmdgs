"""Pydantic v2 schemas for source rows and HTTP error payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def as_utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


class ActualRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    startTime: datetime
    generation: float
    fuelType: str

    @field_validator("startTime", mode="before")
    @classmethod
    def validate_time(cls, value: Any) -> datetime:
        return as_utc(value)

    @field_validator("generation", mode="before")
    @classmethod
    def validate_generation(cls, value: Any) -> float:
        result = float(value)
        if not (-1000 < result < 100000):
            raise ValueError("generation outside plausible bounds")
        return result

    @field_validator("fuelType", mode="before")
    @classmethod
    def validate_fuel(cls, value: Any) -> str:
        text = str(value).upper()
        if text != "WIND":
            raise ValueError("fuelType must be WIND")
        return text


class ForecastRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    startTime: datetime
    publishTime: datetime
    generation: float

    @field_validator("startTime", "publishTime", mode="before")
    @classmethod
    def validate_time(cls, value: Any) -> datetime:
        return as_utc(value)

    @field_validator("generation", mode="before")
    @classmethod
    def validate_generation(cls, value: Any) -> float:
        result = float(value)
        if not (-1000 < result < 100000):
            raise ValueError("generation outside plausible bounds")
        return result


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
