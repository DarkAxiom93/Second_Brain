"""Caller-transaction-owned connector schedule persistence primitives."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connector_schedule import (
    ConnectorRefreshNotification,
    ConnectorRefreshOccurrence,
    ConnectorRefreshSchedule,
)


def get_schedule(
    session: Session, schedule_id: uuid.UUID
) -> ConnectorRefreshSchedule | None:
    return session.get(ConnectorRefreshSchedule, schedule_id)


def get_account_schedule(
    session: Session, account_id: uuid.UUID
) -> ConnectorRefreshSchedule | None:
    return session.scalar(
        select(ConnectorRefreshSchedule).where(
            ConnectorRefreshSchedule.account_id == account_id
        )
    )


def lock_schedule(
    session: Session, schedule_id: uuid.UUID
) -> ConnectorRefreshSchedule | None:
    return session.scalar(
        select(ConnectorRefreshSchedule)
        .where(ConnectorRefreshSchedule.id == schedule_id)
        .with_for_update()
    )


def lock_due_schedules(
    session: Session, now: datetime, limit: int
) -> list[ConnectorRefreshSchedule]:
    return list(
        session.scalars(
            select(ConnectorRefreshSchedule)
            .where(
                ConnectorRefreshSchedule.lifecycle == "enabled",
                ConnectorRefreshSchedule.next_occurrence_at.is_not(None),
                ConnectorRefreshSchedule.next_occurrence_at <= now,
            )
            .order_by(
                ConnectorRefreshSchedule.next_occurrence_at, ConnectorRefreshSchedule.id
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def lock_claimable(
    session: Session, now: datetime, limit: int
) -> list[ConnectorRefreshOccurrence]:
    return list(
        session.scalars(
            select(ConnectorRefreshOccurrence)
            .where(
                ConnectorRefreshOccurrence.state == "due",
                ConnectorRefreshOccurrence.scheduled_at <= now,
            )
            .order_by(
                ConnectorRefreshOccurrence.scheduled_at, ConnectorRefreshOccurrence.id
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def lock_expired(
    session: Session, now: datetime, limit: int
) -> list[ConnectorRefreshOccurrence]:
    return list(
        session.scalars(
            select(ConnectorRefreshOccurrence)
            .where(
                ConnectorRefreshOccurrence.state == "claimed",
                ConnectorRefreshOccurrence.connector_sync_run_id.is_(None),
                ConnectorRefreshOccurrence.lease_expires_at <= now,
            )
            .order_by(
                ConnectorRefreshOccurrence.lease_expires_at,
                ConnectorRefreshOccurrence.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def lock_resumable(
    session: Session, now: datetime, limit: int
) -> list[ConnectorRefreshOccurrence]:
    return list(
        session.scalars(
            select(ConnectorRefreshOccurrence)
            .where(
                ConnectorRefreshOccurrence.state == "sync_created",
                ConnectorRefreshOccurrence.connector_sync_run_id.is_not(None),
                ConnectorRefreshOccurrence.lease_expires_at <= now,
            )
            .order_by(
                ConnectorRefreshOccurrence.lease_expires_at,
                ConnectorRefreshOccurrence.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def lock_occurrence(
    session: Session, occurrence_id: uuid.UUID
) -> ConnectorRefreshOccurrence | None:
    return session.scalar(
        select(ConnectorRefreshOccurrence)
        .where(ConnectorRefreshOccurrence.id == occurrence_id)
        .with_for_update()
    )


def list_history(
    session: Session, schedule_id: uuid.UUID, limit: int, offset: int
) -> list[ConnectorRefreshOccurrence]:
    return list(
        session.scalars(
            select(ConnectorRefreshOccurrence)
            .where(ConnectorRefreshOccurrence.schedule_id == schedule_id)
            .order_by(
                ConnectorRefreshOccurrence.created_at.desc(),
                ConnectorRefreshOccurrence.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )


def list_notifications(
    session: Session, schedule_id: uuid.UUID, limit: int, offset: int
) -> list[ConnectorRefreshNotification]:
    return list(
        session.scalars(
            select(ConnectorRefreshNotification)
            .where(ConnectorRefreshNotification.schedule_id == schedule_id)
            .order_by(
                ConnectorRefreshNotification.created_at.desc(),
                ConnectorRefreshNotification.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
