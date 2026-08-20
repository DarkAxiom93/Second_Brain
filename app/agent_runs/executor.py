"""Synchronous bounded execution of one frozen read-only Agent Run plan."""

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import monotonic

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_runs import faults, service
from app.agent_tools.dispatch import (
    ToolCallContext,
    ToolControlledFailure,
    ToolInputInvalidError,
    ToolOutputInvalidError,
    ToolUnavailableError,
    dispatch_exact,
)
from app.agent_tools.policy import PolicyRejection, resolve_tool_policy
from app.agent_tools.registry import (
    AGENT_TOOL_REGISTRY,
    REGISTRY_VERSION,
    Authority,
    IdempotencyClass,
)
from app.embeddings import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.models.agent_runtime import AgentRun, AgentStep, ToolInvocation
from app.repositories import agent_runtime as repository
from app.research.catalog import RESEARCH_TOOLS, is_research, is_unknown_research
from app.schemas.agent_run import AgentRunState


class ExecutionPlanInvalidError(Exception):
    pass


class ExecutionRegistryVersionError(Exception):
    pass


class ExecutionAgentVersionError(Exception):
    pass


class RetryClass(StrEnum):
    NEVER = "never"
    SAFE_TRANSIENT_READ = "safe_transient_read"
    AMBIGUOUS_MANUAL_RECOVERY = "ambiguous_manual_recovery"


_TRANSIENT_READ_CODES = frozenset(
    {"tool_timeout", "tool_provider_unavailable", "tool_provider_failed"}
)


def classify_retry(
    safe_error_code: str | None, *, authority: str, idempotency: str
) -> RetryClass:
    """Closed retry classification; unknown values always fail closed."""

    if safe_error_code in _TRANSIENT_READ_CODES:
        if (
            authority == Authority.READ.value
            and idempotency == IdempotencyClass.PURE_READ.value
        ):
            return RetryClass.SAFE_TRANSIENT_READ
        return RetryClass.AMBIGUOUS_MANUAL_RECOVERY
    return RetryClass.NEVER


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    run_id: uuid.UUID
    project_scope: uuid.UUID | None
    registry_version: str
    tool_call_budget: int
    agent_kind: str = "manual"
    agent_version: str = "1"
    goal_summary: str = "Manual Agent Run"


def _original_claim_revision(session: Session, run_id: uuid.UUID) -> int | None:
    for event in repository.list_agent_events(session, run_id, limit=1000):
        metadata = event.safe_metadata
        if (
            event.event_type == "agent_run.state_changed"
            and metadata.get("previous_state") == AgentRunState.READY.value
            and metadata.get("new_state") == AgentRunState.RUNNING.value
        ):
            resulting = metadata.get("resulting_revision")
            return resulting - 1 if isinstance(resulting, int) else None
    return None


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def claim_execution(
    session: Session, run_id: uuid.UUID, *, expected_revision: int
) -> ExecutionClaim | None:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise service.AgentRunNotFoundError
    if run.state in {state.value for state in service.TERMINAL_STATES}:
        if _original_claim_revision(session, run.id) == expected_revision:
            return None
        raise service.AgentRunRevisionConflictError
    if run.state == AgentRunState.RUNNING.value:
        if _original_claim_revision(session, run.id) == expected_revision:
            raise service.AgentRunTransitionConflictError
        raise service.AgentRunRevisionConflictError
    if run.revision != expected_revision:
        raise service.AgentRunRevisionConflictError
    if run.state != AgentRunState.READY.value:
        raise service.AgentRunTransitionConflictError
    if run.registry_version != REGISTRY_VERSION:
        raise ExecutionRegistryVersionError
    if is_unknown_research(run.agent_kind, run.agent_version):
        raise ExecutionAgentVersionError
    now = service.utc_now()
    if now >= run.run_deadline:
        service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.READY,
            expected_revision=run.revision,
            new_state=AgentRunState.EXPIRED,
            now=now,
            safe_error_code="deadline_expired",
        )
        return None
    steps = repository.list_agent_steps_for_update(session, run.id)
    valid_tools = True
    for step in steps:
        try:
            version = int(step.tool_version or "")
        except ValueError:
            valid_tools = False
            break
        if (
            step.tool_name is None
            or AGENT_TOOL_REGISTRY.get_exact(step.tool_name, version) is None
            or (
                is_research(run.agent_kind, run.agent_version)
                and (step.tool_name, version) not in RESEARCH_TOOLS
            )
        ):
            valid_tools = False
            break
    if (
        not steps
        or len(steps) > run.step_budget
        or [step.ordinal for step in steps] != list(range(len(steps)))
        or any(step.status != "pending" for step in steps)
        or not valid_tools
    ):
        raise ExecutionPlanInvalidError
    service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.READY,
        expected_revision=run.revision,
        new_state=AgentRunState.RUNNING,
    )
    return ExecutionClaim(
        run_id=run.id,
        project_scope=run.project_id,
        registry_version=run.registry_version,
        tool_call_budget=run.tool_call_budget,
        agent_kind=run.agent_kind,
        agent_version=run.agent_version,
        goal_summary=run.goal_summary,
    )


