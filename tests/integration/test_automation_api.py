"""Checkpoint 77 Automation API, lifecycle, and concurrency coverage."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.automations import service
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentRun
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.models.project import Project
from app.schemas.automation import AutomationCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_automations(
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


def _payload(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "label": "Morning brief",
        "agent_kind": "daily_brief",
        "schedule": {
            "kind": "daily",
            "timezone_name": "Asia/Jerusalem",
            "local_time": "08:30:00",
        },
    }
    values.update(changes)
    return values


def test_create_read_list_pagination_order_and_exact_unassigned_scope() -> None:
    client = TestClient(create_app())
    created = [
        client.post("/automations", json=_payload(label=label)).json()
        for label in ("One", "Two", "Three")
    ]
    assert all(item["lifecycle"] == "draft" for item in created)
    assert all(item["execution_mode"] == "create_only" for item in created)
    assert all(item["project_id"] is None for item in created)
    assert client.get(f"/automations/{created[1]['id']}").json() == created[1]
    full = client.get("/automations").json()
    page = client.get("/automations?limit=1&offset=1").json()
    assert page == full[1:2]
    assert client.get("/automations?limit=101").status_code == 422


def test_lifecycle_revisions_edits_and_terminal_cancellation() -> None:
    client = TestClient(create_app())
    created = client.post("/automations", json=_payload()).json()
    metadata = client.patch(
        f"/automations/{created['id']}",
        json={"expected_revision": 0, "label": "Renamed"},
    ).json()
    assert (metadata["revision"], metadata["schedule_revision"]) == (1, 0)
    schedule_edit = client.patch(
        f"/automations/{created['id']}",
        json={
            "expected_revision": 1,
            "schedule": {
                "kind": "weekly",
                "timezone_name": "UTC",
                "local_time": "09:00:00",
                "weekdays": [1, 3],
            },
        },
    ).json()
    assert (schedule_edit["revision"], schedule_edit["schedule_revision"]) == (2, 1)
    enabled = client.post(
        f"/automations/{created['id']}/enable", json={"expected_revision": 2}
    ).json()
    assert enabled["lifecycle"] == "enabled"
    assert enabled["next_occurrence_at"] is not None
    assert (
        client.patch(
            f"/automations/{created['id']}",
            json={"expected_revision": 3, "execution_mode": "automatic_read_only"},
        ).status_code
        == 409
    )
    paused = client.post(
        f"/automations/{created['id']}/pause", json={"expected_revision": 3}
    ).json()
    mode_edit = client.post(
        f"/automations/{created['id']}/execution-mode",
        json={"expected_revision": 4, "execution_mode": "automatic_read_only"},
    )
    assert mode_edit.status_code == 200
    assert mode_edit.json()["execution_mode"] == "automatic_read_only"
    create_only = client.post(
        f"/automations/{created['id']}/execution-mode",
        json={"expected_revision": 5, "execution_mode": "create_only"},
    ).json()
    assert (create_only["revision"], create_only["schedule_revision"]) == (6, 1)
    assert (
        client.post(
            f"/automations/{created['id']}/execution-mode",
            json={"expected_revision": 4, "execution_mode": "create_only"},
        ).status_code
        == 409
    )
    resumed = client.post(
        f"/automations/{created['id']}/resume", json={"expected_revision": 6}
    ).json()
    assert (paused["lifecycle"], resumed["lifecycle"]) == ("paused", "enabled")
    assert resumed["revision"] == 7
    cancelled = client.post(
        f"/automations/{created['id']}/cancel", json={"expected_revision": 7}
    ).json()
    assert (
        client.post(
            f"/automations/{created['id']}/execution-mode",
            json={"expected_revision": 8, "execution_mode": "create_only"},
        ).status_code
        == 409
    )
    assert cancelled["lifecycle"] == "cancelled"
    assert cancelled["cancelled_at"] is not None
    assert cancelled["next_occurrence_at"] is None
    for suffix in ("resume", "cancel"):
        assert (
            client.post(
                f"/automations/{created['id']}/{suffix}",
                json={"expected_revision": 8},
            ).status_code
            == 409
        )


def test_generic_update_can_activate_implemented_daily_brief_identity() -> None:
    client = TestClient(create_app())
    created = client.post("/automations", json=_payload()).json()
    response = client.patch(
        f"/automations/{created['id']}",
        json={"expected_revision": 0, "execution_mode": "automatic_read_only"},
    )
    assert response.status_code == 200
    assert response.json()["execution_mode"] == "automatic_read_only"
    assert client.get(f"/automations/{created['id']}").json()["revision"] == 1
    assert (
        client.patch(
            f"/automations/{created['id']}",
            json={"expected_revision": 7, "label": "Forbidden"},
        ).status_code
        == 409
    )


def test_invalid_transitions_stale_revision_and_one_time_past_fail_safely() -> None:
    client = TestClient(create_app())
    created = client.post("/automations", json=_payload()).json()
    assert (
        client.post(
            f"/automations/{created['id']}/pause", json={"expected_revision": 0}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/automations/{created['id']}/enable", json={"expected_revision": 9}
        ).status_code
        == 409
    )
    past = client.post(
        "/automations",
        json=_payload(
            schedule={
                "kind": "one_time",
                "timezone_name": "UTC",
                "local_time": "09:00:00",
                "one_time_local_date": "2000-01-01",
            }
        ),
    ).json()
    assert (
        client.post(
            f"/automations/{past['id']}/enable", json={"expected_revision": 0}
        ).status_code
        == 422
    )


def test_preview_is_side_effect_free_and_closed() -> None:
    client = TestClient(create_app())
    created = client.post("/automations", json=_payload()).json()
    before = client.get(f"/automations/{created['id']}").json()
    response = client.post(
        "/automations/preview",
        json={
            "schedule": _payload()["schedule"],
            "after_utc": "2026-08-24T00:00:00Z",
            "count": 3,
        },
    )
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert set(response.json()[0]) == {
        "local_date",
        "local_time",
        "timezone_name",
        "utc_offset_minutes",
        "utc_instant",
    }
    assert client.get(f"/automations/{created['id']}").json() == before
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 0
        )


def test_catalog_project_validation_missing_and_deleted_project_behavior() -> None:
    client = TestClient(create_app())
    missing = str(uuid.uuid4())
    assert (
        client.post("/automations", json=_payload(project_id=missing)).status_code
        == 404
    )
    assert (
        client.post(
            "/automations", json=_payload(agent_kind="project_watch")
        ).status_code
        == 422
    )
    project = client.post("/projects", json={"name": "Watch scope"}).json()
    created = client.post(
        "/automations",
        json=_payload(agent_kind="project_watch", project_id=project["id"]),
    )
    assert created.status_code == 201
    with Session(get_engine()) as session:
        row = session.get(Project, uuid.UUID(project["id"]))
        assert row is not None
        session.delete(row)
        with pytest.raises(IntegrityError):
            session.commit()


def test_no_occurrence_run_provider_or_tool_side_effects() -> None:
    with Session(get_engine()) as session:
        run_count = session.scalar(select(func.count()).select_from(AgentRun))
    client = TestClient(create_app())
    rejected = client.post(
        "/automations",
        json=_payload(execution_mode="automatic_read_only"),
    )
    assert rejected.status_code == 201
    created = rejected.json()
    assert (
        client.post(
            f"/automations/{created['id']}/enable", json={"expected_revision": 0}
        ).status_code
        == 200
    )
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 0
        )
        assert session.scalar(select(func.count()).select_from(AgentRun)) == run_count


def test_concurrent_pause_uses_row_lock_and_revision_cas() -> None:
    captured = datetime(2026, 8, 24, tzinfo=UTC)
    with Session(get_engine()) as session:
        automation = service.create_automation(
            session,
            AutomationCreate.model_validate(_payload()),
        )
        service.enable_automation(session, automation.id, 0, captured_at=captured)
        session.commit()
        automation_id = automation.id

    def pause() -> str:
        with Session(get_engine()) as session:
            try:
                service.pause_automation(session, automation_id, 1)
                session.commit()
                return "won"
            except service.AutomationRevisionConflictError:
                session.rollback()
                return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _: pause(), range(2)))
    assert outcomes == ["stale", "won"]
    with Session(get_engine()) as session:
        current = session.get(Automation, automation_id)
        assert current is not None
        assert (current.lifecycle, current.revision) == ("paused", 2)


def test_service_repositories_leave_commit_and_rollback_to_caller() -> None:
    with Session(get_engine()) as session:
        automation = service.create_automation(
            session, AutomationCreate.model_validate(_payload())
        )
        automation_id = automation.id
        session.rollback()
    with Session(get_engine()) as session:
        assert session.get(Automation, automation_id) is None
