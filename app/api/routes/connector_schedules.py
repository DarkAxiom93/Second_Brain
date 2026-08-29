"""Loopback connector refresh schedule management and safe history."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.connectors import schedules
from app.db.dependencies import get_db_session
from app.models.connector_schedule import (
    ConnectorRefreshNotification,
    ConnectorRefreshOccurrence,
    ConnectorRefreshSchedule,
)
from app.repositories import connector_schedules as repository
from app.schemas.connector_schedule import (
    ConnectorNotificationRead,
    ConnectorOccurrenceRead,
    ConnectorScheduleCreate,
    ConnectorScheduleRead,
    ConnectorScheduleRevisionRequest,
    ConnectorScheduleUpdate,
)

router = APIRouter(tags=["connector-refresh-schedules"])


def _mutate(
    session: Session, operation: Callable[[], ConnectorRefreshSchedule]
) -> ConnectorRefreshSchedule:
    try:
        row = operation()
        session.commit()
        session.refresh(row)
        return row
    except schedules.ScheduleNotFoundError:
        session.rollback()
        raise HTTPException(404, "connector schedule not found") from None
    except schedules.ScheduleRevisionConflictError:
        session.rollback()
        raise HTTPException(409, "connector schedule revision conflict") from None
    except (schedules.ScheduleConflictError, IntegrityError):
        session.rollback()
        raise HTTPException(409, "connector schedule conflict") from None
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "database unavailable") from None


@router.post(
    "/connector-accounts/{account_id}/refresh-schedule",
    response_model=ConnectorScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    account_id: uuid.UUID,
    request: ConnectorScheduleCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _mutate(session, lambda: schedules.create(session, account_id, request))


@router.get(
    "/connector-accounts/{account_id}/refresh-schedule",
    response_model=ConnectorScheduleRead,
)
def get_schedule(
    account_id: uuid.UUID, session: Annotated[Session, Depends(get_db_session)]
) -> ConnectorRefreshSchedule:
    row = repository.get_account_schedule(session, account_id)
    if row is None:
        raise HTTPException(404, "connector schedule not found")
    return row


@router.patch(
    "/connector-refresh-schedules/{schedule_id}", response_model=ConnectorScheduleRead
)
def update_schedule(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleUpdate,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _mutate(session, lambda: schedules.update(session, schedule_id, request))


def _action(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleRevisionRequest,
    session: Session,
    action: str,
) -> ConnectorRefreshSchedule:
    return _mutate(
        session,
        lambda: schedules.transition(
            session, schedule_id, request.expected_revision, action
        ),
    )


@router.post(
    "/connector-refresh-schedules/{schedule_id}/enable",
    response_model=ConnectorScheduleRead,
)
def enable(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _action(schedule_id, request, session, "enable")


@router.post(
    "/connector-refresh-schedules/{schedule_id}/pause",
    response_model=ConnectorScheduleRead,
)
def pause(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _action(schedule_id, request, session, "pause")


@router.post(
    "/connector-refresh-schedules/{schedule_id}/resume",
    response_model=ConnectorScheduleRead,
)
def resume(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _action(schedule_id, request, session, "resume")


@router.post(
    "/connector-refresh-schedules/{schedule_id}/cancel",
    response_model=ConnectorScheduleRead,
)
def cancel(
    schedule_id: uuid.UUID,
    request: ConnectorScheduleRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorRefreshSchedule:
    return _action(schedule_id, request, session, "cancel")


@router.get(
    "/connector-refresh-schedules/{schedule_id}/occurrences",
    response_model=list[ConnectorOccurrenceRead],
)
def history(
    schedule_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConnectorRefreshOccurrence]:
    if repository.get_schedule(session, schedule_id) is None:
        raise HTTPException(404, "connector schedule not found")
    return repository.list_history(session, schedule_id, limit, offset)


@router.get(
    "/connector-refresh-schedules/{schedule_id}/notifications",
    response_model=list[ConnectorNotificationRead],
)
def notifications(
    schedule_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConnectorRefreshNotification]:
    if repository.get_schedule(session, schedule_id) is None:
        raise HTTPException(404, "connector schedule not found")
    return repository.list_notifications(session, schedule_id, limit, offset)
