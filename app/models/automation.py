"""Inert persistence models for Local V1.3 Automation metadata."""

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


class Automation(Base):
    """One operator-owned, typed trigger definition with no execution behavior."""

    __tablename__ = "automations"
    __table_args__ = (
        CheckConstraint(
            "automation_kind = 'scheduled_agent'", name="ck_automations_kind"
        ),
        CheckConstraint(
            "agent_kind IN ('daily_brief','project_watch')",
            name="ck_automations_agent_kind",
        ),
        CheckConstraint("agent_version = '1'", name="ck_automations_agent_version"),
        CheckConstraint(
            "lifecycle IN ('draft','enabled','paused','cancelled')",
            name="ck_automations_lifecycle",
        ),
        CheckConstraint(
            "execution_mode IN ('create_only','automatic_read_only')",
            name="ck_automations_execution_mode",
        ),
        CheckConstraint(
            "schedule_kind IN ('one_time','daily','weekly')",
            name="ck_automations_schedule_kind",
        ),
        CheckConstraint(
            "nonexistent_time_policy = 'first_valid_after_gap'",
            name="ck_automations_nonexistent_policy",
        ),
        CheckConstraint(
            "ambiguous_time_policy = 'earlier_fold'",
            name="ck_automations_ambiguous_policy",
        ),
        CheckConstraint(
            "missed_run_policy IN ('skip','run_once')",
            name="ck_automations_missed_policy",
        ),
        CheckConstraint("revision >= 0", name="ck_automations_revision_nonnegative"),
        CheckConstraint(
            "schedule_revision >= 0",
            name="ck_automations_schedule_revision_nonnegative",
        ),
        CheckConstraint(
            "retry_limit BETWEEN 0 AND 3", name="ck_automations_retry_limit"
        ),
        CheckConstraint(
            "capacity_limit BETWEEN 1 AND 32", name="ck_automations_capacity_limit"
        ),
        CheckConstraint(
            "interval_count BETWEEN 1 AND 365", name="ck_automations_interval_count"
        ),
        CheckConstraint(
            "octet_length(timezone_name) BETWEEN 1 AND 255",
            name="ck_automations_timezone_size",
        ),
        CheckConstraint(
            "char_length(label) BETWEEN 1 AND 200",
            name="ck_automations_label_size",
        ),
        CheckConstraint(
            "cardinality(weekdays) <= 7 AND weekdays <@ ARRAY[1,2,3,4,5,6,7]",
            name="ck_automations_weekdays_shape",
        ),
        CheckConstraint(
            "(schedule_kind = 'one_time') = (one_time_local_date IS NOT NULL)",
            name="ck_automations_one_time_date",
        ),
        CheckConstraint(
            "(schedule_kind = 'weekly') = (cardinality(weekdays) > 0)",
            name="ck_automations_weekdays_required",
        ),
        CheckConstraint(
            "(lifecycle = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_automations_cancelled_timestamp",
        ),
        Index("ix_automations_due", "lifecycle", "next_occurrence_at", "id"),
        Index("ix_automations_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    automation_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="scheduled_agent",
        server_default="scheduled_agent",
    )
    agent_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1", server_default="1"
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    lifecycle: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    execution_mode: Mapped[str] = mapped_column(
        String(24), nullable=False, default="create_only", server_default="create_only"
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
    retry_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    capacity_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    schedule_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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

    occurrences: Mapped[list["AutomationOccurrence"]] = relationship(
        back_populates="automation", passive_deletes=True
    )
    notifications: Mapped[list["AutomationNotification"]] = relationship(
        back_populates="automation",
        passive_deletes=True,
        overlaps="notifications,occurrence",
    )


class AutomationOccurrence(Base):
    """One durable scheduled identity and future fenced work item."""

    __tablename__ = "automation_occurrences"
    __table_args__ = (
        CheckConstraint(
            "schedule_revision >= 0", name="ck_automation_occurrences_schedule_revision"
        ),
        CheckConstraint(
            "automation_revision >= 0",
            name="ck_automation_occurrences_automation_revision",
        ),
        CheckConstraint(
            "state IN ('due','claimed','run_created','completed','missed',"
            "'failed','cancelled')",
            name="ck_automation_occurrences_state",
        ),
        CheckConstraint("revision >= 0", name="ck_automation_occurrences_revision"),
        CheckConstraint(
            "attempt_count >= 0", name="ck_automation_occurrences_attempt_count"
        ),
        CheckConstraint(
            "lease_generation >= 0", name="ck_automation_occurrences_lease_generation"
        ),
        CheckConstraint(
            "automation_kind = 'scheduled_agent'", name="ck_automation_occurrences_kind"
        ),
        CheckConstraint(
            "agent_kind IN ('daily_brief','project_watch')",
            name="ck_automation_occurrences_agent_kind",
        ),
        CheckConstraint(
            "agent_version = '1'", name="ck_automation_occurrences_agent_version"
        ),
        CheckConstraint(
            "execution_mode IN ('create_only','automatic_read_only')",
            name="ck_automation_occurrences_execution_mode",
        ),
        CheckConstraint(
            "scheduled_utc_offset_minutes BETWEEN -840 AND 840",
            name="ck_automation_occurrences_utc_offset",
        ),
        CheckConstraint(
            "(lease_owner_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_automation_occurrences_lease_pair",
        ),
        CheckConstraint(
            "last_renewed_at IS NULL OR lease_owner_token IS NOT NULL",
            name="ck_automation_occurrences_renewed_lease",
        ),
        CheckConstraint(
            "claimed_at IS NULL OR claimed_at >= created_at",
            name="ck_automation_occurrences_claimed_order",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_automation_occurrences_completed_order",
        ),
        CheckConstraint(
            "(state IN ('completed','missed','failed','cancelled')) = "
            "(completed_at IS NOT NULL)",
            name="ck_automation_occurrences_terminal_completed",
        ),
        UniqueConstraint(
            "automation_id",
            "schedule_revision",
            "scheduled_at",
            name="uq_automation_occurrences_schedule_slot",
        ),
        UniqueConstraint("occurrence_key", name="uq_automation_occurrences_key"),
        UniqueConstraint(
            "id", "automation_id", name="uq_automation_occurrences_id_automation"
        ),
        UniqueConstraint("agent_run_id", name="uq_automation_occurrences_agent_run"),
        Index(
            "ix_automation_occurrences_due",
            "state",
            "retry_not_before",
            "scheduled_at",
            "id",
        ),
        Index(
            "ix_automation_occurrences_automation_created",
            "automation_id",
            "created_at",
            "id",
        ),
        Index("ix_automation_occurrences_lease", "state", "lease_expires_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automations.id", ondelete="RESTRICT"),
        nullable=False,
    )
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
    occurrence_key: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="due", server_default="due"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    safe_disposition_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    retry_not_before: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    automation_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    automation_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    automation_label: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )

    automation: Mapped[Automation] = relationship(back_populates="occurrences")
    notifications: Mapped[list["AutomationNotification"]] = relationship(
        back_populates="occurrence",
        passive_deletes=True,
        overlaps="automation,notifications",
    )


class AutomationNotification(Base):
    """One append-only, safe local inbox record."""

    __tablename__ = "automation_notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["occurrence_id", "automation_id"],
            ["automation_occurrences.id", "automation_occurrences.automation_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "event_kind IN ('occurrence_missed','occurrence_failed',"
            "'retry_exhausted','lifecycle_race','capacity_delayed','run_completed')",
            name="ck_automation_notifications_event_kind",
        ),
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_automation_notifications_severity",
        ),
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200 AND "
            "char_length(body) BETWEEN 1 AND 1000 AND "
            "char_length(deduplication_key) BETWEEN 1 AND 500",
            name="ck_automation_notifications_safe_sizes",
        ),
        UniqueConstraint(
            "deduplication_key", name="uq_automation_notifications_deduplication_key"
        ),
        Index("ix_automation_notifications_inbox", "read_at", "created_at", "id"),
        Index(
            "ix_automation_notifications_automation_created",
            "automation_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deduplication_key: Mapped[str] = mapped_column(String(500), nullable=False)

    automation: Mapped[Automation] = relationship(
        back_populates="notifications", overlaps="notifications,occurrence"
    )
    occurrence: Mapped[AutomationOccurrence | None] = relationship(
        back_populates="notifications", overlaps="automation,notifications"
    )
