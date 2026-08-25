"""Bounded trigger-only Automation materialization and fenced Run linking."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.automations import faults
from app.automations.catalog import get_schedulable_agent
from app.automations.schedule import ScheduleDefinition, SchedulePoint, next_point
from app.models.automation import Automation, AutomationOccurrence
from app.repositories import automations as repository
from app.repositories.projects import get_project
from app.schemas.agent_run import AgentRunCreate

MAX_BATCH_SIZE = 16
MAX_ACTIVE_OCCURRENCES = 32
MIN_LEASE = timedelta(seconds=10)
MAX_LEASE = timedelta(minutes=5)
_CLAIM_CAPACITY_LOCK_KEY = 0x53424F4343  # Stable namespace: SBOCC.


class SchedulerValidationError(Exception):
    """Persisted scheduler input fails the closed Checkpoint 78 boundary."""


class ClaimFenceError(Exception):
    """The caller no longer owns the exact live occurrence lease."""


class ExecutionModeUnsupportedError(Exception):
    """Checkpoint 78 cannot progress automatic execution mode."""


@dataclass(frozen=True, slots=True)
class OccurrenceClaim:
    occurrence_id: uuid.UUID
    automation_id: uuid.UUID
    owner_token: uuid.UUID
    lease_generation: int


@dataclass(frozen=True, slots=True)
class TickResult:
    materialized_ids: tuple[uuid.UUID, ...]
    claimed_ids: tuple[uuid.UUID, ...]
    linked_run_ids: tuple[uuid.UUID, ...]
    capacity_deferred_ids: tuple[uuid.UUID, ...]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchedulerValidationError
    return value.astimezone(UTC)


def _batch_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise SchedulerValidationError
    return limit


def _lease_duration(value: timedelta) -> timedelta:
    if value < MIN_LEASE or value > MAX_LEASE:
        raise SchedulerValidationError
    return value


def _definition(automation: Automation) -> ScheduleDefinition:
    return ScheduleDefinition(
        kind=automation.schedule_kind,
        timezone_name=automation.timezone_name,
        local_time=automation.local_time,
        one_time_local_date=automation.one_time_local_date,
        weekdays=tuple(automation.weekdays),
        interval_count=automation.interval_count,
    )


def _scheduled_point(automation: Automation, scheduled_at: datetime) -> SchedulePoint:
    from zoneinfo import ZoneInfo

    local = scheduled_at.astimezone(ZoneInfo(automation.timezone_name))
    offset = local.utcoffset()
    if offset is None:
        raise SchedulerValidationError
    return SchedulePoint(
        local_date=local.date(),
        local_time=local.time().replace(tzinfo=None),
        timezone_name=automation.timezone_name,
        utc_offset_minutes=int(offset.total_seconds() // 60),
        utc_instant=scheduled_at.astimezone(UTC),
    )


def _occurrence_key(automation: Automation, scheduled_at: datetime) -> str:
    instant = scheduled_at.astimezone(UTC).isoformat(timespec="microseconds")
    return (
        f"automation:{automation.id}:schedule:"
        f"{automation.schedule_revision}:at:{instant}"
    )


def materialize_due(
    session: Session, *, now: datetime, limit: int = MAX_BATCH_SIZE
) -> list[AutomationOccurrence]:
    """Insert and advance one slot per locked due Automation in this transaction."""

    operation_time = _aware_utc(now)
    locked = repository.lock_due_automations(
        session, now=operation_time, limit=_batch_limit(limit)
    )
    occurrences: list[AutomationOccurrence] = []
    for automation in locked:
        scheduled_at = automation.next_occurrence_at
        if scheduled_at is None:
            raise SchedulerValidationError
        scheduled_at = _aware_utc(scheduled_at)
        point = _scheduled_point(automation, scheduled_at)
        occurrence = repository.get_occurrence_by_slot(
            session,
            automation_id=automation.id,
            schedule_revision=automation.schedule_revision,
            scheduled_at=scheduled_at,
        )
        if occurrence is None:
            occurrence = AutomationOccurrence(
                automation_id=automation.id,
                schedule_revision=automation.schedule_revision,
                scheduled_at=scheduled_at,
                scheduled_local_date=point.local_date,
                scheduled_local_time=point.local_time,
                scheduled_utc_offset_minutes=point.utc_offset_minutes,
                timezone_name=point.timezone_name,
                occurrence_key=_occurrence_key(automation, scheduled_at),
                state="due",
                revision=0,
                automation_revision=automation.revision,
                automation_kind=automation.automation_kind,
                automation_label=automation.label,
                agent_kind=automation.agent_kind,
                agent_version=automation.agent_version,
                execution_mode=automation.execution_mode,
                project_id=automation.project_id,
                created_at=operation_time,
            )
            try:
                with session.begin_nested():
                    repository.insert_automation_occurrence(session, occurrence)
                    faults.fire(faults.FaultPoint.AFTER_OCCURRENCE_INSERT)
            except IntegrityError:
                occurrence = repository.get_occurrence_by_slot(
                    session,
                    automation_id=automation.id,
                    schedule_revision=automation.schedule_revision,
                    scheduled_at=scheduled_at,
                )
                if occurrence is None:
                    raise
        following = next_point(
            _definition(automation), after_utc=scheduled_at, prior=point
        )
        automation.next_occurrence_at = (
            None if following is None else following.utc_instant
        )
        session.flush()
        faults.fire(faults.FaultPoint.AFTER_NEXT_OCCURRENCE_ADVANCE)
        occurrences.append(occurrence)
    return occurrences


def claim_due(
    session: Session,
    *,
    now: datetime,
    owner_token: uuid.UUID,
    lease_duration: timedelta,
    limit: int = MAX_BATCH_SIZE,
) -> list[OccurrenceClaim]:
    """Claim a deterministic bounded create-only batch in this transaction."""

    operation_time = _aware_utc(now)
    duration = _lease_duration(lease_duration)
    repository.lock_claim_capacity(session, _CLAIM_CAPACITY_LOCK_KEY)
    active = repository.count_occurrences_in_states(session, ("claimed", "run_created"))
    available = max(0, MAX_ACTIVE_OCCURRENCES - active)
    if available == 0:
        return []
    rows = repository.lock_claimable_occurrences(
        session, now=operation_time, limit=min(_batch_limit(limit), available)
    )
    claims: list[OccurrenceClaim] = []
    for occurrence in rows:
        occurrence.state = "claimed"
        occurrence.revision += 1
        occurrence.claimed_at = operation_time
        faults.fire(faults.FaultPoint.AFTER_CLAIM_STATE)
        occurrence.lease_owner_token = owner_token
        occurrence.lease_generation += 1
        faults.fire(faults.FaultPoint.AFTER_LEASE_GENERATION)
        occurrence.lease_expires_at = operation_time + duration
        occurrence.last_renewed_at = operation_time
        session.flush()
        claims.append(
            OccurrenceClaim(
                occurrence_id=occurrence.id,
                automation_id=occurrence.automation_id,
                owner_token=owner_token,
                lease_generation=occurrence.lease_generation,
            )
        )
    return claims


def _validate_claim(
    automation: Automation,
    occurrence: AutomationOccurrence,
    claim: OccurrenceClaim,
    now: datetime,
) -> None:
    if (
        occurrence.automation_id != claim.automation_id
        or occurrence.state != "claimed"
        or occurrence.lease_owner_token != claim.owner_token
        or occurrence.lease_generation != claim.lease_generation
        or occurrence.lease_expires_at is None
        or occurrence.lease_expires_at <= now
    ):
        raise ClaimFenceError
    if (
        automation.lifecycle != "enabled"
        or automation.revision != occurrence.automation_revision
        or automation.schedule_revision != occurrence.schedule_revision
        or automation.project_id != occurrence.project_id
        or automation.automation_kind != occurrence.automation_kind
        or automation.agent_kind != occurrence.agent_kind
        or automation.agent_version != occurrence.agent_version
        or automation.execution_mode != occurrence.execution_mode
    ):
        raise ClaimFenceError


def renew_claim(
    session: Session,
    claim: OccurrenceClaim,
    *,
    now: datetime,
    lease_duration: timedelta,
) -> OccurrenceClaim:
    """Renew only an exact live owner/generation claim."""

    operation_time = _aware_utc(now)
    duration = _lease_duration(lease_duration)
    automation = repository.lock_automation(session, claim.automation_id)
    if automation is None:
        raise ClaimFenceError
    occurrence = repository.lock_occurrence(session, claim.occurrence_id)
    if occurrence is None:
        raise ClaimFenceError
    _validate_claim(automation, occurrence, claim, operation_time)
    occurrence.lease_expires_at = operation_time + duration
    occurrence.last_renewed_at = operation_time
    occurrence.revision += 1
    session.flush()
    return claim


def _run_request(occurrence: AutomationOccurrence) -> AgentRunCreate:
    return AgentRunCreate(
        project_id=occurrence.project_id,
        agent_kind=occurrence.agent_kind,
        agent_version=occurrence.agent_version,
        goal_summary=(
            f"Scheduled {occurrence.agent_kind}: {occurrence.automation_label}"
        ),
    )


def _run_key(occurrence: AutomationOccurrence) -> str:
    return f"automation-occurrence:{occurrence.id}:{occurrence.occurrence_key}"


def create_and_link_run(
    session: Session, claim: OccurrenceClaim, *, now: datetime
) -> tuple[uuid.UUID, bool]:
    """Create/replay one inert Run and link it under the exact live lease."""

    operation_time = _aware_utc(now)
    automation = repository.lock_automation(session, claim.automation_id)
    if automation is None:
        raise ClaimFenceError
    occurrence = repository.lock_occurrence(session, claim.occurrence_id)
    if occurrence is None:
        raise ClaimFenceError
    if occurrence.state == "run_created" and occurrence.agent_run_id is not None:
        request = _run_request(occurrence)
        replay = run_service.resolve_create_replay(
            session,
            idempotency_key_hash=run_service.hash_idempotency_key(_run_key(occurrence)),
            fingerprint=run_service.normalized_request_fingerprint(request),
        )
        if replay is None or replay.run.id != occurrence.agent_run_id:
            raise SchedulerValidationError
        return replay.run.id, False
    _validate_claim(automation, occurrence, claim, operation_time)
    if occurrence.execution_mode != "create_only":
        raise ExecutionModeUnsupportedError
    catalog = get_schedulable_agent(occurrence.agent_kind, occurrence.agent_version)
    if catalog is None or (catalog.project_required and occurrence.project_id is None):
        raise SchedulerValidationError
    if (
        occurrence.project_id is not None
        and get_project(session, occurrence.project_id) is None
    ):
        raise SchedulerValidationError
    request = _run_request(occurrence)
    key_hash = run_service.hash_idempotency_key(_run_key(occurrence))
    result = run_service.create_run(
        session,
        request,
        idempotency_key_hash=key_hash,
        fingerprint=run_service.normalized_request_fingerprint(request),
        now=operation_time,
    )
    faults.fire(faults.FaultPoint.AFTER_RUN_CREATION)
    if occurrence.agent_run_id is not None and occurrence.agent_run_id != result.run.id:
        raise SchedulerValidationError
    occurrence.agent_run_id = result.run.id
    occurrence.state = "run_created"
    occurrence.revision += 1
    occurrence.safe_disposition_code = "run_created"
    session.flush()
    faults.fire(faults.FaultPoint.AFTER_RUN_LINK)
    return result.run.id, result.created
