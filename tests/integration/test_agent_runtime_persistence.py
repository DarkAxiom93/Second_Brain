"""PostgreSQL proofs for the Agent Runtime persistence foundation."""

import hashlib
import threading
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)
from app.models.project import Project
from app.repositories.agent_runtime import (
    AgentOwnershipError,
    append_agent_event,
    create_agent_run,
    get_agent_run_for_update,
    get_agent_run_in_project_scope,
    insert_agent_step,
    insert_approval_request,
    list_agent_events,
    list_agent_steps,
    reserve_tool_invocation,
)
from tests.integration.conftest import verify_connected_test_database


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _run(label: str, project_id: uuid.UUID | None = None) -> AgentRun:
    now = datetime.now(UTC)
    return AgentRun(
        project_id=project_id,
        agent_kind="test",
        agent_version="1",
        goal_summary=label,
        registry_version="1",
        policy_version="1",
        step_budget=2,
        tool_call_budget=2,
        retry_budget=0,
        planning_deadline=now + timedelta(minutes=1),
        run_deadline=now + timedelta(minutes=2),
        correlation_id=uuid.uuid4(),
        idempotency_key_hash=_hash("key-" + label),
        normalized_request_fingerprint=_hash("request-" + label),
    )


def _step(run_id: uuid.UUID, ordinal: int = 0) -> AgentStep:
    return AgentStep(
        run_id=run_id,
        ordinal=ordinal,
        purpose="read safe data",
        normalized_input={},
        expected_evidence=[],
        success_condition="evidence",
        stop_condition="bounded",
    )


