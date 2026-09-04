"""Explicit synchronous bounded Google Calendar full refresh."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.calendar.catalog import event_label
from app.calendar.dependencies import CalendarCredentialBoundary
from app.calendar.google import (
    MAX_EVENTS_PER_CALENDAR,
    MAX_EVENTS_PER_REFRESH,
    MAX_PAGES_PER_CALENDAR,
    REFRESH_DEADLINE_SECONDS,
    CalendarPage,
    CalendarTransport,
    CalendarTransportError,
)
from app.calendar.identity import occurrence_identity
from app.credentials import CredentialStoreError, validate_credential_reference
from app.google_oauth.contract import GoogleOAuthError
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)
from app.repositories import calendar as repository
from app.schemas.calendar import CalendarSyncRunRead


class CalendarSyncNotFoundError(Exception):
    pass


class CalendarSyncConflictError(Exception):
    pass


class CalendarSyncRevisionConflictError(Exception):
    pass


_TYPE_MAP = {
    "default": "default",
    "birthday": "birthday",
    "focusTime": "focus_time",
    "outOfOffice": "out_of_office",
    "workingLocation": "working_location",
}
_EVENT_KEYS = {
    "id",
    "status",
    "eventType",
    "summary",
    "visibility",
    "etag",
    "updated",
    "recurringEventId",
    "originalStartTime",
    "start",
    "end",
}
_TIME_KEYS = {"date", "dateTime", "timeZone"}
_CEILING_CODES = {
    "calendar_deadline_ceiling",
    "calendar_request_ceiling",
    "calendar_response_ceiling",
    "calendar_byte_ceiling",
    "calendar_page_item_ceiling",
    "calendar_page_ceiling",
    "calendar_event_ceiling",
    "calendar_account_event_ceiling",
}


def public_sync_run(
    run: CalendarSyncRun, calendar_id: str, configuration_revision: int
) -> CalendarSyncRunRead:
    return CalendarSyncRunRead(
        id=run.id,
        calendar_id=calendar_id,
        configuration_revision=configuration_revision,
        window_start=run.window_start,
        window_end=run.window_end,
        trigger_kind=cast(Any, run.trigger_kind),
        status=cast(Any, run.status),
        completeness=cast(Any, run.completeness),
        items_seen=run.items_seen,
        items_written=run.items_written,
        items_unchanged=run.items_unchanged,
        safe_failure_code=run.safe_failure_code,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _latest_account(
    session: Session, configuration_id: uuid.UUID, *, lock: bool = False
) -> CalendarAccountRevision | None:
    query = (
        select(CalendarAccountRevision)
        .where(CalendarAccountRevision.configuration_id == configuration_id)
        .order_by(CalendarAccountRevision.configuration_revision.desc())
        .limit(1)
        .options(selectinload(CalendarAccountRevision.calendars))
    )
    if lock:
        query = query.with_for_update(of=CalendarAccountRevision)
    return session.scalar(query)


def _eligible(
    account: CalendarAccountRevision, expected_revision: int | None = None
) -> None:
    if (
        (
            expected_revision is not None
            and account.configuration_revision != expected_revision
        )
        or account.lifecycle != "enabled"
        or account.configuration_state != "configured"
    ):
        raise CalendarSyncConflictError
    if len(account.calendars) < 1 or len(account.calendars) > 10:
        raise CalendarSyncConflictError
    ids = [value.provider_calendar_id for value in account.calendars]
    if len(set(ids)) != len(ids) or any(
        not value or len(value) > 1024 for value in ids
    ):
        raise CalendarSyncConflictError
    validate_credential_reference(account.credential_reference)


def claim(
    session: Session,
    configuration_id: uuid.UUID,
    expected_revision: int,
    *,
    anchor: datetime | None = None,
) -> list[CalendarSyncRun]:
    account = _latest_account(session, configuration_id, lock=True)
    if account is None:
        raise CalendarSyncNotFoundError
    if account.configuration_revision != expected_revision:
        raise CalendarSyncRevisionConflictError
    _eligible(account, expected_revision)
    captured = (anchor or datetime.now(UTC)).astimezone(UTC)
    window_start, window_end = (
        captured - timedelta(days=30),
        captured + timedelta(days=60),
    )
    runs: list[CalendarSyncRun] = []
    try:
        for calendar in sorted(
            account.calendars, key=lambda value: value.provider_calendar_id
        ):
            run = CalendarSyncRun(
                account_revision_id=account.id,
                calendar_identity_id=calendar.id,
                project_id=account.project_id,
                window_start=window_start,
                window_end=window_end,
                trigger_kind="manual",
            )
            runs.append(repository.create_sync_run(session, run))
    except IntegrityError:
        raise CalendarSyncConflictError from None
    return runs


def _fence(
    session: Session,
    configuration_id: uuid.UUID,
    captured: CalendarAccountRevision,
    calendar: CalendarIdentity | None = None,
) -> CalendarAccountRevision:
    current = _latest_account(session, configuration_id)
    if current is None:
        raise CalendarTransportError("calendar_configuration_drift")
    try:
        _eligible(current, captured.configuration_revision)
    except (CalendarSyncConflictError, ValueError):
        raise CalendarTransportError("calendar_configuration_drift") from None
    expected = (
        captured.id,
        captured.project_id,
        captured.account_fingerprint,
        captured.credential_reference,
    )
    if (
        current.id,
        current.project_id,
        current.account_fingerprint,
        current.credential_reference,
    ) != expected:
        raise CalendarTransportError("calendar_configuration_drift")
    if calendar is not None and not any(
        item.id == calendar.id
        and item.provider_calendar_id == calendar.provider_calendar_id
        for item in current.calendars
    ):
        raise CalendarTransportError("calendar_configuration_drift")
    return current


def _string(value: object, *, optional: bool = False) -> str:
    if optional and value is None:
        return ""
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise CalendarTransportError("calendar_invalid_event")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise CalendarTransportError("calendar_invalid_event") from None
    return value


def _instant(raw: object, timezone_name: object = None) -> datetime:
    value = _string(raw)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CalendarTransportError("calendar_invalid_event") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if not isinstance(timezone_name, str) or not timezone_name:
            raise CalendarTransportError("calendar_invalid_event")
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise CalendarTransportError("calendar_invalid_event") from None
        candidates = [
            candidate
            for fold in (0, 1)
            if (candidate := parsed.replace(tzinfo=zone, fold=fold))
            .astimezone(UTC)
            .astimezone(zone)
            .replace(tzinfo=None)
            == parsed
        ]
        if len({candidate.utcoffset() for candidate in candidates}) != 1:
            raise CalendarTransportError("calendar_invalid_event")
        if not candidates:
            raise CalendarTransportError("calendar_invalid_event")
        parsed = candidates[0]
    return parsed


def _temporal(value: object) -> tuple[bool, date | None, datetime | None, str | None]:
    if not isinstance(value, dict) or not set(value).issubset(_TIME_KEYS):
        raise CalendarTransportError("calendar_invalid_event")
    zone = value.get("timeZone")
    if zone is not None and (not isinstance(zone, str) or not zone or len(zone) > 255):
        raise CalendarTransportError("calendar_invalid_event")
    if set(value) & {"date"} and set(value) & {"dateTime"}:
        raise CalendarTransportError("calendar_invalid_event")
    if "date" in value:
        try:
            parsed_date = date.fromisoformat(_string(value["date"]))
        except ValueError:
            raise CalendarTransportError("calendar_invalid_event") from None
        return True, parsed_date, None, zone
    if "dateTime" in value:
        return False, None, _instant(value["dateTime"], zone), zone
    raise CalendarTransportError("calendar_invalid_event")


def _normalized(
    item: object, run: CalendarSyncRun, seen_at: datetime
) -> CalendarEventRevision:
    if not isinstance(item, dict) or not set(item).issubset(_EVENT_KEYS):
        raise CalendarTransportError("calendar_invalid_event")
    if item.get("status") not in {"confirmed", "tentative"}:
        code = (
            "calendar_cancelled_event"
            if item.get("status") == "cancelled"
            else "calendar_invalid_event"
        )
        raise CalendarTransportError(code)
    provider_type = item.get("eventType")
    if provider_type not in _TYPE_MAP:
        raise CalendarTransportError("calendar_event_type_invalid")
    event_type = _TYPE_MAP[cast(str, provider_type)]
    event_id, etag = _string(item.get("id")), _string(item.get("etag"))
    updated = _instant(item.get("updated"))
    start_all, start_date, start_instant, start_zone = _temporal(item.get("start"))
    end_all, end_date, end_instant, end_zone = _temporal(item.get("end"))
    if (
        start_all != end_all
        or (start_all and cast(date, end_date) <= cast(date, start_date))
        or (
            not start_all
            and cast(datetime, end_instant) <= cast(datetime, start_instant)
        )
    ):
        raise CalendarTransportError("calendar_invalid_event")
    private = item.get("visibility") == "private"
    if item.get("visibility") not in {
        None,
        "default",
        "public",
        "private",
        "confidential",
    }:
        raise CalendarTransportError("calendar_invalid_event")
    summary = item.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise CalendarTransportError("calendar_invalid_event")
    try:
        title = event_label(event_type, private=private, ordinary_title=summary or "")
    except ValueError:
        raise CalendarTransportError("calendar_invalid_event") from None
    series = item.get("recurringEventId")
    original_date: date | None = None
    original_instant: datetime | None = None
    if series is not None:
        series = _string(series)
        original_all, original_date, original_instant, _ = _temporal(
            item.get("originalStartTime")
        )
        if original_all != start_all:
            raise CalendarTransportError("calendar_invalid_event")
    elif "originalStartTime" in item:
        raise CalendarTransportError("calendar_invalid_event")
    identity = occurrence_identity(
        event_id=event_id,
        recurring_series_id=series,
        original_start=original_date or original_instant,
    )
    normalized = {
        "event_type": event_type,
        "title": title,
        "all_day": start_all,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "start_instant": start_instant.isoformat() if start_instant else None,
        "end_instant": end_instant.isoformat() if end_instant else None,
        "source_timezone": start_zone or end_zone,
        "state": "current",
        "is_private": private,
    }
    content_hash = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CalendarEventRevision(
        account_revision_id=run.account_revision_id,
        calendar_identity_id=run.calendar_identity_id,
        sync_run_id=run.id,
        project_id=run.project_id,
        provider_event_id=event_id,
        recurring_series_id=series,
        occurrence_key=identity.key,
        original_start_date=original_date,
        original_start_instant=original_instant,
        provider_etag=etag,
        provider_updated_at=updated,
        application_revision=1,
        content_hash=content_hash,
        event_type=event_type,
        title=title,
        all_day=start_all,
        start_date=start_date,
        end_date=end_date,
        start_instant=start_instant,
        end_instant=end_instant,
        source_timezone=start_zone or end_zone,
        state="current",
        is_private=private,
        first_seen_at=seen_at,
        last_seen_at=seen_at,
    )


def _finish(
    session: Session, run: CalendarSyncRun, *, status: str, code: str | None
) -> None:
    current = session.get(CalendarSyncRun, run.id)
    if current is None:
        return
    current.status = status
    current.completeness = "complete" if status == "succeeded" else "incomplete"
    if status != "succeeded":
        current.observation_evidence_version = None
    current.safe_failure_code = code
    current.completed_at = datetime.now(UTC)


def refresh(
    session: Session,
    runs: list[CalendarSyncRun],
    boundary: CalendarCredentialBoundary,
    transport_factory: Callable[[], CalendarTransport],
) -> list[CalendarSyncRun]:
    if not runs:
        return []
    deadline = time.monotonic() + REFRESH_DEADLINE_SECONDS
    captured = session.get(CalendarAccountRevision, runs[0].account_revision_id)
    assert captured is not None
    configuration_id = captured.configuration_id
    captured_fingerprint = captured.account_fingerprint
    run_values = [
        (run.id, run.calendar_identity_id, run.window_start, run.window_end)
        for run in runs
    ]
    account_total = 0
    transport: CalendarTransport | None = None
    access_token: str | None = None
    active_index = 0
    try:
        _fence(session, configuration_id, captured)
        reference = validate_credential_reference(captured.credential_reference)
        session.rollback()
        metadata = boundary.status(reference)
        if (
            metadata.get("status") != "authorized"
            or metadata.get("account_fingerprint") != captured_fingerprint
        ):
            raise CalendarTransportError("calendar_credential_mismatch")
        access_token = boundary.refresh(reference)
        transport = transport_factory()
        for loop_index, (
            run_id,
            calendar_identity_id,
            window_start,
            window_end,
        ) in enumerate(run_values):
            active_index = loop_index
            with session.begin():
                calendar = session.get(CalendarIdentity, calendar_identity_id)
                assert calendar is not None
                _fence(session, configuration_id, captured, calendar)
                current = session.get(CalendarSyncRun, run_id)
                assert current is not None
                current.status = "running"
                current.started_at = datetime.now(UTC)
                calendar_id = calendar.provider_calendar_id
            token: str | None = None
            tokens: set[str] = set()
            calendar_total = 0
            for page_number in range(1, MAX_PAGES_PER_CALENDAR + 1):
                if time.monotonic() >= deadline:
                    raise CalendarTransportError("calendar_deadline_ceiling")
                page: CalendarPage = transport.events(
                    access_token,
                    calendar_id,
                    window_start,
                    window_end,
                    token,
                )
                if calendar_total + len(page.items) > MAX_EVENTS_PER_CALENDAR:
                    raise CalendarTransportError("calendar_event_ceiling")
                if account_total + len(page.items) > MAX_EVENTS_PER_REFRESH:
                    raise CalendarTransportError("calendar_account_event_ceiling")
                now = datetime.now(UTC)
                normalized = [_normalized(item, current, now) for item in page.items]
                keys = [item.occurrence_key for item in normalized]
                if len(set(keys)) != len(keys):
                    raise CalendarTransportError("calendar_invalid_event")
                with session.begin():
                    _fence(session, configuration_id, captured, calendar)
                    current = session.get(CalendarSyncRun, run_id)
                    assert current is not None
                    written = 0
                    for event in normalized:
                        stored, created = repository.record_event_revision(
                            session, event, seen_at=now
                        )
                        repository.record_event_observation(
                            session, current, stored, observed_at=now
                        )
                        written += int(created)
                    current.items_seen += len(normalized)
                    current.items_written += written
                    current.items_unchanged += len(normalized) - written
                calendar_total += len(normalized)
                account_total += len(normalized)
                token = page.next_page_token
                if token is None:
                    break
                if token in tokens:
                    raise CalendarTransportError("calendar_page_token_loop")
                tokens.add(token)
                if page_number == MAX_PAGES_PER_CALENDAR:
                    raise CalendarTransportError("calendar_page_ceiling")
            with session.begin():
                _fence(session, configuration_id, captured, calendar)
                current = session.get(CalendarSyncRun, run_id)
                assert current is not None
                repository.mark_observation_evidence_complete(session, current)
                _finish(session, current, status="succeeded", code=None)
        return [
            cast(CalendarSyncRun, session.get(CalendarSyncRun, run.id)) for run in runs
        ]
    except (CredentialStoreError, GoogleOAuthError) as exc:
        code = getattr(exc, "code", "calendar_credential_failed")
    except CalendarTransportError as exc:
        code = exc.code
    except (repository.CalendarObservationError, IntegrityError):
        code = "calendar_observation_evidence_invalid"
    session.rollback()
    status = "incomplete" if code in _CEILING_CODES else "failed"
    with session.begin():
        for run in runs[active_index:]:
            _finish(session, run, status=status, code=code)
    return [cast(CalendarSyncRun, session.get(CalendarSyncRun, run.id)) for run in runs]


def history(
    session: Session, configuration_id: uuid.UUID, *, limit: int
) -> list[tuple[CalendarSyncRun, str, int]]:
    account = _latest_account(session, configuration_id)
    if account is None:
        raise CalendarSyncNotFoundError
    revision_ids = select(CalendarAccountRevision.id).where(
        CalendarAccountRevision.configuration_id == configuration_id
    )
    rows = session.execute(
        select(
            CalendarSyncRun,
            CalendarIdentity.provider_calendar_id,
            CalendarAccountRevision.configuration_revision,
        )
        .join(
            CalendarIdentity,
            CalendarIdentity.id == CalendarSyncRun.calendar_identity_id,
        )
        .join(
            CalendarAccountRevision,
            CalendarAccountRevision.id == CalendarSyncRun.account_revision_id,
        )
        .where(CalendarSyncRun.account_revision_id.in_(revision_ids))
        .order_by(
            CalendarSyncRun.created_at.desc(),
            CalendarIdentity.provider_calendar_id,
            CalendarSyncRun.id.desc(),
        )
        .limit(limit)
    ).all()
    return [(run, calendar_id, revision) for run, calendar_id, revision in rows]
