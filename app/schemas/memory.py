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
MemoryStatus = Literal["active", "superseded", "invalid", "archived", "expired"]
MemorySearchMode = Literal["semantic", "hybrid"]
ExplainedMemorySearchMode = Literal["lexical", "semantic", "hybrid"]
MemorySearchChannel = Literal["lexical", "semantic"]
MemorySimilarityClassification = Literal["exact_duplicate", "similar"]
MemoryContradictionEvidenceType = Literal["explicit_negation", "opposing_boolean_state"]
MemorySupersessionStatus = Literal["updated", "unchanged"]
MemoryExpirationStatus = Literal["updated", "unchanged"]
MemoryQualityRefinementStatus = Literal["updated", "unchanged"]


class MemoryStructuredFilters(BaseModel):
    """Structured filters shared by lexical and semantic Memory retrieval."""

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
    def require_ordered_ranges(self) -> "MemoryStructuredFilters":
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


class MemoryFilters(MemoryStructuredFilters):
    """Validated query parameters for listing Memories."""

    query: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0)] = 0


class MemorySearchPagination(BaseModel):
    """SQL pagination for semantic Memory search."""

    model_config = ConfigDict(extra="forbid")

    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0)] = 0


class MemorySearchRequest(BaseModel):
    """Validated semantic or hybrid Memory search request."""

    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    mode: MemorySearchMode = "semantic"
    filters: MemoryStructuredFilters = Field(default_factory=MemoryStructuredFilters)
    pagination: MemorySearchPagination = Field(default_factory=MemorySearchPagination)


class ExplainedMemorySearchRequest(BaseModel):
    """Validated request for deterministic explained Memory search."""

    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    mode: ExplainedMemorySearchMode
    filters: MemoryStructuredFilters
    pagination: MemorySearchPagination


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


class MemoryUpdate(BaseModel):
    """Strict partial Memory update input shared by proposal validation."""

    model_config = ConfigDict(extra="forbid")

    content: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=16000),
    ] = None
    source: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] = None
    title: Annotated[str | None, StringConstraints(max_length=255)] = None
    summary: Annotated[str | None, StringConstraints(max_length=4000)] = None
    memory_type: MemoryType | None = None
    importance: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    confidence: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    status: MemoryStatus | None = None
    event_time: datetime | None = None
    expires_at: datetime | None = None
    supersedes_id: uuid.UUID | None = None

    @field_validator("title", "summary", mode="before")
    @classmethod
    def trim_update_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("event_time", "expires_at")
    @classmethod
    def require_update_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_update_field(self) -> "MemoryUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one update field is required")
        required = {"content", "memory_type", "importance", "confidence", "status"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required
        ):
            raise ValueError("non-nullable update field cannot be null")
        return self


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


BoundedSignal = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
NonNegativeScore = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class MemorySearchExplanationRead(BaseModel):
    """Bounded deterministic ranking aids for one search result."""

    model_config = ConfigDict(extra="forbid")

    mode: ExplainedMemorySearchMode
    matched_by: list[MemorySearchChannel]
    lexical_rank: Annotated[int, Field(gt=0)] | None
    semantic_rank: Annotated[int, Field(gt=0)] | None
    lexical_signal: BoundedSignal | None
    semantic_signal: BoundedSignal | None
    lexical_rrf_contribution: NonNegativeScore | None
    semantic_rrf_contribution: NonNegativeScore | None
    fused_rrf_score: NonNegativeScore | None

    @model_validator(mode="after")
    def require_mode_invariants(self) -> "MemorySearchExplanationRead":
        """Reject inconsistent channel ordering, nullability, and score fields."""

        if self.matched_by not in (["lexical"], ["semantic"], ["lexical", "semantic"]):
            raise ValueError("matched_by must contain ordered ranking channels")
        if self.mode == "lexical":
            valid = (
                self.matched_by == ["lexical"]
                and self.lexical_rank is not None
                and self.lexical_signal is not None
                and self.semantic_rank is None
                and self.semantic_signal is None
                and self.lexical_rrf_contribution is None
                and self.semantic_rrf_contribution is None
                and self.fused_rrf_score is None
            )
        elif self.mode == "semantic":
            valid = (
                self.matched_by == ["semantic"]
                and self.semantic_rank is not None
                and self.semantic_signal is not None
                and self.lexical_rank is None
                and self.lexical_signal is None
                and self.lexical_rrf_contribution is None
                and self.semantic_rrf_contribution is None
                and self.fused_rrf_score is None
            )
        else:
            valid = (
                self.fused_rrf_score is not None
                and (self.lexical_rank is not None) == ("lexical" in self.matched_by)
                and (self.semantic_rank is not None) == ("semantic" in self.matched_by)
                and (self.lexical_signal is not None) == (self.lexical_rank is not None)
                and (self.semantic_signal is not None)
                == (self.semantic_rank is not None)
                and (self.lexical_rrf_contribution is not None)
                == (self.lexical_rank is not None)
                and (self.semantic_rrf_contribution is not None)
                == (self.semantic_rank is not None)
            )
        if not valid:
            raise ValueError("ranking explanation is inconsistent with mode")
        return self


class ExplainedMemorySearchResultRead(BaseModel):
    """One globally ranked Memory and its bounded ranking explanation."""

    model_config = ConfigDict(extra="forbid")

    rank: Annotated[int, Field(gt=0)]
    memory: MemoryRead
    explanation: MemorySearchExplanationRead


class MemorySupersedeRequest(BaseModel):
    """Identify the existing active Memory that replaces the path Memory."""

    model_config = ConfigDict(extra="forbid")

    replacement_memory_id: uuid.UUID


class MemorySupersessionRead(BaseModel):
    """Public result of an explicit Memory supersession transition."""

    supersession_status: MemorySupersessionStatus
    superseded_memory: MemoryRead
    replacement_memory: MemoryRead


class MemoryExpirationRead(BaseModel):
    """Public result of an explicit Memory expiration transition."""

    expiration_status: MemoryExpirationStatus
    memory: MemoryRead


class MemoryQualityRefinementRequest(BaseModel):
    """Explicit non-null quality values to apply to one active Memory."""

    model_config = ConfigDict(extra="forbid")

    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    importance: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def require_quality_value(self) -> "MemoryQualityRefinementRequest":
        """Require at least one usable refinement value."""

        if self.confidence is None and self.importance is None:
            raise ValueError("at least one quality value is required")
        return self


class MemoryQualityRefinementRead(BaseModel):
    """Public result of an explicit Memory quality refinement."""

    refinement_status: MemoryQualityRefinementStatus
    memory: MemoryRead


class MemorySimilarityCandidateRead(BaseModel):
    """Public advisory evidence for one duplicate or similar candidate."""

    memory_id: uuid.UUID
    classification: MemorySimilarityClassification
    lexical_similarity: float | None
    semantic_similarity: float | None
    reason: str


class MemorySimilarityRead(BaseModel):
    """Read-only duplicate and similarity result for one target Memory."""

    target_memory_id: uuid.UUID
    candidates: list[MemorySimilarityCandidateRead]


class MemoryContradictionCandidateRead(BaseModel):
    """Public deterministic evidence for a potential contradiction."""

    memory_id: uuid.UUID
    classification: Literal["potential_contradiction"]
    evidence_type: MemoryContradictionEvidenceType
    reason: str
    lexical_similarity: float | None
    semantic_similarity: float | None
    target_state: str
    candidate_state: str


class MemoryContradictionRead(BaseModel):
    """Read-only advisory contradiction result for one target Memory."""

    target_memory_id: uuid.UUID
    candidates: list[MemoryContradictionCandidateRead]
