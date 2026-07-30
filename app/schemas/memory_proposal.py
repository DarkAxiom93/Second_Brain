"""Memory-proposal generation API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.memory import MemoryType

ReviewStatus = Literal["pending", "approved", "rejected"]
ReviewStatusFilter = Literal["pending", "approved", "rejected", "all"]


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


class MemoryProposalFilters(BaseModel):
    review_status: ReviewStatusFilter = "pending"
    run_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    memory_type: MemoryType | None = None
    importance_min: float | None = Field(default=None, ge=0, le=1)
    importance_max: float | None = Field(default=None, ge=0, le=1)
    confidence_min: float | None = Field(default=None, ge=0, le=1)
    confidence_max: float | None = Field(default=None, ge=0, le=1)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "MemoryProposalFilters":
        if (
            self.importance_min is not None
            and self.importance_max is not None
            and self.importance_min > self.importance_max
        ):
            raise ValueError("importance_min must not exceed importance_max")
        if (
            self.confidence_min is not None
            and self.confidence_max is not None
            and self.confidence_min > self.confidence_max
        ):
            raise ValueError("confidence_min must not exceed confidence_max")
        return self


class ApproveMemoryProposal(BaseModel):
    review_note: str | None = Field(default=None, max_length=2000)

    @field_validator("review_note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return None if value is None or not value.strip() else value.strip()


class RejectMemoryProposal(BaseModel):
    review_note: str = Field(max_length=2000)

    @field_validator("review_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        if not (normalized := value.strip()):
            raise ValueError("review_note must not be blank")
        return normalized


class MemoryProposalListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    source_id: uuid.UUID
    document_id: uuid.UUID
    source_chunk_id: uuid.UUID | None
    project_id: uuid.UUID | None
    proposal_index: int
    title: str | None
    summary: str | None
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    source_locator: str | None
    review_status: ReviewStatus
    review_note: str | None
    reviewed_at: datetime | None
    memory_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    source_type: str
    source_name: str
    original_filename: str | None
    run_provider: str
    run_model: str
    run_prompt_version: str


class MemoryProposalDetail(MemoryProposalListItem):
    source_chunk_hash: str
    evidence_text: str
    evidence_char_start: int
    evidence_char_end: int
    proposal_hash: str
    run_status: Literal["pending", "completed", "failed"]
    source_chunk_available: bool


class MemoryProposalReviewResult(MemoryProposalDetail):
    transition_status: Literal["updated", "unchanged"]
