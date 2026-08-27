"""Claim, validate, and atomically freeze one Agent Run plan."""

import re
import uuid
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent_planning.provider import PlanningContext, PlanningResult
from app.agent_runs import service as run_service
from app.agent_tools.policy import PolicyRejection, resolve_tool_policy
from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.automations.catalog import is_reserved_automation_agent_identity
from app.curator.catalog import CURATOR_TOOLS, is_curator, is_unknown_curator
from app.models.agent_runtime import AgentRun, AgentStep
from app.repositories import agent_runtime as repository
from app.research.catalog import RESEARCH_TOOLS, is_research, is_unknown_research
from app.schemas.agent_run import AgentRunState

_FORBIDDEN_REQUEST = re.compile(
    r"\b(?:run|execute|invoke|use|open|write|modify|install|access|connect|query)\b"
    r".{0,40}\b(?:sql|shell|powershell|python|filesystem|file|browser|git|"
    r"dependency|credential|environment|connector|transaction|http|network)\b",
    re.IGNORECASE,
)


class PlanningPolicyRejectedError(Exception):
    pass


class PlanningOutputRejectedError(Exception):
    pass


class AgentRunRegistryVersionError(Exception):
    pass


class AgentDefinitionUnsupportedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PlanningClaim:
    run_id: uuid.UUID
    goal_summary: str
    project_id: uuid.UUID | None
    registry_version: str
    policy_version: str
    step_budget: int
    tool_call_budget: int
    retry_budget: int
    planning_revision: int
    agent_kind: str = "manual"
    agent_version: str = "1"


@dataclass(frozen=True, slots=True)
class ValidatedStep:
    ordinal: int
    purpose: str
    tool_name: str
    tool_version: int
    normalized_input: dict[str, Any]
    expected_evidence: list[str]
    success_condition: str
    stop_condition: str


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def claim_planning(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_revision: int,
    automatic_allowed_tools: tuple[tuple[str, int], ...] | None = None,
) -> PlanningClaim | None:
    """Lock and reserve planning. None means a complete ready plan is replayed."""

    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise run_service.AgentRunNotFoundError
    if (
        is_reserved_automation_agent_identity(run.agent_kind, run.agent_version)
        or (run.agent_kind, run.agent_version)
        in {("daily_brief", "1"), ("project_watch", "1")}
    ) and automatic_allowed_tools is None:
        raise AgentDefinitionUnsupportedError
    if run.state == AgentRunState.READY.value:
        steps = repository.list_agent_steps(session, run.id, limit=13)
        if _is_complete_plan(run, steps):
            return None
        raise run_service.AgentRunTransitionConflictError
    if run.revision != expected_revision:
        raise run_service.AgentRunRevisionConflictError
    if run.registry_version != REGISTRY_VERSION:
        raise AgentRunRegistryVersionError
    if is_unknown_research(run.agent_kind, run.agent_version) or is_unknown_curator(
        run.agent_kind, run.agent_version
    ):
        raise AgentDefinitionUnsupportedError
    if run.state != AgentRunState.CREATED.value:
        raise run_service.AgentRunTransitionConflictError
    claimed = run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.CREATED,
        expected_revision=expected_revision,
        new_state=AgentRunState.PLANNING,
    )
    return PlanningClaim(
        run_id=claimed.id,
        goal_summary=claimed.goal_summary,
        project_id=claimed.project_id,
        registry_version=claimed.registry_version,
        policy_version=claimed.policy_version,
        step_budget=claimed.step_budget,
        tool_call_budget=claimed.tool_call_budget,
        retry_budget=claimed.retry_budget,
        planning_revision=claimed.revision,
        agent_kind=claimed.agent_kind,
        agent_version=claimed.agent_version,
    )


def build_context(
    claim: PlanningClaim,
    *,
    automatic_allowed_tools: tuple[tuple[str, int], ...] | None = None,
) -> PlanningContext:
    permitted_tools: list[dict[str, Any]] = []
    allowed = automatic_allowed_tools or (
        RESEARCH_TOOLS
        if is_research(claim.agent_kind, claim.agent_version)
        else (
            CURATOR_TOOLS if is_curator(claim.agent_kind, claim.agent_version) else None
        )
    )
    definitions = (
        [
            definition
            for identity in allowed
            if (definition := AGENT_TOOL_REGISTRY.get_exact(*identity)) is not None
        ]
        if allowed is not None
        else list(AGENT_TOOL_REGISTRY.inventory)
    )
    for definition in definitions:
        permitted_tools.append(
            {
                "name": definition.name,
                "version": definition.version,
                "description": definition.description,
                "authority": definition.authority.value,
                "scope_mode": definition.scope_mode.value,
                "provider_mode": definition.provider_mode.value,
                "network_mode": definition.network_mode.value,
                "calls_per_run": definition.calls_per_run,
                "input_schema": definition.input_schema.model_json_schema(),
            }
        )
    return PlanningContext(
        goal_summary=claim.goal_summary,
        scope=(
            {"kind": "unassigned"}
            if claim.project_id is None
            else {"kind": "project", "project_id": str(claim.project_id)}
        ),
        registry_version=claim.registry_version,
        policy_version=claim.policy_version,
        budgets={
            "step_budget": claim.step_budget,
            "tool_call_budget": claim.tool_call_budget,
            "retry_budget": claim.retry_budget,
            "maximum_plan_steps": min(claim.step_budget, 12),
        },
        permitted_tools=permitted_tools,
        output_contract=PlanningResult.model_json_schema(),
    )


