"""Strict, bounded schemas used only by the Agent Tool Registry."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.memory import MemoryStatus, MemoryType


class StrictToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ProjectGetInput(StrictToolModel):
    project_id: uuid.UUID


class MemoryGetInput(StrictToolModel):
    memory_id: uuid.UUID


class SourceGetInput(StrictToolModel):
    source_id: uuid.UUID


class SourceChunkGetInput(StrictToolModel):
    source_chunk_id: uuid.UUID


class ExplainedSearchFilters(StrictToolModel):
    memory_type: MemoryType | None = None
    status: MemoryStatus | None = None
    importance_min: Annotated[float | None, Field(ge=0, le=1)] = None
    importance_max: Annotated[float | None, Field(ge=0, le=1)] = None
    confidence_min: Annotated[float | None, Field(ge=0, le=1)] = None
    confidence_max: Annotated[float | None, Field(ge=0, le=1)] = None
    event_time_from: datetime | None = None
    event_time_to: datetime | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None

    @field_validator(
        "event_time_from", "event_time_to", "created_at_from", "created_at_to"
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_ordered_ranges(self) -> "ExplainedSearchFilters":
        numeric_ranges = (
            (self.importance_min, self.importance_max),
            (self.confidence_min, self.confidence_max),
        )
        datetime_ranges = (
            (self.event_time_from, self.event_time_to),
            (self.created_at_from, self.created_at_to),
        )
        if any(
            low is not None and high is not None and low > high
            for low, high in numeric_ranges
        ) or any(
            low is not None and high is not None and low > high
            for low, high in datetime_ranges
        ):
            raise ValueError("filter lower bound must not exceed upper bound")
        return self


class ExplainedSearchPagination(StrictToolModel):
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0, le=10_000)]


class MemorySearchExplainedInput(StrictToolModel):
    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    mode: Literal["lexical", "semantic", "hybrid"]
    filters: ExplainedSearchFilters
    pagination: ExplainedSearchPagination


class EmptyInput(StrictToolModel):
    pass


SafeText = Annotated[str, StringConstraints(max_length=2_000)]
SafeShortText = Annotated[str, StringConstraints(max_length=500)]


class ProjectGetOutput(StrictToolModel):
    id: uuid.UUID
    name: Annotated[str, StringConstraints(max_length=200)]
    description: SafeText | None


class MemoryGetOutput(StrictToolModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    title: Annotated[str, StringConstraints(max_length=255)] | None
    summary: SafeText | None
    content: SafeText
    memory_type: MemoryType
    status: MemoryStatus


class SourceGetOutput(StrictToolModel):
    id: uuid.UUID
    source_type: Annotated[str, StringConstraints(max_length=50)]
    name: Annotated[str, StringConstraints(max_length=255)]
    reference: SafeShortText | None


class SourceChunkGetOutput(StrictToolModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: Annotated[int, Field(ge=0)]
    content: Annotated[str, StringConstraints(max_length=10_000)]
    char_start: Annotated[int, Field(ge=0)]
    char_end: Annotated[int, Field(ge=0)]
    locator: SafeShortText | None


class ExplainedSearchItem(StrictToolModel):
    rank: Annotated[int, Field(gt=0, le=100)]
    memory_id: uuid.UUID
    title: Annotated[str, StringConstraints(max_length=255)] | None
    summary: SafeText | None
    mode: Literal["lexical", "semantic", "hybrid"]
    matched_by: tuple[Literal["lexical", "semantic"], ...]


class MemorySearchExplainedOutput(StrictToolModel):
    results: Annotated[tuple[ExplainedSearchItem, ...], Field(max_length=100)]


class AggregateFinding(StrictToolModel):
    code: Annotated[
        str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$", max_length=64)
    ]
    count: Annotated[int, Field(ge=0)]


class AggregateOutput(StrictToolModel):
    status: Literal["ok", "warning", "failed"]
    findings: Annotated[tuple[AggregateFinding, ...], Field(max_length=50)]