def _fail_without_invocation(
    session: Session, run: AgentRun, step: AgentStep, code: str, now: datetime
) -> None:
    step.status = "failed"
    step.started_at = now
    step.finished_at = now
    repository.append_agent_event(
        session,
        run_id=run.id,
        step_id=step.id,
        event_type="agent_step.failed",
        safe_code=code,
        safe_message="agent step failed",
        metadata={"ordinal": step.ordinal},
        correlation_id=run.correlation_id,
        occurred_at=now,
    )
    service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.FAILED,
        now=now,
        safe_error_code=code,
    )


def reserve_next(
    session: Session,
    claim: ExecutionClaim,
    *,
    provider_available: bool,
) -> tuple[AgentStep, ToolInvocation, int] | None:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return None
    steps = repository.list_agent_steps_for_update(session, run.id)
    now = service.utc_now()
    if now >= run.run_deadline:
        _expire_execution(session, run, steps, now)
        return None
    candidates = [step for step in steps if step.status in {"pending", "running"}]
    if not candidates:
        return None
    step = candidates[0]
    if is_unknown_research(run.agent_kind, run.agent_version):
        _fail_without_invocation(
            session, run, step, "agent_definition_unsupported", now
        )
        return None
    if any(previous.status != "succeeded" for previous in steps[: step.ordinal]):
        raise ExecutionPlanInvalidError
    assert step.tool_name is not None and step.tool_version is not None
    all_invocations = repository.list_step_invocations_for_update(session, run.id)
    prior = [item for item in all_invocations if item.step_id == step.id]
    attempt = 0
    if step.status == "running":
        if (
            len(prior) != 1
            or prior[0].attempt != 0
            or prior[0].status not in {"failed", "timed_out", "discarded"}
        ):
            raise ExecutionPlanInvalidError
        definition = AGENT_TOOL_REGISTRY.get_exact(
            step.tool_name, int(step.tool_version)
        )
        if (
            definition is None
            or classify_retry(
                prior[0].safe_error_code,
                authority=prior[0].authority,
                idempotency=definition.idempotency.value,
            )
            != RetryClass.SAFE_TRANSIENT_READ
        ):
            _fail_active_step(session, run, step, "ambiguous_recovery_denied", now)
            return None
        retries_used = sum(item.attempt > 0 for item in all_invocations)
        if retries_used >= run.retry_budget:
            _fail_active_step(session, run, step, "retry_exhausted", now)
            return None
        attempt = 1
    total = repository.count_tool_invocations(session, run.id)
    per_tool = repository.count_tool_invocations(
        session, run.id, tool_name=step.tool_name
    )
    definition = AGENT_TOOL_REGISTRY.get_exact(step.tool_name, int(step.tool_version))
    candidate_input: object = step.normalized_input
    if definition is not None:
        try:
            candidate_input = definition.input_schema.model_validate_json(
                json.dumps(step.normalized_input, separators=(",", ":")), strict=True
            ).model_dump(mode="python")
        except (TypeError, ValueError):
            candidate_input = step.normalized_input
    policy = resolve_tool_policy(
        name=step.tool_name,
        version=int(step.tool_version),
        requested_authority="read",
        candidate_input=candidate_input,
        captured_registry_version=run.registry_version,
        captured_run_project_scope=run.project_id,
        captured_run_tool_call_budget=run.tool_call_budget,
        total_calls_reserved=total,
        tool_calls_reserved=per_tool,
        configured_provider_available=provider_available,
        operator_aggregate_allowed=False,
    )
    if isinstance(policy, PolicyRejection):
        _fail_without_invocation(
            session, run, step, f"tool_policy_{policy.code.value}", now
        )
        return None
    normalized_value = _plain(policy.normalized_input)
    assert isinstance(normalized_value, dict)
    normalized = normalized_value
    input_hash = _hash(_canonical(normalized))
    identity = _hash(
        f"{run.id}:{step.id}:{attempt}:{step.tool_name}:{step.tool_version}:{input_hash}".encode(
            "ascii"
        )
    )
    faults.fire(faults.FaultPoint.BEFORE_INVOCATION_RESERVATION)
    invocation = repository.reserve_tool_invocation(
        session,
        ToolInvocation(
            run_id=run.id,
            step_id=step.id,
            attempt=attempt,
            tool_name=step.tool_name,
            tool_version=step.tool_version,
            authority="read",
            validated_input_hash=input_hash,
            validated_input=normalized,
            idempotency_key_hash=identity,
            status="reserved",
            reserved_at=now,
        ),
    )
    invocation.status = "running"
    invocation.started_at = now
    step.status = "running"
    step.started_at = now
    repository.append_agent_event(
        session,
        run_id=run.id,
        step_id=step.id,
        invocation_id=invocation.id,
        event_type="tool_invocation.started",
        safe_code="tool_invocation_started",
        safe_message="tool invocation started",
        metadata={"ordinal": step.ordinal, "tool_name": step.tool_name},
        correlation_id=run.correlation_id,
        occurred_at=now,
    )
    faults.fire(faults.FaultPoint.AFTER_INVOCATION_RESERVATION)
    return step, invocation, policy.timeout_seconds


