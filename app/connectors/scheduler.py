"""Bounded connector-only refresh scheduler; never creates Agent Runs."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.automations.schedule import SchedulePoint, next_point
from app.connectors import schedules
from app.connectors import sync as sync_service
from app.models.connector import ConnectorAccount, ConnectorSyncRun
from app.models.connector_schedule import (
    ConnectorRefreshNotification,
    ConnectorRefreshOccurrence,
    ConnectorRefreshSchedule,
)
from app.repositories import connector_schedules as repository

MAX_LOOKBACK = timedelta(days=7)


@dataclass(frozen=True)
class Claim:
    occurrence_id: uuid.UUID
    schedule_id: uuid.UUID
    owner_token: uuid.UUID
    lease_generation: int


def occurrence_key(
    schedule_id: uuid.UUID, schedule_revision: int, instant: datetime
) -> str:
    canonical = (
        instant.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    return (
        f"connector-refresh-occurrence:v1:{schedule_id}:{schedule_revision}:{canonical}"
    )


def trigger_identity(key: str) -> str:
    return "connector_schedule_" + hashlib.sha256(key.encode("utf-8")).hexdigest()


def _occurrence(
    row: ConnectorRefreshSchedule,
    account: ConnectorAccount,
    point: SchedulePoint,
    state: str,
    now: datetime,
) -> ConnectorRefreshOccurrence:
    return ConnectorRefreshOccurrence(
        schedule_id=row.id,
        account_id=row.account_id,
        provider="github",
        account_revision=account.revision,
        schedule_row_revision=row.revision,
        schedule_revision=row.schedule_revision,
        scheduled_at=point.utc_instant,
        scheduled_local_date=point.local_date,
        scheduled_local_time=point.local_time,
        scheduled_utc_offset_minutes=point.utc_offset_minutes,
        timezone_name=point.timezone_name,
        occurrence_key=occurrence_key(row.id, row.schedule_revision, point.utc_instant),
        state=state,
        safe_disposition_code="missed_skipped" if state == "missed" else None,
        completed_at=now if state == "missed" else None,
    )


def _latest_due(
    row: ConnectorRefreshSchedule, now: datetime
) -> tuple[SchedulePoint, SchedulePoint | None, bool]:
    if row.next_occurrence_at is None:
        raise ValueError("schedule has no next occurrence")
    point = next_point(
        schedules.definition(row),
        after_utc=row.next_occurrence_at - timedelta(microseconds=1),
    )
    if point is None:
        raise ValueError("schedule has no canonical occurrence")
    latest = point
    following = next_point(schedules.definition(row), after_utc=latest.utc_instant)
    while following is not None and following.utc_instant <= now:
        latest = following
        following = next_point(schedules.definition(row), after_utc=latest.utc_instant)
    return latest, following, latest.utc_instant < now - MAX_LOOKBACK


def materialize_due(
    session: Session, *, now: datetime, limit: int = 16
) -> list[ConnectorRefreshOccurrence]:
    result = []
    for row in repository.lock_due_schedules(session, now, limit):
        account = session.get(ConnectorAccount, row.account_id)
        if account is None:
            continue
        point, following, old = _latest_due(row, now)
        missed = row.missed_run_policy == "skip"
        occurrence = _occurrence(
            row, account, point, "missed" if missed else "due", now
        )
        if missed and old:
            occurrence.safe_disposition_code = "missed_lookback_bounded"
        try:
            with session.begin_nested():
                session.add(occurrence)
                session.flush()
        except IntegrityError:
            continue
        row.next_occurrence_at = following.utc_instant if following else None
        if missed:
            notify(
                session,
                occurrence,
                "occurrence_missed",
                "warning",
                occurrence.safe_disposition_code or "missed_skipped",
            )
        result.append(occurrence)
    return result


def claim_due(
    session: Session,
    *,
    now: datetime,
    owner_token: uuid.UUID,
    lease_duration: timedelta,
    limit: int = 16,
) -> list[Claim]:
    claims = []
    for row in repository.lock_claimable(session, now, limit):
        schedule = repository.lock_schedule(session, row.schedule_id)
        account = session.get(ConnectorAccount, row.account_id)
        if (
            schedule is None
            or schedule.lifecycle != "enabled"
            or schedule.schedule_revision != row.schedule_revision
            or schedule.revision != row.schedule_row_revision
            or account is None
            or account.lifecycle != "enabled"
            or account.revision != row.account_revision
        ):
            row.state = "cancelled"
            row.completed_at = now
            row.safe_disposition_code = "authority_fenced"
            notify(session, row, "occurrence_cancelled", "warning", "authority_fenced")
            continue
        row.state = "claimed"
        row.claimed_at = now
        row.lease_owner_token = owner_token
        row.lease_generation += 1
        row.lease_expires_at = now + lease_duration
        row.last_renewed_at = now
        row.attempt_count += 1
        row.revision += 1
        claims.append(Claim(row.id, row.schedule_id, owner_token, row.lease_generation))
    session.flush()
    return claims


def reclaim_expired(
    session: Session,
    *,
    now: datetime,
    owner_token: uuid.UUID,
    lease_duration: timedelta,
    limit: int = 16,
) -> list[Claim]:
    claims = []
    for row in repository.lock_expired(session, now, limit):
        row.lease_owner_token = owner_token
        row.lease_generation += 1
        row.lease_expires_at = now + lease_duration
        row.last_renewed_at = now
        row.revision += 1
        claims.append(Claim(row.id, row.schedule_id, owner_token, row.lease_generation))
    session.flush()
    return claims


def reclaim_linked(
    session: Session,
    *,
    now: datetime,
    owner_token: uuid.UUID,
    lease_duration: timedelta,
    limit: int = 16,
) -> list[Claim]:
    claims = []
    for row in repository.lock_resumable(session, now, limit):
        row.lease_owner_token = owner_token
        row.lease_generation += 1
        row.lease_expires_at = now + lease_duration
        row.last_renewed_at = now
        row.revision += 1
        claims.append(Claim(row.id, row.schedule_id, owner_token, row.lease_generation))
    session.flush()
    return claims


def _validated(
    session: Session, claim: Claim, expected_state: str
) -> tuple[ConnectorRefreshOccurrence, ConnectorRefreshSchedule, ConnectorAccount]:
    row = repository.lock_occurrence(session, claim.occurrence_id)
    schedule = repository.lock_schedule(session, claim.schedule_id)
    if (
        row is None
        or schedule is None
        or row.state != expected_state
        or row.lease_owner_token != claim.owner_token
        or row.lease_generation != claim.lease_generation
    ):
        raise ValueError("stale_connector_schedule_claim")
    account = session.get(ConnectorAccount, row.account_id)
    if (
        schedule.lifecycle != "enabled"
        or schedule.revision != row.schedule_row_revision
        or schedule.schedule_revision != row.schedule_revision
        or account is None
        or account.lifecycle != "enabled"
        or account.revision != row.account_revision
    ):
        raise ValueError("connector_schedule_authority_fenced")
    return row, schedule, account


def create_and_link_sync(session: Session, claim: Claim) -> ConnectorSyncRun:
    row, _, account = _validated(session, claim, "claimed")
    if row.connector_sync_run_id is not None:
        existing = session.get(ConnectorSyncRun, row.connector_sync_run_id)
        if existing is None:
            raise ValueError("connector_schedule_link_invalid")
        return existing
    run = sync_service.claim_with_trigger(
        session,
        account.id,
        row.account_revision,
        trigger_kind="scheduled",
        trigger_identity=trigger_identity(row.occurrence_key),
    )
    row.connector_sync_run_id = run.id
    row.state = "sync_created"
    row.revision += 1
    session.flush()
    return run


def validate_network_fence(session: Session, claim: Claim) -> ConnectorSyncRun:
    row, _, _ = _validated(session, claim, "sync_created")
    if row.connector_sync_run_id is None:
        raise ValueError("connector_schedule_link_missing")
    run = session.get(ConnectorSyncRun, row.connector_sync_run_id)
    if run is None:
        raise ValueError("connector_schedule_link_invalid")
    return run


def finalize(
    session: Session, claim: Claim, *, now: datetime
) -> ConnectorRefreshOccurrence:
    row, _, _ = _validated(session, claim, "sync_created")
    run = session.get(ConnectorSyncRun, row.connector_sync_run_id)
    if run is None or run.status not in {
        "succeeded",
        "incomplete",
        "failed",
        "cancelled",
    }:
        raise ValueError("connector_schedule_sync_not_terminal")
    row.state = run.status if run.status != "cancelled" else "failed"
    row.safe_error_code = run.safe_error_code
    row.safe_disposition_code = "sync_" + run.status
    row.completed_at = now
    row.lease_owner_token = None
    row.lease_expires_at = None
    row.last_renewed_at = None
    row.revision += 1
    event = "occurrence_" + row.state
    severity = (
        "info"
        if row.state == "succeeded"
        else ("warning" if row.state == "incomplete" else "error")
    )
    notify(session, row, event, severity, row.safe_disposition_code)
    session.flush()
    return row


def notify(
    session: Session,
    row: ConnectorRefreshOccurrence,
    event: str,
    severity: str,
    code: str,
) -> None:
    session.add(
        ConnectorRefreshNotification(
            schedule_id=row.schedule_id,
            occurrence_id=row.id,
            event_kind=event,
            severity=severity,
            status_code=code,
            deduplication_key=f"{event}:{row.id}",
        )
    )
