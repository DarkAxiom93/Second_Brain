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


def get_agent_run_by_idempotency_hash(
    session: Session, idempotency_key_hash: str
) -> AgentRun | None:
    return session.scalar(
        select(AgentRun).where(AgentRun.idempotency_key_hash == idempotency_key_hash)
    )


def get_agent_run_by_idempotency_hash_for_update(
    session: Session, idempotency_key_hash: str
) -> AgentRun | None:
    return session.scalar(
        select(AgentRun)
        .where(AgentRun.idempotency_key_hash == idempotency_key_hash)
        .with_for_update(of=AgentRun)
    )


def lock_agent_run_capacity(session: Session, lock_key: int) -> None:
    """Serialize the transaction-scoped active-Run capacity decision."""

    session.execute(select(func.pg_advisory_xact_lock(lock_key)))


def count_agent_runs_in_states(session: Session, states: frozenset[str]) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.state.in_(states))
        )
        or 0
    )


def list_agent_runs(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    unassigned: bool,
    state: str | None,
    limit: int,
    offset: int,
) -> list[AgentRun]:
    statement = select(AgentRun)
    if project_id is not None:
        statement = statement.where(AgentRun.project_id == project_id)
    elif unassigned:
        statement = statement.where(AgentRun.project_id.is_(None))
    if state is not None:
        statement = statement.where(AgentRun.state == state)
    statement = (
        statement.order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement).all())


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


def list_agent_steps_for_update(session: Session, run_id: uuid.UUID) -> list[AgentStep]:
    return list(
        session.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.ordinal.asc(), AgentStep.id.asc())
            .with_for_update(of=AgentStep)
        ).all()
    )


def get_agent_step_for_update(
    session: Session, run_id: uuid.UUID, step_id: uuid.UUID
) -> AgentStep | None:
    return session.scalar(
        select(AgentStep)
        .where(AgentStep.id == step_id, AgentStep.run_id == run_id)
        .with_for_update(of=AgentStep)
    )


def get_agent_step(
    session: Session, run_id: uuid.UUID, step_id: uuid.UUID
) -> AgentStep | None:
    return session.scalar(
        select(AgentStep).where(AgentStep.id == step_id, AgentStep.run_id == run_id)
    )


def count_agent_steps(session: Session, run_id: uuid.UUID) -> int:
    """Return the durable plan size without loading private Step rows."""

    count = session.scalar(
        select(func.count()).select_from(AgentStep).where(AgentStep.run_id == run_id)
    )
    assert count is not None
    return count


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


def get_tool_invocation_for_update(
    session: Session, run_id: uuid.UUID, invocation_id: uuid.UUID
) -> ToolInvocation | None:
    return session.scalar(
        select(ToolInvocation)
        .where(ToolInvocation.id == invocation_id, ToolInvocation.run_id == run_id)
        .with_for_update(of=ToolInvocation)
    )


def count_tool_invocations(
    session: Session, run_id: uuid.UUID, *, tool_name: str | None = None
) -> int:
    statement = (
        select(func.count())
        .select_from(ToolInvocation)
        .where(ToolInvocation.run_id == run_id)
    )
    if tool_name is not None:
        statement = statement.where(ToolInvocation.tool_name == tool_name)
    count = session.scalar(statement)
    assert count is not None
    return count


def list_step_invocations(session: Session, run_id: uuid.UUID) -> list[ToolInvocation]:
    return list(
        session.scalars(
            select(ToolInvocation)
            .join(AgentStep, AgentStep.id == ToolInvocation.step_id)
            .where(ToolInvocation.run_id == run_id)
            .order_by(AgentStep.ordinal.asc(), ToolInvocation.attempt.asc())
        ).all()
    )


def list_step_invocations_for_update(
    session: Session, run_id: uuid.UUID
) -> list[ToolInvocation]:
    return list(
        session.scalars(
            select(ToolInvocation)
            .join(AgentStep, AgentStep.id == ToolInvocation.step_id)
            .where(ToolInvocation.run_id == run_id)
            .order_by(AgentStep.ordinal.asc(), ToolInvocation.attempt.asc())
            .with_for_update(of=ToolInvocation)
        ).all()
    )


def list_nonterminal_agent_runs(session: Session, *, limit: int) -> list[AgentRun]:
    return list(
        session.scalars(
            select(AgentRun)
            .where(AgentRun.state.in_(("created", "planning", "ready", "running")))
            .order_by(AgentRun.created_at.asc(), AgentRun.id.asc())
            .limit(limit)
        ).all()
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


def get_approval_request_by_id(
    session: Session, approval_id: uuid.UUID
) -> ApprovalRequest | None:
    return session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )


def get_approval_request_for_update(
    session: Session, approval_id: uuid.UUID
) -> ApprovalRequest | None:
    return session.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.id == approval_id)
        .with_for_update(of=ApprovalRequest)
    )


def get_exact_approval_request(
    session: Session,
    *,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    action_type: str,
    target_type: str,
    target_public_id: uuid.UUID,
    target_version: str,
    proposal_hash: str,
) -> ApprovalRequest | None:
    return session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.step_id == step_id,
            ApprovalRequest.action_type == action_type,
            ApprovalRequest.target_type == target_type,
            ApprovalRequest.target_public_id == target_public_id,
            ApprovalRequest.target_version == target_version,
            ApprovalRequest.proposal_hash == proposal_hash,
        )
    )


def list_approval_requests(
    session: Session, run_id: uuid.UUID, *, limit: int, offset: int
) -> list[ApprovalRequest]:
    return list(
        session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.run_id == run_id)
            .order_by(ApprovalRequest.created_at.asc(), ApprovalRequest.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


def get_agent_step_by_ordinal_for_update(
    session: Session, run_id: uuid.UUID, ordinal: int
) -> AgentStep | None:
    return session.scalar(
        select(AgentStep)
        .where(AgentStep.run_id == run_id, AgentStep.ordinal == ordinal)
        .with_for_update(of=AgentStep)
    )


def list_step_evidence(
    session: Session, run_id: uuid.UUID, step_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ToolInvocation)
        .where(
            ToolInvocation.run_id == run_id,
            ToolInvocation.step_id == step_id,
            ToolInvocation.status == "succeeded",
        )
        .order_by(ToolInvocation.attempt.asc(), ToolInvocation.id.asc())
    ).all()
    return [reference for row in rows for reference in row.evidence_references]


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
