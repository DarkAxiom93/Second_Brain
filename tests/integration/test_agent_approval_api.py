"""PostgreSQL API proofs for immutable Approval Requests."""

import hashlib
import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.agent_runs import approvals, service
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)
from app.models.memory import Memory
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database

CREATED_MEMORY_IDS: set[uuid.UUID] = set()
CREATED_PROJECT_IDS: set[uuid.UUID] = set()


@pytest.fixture(autouse=True)
def clean_agent_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        if CREATED_MEMORY_IDS:
            session.execute(delete(Memory).where(Memory.id.in_(CREATED_MEMORY_IDS)))
        if CREATED_PROJECT_IDS:
            session.execute(delete(Project).where(Project.id.in_(CREATED_PROJECT_IDS)))
        session.commit()
    CREATED_MEMORY_IDS.clear()
    CREATED_PROJECT_IDS.clear()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        if CREATED_MEMORY_IDS:
            session.execute(delete(Memory).where(Memory.id.in_(CREATED_MEMORY_IDS)))
        if CREATED_PROJECT_IDS:
            session.execute(delete(Project).where(Project.id.in_(CREATED_PROJECT_IDS)))
        session.commit()
    CREATED_MEMORY_IDS.clear()
    CREATED_PROJECT_IDS.clear()


def _fixture(*, project: bool = True) -> tuple[TestClient, uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        project_row = Project(name=f"CP68 {uuid.uuid4()}") if project else None
        if project_row is not None:
            session.add(project_row)
            session.flush()
        memory = Memory(
            project_id=None if project_row is None else project_row.id,
            content="Original target",
            memory_type="semantic",
            importance=0.5,
            confidence=1.0,
            status="active",
        )
        session.add(memory)
        session.flush()
        run = AgentRun(
            project_id=memory.project_id,
            agent_kind="research-agent",
            agent_version="1.0.0",
            goal_summary="Propose a bounded update",
            registry_version="agent-tools-v1",
            policy_version=service.POLICY_VERSION,
            state="ready",
            step_budget=12,
            tool_call_budget=20,
            retry_budget=1,
            planning_deadline=now + timedelta(minutes=10),
            run_deadline=now + timedelta(minutes=10),
            revision=0,
            correlation_id=uuid.uuid4(),
            idempotency_key_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            normalized_request_fingerprint=hashlib.sha256(
                uuid.uuid4().bytes
            ).hexdigest(),
            created_at=now,
            updated_at=now,
        )
        session.add(run)
        session.flush()
        session.add(
            AgentStep(
                run_id=run.id,
                ordinal=0,
                purpose="Propose update",
                tool_name=None,
                tool_version=None,
                normalized_input={},
                expected_evidence=[],
                success_condition="proposal created",
                stop_condition="human review",
                status="pending",
                created_at=now,
            )
        )
        session.commit()
        CREATED_MEMORY_IDS.add(memory.id)
        if project_row is not None:
            CREATED_PROJECT_IDS.add(project_row.id)
        return TestClient(create_app()), run.id, memory.id


def _create(client: TestClient, run_id: uuid.UUID, memory_id: uuid.UUID):
    return client.post(
        f"/agent-runs/{run_id}/approval-requests",
        json={
            "step_ordinal": 0,
            "action_type": "memory.update",
            "target_id": str(memory_id),
            "proposed_input": {"title": "Human review only"},
        },
    )


def _memory_snapshot(memory_id: uuid.UUID) -> dict[str, object]:
    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        return {
            column.name: getattr(memory, column.name)
            for column in Memory.__table__.columns
        }


def _run_snapshot(run_id: uuid.UUID) -> dict[str, object]:
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        return {
            column.name: getattr(run, column.name)
            for column in AgentRun.__table__.columns
        }


def _approval_counts(run_id: uuid.UUID) -> tuple[int, int, int]:
    with Session(get_engine()) as session:
        approvals_count = session.scalar(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(ApprovalRequest.run_id == run_id)
        )
        events_count = session.scalar(
            select(func.count())
            .select_from(AgentEvent)
            .where(AgentEvent.run_id == run_id)
        )
        invocations_count = session.scalar(
            select(func.count())
            .select_from(ToolInvocation)
            .where(ToolInvocation.run_id == run_id)
        )
        assert approvals_count is not None
        assert events_count is not None
        assert invocations_count is not None
        return approvals_count, events_count, invocations_count


def test_create_replay_projection_and_review_never_mutate_target() -> None:
    client, run_id, memory_id = _fixture()
    before_run = _run_snapshot(run_id)
    created = _create(client, run_id, memory_id)
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {
        "id",
        "run_id",
        "step_ordinal",
        "action_type",
        "target_type",
        "target_id",
        "target_version",
        "proposed_input",
        "preview",
        "evidence_references",
        "risk_classification",
        "status",
        "created_at",
        "expires_at",
        "reviewed_at",
    }
    replay = _create(client, run_id, memory_id)
    assert replay.status_code == 200
    assert replay.json() == body
    reviewed = client.post(
        f"/approval-requests/{body['id']}/review", json={"decision": "approve"}
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    repeated = client.post(
        f"/approval-requests/{body['id']}/review", json={"decision": "approve"}
    )
    assert repeated.status_code == 200
    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None and memory.title is None
        assert approvals.target_version(memory) == body["target_version"]
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 1
        events = session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id)
        ).all()
        assert [event.sequence for event in events] == [0, 1]
        assert all(
            not set(event.safe_metadata)
            & {
                "content",
                "normalized_input",
                "proposal_hash",
                "execution_identity",
                "exception",
            }
            for event in events
        )
    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        assert approvals.target_version(memory) == body["target_version"]
    assert _run_snapshot(run_id) == before_run


