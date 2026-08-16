"""Real PostgreSQL transaction and API proofs for Checkpoint 65."""

import threading
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_planning.provider import (
    FakePlanningProvider,
    PlanningProviderRequestError,
    PlanningProviderUnavailableError,
    PlanningResult,
)
from app.api.routes.agent_runs import (
    configured_provider_availability,
    planning_provider_resolver,
)
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.repositories.agent_runtime import list_agent_events
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


def _result(goal: str = "Find safe evidence") -> PlanningResult:
    return PlanningResult.model_validate(
        {
            "goal_summary": goal,
            "steps": [
                {
                    "purpose": "Find matching reviewed memories",
                    "tool_name": "memory.search_explained",
                    "tool_version": 1,
                    "candidate_input": {
                        "query": "safe evidence",
                        "mode": "lexical",
                        "filters": {
                            "memory_type": None,
                            "status": None,
                            "importance_min": None,
                            "importance_max": None,
                            "confidence_min": None,
                            "confidence_max": None,
                            "event_time_from": None,
                            "event_time_to": None,
                            "created_at_from": None,
                            "created_at_to": None,
                        },
                        "pagination": {"limit": 5, "offset": 0},
                    },
                    "expected_evidence": ["Ordered matching memory identifiers"],
                    "success_condition": "A bounded result set is returned",
                    "stop_condition": "Stop after the one read",
                }
            ],
        },
        strict=True,
    )


def _client(provider: FakePlanningProvider) -> TestClient:
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: lambda: provider
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    return TestClient(app)


def _create(client: TestClient, key: str = "plan") -> dict[str, object]:
    response = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research-agent",
            "agent_version": "1.0.0",
            "goal_summary": "Find safe evidence",
        },
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def test_plan_persists_safe_projection_atomically_and_replays_without_work() -> None:
    provider = FakePlanningProvider(_result())
    client = _client(provider)
    created = _create(client)
    response = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["state"] == "ready"
    assert body["run"]["revision"] == 2
    assert body["goal_summary"] == "Find safe evidence"
    assert set(body["steps"][0]) == {
        "ordinal",
        "purpose",
        "tool_name",
        "tool_version",
        "normalized_input",
        "expected_evidence",
        "success_condition",
        "stop_condition",
    }
    assert client.get(f"/agent-runs/{created['id']}/plan").json() == body
    replay = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert replay.status_code == 200
    assert replay.json() == body
    assert provider.calls == 1
    with Session(get_engine()) as session:
        run_id = uuid.UUID(str(created["id"]))
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 1
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 0
        events = list_agent_events(session, run_id, limit=10)
        assert [
            (event.sequence, event.safe_metadata["new_state"]) for event in events
        ] == [
            (0, "created"),
            (1, "planning"),
            (2, "ready"),
        ]


def test_stale_registry_and_missing_plan_never_call_provider() -> None:
    provider = FakePlanningProvider(_result())
    client = _client(provider)
    created = _create(client, "guards")
    missing_plan = client.get(f"/agent-runs/{created['id']}/plan")
    assert missing_plan.status_code == 409
    assert missing_plan.json() == {"detail": "agent run plan not available"}
    stale = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 1}
    )
    assert stale.status_code == 409
    assert stale.json() == {"detail": "agent run revision conflict"}
    with Session(get_engine()) as session:
        run = session.get(AgentRun, uuid.UUID(str(created["id"])))
        assert run is not None
        run.registry_version = "legacy"
        session.commit()
    unsupported = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert unsupported.status_code == 409
    assert unsupported.json() == {"detail": "agent run registry version unsupported"}
    assert provider.calls == 0


def test_provider_failure_has_no_steps_and_safe_failed_state() -> None:
    provider = FakePlanningProvider(PlanningProviderRequestError("private canary"))
    client = _client(provider)
    created = _create(client, "failure")
    response = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "planning provider failed"}
    with Session(get_engine()) as session:
        run = session.get(AgentRun, uuid.UUID(str(created["id"])))
        assert run is not None
        assert (run.state, run.revision, run.safe_error_code) == (
            "failed",
            2,
            "planning_provider_failed",
        )
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 0
        assert "private canary" not in str(list_agent_events(session, run.id, limit=10))


def test_missing_provider_configuration_fails_only_after_committed_claim() -> None:
    app = create_app()

    def unavailable() -> object:
        raise PlanningProviderUnavailableError

    app.dependency_overrides[planning_provider_resolver] = lambda: unavailable
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    client = TestClient(app)
    created = _create(client, "unavailable")
    response = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "planning provider unavailable"}
    with Session(get_engine()) as session:
        run = session.get(AgentRun, uuid.UUID(str(created["id"])))
        assert run is not None
        assert run.safe_error_code == "planning_provider_unavailable"
        assert run.revision == 2


def test_only_one_concurrent_caller_reaches_provider() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider:
        calls = 0

        def plan(self, context: object) -> PlanningResult:
            self.calls += 1
            entered.set()
            assert release.wait(timeout=10)
            return _result()

    provider = BlockingProvider()
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: lambda: provider
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    client = TestClient(app)
    created = _create(client, "one-claimant")
    first: list[object] = []

    def planner() -> None:
        first.append(
            client.post(
                f"/agent-runs/{created['id']}/plan",
                json={"expected_revision": 0},
            )
        )

    thread = threading.Thread(target=planner)
    thread.start()
    assert entered.wait(timeout=10)
    second = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert second.status_code == 409
    assert provider.calls == 1
    release.set()
    thread.join(timeout=10)
    assert len(first) == 1 and first[0].status_code == 200  # type: ignore[union-attr]


def test_cancellation_during_provider_latency_wins_and_discards_result() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider:
        calls = 0

        def plan(self, context: object) -> PlanningResult:
            self.calls += 1
            entered.set()
            assert release.wait(timeout=10)
            return _result()

    provider = BlockingProvider()
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: lambda: provider
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    client = TestClient(app)
    created = _create(client, "cancel-latency")
    outcome: list[object] = []

    def planner() -> None:
        outcome.append(
            client.post(
                f"/agent-runs/{created['id']}/plan",
                json={"expected_revision": 0},
            )
        )

    thread = threading.Thread(target=planner)
    thread.start()
    assert entered.wait(timeout=10)
    cancelled = client.post(
        f"/agent-runs/{created['id']}/cancel", json={"expected_revision": 1}
    )
    assert cancelled.status_code == 200
    release.set()
    thread.join(timeout=10)
    assert len(outcome) == 1
    assert outcome[0].status_code == 409  # type: ignore[union-attr]
    with Session(get_engine()) as session:
        run = session.get(AgentRun, uuid.UUID(str(created["id"])))
        assert run is not None and run.state == "cancelled"
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 0


def test_openapi_has_exactly_the_agent_run_operations_through_checkpoint_66() -> None:
    schema = create_app().openapi()
    agent_operations = {
        (path, method)
        for path, item in schema["paths"].items()
        if path.startswith("/agent-runs")
        for method in item
    }
    assert agent_operations == {
        ("/agent-runs", "get"),
        ("/agent-runs", "post"),
        ("/agent-runs/{run_id}", "get"),
        ("/agent-runs/{run_id}/cancel", "post"),
        ("/agent-runs/{run_id}/plan", "get"),
        ("/agent-runs/{run_id}/plan", "post"),
        ("/agent-runs/{run_id}/execute", "post"),
        ("/agent-runs/{run_id}/execution", "get"),
    }
