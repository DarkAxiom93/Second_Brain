"""Transaction-neutral persistence primitives for future Agent Runtime services."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)


class AgentOwnershipError(Exception):
    """A requested child does not belong to the supplied Run."""


class AgentRevisionConflictError(Exception):
    """The durable Run revision did not match the caller's expectation."""


def create_agent_run(session: Session, run: AgentRun) -> AgentRun:
    session.add(run)
    session.flush()
    session.refresh(run)
    return run


def get_agent_run(session: Session, run_id: uuid.UUID) -> AgentRun | None:
    return session.scalar(select(AgentRun).where(AgentRun.id == run_id))


def get_agent_run_in_project_scope(
    session: Session, run_id: uuid.UUID, project_id: uuid.UUID | None
) -> AgentRun | None:
    scope_predicate = (
        AgentRun.project_id.is_(None)
        if project_id is None
        else AgentRun.project_id == project_id
    )
    return session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, scope_predicate)
    )


def get_agent_run_for_update(session: Session, run_id: uuid.UUID) -> AgentRun | None:
    return session.scalar(
        select(AgentRun).where(AgentRun.id == run_id).with_for_update(of=AgentRun)
    )


def advance_agent_run_revision(
    session: Session, run_id: uuid.UUID, *, expected_revision: int
) -> AgentRun:
    result = session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.revision == expected_revision)
        .values(revision=expected_revision + 1)
        .returning(AgentRun.id)
    )
    if result.scalar_one_or_none() is None:
        raise AgentRevisionConflictError
    session.flush()
    run = get_agent_run(session, run_id)
    assert run is not None
    session.refresh(run)
    return run


def insert_agent_step(session: Session, step: AgentStep) -> AgentStep:
    if get_agent_run(session, step.run_id) is None:
        raise AgentOwnershipError
    session.add(step)
    session.flush()
    session.refresh(step)
    return step


def list_agent_steps(
    session: Session, run_id: uuid.UUID, *, limit: int, offset: int = 0
) -> list[AgentStep]:
    if get_agent_run(session, run_id) is None:
        raise AgentOwnershipError
    return list(
        session.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.ordinal.asc(), AgentStep.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


def reserve_tool_invocation(
    session: Session, invocation: ToolInvocation
) -> ToolInvocation:
    owner = session.scalar(
        select(AgentStep.id).where(
            AgentStep.id == invocation.step_id,
            AgentStep.run_id == invocation.run_id,
        )
    )
    if owner is None:
        raise AgentOwnershipError
    session.add(invocation)
    session.flush()
    session.refresh(invocation)
    return invocation


def get_tool_invocation(
    session: Session, run_id: uuid.UUID, invocation_id: uuid.UUID
) -> ToolInvocation | None:
    return session.scalar(
        select(ToolInvocation).where(
            ToolInvocation.id == invocation_id, ToolInvocation.run_id == run_id
        )
    )


def insert_approval_request(
    session: Session, approval: ApprovalRequest
) -> ApprovalRequest:
    owner = session.scalar(
        select(AgentStep.id).where(
            AgentStep.id == approval.step_id, AgentStep.run_id == approval.run_id
        )
    )
    if owner is None:
        raise AgentOwnershipError
    session.add(approval)
    session.flush()
    session.refresh(approval)
    return approval


def get_approval_request(
    session: Session, run_id: uuid.UUID, approval_id: uuid.UUID
) -> ApprovalRequest | None:
    return session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id, ApprovalRequest.run_id == run_id
        )
    )


def append_agent_event(
    session: Session,
    *,
    run_id: uuid.UUID,
    event_type: str,
    safe_code: str,
    safe_message: str,
    metadata: dict[str, Any],
    correlation_id: uuid.UUID,
    occurred_at: datetime,
    step_id: uuid.UUID | None = None,
    invocation_id: uuid.UUID | None = None,
    approval_id: uuid.UUID | None = None,
    event_idempotency_hash: str | None = None,
) -> AgentEvent:
    """Lock the Run and append the next monotonic event in this transaction."""

    if get_agent_run_for_update(session, run_id) is None:
        raise AgentOwnershipError
    sequence = session.scalar(
        select(func.coalesce(func.max(AgentEvent.sequence), -1)).where(
            AgentEvent.run_id == run_id
        )
    )
    assert sequence is not None
    event = AgentEvent(
        run_id=run_id,
        step_id=step_id,
        invocation_id=invocation_id,
        approval_id=approval_id,
        sequence=sequence + 1,
        event_type=event_type,
        safe_code=safe_code,
        safe_message=safe_message,
        safe_metadata=metadata,
        correlation_id=correlation_id,
        occurred_at=occurred_at,
        event_idempotency_hash=event_idempotency_hash,
    )
    session.add(event)
    session.flush()
    session.refresh(event)
    return event


def list_agent_events(
    session: Session, run_id: uuid.UUID, *, limit: int, offset: int = 0
) -> list[AgentEvent]:
    if get_agent_run(session, run_id) is None:
        raise AgentOwnershipError
    return list(
        session.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.sequence.asc(), AgentEvent.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