def test_changed_target_becomes_superseded_and_opposite_decision_conflicts() -> None:
    client, run_id, memory_id = _fixture(project=False)
    body = _create(client, run_id, memory_id).json()
    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        memory.content = "Changed after proposal"
        session.commit()
    stale = client.post(
        f"/approval-requests/{body['id']}/review", json={"decision": "approve"}
    )
    assert stale.status_code == 409
    fetched = client.get(f"/approval-requests/{body['id']}")
    assert fetched.json()["status"] == "superseded"
    rejected = client.post(
        f"/approval-requests/{body['id']}/review", json={"decision": "reject"}
    )
    assert rejected.status_code == 409


def test_scope_matrix_changed_payload_and_reject_replay_are_exact() -> None:
    client_a, run_a, memory_a = _fixture(project=True)
    _client_b, _run_b, memory_b = _fixture(project=True)
    _client_u, _run_u, memory_u = _fixture(project=False)
    before_a = _memory_snapshot(memory_a)

    assert _create(client_a, run_a, memory_b).status_code == 404
    assert _create(client_a, run_a, memory_u).status_code == 404
    first = _create(client_a, run_a, memory_a)
    assert first.status_code == 201
    changed = client_a.post(
        f"/agent-runs/{run_a}/approval-requests",
        json={
            "step_ordinal": 0,
            "action_type": "memory.update",
            "target_id": str(memory_a),
            "proposed_input": {"title": "A distinct valid proposal"},
        },
    )
    assert changed.status_code == 201
    rejected = client_a.post(
        f"/approval-requests/{first.json()['id']}/review",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200
    before_replay = rejected.json()
    counts = _approval_counts(run_a)
    replay = client_a.post(
        f"/approval-requests/{first.json()['id']}/review",
        json={"decision": "reject"},
    )
    assert replay.status_code == 200
    assert replay.json() == before_replay
    assert _approval_counts(run_a) == counts
    assert (
        client_a.post(
            f"/approval-requests/{first.json()['id']}/review",
            json={"decision": "approve"},
        ).status_code
        == 409
    )
    assert _memory_snapshot(memory_a) == before_a
    assert _approval_counts(run_a)[2] == 0

    client_unassigned, run_unassigned, _own_unassigned = _fixture(project=False)
    assert _create(client_unassigned, run_unassigned, memory_a).status_code == 404


def test_expiry_is_permanent_write_safe_and_does_not_renew() -> None:
    client, run_id, memory_id = _fixture()
    before_memory = _memory_snapshot(memory_id)
    approval_id = uuid.UUID(_create(client, run_id, memory_id).json()["id"])
    now = datetime.now(UTC)
    expired_at = now - timedelta(hours=1)
    with Session(get_engine()) as session:
        session.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == approval_id)
            .values(created_at=now - timedelta(days=2), expires_at=expired_at)
        )
        session.commit()
    response = client.post(
        f"/approval-requests/{approval_id}/review", json={"decision": "approve"}
    )
    assert response.status_code == 409
    fetched = client.get(f"/approval-requests/{approval_id}").json()
    assert fetched["status"] == "expired"
    assert datetime.fromisoformat(fetched["expires_at"]) == expired_at
    counts = _approval_counts(run_id)
    assert (
        client.post(
            f"/approval-requests/{approval_id}/review", json={"decision": "reject"}
        ).status_code
        == 409
    )
    assert _approval_counts(run_id) == counts
    assert _memory_snapshot(memory_id) == before_memory


