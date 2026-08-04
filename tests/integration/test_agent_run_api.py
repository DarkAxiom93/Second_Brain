"""Real PostgreSQL API and concurrency proofs for Checkpoint 63."""

import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_runs import service
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun
from app.models.project import Project
from app.repositories.agent_runtime import list_agent_events
from app.schemas.agent_run import AgentRunCreate, AgentRunState
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_runs(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.commit()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _payload(project_id: uuid.UUID | None = None) -> dict[str, object]:
    return {
        "project_id": None if project_id is None else str(project_id),
        "agent_kind": "research-agent",
        "agent_version": "1.0.0",
        "goal_summary": "Find safe evidence",
    }


def test_create_retrieve_replay_and_raw_key_is_not_persisted(
    client: TestClient,
) -> None:
    raw_key = "private key material"
    created = client.post(
        "/agent-runs", json=_payload(), headers={"Idempotency-Key": raw_key}
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body) == set(service.__dict__.get("__never_public__", ())) | {
        "id",
        "project_id",
        "agent_kind",
        "agent_version",
        "goal_summary",
        "registry_version",
        "policy_version",
        "state",
        "step_budget",
        "tool_call_budget",
        "retry_budget",
        "planning_deadline",
        "run_deadline",
        "revision",
        "safe_error_code",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    }
    assert body["registry_version"] == "unavailable"
    assert body["policy_version"] == "agent-run-api-v1"
    assert (body["step_budget"], body["tool_call_budget"], body["retry_budget"]) == (
        12,
        20,
        1,
    )
    replay = client.post(
        "/agent-runs", json=_payload(), headers={"Idempotency-Key": raw_key}
    )
    assert replay.status_code == 200
    assert replay.json() == body
    assert client.get(f"/agent-runs/{body['id']}").json() == body
    with Session(get_engine()) as session:
        run = session.get(AgentRun, uuid.UUID(body["id"]))
        assert run is not None
        assert raw_key not in run.idempotency_key_hash
        assert len(run.idempotency_key_hash) == 64
        events = list_agent_events(session, run.id, limit=10)
        assert len(events) == 1
        assert events[0].sequence == 0
        assert events[0].safe_metadata == {
            "previous_state": None,
            "new_state": "created",
            "resulting_revision": 0,
        }


def test_changed_payload_reuse_missing_project_and_header_validation(
    client: TestClient,
) -> None:
    headers = {"Idempotency-Key": "same"}
    assert (
        client.post("/agent-runs", json=_payload(), headers=headers).status_code == 201
    )
    changed = _payload()
    changed["goal_summary"] = "Changed"
    conflict = client.post("/agent-runs", json=changed, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "idempotency key already used with a different request"
    }
    missing = client.post(
        "/agent-runs",
        json=_payload(uuid.uuid4()),
        headers={"Idempotency-Key": "missing-project"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "project not found"}
    for key in (" leading", "trailing ", "bad\nkey", "x" * 129):
        assert (
            client.post(
                "/agent-runs", json=_payload(), headers={"Idempotency-Key": key}
            ).status_code
            == 422
        )


def test_list_scopes_order_pagination_and_cancel_contract(client: TestClient) -> None:
    with Session(get_engine()) as session:
        project_a = Project(name="c63-a-" + uuid.uuid4().hex)
        project_b = Project(name="c63-b-" + uuid.uuid4().hex)
        session.add_all([project_a, project_b])
        session.commit()
        a_id, b_id = project_a.id, project_b.id
    created = []
    for index, project_id in enumerate((a_id, b_id, None)):
        response = client.post(
            "/agent-runs",
            json=_payload(project_id),
            headers={"Idempotency-Key": f"scope-{index}"},
        )
        assert response.status_code == 201
        created.append(response.json())
    assert [item["id"] for item in client.get("/agent-runs?limit=2").json()] == [
        created[2]["id"],
        created[1]["id"],
    ]
    assert [
        item["id"] for item in client.get(f"/agent-runs?project_id={a_id}").json()
    ] == [created[0]["id"]]
    assert [
        item["id"] for item in client.get("/agent-runs?unassigned=true").json()
    ] == [created[2]["id"]]
    assert (
        client.get(f"/agent-runs?project_id={a_id}&unassigned=true").status_code == 422
    )

    cancelled = client.post(
        f"/agent-runs/{created[0]['id']}/cancel", json={"expected_revision": 0}
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    assert cancelled.json()["revision"] == 1
    repeated = client.post(
        f"/agent-runs/{created[0]['id']}/cancel", json={"expected_revision": 0}
    )
    assert repeated.status_code == 200
    assert repeated.json() == cancelled.json()
    with Session(get_engine()) as session:
        assert (
            len(list_agent_events(session, uuid.UUID(created[0]["id"]), limit=10)) == 2
        )


def test_transition_timestamps_expiry_and_outer_rollback() -> None:
    request = AgentRunCreate.model_validate(_payload())
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        result = service.create_run(
            session,
            request,
            idempotency_key_hash=service.hash_idempotency_key("rollback"),
            fingerprint=service.normalized_request_fingerprint(request),
            now=created_at,
        )
        run_id = result.run.id
        session.rollback()
    with Session(get_engine()) as session:
        assert session.get(AgentRun, run_id) is None
        assert session.scalar(select(func.count()).select_from(AgentEvent)) == 0

    with Session(get_engine()) as session:
        result = service.create_run(
            session,
            request,
            idempotency_key_hash=service.hash_idempotency_key("expiry"),
            fingerprint=service.normalized_request_fingerprint(request),
            now=created_at,
        )
        session.commit()
        run_id = result.run.id
    with Session(get_engine()) as session:
        with pytest.raises(service.AgentRunTransitionConflictError):
            service.transition_run(
                session,
                run_id,
                expected_state=AgentRunState.CREATED,
                expected_revision=0,
                new_state=AgentRunState.EXPIRED,
                now=created_at + timedelta(minutes=10) - timedelta(microseconds=1),
            )
        session.rollback()
    boundary = created_at + timedelta(minutes=10)
    with Session(get_engine()) as session:
        run = service.transition_run(
            session,
            run_id,
            expected_state=AgentRunState.CREATED,
            expected_revision=0,
            new_state=AgentRunState.EXPIRED,
            now=boundary,
        )
        session.commit()
        assert run.revision == 1
        assert run.finished_at == boundary


def test_concurrent_exact_create_produces_one_run_and_event() -> None:
    barrier = threading.Barrier(2)
    outcomes: list[bool] = []
    request = AgentRunCreate.model_validate(_payload())
    key_hash = service.hash_idempotency_key("concurrent")
    fingerprint = service.normalized_request_fingerprint(request)

    def worker() -> None:
        with Session(get_engine()) as session:
            barrier.wait()
            try:
                result = service.create_run(
                    session,
                    request,
                    idempotency_key_hash=key_hash,
                    fingerprint=fingerprint,
                )
                session.commit()
            except Exception as error:
                from sqlalchemy.exc import IntegrityError

                if not isinstance(error, IntegrityError):
                    raise
                session.rollback()
                resolved = service.resolve_create_replay(
                    session,
                    idempotency_key_hash=key_hash,
                    fingerprint=fingerprint,
                )
                assert resolved is not None
                result = resolved
            outcomes.append(result.created)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == [False, True]
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        assert session.scalar(select(func.count()).select_from(AgentEvent)) == 1
