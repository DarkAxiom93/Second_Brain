"""Bounded trigger-only Automation materialization and fenced Run linking."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.automations import faults
from app.automations.catalog import (
    IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES,
    get_automatic_agent_definition,
    get_schedulable_agent,
)
from app.automations.schedule import ScheduleDefinition, SchedulePoint, next_point
from app.models.agent_runtime import AgentRun
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.repositories import automations as repository
from app.repositories.projects import get_project
from app.schemas.agent_run import AgentRunCreate

MAX_BATCH_SIZE = 16
MAX_ACTIVE_OCCURRENCES = 32
MIN_LEASE = timedelta(seconds=10)
MAX_LEASE = timedelta(minutes=5)
MAX_LOOKBACK = timedelta(days=7)
MAX_SETUP_ATTEMPTS = 3
MAX_RETRY_DELAY = timedelta(minutes=5)
_CLAIM_CAPACITY_LOCK_KEY = 0x53424F4343  # Stable namespace: SBOCC.


class SchedulerValidationError(Exception):
    """Persisted scheduler input fails the closed Checkpoint 78 boundary."""


class ClaimFenceError(Exception):
    """The caller no longer owns the exact live occurrence lease."""


class ExecutionModeUnsupportedError(Exception):
    """Checkpoint 78 cannot progress automatic execution mode."""


class AmbiguousSchedulerOutcomeError(Exception):
    """Durable state cannot prove whether a scheduler mutation committed."""


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
    reclaimed_ids: tuple[uuid.UUID, ...] = ()
    reconciled_ids: tuple[uuid.UUID, ...] = ()
    missed_ids: tuple[uuid.UUID, ...] = ()
    retry_deferred_ids: tuple[uuid.UUID, ...] = ()
    failed_ids: tuple[uuid.UUID, ...] = ()
    automatically_coordinated_ids: tuple[uuid.UUID, ...] = ()


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


def _notification(
    session: Session,
    occurrence: AutomationOccurrence,
    *,
    event_kind: str,
    severity: str,
    code: str,
    now: datetime,
) -> None:
    if not code:
        raise SchedulerValidationError
    notification = AutomationNotification(
        automation_id=occurrence.automation_id,
        occurrence_id=occurrence.id,
        agent_run_id=occurrence.agent_run_id,
        event_kind=event_kind,
        severity=severity,
        title="Automation needs operator attention",
        body="Open the Automation history to review its safe status and links.",
        created_at=now,
        deduplication_key=f"automation-notice:{occurrence.id}:{event_kind}",
    )
    try:
        with session.begin_nested():
            repository.insert_automation_notification(session, notification)
    except IntegrityError:
        pass


def _new_occurrence(
    automation: Automation,
    point: SchedulePoint,
    *,
    now: datetime,
    state: str,
    disposition: str | None = None,
) -> AutomationOccurrence:
    terminal = state in {"completed", "missed", "failed", "cancelled"}
    return AutomationOccurrence(
        automation_id=automation.id,
        schedule_revision=automation.schedule_revision,
        scheduled_at=point.utc_instant,
        scheduled_local_date=point.local_date,
        scheduled_local_time=point.local_time,
        scheduled_utc_offset_minutes=point.utc_offset_minutes,
        timezone_name=point.timezone_name,
        occurrence_key=_occurrence_key(automation, point.utc_instant),
        state=state,
        revision=0,
        automation_revision=automation.revision,
        automation_kind=automation.automation_kind,
        automation_label=automation.label,
        agent_kind=automation.agent_kind,
        agent_version=automation.agent_version,
        execution_mode=automation.execution_mode,
        project_id=automation.project_id,
        safe_disposition_code=disposition,
        created_at=now,
        completed_at=now if terminal else None,
    )


def _latest_due_and_future(
    automation: Automation, *, now: datetime
) -> tuple[SchedulePoint, SchedulePoint | None, bool]:
    """Return latest canonical due slot, first future slot, and old-window flag."""

    scheduled_at = automation.next_occurrence_at
    if scheduled_at is None:
        raise SchedulerValidationError
    point = _scheduled_point(automation, _aware_utc(scheduled_at))
    latest = point
    older_than_lookback = point.utc_instant < now - MAX_LOOKBACK
    definition = _definition(automation)
    # Recurrences are at least daily. The persistence work remains constant even
    # across long downtime; this loop only calculates canonical calendar slots.
    for _ in range(1_000_000):
        following = next_point(definition, after_utc=latest.utc_instant, prior=latest)
        if following is None or following.utc_instant > now:
            return latest, following, older_than_lookback
        latest = following
    raise SchedulerValidationError


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
        point, following, older_than_lookback = _latest_due_and_future(
            automation, now=operation_time
        )
        missed = automation.missed_run_policy == "skip"
        state = "missed" if missed else "due"
        disposition = None
        if missed:
            disposition = (
                "missed_lookback_bounded" if older_than_lookback else "missed_skipped"
            )
        scheduled_at = point.utc_instant
        occurrence = repository.get_occurrence_by_slot(
            session,
            automation_id=automation.id,
            schedule_revision=automation.schedule_revision,
            scheduled_at=scheduled_at,
        )
        if occurrence is None:
            occurrence = _new_occurrence(
                automation,
                point,
                now=operation_time,
                state=state,
                disposition=disposition,
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
        automation.next_occurrence_at = (
            None if following is None else following.utc_instant
        )
        if missed:
            _notification(
                session,
                occurrence,
                event_kind="occurrence_missed",
                severity="warning",
                code=disposition or "missed_skipped",
                now=operation_time,
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
        session,
        now=operation_time,
        limit=min(_batch_limit(limit), available),
        automatic_identities=IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES,
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


def reclaim_expired(
    session: Session,
    *,
    now: datetime,
    owner_token: uuid.UUID,
    lease_duration: timedelta,
    limit: int = MAX_BATCH_SIZE,
) -> list[OccurrenceClaim]:
    """Reclaim only DB-time-expired unlinked claims and fence their old owner."""

    operation_time = _aware_utc(now)
    duration = _lease_duration(lease_duration)
    rows = repository.lock_expired_claims(
        session, now=operation_time, limit=_batch_limit(limit)
    )
    claims: list[OccurrenceClaim] = []
    for occurrence in rows:
        if occurrence.agent_run_id is not None:
            continue
        occurrence.lease_owner_token = owner_token
        occurrence.lease_generation += 1
        occurrence.lease_expires_at = operation_time + duration
        occurrence.last_renewed_at = operation_time
        occurrence.revision += 1
        session.flush()
        claims.append(
            OccurrenceClaim(
                occurrence.id,
                occurrence.automation_id,
                owner_token,
                occurrence.lease_generation,
            )
        )
    return claims


def reconcile_linked(
    session: Session, *, now: datetime, limit: int = MAX_BATCH_SIZE
) -> list[uuid.UUID]:
    """Project exact durable linked Run state into safe occurrence summaries."""

    operation_time = _aware_utc(now)
    reconciled: list[uuid.UUID] = []
    for occurrence in repository.lock_linked_occurrences(
        session, limit=_batch_limit(limit)
    ):
        run = session.get(AgentRun, occurrence.agent_run_id)
        if run is None:
            occurrence.state = "failed"
            occurrence.safe_error_code = "linked_run_missing"
            occurrence.safe_disposition_code = "operator_review_required"
            occurrence.completed_at = operation_time
            occurrence.revision += 1
            _notification(
                session,
                occurrence,
                event_kind="occurrence_failed",
                severity="error",
                code="linked_run_missing",
                now=operation_time,
            )
        elif run.state in {"completed", "failed", "cancelled", "expired"}:
            occurrence.state = "completed" if run.state == "completed" else "failed"
            occurrence.safe_disposition_code = f"run_{run.state}"
            occurrence.safe_error_code = (
                None if run.state == "completed" else f"run_{run.state}"
            )
            occurrence.completed_at = operation_time
            occurrence.revision += 1
            if run.state != "completed":
                _notification(
                    session,
                    occurrence,
                    event_kind="occurrence_failed",
                    severity="error",
                    code=f"run_{run.state}",
                    now=operation_time,
                )
        elif occurrence.state == "claimed":
            occurrence.state = "run_created"
            occurrence.safe_disposition_code = "run_created"
            occurrence.revision += 1
        session.flush()
        reconciled.append(occurrence.id)
    return reconciled


def retry_delay(occurrence_id: uuid.UUID, attempt: int) -> timedelta:
    """Return capped exponential delay with stable occurrence-derived jitter."""

    base = min(5 * (2 ** max(0, attempt - 1)), int(MAX_RETRY_DELAY.total_seconds()))
    jitter = (occurrence_id.int + attempt) % 5
    return timedelta(seconds=min(base + jitter, int(MAX_RETRY_DELAY.total_seconds())))


def is_retryable_setup_error(exc: BaseException) -> bool:
    """Closed classifier for approved pre-link database failures."""

    if not isinstance(exc, (OperationalError, DBAPIError)):
        return False
    code = getattr(getattr(exc, "orig", None), "sqlstate", None)
    return code in {"40001", "40P01"} or isinstance(exc, OperationalError)


def defer_setup(
    session: Session,
    occurrence_id: uuid.UUID,
    *,
    now: datetime,
    capacity: bool,
) -> bool:
    """Durably defer the same occurrence; return False after exhaustion."""

    operation_time = _aware_utc(now)
    occurrence = repository.lock_occurrence(session, occurrence_id)
    if occurrence is None or occurrence.agent_run_id is not None:
        raise AmbiguousSchedulerOutcomeError
    automation = repository.lock_automation(session, occurrence.automation_id)
    if automation is None or occurrence.state != "claimed":
        raise AmbiguousSchedulerOutcomeError
    if capacity:
        repeatedly_delayed = occurrence.safe_disposition_code == "capacity_deferred"
        occurrence.state = "due"
        occurrence.retry_not_before = operation_time + retry_delay(occurrence.id, 1)
        occurrence.lease_owner_token = None
        occurrence.lease_expires_at = None
        occurrence.last_renewed_at = None
        occurrence.safe_disposition_code = "capacity_deferred"
        occurrence.revision += 1
        if repeatedly_delayed:
            _notification(
                session,
                occurrence,
                event_kind="capacity_delayed",
                severity="warning",
                code="capacity_deferred",
                now=operation_time,
            )
        session.flush()
        return True
    occurrence.attempt_count += 1
    limit = min(automation.retry_limit, MAX_SETUP_ATTEMPTS)
    if occurrence.attempt_count >= limit:
        occurrence.state = "failed"
        occurrence.safe_error_code = "setup_retry_exhausted"
        occurrence.safe_disposition_code = "operator_review_required"
        occurrence.retry_not_before = None
        occurrence.completed_at = operation_time
        occurrence.revision += 1
        _notification(
            session,
            occurrence,
            event_kind="retry_exhausted",
            severity="error",
            code="setup_retry_exhausted",
            now=operation_time,
        )
        session.flush()
        return False
    occurrence.state = "due"
    occurrence.retry_not_before = operation_time + retry_delay(
        occurrence.id, occurrence.attempt_count
    )
    occurrence.lease_owner_token = None
    occurrence.lease_expires_at = None
    occurrence.last_renewed_at = None
    occurrence.safe_disposition_code = "setup_retry_deferred"
    occurrence.revision += 1
    session.flush()
    return True


def fail_closed(
    session: Session, occurrence_id: uuid.UUID, *, now: datetime, code: str
) -> None:
    """Persist one content-free terminal outcome for a proven unlinked occurrence."""

    operation_time = _aware_utc(now)
    occurrence = repository.lock_occurrence(session, occurrence_id)
    if occurrence is None or occurrence.agent_run_id is not None:
        raise AmbiguousSchedulerOutcomeError
    if occurrence.state in {"completed", "missed", "failed", "cancelled"}:
        return
    occurrence.state = "failed"
    occurrence.safe_error_code = code
    occurrence.safe_disposition_code = "operator_review_required"
    occurrence.retry_not_before = None
    occurrence.completed_at = operation_time
    occurrence.revision += 1
    _notification(
        session,
        occurrence,
        event_kind="occurrence_failed",
        severity="error",
        code=code,
        now=operation_time,
    )
    session.flush()


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
    if occurrence.execution_mode == "automatic_read_only":
        definition = get_automatic_agent_definition(
            occurrence.agent_kind, occurrence.agent_version
        )
        if (
            definition is None
            or not definition.code_owned
            or definition.authority != "read"
            or not definition.allowed_tools
        ):
            raise ExecutionModeUnsupportedError
    elif occurrence.execution_mode != "create_only":
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
