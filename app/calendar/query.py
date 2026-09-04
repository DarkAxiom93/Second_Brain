"""Scoped local-only Calendar External Context projections."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventObservation,
    CalendarEventRevision,
    CalendarSyncRun,
)
from app.models.project import Project
from app.schemas.calendar import CalendarEventPage, CalendarEventRead, CalendarScope

MAX_PAGE_SIZE = 50
EVIDENCE_VERSION = "calendar-observations-v1"
_CURSOR_DOMAIN = b"second-brain:calendar-events:v1"
_OCCURRENCE_DOMAIN = b"second-brain:calendar-occurrence:v1:"


class CalendarEventNotFoundError(Exception):
    pass


class CalendarEventCursorError(Exception):
    pass


@dataclass(frozen=True)
class CalendarExternalScope:
    project_id: uuid.UUID | None


def parse_scope(value: str) -> CalendarExternalScope:
    if value == "unassigned":
        return CalendarExternalScope(None)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("invalid calendar event scope") from None
    if str(parsed) != value.lower():
        raise ValueError("invalid calendar event scope")
    return CalendarExternalScope(parsed)


def _require_scope(session: Session, scope: CalendarExternalScope) -> None:
    if scope.project_id is not None and session.get(Project, scope.project_id) is None:
        raise CalendarEventNotFoundError


def _eligible_condition() -> ColumnElement[bool]:
    observation_count = (
        select(func.count(CalendarEventObservation.id))
        .where(CalendarEventObservation.sync_run_id == CalendarSyncRun.id)
        .correlate(CalendarSyncRun)
        .scalar_subquery()
    )
    return and_(
        CalendarSyncRun.status == "succeeded",
        CalendarSyncRun.completeness == "complete",
        CalendarSyncRun.observation_evidence_version == EVIDENCE_VERSION,
        observation_count == CalendarSyncRun.items_seen,
    )


def _latest_positive_query(
    scope: CalendarExternalScope,
) -> Select[tuple[CalendarEventRevision]]:
    scope_condition = (
        CalendarAccountRevision.project_id.is_(None)
        if scope.project_id is None
        else CalendarAccountRevision.project_id == scope.project_id
    )
    ranked = (
        select(
            CalendarEventObservation.event_revision_id.label("event_revision_id"),
            CalendarEventObservation.account_revision_id.label("account_revision_id"),
            CalendarEventObservation.calendar_identity_id.label("calendar_identity_id"),
            CalendarEventObservation.occurrence_key.label("occurrence_key"),
            func.row_number()
            .over(
                partition_by=(
                    CalendarEventObservation.account_revision_id,
                    CalendarEventObservation.calendar_identity_id,
                    CalendarEventObservation.occurrence_key,
                ),
                order_by=(
                    CalendarSyncRun.completed_at.desc(),
                    CalendarSyncRun.id.desc(),
                ),
            )
            .label("position"),
        )
        .join(
            CalendarSyncRun, CalendarSyncRun.id == CalendarEventObservation.sync_run_id
        )
        .join(
            CalendarAccountRevision,
            CalendarAccountRevision.id == CalendarEventObservation.account_revision_id,
        )
        .where(_eligible_condition(), scope_condition)
        .subquery()
    )
    return (
        select(CalendarEventRevision)
        .join(ranked, CalendarEventRevision.id == ranked.c.event_revision_id)
        .where(ranked.c.position == 1)
    )


def _covered(event: CalendarEventRevision, run: CalendarSyncRun) -> bool:
    if not event.all_day:
        assert event.start_instant is not None and event.end_instant is not None
        return (
            event.end_instant > run.window_start
            and event.start_instant < run.window_end
        )
    if (
        event.start_date is None
        or event.end_date is None
        or event.source_timezone is None
    ):
        return False
    try:
        zone = ZoneInfo(event.source_timezone)
    except ZoneInfoNotFoundError:
        return False
    start = datetime.combine(event.start_date, time.min, zone).astimezone(UTC)
    end = datetime.combine(event.end_date, time.min, zone).astimezone(UTC)
    return end > run.window_start and start < run.window_end


def _effective(
    session: Session, event: CalendarEventRevision
) -> tuple[Literal["current", "stale"], datetime]:
    observed = (
        select(CalendarEventObservation.id)
        .where(
            CalendarEventObservation.sync_run_id == CalendarSyncRun.id,
            CalendarEventObservation.occurrence_key == event.occurrence_key,
        )
        .correlate(CalendarSyncRun)
        .exists()
    )
    rows = session.execute(
        select(CalendarSyncRun, observed.label("observed"))
        .where(
            CalendarSyncRun.account_revision_id == event.account_revision_id,
            CalendarSyncRun.calendar_identity_id == event.calendar_identity_id,
            _eligible_condition(),
        )
        .order_by(CalendarSyncRun.completed_at.desc(), CalendarSyncRun.id.desc())
    ).all()
    for run, was_observed in rows:
        if was_observed:
            assert run.completed_at is not None
            return "current", run.completed_at
        if _covered(event, run):
            assert run.completed_at is not None
            return "stale", run.completed_at
    raise CalendarEventNotFoundError


def _occurrence_id(event: CalendarEventRevision) -> str:
    return hashlib.sha256(
        _OCCURRENCE_DOMAIN
        + str(event.calendar_identity_id).encode()
        + b":"
        + event.occurrence_key.encode()
    ).hexdigest()


def _public(session: Session, event: CalendarEventRevision) -> CalendarEventRead:
    state, evidence_at = _effective(session, event)
    return CalendarEventRead(
        id=event.id,
        occurrence_id=_occurrence_id(event),
        scope=CalendarScope(
            kind="unassigned" if event.project_id is None else "project",
            project_id=event.project_id,
        ),
        application_revision=event.application_revision,
        event_type=cast(Any, event.event_type),
        title=event.title,
        all_day=event.all_day,
        start_date=event.start_date,
        end_date=event.end_date,
        start_instant=event.start_instant,
        end_instant=event.end_instant,
        source_timezone=event.source_timezone,
        effective_state=state,
        last_evidence_at=evidence_at,
    )


def _filter_key(scope: CalendarExternalScope) -> str:
    return hashlib.sha256(
        ("unassigned" if scope.project_id is None else str(scope.project_id)).encode()
    ).hexdigest()


def _encode_cursor(event: CalendarEventRevision, key: str) -> str:
    payload = json.dumps(
        {"f": key, "r": event.application_revision, "i": str(event.id)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    tag = hmac.new(_CURSOR_DOMAIN, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + tag).decode().rstrip("=")


def _decode_cursor(value: str, key: str) -> tuple[int, uuid.UUID]:
    if not value or len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise CalendarEventCursorError
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload, tag = raw[:-32], raw[-32:]
        if not hmac.compare_digest(
            tag, hmac.new(_CURSOR_DOMAIN, payload, hashlib.sha256).digest()
        ):
            raise CalendarEventCursorError
        decoded = json.loads(payload)
        if set(decoded) != {"f", "i", "r"} or decoded["f"] != key:
            raise CalendarEventCursorError
        revision = decoded["r"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise CalendarEventCursorError
        return revision, uuid.UUID(decoded["i"])
    except (ValueError, TypeError, json.JSONDecodeError):
        raise CalendarEventCursorError from None


def list_events(
    session: Session,
    scope: CalendarExternalScope,
    *,
    limit: int,
    cursor: str | None,
) -> CalendarEventPage:
    _require_scope(session, scope)
    query = _latest_positive_query(scope)
    key = _filter_key(scope)
    if cursor is not None:
        revision, row_id = _decode_cursor(cursor, key)
        anchor = session.scalar(query.where(CalendarEventRevision.id == row_id))
        if anchor is None or anchor.application_revision != revision:
            raise CalendarEventCursorError
        query = query.where(
            (CalendarEventRevision.application_revision < revision)
            | and_(
                CalendarEventRevision.application_revision == revision,
                CalendarEventRevision.id < row_id,
            )
        )
    rows = list(
        session.scalars(
            query.order_by(
                CalendarEventRevision.application_revision.desc(),
                CalendarEventRevision.id.desc(),
            ).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return CalendarEventPage(
        items=[_public(session, event) for event in page],
        next_cursor=_encode_cursor(page[-1], key)
        if len(rows) > limit and page
        else None,
    )


def get_event(
    session: Session,
    scope: CalendarExternalScope,
    event_id: uuid.UUID,
) -> CalendarEventRead:
    _require_scope(session, scope)
    event = session.scalar(
        _latest_positive_query(scope).where(CalendarEventRevision.id == event_id)
    )
    if event is None:
        raise CalendarEventNotFoundError
    return _public(session, event)
