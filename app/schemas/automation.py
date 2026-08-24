"""Closed request and safe response schemas for Automation lifecycle APIs."""

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
AgentKind = Literal["daily_brief", "project_watch"]
ExecutionMode = Literal["create_only", "automatic_read_only"]
MissedRunPolicy = Literal["skip", "run_once"]
ScheduleKind = Literal["one_time", "daily", "weekly"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AutomationSchedule(ClosedModel):
    kind: ScheduleKind
    timezone_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    local_time: time
    one_time_local_date: date | None = None
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(
        default_factory=list, max_length=7
    )
    interval_count: Annotated[int, Field(ge=1, le=365)] = 1

    @field_validator("local_time")
    @classmethod
    def minute_precision(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("local_time must not include a timezone")
        if value.second or value.microsecond:
            raise ValueError("seconds-level schedules are not supported")
        return value

    @model_validator(mode="after")
    def closed_shape(self) -> "AutomationSchedule":
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must be unique")
        if self.kind == "one_time":
            if self.one_time_local_date is None or self.weekdays:
                raise ValueError("one_time requires a date and no weekdays")
        elif self.kind == "daily":
            if self.one_time_local_date is not None or self.weekdays:
                raise ValueError("daily does not accept a date or weekdays")
        elif self.one_time_local_date is not None or not self.weekdays:
            raise ValueError("weekly requires weekdays and no one-time date")
        return self


class AutomationCreate(ClosedModel):
    label: Label
    agent_kind: AgentKind
    agent_version: Literal["1"] = "1"
    project_id: uuid.UUID | None = None
    execution_mode: ExecutionMode = "create_only"
    schedule: AutomationSchedule
    missed_run_policy: MissedRunPolicy = "skip"
    retry_limit: Annotated[int, Field(ge=0, le=3)] = 3
    capacity_limit: Annotated[int, Field(ge=1, le=32)] = 1

    @model_validator(mode="after")
    def one_time_missed_default(self) -> "AutomationCreate":
        if (
            "missed_run_policy" not in self.model_fields_set
            and self.schedule.kind == "one_time"
        ):
            self.missed_run_policy = "run_once"
        return self


class AutomationUpdate(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]
    label: Label | None = None
    project_id: uuid.UUID | None = None
    execution_mode: ExecutionMode | None = None
    schedule: AutomationSchedule | None = None
    missed_run_policy: MissedRunPolicy | None = None
    retry_limit: Annotated[int, Field(ge=0, le=3)] | None = None
    capacity_limit: Annotated[int, Field(ge=1, le=32)] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AutomationUpdate":
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("at least one update field is required")
        if "label" in self.model_fields_set and self.label is None:
            raise ValueError("label cannot be null")
        return self


class AutomationRevisionRequest(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]


class SchedulePreviewRequest(ClosedModel):
    schedule: AutomationSchedule
    after_utc: datetime
    count: Annotated[int, Field(ge=1, le=10)] = 5

    @field_validator("after_utc")
    @classmethod
    def aware_instant(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("after_utc must be timezone-aware")
        return value


class SchedulePointRead(ClosedModel):
    local_date: date
    local_time: time
    timezone_name: str
    utc_offset_minutes: int
    utc_instant: datetime


class AutomationRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    label: str
    automation_kind: Literal["scheduled_agent"]
    agent_kind: AgentKind
    agent_version: Literal["1"]
    project_id: uuid.UUID | None
    lifecycle: Literal["draft", "enabled", "paused", "cancelled"]
    revision: int
    execution_mode: ExecutionMode
    schedule_kind: ScheduleKind
    timezone_name: str
    local_time: time
    one_time_local_date: date | None
    weekdays: list[int]
    interval_count: int
    nonexistent_time_policy: Literal["first_valid_after_gap"]
    ambiguous_time_policy: Literal["earlier_fold"]
    missed_run_policy: MissedRunPolicy
    retry_limit: int
    capacity_limit: int
    schedule_revision: int
    next_occurrence_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None

    @field_validator("next_occurrence_at", "created_at", "updated_at", "cancelled_at")
    @classmethod
    def aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must be timezone-aware")
        return value
