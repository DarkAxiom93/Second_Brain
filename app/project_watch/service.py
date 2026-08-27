"""Version- and window-validated persistence for Project Watch v1."""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.automations.catalog import PROJECT_WATCH_DEFINITION
from app.models.agent_runtime import AgentEvent
from app.project_watch import changes
from app.project_watch.provider import (
    ProjectWatchOutputInvalidError,
    ProjectWatchProvider,
    ProjectWatchProviderError,
    ProjectWatchProviderRequestError,
    ProjectWatchProviderResult,
    ProjectWatchProviderTimeoutError,
    ProjectWatchProviderUnavailableError,
)
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import AgentRunState

RESULT_EVENT = "project_watch.result"


def synthesize_and_persist(
    session: Session,
    *,
    run_id: uuid.UUID,
    resolve_provider: Callable[[], ProjectWatchProvider],
) -> None:
    try:
        window = changes.derive_window(session, run_id)
        evidence = changes.collect(session, window)
    except changes.ChangeValidationError:
        _fail(session, run_id, "project_watch_evidence_invalid")
        session.commit()
        return
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return
    goal = run.goal_summary
    session.commit()
    try:
        result = (
            ProjectWatchProviderResult(status="no_meaningful_change", findings=[])
            if not evidence
            else resolve_provider().synthesize(
                goal=goal, evidence=[item.provider_value() for item in evidence]
            )
        )
        _persist(
            session, run_id=run_id, window=window, evidence=evidence, result=result
        )
        session.commit()
    except ProjectWatchProviderUnavailableError:
        session.rollback()
        _fail(session, run_id, "project_watch_provider_unavailable")
        session.commit()
    except ProjectWatchProviderTimeoutError:
        session.rollback()
        _fail(session, run_id, "project_watch_provider_timeout")
        session.commit()
    except ProjectWatchProviderRequestError:
        session.rollback()
        _fail(session, run_id, "project_watch_provider_failed")
        session.commit()
    except (
        ProjectWatchOutputInvalidError,
        ProjectWatchProviderError,
        changes.ChangeValidationError,
    ):
        session.rollback()
        _fail(session, run_id, "project_watch_result_invalid")
        session.commit()


def _persist(
    session: Session,
    *,
    run_id: uuid.UUID,
    window: changes.ChangeWindow,
    evidence: list[changes.ChangeEvidence],
    result: ProjectWatchProviderResult,
) -> None:
    session.expire_all()
    run = repository.get_agent_run_for_update(session, run_id)
    if (
        run is None
        or (run.agent_kind, run.agent_version) != ("project_watch", "1")
        or run.project_id is None
        or run.state != AgentRunState.RUNNING.value
    ):
        raise changes.ChangeValidationError
    if len(evidence) > PROJECT_WATCH_DEFINITION.max_evidence or not changes.is_current(
        session, window, evidence
    ):
        raise changes.ChangeValidationError
    by_id = {item.evidence_id: item for item in evidence}
    if result.status == "no_meaningful_change":
        if result.findings:
            raise changes.ChangeValidationError
        findings: list[dict[str, object]] = []
        citations: list[dict[str, object]] = []
    else:
        if not result.findings:
            raise changes.ChangeValidationError
        used: list[str] = []
        findings = []
        for finding in result.findings:
            if len(set(finding.evidence_ids)) != len(finding.evidence_ids) or any(
                item not in by_id for item in finding.evidence_ids
            ):
                raise changes.ChangeValidationError
            used.extend(item for item in finding.evidence_ids if item not in used)
            findings.append(
                {
                    "text": finding.text,
                    "citation_numbers": [
                        used.index(item) + 1 for item in finding.evidence_ids
                    ],
                }
            )
        if len(used) > PROJECT_WATCH_DEFINITION.max_citations:
            raise changes.ChangeValidationError
        citations = [
            {
                "number": index,
                "entity_type": by_id[item].entity_type,
                "entity_id": str(by_id[item].entity_id),
                "version": by_id[item].version,
            }
            for index, item in enumerate(used, 1)
        ]
    value: dict[str, object] = {
        "status": result.status,
        "findings": findings,
        "citations": citations,
        "window_start": window.lower.isoformat(),
        "window_end": window.upper.isoformat(),
    }
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type=RESULT_EVENT,
        safe_code="project_watch_result",
        safe_message="bounded Project Watch result produced",
        metadata=value,
        correlation_id=run.correlation_id,
        occurred_at=run_service.utc_now(),
    )


def _fail(session: Session, run_id: uuid.UUID, code: str) -> None:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is not None and run.state == AgentRunState.RUNNING.value:
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
