"""Caller-transaction-owned primitives for inert Calendar persistence."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.catalog import event_label
from app.calendar.identity import occurrence_identity
from app.credentials import validate_credential_reference
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)


class CalendarOwnershipError(Exception):
    """A child does not belong to the exact captured owner and scope."""


def create_account_revision(
    session: Session, account: CalendarAccountRevision
) -> CalendarAccountRevision:
    validate_credential_reference(account.credential_reference)
    if len(account.account_fingerprint) != 64 or any(
        c not in "0123456789abcdef" for c in account.account_fingerprint
    ):
        raise ValueError("invalid account fingerprint")
    latest = session.scalar(
        select(CalendarAccountRevision)
        .where(CalendarAccountRevision.configuration_id == account.configuration_id)
        .order_by(CalendarAccountRevision.configuration_revision.desc())
        .limit(1)
        .with_for_update(of=CalendarAccountRevision)
    )
    expected = 1 if latest is None else latest.configuration_revision + 1
    if account.configuration_revision != expected:
        raise ValueError("configuration revision must be monotonic")
    session.add(account)
    session.flush()
    session.refresh(account)
    return account


def create_calendar_identity(
    session: Session, calendar: CalendarIdentity
) -> CalendarIdentity:
    if (
        not calendar.provider_calendar_id.strip()
        or len(calendar.provider_calendar_id) > 1024
    ):
        raise ValueError("invalid calendar id")
    account = session.get(CalendarAccountRevision, calendar.account_revision_id)
    if account is None or account.account_fingerprint != calendar.account_fingerprint:
        raise CalendarOwnershipError
    session.add(calendar)
    session.flush()
    session.refresh(calendar)
    return calendar


def create_sync_run(session: Session, run: CalendarSyncRun) -> CalendarSyncRun:
    calendar = session.get(CalendarIdentity, run.calendar_identity_id)
    account = session.get(CalendarAccountRevision, run.account_revision_id)
    if (
        calendar is None
        or account is None
        or calendar.account_revision_id != account.id
        or run.project_id != account.project_id
    ):
        raise CalendarOwnershipError
    if run.window_start.tzinfo is None or run.window_end.tzinfo is None:
        raise ValueError("sync window must use timezone-aware instants")
    session.add(run)
    session.flush()
    session.refresh(run)
    return run


def record_event_revision(
    session: Session, event: CalendarEventRevision, *, seen_at: datetime
) -> tuple[CalendarEventRevision, bool]:
    run = session.get(CalendarSyncRun, event.sync_run_id)
    if run is None or (
        run.account_revision_id,
        run.calendar_identity_id,
        run.project_id,
    ) != (event.account_revision_id, event.calendar_identity_id, event.project_id):
        raise CalendarOwnershipError
    identity = occurrence_identity(
        event_id=event.provider_event_id,
        recurring_series_id=event.recurring_series_id,
        original_start=event.original_start_date or event.original_start_instant,
    )
    if identity.key != event.occurrence_key:
        raise ValueError("occurrence identity mismatch")
    expected_title = event_label(
        event.event_type, private=event.is_private, ordinary_title=event.title
    )
    if expected_title != event.title:
        raise ValueError("event title is not minimized")
    if event.all_day:
        if (
            event.start_date is None
            or event.end_date is None
            or event.start_instant is not None
            or event.end_instant is not None
        ):
            raise ValueError("invalid all-day temporal shape")
    elif (
        event.start_instant is None
        or event.end_instant is None
        or event.start_instant.tzinfo is None
        or event.end_instant.tzinfo is None
    ):
        raise ValueError("timed event requires timezone-aware instants")
    existing = session.scalar(
        select(CalendarEventRevision).where(
            CalendarEventRevision.calendar_identity_id == event.calendar_identity_id,
            CalendarEventRevision.occurrence_key == event.occurrence_key,
            CalendarEventRevision.provider_etag == event.provider_etag,
            CalendarEventRevision.content_hash == event.content_hash,
        )
    )
    if existing is not None:
        return existing, False
    latest = session.scalar(
        select(CalendarEventRevision)
        .where(
            CalendarEventRevision.calendar_identity_id == event.calendar_identity_id,
            CalendarEventRevision.occurrence_key == event.occurrence_key,
        )
        .order_by(CalendarEventRevision.application_revision.desc())
        .limit(1)
        .with_for_update(of=CalendarEventRevision)
    )
    event.application_revision = (
        1 if latest is None else latest.application_revision + 1
    )
    event.first_seen_at = seen_at if latest is None else latest.first_seen_at
    event.last_seen_at = seen_at
    session.add(event)
    session.flush()
    session.refresh(event)
    return event, True
