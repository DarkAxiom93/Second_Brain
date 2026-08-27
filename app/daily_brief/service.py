"""Version-validated persistence for scheduled Daily Brief results."""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.automations.catalog import DAILY_BRIEF_DEFINITION
from app.daily_brief import events as event_evidence
from app.daily_brief.provider import (
    DailyBriefOutputInvalidError,
    DailyBriefProvider,
    DailyBriefProviderError,
    DailyBriefProviderRequestError,
    DailyBriefProviderResult,
    DailyBriefProviderTimeoutError,
    DailyBriefProviderUnavailableError,
)
from app.models.agent_runtime import AgentEvent
from app.repositories import agent_runtime as repository
from app.research import service as evidence_service
from app.schemas.agent_run import AgentRunState

RESULT_EVENT = "daily_brief.result"
INSUFFICIENT = "The reviewed local evidence is insufficient for a safe Daily Brief."


def is_daily_brief(kind: str, version: str) -> bool:
    return (kind, version) == ("daily_brief", "1")


def synthesize_and_persist(
    session: Session,
    *,
    run_id: uuid.UUID,
    evidence: list[evidence_service.CollectedEvidence],
    resolve_provider: Callable[[], DailyBriefProvider],
) -> None:
    if len(evidence) > DAILY_BRIEF_DEFINITION.max_evidence:
        _fail(session, run_id, "daily_brief_evidence_invalid")
        session.commit()
        return
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return
    goal = run.goal_summary
    application_events = event_evidence.collect(
        session,
        project_id=run.project_id,
        offset=len(evidence),
        limit=DAILY_BRIEF_DEFINITION.max_evidence - len(evidence),
    )
    all_evidence: list[
        evidence_service.CollectedEvidence | event_evidence.ApplicationEventEvidence
    ] = [*evidence, *application_events]
    session.commit()
    try:
        result = (
            DailyBriefProviderResult(
                status="insufficient_evidence", claims=[], insufficiency=INSUFFICIENT
            )
            if not all_evidence
            else resolve_provider().synthesize(
                goal=goal, evidence=[item.provider_value() for item in all_evidence]
            )
        )
        _persist(session, run_id=run_id, evidence=all_evidence, result=result)
        session.commit()
    except DailyBriefProviderUnavailableError:
        session.rollback()
        _fail(session, run_id, "daily_brief_provider_unavailable")
        session.commit()
    except DailyBriefProviderTimeoutError:
        session.rollback()
        _fail(session, run_id, "daily_brief_provider_timeout")
        session.commit()
    except DailyBriefProviderRequestError:
        session.rollback()
        _fail(session, run_id, "daily_brief_provider_failed")
        session.commit()
    except (
        DailyBriefOutputInvalidError,
        DailyBriefProviderError,
        evidence_service.ResearchValidationError,
    ):
        session.rollback()
        _fail(session, run_id, "daily_brief_result_invalid")
        session.commit()


def _persist(
    session: Session,
    *,
    run_id: uuid.UUID,
    evidence: list[
        evidence_service.CollectedEvidence | event_evidence.ApplicationEventEvidence
    ],
    result: DailyBriefProviderResult,
) -> None:
    session.expire_all()
    run = repository.get_agent_run_for_update(session, run_id)
    if (
        run is None
        or not is_daily_brief(run.agent_kind, run.agent_version)
        or run.state != AgentRunState.RUNNING.value
    ):
        raise evidence_service.ResearchValidationError
    knowledge = [
        item
        for item in evidence
        if isinstance(item, evidence_service.CollectedEvidence)
    ]
    application_events = [
        item
        for item in evidence
        if isinstance(item, event_evidence.ApplicationEventEvidence)
    ]
    if not evidence_service.evidence_is_current(session, run, knowledge) or not (
        event_evidence.is_current(
            session, project_id=run.project_id, evidence=application_events
        )
    ):
        raise evidence_service.ResearchValidationError
    value = evidence_service.validate_result(result, evidence)
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type=RESULT_EVENT,
        safe_code="daily_brief_result",
        safe_message="bounded Daily Brief result produced",
        metadata=value,
        correlation_id=run.correlation_id,
        occurred_at=run_service.utc_now(),
    )


def _fail(session: Session, run_id: uuid.UUID, code: str) -> None:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return
    run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.FAILED,
        safe_error_code=code,
    )


def get_result(session: Session, run_id: uuid.UUID) -> dict[str, Any] | None:
    event = session.scalar(
        select(AgentEvent)
        .where(AgentEvent.run_id == run_id, AgentEvent.event_type == RESULT_EVENT)
        .order_by(AgentEvent.sequence.desc())
        .limit(1)
    )
    return None if event is None else event.safe_metadata
