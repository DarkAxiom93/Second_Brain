"""Explicit synchronous stale detection and single-Run recovery."""

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agent_runs import executor, service
from app.agent_tools.registry import (
    AGENT_TOOL_REGISTRY,
    REGISTRY_VERSION,
    ToolDefinition,
)
from app.models.agent_runtime import AgentRun, AgentStep, ToolInvocation
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import AgentRunState

RECOVERY_GRACE = timedelta(seconds=30)
SCAN_LIMIT = 100


def _definition(invocation: ToolInvocation) -> ToolDefinition | None:
    try:
        version = int(invocation.tool_version)
    except ValueError:
        return None
    return AGENT_TOOL_REGISTRY.get_exact(invocation.tool_name, version)


def _exact_pure_read_definition(
    run: AgentRun,
    step: AgentStep | None,
    invocation: ToolInvocation,
) -> bool:
    if (
        run.registry_version != REGISTRY_VERSION
        or step is None
        or step.tool_name != invocation.tool_name
        or step.tool_version != invocation.tool_version
        or invocation.authority != "read"
    ):
        return False
    definition = _definition(invocation)
    return definition is not None and definition.idempotency.value == "pure_read"


@dataclass(frozen=True, slots=True)
class RecoveryFinding:
    run_id: str
    state: str
    code: str
    ordinal: int | None
    attempt: int | None
    relevant_at: str

    def safe_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_run(
    session: Session, run: AgentRun, *, now: datetime
) -> RecoveryFinding | None:
    steps = repository.list_agent_steps(session, run.id, limit=13)
    invocations = repository.list_step_invocations(session, run.id)
    code: str | None = None
    ordinal: int | None = None
    attempt: int | None = None
    relevant_at = run.updated_at
    if run.state in {"created", "planning"} and now >= run.planning_deadline:
        code, relevant_at = "deadline_expired", run.planning_deadline
    elif run.state in {"ready", "running"} and now >= run.run_deadline:
        code, relevant_at = "deadline_expired", run.run_deadline
    elif run.state == "running":
        active = [
            item for item in invocations if item.status in {"reserved", "running"}
        ]
        if active:
            item = active[0]
            step = next((step for step in steps if step.id == item.step_id), None)
            definition = _definition(item)
            stale_at = (
                item.reserved_at
                + timedelta(
                    seconds=0 if definition is None else definition.timeout_seconds
                )
                + RECOVERY_GRACE
            )
            if now >= stale_at:
                ordinal = None if step is None else step.ordinal
                attempt, relevant_at = item.attempt, stale_at
                code = (
                    "stale_pure_read"
                    if _exact_pure_read_definition(run, step, item)
                    else "ambiguous_recovery_denied"
                )
        elif steps and all(step.status == "succeeded" for step in steps):
            code = "completion_pending"
        elif any(step.status in {"pending", "running"} for step in steps):
            code = "durable_work_remaining"
        else:
            code = "recovery_state_invalid"
    if code is None:
        return None
    return RecoveryFinding(
        run_id=str(run.id),
        state=run.state,
        code=code,
        ordinal=ordinal,
        attempt=attempt,
        relevant_at=relevant_at.isoformat(),
    )


def scan(session: Session, *, now: datetime | None = None) -> list[RecoveryFinding]:
    operation_time = now or service.utc_now()
    return [
        finding
        for run in repository.list_nonterminal_agent_runs(session, limit=SCAN_LIMIT)
        if (finding := classify_run(session, run, now=operation_time)) is not None
    ]


def prepare_one(
    session: Session, run_id: uuid.UUID, *, now: datetime | None = None
) -> executor.ExecutionClaim | None:
    operation_time = now or service.utc_now()
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise service.AgentRunNotFoundError
    if AgentRunState(run.state) in service.TERMINAL_STATES:
        return None
    steps = repository.list_agent_steps_for_update(session, run.id)
    invocations = repository.list_step_invocations_for_update(session, run.id)
    if run.state in {"created", "planning"} and operation_time >= run.planning_deadline:
        service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState(run.state),
            expected_revision=run.revision,
            new_state=AgentRunState.EXPIRED,
            now=operation_time,
            safe_error_code="deadline_expired",
        )
        return None
    if run.state == "ready":
        if operation_time >= run.run_deadline:
            service.transition_run(
                session,
                run.id,
                expected_state=AgentRunState.READY,
                expected_revision=run.revision,
                new_state=AgentRunState.EXPIRED,
                now=operation_time,
                safe_error_code="deadline_expired",
            )
        return None
    if run.state != "running":
        return None
    if operation_time >= run.run_deadline:
        executor._expire_execution(session, run, steps, operation_time)
        return None
    active = [item for item in invocations if item.status in {"reserved", "running"}]
    if len(active) > 1:
        service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.FAILED,
            now=operation_time,
            safe_error_code="recovery_state_invalid",
        )
        return None
    if active:
        item = active[0]
        step = next((step for step in steps if step.id == item.step_id), None)
        definition = _definition(item)
        stale_at = (
            item.reserved_at
            + timedelta(seconds=0 if definition is None else definition.timeout_seconds)
            + RECOVERY_GRACE
        )
        if operation_time < stale_at:
            return None
        if not _exact_pure_read_definition(run, step, item):
            if step is None:
                service.transition_run(
                    session,
                    run.id,
                    expected_state=AgentRunState.RUNNING,
                    expected_revision=run.revision,
                    new_state=AgentRunState.FAILED,
                    now=operation_time,
                    safe_error_code="recovery_state_invalid",
                )
                return None
            executor._fail_active_step(
                session, run, step, "ambiguous_recovery_denied", operation_time
            )
            return None
        item.status = "discarded"
        item.safe_error_code = "tool_timeout"
        item.started_at = item.started_at or item.reserved_at
        item.finished_at = operation_time
        repository.append_agent_event(
            session,
            run_id=run.id,
            step_id=item.step_id,
            invocation_id=item.id,
            event_type="agent_recovery.reconciled",
            safe_code="stale_pure_read_discarded",
            safe_message="stale pure-read invocation discarded",
            metadata={"attempt": item.attempt},
            correlation_id=run.correlation_id,
            occurred_at=operation_time,
        )
        if item.attempt >= run.retry_budget:
            assert step is not None
            executor._fail_active_step(
                session, run, step, "retry_exhausted", operation_time
            )
            return None
    elif not steps or not any(step.status in {"pending", "running"} for step in steps):
        if steps and all(step.status == "succeeded" for step in steps):
            pass
        else:
            service.transition_run(
                session,
                run.id,
                expected_state=AgentRunState.RUNNING,
                expected_revision=run.revision,
                new_state=AgentRunState.FAILED,
                now=operation_time,
                safe_error_code="recovery_state_invalid",
            )
            return None
    elif any(
        step.status == "running"
        and not any(item.step_id == step.id for item in invocations)
        for step in steps
    ):
        step = next(step for step in steps if step.status == "running")
        executor._fail_active_step(
            session, run, step, "recovery_state_invalid", operation_time
        )
        return None
    return executor.ExecutionClaim(
        run_id=run.id,
        project_scope=run.project_id,
        registry_version=run.registry_version,
        tool_call_budget=run.tool_call_budget,
        agent_kind=run.agent_kind,
        agent_version=run.agent_version,
        goal_summary=run.goal_summary,
    )
