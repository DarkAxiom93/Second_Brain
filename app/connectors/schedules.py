"""Revision-aware connector refresh schedule lifecycle."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.automations.schedule import ScheduleDefinition, next_point
from app.models.connector import ConnectorAccount
from app.models.connector_schedule import ConnectorRefreshSchedule
from app.repositories import connector_schedules as repository
from app.schemas.connector_schedule import (
    ConnectorScheduleCreate,
    ConnectorScheduleDefinition,
    ConnectorScheduleUpdate,
)


class ScheduleNotFoundError(Exception):
    pass


class ScheduleConflictError(Exception):
    pass


class ScheduleRevisionConflictError(Exception):
    pass


def definition(
    value: ConnectorScheduleDefinition | ConnectorRefreshSchedule,
) -> ScheduleDefinition:
    if isinstance(value, ConnectorScheduleDefinition):
        return ScheduleDefinition(
            kind=value.kind,
            timezone_name=value.timezone_name,
            local_time=value.local_time,
            one_time_local_date=value.one_time_local_date,
            weekdays=tuple(value.weekdays),
            interval_count=1,
        )
    return ScheduleDefinition(
        kind=value.schedule_kind,
        timezone_name=value.timezone_name,
        local_time=value.local_time,
        one_time_local_date=value.one_time_local_date,
        weekdays=tuple(value.weekdays),
        interval_count=1,
    )


def _apply(row: ConnectorRefreshSchedule, value: ConnectorScheduleDefinition) -> None:
    definition(value)  # structural adapter; timezone is validated by next_point below
    row.schedule_kind = value.kind
    row.timezone_name = value.timezone_name
    row.local_time = value.local_time
    row.one_time_local_date = value.one_time_local_date
    row.weekdays = sorted(value.weekdays)
    row.interval_count = 1


def create(
    session: Session, account_id: uuid.UUID, request: ConnectorScheduleCreate
) -> ConnectorRefreshSchedule:
    account = session.get(ConnectorAccount, account_id)
    if account is None:
        raise ScheduleNotFoundError
    if repository.get_account_schedule(session, account_id) is not None:
        raise ScheduleConflictError
    next_point(definition(request.schedule), after_utc=datetime.now(UTC))
    row = ConnectorRefreshSchedule(
        account_id=account.id,
        provider="github",
        schedule_kind=request.schedule.kind,
        timezone_name=request.schedule.timezone_name,
        local_time=request.schedule.local_time,
        one_time_local_date=request.schedule.one_time_local_date,
        weekdays=sorted(request.schedule.weekdays),
        missed_run_policy=request.missed_run_policy,
    )
    session.add(row)
    session.flush()
    return row


def update(
    session: Session,
    schedule_id: uuid.UUID,
    request: ConnectorScheduleUpdate,
    *,
    now: datetime | None = None,
) -> ConnectorRefreshSchedule:
    row = repository.lock_schedule(session, schedule_id)
    if row is None:
        raise ScheduleNotFoundError
    if row.revision != request.expected_revision:
        raise ScheduleRevisionConflictError
    if row.lifecycle == "cancelled":
        raise ScheduleConflictError
    point = next_point(definition(request.schedule), after_utc=now or datetime.now(UTC))
    _apply(row, request.schedule)
    row.missed_run_policy = request.missed_run_policy
    row.revision += 1
    row.schedule_revision += 1
    row.next_occurrence_at = (
        point.utc_instant if row.lifecycle == "enabled" and point else None
    )
    session.flush()
    return row


def transition(
    session: Session,
    schedule_id: uuid.UUID,
    expected: int,
    action: str,
    *,
    now: datetime | None = None,
) -> ConnectorRefreshSchedule:
    row = repository.lock_schedule(session, schedule_id)
    if row is None:
        raise ScheduleNotFoundError
    if row.revision != expected:
        raise ScheduleRevisionConflictError
    allowed = {
        ("draft", "enable"): "enabled",
        ("enabled", "pause"): "paused",
        ("paused", "resume"): "enabled",
    }
    target: str | None
    if action == "cancel" and row.lifecycle in {"draft", "enabled", "paused"}:
        target = "cancelled"
    else:
        target = allowed.get((row.lifecycle, action))
    if target is None:
        raise ScheduleConflictError
    operation_time = now or datetime.now(UTC)
    row.lifecycle = target
    row.revision += 1
    if target == "enabled":
        point = next_point(definition(row), after_utc=operation_time)
        if point is None:
            raise ScheduleConflictError
        row.next_occurrence_at = point.utc_instant
    else:
        row.next_occurrence_at = None
    if target == "cancelled":
        row.cancelled_at = operation_time
    session.flush()
    return row
