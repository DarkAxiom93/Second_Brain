"""Fail-closed coordinator for exact linked automatic read-only Runs."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_planning.provider import PlanningProvider
from app.agent_runs import orchestration
from app.agent_runs import service as run_service
from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.automations.catalog import (
    AutomaticAgentDefinition,
    get_automatic_agent_definition,
    get_schedulable_agent,
)
from app.daily_brief.provider import DailyBriefProvider
from app.embeddings.provider import EmbeddingProvider
from app.models.agent_runtime import AgentRun
from app.models.automation import AutomationOccurrence
from app.models.project import Project
from app.repositories import automations as repository


class AutomaticEligibilityError(Exception):
    """The exact linked work no longer satisfies unattended eligibility."""


DefinitionResolver = Callable[[str, str], AutomaticAgentDefinition | None]


def _eligible_linked_run(
    session: Session,
    occurrence_id: uuid.UUID,
    definition_resolver: DefinitionResolver,
) -> tuple[uuid.UUID, AutomaticAgentDefinition]:
    observed = session.get(AutomationOccurrence, occurrence_id)
    if observed is None:
        raise AutomaticEligibilityError
    automation = repository.lock_automation(session, observed.automation_id)
    occurrence = repository.lock_occurrence(session, occurrence_id)
    if occurrence is None or occurrence.agent_run_id is None:
        raise AutomaticEligibilityError
    run = session.get(AgentRun, occurrence.agent_run_id, with_for_update=True)
    definition = definition_resolver(occurrence.agent_kind, occurrence.agent_version)
    catalog = get_schedulable_agent(occurrence.agent_kind, occurrence.agent_version)
    linked_count = session.scalar(
        select(func.count())
        .select_from(AutomationOccurrence)
        .where(AutomationOccurrence.agent_run_id == occurrence.agent_run_id)
    )
    if (
        automation is None
        or run is None
        or linked_count != 1
        or automation.lifecycle != "enabled"
        or automation.revision != occurrence.automation_revision
        or automation.schedule_revision != occurrence.schedule_revision
        or automation.execution_mode != "automatic_read_only"
        or occurrence.execution_mode != "automatic_read_only"
        or occurrence.state not in {"run_created", "completed", "failed"}
        or automation.agent_kind != occurrence.agent_kind != run.agent_kind
        or automation.agent_version != occurrence.agent_version != run.agent_version
        or automation.project_id != occurrence.project_id != run.project_id
        or catalog is None
        or (catalog.project_required and occurrence.project_id is None)
        or definition is None
        or not definition.code_owned
        or definition.authority != "read"
        or definition.registry_version != REGISTRY_VERSION
        or not definition.allowed_tools
        or any(
            AGENT_TOOL_REGISTRY.get_exact(*tool) is None
            for tool in definition.allowed_tools
        )
        or run.registry_version != REGISTRY_VERSION
        or run.policy_version != run_service.POLICY_VERSION
        or (
            run.state not in {"completed", "failed"}
            and (
                run.state in {"cancelled", "expired"}
                or datetime.now(UTC) >= run.run_deadline
            )
        )
        or (
            occurrence.project_id is not None
            and session.get(Project, occurrence.project_id) is None
        )
    ):
        raise AutomaticEligibilityError
    return run.id, definition


def coordinate_occurrence(
    session: Session,
    occurrence_id: uuid.UUID,
    *,
    resolve_planning_provider: Callable[[], PlanningProvider],
    resolve_embedding_provider: Callable[[], EmbeddingProvider],
    provider_available: Callable[[], bool],
    resolve_daily_brief_provider: Callable[[], DailyBriefProvider] | None = None,
    definition_resolver: DefinitionResolver = get_automatic_agent_definition,
) -> uuid.UUID:
    """Validate, release locks, reuse Run orchestration, then reconcile."""

    run_id, definition = _eligible_linked_run(
        session, occurrence_id, definition_resolver
    )
    run = session.get(AgentRun, run_id)
    assert run is not None
    revision = run.revision
    state = run.state
    session.commit()
    if state == "created":
        orchestration.plan_read_only_run(
            session,
            run_id,
            expected_revision=revision,
            allowed_tools=definition.allowed_tools,
            resolve_provider=resolve_planning_provider,
            provider_available=provider_available,
        )
    run = session.get(AgentRun, run_id)
    if run is not None and run.state == "ready":
        orchestration.execute_read_only_run(
            session,
            run_id,
            expected_revision=run.revision,
            allowed_tools=definition.allowed_tools,
            resolve_provider=resolve_embedding_provider,
            provider_available=provider_available,
            resolve_daily_brief_provider=resolve_daily_brief_provider,
        )
    repository.lock_occurrence(session, occurrence_id)
    from app.automations.scheduler import reconcile_linked

    reconcile_linked(session, now=datetime.now(UTC), limit=1)
    session.commit()
    return run_id
