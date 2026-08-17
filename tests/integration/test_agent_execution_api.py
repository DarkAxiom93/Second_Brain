"""Real PostgreSQL transaction and API proofs for Checkpoint 66."""

import threading
import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.agent_planning.provider import FakePlanningProvider, PlanningResult
from app.agent_runs import executor, faults, recovery, service
from app.agent_tools.registry import AGENT_TOOL_REGISTRY
from app.agent_tools.schemas import MemorySearchExplainedOutput
from app.api.routes.agent_runs import (
    configured_provider_availability,
    planning_provider_resolver,
)
from app.db.session import get_engine
from app.embeddings import ProviderRequestError
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.models.memory import Memory
from app.models.project import Project
from app.models.source import Source
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


def _ready_client(
    step_count: int = 2,
    *,
    project_id: str | None = None,
    raise_server_exceptions: bool = True,
) -> tuple[TestClient, dict[str, object]]:
    app = create_app()
    app.dependency_overrides[planning_provider_resolver] = lambda: (
        lambda: FakePlanningProvider(_plan(step_count))
    )
    app.dependency_overrides[configured_provider_availability] = lambda: lambda: False
    client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
    created = client.post(
        "/agent-runs",
        json={
            "project_id": project_id,
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


def _claim_for_recovery(run_id: uuid.UUID) -> executor.ExecutionClaim | None:
    with Session(get_engine()) as session:
        claim = recovery.prepare_one(session, run_id)
        session.commit()
        return claim


def _drive_claim(
    claim: executor.ExecutionClaim,
    dispatch_calls: list[uuid.UUID | None] | None = None,
) -> None:
    while True:
        with Session(get_engine()) as session:
            reserved = executor.reserve_next(session, claim, provider_available=False)
            session.commit()
            if reserved is None:
                break
            step, invocation, timeout = reserved
            if dispatch_calls is not None:
                dispatch_calls.append(claim.project_scope)
            output, error = executor.call_reserved_tool(
                session,
                claim,
                step,
                invocation,
                timeout,
                lambda: None,  # type: ignore[arg-type,return-value]
            )
            session.rollback()
            keep_going = executor.finalize_invocation(
                session,
                claim,
                step_id=step.id,
                invocation_id=invocation.id,
                output=output,
                safe_error_code=error,
            )
            session.commit()
            if not keep_going:
                break
    with Session(get_engine()) as session:
        executor.complete_run(session, claim)
        session.commit()


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


def test_transient_read_retries_once_and_terminal_replay_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    calls = 0

    def transient_dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderRequestError
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", transient_dispatch)
    url = f"/agent-runs/{planned['run']['id']}/execute"
    payload = {"expected_revision": planned["run"]["revision"]}
    first = client.post(url, json=payload)
    assert first.status_code == 200
    assert first.json()["run"]["state"] == "completed"
    assert calls == 2
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        durable_attempts = list(
            session.scalars(
                select(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
                .order_by(ToolInvocation.attempt)
            )
        )
        before_events = session.scalar(
            select(func.count())
            .select_from(AgentEvent)
            .where(AgentEvent.run_id == run_id)
        )
        before_run = session.get(AgentRun, run_id)
        assert before_run is not None
        before_state = (before_run.state, before_run.revision, before_run.updated_at)
    assert [item.attempt for item in durable_attempts] == [0, 1]
    assert [item.status for item in durable_attempts] == ["failed", "succeeded"]
    assert durable_attempts[0].id != durable_attempts[1].id
    assert (
        durable_attempts[0].idempotency_key_hash
        != durable_attempts[1].idempotency_key_hash
    )
    attempt0_snapshot = (
        durable_attempts[0].status,
        durable_attempts[0].safe_error_code,
        durable_attempts[0].finished_at,
    )
    replay = client.post(url, json=payload)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert calls == 2
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AgentEvent)
                .where(AgentEvent.run_id == run_id)
            )
            == before_events
        )
        after_run = session.get(AgentRun, run_id)
        assert after_run is not None
        assert (
            after_run.state,
            after_run.revision,
            after_run.updated_at,
        ) == before_state
        after_attempts = list(
            session.scalars(
                select(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
                .order_by(ToolInvocation.attempt)
            )
        )
        assert len(after_attempts) == 2
        assert (
            after_attempts[0].status,
            after_attempts[0].safe_error_code,
            after_attempts[0].finished_at,
        ) == attempt0_snapshot
    changed = client.post(
        url, json={"expected_revision": int(payload["expected_revision"]) + 1}
    )
    assert changed.status_code == 409


def test_second_transient_failure_never_creates_attempt_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    calls = 0

    def failing_dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        raise ProviderRequestError

    monkeypatch.setattr(executor, "dispatch_exact", failing_dispatch)
    response = client.post(
        f"/agent-runs/{planned['run']['id']}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 200
    assert response.json()["run"]["state"] == "failed"
    assert calls == 2
    with Session(get_engine()) as session:
        assert list(
            session.scalars(
                select(ToolInvocation.attempt).order_by(ToolInvocation.attempt)
            )
        ) == [0, 1]


def test_concurrent_retry_reservation_has_one_attempt_one() -> None:
    _, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        claim = executor.claim_execution(
            session, run_id, expected_revision=int(planned["run"]["revision"])
        )
        assert claim is not None
        session.commit()
        step, invocation, _ = executor.reserve_next(
            session, claim, provider_available=False
        ) or pytest.fail("reservation expected")
        session.commit()
        assert executor.finalize_invocation(
            session,
            claim,
            step_id=step.id,
            invocation_id=invocation.id,
            output=None,
            safe_error_code="tool_provider_failed",
        )
        session.commit()

    outcomes: list[str] = []

    def reserve_retry() -> None:
        with Session(get_engine()) as session:
            try:
                reserved = executor.reserve_next(
                    session, claim, provider_available=False
                )
                session.commit()
                outcomes.append("reserved" if reserved is not None else "none")
            except executor.ExecutionPlanInvalidError:
                session.rollback()
                outcomes.append("conflict")

    threads = [threading.Thread(target=reserve_retry) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ["conflict", "reserved"]
    with Session(get_engine()) as session:
        assert list(
            session.scalars(
                select(ToolInvocation.attempt)
                .where(ToolInvocation.run_id == run_id)
                .order_by(ToolInvocation.attempt)
            )
        ) == [0, 1]


@pytest.mark.parametrize(
    ("step_count", "tool_budget", "failure_call"), [(1, 1, 1), (5, 20, 5)]
)
def test_retry_counts_against_total_and_per_tool_budgets(
    monkeypatch: pytest.MonkeyPatch,
    step_count: int,
    tool_budget: int,
    failure_call: int,
) -> None:
    client, planned = _ready_client(step_count=step_count)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        run.tool_call_budget = tool_budget
        session.commit()
    calls = 0

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise ProviderRequestError
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    response = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 200
    assert response.json()["run"]["state"] == "failed"
    assert calls == failure_call
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
            )
            == failure_call
        )


def test_cancel_before_reservation_is_idempotent_and_write_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    calls = 0

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    payload = {"expected_revision": planned["run"]["revision"]}
    cancelled = client.post(f"/agent-runs/{run_id}/cancel", json=payload)
    assert cancelled.status_code == 200
    with Session(get_engine()) as session:
        before = session.scalar(
            select(func.count())
            .select_from(AgentEvent)
            .where(AgentEvent.run_id == run_id)
        )
    repeated = client.post(f"/agent-runs/{run_id}/cancel", json=payload)
    execute = client.post(f"/agent-runs/{run_id}/execute", json=payload)
    assert repeated.json() == cancelled.json()
    assert execute.status_code == 409
    assert calls == 0
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AgentEvent)
                .where(AgentEvent.run_id == run_id)
            )
            == before
        )
        step = session.scalar(select(AgentStep).where(AgentStep.run_id == run_id))
        assert step is not None and step.status == "cancelled"


