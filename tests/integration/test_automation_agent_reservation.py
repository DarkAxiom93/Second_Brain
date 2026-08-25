"""PostgreSQL/API proofs for the pre-Checkpoint 78 identity remediation."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_planning import service as planning_service
from app.agent_runs import service as run_service
from app.api.routes.agent_runs import (
    configured_provider_availability,
    planning_provider_resolver,
)
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.schemas.agent_run import AgentRunCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_runs(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(ToolInvocation))
        session.execute(delete(AgentStep))
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(ToolInvocation))
        session.execute(delete(AgentStep))
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.commit()


def _payload(kind: str, version: str) -> dict[str, object]:
    return {
        "project_id": None,
        "agent_kind": kind,
        "agent_version": version,
        "goal_summary": "Future scheduler-created work",
    }


def _create_internal(kind: str) -> uuid.UUID:
    request = AgentRunCreate.model_validate(_payload(kind, "1"))
    key = f"automation-occurrence:{kind}:{uuid.uuid4()}"
    with Session(get_engine()) as session:
        result = run_service.create_run(
            session,
            request,
            idempotency_key_hash=run_service.hash_idempotency_key(key),
            fingerprint=run_service.normalized_request_fingerprint(request),
        )
        session.commit()
        return result.run.id


@pytest.mark.parametrize("kind", ["daily_brief", "project_watch"])
@pytest.mark.parametrize("version", ["1", "999"])
def test_manual_creation_rejects_every_reserved_family_version(
    kind: str, version: str
) -> None:
    response = TestClient(create_app()).post(
        "/agent-runs",
        json=_payload(kind, version),
        headers={"Idempotency-Key": f"reserved-{kind}-{version}"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "agent definition unsupported"}
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


@pytest.mark.parametrize(
    ("kind", "version"),
    [
        ("research-agent", "1.0.0"),
        ("research", "1"),
        ("memory_curator", "1"),
    ],
)
def test_existing_manual_agent_creation_compatibility(kind: str, version: str) -> None:
    response = TestClient(create_app()).post(
        "/agent-runs",
        json=_payload(kind, version),
        headers={"Idempotency-Key": f"compatible-{kind}-{version}"},
    )
    assert response.status_code == 201


@pytest.mark.parametrize("kind", ["daily_brief", "project_watch"])
def test_internal_reserved_run_stays_created_when_planning_is_rejected(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _create_internal(kind)
    provider_calls = 0
    context_calls = 0

    def forbidden_provider() -> object:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("reserved identity resolved a planning provider")

    def forbidden_context(claim: object) -> object:
        nonlocal context_calls
        context_calls += 1
        raise AssertionError(f"reserved identity received inventory: {claim!r}")

    monkeypatch.setattr(planning_service, "build_context", forbidden_context)
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: forbidden_provider
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    response = TestClient(app).post(
        f"/agent-runs/{run_id}/plan", json={"expected_revision": 0}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "agent definition unsupported"}
    assert provider_calls == 0
    assert context_calls == 0
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert (run.state, run.revision) == ("created", 0)
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 0
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 0


@pytest.mark.parametrize("kind", ["daily_brief", "project_watch"])
def test_reserved_run_cannot_cross_execution_claim(kind: str) -> None:
    run_id = _create_internal(kind)
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        run.state = "ready"
        run.revision = 1
        session.commit()

    response = TestClient(create_app()).post(
        f"/agent-runs/{run_id}/execute", json={"expected_revision": 1}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "agent definition unsupported"}
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        assert (run.state, run.revision) == ("ready", 1)
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 0
