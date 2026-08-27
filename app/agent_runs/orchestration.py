"""Reusable synchronous orchestration over the durable Agent Run services."""

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.agent_planning import service as planning
from app.agent_planning.provider import (
    PlanningOutputInvalidError,
    PlanningProvider,
    PlanningProviderRequestError,
    PlanningProviderTimeoutError,
    PlanningProviderUnavailableError,
)
from app.agent_runs import executor
from app.daily_brief import service as daily_brief_service
from app.daily_brief.provider import DailyBriefProvider
from app.embeddings.provider import EmbeddingProvider
from app.project_watch import service as project_watch_service
from app.project_watch.provider import ProjectWatchProvider
from app.repositories import agent_runtime as repository
from app.research import service as evidence_service


def plan_read_only_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_revision: int,
    allowed_tools: tuple[tuple[str, int], ...],
    resolve_provider: Callable[[], PlanningProvider],
    provider_available: Callable[[], bool],
) -> None:
    """Plan once through the ordinary claim/validate/finalize state machine."""

    claim = planning.claim_planning(
        session,
        run_id,
        expected_revision=expected_revision,
        automatic_allowed_tools=allowed_tools,
    )
    session.commit()
    if claim is None:
        return
    try:
        result = resolve_provider().plan(
            planning.build_context(claim, automatic_allowed_tools=allowed_tools)
        )
        steps = planning.validate_plan(
            claim,
            result,
            configured_provider_available=provider_available(),
            automatic_allowed_tools=allowed_tools,
        )
    except PlanningProviderUnavailableError:
        code = "planning_provider_unavailable"
    except PlanningProviderTimeoutError:
        code = "planning_provider_timeout"
    except PlanningProviderRequestError:
        code = "planning_provider_failed"
    except (
        PlanningOutputInvalidError,
        planning.PlanningOutputRejectedError,
        planning.PlanningPolicyRejectedError,
    ):
        code = "planning_output_invalid"
    else:
        planning.finalize_plan(session, claim, steps)
        session.commit()
        return
    planning.finalize_failure(session, claim, safe_error_code=code)
    session.commit()


def execute_read_only_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    expected_revision: int,
    allowed_tools: tuple[tuple[str, int], ...],
    resolve_provider: Callable[[], EmbeddingProvider],
    provider_available: Callable[[], bool],
    resolve_daily_brief_provider: Callable[[], DailyBriefProvider] | None = None,
    resolve_project_watch_provider: Callable[[], ProjectWatchProvider] | None = None,
) -> None:
    """Execute once through ordinary reservations, dispatch, and finalization."""

    claim = executor.claim_execution(
        session,
        run_id,
        expected_revision=expected_revision,
        automatic_allowed_tools=allowed_tools,
    )
    session.commit()
    if claim is None:
        return
    collected: list[evidence_service.CollectedEvidence] = []
    daily_brief = (claim.agent_kind, claim.agent_version) == ("daily_brief", "1")
    project_watch = (claim.agent_kind, claim.agent_version) == ("project_watch", "1")
    while True:
        reserved = executor.reserve_next(
            session,
            claim,
            provider_available=provider_available(),
            automatic_allowed_tools=allowed_tools,
        )
        session.commit()
        if reserved is None:
            break
        step, invocation, timeout_seconds = reserved
        observed: list[evidence_service.ObservedEvidence] = []

        def capture_evidence(
            entity_type: str,
            row: object,
            target: list[evidence_service.ObservedEvidence] = observed,
        ) -> None:
            target.append(evidence_service.observe_entity(entity_type, row))

        output, safe_error = executor.call_reserved_tool(
            session,
            claim,
            step,
            invocation,
            timeout_seconds,
            resolve_provider,
            capture_evidence if daily_brief else None,
        )
        references: list[dict[str, object]] | None = None
        if daily_brief and output is not None and safe_error is None:
            try:
                run = repository.get_agent_run(session, claim.run_id)
                if run is None:
                    raise evidence_service.ResearchValidationError
                new_evidence = evidence_service.collect_output(
                    run=run,
                    step=step,
                    invocation=invocation,
                    output=output,
                    offset=len(collected),
                    observed=observed,
                )
                collected.extend(new_evidence)
                references = evidence_service.evidence_references(new_evidence)
            except evidence_service.ResearchValidationError:
                safe_error = "daily_brief_evidence_invalid"
        session.rollback()
        succeeded = executor.finalize_invocation(
            session,
            claim,
            step_id=step.id,
            invocation_id=invocation.id,
            output=output,
            safe_error_code=safe_error,
            evidence_references=references,
        )
        session.commit()
        if not succeeded:
            break
    if daily_brief and resolve_daily_brief_provider is not None:
        daily_brief_service.synthesize_and_persist(
            session,
            run_id=claim.run_id,
            evidence=collected,
            resolve_provider=resolve_daily_brief_provider,
        )
    if project_watch and resolve_project_watch_provider is not None:
        project_watch_service.synthesize_and_persist(
            session,
            run_id=claim.run_id,
            resolve_provider=resolve_project_watch_provider,
        )
    executor.complete_run(
        session,
        claim,
        require_daily_brief_result=(
            daily_brief and resolve_daily_brief_provider is not None
        ),
        require_project_watch_result=(
            project_watch and resolve_project_watch_provider is not None
        ),
    )
    session.commit()