def test_cancellation_during_tool_latency_discards_late_result_and_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=2)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    entered, release = threading.Event(), threading.Event()

    calls = 0

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        if calls == 1:
            return MemorySearchExplainedOutput(results=())
        entered.set()
        assert release.wait(timeout=10)
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    outcome: list[object] = []
    thread = threading.Thread(
        target=lambda: outcome.append(
            client.post(
                f"/agent-runs/{run_id}/execute",
                json={"expected_revision": planned["run"]["revision"]},
            )
        )
    )
    thread.start()
    assert entered.wait(timeout=10)
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        revision = run.revision
    cancelled = client.post(
        f"/agent-runs/{run_id}/cancel", json={"expected_revision": revision}
    )
    assert cancelled.status_code == 200
    release.set()
    thread.join(timeout=10)
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        steps = list(
            session.scalars(select(AgentStep).where(AgentStep.run_id == run_id))
        )
        assert run is not None and run.state == "cancelled"
        invocations = list(
            session.scalars(
                select(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
                .order_by(ToolInvocation.reserved_at)
            )
        )
        assert [step.status for step in steps] == ["succeeded", "cancelled"]
        assert [item.status for item in invocations] == ["succeeded", "discarded"]
        assert invocations[1].safe_result_summary is None
        assert invocations[1].evidence_references == []


def test_cancellation_after_reservation_before_tool_call_discards_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    reserved, release = threading.Event(), threading.Event()
    calls = 0

    def hook(point: faults.FaultPoint) -> None:
        if point == faults.FaultPoint.BEFORE_TOOL_CALL:
            reserved.set()
            assert release.wait(timeout=10)

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(faults, "fire", hook)
    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    thread = threading.Thread(
        target=lambda: client.post(
            f"/agent-runs/{run_id}/execute",
            json={"expected_revision": planned["run"]["revision"]},
        )
    )
    thread.start()
    assert reserved.wait(timeout=10)
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        revision = run.revision
        invocation = session.scalar(
            select(ToolInvocation).where(ToolInvocation.run_id == run_id)
        )
        assert invocation is not None and invocation.status == "running"
    assert (
        client.post(
            f"/agent-runs/{run_id}/cancel", json={"expected_revision": revision}
        ).status_code
        == 200
    )
    release.set()
    thread.join(timeout=10)
    assert calls == 1
    with Session(get_engine()) as session:
        invocation = session.scalar(
            select(ToolInvocation).where(ToolInvocation.run_id == run_id)
        )
        assert invocation is not None and invocation.status == "discarded"
        assert invocation.safe_result_summary is None


def test_completion_first_rejects_later_cancellation() -> None:
    client, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    completed = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert completed.json()["run"]["state"] == "completed"
    cancelled = client.post(
        f"/agent-runs/{run_id}/cancel",
        json={"expected_revision": completed.json()["run"]["revision"]},
    )
    assert cancelled.status_code == 409


def test_expiration_before_call_and_during_latency_rejects_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None
        past = service.utc_now() - timedelta(seconds=1)
        run.planning_deadline = past
        run.run_deadline = past
        session.commit()
    monkeypatch.setattr(
        executor,
        "dispatch_exact",
        lambda **_: (_ for _ in ()).throw(AssertionError("must not call")),
    )
    expired = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert expired.status_code == 200 and expired.json()["run"]["state"] == "expired"
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
            )
            == 0
        )

    monkeypatch.undo()
    client2, planned2 = _ready_client(step_count=1)
    run_id2 = uuid.UUID(str(planned2["run"]["id"]))

    def late_dispatch(**_: object) -> MemorySearchExplainedOutput:
        with Session(get_engine()) as deadline_session:
            past = service.utc_now() - timedelta(seconds=1)
            deadline_session.execute(
                update(AgentRun)
                .where(AgentRun.id == run_id2)
                .values(planning_deadline=past, run_deadline=past)
            )
            deadline_session.commit()
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", late_dispatch)
    late = client2.post(
        f"/agent-runs/{run_id2}/execute",
        json={"expected_revision": planned2["run"]["revision"]},
    )
    assert late.json()["run"]["state"] == "expired"
    with Session(get_engine()) as session:
        invocation = session.scalar(
            select(ToolInvocation).where(ToolInvocation.run_id == run_id2)
        )
        assert invocation is not None and invocation.status == "discarded"
        assert invocation.safe_result_summary is None


