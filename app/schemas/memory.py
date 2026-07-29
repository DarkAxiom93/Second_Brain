"""Memory request and response schemas."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

MemoryType = Literal[
    "working",
    "episodic",
    "semantic",
    "decision",
    "procedural",
    "preference",
    "temporary",
]
MemoryStatus = Literal["active", "superseded", "invalid", "archived"]


class MemoryFilters(BaseModel):
    """Validated query parameters for listing Memories."""

    project_id: uuid.UUID | None = None
    memory_type: MemoryType | None = None
    status: MemoryStatus | None = None
    importance_min: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    importance_max: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    confidence_min: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    confidence_max: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    event_time_from: datetime | None = None
    event_time_to: datetime | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0)] = 0

    @field_validator(
        "event_time_from",
        "event_time_to",
        "created_at_from",
        "created_at_to",
    )
    @classmethod
    def require_filter_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject date filters without a usable timezone offset."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_ordered_ranges(self) -> "MemoryFilters":
        """Reject reversed numeric and timestamp ranges."""

        score_ranges = (
            (self.importance_min, self.importance_max, "importance"),
            (self.confidence_min, self.confidence_max, "confidence"),
        )
        for lower, upper, name in score_ranges:
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"{name} lower bound must not exceed upper bound")
        timestamp_ranges = (
            (self.event_time_from, self.event_time_to, "event_time"),
            (self.created_at_from, self.created_at_to, "created_at"),
        )
        for date_lower, date_upper, name in timestamp_ranges:
            if (
                date_lower is not None
                and date_upper is not None
                and date_lower > date_upper
            ):
                raise ValueError(f"{name} lower bound must not exceed upper bound")
        return self


class MemoryCreate(BaseModel):
    """Validated input for creating a memory."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None = None
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] = None
    title: Annotated[str | None, StringConstraints(max_length=255)] = None
    summary: str | None = None
    memory_type: MemoryType = "semantic"
    importance: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    status: MemoryStatus = "active"
    event_time: datetime | None = None
    expires_at: datetime | None = None
    supersedes_id: uuid.UUID | None = None

    @field_validator("title", "summary", mode="before")
    @classmethod
    def trim_optional_text(cls, value: Any) -> Any:
        """Trim optional text and normalize whitespace-only values to None."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("event_time", "expires_at")
    @classmethod
    def require_optional_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject supplied datetimes without a usable timezone offset."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryRead(BaseModel):
    """Public representation of a persisted memory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    content: str
    source: str | None
    title: str | None
    summary: str | None
    memory_type: MemoryType
    importance: float
    confidence: float
    status: MemoryStatus
    event_time: datetime | None
    expires_at: datetime | None
    supersedes_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", "event_time", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject timestamps without a usable timezone offset."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value
