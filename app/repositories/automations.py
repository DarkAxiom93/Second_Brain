"""Caller-transaction-owned persistence primitives for Automation metadata."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)


class AutomationOwnershipError(Exception):
    """A child row does not belong to its supplied Automation."""


def create_automation(session: Session, automation: Automation) -> Automation:
    session.add(automation)
    session.flush()
    session.refresh(automation)
    return automation


def get_automation(session: Session, automation_id: uuid.UUID) -> Automation | None:
    return session.scalar(select(Automation).where(Automation.id == automation_id))


def lock_automation(session: Session, automation_id: uuid.UUID) -> Automation | None:
    """Lock one Automation for a caller-owned lifecycle transaction."""

    return session.scalar(
        select(Automation)
        .where(Automation.id == automation_id)
        .with_for_update(of=Automation)
    )


def list_automations(
    session: Session, *, limit: int, offset: int = 0
) -> list[Automation]:
    """Return a bounded newest-first page with a stable UUID tie-breaker."""

    return list(
        session.scalars(
            select(Automation)
            .order_by(Automation.created_at.desc(), Automation.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


def insert_automation_occurrence(
    session: Session, occurrence: AutomationOccurrence
) -> AutomationOccurrence:
    if get_automation(session, occurrence.automation_id) is None:
        raise AutomationOwnershipError
    session.add(occurrence)
    session.flush()
    session.refresh(occurrence)
    return occurrence


def get_automation_occurrence(
    session: Session, automation_id: uuid.UUID, occurrence_id: uuid.UUID
) -> AutomationOccurrence | None:
    return session.scalar(
        select(AutomationOccurrence).where(
            AutomationOccurrence.id == occurrence_id,
            AutomationOccurrence.automation_id == automation_id,
        )
    )


def list_automation_occurrences(
    session: Session, automation_id: uuid.UUID, *, limit: int, offset: int = 0
) -> list[AutomationOccurrence]:
    if get_automation(session, automation_id) is None:
        raise AutomationOwnershipError
    return list(
        session.scalars(
            select(AutomationOccurrence)
            .where(AutomationOccurrence.automation_id == automation_id)
            .order_by(
                AutomationOccurrence.scheduled_at.desc(),
                AutomationOccurrence.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )


def insert_automation_notification(
    session: Session, notification: AutomationNotification
) -> AutomationNotification:
    if get_automation(session, notification.automation_id) is None:
        raise AutomationOwnershipError
    if notification.occurrence_id is not None:
        occurrence = get_automation_occurrence(
            session, notification.automation_id, notification.occurrence_id
        )
        if occurrence is None:
            raise AutomationOwnershipError
    session.add(notification)
    session.flush()
    session.refresh(notification)
    return notification


def list_automation_notifications(
    session: Session, automation_id: uuid.UUID, *, limit: int, offset: int = 0
) -> list[AutomationNotification]:
    if get_automation(session, automation_id) is None:
        raise AutomationOwnershipError
    return list(
        session.scalars(
            select(AutomationNotification)
            .where(AutomationNotification.automation_id == automation_id)
            .order_by(
                AutomationNotification.created_at.desc(),
                AutomationNotification.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