def test_missing_and_moved_targets_fail_closed_without_mutation() -> None:
    client, run_id, memory_id = _fixture()
    approval_id = _create(client, run_id, memory_id).json()["id"]
    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        before = {
            column.name: getattr(memory, column.name)
            for column in Memory.__table__.columns
        }
        memory.project_id = None
        session.commit()
    moved = _memory_snapshot(memory_id)
    assert moved != before
    assert (
        client.post(
            f"/approval-requests/{approval_id}/review", json={"decision": "approve"}
        ).status_code
        == 409
    )
    assert client.get(f"/approval-requests/{approval_id}").json()["status"] == (
        "superseded"
    )
    assert _memory_snapshot(memory_id) == moved

    missing_client, _missing_run_id, missing_memory_id = _fixture(project=False)
    missing_approval_id = _create(
        missing_client, _missing_run_id, missing_memory_id
    ).json()["id"]
    with Session(get_engine()) as session:
        memory = session.get(Memory, missing_memory_id)
        assert memory is not None
        session.delete(memory)
        session.commit()
    response = missing_client.post(
        f"/approval-requests/{missing_approval_id}/review",
        json={"decision": "approve"},
    )
    assert response.status_code == 409
    assert (
        missing_client.get(f"/approval-requests/{missing_approval_id}").json()["status"]
        == "superseded"
    )


def test_concurrent_duplicate_creation_has_one_row_event_and_frozen_fields() -> None:
    _client, run_id, memory_id = _fixture()
    barrier = threading.Barrier(2)
    results: list[tuple[uuid.UUID, datetime, uuid.UUID]] = []
    errors: list[BaseException] = []

    def create() -> None:
        try:
            with Session(get_engine()) as session:
                barrier.wait()
                row, _created = approvals.create_proposal(
                    session,
                    run_id=run_id,
                    step_ordinal=0,
                    action_type="memory.update",
                    target_id=memory_id,
                    proposed_input={"title": "Human review only"},
                )
                session.commit()
                session.refresh(row)
                results.append((row.id, row.expires_at, row.execution_identity))
        except BaseException as exc:  # pragma: no cover - diagnostic capture
            errors.append(exc)

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert len(results) == 2 and results[0] == results[1]
    assert _approval_counts(run_id) == (1, 1, 0)


