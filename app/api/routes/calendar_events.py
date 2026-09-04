"""Local-only scoped Calendar External Context routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.calendar import query
from app.db.dependencies import get_db_session
from app.schemas.calendar import CalendarEventPage, CalendarEventRead

router = APIRouter(prefix="/calendar-events", tags=["calendar-events"])


def _scope(value: str) -> query.CalendarExternalScope:
    try:
        return query.parse_scope(value)
    except ValueError:
        raise HTTPException(422, "invalid calendar event scope") from None


@router.get("", response_model=CalendarEventPage)
def list_calendar_events(
    scope: str,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CalendarEventPage:
    try:
        return query.list_events(session, _scope(scope), limit=limit, cursor=cursor)
    except query.CalendarEventNotFoundError:
        raise HTTPException(404, "calendar event scope not found") from None
    except query.CalendarEventCursorError:
        raise HTTPException(422, "invalid calendar event cursor") from None
    except SQLAlchemyError:
        raise HTTPException(503, "database unavailable") from None


@router.get("/{event_id}", response_model=CalendarEventRead)
def get_calendar_event(
    event_id: uuid.UUID,
    scope: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarEventRead:
    try:
        return query.get_event(session, _scope(scope), event_id)
    except query.CalendarEventNotFoundError:
        raise HTTPException(404, "calendar event not found") from None
    except SQLAlchemyError:
        raise HTTPException(503, "database unavailable") from None
