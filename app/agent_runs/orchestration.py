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
from app.embeddings.provider import EmbeddingProvider


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
        output, safe_error = executor.call_reserved_tool(
            session,
            claim,
            step,
            invocation,
            timeout_seconds,
            resolve_provider,
        )
        session.rollback()
        succeeded = executor.finalize_invocation(
            session,
            claim,
            step_id=step.id,
            invocation_id=invocation.id,
            output=output,
            safe_error_code=safe_error,
        )
        session.commit()
        if not succeeded:
            break
    executor.complete_run(session, claim)
    session.commit()
