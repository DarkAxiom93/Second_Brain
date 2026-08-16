"""Real PostgreSQL transaction and API proofs for Checkpoint 66."""

import threading
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_planning.provider import FakePlanningProvider, PlanningResult
from app.agent_runs import executor
from app.agent_tools.schemas import MemorySearchExplainedOutput
from app.api.routes.agent_runs import (
    configured_provider_availability,
    planning_provider_resolver,
)
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
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


def _plan(step_count: int = 2) -> PlanningResult:
    steps = []
    for ordinal in range(step_count):
        steps.append(
            {
                "purpose": f"Read evidence {ordinal}",
                "tool_name": "memory.search_explained",
                "tool_version": 1,
                "candidate_input": {
                    "query": f"evidence {ordinal}",
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
                "expected_evidence": ["memory ids"],
                "success_condition": "bounded results returned",
                "stop_condition": "stop after read",
            }
        )
    return PlanningResult.model_validate(
        {"goal_summary": "Read evidence", "steps": steps}, strict=True
    )


def _ready_client(step_count: int = 2) -> tuple[TestClient, dict[str, object]]:
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: (
        lambda: FakePlanningProvider(_plan(step_count))
    )
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    client = TestClient(app)
    created = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research-agent",
            "agent_version": "1.0.0",
            "goal_summary": "Read evidence",
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    ).json()
    planned = client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    )
    assert planned.status_code == 200
    return client, planned.json()


def test_successful_steps_are_ordered_reserved_and_safely_projected() -> None:
    client, planned = _ready_client()
    response = client.post(
        f"/agent-runs/{planned['run']['id']}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["state"] == "completed"
    assert [step["ordinal"] for step in body["steps"]] == [0, 1]
    assert [step["status"] for step in body["steps"]] == ["succeeded", "succeeded"]
    assert all(step["invocation_status"] == "succeeded" for step in body["steps"])
    assert all(
        set(step)
        == {
            "ordinal",
            "purpose",
            "tool_name",
            "tool_version",
            "status",
            "invocation_status",
            "safe_result_summary",
            "evidence_references",
            "safe_error_code",
        }
        for step in body["steps"]
    )
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(AgentStep)
                .where(AgentStep.status == "succeeded")
            )
            == 2
        )


def test_only_one_execution_claims_and_run_lock_is_free_during_tool_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def blocking_dispatch(**kwargs: object) -> MemorySearchExplainedOutput:
        calls.append(str(kwargs["name"]))
        entered.set()
        assert release.wait(timeout=10)
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", blocking_dispatch)
    outcomes: list[object] = []

    def execute() -> None:
        outcomes.append(
            client.post(
                f"/agent-runs/{planned['run']['id']}/execute",
                json={"expected_revision": planned["run"]["revision"]},
            )
        )

    thread = threading.Thread(target=execute)
    thread.start()
    assert entered.wait(timeout=10)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None and run.state == "running"
        locked = session.scalar(
            select(AgentRun).where(AgentRun.id == run_id).with_for_update(nowait=True)
        )
        assert locked is not None
        session.rollback()
    loser = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert loser.status_code == 409
    release.set()
    thread.join(timeout=10)
    assert len(calls) == 1
    assert len(outcomes) == 1 and outcomes[0].status_code == 200  # type: ignore[union-attr]


def test_controlled_failure_stops_later_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    client, planned = _ready_client()
    calls = 0

    def failing_dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        raise RuntimeError("private canary")

    monkeypatch.setattr(executor, "dispatch_exact", failing_dispatch)
    response = client.post(
        f"/agent-runs/{planned['run']['id']}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["state"] == "failed"
    assert body["run"]["safe_error_code"] == "tool_controlled_failure"
    assert [step["status"] for step in body["steps"]] == ["failed", "pending"]
    assert calls == 1
    assert "private canary" not in response.text
