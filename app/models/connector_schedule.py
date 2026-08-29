"""Connector-owned refresh schedule persistence; never Agent Automation state."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConnectorRefreshSchedule(Base):
    __tablename__ = "connector_refresh_schedules"
    __table_args__ = (
        CheckConstraint(
            "provider = 'github'", name="ck_connector_refresh_schedules_provider"
        ),
        CheckConstraint(
            "lifecycle IN ('draft','enabled','paused','cancelled')",
            name="ck_connector_refresh_schedules_lifecycle",
        ),
        CheckConstraint(
            "revision >= 0 AND schedule_revision >= 0",
            name="ck_connector_refresh_schedules_revisions",
        ),
        CheckConstraint(
            "schedule_kind IN ('one_time','daily','weekly')",
            name="ck_connector_refresh_schedules_kind",
        ),
        CheckConstraint(
            "interval_count = 1", name="ck_connector_refresh_schedules_interval"
        ),
        CheckConstraint(
            "nonexistent_time_policy = 'first_valid_after_gap'",
            name="ck_connector_refresh_schedules_nonexistent",
        ),
        CheckConstraint(
            "ambiguous_time_policy = 'earlier_fold'",
            name="ck_connector_refresh_schedules_ambiguous",
        ),
        CheckConstraint(
            "missed_run_policy IN ('skip','run_once')",
            name="ck_connector_refresh_schedules_missed",
        ),
        CheckConstraint(
            "octet_length(timezone_name) BETWEEN 1 AND 255",
            name="ck_connector_refresh_schedules_timezone",
        ),
        CheckConstraint(
            "(schedule_kind = 'one_time') = (one_time_local_date IS NOT NULL)",
            name="ck_connector_refresh_schedules_one_time",
        ),
        CheckConstraint(
            "(schedule_kind = 'weekly') = (cardinality(weekdays) > 0)",
            name="ck_connector_refresh_schedules_weekly",
        ),
        CheckConstraint(
            "cardinality(weekdays) <= 7 AND "
            "weekdays <@ ARRAY[1,2,3,4,5,6,7] AND "
            "cardinality(array_positions(weekdays,1)) <= 1 AND "
            "cardinality(array_positions(weekdays,2)) <= 1 AND "
            "cardinality(array_positions(weekdays,3)) <= 1 AND "
            "cardinality(array_positions(weekdays,4)) <= 1 AND "
            "cardinality(array_positions(weekdays,5)) <= 1 AND "
            "cardinality(array_positions(weekdays,6)) <= 1 AND "
            "cardinality(array_positions(weekdays,7)) <= 1",
            name="ck_connector_refresh_schedules_weekdays",
        ),
        CheckConstraint(
            "(lifecycle = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_connector_refresh_schedules_cancelled",
        ),
        UniqueConstraint("account_id", name="uq_connector_refresh_schedules_account"),
        UniqueConstraint(
            "id", "account_id", "provider", name="uq_connector_refresh_schedules_owner"
        ),
        Index(
            "ix_connector_refresh_schedules_due",
            "lifecycle",
            "next_occurrence_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="github", server_default="github"
    )
    lifecycle: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    schedule_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    schedule_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(255), nullable=False)
    local_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    one_time_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list, server_default="{}"
    )
    interval_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    nonexistent_time_policy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="first_valid_after_gap",
        server_default="first_valid_after_gap",
    )
    ambiguous_time_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="earlier_fold",
        server_default="earlier_fold",
    )
    missed_run_policy: Mapped[str] = mapped_column(
        String(16), nullable=False, default="skip", server_default="skip"
    )
    next_occurrence_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    occurrences: Mapped[list["ConnectorRefreshOccurrence"]] = relationship(
        back_populates="schedule", passive_deletes=True
    )


class ConnectorRefreshOccurrence(Base):
    __tablename__ = "connector_refresh_occurrences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["schedule_id", "account_id", "provider"],
            [
                "connector_refresh_schedules.id",
                "connector_refresh_schedules.account_id",
                "connector_refresh_schedules.provider",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["connector_sync_run_id", "account_id", "provider"],
            [
                "connector_sync_runs.id",
                "connector_sync_runs.account_id",
                "connector_sync_runs.provider",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "provider = 'github'", name="ck_connector_refresh_occurrences_provider"
        ),
        CheckConstraint(
            "account_revision >= 0 AND schedule_revision >= 0 AND "
            "schedule_row_revision >= 0 AND revision >= 0",
            name="ck_connector_refresh_occurrences_revisions",
        ),
        CheckConstraint(
            "state IN ('due','claimed','sync_created','succeeded','incomplete',"
            "'failed','missed','cancelled')",
            name="ck_connector_refresh_occurrences_state",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND lease_generation >= 0",
            name="ck_connector_refresh_occurrences_attempt_lease",
        ),
        CheckConstraint(
            "scheduled_utc_offset_minutes BETWEEN -840 AND 840",
            name="ck_connector_refresh_occurrences_offset",
        ),
        CheckConstraint(
            "(lease_owner_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_connector_refresh_occurrences_lease_pair",
        ),
        CheckConstraint(
            "last_renewed_at IS NULL OR lease_owner_token IS NOT NULL",
            name="ck_connector_refresh_occurrences_renewed",
        ),
        CheckConstraint(
            "(state IN ('succeeded','incomplete','failed','missed','cancelled')) "
            "= (completed_at IS NOT NULL)",
            name="ck_connector_refresh_occurrences_terminal",
        ),
        UniqueConstraint(
            "schedule_id",
            "schedule_revision",
            "scheduled_at",
            name="uq_connector_refresh_occurrences_slot",
        ),
        UniqueConstraint("occurrence_key", name="uq_connector_refresh_occurrences_key"),
        UniqueConstraint(
            "connector_sync_run_id", name="uq_connector_refresh_occurrences_sync"
        ),
        UniqueConstraint(
            "id", "schedule_id", name="uq_connector_refresh_occurrences_owner"
        ),
        Index("ix_connector_refresh_occurrences_due", "state", "scheduled_at", "id"),
        Index(
            "ix_connector_refresh_occurrences_lease", "state", "lease_expires_at", "id"
        ),
        Index(
            "ix_connector_refresh_occurrences_history",
            "schedule_id",
            "created_at",
            "id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="github", server_default="github"
    )
    account_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_row_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_local_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_local_time: Mapped[time] = mapped_column(
        Time(timezone=False), nullable=False
    )
    scheduled_utc_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_key: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="due", server_default="due"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    safe_disposition_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    connector_sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    lease_owner_token: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    lease_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_renewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schedule: Mapped[ConnectorRefreshSchedule] = relationship(
        back_populates="occurrences"
    )


class ConnectorRefreshNotification(Base):
    __tablename__ = "connector_refresh_notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["occurrence_id", "schedule_id"],
            [
                "connector_refresh_occurrences.id",
                "connector_refresh_occurrences.schedule_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "event_kind IN ('occurrence_missed','occurrence_succeeded',"
            "'occurrence_incomplete','occurrence_failed','occurrence_cancelled')",
            name="ck_connector_refresh_notifications_event",
        ),
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_connector_refresh_notifications_severity",
        ),
        CheckConstraint(
            "status_code ~ '^[a-z][a-z0-9_]{0,99}$' AND "
            "deduplication_key ~ '^[a-z0-9:_-]{1,200}$'",
            name="ck_connector_refresh_notifications_safe",
        ),
        UniqueConstraint(
            "deduplication_key", name="uq_connector_refresh_notifications_dedup"
        ),
        Index(
            "ix_connector_refresh_notifications_inbox", "read_at", "created_at", "id"
        ),
        Index(
            "ix_connector_refresh_notifications_schedule",
            "schedule_id",
            "created_at",
            "id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    occurrence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status_code: Mapped[str] = mapped_column(String(100), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
