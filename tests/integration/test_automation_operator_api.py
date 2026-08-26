"""Checkpoint 81 safe history and local notification inbox coverage."""

from collections.abc import Generator
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_rows(
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


def _facts() -> tuple[Automation, AutomationOccurrence, AutomationOccurrence]:
    now = datetime(2026, 8, 26, 8, tzinfo=UTC)
    automation = Automation(
        label="Safe operator history",
        agent_kind="daily_brief",
        schedule_kind="daily",
        timezone_name="Asia/Jerusalem",
        local_time=time(11),
    )
    with Session(get_engine()) as session:
        session.add(automation)
        session.flush()
        rows = []
        for index, state in enumerate(("missed", "failed")):
            instant = now + timedelta(days=index)
            row = AutomationOccurrence(
                automation_id=automation.id,
                schedule_revision=0,
                scheduled_at=instant,
                scheduled_local_date=date(2026, 8, 26 + index),
                scheduled_local_time=time(11),
                scheduled_utc_offset_minutes=180,
                timezone_name="Asia/Jerusalem",
                occurrence_key=f"safe:{automation.id}:{index}",
                state=state,
                attempt_count=index + 1,
                safe_disposition_code="operator_review_required",
                safe_error_code=None if state == "missed" else "setup_failed_safe",
                automation_revision=0,
                automation_kind="scheduled_agent",
                automation_label=automation.label,
                agent_kind="daily_brief",
                agent_version="1",
                execution_mode="create_only",
                created_at=instant,
                completed_at=instant,
            )
            session.add(row)
            rows.append(row)
        session.commit()
        for row in (automation, *rows):
            session.refresh(row)
            session.expunge(row)
    return automation, rows[0], rows[1]


def test_occurrence_history_is_bounded_newest_first_and_redacted() -> None:
    automation, older, newer = _facts()
    client = TestClient(create_app())
    response = client.get(f"/automations/{automation.id}/occurrences?limit=1&offset=0")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(newer.id)]
    keys = set(response.json()[0])
    assert "lease_owner_token" not in keys
    assert "occurrence_key" not in keys
    assert "automation_label" not in keys
    page_two = client.get(
        f"/automations/{automation.id}/occurrences?limit=1&offset=1"
    ).json()
    assert [item["id"] for item in page_two] == [str(older.id)]
    assert (
        client.get(f"/automations/{automation.id}/occurrences?limit=101").status_code
        == 422
    )


def test_notification_inbox_dedup_redaction_and_idempotent_mark_read() -> None:
    automation, _, occurrence = _facts()
    secret = "provider-secret-must-not-appear"
    with Session(get_engine()) as session:
        session.add(
            AutomationNotification(
                automation_id=automation.id,
                occurrence_id=occurrence.id,
                event_kind="occurrence_failed",
                severity="error",
                title="Automation needs review",
                body="Open Automation history for safe status.",
                deduplication_key=f"private:{secret}:{occurrence.id}",
            )
        )
        session.commit()
    client = TestClient(create_app())
    listed = client.get("/automation-notifications?limit=50&offset=0").json()
    assert len(listed) == 1
    assert "deduplication_key" not in listed[0]
    assert secret not in str(listed)
    notification_id = listed[0]["id"]
    first = client.post(f"/automation-notifications/{notification_id}/read").json()
    repeated = client.post(f"/automation-notifications/{notification_id}/read").json()
    assert first["read_at"] == repeated["read_at"]
    assert client.get("/automation-notifications?unread_only=true").json() == []
    assert (
        client.get(
            f"/automation-notifications?automation_id={automation.id}"
        ).status_code
        == 200
    )
