"""Memory request and response schemas."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class MemoryCreate(BaseModel):
    """Validated input for creating a memory."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None = None
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] = None


class MemoryRead(BaseModel):
    """Public representation of a persisted memory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    content: str
    source: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject timestamps without a usable timezone offset."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value
