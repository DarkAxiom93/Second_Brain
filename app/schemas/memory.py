"""Memory request and response schemas."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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
