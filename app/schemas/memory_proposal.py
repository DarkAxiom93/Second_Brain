"""Memory-proposal generation API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MemoryProposalGenerationRequest(BaseModel):
    project_id: uuid.UUID | None = None
    chunk_start: int = Field(default=0, ge=0)
    chunk_limit: int = Field(default=10, ge=1, le=20)
    max_proposals_per_chunk: int = Field(default=3, ge=1, le=5)


class MemoryProposalGenerationRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID | None
    provider: str
    model: str
    prompt_version: str
    input_hash: str
    run_status: Literal["completed"]
    error_code: str | None
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    updated_at: datetime
    proposal_count: int
    generation_status: Literal["created", "retried", "unchanged"]
