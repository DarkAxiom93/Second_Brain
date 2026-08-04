"""Strict public schemas for the manual Agent Run lifecycle."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

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