@pytest.fixture(autouse=True)
def clean_agent_tables(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (AgentEvent, ApprovalRequest, ToolInvocation, AgentStep, AgentRun):
            session.execute(delete(model))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in (AgentEvent, ApprovalRequest, ToolInvocation, AgentStep, AgentRun):
            session.execute(delete(model))
        session.commit()


def test_outer_rollback_removes_all_five_entities_and_repositories_do_not_commit() -> (
    None
):
    with Session(get_engine()) as session:
        run = create_agent_run(session, _run("rollback"))
        step = insert_agent_step(session, _step(run.id))
        reserve_tool_invocation(
            session,
            ToolInvocation(
                run_id=run.id,
                step_id=step.id,
                attempt=0,
                tool_name="memory.read",
                tool_version="1",
                authority="read",
                validated_input_hash=_hash("input"),
                validated_input={},
                idempotency_key_hash=_hash("invocation"),
            ),
        )
        insert_approval_request(
            session,
            ApprovalRequest(
                run_id=run.id,
                step_id=step.id,
                action_type="proposal",
                target_type="memory",
                target_public_id=uuid.uuid4(),
                target_version="1",
                normalized_input={},
                proposal_hash=_hash("proposal"),
                preview="safe preview",
                evidence_references=[],
                risk_classification="low",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                execution_identity=uuid.uuid4(),
            ),
        )
        append_agent_event(
            session,
            run_id=run.id,
            event_type="created",
            safe_code="created",
            safe_message="created",
            metadata={},
            correlation_id=run.correlation_id,
            occurred_at=datetime.now(UTC),
        )
        session.rollback()
    with Session(get_engine()) as session:
        for model in (AgentRun, AgentStep, ToolInvocation, ApprovalRequest, AgentEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_uniqueness_and_foreign_key_fail_closed() -> None:
    with Session(get_engine()) as session:
        run = create_agent_run(session, _run("unique"))
        step = insert_agent_step(session, _step(run.id))
        session.commit()
        run_id, step_id = run.id, step.id
    with Session(get_engine()) as session:
        session.add(
            ToolInvocation(
                run_id=run_id,
                step_id=step_id,
                attempt=0,
                tool_name="x",
                tool_version="1",
                authority="read",
                validated_input_hash=_hash("a"),
                validated_input={},
                idempotency_key_hash=_hash("a"),
            )
        )
        session.commit()
    duplicates = [
        _run("unique"),
        _step(run_id),
        ToolInvocation(
            run_id=run_id,
            step_id=step_id,
            attempt=0,
            tool_name="other",
            tool_version="1",
            authority="read",
            validated_input_hash=_hash("attempt"),
            validated_input={},
            idempotency_key_hash=_hash("attempt"),
        ),
        ToolInvocation(
            run_id=run_id,
            step_id=step_id,
            attempt=1,
            tool_name="x",
            tool_version="1",
            authority="read",
            validated_input_hash=_hash("idempotency"),
            validated_input={},
            idempotency_key_hash=_hash("a"),
        ),
    ]
    for duplicate in duplicates:
        with Session(get_engine()) as session:
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 1
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 1
    with Session(get_engine()) as session:
        with pytest.raises(AgentOwnershipError):
            insert_agent_step(session, _step(uuid.uuid4()))
        session.rollback()


def test_approval_and_event_unique_identities() -> None:
    with Session(get_engine()) as session:
        run = create_agent_run(session, _run("identities"))
        step = insert_agent_step(session, _step(run.id))
        run_id, correlation = run.id, run.correlation_id
        execution = uuid.uuid4()
        kwargs = dict(
            run_id=run_id,
            step_id=step.id,
            action_type="proposal",
            target_type="memory",
            target_public_id=uuid.uuid4(),
            target_version="1",
            normalized_input={},
            proposal_hash=_hash("p"),
            preview="safe",
            evidence_references=[],
            risk_classification="low",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            execution_identity=execution,
        )
        insert_approval_request(session, ApprovalRequest(**kwargs))
        session.commit()
    with Session(get_engine()) as session:
        changed = dict(kwargs)
        changed["proposal_hash"] = _hash("other")
        session.add(ApprovalRequest(**changed))
        with pytest.raises(IntegrityError):
            session.commit()
    with Session(get_engine()) as session:
        run = get_agent_run_for_update(session, run_id)
        assert run is not None
        append_agent_event(
            session,
            run_id=run_id,
            event_type="fact",
            safe_code="ok",
            safe_message="ok",
            metadata={},
            correlation_id=correlation,
            occurred_at=datetime.now(UTC),
            event_idempotency_hash=_hash("event"),
        )
        session.commit()
    with Session(get_engine()) as session:
        session.add(
            AgentEvent(
                run_id=run_id,
                sequence=0,
                event_type="fact",
                event_version=1,
                safe_code="ok",
                safe_message="ok",
                safe_metadata={},
                correlation_id=correlation,
                occurred_at=datetime.now(UTC),
                event_idempotency_hash=_hash("other-event"),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    with Session(get_engine()) as session:
        session.add(
            AgentEvent(
                run_id=run_id,
                sequence=1,
                event_type="fact",
                event_version=1,
                safe_code="ok",
                safe_message="ok",
                safe_metadata={},
                correlation_id=correlation,
                occurred_at=datetime.now(UTC),
                event_idempotency_hash=_hash("event"),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 1
        assert session.scalar(select(func.count()).select_from(AgentEvent)) == 1


def test_project_and_null_scope_separation_and_deterministic_ordering() -> None:
    with Session(get_engine()) as session:
        a = Project(name="agent-scope-a-" + uuid.uuid4().hex)
        b = Project(name="agent-scope-b-" + uuid.uuid4().hex)
        session.add_all([a, b])
        session.flush()
        runs = [_run("scope-a", a.id), _run("scope-b", b.id), _run("scope-null")]
        for run in runs:
            create_agent_run(session, run)
        insert_agent_step(session, _step(runs[0].id, 1))
        insert_agent_step(session, _step(runs[0].id, 0))
        session.flush()
        assert get_agent_run_in_project_scope(session, runs[0].id, a.id) is not None
        assert get_agent_run_in_project_scope(session, runs[0].id, b.id) is None
        assert get_agent_run_in_project_scope(session, runs[0].id, None) is None
        assert get_agent_run_in_project_scope(session, runs[2].id, None) is not None
        assert [
            item.ordinal for item in list_agent_steps(session, runs[0].id, limit=10)
        ] == [0, 1]
        session.rollback()


def test_concurrent_event_append_is_unique_monotonic_and_run_lock_serializes() -> None:
    with Session(get_engine()) as session:
        run = create_agent_run(session, _run("concurrency"))
        session.commit()
        run_id = run.id
        correlation = run.correlation_id
    barrier = threading.Barrier(2)
    elapsed: list[float] = []

    def worker(delay: float) -> None:
        with Session(get_engine()) as session:
            barrier.wait()
            started = time.monotonic()
            locked = get_agent_run_for_update(session, run_id)
            assert locked
            time.sleep(delay)
            append_agent_event(
                session,
                run_id=run_id,
                event_type="fact",
                safe_code="ok",
                safe_message="ok",
                metadata={},
                correlation_id=correlation,
                occurred_at=datetime.now(UTC),
            )
            session.commit()
            elapsed.append(time.monotonic() - started)

    first = threading.Thread(target=worker, args=(0.3,))
    second = threading.Thread(target=worker, args=(0.0,))
    first.start()
    second.start()
    first.join()
    second.join()
    with Session(get_engine()) as session:
        assert [
            event.sequence for event in list_agent_events(session, run_id, limit=10)
        ] == [0, 1]
    assert max(elapsed) >= 0.25
