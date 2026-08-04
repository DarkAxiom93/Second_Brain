"""Manual Agent Run create, read, list, and cancel endpoints."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_planning import service as planning_service
from app.agent_planning.dependencies import (
    configured_embedding_provider_available,
    get_planning_provider,
)
from app.agent_planning.provider import (
    PlanningOutputInvalidError,
    PlanningProvider,
    PlanningProviderRequestError,
    PlanningProviderTimeoutError,
    PlanningProviderUnavailableError,
)
from app.agent_runs import service
from app.db.dependencies import get_db_session
from app.models.agent_runtime import AgentRun, AgentStep
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import (
    AgentRunCancel,
    AgentRunCreate,
    AgentRunPlanRead,
    AgentRunPlanRequest,
    AgentRunRead,
    AgentRunState,
    AgentStepRead,
)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def planning_provider_resolver() -> Callable[[], PlanningProvider]:
    return get_planning_provider


def configured_provider_availability() -> Callable[[], bool]:
    return configured_embedding_provider_available


def _error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _validate_idempotency_key(value: str) -> str:
    if (
        not 1 <= len(value) <= 128
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) > 126 for character in value)
    ):
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid Idempotency-Key")
    return value


@router.post("", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_agent_run(
    request: AgentRunCreate,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AgentRun:
    """Create one Run and its sequence-zero event atomically."""

    key_hash = service.hash_idempotency_key(_validate_idempotency_key(idempotency_key))
    fingerprint = service.normalized_request_fingerprint(request)
    try:
        result = service.create_run(
            session,
            request,
            idempotency_key_hash=key_hash,
            fingerprint=fingerprint,
        )
        session.commit()
        session.refresh(result.run)
    except service.ProjectNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "project not found") from None
    except service.IdempotencyConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT,
            "idempotency key already used with a different request",
        ) from None
    except IntegrityError:
        # A concurrent creator may win the unique hash constraint after our
        # initial lookup. Roll back the failed transaction before resolving it.
        session.rollback()
        try:
            replay_result = service.resolve_create_replay(
                session,
                idempotency_key_hash=key_hash,
                fingerprint=fingerprint,
            )
            if replay_result is None:
                raise _error(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
                )
            result = replay_result
        except service.IdempotencyConflictError:
            session.rollback()
            raise _error(
                status.HTTP_409_CONFLICT,
                "idempotency key already used with a different request",
            ) from None
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None

    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result.run


@router.get("", response_model=list[AgentRunRead])
def list_agent_runs(
    session: Annotated[Session, Depends(get_db_session)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    unassigned: Annotated[bool, Query()] = False,
    state_filter: Annotated[AgentRunState | None, Query(alias="state")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AgentRun]:
    if project_id is not None and unassigned:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "project_id and unassigned=true are mutually exclusive",
        )
    try:
        return repository.list_agent_runs(
            session,
            project_id=project_id,
            unassigned=unassigned,
            state=None if state_filter is None else state_filter.value,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.get("/{run_id}", response_model=AgentRunRead)
def get_agent_run(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRun:
    try:
        run = repository.get_agent_run(session, run_id)
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
    if run is None:
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found")
    return run


def _plan_projection(run: AgentRun, steps: list[AgentStep]) -> AgentRunPlanRead:
    return AgentRunPlanRead(
        run=AgentRunRead.model_validate(run),
        goal_summary=run.goal_summary,
        steps=[
            AgentStepRead(
                ordinal=step.ordinal,
                purpose=step.purpose,
                tool_name=step.tool_name or "",
                tool_version=int(step.tool_version or "0"),
                normalized_input=step.normalized_input,
                expected_evidence=step.expected_evidence,
                success_condition=step.success_condition,
                stop_condition=step.stop_condition,
            )
            for step in steps
        ],
    )


@router.get("/{run_id}/plan", response_model=AgentRunPlanRead)
def get_agent_run_plan(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRunPlanRead:
    try:
        run, steps = planning_service.get_frozen_plan(session, run_id)
        return _plan_projection(run, list(steps))
    except service.AgentRunNotFoundError:
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunTransitionConflictError:
        raise _error(status.HTTP_409_CONFLICT, "agent run plan not available") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{run_id}/plan", response_model=AgentRunPlanRead)
def plan_agent_run(
    run_id: uuid.UUID,
    request: AgentRunPlanRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], PlanningProvider], Depends(planning_provider_resolver)
    ],
    provider_available: Annotated[
        Callable[[], bool], Depends(configured_provider_availability)
    ],
) -> AgentRunPlanRead:
    """Claim, externally plan, validate, and atomically freeze one Run."""

    try:
        claim = planning_service.claim_planning(
            session, run_id, expected_revision=request.expected_revision
        )
        session.commit()
        if claim is None:
            run, steps = planning_service.get_frozen_plan(session, run_id)
            return _plan_projection(run, list(steps))
    except service.AgentRunNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run revision conflict") from None
    except planning_service.AgentRunRegistryVersionError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run registry version unsupported"
        ) from None
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None

    error_code: str | None = None
    error_detail: str | None = None
    try:
        provider = resolve_provider()
        result = provider.plan(planning_service.build_context(claim))
        validated_steps = planning_service.validate_plan(
            claim,
            result,
            configured_provider_available=provider_available(),
        )
    except PlanningProviderUnavailableError:
        error_code, error_detail = (
            "planning_provider_unavailable",
            "planning provider unavailable",
        )
    except PlanningProviderTimeoutError:
        error_code, error_detail = (
            "planning_provider_timeout",
            "planning provider failed",
        )
    except PlanningProviderRequestError:
        error_code, error_detail = (
            "planning_provider_failed",
            "planning provider failed",
        )
    except (PlanningOutputInvalidError, planning_service.PlanningOutputRejectedError):
        error_code, error_detail = (
            "planning_output_invalid",
            "planning provider returned an invalid plan",
        )
    except planning_service.PlanningPolicyRejectedError:
        error_code, error_detail = (
            "planning_policy_rejected",
            "planning provider returned an invalid plan",
        )

    if error_code is not None:
        try:
            won = planning_service.finalize_failure(
                session, claim, safe_error_code=error_code
            )
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
        if not won:
            raise _error(status.HTTP_409_CONFLICT, "agent run transition conflict")
        assert error_detail is not None
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error_code == "planning_provider_unavailable"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise _error(code, error_detail)

    try:
        run = planning_service.finalize_plan(session, claim, validated_steps)
        session.commit()
        session.refresh(run)
        persisted = repository.list_agent_steps(session, run.id, limit=13)
        return _plan_projection(run, list(persisted))
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{run_id}/cancel", response_model=AgentRunRead)
def cancel_agent_run(
    run_id: uuid.UUID,
    request: AgentRunCancel,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRun:
    try:
        run = service.cancel_run(
            session, run_id, expected_revision=request.expected_revision
        )
        session.commit()
        session.refresh(run)
        return run
    except service.AgentRunNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run revision conflict") from None
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
