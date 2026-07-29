"""Source and memory-source request and response schemas."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.schemas.memory import MemoryStatus, MemoryType


class SourceCreate(BaseModel):
    """Validated input for creating a normalized source."""

    model_config = ConfigDict(extra="forbid")
    source_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    reference: str | None = None
    checksum: Annotated[str | None, StringConstraints(max_length=64)] = None

    @field_validator("reference", "checksum", mode="before")
    @classmethod
    def trim_optional_string(cls, value: Any) -> Any:
        """Trim strings and normalize whitespace-only values to None."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SourceRead(BaseModel):
    """Public representation of a persisted source."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_type: str
    name: str
    reference: str | None
    checksum: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject timestamps without a usable timezone offset."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemorySourceLinkCreate(BaseModel):
    """Validated input for linking a source to a memory."""

    model_config = ConfigDict(extra="forbid")
    source_id: uuid.UUID
    source_location: Annotated[str | None, StringConstraints(max_length=500)] = None

    @field_validator("source_location", mode="before")
    @classmethod
    def trim_source_location(cls, value: Any) -> Any:
        """Trim locations and normalize whitespace-only values to None."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class MemorySourceRead(BaseModel):
    """Public representation of a persisted memory-source link."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    memory_id: uuid.UUID
    source_id: uuid.UUID
    source_location: str | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject timestamps without a usable timezone offset."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class LinkedSourceRead(BaseModel):
    """A Source returned in the context of its link to a Memory."""

    model_config = ConfigDict(from_attributes=True)
    link_id: uuid.UUID
    memory_id: uuid.UUID
    source_id: uuid.UUID
    source_location: str | None
    linked_at: datetime
    source_type: str
    name: str
    reference: str | None
    checksum: str | None
    source_created_at: datetime
    source_updated_at: datetime


class LinkedMemoryRead(BaseModel):
    """A Memory returned in the context of its link to a Source."""

    model_config = ConfigDict(from_attributes=True)
    link_id: uuid.UUID
    source_id: uuid.UUID
    memory_id: uuid.UUID
    source_location: str | None
    linked_at: datetime
    project_id: uuid.UUID | None
    content: str
    legacy_source: str | None
    title: str | None
    summary: str | None
    memory_type: MemoryType
    importance: float
    confidence: float
    status: MemoryStatus
    event_time: datetime | None
    expires_at: datetime | None
    supersedes_id: uuid.UUID | None
    memory_created_at: datetime
    memory_updated_at: datetime