@pytest.mark.parametrize(
    ("point", "step_count", "expected_prior_calls"),
    [
        (faults.FaultPoint.AFTER_RUN_CLAIM, 1, 0),
        (faults.FaultPoint.AFTER_INVOCATION_FINALIZATION, 2, 1),
        (faults.FaultPoint.BEFORE_RUN_COMPLETION, 1, 1),
    ],
)
def test_crash_recovery_resumes_only_from_durable_progress(
    monkeypatch: pytest.MonkeyPatch,
    point: faults.FaultPoint,
    step_count: int,
    expected_prior_calls: int,
) -> None:
    client, planned = _ready_client(
        step_count=step_count, raise_server_exceptions=False
    )
    run_id = uuid.UUID(str(planned["run"]["id"]))
    calls: list[str] = []

    def dispatch(**kwargs: object) -> MemorySearchExplainedOutput:
        calls.append(str(kwargs["name"]))
        return MemorySearchExplainedOutput(results=())

    def inject(candidate: faults.FaultPoint) -> None:
        if candidate == point:
            raise RuntimeError("deterministic crash")

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    monkeypatch.setattr(faults, "fire", inject)
    crashed = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert crashed.status_code == 500
    assert len(calls) == expected_prior_calls
    monkeypatch.setattr(faults, "fire", lambda _: None)
    claim = _claim_for_recovery(run_id)
    assert claim is not None
    _drive_claim(claim)
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        attempts = list(
            session.scalars(
                select(ToolInvocation.attempt).where(ToolInvocation.run_id == run_id)
            )
        )
        assert run is not None and run.state == "completed"
        assert attempts == [0] * step_count
    assert len(calls) == step_count


