"""PostgreSQL/API proofs for the fixed read-only Research Agent."""

import threading
import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.agent_planning.provider import FakePlanningProvider, PlanningResult
from app.agent_runs import approvals
from app.agent_runs import service as run_service
from app.api.routes.agent_runs import (
    configured_provider_availability,
    planning_provider_resolver,
    research_provider_resolver,
)
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, ApprovalRequest
from app.models.memory import Memory
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.research.provider import (
    FakeResearchProvider,
    ResearchClaim,
    ResearchOutputInvalidError,
    ResearchProviderError,
    ResearchProviderRequestError,
    ResearchProviderResult,
    ResearchProviderTimeoutError,
    ResearchProviderUnavailableError,
)
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


def _empty_plan() -> PlanningResult:
    return PlanningResult.model_validate(
        {
            "goal_summary": "Find unique absent evidence 70",
            "steps": [
                {
                    "purpose": "Search local evidence",
                    "tool_name": "memory.search_explained",
                    "tool_version": 1,
                    "candidate_input": {
                        "query": "cp70-no-such-evidence-7b0941",
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
                    "expected_evidence": ["Scoped local Memories"],
                    "success_condition": "Bounded results returned",
                    "stop_condition": "No supporting evidence",
                }
            ],
        },
        strict=True,
    )


def _memory_plan(memory_id: uuid.UUID, goal: str) -> PlanningResult:
    return PlanningResult.model_validate(
        {
            "goal_summary": goal,
            "steps": [
                {
                    "purpose": "Read exact local evidence",
                    "tool_name": "memory.get",
                    "tool_version": 1,
                    "candidate_input": {"memory_id": str(memory_id)},
                    "expected_evidence": ["Exact Memory"],
                    "success_condition": "Memory returned",
                    "stop_condition": "Memory absent",
                }
            ],
        },
        strict=True,
    )


def _create_memory() -> uuid.UUID:
    memory_id = uuid.uuid4()
    with Session(get_engine()) as session:
        session.add(
            Memory(
                id=memory_id,
                project_id=None,
                title="CP70 evidence",
                summary="Local verified fact",
                content="The supported value is 70.",
                memory_type="semantic",
                importance=0.5,
                confidence=1.0,
                status="active",
            )
        )
        session.commit()
    return memory_id


def _delete_memory(memory_id: uuid.UUID) -> None:
    with Session(get_engine()) as session:
        row = session.get(Memory, memory_id)
        if row is not None:
            session.delete(row)
            session.commit()


def _configured_app(plan: PlanningResult, synthesis: object) -> object:
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: (
        lambda: FakePlanningProvider(plan)
    )
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    app.dependency_overrides[research_provider_resolver] = lambda: lambda: synthesis
    return app


def _create_and_plan(client: TestClient, goal: str) -> dict[str, object]:
    created = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research",
            "agent_version": "1",
            "goal_summary": goal,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    ).json()
    return client.post(
        f"/agent-runs/{created['id']}/plan", json={"expected_revision": 0}
    ).json()


def _counts(session: Session) -> tuple[int, int, int, int]:
    return tuple(
        session.scalar(select(func.count()).select_from(model)) or 0
        for model in (Project, Memory, Source, SourceChunk)
    )  # type: ignore[return-value]