def test_concurrent_opposite_review_has_one_winner_and_one_event() -> None:
    client, run_id, memory_id = _fixture()
    before_memory = _memory_snapshot(memory_id)
    approval_id = uuid.UUID(_create(client, run_id, memory_id).json()["id"])
    barrier = threading.Barrier(2)
    winners: list[str] = []
    conflicts: list[str] = []

    def review(decision: str) -> None:
        with Session(get_engine()) as session:
            barrier.wait()
            try:
                row, _changed = approvals.review_proposal(
                    session,
                    approval_id=approval_id,
                    decision=decision,  # type: ignore[arg-type]
                )
                session.commit()
                winners.append(row.status)
            except approvals.ReviewConflictError:
                session.rollback()
                conflicts.append(decision)

    threads = [
        threading.Thread(target=review, args=(decision,))
        for decision in ("approve", "reject")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(winners) == len(conflicts) == 1
    with Session(get_engine()) as session:
        row = session.get(ApprovalRequest, approval_id)
        assert row is not None and row.status == winners[0]
        review_events = session.scalars(
            select(AgentEvent).where(
                AgentEvent.run_id == run_id,
                AgentEvent.event_type.in_(("approval_approved", "approval_rejected")),
            )
        ).all()
        assert len(review_events) == 1
    assert _memory_snapshot(memory_id) == before_memory
    assert _approval_counts(run_id) == (1, 2, 0)


def test_create_and_review_failures_roll_back_every_partial_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client, run_id, memory_id = _fixture()
    original_append = approvals.repository.append_agent_event

    def fail_event(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(approvals.repository, "append_agent_event", fail_event)
    with Session(get_engine()) as session:
        with pytest.raises(RuntimeError, match="injected event failure"):
            approvals.create_proposal(
                session,
                run_id=run_id,
                step_ordinal=0,
                action_type="memory.update",
                target_id=memory_id,
                proposed_input={"title": "Rollback"},
            )
        session.rollback()
    assert _approval_counts(run_id) == (0, 0, 0)

    monkeypatch.setattr(approvals.repository, "append_agent_event", original_append)
    client = TestClient(create_app())
    approval_id = uuid.UUID(_create(client, run_id, memory_id).json()["id"])
    monkeypatch.setattr(approvals.repository, "append_agent_event", fail_event)
    with Session(get_engine()) as session:
        with pytest.raises(RuntimeError, match="injected event failure"):
            approvals.review_proposal(
                session, approval_id=approval_id, decision="approve"
            )
        session.rollback()
    with Session(get_engine()) as session:
        row = session.get(ApprovalRequest, approval_id)
        assert row is not None
        assert (row.status, row.reviewed_at, row.reviewer_metadata) == (
            "pending",
            None,
            None,
        )
    assert _approval_counts(run_id) == (1, 1, 0)


def test_evidence_is_only_from_the_exact_persisted_run_step() -> None:
    client, run_id, memory_id = _fixture()
    _other_client, other_run_id, other_memory_id = _fixture()
    wanted = uuid.uuid4()
    wrong_step = uuid.uuid4()
    wrong_run = uuid.uuid4()
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        step = session.scalar(
            select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.ordinal == 0)
        )
        other_step = session.scalar(
            select(AgentStep).where(
                AgentStep.run_id == other_run_id, AgentStep.ordinal == 0
            )
        )
        assert step is not None and other_step is not None
        second_step = AgentStep(
            run_id=run_id,
            ordinal=1,
            purpose="Other step",
            normalized_input={},
            expected_evidence=[],
            success_condition="done",
            stop_condition="stop",
            status="succeeded",
            created_at=now,
        )
        session.add(second_step)
        session.flush()
        for owner_run, owner_step, evidence_id in (
            (run_id, step.id, wanted),
            (run_id, second_step.id, wrong_step),
            (other_run_id, other_step.id, wrong_run),
        ):
            session.add(
                ToolInvocation(
                    run_id=owner_run,
                    step_id=owner_step,
                    attempt=0,
                    tool_name="memory.get",
                    tool_version="1",
                    authority="read",
                    validated_input_hash="a" * 64,
                    validated_input={"memory_id": str(other_memory_id)},
                    idempotency_key_hash=hashlib.sha256(
                        f"{owner_run}:{owner_step}".encode()
                    ).hexdigest(),
                    status="succeeded",
                    safe_result_summary="memory read succeeded",
                    evidence_references=[
                        {"entity_type": "memory", "id": str(evidence_id)}
                    ],
                    reserved_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )
        session.commit()
    response = _create(client, run_id, memory_id)
    assert response.status_code == 201
    assert response.json()["evidence_references"] == [
        {"entity_type": "memory", "id": str(wanted)}
    ]
    assert (
        client.post(
            f"/agent-runs/{run_id}/approval-requests",
            json={
                "step_ordinal": 0,
                "action_type": "memory.update",
                "target_id": str(memory_id),
                "proposed_input": {"title": "Another"},
                "evidence_references": [
                    {"entity_type": "memory", "id": str(uuid.uuid4())}
                ],
            },
        ).status_code
        == 422
    )
