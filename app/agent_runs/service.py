"""Atomic, transaction-neutral Agent Run lifecycle operations."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.agent_tools.registry import REGISTRY_VERSION
from app.models.agent_runtime import AgentRun
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import AgentRunCreate, AgentRunState

POLICY_VERSION = "agent-run-api-v1"
STEP_BUDGET = 12
TOOL_CALL_BUDGET = 20
RETRY_BUDGET = 1
RUN_DURATION = timedelta(minutes=10)

LEGAL_TRANSITIONS: dict[AgentRunState, frozenset[AgentRunState]] = {
    AgentRunState.CREATED: frozenset(
        {AgentRunState.PLANNING, AgentRunState.CANCELLED, AgentRunState.EXPIRED}
    ),
    AgentRunState.PLANNING: frozenset(
        {
            AgentRunState.READY,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
            AgentRunState.EXPIRED,
        }
    ),
    AgentRunState.READY: frozenset(
        {AgentRunState.RUNNING, AgentRunState.CANCELLED, AgentRunState.EXPIRED}
    ),
    AgentRunState.RUNNING: frozenset(
        {
            AgentRunState.RUNNING,
            AgentRunState.AWAITING_APPROVAL,
            AgentRunState.COMPLETED,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
            AgentRunState.EXPIRED,
        }
    ),
    AgentRunState.AWAITING_APPROVAL: frozenset(
        {
            AgentRunState.RUNNING,
            AgentRunState.FAILED,
            AgentRunState.CANCELLED,
            AgentRunState.EXPIRED,
        }
    ),
    AgentRunState.COMPLETED: frozenset(),
    AgentRunState.FAILED: frozenset(),
    AgentRunState.CANCELLED: frozenset(),
    AgentRunState.EXPIRED: frozenset(),
}
TERMINAL_STATES = frozenset(
    {
        AgentRunState.COMPLETED,
        AgentRunState.FAILED,
        AgentRunState.CANCELLED,
        AgentRunState.EXPIRED,
    }
)
ACTIVE_PROCESSING_STATES = frozenset(
    {
        AgentRunState.PLANNING,
        AgentRunState.READY,
        AgentRunState.RUNNING,
        AgentRunState.AWAITING_APPROVAL,
    }
)


class AgentRunNotFoundError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class AgentRunRevisionConflictError(Exception):
    pass


class AgentRunTransitionConflictError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


@dataclass(frozen=True)
class CreateResult:
    run: AgentRun
    created: bool


def utc_now() -> datetime:
    return datetime.now(UTC)


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def normalized_request_fingerprint(request: AgentRunCreate) -> str:
    payload = request.model_dump(mode="json")
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _replay_or_conflict(run: AgentRun, fingerprint: str) -> CreateResult:
    if run.normalized_request_fingerprint != fingerprint:
        raise IdempotencyConflictError
    return CreateResult(run=run, created=False)


def resolve_create_replay(
    session: Session, *, idempotency_key_hash: str, fingerprint: str
) -> CreateResult | None:
    run = repository.get_agent_run_by_idempotency_hash(session, idempotency_key_hash)
    return None if run is None else _replay_or_conflict(run, fingerprint)


def create_run(
    session: Session,
    request: AgentRunCreate,
    *,
    idempotency_key_hash: str,
    fingerprint: str,
    now: datetime | None = None,
) -> CreateResult:
    existing = repository.get_agent_run_by_idempotency_hash_for_update(
        session, idempotency_key_hash
    )
    if existing is not None:
        return _replay_or_conflict(existing, fingerprint)
    if request.project_id is not None:
        from app.repositories.projects import get_project

        if get_project(session, request.project_id) is None:
            raise ProjectNotFoundError

    operation_time = now or utc_now()
    correlation_id = uuid.uuid4()
    run = repository.create_agent_run(
        session,
        AgentRun(
            project_id=request.project_id,
            agent_kind=request.agent_kind,
            agent_version=request.agent_version,
            goal_summary=request.goal_summary,
            registry_version=REGISTRY_VERSION,
            policy_version=POLICY_VERSION,
            state=AgentRunState.CREATED.value,
            step_budget=STEP_BUDGET,
            tool_call_budget=TOOL_CALL_BUDGET,
            retry_budget=RETRY_BUDGET,
            planning_deadline=operation_time + RUN_DURATION,
            run_deadline=operation_time + RUN_DURATION,
            revision=0,
            correlation_id=correlation_id,
            idempotency_key_hash=idempotency_key_hash,
            normalized_request_fingerprint=fingerprint,
            created_at=operation_time,
            updated_at=operation_time,
        ),
    )
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type="agent_run.created",
        safe_code="agent_run_created",
        safe_message="agent run created",
        metadata={
            "previous_state": None,
            "new_state": AgentRunState.CREATED.value,
            "resulting_revision": 0,
        },
        correlation_id=correlation_id,
        occurred_at=operation_time,
    )
    return CreateResult(run=run, created=True)


def transition_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_state: AgentRunState,
    expected_revision: int,
    new_state: AgentRunState,
    now: datetime | None = None,
    safe_error_code: str | None = None,
) -> AgentRun:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise AgentRunNotFoundError
    current_state = AgentRunState(run.state)
    if (
        current_state != expected_state
        or new_state not in LEGAL_TRANSITIONS[current_state]
    ):
        raise AgentRunTransitionConflictError
    if run.revision != expected_revision:
        raise AgentRunRevisionConflictError

    operation_time = now or utc_now()
    if new_state == AgentRunState.EXPIRED:
        deadline = (
            run.planning_deadline
            if current_state in {AgentRunState.CREATED, AgentRunState.PLANNING}
            else run.run_deadline
        )
        if operation_time < deadline:
            raise AgentRunTransitionConflictError

    resulting_revision = run.revision + 1
    run.state = new_state.value
    run.revision = resulting_revision
    run.updated_at = operation_time
    run.safe_error_code = safe_error_code
    if run.started_at is None and new_state in ACTIVE_PROCESSING_STATES:
        run.started_at = operation_time
    if new_state in TERMINAL_STATES:
        # The Checkpoint 62 database invariant requires terminal Runs to have a
        # start timestamp, including direct created -> cancelled/expired stops.
        if run.started_at is None:
            run.started_at = operation_time
        run.finished_at = operation_time
    session.flush()
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type="agent_run.state_changed",
        safe_code="agent_run_state_changed",
        safe_message="agent run state changed",
        metadata={
            "previous_state": current_state.value,
            "new_state": new_state.value,
            "resulting_revision": resulting_revision,
        },
        correlation_id=run.correlation_id,
        occurred_at=operation_time,
    )
    session.refresh(run)
    return run


def cancel_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_revision: int,
    now: datetime | None = None,
) -> AgentRun:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise AgentRunNotFoundError
    current_state = AgentRunState(run.state)
    if current_state == AgentRunState.CANCELLED:
        return run
    if current_state in TERMINAL_STATES:
        raise AgentRunTransitionConflictError
    if run.revision != expected_revision:
        raise AgentRunRevisionConflictError
    return transition_run(
        session,
        run_id,
        expected_state=current_state,
        expected_revision=expected_revision,
        new_state=AgentRunState.CANCELLED,
        now=now,
    )
