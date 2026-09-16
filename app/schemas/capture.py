"""Closed request and safe response schemas for the Capture Inbox."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CaptureState = Literal["pending", "processed", "discarded"]


def _default_states() -> list[CaptureState]:
    return ["pending"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaptureScope(ClosedModel):
    project_id: uuid.UUID | None = None
    unassigned: bool | None = None

    @model_validator(mode="after")
    def exact_scope(self) -> "CaptureScope":
        if self.model_fields_set == {"project_id"} and self.project_id is not None:
            return self
        if self.model_fields_set == {"unassigned"} and self.unassigned is True:
            return self
        raise ValueError("exactly one non-null Capture scope is required")


class CaptureCreateRequest(ClosedModel):
    content: str
    project_id: uuid.UUID | None = None
    unassigned: bool | None = None

    @model_validator(mode="after")
    def creation_scope(self) -> "CaptureCreateRequest":
        scope_fields = self.model_fields_set & {"project_id", "unassigned"}
        if not scope_fields:
            return self
        if scope_fields == {"project_id"} and self.project_id is not None:
            return self
        if scope_fields == {"unassigned"} and self.unassigned is True:
            return self
        raise ValueError("creation scope is invalid")


class CaptureQueryRequest(ClosedModel):
    scope: CaptureScope
    states: list[CaptureState] = Field(
        default_factory=_default_states, min_length=1, max_length=3
    )
    query: str | None = None
    page_size: Annotated[int, Field(ge=1, le=50)] = 25
    cursor: Annotated[str | None, Field(max_length=2048)] = None

    @field_validator("states")
    @classmethod
    def unique_states(cls, value: list[CaptureState]) -> list[CaptureState]:
        if len(set(value)) != len(value):
            raise ValueError("states must be unique")
        return value

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
            raise ValueError("query contains a disallowed control character")
        normalized = value.strip()
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters after trimming")
        try:
            size = len(normalized.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("query contains a non-scalar Unicode value") from exc
        if size > 800:
            raise ValueError("query exceeds 800 UTF-8 bytes")
        return normalized


class CaptureDetailRequest(ClosedModel):
    scope: CaptureScope


class CaptureRevisionRequest(CaptureDetailRequest):
    revision: Annotated[int, Field(gt=0)]


class CaptureEditRequest(CaptureRevisionRequest):
    content: str


class CaptureReassignRequest(CaptureRevisionRequest):
    target_scope: CaptureScope


class CaptureRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID | None
    content: str
    state: CaptureState
    revision: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    resulting_source_id: uuid.UUID | None


class CapturePage(ClosedModel):
    items: list[CaptureRead]
    next_cursor: str | None