def test_fault_after_reservation_rolls_back_invocation_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1, raise_server_exceptions=False)
    run_id = uuid.UUID(str(planned["run"]["id"]))

    def inject(point: faults.FaultPoint) -> None:
        if point == faults.FaultPoint.AFTER_INVOCATION_RESERVATION:
            raise RuntimeError("reservation rollback")

    monkeypatch.setattr(faults, "fire", inject)
    response = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 500
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ToolInvocation)
                .where(ToolInvocation.run_id == run_id)
            )
            == 0
        )
        step = session.scalar(select(AgentStep).where(AgentStep.run_id == run_id))
        assert step is not None and step.status == "pending"
    monkeypatch.setattr(faults, "fire", lambda _: None)
    claim = _claim_for_recovery(run_id)
    assert claim is not None
    _drive_claim(claim)


def test_fault_after_tool_return_is_not_translated_and_stale_recovery_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, planned = _ready_client(step_count=1, raise_server_exceptions=False)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    calls = 0

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        return MemorySearchExplainedOutput(results=())

    def inject(point: faults.FaultPoint) -> None:
        if point == faults.FaultPoint.AFTER_TOOL_RETURN:
            raise faults.FaultInjectionError("post-return crash")

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    monkeypatch.setattr(faults, "fire", inject)
    response = client.post(
        f"/agent-runs/{run_id}/execute",
        json={"expected_revision": planned["run"]["revision"]},
    )
    assert response.status_code == 500 and calls == 1
    with Session(get_engine()) as session:
        invocation = session.scalar(
            select(ToolInvocation).where(ToolInvocation.run_id == run_id)
        )
        assert invocation is not None and invocation.status == "running"
        aged_at = service.utc_now() - timedelta(seconds=46)
        invocation.reserved_at = aged_at
        invocation.started_at = aged_at
        session.commit()
        claim = recovery.prepare_one(session, run_id, now=service.utc_now())
        session.commit()
    assert claim is not None
    monkeypatch.setattr(faults, "fire", lambda _: None)
    _drive_claim(claim)
    assert calls == 2


