"""Synchronous bounded execution of one frozen read-only Agent Run plan."""

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_runs import service
from app.agent_tools.dispatch import (
    ToolCallContext,
    ToolControlledFailure,
    ToolInputInvalidError,
    ToolOutputInvalidError,
    ToolUnavailableError,
    dispatch_exact,
)
from app.agent_tools.policy import PolicyRejection, resolve_tool_policy
from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.embeddings import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.models.agent_runtime import AgentRun, AgentStep, ToolInvocation
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import AgentRunState


class ExecutionPlanInvalidError(Exception):
    pass


class ExecutionRegistryVersionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    run_id: uuid.UUID
    project_scope: uuid.UUID | None
    registry_version: str
    tool_call_budget: int


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
) -> ExecutionClaim:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise service.AgentRunNotFoundError
    if run.revision != expected_revision:
        raise service.AgentRunRevisionConflictError
    if run.state != AgentRunState.READY.value:
        raise service.AgentRunTransitionConflictError
    if run.registry_version != REGISTRY_VERSION:
        raise ExecutionRegistryVersionError
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
    pending = [step for step in steps if step.status == "pending"]
    if not pending:
        return None
    step = pending[0]
    if any(previous.status != "succeeded" for previous in steps[: step.ordinal]):
        raise ExecutionPlanInvalidError
    assert step.tool_name is not None and step.tool_version is not None
    total = repository.count_tool_invocations(session, run.id)
    per_tool = repository.count_tool_invocations(
        session, run.id, tool_name=step.tool_name
    )
    policy = resolve_tool_policy(
        name=step.tool_name,
        version=int(step.tool_version),
        requested_authority="read",
        candidate_input=step.normalized_input,
        captured_registry_version=run.registry_version,
        captured_run_project_scope=run.project_id,
        captured_run_tool_call_budget=run.tool_call_budget,
        total_calls_reserved=total,
        tool_calls_reserved=per_tool,
        configured_provider_available=provider_available,
        operator_aggregate_allowed=False,
    )
    now = service.utc_now()
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
        f"{run.id}:{step.id}:0:{step.tool_name}:{step.tool_version}:{input_hash}".encode(
            "ascii"
        )
    )
    invocation = repository.reserve_tool_invocation(
        session,
        ToolInvocation(
            run_id=run.id,
            step_id=step.id,
            attempt=0,
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
    return step, invocation, policy.timeout_seconds


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
        invocation.safe_error_code = "tool_result_discarded"
        invocation.finished_at = now
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
            invocation.evidence_references = evidence
            step.status = "succeeded"
    if safe_error_code is not None:
        invocation.status = (
            "timed_out" if safe_error_code == "tool_timeout" else "failed"
        )
        invocation.safe_error_code = safe_error_code
        step.status = "failed"
    invocation.finished_at = now
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
    if safe_error_code is not None:
        service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.FAILED,
            now=now,
            safe_error_code=safe_error_code,
        )
    return safe_error_code is None


def complete_run(session: Session, claim: ExecutionClaim) -> AgentRun | None:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return None
    steps = repository.list_agent_steps_for_update(session, run.id)
    if not steps or any(step.status != "succeeded" for step in steps):
        return None
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
) -> tuple[BaseModel | None, str | None]:
    started = monotonic()
    provider: EmbeddingProvider | None = None
    try:
        if (
            step.tool_name == "memory.search_explained"
            and invocation.validated_input.get("mode") in {"semantic", "hybrid"}
        ):
            provider = resolve_provider()
        output = dispatch_exact(
            name=invocation.tool_name,
            version=int(invocation.tool_version),
            normalized_input=invocation.validated_input,
            context=ToolCallContext(session, claim.project_scope, provider),
        )
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
    except (ToolControlledFailure, SQLAlchemyError, ValueError):
        return None, "tool_controlled_failure"
    except Exception:
        return None, "tool_controlled_failure"
