"""Checkpoint 80 automatic coordinator and mutation-boundary proofs."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_planning.provider import FakePlanningProvider, PlanningResult
from app.agent_runs import service as run_service
from app.automations import coordinator
from app.automations.catalog import AutomaticAgentDefinition
from app.db.session import get_engine
from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.models.memory import Memory
from app.models.memory_proposal import MemoryProposal
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.schemas.agent_run import AgentRunCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_runtime(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (
            AutomationNotification,
            AutomationOccurrence,
            ToolInvocation,
            AgentStep,
            AgentEvent,
            AgentRun,
            Automation,
        ):
            session.execute(delete(model))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in (
            AutomationNotification,
            AutomationOccurrence,
            ToolInvocation,
            AgentStep,
            AgentEvent,
            AgentRun,
            Automation,
        ):
            session.execute(delete(model))
        session.commit()


def _linked(session: Session) -> tuple[AutomationOccurrence, AgentRun]:
    now = datetime.now(UTC).replace(microsecond=0)
    automation = Automation(
        label="Injected fixed definition",
        automation_kind="scheduled_agent",
        agent_kind="daily_brief",
        agent_version="1",
        project_id=None,
        lifecycle="enabled",
        revision=4,
        execution_mode="automatic_read_only",
        schedule_kind="daily",
        timezone_name="UTC",
        local_time=time(8),
        weekdays=[],
        interval_count=1,
        missed_run_policy="run_once",
        retry_limit=3,
        capacity_limit=1,
        schedule_revision=0,
        next_occurrence_at=now + timedelta(days=1),
    )
    session.add(automation)
    session.flush()
    request = AgentRunCreate(
        project_id=None,
        agent_kind="daily_brief",
        agent_version="1",
        goal_summary="Scheduled daily_brief: Injected fixed definition",
    )
    run = run_service.create_run(
        session,
        request,
        idempotency_key_hash=run_service.hash_idempotency_key(f"cp80-{uuid.uuid4()}"),
        fingerprint=run_service.normalized_request_fingerprint(request),
        now=now,
    ).run
    occurrence = AutomationOccurrence(
        automation_id=automation.id,
        schedule_revision=0,
        scheduled_at=now,
        scheduled_local_date=now.date(),
        scheduled_local_time=now.time().replace(tzinfo=None),
        scheduled_utc_offset_minutes=0,
        timezone_name="UTC",
        occurrence_key=f"cp80:{uuid.uuid4()}",
        state="run_created",
        revision=1,
        automation_revision=4,
        automation_kind="scheduled_agent",
        automation_label=automation.label,
        agent_kind="daily_brief",
        agent_version="1",
        execution_mode="automatic_read_only",
        project_id=None,
        agent_run_id=run.id,
    )
    session.add(occurrence)
    session.commit()
    return occurrence, run


def _definition(authority: str = "read") -> AutomaticAgentDefinition:
    return AutomaticAgentDefinition(
        kind="daily_brief",
        version="1",
        authority=authority,
        registry_version="agent-tools-v1",
        allowed_tools=(("memory.search_explained", 1),),
    )


def _plan(goal: str) -> PlanningResult:
    return PlanningResult.model_validate(
        {
            "goal_summary": goal,
            "steps": [
                {
                    "purpose": "Find matching reviewed memories",
                    "tool_name": "memory.search_explained",
                    "tool_version": 1,
                    "candidate_input": {
                        "query": "brief",
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
                    "expected_evidence": ["Bounded local identifiers"],
                    "success_condition": "The bounded read returns",
                    "stop_condition": "Stop after one read",
                }
            ],
        },
        strict=True,
    )


def test_unimplemented_and_non_read_definitions_fail_before_planning() -> None:
    with Session(get_engine()) as session:
        occurrence, _ = _linked(session)
        provider = FakePlanningProvider(_plan("unused"))
        for resolver in (lambda _k, _v: None, lambda _k, _v: _definition("propose")):
            with pytest.raises(coordinator.AutomaticEligibilityError):
                coordinator.coordinate_occurrence(
                    session,
                    occurrence.id,
                    resolve_planning_provider=lambda: provider,
                    resolve_embedding_provider=lambda: pytest.fail(
                        "tool provider used"
                    ),
                    provider_available=lambda: False,
                    definition_resolver=resolver,
                )
            session.rollback()
        assert provider.calls == 0


def test_fixed_read_only_definition_executes_once_replays_and_mutates_no_domain() -> (
    None
):
    protected = (Project, Memory, Source, SourceChunk, MemoryProposal, ApprovalRequest)
    with Session(get_engine()) as session:
        occurrence, run = _linked(session)
        before = tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in protected
        )
        provider = FakePlanningProvider(_plan(run.goal_summary))
        arguments = dict(
            resolve_planning_provider=lambda: provider,
            resolve_embedding_provider=lambda: pytest.fail(
                "lexical read resolved provider"
            ),
            provider_available=lambda: False,
            definition_resolver=lambda _k, _v: _definition(),
        )
        coordinator.coordinate_occurrence(session, occurrence.id, **arguments)
        coordinator.coordinate_occurrence(session, occurrence.id, **arguments)
        after = tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in protected
        )
        assert before == after
        assert provider.calls == 1
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 1
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 1
        session.refresh(occurrence)
        assert occurrence.state == "completed"