def test_stale_pure_read_recovery_retries_once_then_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        claim = executor.claim_execution(
            session, run_id, expected_revision=int(planned["run"]["revision"])
        )
        assert claim is not None
        session.commit()
        _, invocation, _ = executor.reserve_next(
            session, claim, provider_available=False
        ) or pytest.fail("reservation expected")
        session.commit()
        stale_now = service.utc_now()
        aged_at = stale_now - timedelta(seconds=46)
        session.execute(
            update(ToolInvocation)
            .where(ToolInvocation.id == invocation.id)
            .values(reserved_at=aged_at, started_at=aged_at)
        )
        session.commit()
    calls = 0

    def dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal calls
        calls += 1
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    with Session(get_engine()) as session:
        finding = recovery.classify_run(
            session,
            session.get(AgentRun, run_id),
            now=stale_now,  # type: ignore[arg-type]
        )
        assert finding is not None and finding.code == "stale_pure_read"
        definition = AGENT_TOOL_REGISTRY.get_exact("memory.search_explained", 1)
        assert definition is not None
        assert (
            recovery.classify_run(
                session,
                session.get(AgentRun, run_id),  # type: ignore[arg-type]
                now=(
                    aged_at
                    + timedelta(seconds=definition.timeout_seconds)
                    + recovery.RECOVERY_GRACE
                    - timedelta(microseconds=1)
                ),
            )
            is None
        )
        recovered = recovery.prepare_one(session, run_id, now=stale_now)
        session.commit()
    assert recovered is not None
    _drive_claim(recovered)
    assert calls == 1
    with Session(get_engine()) as session:
        run = session.get(AgentRun, run_id)
        assert run is not None and recovery.prepare_one(session, run_id) is None
        session.commit()
        assert list(
            session.scalars(
                select(ToolInvocation.attempt)
                .where(ToolInvocation.run_id == run_id)
                .order_by(ToolInvocation.attempt)
            )
        ) == [0, 1]


def test_stale_retry_exhaustion_and_ambiguous_recovery_execute_no_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool_calls = 0

    def forbidden_dispatch(**_: object) -> MemorySearchExplainedOutput:
        nonlocal tool_calls
        tool_calls += 1
        raise AssertionError("recovery must not execute ambiguous tool")

    monkeypatch.setattr(executor, "dispatch_exact", forbidden_dispatch)
    _, planned = _ready_client(step_count=1)
    run_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        claim = executor.claim_execution(
            session, run_id, expected_revision=int(planned["run"]["revision"])
        )
        assert claim is not None
        session.commit()
        step, attempt0, _ = executor.reserve_next(
            session, claim, provider_available=False
        ) or pytest.fail("reservation expected")
        session.commit()
        assert executor.finalize_invocation(
            session,
            claim,
            step_id=step.id,
            invocation_id=attempt0.id,
            output=None,
            safe_error_code="tool_timeout",
        )
        session.commit()
        _, attempt1, _ = executor.reserve_next(
            session, claim, provider_available=False
        ) or pytest.fail("retry expected")
        session.commit()
        stale_now = service.utc_now()
        aged_at = stale_now - timedelta(seconds=46)
        session.execute(
            update(ToolInvocation)
            .where(ToolInvocation.id == attempt1.id)
            .values(reserved_at=aged_at, started_at=aged_at)
        )
        session.commit()
        assert recovery.prepare_one(session, run_id, now=stale_now) is None
        session.commit()
        run = session.get(AgentRun, run_id)
        assert run is not None and run.safe_error_code == "retry_exhausted"

    _, planned2 = _ready_client(step_count=1)
    run_id2 = uuid.UUID(str(planned2["run"]["id"]))
    with Session(get_engine()) as session:
        claim2 = executor.claim_execution(
            session, run_id2, expected_revision=int(planned2["run"]["revision"])
        )
        assert claim2 is not None
        session.commit()
        _, ambiguous, _ = executor.reserve_next(
            session, claim2, provider_available=False
        ) or pytest.fail("reservation expected")
        session.commit()
        ambiguous.authority = "propose"
        session.commit()
        stale_now2 = service.utc_now()
        aged_at2 = stale_now2 - timedelta(seconds=46)
        session.execute(
            update(ToolInvocation)
            .where(ToolInvocation.id == ambiguous.id)
            .values(reserved_at=aged_at2, started_at=aged_at2, authority="propose")
        )
        session.commit()
        finding = recovery.classify_run(
            session,
            session.get(AgentRun, run_id2),  # type: ignore[arg-type]
            now=stale_now2,
        )
        assert finding is not None and finding.code == "ambiguous_recovery_denied"
        assert recovery.prepare_one(session, run_id2, now=stale_now2) is None
        session.commit()
        run2 = session.get(AgentRun, run_id2)
        assert run2 is not None and run2.safe_error_code == "ambiguous_recovery_denied"
    assert tool_calls == 0