def _fail_active_step(
    session: Session, run: AgentRun, step: AgentStep, code: str, now: datetime
) -> None:
    step.status = "failed"
    step.finished_at = now
    service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.FAILED,
        now=now,
        safe_error_code=code,
    )


def _expire_execution(
    session: Session, run: AgentRun, steps: list[AgentStep], now: datetime
) -> None:
    for invocation in repository.list_step_invocations_for_update(session, run.id):
        if invocation.status in {"reserved", "running"}:
            invocation.status = "discarded"
            invocation.safe_error_code = "deadline_expired"
            invocation.started_at = invocation.started_at or now
            invocation.finished_at = now
    for step in steps:
        if step.status in {"pending", "running"}:
            step.status = "cancelled"
            step.started_at = step.started_at or now
            step.finished_at = now
    service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.EXPIRED,
        now=now,
        safe_error_code="deadline_expired",
    )


def _safe_projection(
    output: BaseModel, tool_name: str
) -> tuple[str, list[dict[str, object]]]:
    value = output.model_dump(mode="json")
    if tool_name == "memory.search_explained":
        rows = value["results"]
        return (
            f"explained search returned {len(rows)} result(s)",
            [{"entity_type": "memory", "id": row["memory_id"]} for row in rows],
        )
    entity_type = {
        "project.get": "project",
        "memory.get": "memory",
        "source.get": "source",
        "source_chunk.get": "source_chunk",
    }[tool_name]
    return f"{entity_type} read succeeded", [
        {"entity_type": entity_type, "id": value["id"]}
    ]


