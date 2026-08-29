"""Closed connector refresh scheduling API schemas."""

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

ScheduleKind = Literal["one_time", "daily", "weekly"]
MissedPolicy = Literal["skip", "run_once"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConnectorScheduleDefinition(ClosedModel):
    kind: ScheduleKind
    timezone_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    local_time: time
    one_time_local_date: date | None = None
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(
        default_factory=list, max_length=7
    )
    interval_count: Literal[1] = 1

    @field_validator("local_time")
    @classmethod
    def minute_precision(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("local_time must be a timezone-free minute")
        return value

    @model_validator(mode="after")
    def closed_shape(self) -> "ConnectorScheduleDefinition":
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must be unique")
        if self.kind == "one_time" and (
            self.one_time_local_date is None or self.weekdays
        ):
            raise ValueError("one_time requires a date and no weekdays")
        if self.kind == "daily" and (
            self.one_time_local_date is not None or self.weekdays
        ):
            raise ValueError("daily accepts no date or weekdays")
        if self.kind == "weekly" and (
            self.one_time_local_date is not None or not self.weekdays
        ):
            raise ValueError("weekly requires weekdays and no date")
        return self


class ConnectorScheduleCreate(ClosedModel):
    schedule: ConnectorScheduleDefinition
    missed_run_policy: MissedPolicy = "skip"


class ConnectorScheduleUpdate(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]
    schedule: ConnectorScheduleDefinition
    missed_run_policy: MissedPolicy


class ConnectorScheduleRevisionRequest(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]


class ConnectorScheduleRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    account_id: uuid.UUID
    provider: Literal["github"]
    lifecycle: Literal["draft", "enabled", "paused", "cancelled"]
    revision: int
    schedule_revision: int
    schedule_kind: ScheduleKind
    timezone_name: str
    local_time: time
    one_time_local_date: date | None
    weekdays: list[int]
    interval_count: Literal[1]
    nonexistent_time_policy: Literal["first_valid_after_gap"]
    ambiguous_time_policy: Literal["earlier_fold"]
    missed_run_policy: MissedPolicy
    next_occurrence_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None


class ConnectorOccurrenceRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    schedule_id: uuid.UUID
    scheduled_at: datetime
    scheduled_local_date: date
    scheduled_local_time: time
    scheduled_utc_offset_minutes: int
    timezone_name: str
    state: Literal[
        "due",
        "claimed",
        "sync_created",
        "succeeded",
        "incomplete",
        "failed",
        "missed",
        "cancelled",
    ]
    attempt_count: int
    safe_disposition_code: str | None
    safe_error_code: str | None
    connector_sync_run_id: uuid.UUID | None
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None


class ConnectorNotificationRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    schedule_id: uuid.UUID
    occurrence_id: uuid.UUID
    event_kind: Literal[
        "occurrence_missed",
        "occurrence_succeeded",
        "occurrence_incomplete",
        "occurrence_failed",
        "occurrence_cancelled",
    ]
    severity: Literal["info", "warning", "error"]
    status_code: str
    read_at: datetime | None
    created_at: datetime
