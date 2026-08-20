"""Strict public schemas for the manual Agent Run lifecycle."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class AgentRunState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


StableAgentKind = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
    ),
]
StableAgentVersion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9._+-]*[A-Za-z0-9])?$",
    ),
]
ApprovalRequestStatus = Literal[
    "pending", "approved", "rejected", "expired", "superseded"
]


class AgentRunCreate(BaseModel):
    """The only client-controlled fields of a new Run."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None
    agent_kind: StableAgentKind
    agent_version: StableAgentVersion
    goal_summary: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]


class AgentRunCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: Annotated[int, Field(ge=0)]


class AgentRunPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: Annotated[int, Field(ge=0)]


class AgentRunExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: Annotated[int, Field(ge=0)]


class AgentStepRead(BaseModel):
    """Allowlisted public projection of one frozen planning Step."""

    model_config = ConfigDict(from_attributes=True)

    ordinal: int
    purpose: str
    tool_name: str
    tool_version: int
    normalized_input: dict[str, object]
    expected_evidence: list[str]
    success_condition: str
    stop_condition: str


class AgentRunRead(BaseModel):
    """Allowlisted public Run projection."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    agent_kind: str
    agent_version: str
    goal_summary: str
    registry_version: str
    policy_version: str
    state: AgentRunState
    step_budget: int
    tool_call_budget: int
    retry_budget: int
    planning_deadline: datetime
    run_deadline: datetime
    revision: int
    safe_error_code: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_validator(
        "planning_deadline",
        "run_deadline",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value


class AgentRunPlanRead(BaseModel):
    run: AgentRunRead
    goal_summary: str
    steps: list[AgentStepRead]


class AgentStepExecutionRead(BaseModel):
    ordinal: int
    purpose: str
    tool_name: str
    tool_version: int
    status: str
    invocation_status: str | None
    safe_result_summary: str | None
    evidence_references: list[dict[str, object]]
    safe_error_code: str | None


class ResearchCitationRead(BaseModel):
    number: Annotated[int, Field(gt=0)]
    entity_type: Literal["project", "memory", "source", "source_chunk"]
    entity_id: uuid.UUID
    version: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ResearchClaimRead(BaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    citation_numbers: Annotated[list[int], Field(min_length=1, max_length=20)]


class ResearchResultRead(BaseModel):
    status: Literal["answered", "insufficient_evidence"]
    claims: Annotated[list[ResearchClaimRead], Field(max_length=5)]
    citations: Annotated[list[ResearchCitationRead], Field(max_length=20)]
    insufficiency: Annotated[str | None, StringConstraints(max_length=1000)]


class CuratorEvidenceRead(BaseModel):
    entity_type: Literal["project", "memory", "source", "source_chunk"]
    entity_id: uuid.UUID
    version: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CuratorFindingRead(BaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    evidence: Annotated[list[CuratorEvidenceRead], Field(min_length=1, max_length=20)]


class CuratorProposedActionRead(BaseModel):
    approval_id: uuid.UUID
    action_type: Literal["memory.update"]
    target_id: uuid.UUID
    target_version: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CuratorResultRead(BaseModel):
    findings: Annotated[list[CuratorFindingRead], Field(max_length=10)]
    proposed_actions: Annotated[list[CuratorProposedActionRead], Field(max_length=5)]


class AgentRunExecutionRead(BaseModel):
    run: AgentRunRead
    steps: list[AgentStepExecutionRead]
    research_result: ResearchResultRead | None = None
    curator_result: CuratorResultRead | None = None


class ApprovalRequestCreate(BaseModel):
    """Only caller-controlled proposal fields."""

    model_config = ConfigDict(extra="forbid")

    step_ordinal: Annotated[int, Field(ge=0)]
    action_type: Literal["memory.update"]
    target_id: uuid.UUID
    proposed_input: dict[str, object]


class ApprovalReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]


class ApprovalRequestRead(BaseModel):
    """Allowlisted public Approval projection; private identities stay hidden."""

    id: uuid.UUID
    run_id: uuid.UUID
    step_ordinal: int
    action_type: str
    target_type: str
    target_id: uuid.UUID
    target_version: str
    proposed_input: dict[str, object]
    preview: str
    evidence_references: list[dict[str, object]]
    risk_classification: str
    status: ApprovalRequestStatus
    created_at: datetime
    expires_at: datetime
    reviewed_at: datetime | None

    @field_validator("created_at", "expires_at", "reviewed_at")
    @classmethod
    def require_approval_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value
