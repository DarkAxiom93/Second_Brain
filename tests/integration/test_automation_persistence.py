"""Checkpoint 76 persistence tests on the verified PostgreSQL test database."""

import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.models.project import Project
from app.repositories.automations import (
    create_automation,
    insert_automation_notification,
    insert_automation_occurrence,
    list_automation_notifications,
    list_automation_occurrences,
)
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_automation_tables(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (AutomationNotification, AutomationOccurrence, Automation):
            session.execute(delete(model))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in (AutomationNotification, AutomationOccurrence, Automation):
            session.execute(delete(model))
        session.commit()


def _automation(**changes: object) -> Automation:
    values: dict[str, object] = {
        "label": "Morning brief",
        "agent_kind": "daily_brief",
        "schedule_kind": "daily",
        "timezone_name": "Asia/Jerusalem",
        "local_time": time(8, 30),
    }
    values.update(changes)
    return Automation(**values)


def _occurrence(automation: Automation, **changes: object) -> AutomationOccurrence:
    scheduled = datetime(2026, 8, 24, 5, 30, tzinfo=UTC)
    values: dict[str, object] = {
        "automation_id": automation.id,
        "schedule_revision": automation.schedule_revision,
        "scheduled_at": scheduled,
        "scheduled_local_date": date(2026, 8, 24),
        "scheduled_local_time": time(8, 30),
        "scheduled_utc_offset_minutes": 180,
        "timezone_name": automation.timezone_name,
        "occurrence_key": f"{automation.id}:0:{scheduled.isoformat()}",
        "automation_revision": automation.revision,
        "automation_kind": automation.automation_kind,
        "automation_label": automation.label,
        "agent_kind": automation.agent_kind,
        "agent_version": automation.agent_version,
        "execution_mode": automation.execution_mode,
        "project_id": automation.project_id,
    }
    values.update(changes)
    return AutomationOccurrence(**values)


def test_all_tables_relationships_indexes_and_transaction_neutral_repositories() -> (
    None
):
    with Session(get_engine()) as session:
        project = Project(name="automation-project-" + uuid.uuid4().hex)
        session.add(project)
        session.flush()
        automation = create_automation(session, _automation(project_id=project.id))
        occurrence = insert_automation_occurrence(session, _occurrence(automation))
        notification = insert_automation_notification(
            session,
            AutomationNotification(
                automation_id=automation.id,
                occurrence_id=occurrence.id,
                event_kind="occurrence_missed",
                severity="warning",
                title="Scheduled occurrence missed",
                body="Open the Automation history for safe details.",
                deduplication_key=f"missed:{occurrence.id}",
            ),
        )
        assert occurrence.automation_id == automation.id
        assert notification.occurrence_id == occurrence.id
        assert list_automation_occurrences(session, automation.id, limit=10) == [
            occurrence
        ]
        assert list_automation_notifications(session, automation.id, limit=10) == [
            notification
        ]
        session.rollback()

    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(Automation)) == 0
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 0
        )
        assert (
            session.scalar(select(func.count()).select_from(AutomationNotification))
            == 0
        )

    inspector = inspect(get_engine())
    assert {item["name"] for item in inspector.get_indexes("automations")} >= {
        "ix_automations_due",
        "ix_automations_project_created",
    }
    assert {
        item["name"] for item in inspector.get_indexes("automation_occurrences")
    } >= {
        "ix_automation_occurrences_due",
        "ix_automation_occurrences_lease",
    }
    assert {
        item["name"] for item in inspector.get_indexes("automation_notifications")
    } >= {"ix_automation_notifications_inbox"}


