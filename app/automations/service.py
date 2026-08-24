"""Revision-aware, caller-transaction-owned Automation lifecycle service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.automations.catalog import get_schedulable_agent
from app.automations.schedule import ScheduleDefinition, next_point, validate_definition
from app.models.automation import Automation
from app.models.project import Project
from app.repositories import automations as repository
from app.schemas.automation import (
    AutomationCreate,
    AutomationSchedule,
    AutomationUpdate,
)


class AutomationNotFoundError(Exception):
    pass


class AutomationRevisionConflictError(Exception):
    pass


class AutomationTransitionConflictError(Exception):
    pass


class AutomationDefinitionError(ValueError):
    pass


class AutomationProjectNotFoundError(Exception):
    pass


def _now(value: datetime | None) -> datetime:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise AutomationDefinitionError("captured instant must be timezone-aware")
    return instant.astimezone(UTC)


def schedule_definition(
    schedule: AutomationSchedule | Automation,
) -> ScheduleDefinition:
    if isinstance(schedule, Automation):
        return ScheduleDefinition(
            kind=schedule.schedule_kind,
            timezone_name=schedule.timezone_name,
            local_time=schedule.local_time,
            one_time_local_date=schedule.one_time_local_date,
            weekdays=tuple(schedule.weekdays),
            interval_count=schedule.interval_count,
        )
    return ScheduleDefinition(
        kind=schedule.kind,
        timezone_name=schedule.timezone_name,
        local_time=schedule.local_time,
        one_time_local_date=schedule.one_time_local_date,
        weekdays=tuple(schedule.weekdays),
        interval_count=schedule.interval_count,
    )


def _validate_scope_and_catalog(
    session: Session,
    *,
    agent_kind: str,
    agent_version: str,
    project_id: uuid.UUID | None,
) -> None:
    catalog_entry = get_schedulable_agent(agent_kind, agent_version)
    if catalog_entry is None:
        raise AutomationDefinitionError("automation agent is not schedulable")
    if catalog_entry.project_required and project_id is None:
        raise AutomationDefinitionError("project_watch requires an exact Project scope")
    if project_id is not None and session.get(Project, project_id) is None:
        raise AutomationProjectNotFoundError


def _lock_expected(
    session: Session, automation_id: uuid.UUID, expected_revision: int
) -> Automation:
    automation = repository.lock_automation(session, automation_id)
    if automation is None:
        raise AutomationNotFoundError
    if automation.revision != expected_revision:
        raise AutomationRevisionConflictError
    return automation


def _apply_schedule(automation: Automation, schedule: AutomationSchedule) -> None:
    automation.schedule_kind = schedule.kind
    automation.timezone_name = schedule.timezone_name
    automation.local_time = schedule.local_time
    automation.one_time_local_date = schedule.one_time_local_date
    automation.weekdays = sorted(schedule.weekdays)
    automation.interval_count = schedule.interval_count


def create_automation(session: Session, request: AutomationCreate) -> Automation:
    validate_definition(schedule_definition(request.schedule))
    _validate_scope_and_catalog(
        session,
        agent_kind=request.agent_kind,
        agent_version=request.agent_version,
        project_id=request.project_id,
    )
    automation = Automation(
        label=request.label,
        agent_kind=request.agent_kind,
        agent_version=request.agent_version,
        project_id=request.project_id,
        execution_mode=request.execution_mode,
        schedule_kind=request.schedule.kind,
        timezone_name=request.schedule.timezone_name,
        local_time=request.schedule.local_time,
        one_time_local_date=request.schedule.one_time_local_date,
        weekdays=sorted(request.schedule.weekdays),
        interval_count=request.schedule.interval_count,
        missed_run_policy=request.missed_run_policy,
        retry_limit=request.retry_limit,
        capacity_limit=request.capacity_limit,
    )
    return repository.create_automation(session, automation)


def update_automation(
    session: Session,
    automation_id: uuid.UUID,
    request: AutomationUpdate,
    *,
    captured_at: datetime | None = None,
) -> Automation:
    automation = _lock_expected(session, automation_id, request.expected_revision)
    if automation.lifecycle == "cancelled":
        raise AutomationTransitionConflictError
    fields = request.model_fields_set - {"expected_revision"}
    definition_affecting = fields - {"label"}
    schedule_affecting = "schedule" in fields
    if definition_affecting and automation.lifecycle not in {"draft", "paused"}:
        raise AutomationTransitionConflictError

    project_id = request.project_id if "project_id" in fields else automation.project_id
    _validate_scope_and_catalog(
        session,
        agent_kind=automation.agent_kind,
        agent_version=automation.agent_version,
        project_id=project_id,
    )
    if request.schedule is not None:
        validate_definition(schedule_definition(request.schedule))
        _apply_schedule(automation, request.schedule)
    if "label" in fields:
        assert request.label is not None
        automation.label = request.label
    if "project_id" in fields:
        automation.project_id = request.project_id
    for field in (
        "execution_mode",
        "missed_run_policy",
        "retry_limit",
        "capacity_limit",
    ):
        if field in fields:
            setattr(automation, field, getattr(request, field))

    automation.revision += 1
    if schedule_affecting:
        automation.schedule_revision += 1
        if automation.lifecycle == "paused":
            point = next_point(
                schedule_definition(automation), after_utc=_now(captured_at)
            )
            if point is None:
                raise AutomationDefinitionError("schedule has no future occurrence")
            automation.next_occurrence_at = point.utc_instant
        else:
            automation.next_occurrence_at = None
    session.flush()
    session.refresh(automation)
    return automation


def enable_automation(
    session: Session,
    automation_id: uuid.UUID,
    expected_revision: int,
    *,
    captured_at: datetime | None = None,
) -> Automation:
    automation = _lock_expected(session, automation_id, expected_revision)
    if automation.lifecycle != "draft":
        raise AutomationTransitionConflictError
    _validate_scope_and_catalog(
        session,
        agent_kind=automation.agent_kind,
        agent_version=automation.agent_version,
        project_id=automation.project_id,
    )
    point = next_point(schedule_definition(automation), after_utc=_now(captured_at))
    if point is None:
        raise AutomationDefinitionError("schedule has no future occurrence")
    automation.lifecycle = "enabled"
    automation.next_occurrence_at = point.utc_instant
    automation.revision += 1
    session.flush()
    session.refresh(automation)
    return automation


def pause_automation(
    session: Session, automation_id: uuid.UUID, expected_revision: int
) -> Automation:
    automation = _lock_expected(session, automation_id, expected_revision)
    if automation.lifecycle != "enabled":
        raise AutomationTransitionConflictError
    automation.lifecycle = "paused"
    automation.revision += 1
    session.flush()
    session.refresh(automation)
    return automation


def resume_automation(
    session: Session,
    automation_id: uuid.UUID,
    expected_revision: int,
    *,
    captured_at: datetime | None = None,
) -> Automation:
    automation = _lock_expected(session, automation_id, expected_revision)
    if automation.lifecycle != "paused":
        raise AutomationTransitionConflictError
    _validate_scope_and_catalog(
        session,
        agent_kind=automation.agent_kind,
        agent_version=automation.agent_version,
        project_id=automation.project_id,
    )
    point = next_point(schedule_definition(automation), after_utc=_now(captured_at))
    if point is None:
        raise AutomationDefinitionError("schedule has no future occurrence")
    automation.lifecycle = "enabled"
    automation.next_occurrence_at = point.utc_instant
    automation.revision += 1
    session.flush()
    session.refresh(automation)
    return automation


def cancel_automation(
    session: Session,
    automation_id: uuid.UUID,
    expected_revision: int,
    *,
    captured_at: datetime | None = None,
) -> Automation:
    automation = _lock_expected(session, automation_id, expected_revision)
    if automation.lifecycle == "cancelled":
        raise AutomationTransitionConflictError
    automation.lifecycle = "cancelled"
    automation.cancelled_at = _now(captured_at)
    automation.next_occurrence_at = None
    automation.revision += 1
    session.flush()
    session.refresh(automation)
    return automation
