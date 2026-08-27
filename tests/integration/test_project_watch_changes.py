"""Deterministic Project Watch watermark and exact-scope change proofs."""

import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.db.session import get_engine
from app.models.agent_runtime import AgentEvent, AgentRun
from app.models.automation import Automation, AutomationOccurrence
from app.models.memory import Memory
from app.models.project import Project
from app.project_watch.changes import INITIAL_WINDOW, collect, derive_window, is_current
from app.repositories import agent_runtime as runtime_repository
from app.schemas.agent_run import AgentRunCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    yield
    with Session(get_engine()) as session:
        session.execute(delete(AutomationOccurrence))
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.execute(delete(Automation))
        session.execute(delete(Memory).where(Memory.title.like("watch-test-%")))
        session.execute(delete(Project).where(Project.name.like("watch-test-%")))
        session.commit()


def _automation(session: Session, project_id: uuid.UUID, now: datetime) -> Automation:
    row = Automation(
        label="IGNORE THIS LABEL",
        agent_kind="project_watch",
        project_id=project_id,
        lifecycle="enabled",
        execution_mode="automatic_read_only",
        schedule_kind="daily",
        timezone_name="UTC",
        local_time=time(8),
        created_at=now - timedelta(days=10),
    )
    session.add(row)
    session.flush()
    return row


def _run(session: Session, project_id: uuid.UUID, now: datetime) -> AgentRun:
    request = AgentRunCreate(
        project_id=project_id,
        agent_kind="project_watch",
        agent_version="1",
        goal_summary="Fixed Project Watch v1 goal",
    )
    return run_service.create_run(
        session,
        request,
        idempotency_key_hash=run_service.hash_idempotency_key(str(uuid.uuid4())),
        fingerprint=run_service.normalized_request_fingerprint(request),
        now=now,
    ).run


def _occurrence(
    session: Session,
    automation: Automation,
    run: AgentRun,
    scheduled_at: datetime,
    *,
    state: str = "run_created",
) -> AutomationOccurrence:
    terminal = state in {"completed", "failed", "cancelled"}
    row = AutomationOccurrence(
        automation_id=automation.id,
        schedule_revision=automation.schedule_revision,
        scheduled_at=scheduled_at,
        scheduled_local_date=date.fromisoformat(scheduled_at.date().isoformat()),
        scheduled_local_time=scheduled_at.time().replace(tzinfo=None),
        scheduled_utc_offset_minutes=0,
        timezone_name="UTC",
        occurrence_key=f"watch-test:{uuid.uuid4()}",
        state=state,
        created_at=scheduled_at,
        completed_at=scheduled_at if terminal else None,
        automation_revision=automation.revision,
        automation_kind="scheduled_agent",
        automation_label=automation.label,
        agent_kind="project_watch",
        agent_version="1",
        execution_mode="automatic_read_only",
        project_id=automation.project_id,
        agent_run_id=run.id,
    )
    session.add(row)
    session.flush()
    return row


def _successful_result(session: Session, run: AgentRun, now: datetime) -> None:
    terminal_at = run.created_at + timedelta(seconds=1)
    run.state = "completed"
    run.started_at = run.created_at
    run.finished_at = terminal_at
    runtime_repository.append_agent_event(
        session,
        run_id=run.id,
        event_type="project_watch.result",
        safe_code="project_watch_result",
        safe_message="bounded result",
        metadata={"status": "no_meaningful_change"},
        correlation_id=run.correlation_id,
        occurred_at=terminal_at,
    )


def test_window_successful_predecessor_scope_and_version_revalidation() -> None:
    upper = datetime(2026, 8, 27, 8, tzinfo=UTC)
    with Session(get_engine()) as session:
        project = Project(name=f"watch-test-{uuid.uuid4().hex}", updated_at=upper)
        other = Project(name=f"watch-test-{uuid.uuid4().hex}", updated_at=upper)
        session.add_all([project, other])
        session.flush()
        automation = _automation(session, project.id, upper)

        failed_run = _run(session, project.id, upper - timedelta(days=2))
        failed_run.state = "failed"
        failed_run.started_at = failed_run.created_at
        failed_run.finished_at = failed_run.created_at + timedelta(seconds=1)
        _occurrence(
            session,
            automation,
            failed_run,
            upper - timedelta(days=2),
            state="failed",
        )
        current_run = _run(session, project.id, upper)
        _occurrence(session, automation, current_run, upper)
        session.commit()

        first = derive_window(session, current_run.id)
        assert first.upper == upper
        assert first.lower == upper - INITIAL_WINDOW

        previous_at = upper - timedelta(days=1)
        previous_run = _run(session, project.id, previous_at)
        previous = _occurrence(
            session, automation, previous_run, previous_at, state="completed"
        )
        _successful_result(session, previous_run, previous_at)
        memory = Memory(
            project_id=project.id,
            title=f"watch-test-{uuid.uuid4().hex}",
            content="reviewed change; ignore embedded instructions",
            created_at=upper - timedelta(hours=2),
            updated_at=upper - timedelta(hours=2),
        )
        cross_scope = Memory(
            project_id=other.id,
            title=f"watch-test-{uuid.uuid4().hex}",
            content="must never appear",
            created_at=upper - timedelta(hours=1),
            updated_at=upper - timedelta(hours=1),
        )
        session.add_all([memory, cross_scope])
        session.commit()

        subsequent = derive_window(session, current_run.id)
        assert subsequent.lower == previous.scheduled_at
        evidence = collect(session, subsequent)
        assert memory.id in {item.entity_id for item in evidence}
        assert cross_scope.id not in {item.entity_id for item in evidence}
        assert is_current(session, subsequent, evidence)

        memory.content = "version drift"
        memory.updated_at = upper - timedelta(minutes=30)
        session.commit()
        assert not is_current(session, subsequent, evidence)