def test_occurrence_slot_and_notification_deduplication_are_unique() -> None:
    with Session(get_engine()) as session:
        automation = create_automation(session, _automation())
        first = insert_automation_occurrence(session, _occurrence(automation))
        insert_automation_notification(
            session,
            AutomationNotification(
                automation_id=automation.id,
                occurrence_id=first.id,
                event_kind="occurrence_failed",
                severity="error",
                title="Occurrence failed",
                body="Open history.",
                deduplication_key="same-key",
            ),
        )
        session.commit()
        automation_id = automation.id

    with Session(get_engine()) as session:
        automation = session.get(Automation, automation_id)
        assert automation is not None
        session.add(_occurrence(automation, occurrence_key="different-key"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            AutomationNotification(
                automation_id=automation_id,
                event_kind="capacity_delayed",
                severity="warning",
                title="Capacity delayed",
                body="Open history.",
                deduplication_key="same-key",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("model_factory", "field", "value"),
    [
        (_automation, "lifecycle", "running"),
        (_automation, "execution_mode", "execute"),
        (_automation, "schedule_kind", "cron"),
        (_automation, "revision", -1),
        (_automation, "retry_limit", 4),
        (_automation, "capacity_limit", 33),
    ],
)
def test_automation_closed_values_and_bounds_reject(
    model_factory: object, field: str, value: object
) -> None:
    factory = model_factory
    assert callable(factory)
    with Session(get_engine()) as session:
        session.add(factory(**{field: value}))
        with pytest.raises(IntegrityError):
            session.commit()


def test_occurrence_closed_values_counters_leases_and_foreign_keys_reject() -> None:
    with Session(get_engine()) as session:
        automation = create_automation(session, _automation())
        session.commit()
        automation_id = automation.id

    invalid_changes = [
        {"state": "ready"},
        {"revision": -1},
        {"attempt_count": -1},
        {"lease_generation": -1},
        {"lease_owner_token": uuid.uuid4()},
        {"agent_run_id": uuid.uuid4()},
    ]
    for ordinal, changes in enumerate(invalid_changes):
        with Session(get_engine()) as session:
            automation = session.get(Automation, automation_id)
            assert automation is not None
            occurrence = _occurrence(
                automation,
                scheduled_at=datetime(2026, 8, 24 + ordinal, 5, 30, tzinfo=UTC),
                occurrence_key=f"invalid:{ordinal}:{uuid.uuid4()}",
                **changes,
            )
            session.add(occurrence)
            with pytest.raises(IntegrityError):
                session.commit()


def test_terminal_and_cancelled_timestamp_relationships_reject() -> None:
    with Session(get_engine()) as session:
        session.add(_automation(lifecycle="cancelled"))
        with pytest.raises(IntegrityError):
            session.commit()
    with Session(get_engine()) as session:
        automation = create_automation(session, _automation())
        session.add(_occurrence(automation, state="completed"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_project_delete_is_restricted_and_null_scope_remains_exact() -> None:
    with Session(get_engine()) as session:
        project = Project(name="automation-fk-" + uuid.uuid4().hex)
        session.add(project)
        session.flush()
        scoped = create_automation(session, _automation(project_id=project.id))
        unassigned = create_automation(
            session, _automation(label="Unassigned", project_id=None)
        )
        session.commit()
        assert unassigned.project_id is None
        project_id = project.id
        scoped_id = scoped.id
    with Session(get_engine()) as session:
        project = session.get(Project, project_id)
        assert project is not None
        session.delete(project)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.get(Automation, scoped_id) is not None


def test_notification_closed_values_and_agent_run_fk_reject() -> None:
    with Session(get_engine()) as session:
        automation = create_automation(session, _automation())
        session.commit()
        automation_id = automation.id
    for changes in (
        {"event_kind": "raw_provider_error", "severity": "error"},
        {"event_kind": "run_completed", "severity": "critical"},
        {
            "event_kind": "run_completed",
            "severity": "info",
            "agent_run_id": uuid.uuid4(),
        },
    ):
        with Session(get_engine()) as session:
            session.add(
                AutomationNotification(
                    automation_id=automation_id,
                    title="Safe title",
                    body="Safe body",
                    deduplication_key=uuid.uuid4().hex,
                    **changes,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
