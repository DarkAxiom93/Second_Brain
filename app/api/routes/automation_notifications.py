"""Safe loopback-only Automation notification inbox APIs."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.models.automation import AutomationNotification
from app.repositories import automations as repository
from app.schemas.automation import AutomationNotificationRead

router = APIRouter(prefix="/automation-notifications", tags=["automations"])


@router.get("", response_model=list[AutomationNotificationRead])
def list_notifications(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    unread_only: bool = False,
    automation_id: uuid.UUID | None = None,
) -> list[AutomationNotification]:
    try:
        return repository.list_notifications(
            session,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
            automation_id=automation_id,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{notification_id}/read", response_model=AutomationNotificationRead)
def mark_notification_read(
    notification_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AutomationNotification:
    try:
        notification = repository.lock_notification(session, notification_id)
        if notification is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            session.flush()
        session.commit()
        session.refresh(notification)
        return notification
    except HTTPException:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
