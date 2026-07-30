"""Public metadata response for explicit embedding generation."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.repositories.memory_embeddings import GenerationStatus


class MemoryEmbeddingRead(BaseModel):
    """Embedding metadata that intentionally excludes vector values."""

    id: uuid.UUID
    memory_id: uuid.UUID
    provider: str
    model: str
    dimensions: int
    input_hash: str
    embedded_at: datetime
    created_at: datetime
    updated_at: datetime
    generation_status: GenerationStatus


class MemoryEmbeddingMetadata(BaseModel):
    """Public embedding metadata without workflow status or vector values."""

    id: uuid.UUID
    memory_id: uuid.UUID
    provider: str
    model: str
    dimensions: int
    input_hash: str
    embedded_at: datetime
    created_at: datetime
    updated_at: datetime


class MemoryEmbeddingBatchRequest(BaseModel):
    """Explicit bounded selection rules for missing active embeddings."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    project_id: uuid.UUID | None = None
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_scope(self) -> "MemoryEmbeddingBatchRequest":
        if self.scope not in {"project", "unassigned", "all"}:
            raise ValueError("scope must be project, unassigned, or all")
        if self.scope == "project" and self.project_id is None:
            raise ValueError("project scope requires project_id")
        if self.scope != "project" and self.project_id is not None:
            raise ValueError(f"{self.scope} scope forbids project_id")
        return self


class MemoryEmbeddingBatchItem(BaseModel):
    memory_id: uuid.UUID
    generation_status: Literal["created", "unchanged", "skipped"]
    embedding: MemoryEmbeddingMetadata | None = None
    skipped_reason: str | None = None


class MemoryEmbeddingBatchRead(BaseModel):
    batch_status: Literal["completed", "empty"]
    selected_count: int
    created_count: int
    unchanged_count: int
    skipped_count: int
    items: list[MemoryEmbeddingBatchItem]