def finalize_invocation(
    session: Session,
    claim: ExecutionClaim,
    *,
    step_id: uuid.UUID,
    invocation_id: uuid.UUID,
    output: BaseModel | None,
    safe_error_code: str | None,
    evidence_references: list[dict[str, object]] | None = None,
) -> bool:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None:
        return False
    step = repository.get_agent_step_for_update(session, run.id, step_id)
    invocation = repository.get_tool_invocation_for_update(
        session, run.id, invocation_id
    )
    if step is None or invocation is None or invocation.status != "running":
        return False
    now = service.utc_now()
    if run.state != AgentRunState.RUNNING.value:
        invocation.status = "discarded"
        invocation.safe_error_code = (
            "cancellation_discard"
            if run.state == AgentRunState.CANCELLED.value
            else "tool_result_discarded"
        )
        invocation.finished_at = now
        return False
    if now >= run.run_deadline:
        invocation.status = "discarded"
        invocation.safe_error_code = "deadline_expired"
        invocation.finished_at = now
        _expire_execution(
            session, run, repository.list_agent_steps_for_update(session, run.id), now
        )
        return False
    if safe_error_code is None and output is not None:
        definition = AGENT_TOOL_REGISTRY.get_exact(
            invocation.tool_name, int(invocation.tool_version)
        )
        assert definition is not None
        encoded = _canonical(output.model_dump(mode="json"))
        if len(encoded) > definition.max_output_bytes:
            safe_error_code = "tool_output_oversized"
        else:
            summary, evidence = _safe_projection(output, invocation.tool_name)
            invocation.status = "succeeded"
            invocation.safe_result_summary = summary
            invocation.evidence_references = evidence_references or evidence
            step.status = "succeeded"
    if safe_error_code is not None:
        invocation.status = (
            "timed_out" if safe_error_code == "tool_timeout" else "failed"
        )
        invocation.safe_error_code = safe_error_code
        definition = AGENT_TOOL_REGISTRY.get_exact(
            invocation.tool_name, int(invocation.tool_version)
        )
        retryable = (
            definition is not None
            and invocation.attempt == 0
            and classify_retry(
                safe_error_code,
                authority=invocation.authority,
                idempotency=definition.idempotency.value,
            )
            == RetryClass.SAFE_TRANSIENT_READ
        )
        step.status = "running" if retryable else "failed"
    invocation.finished_at = now
    if step.status != "running":
        step.finished_at = now
    repository.append_agent_event(
        session,
        run_id=run.id,
        step_id=step.id,
        invocation_id=invocation.id,
        event_type="tool_invocation.finished",
        safe_code=safe_error_code or "tool_invocation_succeeded",
        safe_message=(
            "tool invocation failed" if safe_error_code else "tool invocation succeeded"
        ),
        metadata={"ordinal": step.ordinal, "status": invocation.status},
        correlation_id=run.correlation_id,
        occurred_at=now,
    )
    if safe_error_code is not None and step.status == "failed":
        service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.FAILED,
            now=now,
            safe_error_code=safe_error_code,
        )
    return safe_error_code is None or step.status == "running"


def complete_run(session: Session, claim: ExecutionClaim) -> AgentRun | None:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return None
    steps = repository.list_agent_steps_for_update(session, run.id)
    if not steps or any(step.status != "succeeded" for step in steps):
        return None
    if is_research(run.agent_kind, run.agent_version) and not any(
        event.event_type == "research.result"
        for event in repository.list_agent_events(session, run.id, limit=1000)
    ):
        return service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.FAILED,
            safe_error_code="research_result_missing",
        )
    faults.fire(faults.FaultPoint.BEFORE_RUN_COMPLETION)
    return service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.COMPLETED,
    )


def call_reserved_tool(
    session: Session,
    claim: ExecutionClaim,
    step: AgentStep,
    invocation: ToolInvocation,
    timeout_seconds: int,
    resolve_provider: Callable[[], EmbeddingProvider],
    capture_evidence: Callable[[str, object], None] | None = None,
) -> tuple[BaseModel | None, str | None]:
    started = monotonic()
    provider: EmbeddingProvider | None = None
    try:
        faults.fire(faults.FaultPoint.BEFORE_TOOL_CALL)
        if (
            step.tool_name == "memory.search_explained"
            and invocation.validated_input.get("mode") in {"semantic", "hybrid"}
        ):
            provider = resolve_provider()
        definition = AGENT_TOOL_REGISTRY.get_exact(
            invocation.tool_name, int(invocation.tool_version)
        )
        if definition is None:
            return None, "tool_unavailable"
        dispatch_input = definition.input_schema.model_validate_json(
            json.dumps(invocation.validated_input, separators=(",", ":")), strict=True
        ).model_dump(mode="python")
        output = dispatch_exact(
            name=invocation.tool_name,
            version=int(invocation.tool_version),
            normalized_input=dispatch_input,
            context=ToolCallContext(
                session, claim.project_scope, provider, capture_evidence
            ),
        )
        faults.fire(faults.FaultPoint.AFTER_TOOL_RETURN)
        if monotonic() - started > timeout_seconds:
            return None, "tool_timeout"
        return output, None
    except ToolUnavailableError:
        return None, "tool_unavailable"
    except ToolInputInvalidError:
        return None, "tool_input_invalid"
    except ToolOutputInvalidError:
        return None, "tool_output_invalid"
    except ProviderUnavailableError:
        return None, "tool_provider_unavailable"
    except InvalidEmbeddingResponseError:
        return None, "tool_output_invalid"
    except ProviderRequestError:
        return None, "tool_provider_failed"
    except faults.FaultInjectionError:
        raise
    except (ToolControlledFailure, SQLAlchemyError, ValueError):
        return None, "tool_controlled_failure"
    except Exception:
        return None, "tool_controlled_failure"
