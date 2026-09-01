"""Checkpoint 100 persistence and export isolation tests."""

import uuid
import zipfile
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendar.identity import occurrence_identity
from app.db.session import get_engine
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)
from app.models.project import Project
from app.project_export.models import CURRENT_DATABASE_REVISION
from app.project_export.service import export_project
from app.repositories.calendar import (
    CalendarOwnershipError,
    create_account_revision,
    create_calendar_identity,
    create_sync_run,
    record_event_revision,
)
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_calendar_tables(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (
            CalendarEventRevision,
            CalendarSyncRun,
            CalendarIdentity,
            CalendarAccountRevision,
        ):
            session.execute(delete(model))
        session.commit()
    yield


def _account(**changes: object) -> CalendarAccountRevision:
    values: dict[str, object] = {
        "configuration_id": uuid.uuid4(),
        "configuration_revision": 1,
        "account_fingerprint": "a" * 64,
        "credential_reference": "sbcred:v1:12345678-1234-4123-8123-123456789abc",
    }
    values.update(changes)
    return CalendarAccountRevision(**values)


def _graph(
    session: Session, **account_changes: object
) -> tuple[CalendarAccountRevision, CalendarIdentity, CalendarSyncRun]:
    account = create_account_revision(session, _account(**account_changes))
    calendar = create_calendar_identity(
        session,
        CalendarIdentity(
            account_revision_id=account.id,
            account_fingerprint=account.account_fingerprint,
            provider_calendar_id="operator-entered-calendar",
        ),
    )
    now = datetime.now(UTC)
    run = create_sync_run(
        session,
        CalendarSyncRun(
            account_revision_id=account.id,
            calendar_identity_id=calendar.id,
            project_id=account.project_id,
            window_start=now,
            window_end=now + timedelta(days=30),
            trigger_kind="manual",
        ),
    )
    return account, calendar, run


def _event(run: CalendarSyncRun, **changes: object) -> CalendarEventRevision:
    now = datetime.now(UTC)
    identity = occurrence_identity(event_id="event-1")
    values: dict[str, object] = {
        "account_revision_id": run.account_revision_id,
        "calendar_identity_id": run.calendar_identity_id,
        "sync_run_id": run.id,
        "project_id": run.project_id,
        "provider_event_id": "event-1",
        "occurrence_key": identity.key,
        "provider_etag": '"etag-1"',
        "provider_updated_at": now,
        "application_revision": 999,
        "content_hash": "b" * 64,
        "event_type": "default",
        "title": "Safe title",
        "all_day": False,
        "start_instant": now,
        "end_instant": now + timedelta(hours=1),
        "source_timezone": "UTC",
        "state": "current",
        "is_private": False,
        "first_seen_at": now,
        "last_seen_at": now,
    }
    values.update(changes)
    return CalendarEventRevision(**values)


def test_tables_safe_fields_and_one_active_sync() -> None:
    columns = {
        item["name"]
        for item in inspect(get_engine()).get_columns("calendar_event_revisions")
    }
    assert not columns & {
        "description",
        "location",
        "attendees",
        "organizer",
        "creator",
        "conference_url",
        "raw_json",
        "recurrence",
    }
    with Session(get_engine()) as session:
        account, calendar, run = _graph(session)
        assert (
            account.account_fingerprint == "a" * 64
            and account.credential_reference.startswith("sbcred:v1:")
        )
        session.add(
            CalendarSyncRun(
                account_revision_id=account.id,
                calendar_identity_id=calendar.id,
                project_id=None,
                window_start=run.window_start,
                window_end=run.window_end,
                trigger_kind="manual",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_scope_ownership_revision_replay_and_historical_scope() -> None:
    with Session(get_engine()) as session:
        project = Project(name="calendar-" + uuid.uuid4().hex)
        session.add(project)
        session.flush()
        account, _, run = _graph(session, project_id=project.id)
        first, created = record_event_revision(
            session, _event(run), seen_at=datetime.now(UTC)
        )
        assert (
            created
            and first.application_revision == 1
            and first.project_id == project.id
        )
        replay, created = record_event_revision(
            session, _event(run), seen_at=datetime.now(UTC)
        )
        assert not created and replay.id == first.id
        changed, created = record_event_revision(
            session,
            _event(
                run,
                provider_etag='"etag-2"',
                content_hash="c" * 64,
                start_instant=first.start_instant + timedelta(hours=2),
                end_instant=first.end_instant + timedelta(hours=2),
            ),
            seen_at=datetime.now(UTC),
        )
        assert (
            created
            and changed.application_revision == 2
            and changed.occurrence_key == first.occurrence_key
        )
        revised = _account(
            configuration_id=account.configuration_id,
            configuration_revision=2,
            account_fingerprint="b" * 64,
            project_id=None,
            credential_reference="sbcred:v1:22345678-1234-4123-8123-123456789abc",
        )
        create_account_revision(session, revised)
        assert first.project_id == project.id and revised.project_id is None
        forged = CalendarIdentity(
            account_revision_id=revised.id,
            account_fingerprint=account.account_fingerprint,
            provider_calendar_id="forged",
        )
        with pytest.raises(CalendarOwnershipError):
            create_calendar_identity(session, forged)


def test_private_special_temporal_and_unknown_type_fail_closed() -> None:
    with Session(get_engine()) as session:
        _, _, run = _graph(session)
        private = _event(run, title="Busy", is_private=True)
        record_event_revision(session, private, seen_at=datetime.now(UTC))
        special = _event(
            run,
            provider_event_id="special",
            occurrence_key="event:special",
            provider_etag='"special"',
            content_hash="d" * 64,
            event_type="birthday",
            title="Birthday",
            all_day=True,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            start_instant=None,
            end_instant=None,
        )
        record_event_revision(session, special, seen_at=datetime.now(UTC))
        with pytest.raises(ValueError):
            record_event_revision(
                session,
                _event(
                    run,
                    provider_event_id="unknown",
                    occurrence_key="event:unknown",
                    event_type="future_type",
                ),
                seen_at=datetime.now(UTC),
            )


def test_export_v1_excludes_calendar_and_secret_canary(tmp_path: Path) -> None:
    canary = "sbcred:v1:32345678-1234-4123-8123-123456789abc"
    with Session(get_engine()) as session:
        project = Project(name="calendar-export-" + uuid.uuid4().hex)
        session.add(project)
        session.flush()
        _, _, run = _graph(session, project_id=project.id, credential_reference=canary)
        record_event_revision(session, _event(run), seen_at=datetime.now(UTC))
        session.commit()
        output = tmp_path / "project.zip"
        result = export_project(
            session,
            project.id,
            output,
            source_alembic_revision=CURRENT_DATABASE_REVISION,
        )
        assert result.format_version == 1
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        payload = b"".join(archive.read(name) for name in names)
    assert not any(name.startswith("calendar_") for name in names)
    assert (
        canary.encode() not in payload and b"operator-entered-calendar" not in payload
    )