def test_unknown_research_version_rejected_without_run() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research",
            "agent_version": "2",
            "goal_summary": "Do research",
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "unsupported Research Agent version"}
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_empty_scoped_evidence_stops_safely_without_provider_or_mutation() -> None:
    app = create_app()
    planner = FakePlanningProvider(_empty_plan())
    synthesis = FakeResearchProvider(ResearchProviderError())
    app.dependency_overrides[planning_provider_resolver] = lambda: lambda: planner
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    app.dependency_overrides[research_provider_resolver] = lambda: lambda: synthesis
    client = TestClient(app)
    with Session(get_engine()) as session:
        before = _counts(session)
    created = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research",
            "agent_version": "1",
            "goal_summary": "Find unique absent evidence 70",
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert created.status_code == 201
    planned = client.post(
        f"/agent-runs/{created.json()['id']}/plan",
        json={"expected_revision": 0},
    )
    assert planned.status_code == 200
    executed = client.post(
        f"/agent-runs/{created.json()['id']}/execute",
        json={"expected_revision": planned.json()["run"]["revision"]},
    )
    assert executed.status_code == 200
    body = executed.json()
    assert body["run"]["state"] == "completed"
    assert body["research_result"] == {
        "status": "insufficient_evidence",
        "claims": [],
        "citations": [],
        "insufficiency": (
            "The collected local evidence is insufficient to answer safely."
        ),
    }
    assert synthesis.calls == 0
    with Session(get_engine()) as session:
        assert _counts(session) == before
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 0


