"""Source and memory-source request and response schemas."""

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

from app.ingestion.text import chunk_text, normalize_plain_text
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


class SourceTextIngest(BaseModel):
    """Validated normalized plain-text ingestion request."""

    model_config = ConfigDict(extra="forbid")
    text: str
    original_filename: str | None = None
    chunk_size: Annotated[int, Field(ge=1000, le=10000)] = 2000
    chunk_overlap: Annotated[int, Field(ge=0, le=500)] = 200

    @field_validator("text")
    @classmethod
    def normalize_and_validate_text(cls, value: str) -> str:
        normalized = normalize_plain_text(value)
        if not normalized.strip():
            raise ValueError("text must contain a non-whitespace character")
        if len(normalized.encode("utf-8")) > 5_000_000:
            raise ValueError("normalized text exceeds 5000000 UTF-8 bytes")
        return normalized

    @field_validator("original_filename", mode="before")
    @classmethod
    def validate_filename(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        filename = value.strip()
        if not filename:
            return None
        if len(filename) > 255:
            raise ValueError("original_filename must be at most 255 characters")
        if filename in {".", ".."} or any(char in filename for char in "/\\\0"):
            raise ValueError("original_filename must be a filename only")
        return filename

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "SourceTextIngest":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        chunk_text(self.text, self.chunk_size, self.chunk_overlap)
        return self


class SourceDocumentRead(BaseModel):
    """Public ingestion result without document or chunk content."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    media_type: str
    original_filename: str | None
    byte_size: int
    ingestion_status: str
    error_code: str | None
    extracted_at: datetime
    created_at: datetime
    updated_at: datetime
    chunk_count: int
    generation_status: Literal["created", "updated", "unchanged"]

    @field_validator("extracted_at", "created_at", "updated_at")
    @classmethod
    def require_document_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class SourceDocumentDetailRead(BaseModel):
    """Public persisted document metadata without extracted document text."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    media_type: str
    original_filename: str | None
    byte_size: int | None
    ingestion_status: str
    error_code: str | None
    extracted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int

    @field_validator("extracted_at", "created_at", "updated_at")
    @classmethod
    def require_optional_document_timezone(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value


class SourceChunkRead(BaseModel):
    """Public chunk evidence for local document inspection."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    content_hash: str
    locator: str | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_chunk_timezone(cls, value: datetime) -> datetime:
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
