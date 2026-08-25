"""Caller-transaction-owned persistence primitives for Automation metadata."""

import uuid
from datetime import datetime

from sqlalchemy import and_, exists, func, not_, or_, select
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


def lock_due_automations(
    session: Session, *, now: datetime, limit: int
) -> list[Automation]:
    """Lock one deterministic bounded materialization batch without waiting."""

    return list(
        session.scalars(
            select(Automation)
            .where(
                Automation.lifecycle == "enabled",
                Automation.next_occurrence_at.is_not(None),
                Automation.next_occurrence_at <= now,
                ~exists(
                    select(AutomationOccurrence.id).where(
                        AutomationOccurrence.automation_id == Automation.id,
                        AutomationOccurrence.state.in_(
                            ("due", "claimed", "run_created")
                        ),
                        not_(
                            and_(
                                AutomationOccurrence.schedule_revision
                                == Automation.schedule_revision,
                                AutomationOccurrence.scheduled_at
                                == Automation.next_occurrence_at,
                            )
                        ),
                    )
                ),
            )
            .order_by(Automation.next_occurrence_at.asc(), Automation.id.asc())
            .limit(limit)
            .with_for_update(of=Automation, skip_locked=True)
        ).all()
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


def get_occurrence_by_slot(
    session: Session,
    *,
    automation_id: uuid.UUID,
    schedule_revision: int,
    scheduled_at: datetime,
) -> AutomationOccurrence | None:
    return session.scalar(
        select(AutomationOccurrence).where(
            AutomationOccurrence.automation_id == automation_id,
            AutomationOccurrence.schedule_revision == schedule_revision,
            AutomationOccurrence.scheduled_at == scheduled_at,
        )
    )


def lock_occurrence(
    session: Session, occurrence_id: uuid.UUID
) -> AutomationOccurrence | None:
    return session.scalar(
        select(AutomationOccurrence)
        .where(AutomationOccurrence.id == occurrence_id)
        .with_for_update(of=AutomationOccurrence)
    )


def lock_claimable_occurrences(
    session: Session, *, now: datetime, limit: int
) -> list[AutomationOccurrence]:
    """Lock eligible create-only work in stable due order without waiting."""

    return list(
        session.scalars(
            select(AutomationOccurrence)
            .join(Automation, Automation.id == AutomationOccurrence.automation_id)
            .where(
                AutomationOccurrence.state == "due",
                AutomationOccurrence.scheduled_at <= now,
                or_(
                    AutomationOccurrence.retry_not_before.is_(None),
                    AutomationOccurrence.retry_not_before <= now,
                ),
                AutomationOccurrence.execution_mode == "create_only",
                Automation.lifecycle == "enabled",
                Automation.revision == AutomationOccurrence.automation_revision,
                Automation.schedule_revision == AutomationOccurrence.schedule_revision,
            )
            .order_by(
                AutomationOccurrence.scheduled_at.asc(),
                AutomationOccurrence.id.asc(),
            )
            .limit(limit)
            .with_for_update(of=(Automation, AutomationOccurrence), skip_locked=True)
        ).all()
    )


def lock_claim_capacity(session: Session, lock_key: int) -> None:
    """Serialize the instance-wide claimed/run-created occurrence bound."""

    session.execute(select(func.pg_advisory_xact_lock(lock_key)))


def count_occurrences_in_states(session: Session, states: tuple[str, ...]) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(AutomationOccurrence)
            .where(AutomationOccurrence.state.in_(states))
        )
        or 0
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