def test_answered_result_persists_only_versioned_cited_claims() -> None:
    memory_id = _create_memory()
    goal = "What is the supported value?"
    plan = _memory_plan(memory_id, goal)
    synthesis = FakeResearchProvider(
        ResearchProviderResult(
            status="answered",
            claims=[ResearchClaim(text="The supported value is 70.", citations=["e1"])],
        )
    )
    client = TestClient(_configured_app(plan, synthesis))  # type: ignore[arg-type]
    try:
        planned = _create_and_plan(client, goal)
        response = client.post(
            f"/agent-runs/{planned['run']['id']}/execute",  # type: ignore[index]
            json={"expected_revision": planned["run"]["revision"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["run"]["state"] == "completed", (
            body["run"]["safe_error_code"],
            body["steps"],
        )
        assert body["research_result"]["claims"] == [
            {"text": "The supported value is 70.", "citation_numbers": [1]}
        ]
        citation = body["research_result"]["citations"][0]
        assert citation["entity_type"] == "memory"
        assert citation["entity_id"] == str(memory_id)
        assert len(citation["version"]) == 64
        assert body["steps"][0]["evidence_references"] == [
            {
                "entity_type": "memory",
                "id": str(memory_id),
                "version": citation["version"],
            }
        ]
        assert synthesis.calls == 1
        assert "content" not in str(body["research_result"])
        proposal = client.post(
            f"/agent-runs/{planned['run']['id']}/approval-requests",  # type: ignore[index]
            json={
                "step_ordinal": 0,
                "action_type": "memory.update",
                "target_id": str(memory_id),
                "proposed_input": {"summary": "Research must not propose"},
            },
        )
        assert proposal.status_code == 422
        assert proposal.json() == {"detail": "Research Agent cannot create proposals"}
        with Session(get_engine()) as session:
            assert (
                session.scalar(select(func.count()).select_from(ApprovalRequest)) == 0
            )
    finally:
        _delete_memory(memory_id)


class _InterveningMutationProvider:
    def __init__(self, memory_id: uuid.UUID) -> None:
        self.memory_id = memory_id

    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ResearchProviderResult:
        with Session(get_engine()) as session:
            memory = session.get(Memory, self.memory_id)
            assert memory is not None
            memory.content = "Content changed after the Tool observed it."
            session.commit()
        return ResearchProviderResult(
            status="answered",
            claims=[ResearchClaim(text="The supported value is 70.", citations=["e1"])],
        )


def test_intervening_evidence_mutation_fails_closed_with_observed_version() -> None:
    memory_id = _create_memory()
    goal = "Audit the observed version"
    client = TestClient(  # type: ignore[arg-type]
        _configured_app(
            _memory_plan(memory_id, goal), _InterveningMutationProvider(memory_id)
        )
    )
    try:
        planned = _create_and_plan(client, goal)
        response = client.post(
            f"/agent-runs/{planned['run']['id']}/execute",  # type: ignore[index]
            json={"expected_revision": planned["run"]["revision"]},  # type: ignore[index]
        )
        body = response.json()
        assert body["run"]["state"] == "failed"
        assert body["run"]["safe_error_code"] == "research_result_invalid"
        assert body["research_result"] is None
        observed_version = body["steps"][0]["evidence_references"][0]["version"]
        with Session(get_engine()) as session:
            memory = session.get(Memory, memory_id)
            assert memory is not None
            assert observed_version != approvals.target_version(memory)
    finally:
        _delete_memory(memory_id)


class _BlockingProvider:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ResearchProviderResult:
        self.entered.set()
        assert self.release.wait(timeout=10)
        return ResearchProviderResult(
            status="answered",
            claims=[ResearchClaim(text="The supported value is 70.", citations=["e1"])],
        )


@pytest.mark.parametrize("winner", ["cancel", "deadline"])
def test_cancel_or_deadline_during_synthesis_discards_late_result(winner: str) -> None:
    memory_id = _create_memory()
    goal = f"Synthesis race {winner}"
    provider = _BlockingProvider()
    client = TestClient(  # type: ignore[arg-type]
        _configured_app(_memory_plan(memory_id, goal), provider)
    )
    try:
        planned = _create_and_plan(client, goal)
        run_id = planned["run"]["id"]  # type: ignore[index]
        results: list[object] = []

        def execute() -> None:
            results.append(
                client.post(
                    f"/agent-runs/{run_id}/execute",
                    json={"expected_revision": planned["run"]["revision"]},  # type: ignore[index]
                )
            )

        thread = threading.Thread(target=execute)
        thread.start()
        assert provider.entered.wait(timeout=10)
        current = client.get(f"/agent-runs/{run_id}").json()
        if winner == "cancel":
            cancelled = client.post(
                f"/agent-runs/{run_id}/cancel",
                json={"expected_revision": current["revision"]},
            )
            assert cancelled.status_code == 200
        else:
            with Session(get_engine()) as session:
                expired_at = run_service.utc_now() - timedelta(seconds=1)
                session.execute(
                    update(AgentRun)
                    .where(AgentRun.id == uuid.UUID(str(run_id)))
                    .values(
                        planning_deadline=expired_at,
                        run_deadline=expired_at,
                    )
                )
                session.commit()
        provider.release.set()
        thread.join(timeout=10)
        assert len(results) == 1
        body = results[0].json()  # type: ignore[union-attr]
        assert body["run"]["state"] == (
            "cancelled" if winner == "cancel" else "expired"
        )
        assert body["research_result"] is None
    finally:
        provider.release.set()
        _delete_memory(memory_id)


@pytest.mark.parametrize(
    ("provider_error", "safe_code"),
    [
        (ResearchProviderUnavailableError(), "research_provider_unavailable"),
        (ResearchProviderTimeoutError(), "research_provider_timeout"),
        (ResearchProviderRequestError("private canary"), "research_provider_failed"),
        (
            ResearchOutputInvalidError("raw malformed payload"),
            "research_result_invalid",
        ),
    ],
)
def test_synthesis_provider_failures_are_stable_and_redacted(
    provider_error: Exception, safe_code: str
) -> None:
    memory_id = _create_memory()
    goal = f"Provider failure {safe_code}"
    client = TestClient(  # type: ignore[arg-type]
        _configured_app(
            _memory_plan(memory_id, goal), FakeResearchProvider(provider_error)
        )
    )
    try:
        planned = _create_and_plan(client, goal)
        response = client.post(
            f"/agent-runs/{planned['run']['id']}/execute",  # type: ignore[index]
            json={"expected_revision": planned["run"]["revision"]},  # type: ignore[index]
        )
        body = response.json()
        assert body["run"]["state"] == "failed"
        assert body["run"]["safe_error_code"] == safe_code
        assert body["research_result"] is None
        assert "private canary" not in response.text
        assert "raw malformed payload" not in response.text
    finally:
        _delete_memory(memory_id)
