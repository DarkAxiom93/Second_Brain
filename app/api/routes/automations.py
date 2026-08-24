"""Loopback Automation definition, lifecycle, and calculation-only APIs."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.automations import service
from app.automations.schedule import ScheduleCalculationError, preview
from app.db.dependencies import get_db_session
from app.models.automation import Automation
from app.repositories import automations as repository
from app.schemas.automation import (
    AutomationCreate,
    AutomationRead,
    AutomationRevisionRequest,
    AutomationUpdate,
    SchedulePointRead,
    SchedulePreviewRequest,
)

router = APIRouter(prefix="/automations", tags=["automations"])


def _error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _handle_mutation(
    session: Session, operation: Callable[[], Automation]
) -> Automation:
    try:
        automation = operation()
        session.commit()
        session.refresh(automation)
        return automation
    except service.AutomationNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "automation not found") from None
    except service.AutomationProjectNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "project not found") from None
    except service.AutomationRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "automation revision conflict") from None
    except service.AutomationTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "automation transition conflict"
        ) from None
    except (service.AutomationDefinitionError, ScheduleCalculationError) as exc:
        session.rollback()
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
def create_automation(
    request: AutomationCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _handle_mutation(
        session, lambda: service.create_automation(session, request)
    )


@router.get("", response_model=list[AutomationRead])
def list_automations(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Automation]:
    try:
        return repository.list_automations(session, limit=limit, offset=offset)
    except SQLAlchemyError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/preview", response_model=list[SchedulePointRead])
def preview_schedule(request: SchedulePreviewRequest) -> list[SchedulePointRead]:
    try:
        points = preview(
            service.schedule_definition(request.schedule),
            after_utc=request.after_utc,
            count=request.count,
        )
    except ScheduleCalculationError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return [
        SchedulePointRead.model_validate(point, from_attributes=True)
        for point in points
    ]


@router.get("/{automation_id}", response_model=AutomationRead)
def get_automation(
    automation_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    try:
        automation = repository.get_automation(session, automation_id)
    except SQLAlchemyError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
    if automation is None:
        raise _error(status.HTTP_404_NOT_FOUND, "automation not found")
    return automation


@router.patch("/{automation_id}", response_model=AutomationRead)
def update_automation(
    automation_id: uuid.UUID,
    request: AutomationUpdate,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _handle_mutation(
        session, lambda: service.update_automation(session, automation_id, request)
    )


def _lifecycle_route(
    operation: Callable[[Session, uuid.UUID, int], Automation],
    session: Session,
    automation_id: uuid.UUID,
    request: AutomationRevisionRequest,
) -> Automation:
    return _handle_mutation(
        session, lambda: operation(session, automation_id, request.expected_revision)
    )


@router.post("/{automation_id}/enable", response_model=AutomationRead)
def enable_automation(
    automation_id: uuid.UUID,
    request: AutomationRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _lifecycle_route(service.enable_automation, session, automation_id, request)


@router.post("/{automation_id}/pause", response_model=AutomationRead)
def pause_automation(
    automation_id: uuid.UUID,
    request: AutomationRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _lifecycle_route(service.pause_automation, session, automation_id, request)


@router.post("/{automation_id}/resume", response_model=AutomationRead)
def resume_automation(
    automation_id: uuid.UUID,
    request: AutomationRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _lifecycle_route(service.resume_automation, session, automation_id, request)


@router.post("/{automation_id}/cancel", response_model=AutomationRead)
def cancel_automation(
    automation_id: uuid.UUID,
    request: AutomationRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> Automation:
    return _lifecycle_route(service.cancel_automation, session, automation_id, request)
