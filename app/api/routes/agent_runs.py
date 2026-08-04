"""Manual Agent Run create, read, list, and cancel endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_runs import service
from app.db.dependencies import get_db_session
from app.models.agent_runtime import AgentRun
from app.repositories import agent_runtime as repository
from app.schemas.agent_run import (
    AgentRunCancel,
    AgentRunCreate,
    AgentRunRead,
    AgentRunState,
)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


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