def validate_plan(
    claim: PlanningClaim,
    result: PlanningResult,
    *,
    configured_provider_available: bool,
    automatic_allowed_tools: tuple[tuple[str, int], ...] | None = None,
) -> list[ValidatedStep]:
    try:
        plan = PlanningResult.model_validate(result, strict=True)
    except (ValidationError, TypeError, ValueError):
        raise PlanningOutputRejectedError from None
    if plan.goal_summary != claim.goal_summary:
        raise PlanningOutputRejectedError
    maximum = min(claim.step_budget, 12)
    if not 1 <= len(plan.steps) <= maximum:
        raise PlanningOutputRejectedError

    per_tool: Counter[tuple[str, int]] = Counter()
    allowed = automatic_allowed_tools or (
        RESEARCH_TOOLS
        if is_research(claim.agent_kind, claim.agent_version)
        else (
            CURATOR_TOOLS if is_curator(claim.agent_kind, claim.agent_version) else None
        )
    )
    seen: set[tuple[str, int, str]] = set()
    validated: list[ValidatedStep] = []
    import json

    for ordinal, step in enumerate(plan.steps):
        if any(
            _FORBIDDEN_REQUEST.search(text)
            for text in (
                step.purpose,
                step.success_condition,
                step.stop_condition,
                *step.expected_evidence,
            )
        ):
            raise PlanningPolicyRejectedError
        identity = (step.tool_name, step.tool_version)
        if allowed is not None and identity not in allowed:
            raise PlanningPolicyRejectedError
        candidate_input: object = step.candidate_input
        definition = AGENT_TOOL_REGISTRY.get_exact(*identity)
        if definition is not None:
            try:
                candidate_input = definition.input_schema.model_validate_json(
                    json.dumps(step.candidate_input, separators=(",", ":")),
                    strict=True,
                ).model_dump(mode="python")
            except (ValidationError, TypeError, ValueError):
                raise PlanningPolicyRejectedError from None
        resolved = resolve_tool_policy(
            name=step.tool_name,
            version=step.tool_version,
            requested_authority="read",
            candidate_input=candidate_input,
            captured_registry_version=claim.registry_version,
            captured_run_project_scope=claim.project_id,
            captured_run_tool_call_budget=claim.tool_call_budget,
            total_calls_reserved=ordinal,
            tool_calls_reserved=per_tool[identity],
            configured_provider_available=configured_provider_available,
            operator_aggregate_allowed=False,
        )
        if isinstance(resolved, PolicyRejection):
            raise PlanningPolicyRejectedError
        normalized = _jsonable(resolved.normalized_input)
        assert isinstance(normalized, dict)
        signature = (
            step.tool_name,
            step.tool_version,
            json.dumps(normalized, sort_keys=True, separators=(",", ":")),
        )
        if signature in seen:
            raise PlanningPolicyRejectedError
        seen.add(signature)
        per_tool[identity] += 1
        validated.append(
            ValidatedStep(
                ordinal=ordinal,
                purpose=step.purpose,
                tool_name=resolved.name,
                tool_version=resolved.version,
                normalized_input=normalized,
                expected_evidence=list(step.expected_evidence),
                success_condition=step.success_condition,
                stop_condition=step.stop_condition,
            )
        )
    return validated


def finalize_plan(
    session: Session, claim: PlanningClaim, steps: list[ValidatedStep]
) -> AgentRun:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None:
        raise run_service.AgentRunNotFoundError
    if (
        run.state != AgentRunState.PLANNING.value
        or run.revision != claim.planning_revision
        or repository.count_agent_steps(session, run.id) != 0
    ):
        raise run_service.AgentRunTransitionConflictError
    for step in steps:
        repository.insert_agent_step(
            session,
            AgentStep(
                run_id=run.id,
                ordinal=step.ordinal,
                purpose=step.purpose,
                tool_name=step.tool_name,
                tool_version=str(step.tool_version),
                normalized_input=step.normalized_input,
                expected_evidence=step.expected_evidence,
                success_condition=step.success_condition,
                stop_condition=step.stop_condition,
                status="pending",
            ),
        )
    return run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.PLANNING,
        expected_revision=claim.planning_revision,
        new_state=AgentRunState.READY,
    )


def finalize_failure(
    session: Session,
    claim: PlanningClaim,
    *,
    safe_error_code: str,
) -> bool:
    run = repository.get_agent_run_for_update(session, claim.run_id)
    if run is None:
        raise run_service.AgentRunNotFoundError
    if (
        run.state != AgentRunState.PLANNING.value
        or run.revision != claim.planning_revision
    ):
        return False
    run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.PLANNING,
        expected_revision=claim.planning_revision,
        new_state=AgentRunState.FAILED,
        safe_error_code=safe_error_code,
    )
    return True


def _is_complete_plan(run: AgentRun, steps: list[AgentStep]) -> bool:
    maximum = min(run.step_budget, 12)
    return (
        1 <= len(steps) <= maximum
        and [step.ordinal for step in steps] == list(range(len(steps)))
        and all(step.status == "pending" and step.tool_name for step in steps)
    )


def get_frozen_plan(
    session: Session, run_id: uuid.UUID
) -> tuple[AgentRun, list[AgentStep]]:
    run = repository.get_agent_run(session, run_id)
    if run is None:
        raise run_service.AgentRunNotFoundError
    steps = repository.list_agent_steps(session, run_id, limit=13)
    if run.state != AgentRunState.READY.value or not _is_complete_plan(run, steps):
        raise run_service.AgentRunTransitionConflictError
    return run, steps