def test_retry_and_recovery_preserve_project_and_unassigned_scope_and_domain_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_client = TestClient(create_app())
    project_ids = [
        base_client.post("/projects", json={"name": f"scope-{uuid.uuid4()}"}).json()[
            "id"
        ]
        for _ in range(2)
    ]
    scopes: list[uuid.UUID | None] = []

    def dispatch(**kwargs: object) -> MemorySearchExplainedOutput:
        context = kwargs["context"]
        scopes.append(context.project_scope)  # type: ignore[attr-defined]
        if len(scopes) % 2 == 1:
            raise ProviderRequestError
        return MemorySearchExplainedOutput(results=())

    monkeypatch.setattr(executor, "dispatch_exact", dispatch)
    with Session(get_engine()) as session:
        before = tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Project, Memory, Source)
        )
    for project_id in [*project_ids, None]:
        client, planned = _ready_client(step_count=1, project_id=project_id)
        response = client.post(
            f"/agent-runs/{planned['run']['id']}/execute",
            json={"expected_revision": planned["run"]["revision"]},
        )
        assert response.json()["run"]["state"] == "completed"
    expected = [uuid.UUID(value) for value in project_ids]
    assert scopes == [expected[0], expected[0], expected[1], expected[1], None, None]
    with Session(get_engine()) as session:
        after = tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Project, Memory, Source)
        )
    assert after == before


def test_recovery_state_rules_expire_overdue_but_never_start_valid_ready() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/agent-runs",
        json={
            "project_id": None,
            "agent_kind": "research-agent",
            "agent_version": "1.0.0",
            "goal_summary": "Recovery lifecycle",
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    ).json()
    created_id = uuid.UUID(created["id"])
    now = service.utc_now()
    with Session(get_engine()) as session:
        session.execute(
            update(AgentRun)
            .where(AgentRun.id == created_id)
            .values(planning_deadline=now - timedelta(seconds=1))
        )
        session.commit()
        assert recovery.prepare_one(session, created_id, now=now) is None
        session.commit()
        expired = session.get(AgentRun, created_id)
        assert expired is not None and expired.state == "expired"
        revision = expired.revision
        assert recovery.prepare_one(session, created_id, now=now) is None
        session.commit()
        assert session.get(AgentRun, created_id).revision == revision  # type: ignore[union-attr]

    ready_client, planned = _ready_client(step_count=1)
    ready_id = uuid.UUID(str(planned["run"]["id"]))
    with Session(get_engine()) as session:
        ready = session.get(AgentRun, ready_id)
        assert ready is not None
        ready_revision = ready.revision
        assert (
            recovery.prepare_one(
                session, ready_id, now=ready.run_deadline - timedelta(seconds=1)
            )
            is None
        )
        session.commit()
        unchanged = session.get(AgentRun, ready_id)
        assert unchanged is not None
        assert (unchanged.state, unchanged.revision) == ("ready", ready_revision)
        expired_at = service.utc_now()
        past = expired_at - timedelta(seconds=1)
        unchanged.planning_deadline = past
        unchanged.run_deadline = past
        session.commit()
        assert recovery.prepare_one(session, ready_id, now=expired_at) is None
        session.commit()
        assert session.get(AgentRun, ready_id).state == "expired"  # type: ignore[union-attr]
    assert ready_client.get(f"/agent-runs/{ready_id}").status_code == 200
